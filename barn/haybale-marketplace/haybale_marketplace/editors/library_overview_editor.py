# packages/haywire-app/src/haywire_studio/editors/library_overview_editor.py
"""
LibraryOverviewEditor — full center-panel port from LibraryManagerPage.

Renders in the middle area and reacts to LIBRARY_STATE_CHANGED events.
Receives the active library via context.active_library (InstalledLibrary or
Haybale). All services are retrieved from
context.app (= HaywireApp).

When a component (node/widget/type/adapter/renderer) is clicked, the editor
sets context.active_component (which synthetically emits
SessionContext.active_component on the bus) so that the right-panel
ComponentDetailEditor can react.
"""

import asyncio
import dataclasses
import logging
import re
import toml
from functools import partial
from pathlib import Path
from typing import TYPE_CHECKING

from nicegui import ui
from nicegui import background_tasks

from haywire.ui import elements as hui
from haywire.core.adapter.registry import AdapterRegistry
from haywire.core.node.registry import NodeRegistry
from haywire.core.settings import SettingsRegistry
from haywire.core.state import LibraryStateRegistry
from haywire.core.types.registry import TypeRegistry
from haywire.core.library.utils import (
    ADAPTER,
    EDITOR,
    NODE,
    PANEL,
    SETTING,
    SKIN,
    STATE,
    THEME,
    TYPE,
    WIDGET,
)
from haywire.ui.editor.decorator import editor
from haywire.ui.editor.base import BaseEditor
from haywire.ui.editor.registry import EditorTypeRegistry
from haywire.ui.panel.registry import PanelRegistry
from haywire.ui.skin.registry import SkinRegistry
from haywire.ui.themes import ThemeRegistry
from haywire.core.session.context import SessionContext
from haywire.core.session.handlers import redraw_on
from haywire.core.session.signals import (
    LibraryCatalogChanged,
)

from haywire.core.library.info import LibraryInfo
from haywire.core.marketstall import Haybale
from haywire.ui.modals import confirm_modal, info_modal

from haywire.ui.widget.registry import WidgetRegistry

if TYPE_CHECKING:
    from nicegui.element import Element


# ─────────────────────────────────────────────────────────────────────────────
# TabConfig — per-component-type display descriptor
# ─────────────────────────────────────────────────────────────────────────────


logger = logging.getLogger(__name__)


@dataclasses.dataclass
class TabConfig:
    comp_type: str  # plural label for empty/error messages
    prefix_segment: str  # registry key segment (e.g. 'node', 'widget')


_CFG_NODES = TabConfig("nodes", NODE)
_CFG_WIDGETS = TabConfig("widgets", WIDGET)
_CFG_TYPES = TabConfig("types", TYPE)
_CFG_ADAPTERS = TabConfig("adapters", ADAPTER)
_CFG_SKINS = TabConfig("skins", SKIN)
_CFG_SETTINGS = TabConfig("settings", SETTING)
_CFG_STATES = TabConfig("states", STATE)
_CFG_THEMES = TabConfig("themes", THEME)
_CFG_PANELS = TabConfig("panels", PANEL)
_CFG_EDITORS = TabConfig("editors", EDITOR)


def should_block_install_for_os(haybale) -> str | None:
    """Per spec §2.1: return a tooltip message when the current OS doesn't match.

    Returns None when the haybale supports all platforms (empty os) or
    includes the current OS. The return value (string or None) drives the
    Install button's locked/unlocked state in the UI.
    """
    from haywire.core.marketstall import haybale_supports_current_os

    if haybale_supports_current_os(haybale):
        return None
    targets = ", ".join(getattr(haybale, "os", []) or [])
    return f"Not available on this OS; this library targets: {targets}."


@editor(
    label="Library Detail",
    icon=hui.icon.node_info,
    default_slot="main",
    opens="on_context",
    description="Detailed information for the selected library.",
)
class LibraryOverviewEditor(BaseEditor):
    """
    Full center-panel port of LibraryManagerPage.

    Displays:
    - Fixed header: name, version, dist name, badges, action buttons, metadata
    - Scrollable content: tabs (Overview, Nodes, Widgets, Types, Adapters,
      Renderers) for installed libraries, or async overview for marketplace-only.

    Rebuilds on LIBRARY_STATE_CHANGED.
    """

    def __init__(self, wrapper):
        super().__init__(wrapper)
        self._container: "Element | None" = None
        # Fixed (non-scrolling) sub-container — header + metadata + tabs bar
        self._fixed: "ui.column | None" = None
        # Scrollable sub-container — tab panels / placeholder
        self._scroll: "ui.column | None" = None

    # ─────────────────────────────────────────────────────────────────────────
    # Public editor interface
    # ─────────────────────────────────────────────────────────────────────────

    @redraw_on(SessionContext.active_library, LibraryCatalogChanged)
    def _refresh_on_library_change(self, context: "SessionContext", event) -> None:
        # Empty body — the decorator triggers wrapper.redraw() after return.
        pass

    def draw(self, context: "SessionContext", container: "Element") -> None:
        self._container = container
        self._rebuild(context)

    # ─────────────────────────────────────────────────────────────────────────
    # Top-level rebuild
    # ─────────────────────────────────────────────────────────────────────────

    def _rebuild(self, context: "SessionContext") -> None:
        if self._container is None:
            return

        lib = context.active_library
        with self._container:
            with (
                ui.column()
                .classes("w-full gap-0")
                .style("height: 100%; display: flex; flex-direction: column;")
            ):
                self._fixed = ui.column().classes("w-full gap-0").style("flex-shrink: 0;")
                self._scroll = (
                    ui.column().classes("w-full gap-0").style("flex: 1; min-height: 0; overflow: hidden;")
                )

        if lib is None:
            self._render_placeholder()
            return

        if isinstance(lib, LibraryInfo):
            self._render_center(lib, None, context)
        elif isinstance(lib, Haybale):
            self._render_center(None, lib, context)
        else:
            self._render_placeholder()

    def _render_placeholder(self):
        """Placeholder shown when nothing is selected."""
        if self._scroll:
            self._scroll.clear()
            with self._scroll:
                hui.empty_state("Select a library to view details", icon=hui.icon.library)

    # ─────────────────────────────────────────────────────────────────────────
    # Center panel — unified renderer
    # ─────────────────────────────────────────────────────────────────────────

    def _render_center(
        self,
        installed_lib: LibraryInfo | None,
        marketplace_pkg: Haybale | None,
        context: "SessionContext",
    ):
        """
        Unified center panel renderer.

        - installed_lib only  → installed header + tabs
        - installed_lib + pkg → marketplace header with installed badges + tabs
        - pkg only            → marketplace header + Install button, no tabs
        """
        # _rebuild() creates _fixed and _scroll before calling this method —
        # narrow them here so the body can use the columns directly.
        assert self._fixed is not None and self._scroll is not None, (
            "_render_center called before _rebuild created the sub-containers"
        )

        # Resolve registries from context
        from haybale_marketplace.state.library_manager_state import LibraryManagerState

        app = context.app
        svc = app.library_service
        manager_state = context.app_data.get(LibraryManagerState)
        manager = manager_state.manager if manager_state is not None else None
        if manager is None:
            ui.label("Library manager not available").classes("hw-text-dim")
            return
        node_registry: NodeRegistry = svc.get_node_registry()
        widget_registry: WidgetRegistry = svc.get_widget_registry()
        type_registry: TypeRegistry = svc.get_type_registry()
        adapter_registry: AdapterRegistry = svc.get_adapter_registry()
        skin_registry: SkinRegistry = svc.get_skin_registry()
        settings_registry: SettingsRegistry = svc.get_settings_registry()
        theme_registry: ThemeRegistry = svc.get_theme_registry()
        panel_registry: PanelRegistry = svc.get_panel_registry()
        editor_registry: EditorTypeRegistry = svc.get_editor_registry()
        state_registry: LibraryStateRegistry = svc.get_state_registry()

        marketplace_path = str(Path(app.workspace_root) / ".haywire" / "marketplace.toml")

        # Determine display properties
        if installed_lib:
            name = installed_lib.identity.label
            version = installed_lib.identity.version
            description = installed_lib.identity.description
            author = installed_lib.identity.author
            tags = installed_lib.identity.tags or (marketplace_pkg.tags if marketplace_pkg else []) or []
        else:
            assert marketplace_pkg is not None
            name = marketplace_pkg.label or marketplace_pkg.name
            version = marketplace_pkg.min_version
            description = marketplace_pkg.description
            author = marketplace_pkg.author
            tags = marketplace_pkg.tags or []

        # Check for available update
        update_available = False
        if (
            marketplace_pkg
            and installed_lib
            and marketplace_pkg.min_version
            and installed_lib.identity.version
        ):
            try:
                from packaging.version import Version

                update_available = Version(marketplace_pkg.min_version) > Version(
                    installed_lib.identity.version
                )
            except Exception:
                pass

        # Tab references — created in fixed section, used in scroll section
        tabs = t_overview = t_nodes = t_widgets = None
        t_types = t_adapters = t_skins = None
        t_settings = t_states = t_themes = t_panels = t_editors = None

        # Pre-compute component counts (for tab disable state)
        def _count(registry, prefix: str) -> int:
            if not registry:
                return 0
            return sum(1 for k in registry.list_names() if k.startswith(prefix))

        lib_id = installed_lib.identity.id if installed_lib else None

        # ── header + metadata + tabs bar ───────────────────────
        self._fixed.clear()
        with self._fixed:
            with ui.column().classes("w-full px-6 pt-6 min-w-0 gap-1"):
                # ── Header ────────────────────────────────────────────────────
                with ui.row().classes("w-full items-start justify-between mb-2"):
                    with ui.column().classes("gap-0.5 min-w-0 flex-1"):
                        _title_url = (installed_lib.identity.url if installed_lib else "") or ""
                        if _title_url.startswith("http"):
                            with ui.row().classes("items-center gap-1"):
                                ui.label(name).classes("text-2xl font-bold")
                                with ui.link(target=_title_url, new_tab=True).style("line-height:0"):
                                    ui.icon("open_in_new", size="16px").classes("hw-text-accent opacity-60")
                        else:
                            ui.label(name).classes("text-2xl font-bold break-words")

                        with ui.row().classes("items-center gap-2 mt-1 flex-wrap"):
                            ui.label(f"v{version}").classes("text-sm hw-text-muted")
                            _dist_name = (installed_lib.distribution_name if installed_lib else None) or (
                                marketplace_pkg.name if marketplace_pkg else None
                            )
                            if _dist_name:
                                ui.label(_dist_name).classes("text-xs hw-text-muted font-mono")
                            if installed_lib:
                                inst_color = {
                                    "EDITABLE": "purple",
                                    "REGULAR": "blue",
                                    "FOLDER": "teal",
                                }.get(installed_lib.install_type.name, "grey")
                                hui.tag(installed_lib.install_type.name.lower(), color=inst_color)
                            if marketplace_pkg:
                                src_color = "blue" if marketplace_pkg.source == "pypi" else "purple"
                                hui.tag(marketplace_pkg.source, color=src_color)
                            if update_available and marketplace_pkg:
                                hui.tag(f"v{marketplace_pkg.min_version} available", color="orange")

                    # ── Action buttons ─────────────────────────────────────────
                    with ui.row().classes("gap-1 flex-shrink-0 items-center"):
                        if installed_lib and manager:
                            _is_project = self._is_project_library(installed_lib, marketplace_path)
                            _lib_id = installed_lib.identity.id
                            _lib_label = installed_lib.identity.label

                            # Dependents: all installed libs whose @library deps include me
                            _dependents = manager.get_installed_dependents(_lib_id)
                            _enabled_dependents = [d for d in _dependents if d.enabled]
                            # My unmet deps (installed = for enable, installed = for install)
                            _missing_for_enable = manager.get_missing_dependencies(
                                _lib_id, require_enabled=True
                            )

                            # Rules:
                            # disable  → blocked if any enabled dependent
                            # uninstall → blocked if any dependent (enabled or not)
                            # enable   → blocked if any dependency not enabled
                            _block_disable = _enabled_dependents
                            _block_uninstall = _dependents
                            _block_enable = _missing_for_enable

                            # Enable / Disable toggle
                            if installed_lib.enabled:
                                if _block_disable:
                                    _names = ", ".join(f'"{d.identity.label}"' for d in _block_disable)
                                    _msg = f'"{_lib_label}" cannot be disabled — {_names} depend on it.'
                                    _detail = "Disable all dependents first."
                                    ui.button(
                                        "Disable",
                                        icon=hui.icon.locked,
                                        on_click=lambda m=_msg, d=_detail: info_modal(
                                            title="Cannot Disable Library",
                                            icon="lock",
                                            message=m,
                                            detail=d,
                                        ),
                                    ).props("size=sm color=orange flat")
                                else:
                                    ui.button(
                                        "Disable",
                                        icon=hui.icon.pause,
                                        on_click=lambda lid=_lib_id, ctx=context: (
                                            self._disable_library(lid, manager, ctx)
                                        ),
                                    ).props("size=sm color=orange flat")
                            else:
                                if _block_enable:
                                    _names = ", ".join(f'"{d}"' for d in _block_enable)
                                    _msg = (
                                        f'"{_lib_label}" cannot be enabled — {_names} must be enabled first.'
                                    )
                                    ui.button(
                                        "Enable",
                                        icon=hui.icon.locked,
                                        on_click=lambda m=_msg: info_modal(
                                            title="Cannot Enable Library",
                                            icon="lock",
                                            message=m,
                                        ),
                                    ).props("size=sm color=green flat")
                                else:
                                    ui.button(
                                        "Enable",
                                        icon=hui.icon.resume,
                                        on_click=lambda lid=_lib_id, ctx=context: (
                                            self._enable_library(lid, manager, ctx)
                                        ),
                                    ).props("size=sm color=green flat")

                            # Edit (project library) or Uninstall dropdown
                            if _is_project:
                                ui.button(
                                    "Edit",
                                    icon=hui.icon.edit,
                                    on_click=lambda ilib=installed_lib,
                                    mp=marketplace_path,
                                    m=manager,
                                    ctx=context: (self._build_edit_dialog(ilib, mp, m, ctx).open()),
                                ).props("size=sm color=blue flat")
                            elif installed_lib.install_type.name in ("REGULAR", "EDITABLE"):
                                if _block_uninstall:
                                    _names = ", ".join(f'"{d.identity.label}"' for d in _block_uninstall)
                                    _msg = f'"{_lib_label}" cannot be uninstalled — {_names} depend on it.'
                                    _detail = "Uninstall all dependents first."
                                    ui.button(
                                        "Uninstall",
                                        icon=hui.icon.locked,
                                        on_click=lambda m=_msg, d=_detail: info_modal(
                                            title="Cannot Uninstall Library",
                                            icon="lock",
                                            message=m,
                                            detail=d,
                                        ),
                                    ).props("size=sm color=negative flat")
                                else:
                                    with ui.row().classes("gap-0 items-center"):
                                        ui.button(
                                            "Uninstall",
                                            on_click=lambda lid=_lib_id,
                                            ln=_lib_label,
                                            m=manager,
                                            ctx=context: (self._confirm_uninstall(lid, ln, m, ctx)),
                                        ).props("size=sm color=negative flat")
                                        with ui.button(icon=hui.icon.dropdown).props(
                                            "size=sm color=negative flat"
                                        ):
                                            with ui.menu():
                                                if update_available and marketplace_pkg:
                                                    ui.menu_item(
                                                        f"Update to v{marketplace_pkg.min_version}",
                                                        on_click=lambda e,
                                                        spec=marketplace_pkg.install_spec,
                                                        n=marketplace_pkg.name,
                                                        m=manager,
                                                        ctx=context: (
                                                            self._install_package(spec, n, e.sender, m, ctx)
                                                        ),
                                                    )
                                                if marketplace_pkg:
                                                    ui.menu_item(
                                                        "Install specific version…",
                                                        on_click=lambda p=marketplace_pkg,
                                                        m=manager,
                                                        ctx=context: (self._open_version_picker(p, m, ctx)),
                                                    )
                                                ui.separator()
                                                ui.menu_item(
                                                    "Uninstall permanently",
                                                    on_click=lambda lid=_lib_id,
                                                    ln=_lib_label,
                                                    m=manager,
                                                    ctx=context: (self._confirm_uninstall(lid, ln, m, ctx)),
                                                )
                        elif not installed_lib and marketplace_pkg and manager:
                            # Not installed — Install button, blocked if deps missing OR OS doesn't match
                            _installed_ids = {
                                manager._norm(lib.distribution_name or lib.identity.id)
                                for lib in manager.list_installed()
                            }
                            _missing_deps = [
                                dep
                                for dep in (marketplace_pkg.dependencies or [])
                                if manager._norm(dep) not in _installed_ids
                            ]
                            _os_block_msg = should_block_install_for_os(marketplace_pkg)

                            if _missing_deps:
                                _names = ", ".join(f'"{d}"' for d in _missing_deps)
                                _msg = (
                                    f'"{marketplace_pkg.label or marketplace_pkg.name}"'
                                    f" cannot be installed — {_names} must be installed first."
                                )
                                ui.button(
                                    "Install",
                                    icon=hui.icon.locked,
                                    on_click=lambda m=_msg: info_modal(
                                        title="Cannot Install Library",
                                        icon="lock",
                                        message=m,
                                    ),
                                ).props("color=positive size=sm")
                            elif _os_block_msg:
                                ui.button(
                                    "Install",
                                    icon=hui.icon.locked,
                                    on_click=lambda m=_os_block_msg: info_modal(
                                        title="Not available on this OS",
                                        icon="block",
                                        message=m,
                                    ),
                                ).props("color=positive size=sm").tooltip(_os_block_msg)
                            else:
                                ui.button(
                                    "Install",
                                    icon=hui.icon.download,
                                    on_click=lambda e, pkg=marketplace_pkg, m=manager, ctx=context: (
                                        self._install_with_safety_check(pkg, e.sender, m, ctx)
                                    ),
                                ).props("color=positive size=sm")

                # ── Metadata ───────────────────────────────────────────────────
                if description:
                    ui.label(description).classes("hw-text-muted text-sm mb-1")
                if author:
                    _author_url = (installed_lib.identity.author_url if installed_lib else "") or ""
                    if _author_url.startswith("http"):
                        with ui.row().classes("items-center gap-1"):
                            ui.label("By").classes("text-xs hw-text-dim")
                            ui.link(author, _author_url, new_tab=True).classes("text-xs hw-text-accent")
                    else:
                        ui.label(f"By {author}").classes("text-xs hw-text-dim")

                # Collect relevant links
                _links: list[tuple[str, str]] = []
                if marketplace_pkg and marketplace_pkg.source_url:
                    _links.append(("Source", marketplace_pkg.source_url))
                if (
                    marketplace_pkg
                    and marketplace_pkg.docs_url
                    and marketplace_pkg.docs_url.startswith("http")
                ):
                    _links.append(("Docs", marketplace_pkg.docs_url))
                if _links:
                    with ui.row().classes("items-center gap-3 mt-1 flex-wrap"):
                        for _lbl, _href in _links:
                            with ui.row().classes("items-center gap-0.5"):
                                ui.link(_lbl, _href, new_tab=True).classes("text-xs hw-text-accent")
                                ui.icon("open_in_new", size="10px").classes("hw-text-accent opacity-70")
                if tags:
                    with ui.row().classes("gap-1 mt-2 flex-wrap"):
                        for tag in tags:
                            hui.tag(tag)

                # ── Tabs bar (only when library is installed) ──────────────────
                if installed_lib:
                    n_nodes = _count(node_registry, f"{lib_id}:{NODE}:")
                    n_widgets = _count(widget_registry, f"{lib_id}:{WIDGET}:")
                    n_types = _count(type_registry, f"{lib_id}:{TYPE}:")
                    n_adapters = _count(adapter_registry, f"{lib_id}:{ADAPTER}:")
                    n_skins = _count(skin_registry, f"{lib_id}:{SKIN}:")
                    n_settings = _count(settings_registry, f"{lib_id}:{SETTING}:")
                    n_themes = _count(theme_registry, f"{lib_id}:{THEME}:")
                    n_panels = _count(panel_registry, f"{lib_id}:{PANEL}:")
                    n_editors = _count(editor_registry, f"{lib_id}:{EDITOR}:")
                    n_states = _count(state_registry, f"{lib_id}:{STATE}:")

                    ui.separator().classes("mt-4")
                    with ui.tabs().classes("w-full hw-tabs").props("dense no-caps") as tabs:
                        t_overview = ui.tab("Overview", icon=hui.icon.library_component)
                        t_nodes = ui.tab("Nodes", icon=hui.icon.node) if n_nodes else None
                        t_widgets = ui.tab("Widgets", icon=hui.icon.widget) if n_widgets else None
                        t_types = ui.tab("Types", icon=hui.icon.type) if n_types else None
                        t_adapters = ui.tab("Adapters", icon=hui.icon.adapter) if n_adapters else None
                        t_skins = ui.tab("Skins", icon=hui.icon.skin) if n_skins else None
                        t_settings = ui.tab("Settings", icon=hui.icon.node_settings) if n_settings else None
                        t_states = ui.tab("States", icon="data_object") if n_states else None
                        t_themes = ui.tab("Themes", icon=hui.icon.theme) if n_themes else None
                        t_panels = ui.tab("Panels", icon=hui.icon.panel) if n_panels else None
                        t_editors = ui.tab("Editors", icon=hui.icon.editor) if n_editors else None

        # ── Scrollable section: tab panels / placeholder ──────────────────────
        self._scroll.clear()
        with self._scroll:
            if installed_lib and tabs is not None:
                with ui.tab_panels(tabs, value=t_overview).classes("w-full").style("height: 100%;"):
                    self._make_tab_panel(t_overview, self._render_overview, installed_lib)
                    if t_nodes:
                        self._make_tab_panel(
                            t_nodes,
                            self._render_component_tab,
                            installed_lib,
                            node_registry,
                            _CFG_NODES,
                            context,
                        )
                    if t_widgets:
                        self._make_tab_panel(
                            t_widgets,
                            self._render_component_tab,
                            installed_lib,
                            widget_registry,
                            _CFG_WIDGETS,
                            context,
                        )
                    if t_types:
                        self._make_tab_panel(
                            t_types,
                            self._render_component_tab,
                            installed_lib,
                            type_registry,
                            _CFG_TYPES,
                            context,
                        )
                    if t_adapters:
                        self._make_tab_panel(
                            t_adapters,
                            self._render_component_tab,
                            installed_lib,
                            adapter_registry,
                            _CFG_ADAPTERS,
                            context,
                        )
                    if t_skins:
                        self._make_tab_panel(
                            t_skins,
                            self._render_component_tab,
                            installed_lib,
                            skin_registry,
                            _CFG_SKINS,
                            context,
                        )
                    if t_settings:
                        self._make_tab_panel(
                            t_settings,
                            self._render_component_tab,
                            installed_lib,
                            settings_registry,
                            _CFG_SETTINGS,
                            context,
                        )
                    if t_states:
                        self._make_tab_panel(
                            t_states,
                            self._render_component_tab,
                            installed_lib,
                            state_registry,
                            _CFG_STATES,
                            context,
                        )
                    if t_themes:
                        self._make_tab_panel(
                            t_themes,
                            self._render_component_tab,
                            installed_lib,
                            theme_registry,
                            _CFG_THEMES,
                            context,
                        )
                    if t_panels:
                        self._make_tab_panel(
                            t_panels,
                            self._render_component_tab,
                            installed_lib,
                            panel_registry,
                            _CFG_PANELS,
                            context,
                        )
                    if t_editors:
                        self._make_tab_panel(
                            t_editors,
                            self._render_component_tab,
                            installed_lib,
                            editor_registry,
                            _CFG_EDITORS,
                            context,
                        )

            elif marketplace_pkg and not installed_lib:
                # Marketplace-only: async-load OVERVIEW.md from source repo
                with ui.scroll_area().classes("w-full").style("height: 100%;"):
                    with ui.column().classes("w-full p-6 gap-2"):
                        loading_row = ui.row().classes("items-center gap-2")
                        with loading_row:
                            ui.spinner(size="sm")
                            ui.label("Loading overview…").classes("text-sm hw-text-muted")
                        content_area = ui.column().classes("w-full")
                asyncio.ensure_future(
                    self._load_marketplace_overview(marketplace_pkg, loading_row, content_area)
                )

    # ─────────────────────────────────────────────────────────────────────────
    # Tab content renderers
    # ─────────────────────────────────────────────────────────────────────────

    def _make_tab_panel(self, tab, render_fn, *args):
        """Wrap render_fn in the standard scroll-area + column scaffold."""
        with ui.tab_panel(tab).style("height: 100%; padding: 0;"):
            with ui.scroll_area().classes("w-full").style("height: 100%;"):
                with ui.column().classes("w-full p-6 gap-1"):
                    render_fn(*args)

    @staticmethod
    def _registry_items(registry, prefix: str):
        """Return [(key, cls)] from registry whose keys start with prefix."""
        if not registry:
            return []
        return [(k, registry.get(k)) for k in registry.list_names() if k.startswith(prefix)]

    def _component_row(self, key: str, label: str, description: str, handler):
        with (
            ui.row()
            .classes("w-full px-3 py-2 rounded hw-list-item-hover cursor-pointer")
            .on("click", handler)
        ):
            with ui.column().classes("gap-0 min-w-0"):
                ui.label(label).classes("text-sm font-medium")
                if description:
                    ui.label(description).classes("text-xs hw-text-dim truncate")
                ui.label(key).classes("text-xs hw-text-dim font-mono")

    def _render_overview(self, lib: LibraryInfo):
        """Render OVERVIEW.md from lib.identity.folder_path or show a fallback."""
        source = Path(lib.identity.folder_path) if lib.identity.folder_path else None
        overview = source / "OVERVIEW.md" if source else None

        if overview and overview.exists():
            ui.markdown(overview.read_text()).classes("w-full")
        else:
            with ui.column().classes("gap-2 py-4"):
                ui.label("No OVERVIEW.md found.").classes("hw-text-muted italic text-sm")
                ui.label("Run /docs to generate library documentation.").classes("text-xs hw-text-dim")

    def _render_component_tab(
        self,
        lib: LibraryInfo,
        registry,
        config: "TabConfig",
        context: "SessionContext",
    ):
        if not registry:
            ui.label(f"{config.comp_type.title()} registry not available.").classes(
                "hw-text-muted italic text-sm"
            )
            return

        items = self._registry_items(registry, f"{lib.identity.id}:{config.prefix_segment}:")

        if not items:
            ui.label(f"No {config.comp_type} registered for this library.").classes(
                "hw-text-muted italic text-sm py-4"
            )
            return

        for key, cls in sorted(items, key=lambda x: x[1].class_identity.label):
            self._component_row(
                key,
                cls.class_identity.label,
                cls.class_identity.description or "",
                partial(self._select_component, key, context),
            )

    # ─────────────────────────────────────────────────────────────────────────
    # Component click → notify context
    # ─────────────────────────────────────────────────────────────────────────

    def _select_component(
        self,
        registry_key: str,
        context: "SessionContext",
    ):
        """Set context.active_component (synthetic emit)"""
        context.active_component = registry_key

    # ─────────────────────────────────────────────────────────────────────────
    # Enable / Disable
    # ─────────────────────────────────────────────────────────────────────────

    def _enable_library(self, library_id: str, manager, context: "SessionContext"):
        manager.registry.enable_library(library_id)
        ui.notify(f"Enabled: {library_id}", type="positive")
        context.active_library = self._reload_installed(library_id, manager)
        self._notify_library_changed(context)

    def _disable_library(self, library_id: str, manager, context: "SessionContext"):
        manager.registry.disable_library(library_id)
        ui.notify(f"Disabled: {library_id}", type="warning")
        context.active_library = self._reload_installed(library_id, manager)
        self._notify_library_changed(context)

    def _reload_installed(self, library_id: str, manager) -> LibraryInfo | None:
        """Fetch a fresh LibraryInfo snapshot after an enable/disable."""
        try:
            libs = manager.list_installed()
            return next((lib for lib in libs if lib.identity.id == library_id), None)
        except Exception:
            return None

    def _find_installed_by_dist_name(self, dist_name: str, manager) -> LibraryInfo | None:
        """Find a freshly installed library by distribution name."""
        try:
            libs = manager.list_installed()
            return next((lib for lib in libs if lib.distribution_name == dist_name), None)
        except Exception:
            return None

    def _notify_library_changed(self, context: "SessionContext") -> None:
        """Broadcast LibraryCatalogChanged so all editors (incl. LibraryBrowser)
        refresh — and so peer sessions update too (latent-bug-flip per §11:
        was local-only, now cross-session via ``cross_session=True``).
        """
        session = context.session
        if session is not None:
            session.publish(LibraryCatalogChanged())

    # ─────────────────────────────────────────────────────────────────────────
    # Uninstall
    # ─────────────────────────────────────────────────────────────────────────

    def _confirm_uninstall(
        self,
        library_id: str,
        label: str,
        manager,
        context: "SessionContext",
    ):
        """Show confirmation dialog, then uninstall."""

        def _on_confirm():
            client = ui.context.client

            async def _run_with_client():
                with client:
                    await self._do_uninstall(library_id, label, manager, context)

            background_tasks.create(_run_with_client(), name=f"uninstall-{library_id}")

        confirm_modal(
            title=f"Uninstall {label}?",
            message=(
                "This will disable the library and remove it from the venv. "
                "Any graph nodes using this library will show as errors."
            ),
            confirm_label="Uninstall",
            danger=True,
            on_confirm=_on_confirm,
        )

    @staticmethod
    def _create_log_in_card(container, title: str) -> "ui.log":
        """Append an expandable terminal log inside a container."""
        with container:
            with hui.expansion_section(title, icon=hui.icon.terminal):
                log = ui.log(max_lines=50).classes("w-full h-32")
        return log

    async def _do_uninstall(
        self,
        library_id: str,
        label: str,
        manager,
        context: "SessionContext",
    ):
        """Perform uninstall with streaming log output."""
        ui.notify(f"Uninstalling {label}…", type="info")
        log = self._create_log_in_card(self._fixed, f"Uninstalling {label}…")

        success, message = await manager.uninstall_streaming(library_id, log.push)

        if success:
            log.push(f"--- {label} uninstalled successfully ---")
            ui.notify(f"Uninstalled: {label}", type="positive")
        else:
            log.push(f"--- ERROR: {message} ---")
            ui.notify(message, type="negative")

        # Clear the active library and notify all editors
        context.active_library = None
        self._notify_library_changed(context)

    # ─────────────────────────────────────────────────────────────────────────
    # Edit dialog (project library identity + optional rename)
    # ─────────────────────────────────────────────────────────────────────────

    def _is_project_library(self, lib: LibraryInfo, marketplace_path: str | None) -> bool:
        """Return True if lib is the local project library (lives under workspace/barn/)."""
        if not marketplace_path or not lib.identity.folder_path:
            return False
        workspace_root = Path(marketplace_path).parent.parent
        return Path(lib.identity.folder_path).is_relative_to(workspace_root / "barn")

    def _read_os_from_pyproject(self, lib: LibraryInfo, marketplace_path: str | None) -> list[str]:
        """Read the heap's current [tool.haywire].os values. Empty list if unset or non-heap."""
        if not self._is_project_library(lib, marketplace_path):
            return []
        if not lib.identity.folder_path:
            return []
        # lib.identity.folder_path is the MODULE path (e.g. workspace/barn/haybale-foo/haybale_foo).
        # The pyproject.toml lives in its parent.
        pyproject = Path(lib.identity.folder_path).parent / "pyproject.toml"
        if not pyproject.is_file():
            return []
        try:
            data = toml.loads(pyproject.read_text())
        except Exception:
            return []
        os_decl = data.get("tool", {}).get("haywire", {}).get("os", [])
        return [v for v in os_decl if isinstance(v, str)]

    def _build_edit_dialog(
        self,
        lib: LibraryInfo,
        marketplace_path: str | None,
        manager,
        context: "SessionContext",
    ) -> "ui.dialog":
        """Build the Edit dialog — all identity fields immediately editable.

        The package name field is locked behind a padlock icon. Clicking the
        padlock shows a warning dialog; if the user confirms, the name field
        becomes editable and saving triggers a full rename. When only identity
        fields are changed (name unchanged), a lightweight save is performed
        without any directory rename or uv sync.
        """
        old_name_part = (
            lib.distribution_name.removeprefix("haybale-") if lib.distribution_name else lib.identity.id
        )
        _state = {"unlocked": False}

        with ui.dialog() as edit_dialog, ui.card().style("width: 480px;").classes("gap-3"):
            ui.label("Edit Library").classes("text-lg font-bold")
            ui.label(f"haybale-{old_name_part}").classes("text-sm hw-text-muted font-mono")
            ui.separator()

            hui.section_label("Identity")
            label_input = ui.input(label="Label", value=lib.identity.label).classes("w-full")
            version_input = ui.input(label="Version", value=lib.identity.version or "0.1.0").classes(
                "w-full"
            )
            desc_input = ui.input(label="Description", value=lib.identity.description).classes("w-full")
            author_input = ui.input(label="Author", value=lib.identity.author).classes("w-full")
            author_url_input = ui.input(label="Author URL", value=lib.identity.author_url).classes("w-full")
            url_input = ui.input(label="URL", value=lib.identity.url).classes("w-full")
            tags_input = ui.input(
                label="Tags (comma-separated)",
                value=", ".join(lib.identity.tags or []),
            ).classes("w-full")
            with ui.row().classes("w-full items-end gap-2"):
                deps_input = ui.input(
                    label="Dependencies (comma-separated)",
                    value=", ".join(lib.identity.dependencies or []),
                ).classes("flex-1")
                detect_btn = (
                    ui.button(icon="manage_search")
                    .props("flat dense size=sm")
                    .tooltip("Detect dependencies from source imports")
                )
                detect_btn.on(
                    "click",
                    lambda d=deps_input, m=manager, ilib=lib, mp=marketplace_path: (
                        self._detect_dependencies(d, m, ilib, mp)
                    ),
                )

            # OS multi-select — spec §2.1. Visible only for heaps (writable pyproject.toml).
            is_heap = self._is_project_library(lib, marketplace_path)
            current_os = self._read_os_from_pyproject(lib, marketplace_path) if is_heap else []
            os_select = None
            if is_heap:
                os_select = (
                    ui.select(
                        options={"macos": "macOS", "windows": "Windows", "linux": "Linux"},
                        value=current_os,
                        multiple=True,
                        label="Supported OS (leave empty = all platforms)",
                    )
                    .props("dense use-chips")
                    .classes("w-full")
                )
            else:
                # Installed wheels: read-only display of any os declaration.
                marketplace_pkg = getattr(context, "active_marketplace_pkg", None)
                wheel_os = list(getattr(marketplace_pkg, "os", []) or []) if marketplace_pkg else []
                if wheel_os:
                    ui.label(f"Supported OS (read-only): {', '.join(wheel_os)}").classes(
                        "text-xs hw-text-dim"
                    )

            ui.separator()

            hui.section_label("Package Name")
            with ui.row().classes("w-full items-center gap-2"):
                ui.label("haybale-").classes("text-sm font-mono hw-text-muted flex-shrink-0")
                name_input = ui.input(value=old_name_part).classes("flex-1").props("dense")
                name_input.disable()
                lock_btn = (
                    ui.button(icon=hui.icon.locked)
                    .props("flat round dense size=sm color=orange")
                    .tooltip("Click to unlock — renaming breaks saved graph references")
                )
            preview_label = ui.label("").classes("text-xs hw-text-dim font-mono")

            def _update_preview():
                v = name_input.value.strip()
                if _state["unlocked"] and v and v != old_name_part:
                    mod = "haybale_" + re.sub(r"[^a-zA-Z0-9_]", "_", v.lower())
                    preview_label.set_text(f"Package: haybale-{v}  ·  Module: {mod}")
                else:
                    preview_label.set_text("")

            name_input.on("update:model-value", lambda _: _update_preview())

            async def _save():
                new_name = name_input.value.strip()
                identity = {
                    "label": label_input.value.strip(),
                    "version": version_input.value.strip().lstrip("vV"),
                    "description": desc_input.value.strip(),
                    "url": url_input.value.strip(),
                    "author": author_input.value.strip(),
                    "author_url": author_url_input.value.strip(),
                    "tags": [t.strip() for t in tags_input.value.split(",") if t.strip()],
                    "dependencies": [d.strip() for d in deps_input.value.split(",") if d.strip()],
                }
                # Include `os` only if the multi-select was rendered (heap libraries).
                if os_select is not None:
                    identity["os"] = list(os_select.value or [])
                edit_dialog.close()
                if _state["unlocked"] and new_name and new_name != old_name_part:
                    await self._do_rename(lib, new_name, identity, marketplace_path, manager, context)
                else:
                    await self._do_update_identity(lib, identity, marketplace_path, manager, context)

            with ui.row().classes("w-full justify-end gap-2 mt-2"):
                ui.button("Cancel", on_click=edit_dialog.close).props("flat size=sm")
                ui.button("Save Changes", on_click=_save).props("color=positive size=sm")

        # ── Warning dialog ────────────────────────────────────────────────────
        with ui.dialog() as warn_dialog, ui.card().classes("max-w-md gap-3"):
            with ui.row().classes("items-center gap-2"):
                ui.icon("warning", size="24px").classes("hw-text-warning")
                ui.label("Rename changes registry keys").classes("text-lg font-bold")
            ui.separator()
            ui.label(
                "Every node and widget from this library is identified in saved graphs "
                "by its registry key, which includes the library name "
                f'(e.g. "{lib.identity.id}:node:…"). '
                "After renaming, graphs that reference this library from other projects "
                "will fail to load those nodes. If your nodes are using absolute "
                "from ... import ... statements referencing this library, "
                "those will also need to be updated."
            ).classes("text-sm hw-text-muted")
            ui.label(
                "Only proceed if you have a backup of this project and this project's "
                "graphs/ folder is the only place these nodes are used — or if you "
                "really know what you're doing. Alternatively be prepared to enter a "
                "world of pain."
            ).classes("text-sm hw-text-dim italic")

            def _unlock_name():
                warn_dialog.close()
                _state["unlocked"] = True
                name_input.enable()
                lock_btn.props("icon=lock_open color=blue-grey")

            with ui.row().classes("w-full justify-end gap-2 mt-1"):
                ui.button("Cancel", on_click=warn_dialog.close).props("flat size=sm")
                ui.button(
                    "Unlock Name Field",
                    icon=hui.icon.unlocked,
                    on_click=_unlock_name,
                ).props("color=warning size=sm")

        def _lock_clicked():
            if _state["unlocked"]:
                _state["unlocked"] = False
                name_input.value = old_name_part
                name_input.disable()
                lock_btn.props("icon=lock color=orange")
                preview_label.set_text("")
            else:
                warn_dialog.open()

        lock_btn.on("click", lambda: _lock_clicked())
        return edit_dialog

    def _detect_dependencies(
        self,
        deps_input,
        manager,
        lib: LibraryInfo,
        marketplace_path: str | None,
    ) -> None:
        """Scan the library's source for actual imports and offer Union/Replace.

        Reads the live ``deps_input`` value (the @library decorator list the
        user is editing) plus the library's own pyproject.toml ``[project]
        dependencies`` from disk, computes the detected sets via
        ``detect_deps``, and opens a :func:`diff_modal` previewing both sides.

        Union applies the merge: @library deps gain any newly-detected names
        and the pyproject deps gain any newly-detected specifiers, no removals.
        Replace overwrites both lists with the detected ones (also writes
        pyproject.toml immediately).

        The @library deps update only sets ``deps_input.value`` — the user
        still has to click Save Changes for that side to persist. The
        pyproject write happens immediately because it is not part of the
        identity save bundle.
        """
        from haywire.core.library.dep_detect import (
            DetectedDeps,
            detect_deps,
            set_pyproject_dependencies,
        )
        from haywire.ui.modals import DiffSection, diff_modal
        from haywire_studio.share import union_pyproject_deps as _union_pyproject_deps
        import toml

        if not marketplace_path or not lib.distribution_name:
            ui.notify("Cannot detect — no library on disk for this entry.", type="warning")
            return

        workspace_root = Path(marketplace_path).parent.parent
        lib_dir = workspace_root / "barn" / lib.distribution_name
        if not lib_dir.is_dir():
            ui.notify(f"Library directory not found: {lib_dir}", type="negative")
            return

        try:
            detected: DetectedDeps = detect_deps(lib_dir, libraries=manager.registry)
        except Exception as exc:
            logger.exception("detect_deps failed")
            ui.notify(f"Detect failed: {exc}", type="negative")
            return

        # Current @library deps — from the live input, not disk.
        current_decorator = [d.strip() for d in (deps_input.value or "").split(",") if d.strip()]

        # Current pyproject deps — from disk.
        pyproject_path = lib_dir / "pyproject.toml"
        try:
            pyproject_data = toml.loads(pyproject_path.read_text())
            current_pyproject = list(pyproject_data.get("project", {}).get("dependencies", []))
        except (OSError, toml.TomlDecodeError) as exc:
            ui.notify(f"Cannot read pyproject.toml: {exc}", type="negative")
            return

        detected_decorator = list(detected.library_decorator)
        detected_pyproject = list(detected.pyproject)

        # Compute additions / removals for the two interpretations.
        cur_dec_set = set(current_decorator)
        det_dec_set = set(detected_decorator)
        cur_py_set = set(current_pyproject)
        det_py_set = set(detected_pyproject)

        decorator_section = DiffSection(
            title="@library(dependencies=...)",
            additions=sorted(det_dec_set - cur_dec_set),
            removals=sorted(cur_dec_set - det_dec_set),
            unchanged=sorted(cur_dec_set & det_dec_set),
            note=(
                f"Replace will remove {len(cur_dec_set - det_dec_set)} entr"
                f"{'y' if len(cur_dec_set - det_dec_set) == 1 else 'ies'}."
                if (cur_dec_set - det_dec_set)
                else ""
            ),
        )
        pyproject_section = DiffSection(
            title="pyproject.toml [project] dependencies",
            additions=sorted(det_py_set - cur_py_set),
            removals=sorted(cur_py_set - det_py_set),
            unchanged=sorted(cur_py_set & det_py_set),
            note=(
                f"Replace will remove {len(cur_py_set - det_py_set)} entr"
                f"{'y' if len(cur_py_set - det_py_set) == 1 else 'ies'}."
                if (cur_py_set - det_py_set)
                else ""
            ),
        )

        sections = [decorator_section, pyproject_section]
        if detected.unresolved:
            sections.append(
                DiffSection(
                    title="Unresolved imports",
                    additions=[],
                    removals=[],
                    unchanged=sorted(detected.unresolved),
                    note=(
                        "These modules could not be mapped to a distribution. "
                        "Likely dynamic imports or missing installs — review manually."
                    ),
                )
            )

        def _apply_union() -> None:
            new_decorator = sorted(cur_dec_set | det_dec_set)
            # Per spec §12.3: union pyproject deps by distribution NAME, not
            # by full specifier string. For each dist, prefer the detected
            # spec when it's a registered haybale (so lagging floors bump
            # to the installed version); otherwise keep the user's spec.
            new_pyproject = _union_pyproject_deps(
                current=current_pyproject,
                detected=detected_pyproject,
                libraries=manager.registry,
            )
            deps_input.value = ", ".join(new_decorator)
            self._write_pyproject_deps(lib_dir, new_pyproject, set_pyproject_dependencies)

        def _apply_replace() -> None:
            new_decorator = sorted(det_dec_set)
            new_pyproject = sorted(det_py_set)
            deps_input.value = ", ".join(new_decorator)
            self._write_pyproject_deps(lib_dir, new_pyproject, set_pyproject_dependencies)

        diff_modal(
            title="Detected dependencies",
            sections=sections,
            primary_label="Union",
            on_primary=_apply_union,
            secondary_label="Replace",
            on_secondary=_apply_replace,
            empty_message=(
                "No changes detected — the @library decorator and pyproject.toml "
                "already reflect what the source imports."
            ),
        )

    def _write_pyproject_deps(self, lib_dir: Path, deps: list[str], setter) -> None:
        """Wrapper around set_pyproject_dependencies that surfaces UI feedback."""
        try:
            setter(lib_dir, deps)
            ui.notify(
                "pyproject.toml updated. Click Save Changes to persist the @library decorator.",
                type="info",
            )
        except Exception as exc:
            logger.exception("set_pyproject_dependencies failed")
            ui.notify(f"Failed to update pyproject.toml: {exc}", type="negative")

    async def _do_update_identity(
        self,
        lib: LibraryInfo,
        identity: dict,
        marketplace_path: str | None,
        manager,
        context: "SessionContext",
    ):
        """Save identity fields, then rescan so the in-memory identity is refreshed."""
        if not marketplace_path:
            ui.notify("No project workspace set.", type="negative")
            return
        workspace_root = str(Path(marketplace_path).parent.parent)

        success, message = await asyncio.to_thread(
            manager.update_library_identity,
            lib.identity.id,
            workspace_root,
            identity,
        )
        if not success:
            ui.notify(message, type="negative")
            return

        # Rescan
        manager._invalidate_caches()
        await asyncio.to_thread(manager.registry.scan_for_libraries)
        manager.registry.enable_all_libraries()

        ui.notify(f"Saved: {identity.get('label', lib.identity.label)}", type="positive")

        # Reload the freshly-saved library into context and re-render
        try:
            libs = manager.list_installed()
            context.active_library = next(
                (entry for entry in libs if entry.identity.id == lib.identity.id), None
            )
        except Exception:
            pass
        # _do_update_identity is wired from a button drawn during draw(),
        # so _container has been set by then.
        assert self._container is not None
        self._container.clear()
        self._rebuild(context)

    async def _do_rename(
        self,
        lib: LibraryInfo,
        new_name: str,
        new_identity: dict | None,
        marketplace_path: str | None,
        manager,
        context: "SessionContext",
    ):
        """Perform rename with streaming log output."""
        if not marketplace_path:
            ui.notify("No project workspace set.", type="negative")
            return
        old_library_id = lib.identity.id
        ui.notify(f"Renaming {lib.identity.label}…", type="info")
        log = self._create_log_in_card(self._fixed, f"Renaming to haybale-{new_name}…")
        workspace_root = str(Path(marketplace_path).parent.parent)

        success, message = await manager.rename_project_library_streaming(
            library_id=lib.identity.id,
            new_name=new_name,
            workspace_root=workspace_root,
            on_output=log.push,
            new_identity=new_identity,
        )

        if success:
            log.push(f"--- Renamed to haybale-{new_name} ---")
            ui.notify(f"Renamed to haybale-{new_name}", type="positive")
        else:
            log.push(f"--- ERROR: {message} ---")
            ui.notify(message, type="negative")

        # Build the patch dialog BEFORE clearing (slot context must be clean)
        patch_dialog = (
            self._build_graph_patch_dialog(old_library_id, new_name, workspace_root) if success else None
        )

        context.active_library = None
        # _do_rename is wired from a button drawn during draw(), so
        # _container has been set by then.
        assert self._container is not None
        self._container.clear()
        self._rebuild(context)

        if patch_dialog is not None:
            patch_dialog.open()

    # ─────────────────────────────────────────────────────────────────────────
    # Graph file patching (post-rename)
    # ─────────────────────────────────────────────────────────────────────────

    def _build_graph_patch_dialog(
        self, old_library_id: str, new_library_id: str, workspace_root: str
    ) -> "ui.dialog | None":
        """Build (but don't open) a dialog offering to patch graph files."""
        graphs_dir = Path(workspace_root) / "graphs"
        if not graphs_dir.exists():
            return None

        old_prefix = old_library_id + ":"
        matching = [f for f in sorted(graphs_dir.glob("**/*.json")) if old_prefix in f.read_text()]
        if not matching:
            return None

        with ui.dialog() as dialog, ui.card().classes("max-w-lg gap-3"):
            with ui.row().classes("items-center gap-2"):
                ui.icon("find_replace", size="22px").classes("hw-text-accent")
                ui.label("Update graph files?").classes("text-lg font-bold")
            ui.separator()
            ui.label(
                f"Found {len(matching)} graph file(s) in graphs/ that reference "
                f'"{old_library_id}:…" registry keys. '
                f'Replace them with "{new_library_id}:…"?'
            ).classes("text-sm hw-text-muted")
            with ui.column().classes("gap-0 max-h-28 overflow-y-auto"):
                for f in matching[:6]:
                    ui.label(f.name).classes("text-xs font-mono hw-text-dim")
                if len(matching) > 6:
                    ui.label(f"… and {len(matching) - 6} more").classes("text-xs hw-text-dim italic")

            async def _patch_and_close():
                dialog.close()
                count, errors = await asyncio.to_thread(
                    self._patch_graph_files, graphs_dir, old_library_id, new_library_id
                )
                if errors:
                    ui.notify(
                        f"Patched {count} file(s); {len(errors)} error(s)",
                        type="warning",
                    )
                else:
                    ui.notify(f"Updated {count} graph file(s)", type="positive")

            with ui.row().classes("w-full justify-end gap-2 mt-1"):
                ui.button("Skip", on_click=dialog.close).props("flat size=sm")
                ui.button(
                    "Update files",
                    icon=hui.icon.find_replace,
                    on_click=_patch_and_close,
                ).props("color=positive size=sm")

        return dialog

    @staticmethod
    def _patch_graph_files(graphs_dir: Path, old_id: str, new_id: str) -> tuple[int, list[str]]:
        """Replace all occurrences of old_id: with new_id: in .json graph files."""
        old_prefix = old_id + ":"
        new_prefix = new_id + ":"
        count = 0
        errors: list[str] = []
        for f in graphs_dir.glob("**/*.json"):
            try:
                text = f.read_text()
                if old_prefix in text:
                    f.write_text(text.replace(old_prefix, new_prefix))
                    count += 1
            except OSError as e:
                errors.append(f"{f.name}: {e}")
        return count, errors

    # ─────────────────────────────────────────────────────────────────────────
    # Install
    # ─────────────────────────────────────────────────────────────────────────

    def _install_with_safety_check(
        self,
        pkg: Haybale,
        button,
        manager,
        context: "SessionContext",
    ):
        """Interpose the spec §7.4 safety modal before _install_package.

        The modal fires on every Install click. The user can Cancel, Block the
        source (drops the haybale from AVAILABLE permanently), or Install.
        """
        from haywire.core.marketstall import (
            record_block_on_source,
            resolve_block_target,
        )
        from haywire.ui.modals import install_safety_modal

        from haybale_marketplace.state.marketplace_state import MarketplaceState

        def _on_install():
            # Return the coroutine (don't schedule it). The modal awaits it,
            # which keeps the NiceGUI slot context intact so ui.notify() inside
            # _install_package works. See .insights/feedback_nicegui_async.md.
            return self._install_package(pkg.install_spec, pkg.name, button, manager, context)

        def _on_block() -> None:
            if context.app_data is None or MarketplaceState not in context.app_data:
                ui.notify("Marketplace state not available", type="warning")
                return
            state = context.app_data[MarketplaceState]
            global_path = state._global_path()
            target = resolve_block_target(global_path, pkg.via)
            if target is None:
                ui.notify(
                    f"Cannot block {pkg.name}: not from a subscription you can edit.",
                    type="warning",
                )
                return
            try:
                record_block_on_source(global_path, source_url=target, haybale_name=pkg.name)
            except Exception as exc:
                logger.exception("Failed to record block")
                ui.notify(f"Failed to block: {exc}", type="negative")
                return
            ui.notify(f"Blocked {pkg.name} from {target}", type="positive")
            state.refresh()
            active = getattr(context, "active_library", None)
            if active is not None and getattr(active, "name", None) == pkg.name:
                context.active_library = None
            self._notify_library_changed(context)

        def _on_cancel() -> None:
            ui.notify(f"Install of {pkg.name} cancelled", type="info")

        install_safety_modal(
            haybale_name=pkg.name,
            source_url=pkg.source_url or "",
            on_install=_on_install,
            on_block=_on_block,
            on_cancel=_on_cancel,
        )

    async def _install_package(
        self,
        install_spec: str,
        name: str,
        button,
        manager,
        context: "SessionContext",
    ):
        """Install a package with streaming log output."""
        if button:
            try:
                button.disable()
                button.props("loading")
            except Exception:
                pass
        ui.notify(f"Installing {name}…", type="info")
        log = self._create_log_in_card(self._fixed, f"Installing {name}…")

        success, message = await manager.install_streaming(install_spec, log.push)

        if success:
            log.push(f"--- {name} installed successfully ---")
            ui.notify(f"Installed: {name}", type="positive")
            # Point context at the newly installed library so the detail view
            # shows the full installed header + tabs on rebuild.
            installed = self._find_installed_by_dist_name(name, manager)
            if installed:
                context.active_library = installed
            self._notify_library_changed(context)
        else:
            log.push(f"--- ERROR: {message} ---")
            ui.notify(message, type="negative")

    def _open_version_picker(self, pkg: Haybale, manager, context: "SessionContext"):
        """Dialog to fetch and select a specific version for installation."""
        with ui.dialog() as dialog, ui.card().classes("min-w-80"):
            ui.label(f"Install specific version — {pkg.name}").classes("text-lg font-bold mb-2")
            version_select = (
                ui.select(
                    options=["Loading…"],
                    value="Loading…",
                    label="Version",
                )
                .classes("w-full")
                .props("dense")
            )
            status = ui.label("Fetching versions…").classes("text-xs hw-text-dim")

            async def load_versions():
                versions = await manager.fetch_versions(pkg)
                if versions:
                    version_select.options = versions
                    version_select.value = versions[0]
                    status.text = f"{len(versions)} versions available"
                else:
                    version_select.options = ["(unavailable)"]
                    version_select.value = "(unavailable)"
                    status.text = "Could not fetch version list"

            async def install_selected(e):
                selected = version_select.value
                if not selected or selected in ("Loading…", "(unavailable)"):
                    return
                dialog.close()
                spec = manager.build_versioned_spec(pkg, selected)
                # Reuse the safety wrapper with a versioned-install_spec copy of pkg.
                from dataclasses import replace

                versioned_pkg = replace(pkg, install_spec=spec)
                self._install_with_safety_check(versioned_pkg, None, manager, context)

            with ui.row().classes("w-full justify-end gap-2 mt-4"):
                ui.button("Cancel", on_click=dialog.close).props("flat")
                ui.button("Install", on_click=install_selected).props("color=positive")

        dialog.open()
        asyncio.ensure_future(load_versions())

    # ─────────────────────────────────────────────────────────────────────────
    # Marketplace overview fetch (async)
    # ─────────────────────────────────────────────────────────────────────────

    async def _fetch_marketplace_overview(self, pkg: Haybale) -> "str | None":
        """
        Fetch OVERVIEW.md (or README fallback) for a marketplace-only package.

        Priority:
        1. ``docs_url`` field — explicit raw URL to OVERVIEW.md or to the
           directory that contains it (e.g. a GitHub raw content URL).
           If the URL ends with a filename it is fetched directly; otherwise
           OVERVIEW.md and QUICKREF.md are appended and tried in order.
        2. Heuristic GitHub lookup — derived from ``source_url`` or
           ``install_spec``, for both pypi and git sources. The module name
           is inferred from the package name (``-`` → ``_``) and the optional
           ``#subdirectory=`` fragment of ``install_spec`` is respected.
        3. PyPI long_description fallback — only when no GitHub URL is found
           and ``source == 'pypi'``.
        """
        import json
        import urllib.request

        def _try_urls(urls: list) -> "str | None":
            for url in urls:
                try:
                    with urllib.request.urlopen(url, timeout=6) as resp:
                        return resp.read().decode("utf-8", errors="replace")
                except Exception:
                    continue
            return None

        # ── 1. Explicit docs_url ──────────────────────────────────────────────
        if pkg.docs_url:
            p = Path(pkg.docs_url)
            if p.is_dir():
                for candidate in (p / "OVERVIEW.md", p / "QUICKREF.md"):
                    if candidate.exists():
                        return candidate.read_text()
            elif p.is_file():
                return p.read_text()
            elif pkg.docs_url.startswith("http"):
                url = pkg.docs_url.rstrip("/")
                if url.endswith(".md"):
                    candidates = [url]
                else:
                    candidates = [f"{url}/OVERVIEW.md", f"{url}/QUICKREF.md"]
                content = await asyncio.to_thread(_try_urls, candidates)
                if content:
                    return content

        # ── 2. Heuristic: derive raw GitHub URL ──────────────────────────────
        module_name = pkg.name.replace("-", "_")

        subdir = ""
        if pkg.install_spec and "#subdirectory=" in pkg.install_spec:
            subdir = pkg.install_spec.split("#subdirectory=")[-1].strip("/")

        def _github_raw_base(url: str) -> "str | None":
            url = url.rstrip("/").removesuffix(".git")
            if "github.com" not in url:
                return None
            return url.replace("https://github.com/", "https://raw.githubusercontent.com/")

        raw_base = None
        if pkg.source_url and "github.com" in pkg.source_url:
            raw_base = _github_raw_base(pkg.source_url)
        elif pkg.source == "git" and pkg.install_spec:
            git_url = pkg.install_spec.removeprefix("git+").split("@")[0].split("#")[0].rstrip("/")
            raw_base = _github_raw_base(git_url)

        if raw_base:
            candidates = []
            for branch in ("main", "master"):
                prefix = f"{raw_base}/{branch}"
                pkg_prefix = f"{prefix}/{subdir}/{module_name}" if subdir else f"{prefix}/{module_name}"
                candidates.append(f"{pkg_prefix}/OVERVIEW.md")
                candidates.append(f"{pkg_prefix}/QUICKREF.md")
            for branch in ("main", "master"):
                prefix = f"{raw_base}/{branch}"
                if subdir:
                    candidates.append(f"{prefix}/{subdir}/OVERVIEW.md")
                candidates.append(f"{prefix}/OVERVIEW.md")

            content = await asyncio.to_thread(_try_urls, candidates)
            if content:
                return content

        # ── 3. PyPI long_description fallback ────────────────────────────────
        if pkg.source == "pypi":

            def _pypi_desc():
                try:
                    url = f"https://pypi.org/pypi/{pkg.name}/json"
                    with urllib.request.urlopen(url, timeout=8) as resp:
                        data = json.loads(resp.read())
                    return data.get("info", {}).get("description") or None
                except Exception:
                    return None

            return await asyncio.to_thread(_pypi_desc)

        return None

    async def _load_marketplace_overview(
        self,
        pkg: Haybale,
        loading_row,
        content_area,
    ):
        """Fetch overview content async and populate the content_area."""
        content = await self._fetch_marketplace_overview(pkg)
        loading_row.set_visibility(False)
        with content_area:
            if content:
                ui.markdown(content).classes("w-full")
            else:
                ui.label("No overview available for this package.").classes("hw-text-muted text-sm italic")
                if pkg.source_url:
                    ui.link(
                        "View source repository →",
                        pkg.source_url,
                        new_tab=True,
                    ).classes("text-xs hw-text-accent mt-1")
