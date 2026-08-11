# packages/haywire-app/src/haywire_studio/editors/library_overview_editor.py
"""
LibraryOverviewEditor — full center-panel port from LibraryManagerPage.

Renders in the middle area and reacts to LIBRARY_STATE_CHANGED events.
Receives the active library via context.active_library — always a LibraryInfo,
installed or merely catalogued. All services are retrieved from
context.app (= HaywireApp).

When a component (node/widget/type/adapter/renderer) is clicked, the editor
sets context.active_component (which synthetically emits
SessionContext.active_component on the bus) so that the right-panel
ComponentDetailEditor can react.
"""

import asyncio
import dataclasses
import logging
from functools import partial
from pathlib import Path
from typing import TYPE_CHECKING, Callable

from nicegui import ui
from nicegui import background_tasks

from haywire.ui import elements as hui
from haywire.core.adapter.registry import AdapterRegistry
from haywire.core.farmhand.registry import FarmhandRegistry
from haywire.core.node.registry import NodeRegistry
from haywire.core.settings import SettingsRegistry
from haywire.core.state import LibraryStateRegistry
from haywire.core.types.registry import TypeRegistry
from haywire.core.library.utils import (
    ADAPTER,
    EDITOR,
    FARMHAND,
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
from haywire.ui.editor.identity import OpenBehavior, SlotName
from haywire.ui.editor.base import BaseEditor
from haywire.ui.editor.registry import EditorTypeRegistry
from haywire.ui.panel.registry import PanelRegistry
from haywire.ui.skin.registry import SkinRegistry
from haywire.ui.themes import ThemeRegistry
from haywire.core.session.context import SessionContext
from haywire.core.session.handlers import redraw_on
from haywire.core.session.signals import LibraryCatalogChanged

from haywire.core.library.info import LibraryInfo
from haywire.core.library.haybale import Haybale
from haywire.core.marketstall.locate import link_form, module_dir_path, resolve_row_path
from haywire.ui.modals import info_modal

from haywire.ui.widget.registry import WidgetRegistry

from haybale_marketplace.editors._overview_actions import (
    confirm_uninstall,
    disable_library,
    enable_library,
    reload_installed,
)
from haybale_marketplace.editors._overview_edit_dialog import build_edit_dialog
from haybale_marketplace.library_origin import LibraryOrigin, compute_library_origin
from haybale_marketplace.editors._overview_install_flow import (
    install_package,
    install_with_safety_check,
    open_version_picker,
)

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
_CFG_FARMHANDS = TabConfig("farmhands", FARMHAND)


def should_block_install_for_os(haybale) -> str | None:
    """Return a tooltip message when the current OS doesn't match.

    Returns None when the haybale supports all platforms (empty os) or
    includes the current OS. The return value (string or None) drives the
    Install button's locked/unlocked state in the UI.
    """
    from haywire.core.marketstall import haybale_supports_current_os

    if haybale_supports_current_os(haybale):
        return None
    targets = ", ".join(getattr(haybale, "os", []) or [])
    return f"Not available on this OS; this library targets: {targets}."


def collect_overview_links(pkg) -> list[tuple[str, str]]:
    """The (label, href) links shown in the library overview header.

    Rows carry repo-relative paths, not URLs, so each is resolved against the
    row's ``origin`` at ``install_spec``'s ref — a trailing slash links as a
    directory, anything else as a file. ``resolve_row_path`` returns None rather
    than guessing when the host is unrecognised or the row lacks coordinates;
    the link is then simply absent, because a wrong URL is worse than none.

    Examples are surfaced for humans; ``tests_path`` is deliberately NOT
    surfaced (framework-maintainer metadata only).

    ``documentation_url`` is an absolute URL to a rendered site, so it is used
    verbatim. The old "Docs" link resolved the *module directory* and therefore
    opened a source-tree listing — nodes/, widgets/, __init__.py — which is not
    documentation.

    ``issues_url`` is likewise absolute and used verbatim.
    """
    if pkg is None:
        return []
    links: list[tuple[str, str]] = []
    if pkg.origin:
        links.append(("Source", pkg.origin))
    if getattr(pkg, "documentation_url", ""):
        links.append(("Docs", pkg.documentation_url))
    if pkg.issues_url:
        links.append(("Issues", pkg.issues_url))
    notes_dir = module_dir_path(pkg)
    for label, path in (
        ("Notes", f"{notes_dir}{pkg.notes}" if (notes_dir and pkg.notes) else ""),
        ("Examples", pkg.examples_path),
    ):
        if not path:
            continue
        href = resolve_row_path(pkg, path, form=link_form(path))
        if href:
            links.append((label, href))
    return links


@editor(
    label="Library Detail",
    icon=hui.icon.node_info,
    default_slot=SlotName.EDIT,
    opens=OpenBehavior.ON_CONTEXT,
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

        self._render_center(lib, context)

    def _catalog_row_for(self, info: LibraryInfo, context: "SessionContext") -> Haybale | None:
        """The marketplace [[caches]] entry matching an installed library, if any.

        Metadata never comes from here — that is ``info.row``'s job, whatever its
        source. This supplies only what a *feed* knows and a library's own
        ``haybale.toml`` cannot: the version the publisher currently advertises
        (the update check), the install coordinates the Update button and version
        picker need, and the ``source`` field that classifies a library's
        :class:`LibraryOrigin` as pypi vs git. A not-installed library's catalog
        row *is* ``info.row``, so this is only consulted for installed ones.

        Matching by distribution name mirrors the LibraryBrowser update-arrow logic
        so the same packages flagged in the list also expose an Update button here.
        """
        from haybale_marketplace.state.marketplace_state import MarketplaceState

        if context.app_data is None or MarketplaceState not in context.app_data:
            return None
        state = context.app_data[MarketplaceState]
        dist_name = info.row.name
        if not dist_name:
            return None
        try:
            return next(
                (h for h in state.get_project_haybales() if h.name == dist_name),
                None,
            )
        except Exception:
            return None

    def _render_placeholder(self):
        """Placeholder shown when nothing is selected."""
        if self._scroll:
            self._scroll.clear()
            with self._scroll:
                hui.empty_state("Select a library to view details", icon=hui.icon.library)

    # ─────────────────────────────────────────────────────────────────────────
    # Shared UI helpers
    # ─────────────────────────────────────────────────────────────────────────

    def _action_button(
        self,
        label: str,
        icon: str,
        *,
        block_reason: "str | None",
        on_click,
        color: str,
        flat: bool = True,
    ) -> None:
        """Render a button that is locked with an info modal when block_reason is set."""
        props = f"size=sm color={color}{' flat' if flat else ''}"
        if block_reason:
            ui.button(
                label,
                icon=hui.icon.locked,
                on_click=lambda m=block_reason: info_modal(
                    title="Action unavailable", icon="lock", message=m
                ),
            ).props(props)
        else:
            ui.button(label, icon=icon, on_click=on_click).props(props)

    def _notes_click_target(
        self,
        installed_lib: "LibraryInfo | None",
        row: Haybale,
        context: "SessionContext",
    ) -> tuple[Callable[[], None], str] | None:
        """Clicking a local "Notes"  opened an editable in the
        studio's CodeEditor rather than linked out to a remote blob.

        The file need not exist yet: CodeEditor opens a nonexistent path in a new tab

        Returns ``(on_click, icon)`` or None
        """
        if installed_lib is None or not row.notes or not installed_lib.identity.folder_path:
            return None
        notes_path = Path(installed_lib.identity.folder_path) / row.notes

        def _open() -> None:
            from haybale_studio.editors.error_navigation import open_file_in_studio

            open_file_in_studio(str(notes_path), None, context)

        return _open, hui.icon.edit_document

    # ─────────────────────────────────────────────────────────────────────────
    # Center panel — unified renderer
    # ─────────────────────────────────────────────────────────────────────────

    def _render_center(self, info: "LibraryInfo", context: "SessionContext"):
        """Render one library — installed or merely catalogued.

        Takes a single :class:`LibraryInfo`: metadata comes off ``info.row``
        whatever its source, and install-state branches read ``info.installed``.
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
        farmhand_registry: FarmhandRegistry = svc.get_farmhand_registry()

        marketplace_path = str(Path(app.workspace_root) / ".haywire" / "marketplace.toml")

        # Every displayed field comes off the one row, whichever source built it:
        # an installed library's own haybale.toml, read at the point of use so an
        # edit shows without a reload, or the marketstall row for a library that
        # has no files on disk yet. Both carry the same fields.
        row = info.row
        # The file, never the identity: the identity is built at import and is
        # stale after an edit. There is nothing to fall back to — a library whose
        # haybale.toml does not parse never loads (so no LibraryInfo exists for
        # it), and one corrupted while running keeps its previous identity by
        # BaseLibrary's reload contract. An empty row is the sub-render window
        # between a write and the next read.
        name = row.label or row.name
        version = row.version
        description = row.description
        tags = list(row.tags)
        installed_lib = info if info.installed else None

        # The feed's copy of this library, consulted only for what a feed knows
        # and the row cannot say about itself — see _catalog_row_for.
        catalog_row = self._catalog_row_for(info, context) if installed_lib else row

        # Check for available update — the version the publisher advertises
        # against the version installed here.
        update_available = False
        if catalog_row and installed_lib and catalog_row.version and version:
            try:
                from packaging.version import Version

                update_available = Version(catalog_row.version) > Version(version)
            except Exception:
                pass

        # Tab references — created in fixed section, used in scroll section
        tabs = t_overview = t_nodes = t_widgets = None
        t_types = t_adapters = t_skins = None
        t_settings = t_states = t_themes = t_panels = t_editors = t_farmhands = None

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
                        _title_url = row.homepage_url
                        if _title_url.startswith("http"):
                            with ui.row().classes("items-center gap-1"):
                                ui.label(name).classes("text-2xl font-bold")
                                with ui.link(target=_title_url, new_tab=True).style("line-height:0"):
                                    ui.icon("open_in_new", size="16px").classes("hw-text-accent opacity-60")
                        else:
                            ui.label(name).classes("text-2xl font-bold break-words")

                        with ui.row().classes("items-center gap-2 mt-1 flex-wrap"):
                            ui.label(f"v{version}").classes("text-sm hw-text-muted")
                            if row.name:
                                ui.label(row.name).classes("text-xs hw-text-muted font-mono")
                            if update_available and catalog_row:
                                hui.tag(f"v{catalog_row.version} available", color="orange")

                        # Mechanism/origin badges on their own row — kept off the
                        # version/dist-name line above so short vs. long names (e.g.
                        # builtin's "haywire-core" vs. "haybale-example")
                        # don't make badges wrap unpredictably from row to row.
                        # One flat color per AXIS, not per value: every mechanism
                        # badge is blue-grey, every origin badge is purple —
                        # regardless of which of the axis's values it shows —
                        # so the two facts read as visually distinct categories
                        # instead of a 5-way palette nobody will learn to decode.
                        if installed_lib:
                            with ui.row().classes("items-center gap-2 flex-wrap"):
                                hui.tag(info.install_type.name.lower(), color="blue-grey")
                                # Origin badge — always shown, no suppression even for the
                                # single FOLDER+framework row (no special-casing anywhere,
                                # per the settled design). Computed once here; the action
                                # buttons below reuse this same `_origin` value rather than
                                # recomputing it.
                                _origin = compute_library_origin(
                                    info, marketplace_path, catalog_entry=catalog_row
                                )
                                hui.tag(_origin.value, color="purple")

                    # ── Action buttons ─────────────────────────────────────────
                    with ui.row().classes("gap-1 flex-shrink-0 items-center"):
                        if installed_lib and manager:
                            _lib_id = info.identity.id
                            _lib_label = info.identity.label

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
                            if info.enabled:
                                # Annotated because the protected branch below
                                # narrows it to str, while the dependents branch
                                # yields None for "not blocked" — the value
                                # _action_button's block_reason expects.
                                _disable_msg: str | None
                                if _origin.is_protected:
                                    # Framework-owned or this workspace's own
                                    # project-local library — disabling has no
                                    # legitimate use here (mirrors is_required()'s
                                    # reasoning in the Library Browser). Takes
                                    # priority over the dependents message since
                                    # it's true regardless of dependents.
                                    _disable_msg = (
                                        f'"{_lib_label}" cannot be disabled — it is '
                                        f"{_origin.value.replace('_', ' ')}."
                                    )
                                else:
                                    _names = ", ".join(f'"{d.identity.label}"' for d in _block_disable)
                                    _disable_msg = (
                                        f'"{_lib_label}" cannot be disabled — {_names} depend on it.'
                                        " Disable all dependents first."
                                        if _block_disable
                                        else None
                                    )
                                self._action_button(
                                    "Disable",
                                    hui.icon.pause,
                                    block_reason=_disable_msg,
                                    on_click=lambda lid=_lib_id, ctx=context: (
                                        disable_library(lid, manager, ctx)
                                    ),
                                    color="orange",
                                )
                            else:
                                _names = ", ".join(f'"{d}"' for d in _block_enable)
                                _enable_msg = (
                                    f'"{_lib_label}" cannot be enabled — {_names} must be enabled first.'
                                    if _block_enable
                                    else None
                                )
                                self._action_button(
                                    "Enable",
                                    hui.icon.resume,
                                    block_reason=_enable_msg,
                                    on_click=lambda lid=_lib_id, ctx=context: (
                                        enable_library(lid, manager, ctx)
                                    ),
                                    color="green",
                                )

                            # Edit (project library) or Uninstall dropdown. Edit is
                            # scoped to PROJECT_LOCAL specifically, not the broader
                            # is_protected (which also covers FOLDER/framework, e.g.
                            # builtin — that has no on-disk pyproject.toml in the
                            # shape build_edit_dialog expects, and showed neither
                            # button before this origin-axis change; it must not
                            # gain an Edit button as an accidental side effect of
                            # broadening the protection check below).
                            if _origin is LibraryOrigin.PROJECT_LOCAL:
                                ui.button(
                                    "Edit",
                                    icon=hui.icon.edit,
                                    on_click=lambda ilib=info, mp=marketplace_path, m=manager, ctx=context: (
                                        build_edit_dialog(
                                            ilib,
                                            mp,
                                            m,
                                            ctx,
                                            on_save=partial(
                                                self._do_update_identity,
                                                ilib,
                                                marketplace_path=mp,
                                                manager=m,
                                                context=ctx,
                                            ),
                                        ).open()
                                    ),
                                ).props("size=sm color=blue flat")
                            elif not _origin.is_protected:
                                _names = ", ".join(f'"{d.identity.label}"' for d in _block_uninstall)
                                _uninstall_msg = (
                                    f'"{_lib_label}" cannot be uninstalled — {_names} depend on it.'
                                    " Uninstall all dependents first."
                                    if _block_uninstall
                                    else None
                                )
                                if _uninstall_msg:
                                    self._action_button(
                                        "Uninstall",
                                        hui.icon.delete,
                                        block_reason=_uninstall_msg,
                                        on_click=None,
                                        color="negative",
                                    )
                                else:
                                    with ui.row().classes("gap-0 items-center"):
                                        if update_available and catalog_row:
                                            # build_versioned_spec pins to pkg.version — see its
                                            # docstring for why catalog_row.install_spec alone
                                            # isn't safe to use here.
                                            ui.button(
                                                "Update",
                                                icon="arrow_upward",
                                                on_click=lambda e,
                                                n=catalog_row.name,
                                                m=manager,
                                                ctx=context,
                                                pkg=catalog_row: (
                                                    install_package(
                                                        m.build_versioned_spec(pkg, pkg.version),
                                                        n,
                                                        e.sender,
                                                        m,
                                                        ctx,
                                                        pkg,
                                                    )
                                                ),
                                            ).props("size=sm color=warning flat")
                                        else:
                                            ui.button(
                                                "Uninstall",
                                                on_click=lambda lid=_lib_id,
                                                ln=_lib_label,
                                                m=manager,
                                                ctx=context: (confirm_uninstall(lid, ln, m, ctx)),
                                            ).props("size=sm color=negative flat")
                                        with ui.button(icon=hui.icon.dropdown).props(
                                            "size=sm color=negative flat"
                                        ):
                                            with ui.menu():
                                                if catalog_row:
                                                    ui.menu_item(
                                                        "Install specific version…",
                                                        on_click=lambda p=catalog_row,
                                                        m=manager,
                                                        ctx=context: (open_version_picker(p, m, ctx)),
                                                    )
                                                ui.separator()
                                                ui.menu_item(
                                                    "Uninstall permanently",
                                                    on_click=lambda lid=_lib_id,
                                                    ln=_lib_label,
                                                    m=manager,
                                                    ctx=context: (confirm_uninstall(lid, ln, m, ctx)),
                                                )
                        elif not installed_lib and manager:
                            # Not installed — Install, blocked if deps missing/disabled or OS mismatch
                            _missing_deps = manager.get_missing_dependencies_for_package(
                                row, require_enabled=True
                            )
                            _os_block_msg = should_block_install_for_os(row)

                            _install_block: str | None
                            if _missing_deps:
                                _names = ", ".join(f'"{d}"' for d in _missing_deps)
                                _install_block = (
                                    f'"{name}"'
                                    f" cannot be installed — {_names} must be installed and enabled first."
                                )
                            else:
                                _install_block = _os_block_msg

                            self._action_button(
                                "Install",
                                hui.icon.download,
                                block_reason=_install_block,
                                on_click=lambda e, pkg=row, m=manager, ctx=context: (
                                    install_with_safety_check(pkg, e.sender, m, ctx)
                                ),
                                color="positive",
                                flat=False,
                            )

                # ── Metadata ───────────────────────────────────────────────────
                if description:
                    ui.label(description).classes("hw-text-muted text-sm mb-1")
                if row.authors:
                    with ui.row().classes("items-center gap-1"):
                        ui.label("By").classes("text-xs hw-text-dim")
                        for i, (_name, _url) in enumerate(row.authors):
                            if i:
                                ui.label(",").classes("text-xs hw-text-dim")
                            if _url.startswith("http"):
                                ui.link(_name, _url, new_tab=True).classes("text-xs hw-text-accent")
                            else:
                                ui.label(_name).classes("text-xs hw-text-dim")

                # Collect relevant links. Notes gets special handling
                _links = [(_lbl, _href) for _lbl, _href in collect_overview_links(row) if _lbl != "Notes"]
                _notes_click = self._notes_click_target(installed_lib, row, context)
                if _links or _notes_click:
                    with ui.row().classes("items-center gap-3 mt-1 flex-wrap"):
                        if _notes_click:
                            _open_notes, _icon = _notes_click
                            with ui.row().classes("items-center gap-1"):
                                ui.label("Notes").classes("text-xs hw-text-dim")
                                # the target is a studio-side navigation action (open in CodeEditor)
                                ui.icon(_icon, size="14px").classes("hw-text-accent cursor-pointer").on(
                                    "click", _open_notes
                                ).tooltip("Open in CodeEditor")
                        for _lbl, _href in _links:
                            with ui.row().classes("items-center gap-1"):
                                ui.label(_lbl).classes("text-xs hw-text-dim")
                                with ui.link(target=_href, new_tab=True):
                                    ui.icon(hui.icon.open_external, size="14px").classes(
                                        "hw-text-accent"
                                    ).tooltip(_href)
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
                    n_farmhands = _count(farmhand_registry, f"{lib_id}:{FARMHAND}:")

                    ui.separator().classes("mt-4")
                    with ui.tabs().classes("w-full hw-tabs").props("dense no-caps") as tabs:
                        t_overview = ui.tab("Overview", icon=hui.icon.library_component)
                        t_nodes = ui.tab("Nodes", icon=hui.icon.node) if n_nodes else None
                        t_widgets = ui.tab("Widgets", icon=hui.icon.widget) if n_widgets else None
                        t_types = ui.tab("Types", icon=hui.icon.type) if n_types else None
                        t_adapters = ui.tab("Adapters", icon=hui.icon.adapter) if n_adapters else None
                        t_skins = ui.tab("Skins", icon=hui.icon.skin) if n_skins else None
                        t_settings = ui.tab("Settings", icon=hui.icon.node_settings) if n_settings else None
                        t_states = ui.tab("States", icon=hui.icon.state) if n_states else None
                        t_themes = ui.tab("Themes", icon=hui.icon.theme) if n_themes else None
                        t_panels = ui.tab("Panels", icon=hui.icon.panel) if n_panels else None
                        t_editors = ui.tab("Editors", icon=hui.icon.editor) if n_editors else None
                        t_farmhands = ui.tab("Farmhands", icon=hui.icon.farmhand) if n_farmhands else None

        # ── Scrollable section: tab panels / placeholder ──────────────────────
        self._scroll.clear()
        with self._scroll:
            if installed_lib and tabs is not None:
                with ui.tab_panels(tabs, value=t_overview).classes("w-full").style("height: 100%;"):
                    self._make_tab_panel(t_overview, self._render_overview, installed_lib)
                    _tab_configs = [
                        (t_nodes, node_registry, _CFG_NODES),
                        (t_widgets, widget_registry, _CFG_WIDGETS),
                        (t_types, type_registry, _CFG_TYPES),
                        (t_adapters, adapter_registry, _CFG_ADAPTERS),
                        (t_skins, skin_registry, _CFG_SKINS),
                        (t_settings, settings_registry, _CFG_SETTINGS),
                        (t_states, state_registry, _CFG_STATES),
                        (t_themes, theme_registry, _CFG_THEMES),
                        (t_panels, panel_registry, _CFG_PANELS),
                        (t_editors, editor_registry, _CFG_EDITORS),
                        (t_farmhands, farmhand_registry, _CFG_FARMHANDS),
                    ]
                    for tab, registry, cfg in _tab_configs:
                        if tab:
                            self._make_tab_panel(
                                tab, self._render_component_tab, installed_lib, registry, cfg, context
                            )

            elif not installed_lib:
                # Marketplace-only: async-load OVERVIEW.md from source repo
                with ui.scroll_area().classes("w-full").style("height: 100%;"):
                    with ui.column().classes("w-full p-6 gap-2"):
                        loading_row = ui.row().classes("items-center gap-2")
                        with loading_row:
                            ui.spinner(size="sm")
                            ui.label("Loading overview…").classes("text-sm hw-text-muted")
                        content_area = ui.column().classes("w-full")
                background_tasks.create(
                    self._load_marketplace_overview(row, loading_row, content_area, context),
                    name=f"marketplace-overview-{row.name}",
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

    async def _do_update_identity(
        self,
        lib: LibraryInfo,
        identity: dict,
        marketplace_path: str | None,
        manager,
        context: "SessionContext",
    ):
        """Write the edited metadata, then re-render. No reload, no restart."""
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

        # No rescan, no module eviction, no restart offer. The write went to
        # haybale.toml, which every consumer reads at the point of use, and the
        # library's own file watcher refreshes the two identity fields that
        # cannot be read on demand. Re-rendering is enough to show it.
        ui.notify(f"Saved: {identity.get('label', lib.identity.label)}", type="positive")

        # LibraryInfo is frozen and info.row is a snapshot, not a live view —
        # reload_installed() re-fetches
        context.active_library = reload_installed(lib.identity.id, manager)

    # ─────────────────────────────────────────────────────────────────────────
    # Marketplace overview fetch (async)
    # ─────────────────────────────────────────────────────────────────────────

    async def _load_marketplace_overview(
        self,
        pkg: Haybale,
        loading_row,
        content_area,
        context: "SessionContext",
    ):
        """Fetch overview content async and populate the content_area."""
        from haybale_marketplace.state.marketplace_state import MarketplaceState

        marketplace_state = context.app_data.get(MarketplaceState) if context.app_data else None
        content = await marketplace_state.fetch_overview(pkg) if marketplace_state else None
        try:
            loading_row.set_visibility(False)
            with content_area:
                if content:
                    ui.markdown(content).classes("w-full")
                else:
                    ui.label("No overview available for this package.").classes(
                        "hw-text-muted text-sm italic"
                    )
                    if pkg.origin:
                        ui.link(
                            "View source repository →",
                            pkg.origin,
                            new_tab=True,
                        ).classes("text-xs hw-text-accent mt-1")
        except Exception:
            pass  # editor was closed before fetch completed
