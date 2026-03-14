# packages/haywire-app/src/haywire_app/editors/library_detail_editor.py
"""
LibraryDetailEditor — full center-panel port from LibraryManagerPage.

Renders in the middle area and reacts to ACTIVE_LIBRARY_CHANGED events.
Receives the active library via context.active_library (InstalledLibrary or
MarketplaceEntry). All services are retrieved from
context.app (= HaywireApp).

When a component (node/widget/type/adapter/renderer) is clicked, the editor
sets context.active_component and fires ACTIVE_COMPONENT_CHANGED so that the
right-panel ComponentDetailEditor can react.
"""

import asyncio
import re
from pathlib import Path
from typing import TYPE_CHECKING

from nicegui import ui

from haywire.core.node.registry import NodeRegistry
from haywire.core.settings import GlobalSettingsRegistry
from haywire.ui.editor.decorator import editor
from haywire.ui.editor.base import BaseEditor
from haywire.ui.editor.registry import EditorTypeRegistry
from haywire.ui.panel.registry import PanelRegistry
from haywire.ui.themes import ThemeRegistry
from haywire.ui.context_events import ContextChangeType, ContextChangedEvent

from haywire_app.library_manager import InstalledLibrary, LibraryManager, MarketplaceEntry

from haywire.ui.workspace.workspace_state import _K_COMPONENT_DETAIL

if TYPE_CHECKING:
    from haywire.ui.context import SessionContext


class _WidgetPreviewPort:
    """Minimal mock port used to render a live widget preview without binding."""
    id = 'preview'
    widget_config = {}


@editor(
    registry_id='library_detail',
    label='Library Detail',
    icon='info',
    default_area='middle',
    description='Detailed information for the selected library.',
)
class LibraryDetailEditor(BaseEditor):
    """
    Full center-panel port of LibraryManagerPage.

    Displays:
    - Fixed header: name, version, dist name, badges, action buttons, metadata
    - Scrollable content: tabs (Overview, Nodes, Widgets, Types, Adapters,
      Renderers) for installed libraries, or async overview for marketplace-only.

    Rebuilds on ACTIVE_LIBRARY_CHANGED.
    """

    def __init__(self):
        self._container = None
        # Fixed (non-scrolling) sub-container — header + metadata + tabs bar
        self._fixed = None
        # Scrollable sub-container — tab panels / placeholder
        self._scroll = None

    # ─────────────────────────────────────────────────────────────────────────
    # Public editor interface
    # ─────────────────────────────────────────────────────────────────────────

    def render(self, container, context: 'SessionContext') -> None:
        self._container = container
        self._rebuild(context)

    def on_context_changed(
        self, event: 'ContextChangedEvent', context: 'SessionContext'
    ) -> None:
        if (
            event.change_type == ContextChangeType.ACTIVE_LIBRARY_CHANGED
            and self._container is not None
        ):
            self._container.clear()
            self._rebuild(context)

    # ─────────────────────────────────────────────────────────────────────────
    # Top-level rebuild
    # ─────────────────────────────────────────────────────────────────────────

    def _rebuild(self, context: 'SessionContext') -> None:
        if self._container is None:
            return

        lib = context.active_library
        with self._container:
            with ui.column().classes('w-full gap-0').style(
                'height: 100%; display: flex; flex-direction: column;'
            ):
                self._fixed = ui.column().classes('w-full gap-0').style('flex-shrink: 0;')
                self._scroll = ui.column().classes('w-full gap-0').style(
                    'flex: 1; min-height: 0; overflow: hidden;'
                )

        if lib is None:
            self._render_placeholder()
            return

        if isinstance(lib, InstalledLibrary):
            self._render_center(lib, None, context)
        elif isinstance(lib, MarketplaceEntry):
            self._render_center(None, lib, context)
        else:
            self._render_placeholder()

    def _render_placeholder(self):
        """Placeholder shown when nothing is selected."""
        if self._scroll:
            self._scroll.clear()
            with self._scroll:
                with ui.column().classes('w-full items-center gap-2 py-32'):
                    ui.icon('library_books', size='48px').classes('hw-text-dim')
                    ui.label('Select a library to view details').classes('hw-text-muted text-sm')

    # ─────────────────────────────────────────────────────────────────────────
    # Center panel — unified renderer
    # ─────────────────────────────────────────────────────────────────────────

    def _render_center(
        self,
        installed_lib: InstalledLibrary | None,
        marketplace_pkg: MarketplaceEntry | None,
        context: 'SessionContext',
    ):
        """
        Unified center panel renderer.

        - installed_lib only  → installed header + tabs
        - installed_lib + pkg → marketplace header with installed badges + tabs
        - pkg only            → marketplace header + Install button, no tabs
        """
        # Resolve registries from context
        app = context.app
        svc = app.library_service
        manager = app.library_manager
        node_registry = svc.get_node_registry()
        widget_registry = svc.get_widget_registry()
        type_registry = svc.get_type_registry()
        adapter_registry = svc.get_adapter_registry()
        skin_registry = svc.get_skin_registry()
        settings_registry: GlobalSettingsRegistry = svc.get_settings_registry()
        theme_registry: ThemeRegistry = svc.get_theme_registry()
        panel_registry: PanelRegistry = svc.get_panel_registry()
        editor_registry: EditorTypeRegistry = svc.get_editor_registry()
        marketplace_path = str(Path(app.workspace_root) / '.haywire' / 'marketplace.toml')

        # Determine display properties
        if installed_lib:
            name = installed_lib.label
            version = installed_lib.version
            description = installed_lib.description
            author = installed_lib.author
            tags = (
                installed_lib.tags
                or (marketplace_pkg.tags if marketplace_pkg else [])
                or []
            )
        else:
            name = marketplace_pkg.label or marketplace_pkg.name
            version = marketplace_pkg.version
            description = marketplace_pkg.description
            author = marketplace_pkg.author
            tags = marketplace_pkg.tags or []

        # Check for available update
        update_available = False
        if (
            marketplace_pkg
            and installed_lib
            and marketplace_pkg.version
            and installed_lib.version
        ):
            try:
                from packaging.version import Version
                update_available = Version(marketplace_pkg.version) > Version(
                    installed_lib.version
                )
            except Exception:
                pass

        # Tab references — created in fixed section, used in scroll section
        tabs = t_overview = t_nodes = t_widgets = None
        t_types = t_adapters = t_skins = None
        t_settings = t_themes = t_panels = t_editors = None

        # Pre-compute component counts (for tab disable state)
        def _count(registry, prefix: str) -> int:
            if not registry:
                return 0
            return sum(1 for k in registry.list_names() if k.startswith(prefix))

        lib_id = installed_lib.library_id if installed_lib else None

        # ── header + metadata + tabs bar ───────────────────────
        self._fixed.clear()
        with self._fixed:
            with ui.column().classes('w-full px-6 pt-6 min-w-0 gap-1'):

                # ── Header ────────────────────────────────────────────────────
                with ui.row().classes('w-full items-start justify-between mb-2'):
                    with ui.column().classes('gap-0.5 min-w-0 flex-1'):
                        _title_url = (installed_lib.url if installed_lib else '') or ''
                        if _title_url.startswith('http'):
                            with ui.row().classes('items-center gap-1'):
                                ui.label(name).classes('text-2xl font-bold')
                                with ui.link(target=_title_url, new_tab=True).style(
                                    'line-height:0'
                                ):
                                    ui.icon('open_in_new', size='16px').classes(
                                        'text-blue-400 opacity-60'
                                    )
                        else:
                            ui.label(name).classes('text-2xl font-bold break-words')

                        with ui.row().classes('items-center gap-2 mt-1 flex-wrap'):
                            ui.label(f'v{version}').classes('text-sm hw-text-muted')
                            _dist_name = (
                                (installed_lib.distribution_name if installed_lib else None)
                                or (marketplace_pkg.name if marketplace_pkg else None)
                            )
                            if _dist_name:
                                ui.label(_dist_name).classes(
                                    'text-xs hw-text-muted font-mono'
                                )
                            if installed_lib:
                                inst_color = {
                                    'EDITABLE': 'purple',
                                    'REGULAR': 'blue',
                                    'FOLDER': 'teal',
                                }.get(installed_lib.install_type, 'grey')
                                ui.badge(
                                    installed_lib.install_type.lower(),
                                    color=inst_color,
                                ).props('outline')
                            if marketplace_pkg:
                                src_color = (
                                    'blue' if marketplace_pkg.source == 'pypi' else 'purple'
                                )
                                ui.badge(
                                    marketplace_pkg.source, color=src_color
                                ).props('outline')
                            if update_available:
                                ui.badge(
                                    f'v{marketplace_pkg.version} available',
                                    color='orange',
                                ).props('outline')

                    # ── Action buttons ─────────────────────────────────────────
                    with ui.row().classes('gap-1 flex-shrink-0 items-center'):
                        if installed_lib and manager:
                            # Enable / Disable toggle
                            if installed_lib.enabled:
                                ui.button(
                                    'Disable',
                                    icon='pause',
                                    on_click=lambda lid=installed_lib.library_id, ctx=context: (
                                        self._disable_library(lid, manager, ctx)
                                    ),
                                ).props('size=sm color=orange flat')
                            else:
                                ui.button(
                                    'Enable',
                                    icon='play_arrow',
                                    on_click=lambda lid=installed_lib.library_id, ctx=context: (
                                        self._enable_library(lid, manager, ctx)
                                    ),
                                ).props('size=sm color=green flat')

                            # Edit (project library) or Uninstall dropdown
                            if self._is_project_library(installed_lib, marketplace_path):
                                ui.button(
                                    'Edit',
                                    icon='edit',
                                    on_click=lambda ilib=installed_lib,
                                    mp=marketplace_path, m=manager, ctx=context: (
                                        self._build_edit_dialog(ilib, mp, m, ctx).open()
                                    ),
                                ).props('size=sm color=blue flat')
                            elif installed_lib.install_type in ('REGULAR', 'EDITABLE'):
                                _required_by = LibraryManager.is_required_by_another_package(
                                    installed_lib.distribution_name or installed_lib.library_id
                                )
                                if _required_by:
                                    with ui.element('span').props(
                                        f'title="Required by {_required_by} — '
                                        f'remove {_required_by} first to uninstall this one."'
                                    ):
                                        ui.button(
                                            'Uninstall',
                                            icon='lock',
                                        ).props('size=sm color=grey flat').props('disable')
                                else:
                                    with ui.row().classes('gap-0 items-center'):
                                        ui.button(
                                            'Uninstall',
                                            on_click=lambda lid=installed_lib.library_id,
                                            ln=installed_lib.label, m=manager, ctx=context: (
                                                self._confirm_uninstall(lid, ln, m, ctx)
                                            ),
                                        ).props('size=sm color=negative flat')
                                        with ui.button(icon='arrow_drop_down').props(
                                            'size=sm color=negative flat'
                                        ):
                                            with ui.menu():
                                                if update_available and marketplace_pkg:
                                                    ui.menu_item(
                                                        f'Update to v{marketplace_pkg.version}',
                                                        on_click=lambda e,
                                                        spec=marketplace_pkg.install_spec,
                                                        n=marketplace_pkg.name,
                                                        m=manager, ctx=context: (
                                                            self._install_package(
                                                                spec, n, e.sender, m, ctx
                                                            )
                                                        ),
                                                    )
                                                if marketplace_pkg:
                                                    ui.menu_item(
                                                        'Install specific version…',
                                                        on_click=lambda p=marketplace_pkg,
                                                        m=manager, ctx=context: (
                                                            self._open_version_picker(p, m, ctx)
                                                        ),
                                                    )
                                                ui.separator()
                                                ui.menu_item(
                                                    'Uninstall permanently',
                                                    on_click=lambda lid=installed_lib.library_id,
                                                    ln=installed_lib.label, m=manager, ctx=context: (
                                                        self._confirm_uninstall(lid, ln, m, ctx)
                                                    ),
                                                )
                        elif not installed_lib and marketplace_pkg and manager:
                            # Not installed — simple Install button
                            ui.button(
                                'Install',
                                icon='download',
                                on_click=lambda e,
                                spec=marketplace_pkg.install_spec,
                                n=marketplace_pkg.name, m=manager, ctx=context: (
                                    self._install_package(spec, n, e.sender, m, ctx)
                                ),
                            ).props('color=primary size=sm')

                # ── Metadata ───────────────────────────────────────────────────
                if description:
                    ui.label(description).classes('hw-text-muted text-sm mb-1')
                if author:
                    _author_url = (installed_lib.author_url if installed_lib else '') or ''
                    if _author_url.startswith('http'):
                        with ui.row().classes('items-center gap-1'):
                            ui.label('By').classes('text-xs hw-text-dim')
                            ui.link(author, _author_url, new_tab=True).classes(
                                'text-xs text-blue-400'
                            )
                    else:
                        ui.label(f'By {author}').classes('text-xs hw-text-dim')

                # Collect relevant links
                _links: list[tuple[str, str]] = []
                if marketplace_pkg and marketplace_pkg.source_url:
                    _links.append(('Source', marketplace_pkg.source_url))
                if (
                    marketplace_pkg
                    and marketplace_pkg.docs_url
                    and marketplace_pkg.docs_url.startswith('http')
                ):
                    _links.append(('Docs', marketplace_pkg.docs_url))
                if _links:
                    with ui.row().classes('items-center gap-3 mt-1 flex-wrap'):
                        for _lbl, _href in _links:
                            with ui.row().classes('items-center gap-0.5'):
                                ui.link(_lbl, _href, new_tab=True).classes(
                                    'text-xs text-blue-400'
                                )
                                ui.icon('open_in_new', size='10px').classes('text-blue-300')
                if tags:
                    with ui.row().classes('gap-1 mt-2 flex-wrap'):
                        for tag in tags:
                            ui.badge(tag).props('outline color=grey')

                # ── Tabs bar (only when library is installed) ──────────────────
                if installed_lib:
                    n_nodes    = _count(node_registry,     f'{lib_id}:node:')
                    n_widgets  = _count(widget_registry,   f'{lib_id}:widget:')
                    n_types    = _count(type_registry,     f'{lib_id}:type:')
                    n_adapters = _count(adapter_registry,  f'{lib_id}:adapter:')
                    n_skins    = _count(skin_registry,     f'{lib_id}:skin:')
                    n_settings = _count(settings_registry, f'{lib_id}:settings:')
                    n_themes   = _count(theme_registry,    f'{lib_id}:theme:')
                    n_panels   = _count(panel_registry,    f'{lib_id}:panel:')
                    n_editors  = _count(editor_registry,   f'{lib_id}:editor:')

                    ui.separator().classes('mt-4')
                    with ui.tabs().classes('w-full').props('dense') as tabs:
                        t_overview = ui.tab('Overview',  icon='description')
                        t_nodes    = ui.tab('Nodes',     icon='account_tree')
                        t_widgets  = ui.tab('Widgets',   icon='widgets')
                        t_types    = ui.tab('Types',     icon='category')
                        t_adapters = ui.tab('Adapters',  icon='swap_horiz')
                        t_skins    = ui.tab('Skins',     icon='brush')
                        t_settings = ui.tab('Settings',  icon='tune')
                        t_themes   = ui.tab('Themes',    icon='palette')
                        t_panels   = ui.tab('Panels',    icon='view_sidebar')
                        t_editors  = ui.tab('Editors',   icon='tab')
                        if not n_nodes:
                            t_nodes.props('disable')
                        if not n_widgets:
                            t_widgets.props('disable')
                        if not n_types:
                            t_types.props('disable')
                        if not n_adapters:
                            t_adapters.props('disable')
                        if not n_skins:
                            t_skins.props('disable')
                        if not n_settings:
                            t_settings.props('disable')
                        if not n_themes:
                            t_themes.props('disable')
                        if not n_panels:
                            t_panels.props('disable')
                        if not n_editors:
                            t_editors.props('disable')

        # ── Scrollable section: tab panels / placeholder ──────────────────────
        self._scroll.clear()
        with self._scroll:
            if installed_lib and tabs is not None:
                with ui.tab_panels(tabs, value=t_overview).classes('w-full').style('height: 100%;'):
                    with ui.tab_panel(t_overview).style('height: 100%; padding: 0;'):
                        with ui.scroll_area().classes('w-full').style('height: 100%;'):
                            with ui.column().classes('w-full p-6 gap-1'):
                                self._render_overview(installed_lib)
                    with ui.tab_panel(t_nodes).style('height: 100%; padding: 0;'):
                        with ui.scroll_area().classes('w-full').style('height: 100%;'):
                            with ui.column().classes('w-full p-6 gap-1'):
                                self._render_nodes_tab(installed_lib, node_registry, context)
                    with ui.tab_panel(t_widgets).style('height: 100%; padding: 0;'):
                        with ui.scroll_area().classes('w-full').style('height: 100%;'):
                            with ui.column().classes('w-full p-6 gap-1'):
                                self._render_widgets_tab(installed_lib, widget_registry, context)
                    with ui.tab_panel(t_types).style('height: 100%; padding: 0;'):
                        with ui.scroll_area().classes('w-full').style('height: 100%;'):
                            with ui.column().classes('w-full p-6 gap-1'):
                                self._render_generic_component_tab(
                                    installed_lib, type_registry, 'types', context
                                )
                    with ui.tab_panel(t_adapters).style('height: 100%; padding: 0;'):
                        with ui.scroll_area().classes('w-full').style('height: 100%;'):
                            with ui.column().classes('w-full p-6 gap-1'):
                                self._render_generic_component_tab(
                                    installed_lib, adapter_registry, 'adapters', context
                                )
                    with ui.tab_panel(t_skins).style('height: 100%; padding: 0;'):
                        with ui.scroll_area().classes('w-full').style('height: 100%;'):
                            with ui.column().classes('w-full p-6 gap-1'):
                                self._render_generic_component_tab(
                                    installed_lib, skin_registry, 'skins', context
                                )
                    with ui.tab_panel(t_settings).style('height: 100%; padding: 0;'):
                        with ui.scroll_area().classes('w-full').style('height: 100%;'):
                            with ui.column().classes('w-full p-6 gap-1'):
                                self._render_settings_tab(installed_lib, settings_registry, context)
                    with ui.tab_panel(t_themes).style('height: 100%; padding: 0;'):
                        with ui.scroll_area().classes('w-full').style('height: 100%;'):
                            with ui.column().classes('w-full p-6 gap-1'):
                                self._render_themes_tab(installed_lib, theme_registry, context)
                    with ui.tab_panel(t_panels).style('height: 100%; padding: 0;'):
                        with ui.scroll_area().classes('w-full').style('height: 100%;'):
                            with ui.column().classes('w-full p-6 gap-1'):
                                self._render_panels_tab(installed_lib, panel_registry, context)
                    with ui.tab_panel(t_editors).style('height: 100%; padding: 0;'):
                        with ui.scroll_area().classes('w-full').style('height: 100%;'):
                            with ui.column().classes('w-full p-6 gap-1'):
                                self._render_editors_tab(installed_lib, editor_registry, context)

            elif marketplace_pkg and not installed_lib:
                # Marketplace-only: async-load OVERVIEW.md from source repo
                with ui.scroll_area().classes('w-full').style('height: 100%;'):
                    with ui.column().classes('w-full p-6 gap-2'):
                        loading_row = ui.row().classes('items-center gap-2')
                        with loading_row:
                            ui.spinner(size='sm')
                            ui.label('Loading overview…').classes('text-sm hw-text-muted')
                        content_area = ui.column().classes('w-full')
                asyncio.ensure_future(
                    self._load_marketplace_overview(
                        marketplace_pkg, loading_row, content_area
                    )
                )

    # ─────────────────────────────────────────────────────────────────────────
    # Tab content renderers
    # ─────────────────────────────────────────────────────────────────────────

    def _render_overview(self, lib: InstalledLibrary):
        """Render OVERVIEW.md from lib.source_path or show a fallback."""
        source = Path(lib.source_path) if lib.source_path else None
        overview = source / 'OVERVIEW.md' if source else None

        if overview and overview.exists():
            ui.markdown(overview.read_text()).classes('w-full')
        else:
            with ui.column().classes('gap-2 py-4'):
                ui.label('No OVERVIEW.md found.').classes('hw-text-muted italic text-sm')
                ui.label('Run /docs to generate library documentation.').classes(
                    'text-xs hw-text-dim'
                )

    def _render_nodes_tab(
        self, lib: InstalledLibrary, node_registry: NodeRegistry, context: 'SessionContext'
    ):
        """Render the node list grouped by menu category."""
        if not node_registry:
            ui.label('Node registry not available.').classes(
                'hw-text-muted italic text-sm'
            )
            return

        prefix = f'{lib.library_id}:node:'
        items = [
            (k, node_registry.get(k))
            for k in node_registry.list_names()
            if k.startswith(prefix)
        ]
        items = [
            (k, c)
            for k, c in items
            if c
            and hasattr(c, 'class_identity')
            and c.class_identity
            and not getattr(c.class_identity, '_is_error', False)
        ]

        if not items:
            ui.label('No nodes registered for this library.').classes(
                'hw-text-muted italic text-sm py-4'
            )
            return

        categories: dict[str, list] = {}
        for key, cls in items:
            menu = getattr(cls.class_identity, 'menu', '') or ''
            cat = menu.split('/')[0].title() if menu else 'Other'
            categories.setdefault(cat, []).append((key, cls))

        for cat in sorted(categories):
            ui.label(cat).classes(
                'text-xs font-bold hw-text-dim mt-4 mb-1 uppercase tracking-wider'
            )
            for key, cls in sorted(
                categories[cat],
                key=lambda x: x[1].class_identity.label or '',
            ):
                ident = cls.class_identity
                class_name = key.split(':')[-1]
                with ui.row().classes(
                    'w-full items-start gap-3 px-3 py-2 rounded'
                    ' hover:bg-white/10 cursor-pointer'
                ).on(
                    'click',
                    lambda cn=class_name, entry=lib, ctx=context: self._select_component(
                        entry, cn, 'nodes', ctx
                    ),
                ):
                    with ui.column().classes('gap-0 flex-1 min-w-0'):
                        ui.label(ident.label or class_name).classes('text-sm font-medium')
                        if ident.description:
                            ui.label(ident.description).classes(
                                'text-xs hw-text-dim truncate'
                            )

    def _render_widgets_tab(
        self, lib: InstalledLibrary, widget_registry, context: 'SessionContext'
    ):
        """Render the widget list with a live preview of each widget."""
        if not widget_registry:
            ui.label('Widget registry not available.').classes(
                'hw-text-muted italic text-sm'
            )
            return

        prefix = f'{lib.library_id}:widget:'
        items = [
            (k, widget_registry.get(k))
            for k in widget_registry.list_names()
            if k.startswith(prefix)
        ]
        items = [
            (k, c)
            for k, c in items
            if c and hasattr(c, 'class_identity') and c.class_identity
        ]

        if not items:
            ui.label('No widgets registered for this library.').classes(
                'hw-text-muted italic text-sm py-4'
            )
            return

        for key, cls in sorted(items, key=lambda x: x[1].class_identity.label or ''):
            ident = cls.class_identity
            class_name = key.split(':')[-1]
            with ui.row().classes(
                'w-full items-center gap-4 px-3 py-2 rounded'
                ' hover:bg-white/10 cursor-pointer'
            ).on(
                'click',
                lambda cn=class_name, entry=lib, ctx=context: self._select_component(
                    entry, cn, 'widgets', ctx
                ),
            ):
                with ui.column().classes('gap-0 flex-1 min-w-0'):
                    ui.label(ident.label or class_name).classes('text-sm font-medium')
                    if ident.description:
                        ui.label(ident.description).classes(
                            'text-xs hw-text-dim truncate'
                        )
                # Live widget preview — uniform fixed-width box
                with ui.element('div').classes(
                    'flex-shrink-0 border rounded-sm bg-white'
                ).style('width: 11rem; min-height: 2.5rem; padding: 4px; overflow: hidden;'):
                    if not hasattr(cls, 'create_element'):
                        with ui.column().classes('w-full items-center py-1 gap-0.5'):
                            ui.icon('videocam', size='18px').classes('text-gray-400')
                            ui.label('live only').classes('text-xs text-gray-400 italic')
                    else:
                        try:
                            mock_port = _WidgetPreviewPort()
                            instance = cls(mock_port)
                            instance.create_element()
                        except Exception:
                            with ui.column().classes('w-full items-center py-1'):
                                ui.label('—').classes('text-xs text-gray-400 italic')

    def _render_generic_component_tab(
        self,
        lib: InstalledLibrary,
        registry,
        comp_type: str,
        context: 'SessionContext',
    ):
        """Render a flat component list (types, adapters, renderers) for this library."""
        comp_singular = comp_type.removesuffix('s')
        if not registry:
            ui.label(f'{comp_singular.title()} registry not available.').classes(
                'hw-text-muted italic text-sm'
            )
            return

        prefix = f'{lib.library_id}:{comp_singular}:'
        items = [
            (k, registry.get(k))
            for k in registry.list_names()
            if k.startswith(prefix)
        ]
        items = [
            (k, c)
            for k, c in items
            if c and hasattr(c, 'class_identity') and c.class_identity
        ]

        if not items:
            ui.label(f'No {comp_type} registered for this library.').classes(
                'hw-text-muted italic text-sm py-4'
            )
            return

        for key, cls in sorted(items, key=lambda x: x[1].class_identity.label or ''):
            ident = cls.class_identity
            class_name = key.split(':')[-1]
            with ui.row().classes(
                'w-full items-start gap-3 px-3 py-2 rounded hover:bg-white/10 cursor-pointer'
            ).on(
                'click',
                lambda cn=class_name, entry=lib, ct=comp_type, ctx=context: (
                    self._select_component(entry, cn, ct, ctx)
                ),
            ):
                with ui.column().classes('gap-0 flex-1 min-w-0'):
                    ui.label(ident.label or class_name).classes('text-sm font-medium')
                    if ident.description:
                        ui.label(ident.description).classes(
                            'text-xs hw-text-dim truncate'
                        )
                    ui.label(key).classes('text-xs hw-text-dim font-mono')

    def _render_settings_tab(
        self, lib: InstalledLibrary, settings_registry: GlobalSettingsRegistry | None,
        context: 'SessionContext',
    ):
        """Render library settings schemas."""
        if not settings_registry:
            ui.label('Settings registry not available.').classes('hw-text-muted italic text-sm')
            return

        prefix = f'{lib.library_id}:settings:'
        items = [
            (k, settings_registry.get(k))
            for k in settings_registry.list_names()
            if k.startswith(prefix)
        ]
        items = [(k, c) for k, c in items if c]

        if not items:
            ui.label('No settings registered for this library.').classes(
                'hw-text-muted italic text-sm py-4'
            )
            return

        for key, cls in sorted(items, key=lambda x: x[0]):
            ident = getattr(cls, 'class_identity', None)
            label = getattr(ident, 'namespace', None) or key.split(':')[-1]
            description = getattr(ident, 'description', None) or ''
            with ui.row().classes(
                'w-full items-start gap-3 px-3 py-2 rounded hover:bg-white/10 cursor-pointer'
            ).on(
                'click',
                lambda k=key, entry=lib, ctx=context: self._select_component(
                    entry, k.split(':')[-1], 'settings', ctx, registry_key=k
                ),
            ):
                ui.icon('tune', size='18px').classes('hw-text-dim mt-0.5 flex-shrink-0')
                with ui.column().classes('gap-0 flex-1 min-w-0'):
                    ui.label(label).classes('text-sm font-medium')
                    if description:
                        ui.label(description).classes('text-xs hw-text-dim truncate')
                    ui.label(key).classes('text-xs hw-text-dim font-mono')

    def _render_themes_tab(
        self, lib: InstalledLibrary, theme_registry: ThemeRegistry | None, context: 'SessionContext',
    ):
        """Render library themes (workbench and node)."""
        if not theme_registry:
            ui.label('Theme registry not available.').classes('hw-text-muted italic text-sm')
            return

        prefix = f'{lib.library_id}:theme:'
        items = [
            (k, theme_registry.get(k))
            for k in theme_registry.list_names()
            if k.startswith(prefix)
        ]
        items = [(k, c) for k, c in items if c]

        if not items:
            ui.label('No themes registered for this library.').classes(
                'hw-text-muted italic text-sm py-4'
            )
            return

        for key, cls in sorted(items, key=lambda x: x[0]):
            ident = getattr(cls, 'class_identity', None)
            label = getattr(ident, 'label', None) or key.split(':')[-1]
            theme_type = getattr(ident, 'theme_type', '') or ''
            type_icon = 'palette' if theme_type == 'workbench' else 'brush'
            with ui.row().classes(
                'w-full items-start gap-3 px-3 py-2 rounded hover:bg-white/10 cursor-pointer'
            ).on(
                'click',
                lambda k=key, entry=lib, ctx=context: self._select_component(
                    entry, k.split(':')[-1], 'themes', ctx, registry_key=k
                ),
            ):
                ui.icon(type_icon, size='18px').classes('hw-text-dim mt-0.5 flex-shrink-0')
                with ui.column().classes('gap-0 flex-1 min-w-0'):
                    with ui.row().classes('items-center gap-2'):
                        ui.label(label).classes('text-sm font-medium')
                        if theme_type:
                            ui.badge(theme_type).props('outline color=grey')
                    ui.label(key).classes('text-xs hw-text-dim font-mono')

    def _render_panels_tab(
        self, lib: InstalledLibrary, panel_registry: PanelRegistry | None, context: 'SessionContext',
    ):
        """Render panels registered by this library."""
        if not panel_registry:
            ui.label('Panel registry not available.').classes('hw-text-muted italic text-sm')
            return

        prefix = f'{lib.library_id}:panel:'
        items = [
            (k, panel_registry.get(k))
            for k in panel_registry.list_names()
            if k.startswith(prefix)
        ]
        items = [(k, c) for k, c in items if c and hasattr(c, 'class_identity') and c.class_identity]

        if not items:
            ui.label('No panels registered for this library.').classes(
                'hw-text-muted italic text-sm py-4'
            )
            return

        for key, cls in sorted(items, key=lambda x: x[1].class_identity.label or x[0]):
            ident = cls.class_identity
            with ui.row().classes(
                'w-full items-start gap-3 px-3 py-2 rounded hover:bg-white/10 cursor-pointer'
            ).on(
                'click',
                lambda k=key, entry=lib, ctx=context: self._select_component(
                    entry, k.split(':')[-1], 'panels', ctx, registry_key=k
                ),
            ):
                ui.icon('view_sidebar', size='18px').classes('hw-text-dim mt-0.5 flex-shrink-0')
                with ui.column().classes('gap-0 flex-1 min-w-0'):
                    ui.label(ident.label or key.split(':')[-1]).classes('text-sm font-medium')
                    with ui.row().classes('items-center gap-2 flex-wrap'):
                        editor_key = getattr(ident, 'editor_key', '') or ''
                        context_str = getattr(ident, 'context', '') or ''
                        if editor_key:
                            ui.label(f'editor: {editor_key}').classes('text-xs hw-text-dim font-mono')
                        if context_str:
                            ui.badge(context_str).props('outline color=grey')
                    ui.label(key).classes('text-xs hw-text-dim font-mono')

    def _render_editors_tab(
        self, lib: InstalledLibrary, editor_registry: EditorTypeRegistry | None,
        context: 'SessionContext',
    ):
        """Render editors registered by this library."""
        if not editor_registry:
            ui.label('Editor registry not available.').classes('hw-text-muted italic text-sm')
            return

        prefix = f'{lib.library_id}:editor:'
        items = [
            (k, editor_registry.get(k))
            for k in editor_registry.list_names()
            if k.startswith(prefix)
        ]
        items = [(k, c) for k, c in items if c and hasattr(c, 'class_identity') and c.class_identity]

        if not items:
            ui.label('No editors registered for this library.').classes(
                'hw-text-muted italic text-sm py-4'
            )
            return

        for key, cls in sorted(items, key=lambda x: x[1].class_identity.label or x[0]):
            ident = cls.class_identity
            default_area = getattr(ident, 'default_area', '') or ''
            description = getattr(ident, 'description', '') or ''
            with ui.row().classes(
                'w-full items-start gap-3 px-3 py-2 rounded hover:bg-white/10 cursor-pointer'
            ).on(
                'click',
                lambda k=key, entry=lib, ctx=context: self._select_component(
                    entry, k.split(':')[-1], 'editors', ctx, registry_key=k
                ),
            ):
                ui.icon('tab', size='18px').classes('hw-text-dim mt-0.5 flex-shrink-0')
                with ui.column().classes('gap-0 flex-1 min-w-0'):
                    with ui.row().classes('items-center gap-2'):
                        ui.label(ident.label or key.split(':')[-1]).classes('text-sm font-medium')
                        if default_area:
                            ui.badge(default_area).props('outline color=grey')
                    if description:
                        ui.label(description).classes('text-xs hw-text-dim truncate')
                    ui.label(key).classes('text-xs hw-text-dim font-mono')

    # ─────────────────────────────────────────────────────────────────────────
    # Component click → notify context
    # ─────────────────────────────────────────────────────────────────────────

    def _select_component(
        self,
        lib: InstalledLibrary,
        class_name: str,
        comp_type: str,
        context: 'SessionContext',
        registry_key: str | None = None,
    ):
        """Set context.active_component and fire ACTIVE_COMPONENT_CHANGED."""
        context.active_component = {
            'lib': lib,
            'class_name': class_name,
            'comp_type': comp_type,
            'registry_key': registry_key,
        }
        # Ensure the right area shows the ComponentDetailEditor.
        switch_right = context.metadata.get('switch_right_area')
        if switch_right is not None:
            try:
                switch_right(_K_COMPONENT_DETAIL)
            except Exception:
                pass

        session = context.session
        if session is not None:
            session.notify_context_changed(
                ContextChangedEvent(
                    change_type=ContextChangeType.ACTIVE_COMPONENT_CHANGED,
                    source_editor='library_detail',
                )
            )

    # ─────────────────────────────────────────────────────────────────────────
    # Enable / Disable
    # ─────────────────────────────────────────────────────────────────────────

    def _enable_library(self, library_id: str, manager, context: 'SessionContext'):
        manager.enable_library(library_id)
        ui.notify(f'Enabled: {library_id}', type='positive')
        context.active_library = self._reload_installed(library_id, manager)
        self._notify_library_changed(context)

    def _disable_library(self, library_id: str, manager, context: 'SessionContext'):
        manager.disable_library(library_id)
        ui.notify(f'Disabled: {library_id}', type='warning')
        context.active_library = self._reload_installed(library_id, manager)
        self._notify_library_changed(context)

    def _reload_installed(
        self, library_id: str, manager
    ) -> InstalledLibrary | None:
        """Fetch a fresh InstalledLibrary snapshot after an enable/disable."""
        try:
            libs = manager.list_installed()
            return next((lib for lib in libs if lib.library_id == library_id), None)
        except Exception:
            return None

    def _find_installed_by_dist_name(
        self, dist_name: str, manager
    ) -> InstalledLibrary | None:
        """Find a freshly installed library by distribution name."""
        try:
            libs = manager.list_installed()
            return next((lib for lib in libs if lib.distribution_name == dist_name), None)
        except Exception:
            return None

    def _notify_library_changed(self, context: 'SessionContext') -> None:
        """Broadcast ACTIVE_LIBRARY_CHANGED so all editors (incl. LibraryBrowser) refresh."""
        session = context.session
        if session is not None:
            session.notify_context_changed(
                ContextChangedEvent(
                    change_type=ContextChangeType.ACTIVE_LIBRARY_CHANGED,
                    source_editor='library_detail',
                )
            )

    # ─────────────────────────────────────────────────────────────────────────
    # Uninstall
    # ─────────────────────────────────────────────────────────────────────────

    def _confirm_uninstall(
        self,
        library_id: str,
        label: str,
        manager,
        context: 'SessionContext',
    ):
        """Show confirmation dialog, then uninstall."""
        with ui.dialog() as dialog, ui.card():
            ui.label(f'Uninstall {label}?').classes('text-lg font-bold')
            ui.label(
                'This will disable the library and remove it from the venv. '
                'Any graph nodes using this library will show as errors.'
            ).classes('hw-text-muted mb-4')

            async def confirm_and_uninstall():
                dialog.close()
                await self._do_uninstall(library_id, label, manager, context)

            with ui.row().classes('w-full justify-end gap-2'):
                ui.button('Cancel', on_click=dialog.close)
                ui.button(
                    'Uninstall', on_click=confirm_and_uninstall
                ).props('color=negative')

        dialog.open()

    @staticmethod
    def _create_log_in_card(container, title: str) -> 'ui.log':
        """Append an expandable terminal log inside a container."""
        with container:
            with ui.expansion(title, icon='terminal', value=True).classes(
                'w-full min-w-0'
            ):
                log = ui.log(max_lines=50).classes('w-full h-32')
        return log

    async def _do_uninstall(
        self,
        library_id: str,
        label: str,
        manager,
        context: 'SessionContext',
    ):
        """Perform uninstall with streaming log output."""
        ui.notify(f'Uninstalling {label}…', type='info')
        log = self._create_log_in_card(self._fixed, f'Uninstalling {label}…')

        success, message = await manager.uninstall_streaming(library_id, log.push)

        if success:
            log.push(f'--- {label} uninstalled successfully ---')
            ui.notify(f'Uninstalled: {label}', type='positive')
        else:
            log.push(f'--- ERROR: {message} ---')
            ui.notify(message, type='negative')

        # Clear the active library and notify all editors
        context.active_library = None
        self._notify_library_changed(context)

    # ─────────────────────────────────────────────────────────────────────────
    # Edit dialog (project library identity + optional rename)
    # ─────────────────────────────────────────────────────────────────────────

    def _is_project_library(
        self, lib: InstalledLibrary, marketplace_path: str | None
    ) -> bool:
        """Return True if lib is the local project library (lives under workspace/barn/)."""
        if not marketplace_path or not lib.source_path:
            return False
        workspace_root = Path(marketplace_path).parent.parent
        return Path(lib.source_path).is_relative_to(workspace_root / 'barn')

    def _build_edit_dialog(
        self,
        lib: InstalledLibrary,
        marketplace_path: str | None,
        manager,
        context: 'SessionContext',
    ) -> 'ui.dialog':
        """Build the Edit dialog — all identity fields immediately editable.

        The package name field is locked behind a padlock icon. Clicking the
        padlock shows a warning dialog; if the user confirms, the name field
        becomes editable and saving triggers a full rename. When only identity
        fields are changed (name unchanged), a lightweight save is performed
        without any directory rename or uv sync.
        """
        old_name_part = (
            lib.distribution_name.removeprefix('haybale-')
            if lib.distribution_name
            else lib.library_id
        )
        _state = {'unlocked': False}

        with ui.dialog() as edit_dialog, ui.card().style('width: 480px;').classes('gap-3'):
            ui.label('Edit Library').classes('text-lg font-bold')
            ui.label(f'haybale-{old_name_part}').classes('text-sm text-gray-500 font-mono')
            ui.separator()

            ui.label('Identity').classes(
                'text-xs font-bold text-gray-400 uppercase tracking-wider'
            )
            label_input      = ui.input(label='Label',       value=lib.label).classes('w-full')
            version_input    = ui.input(label='Version',     value=lib.version or '0.1.0').classes('w-full')
            desc_input       = ui.input(label='Description', value=lib.description).classes('w-full')
            author_input     = ui.input(label='Author',      value=lib.author).classes('w-full')
            author_url_input = ui.input(label='Author URL',  value=lib.author_url).classes('w-full')
            url_input        = ui.input(label='URL',         value=lib.url).classes('w-full')
            tags_input = ui.input(
                label='Tags (comma-separated)',
                value=', '.join(lib.tags or []),
            ).classes('w-full')
            deps_input = ui.input(
                label='Dependencies (comma-separated)',
                value=', '.join(lib.dependencies or []),
            ).classes('w-full')

            ui.separator()

            ui.label('Package Name').classes(
                'text-xs font-bold text-gray-400 uppercase tracking-wider'
            )
            with ui.row().classes('w-full items-center gap-2'):
                ui.label('haybale-').classes('text-sm font-mono text-gray-500 flex-shrink-0')
                name_input = (
                    ui.input(value=old_name_part)
                    .classes('flex-1')
                    .props('dense')
                )
                name_input.disable()
                lock_btn = (
                    ui.button(icon='lock')
                    .props('flat round dense size=sm color=orange')
                    .tooltip('Click to unlock — renaming breaks saved graph references')
                )
            preview_label = ui.label('').classes('text-xs text-gray-400 font-mono')

            def _update_preview():
                v = name_input.value.strip()
                if _state['unlocked'] and v and v != old_name_part:
                    mod = 'haybale_' + re.sub(r'[^a-zA-Z0-9_]', '_', v.lower())
                    preview_label.set_text(f'Package: haybale-{v}  ·  Module: {mod}')
                else:
                    preview_label.set_text('')

            name_input.on('update:model-value', lambda _: _update_preview())

            async def _save():
                new_name = name_input.value.strip()
                identity = {
                    'label':        label_input.value.strip(),
                    'version':      version_input.value.strip().lstrip('vV'),
                    'description':  desc_input.value.strip(),
                    'url':          url_input.value.strip(),
                    'author':       author_input.value.strip(),
                    'author_url':   author_url_input.value.strip(),
                    'tags':         [t.strip() for t in tags_input.value.split(',') if t.strip()],
                    'dependencies': [d.strip() for d in deps_input.value.split(',') if d.strip()],
                }
                edit_dialog.close()
                if _state['unlocked'] and new_name and new_name != old_name_part:
                    await self._do_rename(lib, new_name, identity, marketplace_path, manager, context)
                else:
                    await self._do_update_identity(lib, identity, marketplace_path, manager, context)

            with ui.row().classes('w-full justify-end gap-2 mt-2'):
                ui.button('Cancel', on_click=edit_dialog.close).props('flat size=sm')
                ui.button('Save Changes', on_click=_save).props('color=primary size=sm')

        # ── Warning dialog ────────────────────────────────────────────────────
        with ui.dialog() as warn_dialog, ui.card().classes('max-w-md gap-3'):
            with ui.row().classes('items-center gap-2'):
                ui.icon('warning', size='24px').classes('text-orange-500')
                ui.label('Rename changes registry keys').classes('text-lg font-bold')
            ui.separator()
            ui.label(
                'Every node and widget from this library is identified in saved graphs '
                'by its registry key, which includes the library name '
                f'(e.g. "{lib.library_id}:node:…"). '
                'After renaming, graphs that reference this library from other projects '
                'will fail to load those nodes. If your nodes are using absolute '
                'from ... import ... statements referencing this library, '
                'those will also need to be updated.'
            ).classes('text-sm text-gray-600')
            ui.label(
                "Only proceed if you have a backup of this project and this project's "
                "graphs/ folder is the only place these nodes are used — or if you "
                "really know what you're doing. Alternatively be prepared to enter a "
                "world of pain."
            ).classes('text-sm text-gray-500 italic')

            def _unlock_name():
                warn_dialog.close()
                _state['unlocked'] = True
                name_input.enable()
                lock_btn.props('icon=lock_open color=blue-grey')

            with ui.row().classes('w-full justify-end gap-2 mt-1'):
                ui.button('Cancel', on_click=warn_dialog.close).props('flat size=sm')
                ui.button(
                    'Unlock Name Field', icon='lock_open', on_click=_unlock_name,
                ).props('color=warning size=sm')

        def _lock_clicked():
            if _state['unlocked']:
                _state['unlocked'] = False
                name_input.value = old_name_part
                name_input.disable()
                lock_btn.props('icon=lock color=orange')
                preview_label.set_text('')
            else:
                warn_dialog.open()

        lock_btn.on('click', lambda: _lock_clicked())
        return edit_dialog

    async def _do_update_identity(
        self,
        lib: InstalledLibrary,
        identity: dict,
        marketplace_path: str | None,
        manager,
        context: 'SessionContext',
    ):
        """Save identity fields, then rescan so the in-memory identity is refreshed."""
        if not marketplace_path:
            ui.notify('No project workspace set.', type='negative')
            return
        workspace_root = str(Path(marketplace_path).parent.parent)

        success, message = await asyncio.to_thread(
            manager.update_library_identity,
            lib.library_id,
            workspace_root,
            identity,
        )
        if not success:
            ui.notify(message, type='negative')
            return

        # Rescan
        manager._invalidate_caches()
        await asyncio.to_thread(manager.registry.scan_for_libraries)
        manager.registry.enable_all_libraries()

        ui.notify(f'Saved: {identity.get("label", lib.label)}', type='positive')

        # Reload the freshly-saved library into context and re-render
        try:
            libs = manager.list_installed()
            context.active_library = next(
                (entry for entry in libs if entry.library_id == lib.library_id), None
            )
        except Exception:
            pass
        self._container.clear()
        self._rebuild(context)

    async def _do_rename(
        self,
        lib: InstalledLibrary,
        new_name: str,
        new_identity: dict | None,
        marketplace_path: str | None,
        manager,
        context: 'SessionContext',
    ):
        """Perform rename with streaming log output."""
        if not marketplace_path:
            ui.notify('No project workspace set.', type='negative')
            return
        old_library_id = lib.library_id
        ui.notify(f'Renaming {lib.label}…', type='info')
        log = self._create_log_in_card(
            self._fixed, f'Renaming to haybale-{new_name}…'
        )
        workspace_root = str(Path(marketplace_path).parent.parent)

        success, message = await manager.rename_project_library_streaming(
            library_id=lib.library_id,
            new_name=new_name,
            workspace_root=workspace_root,
            on_output=log.push,
            new_identity=new_identity,
        )

        if success:
            log.push(f'--- Renamed to haybale-{new_name} ---')
            ui.notify(f'Renamed to haybale-{new_name}', type='positive')
        else:
            log.push(f'--- ERROR: {message} ---')
            ui.notify(message, type='negative')

        # Build the patch dialog BEFORE clearing (slot context must be clean)
        patch_dialog = (
            self._build_graph_patch_dialog(old_library_id, new_name, workspace_root)
            if success
            else None
        )

        context.active_library = None
        self._container.clear()
        self._rebuild(context)

        if patch_dialog is not None:
            patch_dialog.open()

    # ─────────────────────────────────────────────────────────────────────────
    # Graph file patching (post-rename)
    # ─────────────────────────────────────────────────────────────────────────

    def _build_graph_patch_dialog(
        self, old_library_id: str, new_library_id: str, workspace_root: str
    ) -> 'ui.dialog | None':
        """Build (but don't open) a dialog offering to patch graph files."""
        graphs_dir = Path(workspace_root) / 'graphs'
        if not graphs_dir.exists():
            return None

        old_prefix = old_library_id + ':'
        matching = [
            f for f in sorted(graphs_dir.glob('**/*.json'))
            if old_prefix in f.read_text()
        ]
        if not matching:
            return None

        with ui.dialog() as dialog, ui.card().classes('max-w-lg gap-3'):
            with ui.row().classes('items-center gap-2'):
                ui.icon('find_replace', size='22px').classes('text-blue-500')
                ui.label('Update graph files?').classes('text-lg font-bold')
            ui.separator()
            ui.label(
                f'Found {len(matching)} graph file(s) in graphs/ that reference '
                f'"{old_library_id}:…" registry keys. '
                f'Replace them with "{new_library_id}:…"?'
            ).classes('text-sm text-gray-600')
            with ui.column().classes('gap-0 max-h-28 overflow-y-auto'):
                for f in matching[:6]:
                    ui.label(f.name).classes('text-xs font-mono text-gray-400')
                if len(matching) > 6:
                    ui.label(f'… and {len(matching) - 6} more').classes(
                        'text-xs text-gray-400 italic'
                    )

            async def _patch_and_close():
                dialog.close()
                count, errors = await asyncio.to_thread(
                    self._patch_graph_files, graphs_dir, old_library_id, new_library_id
                )
                if errors:
                    ui.notify(
                        f'Patched {count} file(s); {len(errors)} error(s)',
                        type='warning',
                    )
                else:
                    ui.notify(f'Updated {count} graph file(s)', type='positive')

            with ui.row().classes('w-full justify-end gap-2 mt-1'):
                ui.button('Skip', on_click=dialog.close).props('flat size=sm')
                ui.button(
                    'Update files',
                    icon='find_replace',
                    on_click=_patch_and_close,
                ).props('color=primary size=sm')

        return dialog

    @staticmethod
    def _patch_graph_files(
        graphs_dir: Path, old_id: str, new_id: str
    ) -> tuple[int, list[str]]:
        """Replace all occurrences of old_id: with new_id: in .json graph files."""
        old_prefix = old_id + ':'
        new_prefix = new_id + ':'
        count = 0
        errors: list[str] = []
        for f in graphs_dir.glob('**/*.json'):
            try:
                text = f.read_text()
                if old_prefix in text:
                    f.write_text(text.replace(old_prefix, new_prefix))
                    count += 1
            except OSError as e:
                errors.append(f'{f.name}: {e}')
        return count, errors

    # ─────────────────────────────────────────────────────────────────────────
    # Install
    # ─────────────────────────────────────────────────────────────────────────

    async def _install_package(
        self,
        install_spec: str,
        name: str,
        button,
        manager,
        context: 'SessionContext',
    ):
        """Install a package with streaming log output."""
        if button:
            try:
                button.disable()
                button.props('loading')
            except Exception:
                pass
        ui.notify(f'Installing {name}…', type='info')
        log = self._create_log_in_card(self._fixed, f'Installing {name}…')

        success, message = await manager.install_streaming(install_spec, log.push)

        if success:
            log.push(f'--- {name} installed successfully ---')
            ui.notify(f'Installed: {name}', type='positive')
            # Point context at the newly installed library so the detail view
            # shows the full installed header + tabs on rebuild.
            installed = self._find_installed_by_dist_name(name, manager)
            if installed:
                context.active_library = installed
            self._notify_library_changed(context)
        else:
            log.push(f'--- ERROR: {message} ---')
            ui.notify(message, type='negative')

    def _open_version_picker(
        self, pkg: MarketplaceEntry, manager, context: 'SessionContext'
    ):
        """Dialog to fetch and select a specific version for installation."""
        with ui.dialog() as dialog, ui.card().classes('min-w-80'):
            ui.label(f'Install specific version — {pkg.name}').classes(
                'text-lg font-bold mb-2'
            )
            version_select = (
                ui.select(
                    options=['Loading…'],
                    value='Loading…',
                    label='Version',
                )
                .classes('w-full')
                .props('dense')
            )
            status = ui.label('Fetching versions…').classes('text-xs text-gray-400')

            async def load_versions():
                versions = await manager.fetch_versions(pkg)
                if versions:
                    version_select.options = versions
                    version_select.value = versions[0]
                    status.text = f'{len(versions)} versions available'
                else:
                    version_select.options = ['(unavailable)']
                    version_select.value = '(unavailable)'
                    status.text = 'Could not fetch version list'

            async def install_selected(e):
                selected = version_select.value
                if not selected or selected in ('Loading…', '(unavailable)'):
                    return
                dialog.close()
                spec = manager.build_versioned_spec(pkg, selected)
                await self._install_package(spec, pkg.name, None, manager, context)

            with ui.row().classes('w-full justify-end gap-2 mt-4'):
                ui.button('Cancel', on_click=dialog.close).props('flat')
                ui.button(
                    'Install', on_click=install_selected
                ).props('color=primary')

        dialog.open()
        asyncio.ensure_future(load_versions())

    # ─────────────────────────────────────────────────────────────────────────
    # Marketplace overview fetch (async)
    # ─────────────────────────────────────────────────────────────────────────

    async def _fetch_marketplace_overview(self, pkg: MarketplaceEntry) -> 'str | None':
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

        def _try_urls(urls: list) -> 'str | None':
            for url in urls:
                try:
                    with urllib.request.urlopen(url, timeout=6) as resp:
                        return resp.read().decode('utf-8', errors='replace')
                except Exception:
                    continue
            return None

        # ── 1. Explicit docs_url ──────────────────────────────────────────────
        if pkg.docs_url:
            p = Path(pkg.docs_url)
            if p.is_dir():
                for candidate in (p / 'OVERVIEW.md', p / 'QUICKREF.md'):
                    if candidate.exists():
                        return candidate.read_text()
            elif p.is_file():
                return p.read_text()
            elif pkg.docs_url.startswith('http'):
                url = pkg.docs_url.rstrip('/')
                if url.endswith('.md'):
                    candidates = [url]
                else:
                    candidates = [f'{url}/OVERVIEW.md', f'{url}/QUICKREF.md']
                content = await asyncio.to_thread(_try_urls, candidates)
                if content:
                    return content

        # ── 2. Heuristic: derive raw GitHub URL ──────────────────────────────
        module_name = pkg.name.replace('-', '_')

        subdir = ''
        if pkg.install_spec and '#subdirectory=' in pkg.install_spec:
            subdir = pkg.install_spec.split('#subdirectory=')[-1].strip('/')

        def _github_raw_base(url: str) -> 'str | None':
            url = url.rstrip('/').removesuffix('.git')
            if 'github.com' not in url:
                return None
            return url.replace(
                'https://github.com/', 'https://raw.githubusercontent.com/'
            )

        raw_base = None
        if pkg.source_url and 'github.com' in pkg.source_url:
            raw_base = _github_raw_base(pkg.source_url)
        elif pkg.source == 'git' and pkg.install_spec:
            git_url = (
                pkg.install_spec
                .removeprefix('git+')
                .split('@')[0]
                .split('#')[0]
                .rstrip('/')
            )
            raw_base = _github_raw_base(git_url)

        if raw_base:
            candidates = []
            for branch in ('main', 'master'):
                prefix = f'{raw_base}/{branch}'
                pkg_prefix = (
                    f'{prefix}/{subdir}/{module_name}'
                    if subdir
                    else f'{prefix}/{module_name}'
                )
                candidates.append(f'{pkg_prefix}/OVERVIEW.md')
                candidates.append(f'{pkg_prefix}/QUICKREF.md')
            for branch in ('main', 'master'):
                prefix = f'{raw_base}/{branch}'
                if subdir:
                    candidates.append(f'{prefix}/{subdir}/OVERVIEW.md')
                candidates.append(f'{prefix}/OVERVIEW.md')

            content = await asyncio.to_thread(_try_urls, candidates)
            if content:
                return content

        # ── 3. PyPI long_description fallback ────────────────────────────────
        if pkg.source == 'pypi':
            def _pypi_desc():
                try:
                    url = f'https://pypi.org/pypi/{pkg.name}/json'
                    with urllib.request.urlopen(url, timeout=8) as resp:
                        data = json.loads(resp.read())
                    return data.get('info', {}).get('description') or None
                except Exception:
                    return None
            return await asyncio.to_thread(_pypi_desc)

        return None

    async def _load_marketplace_overview(
        self,
        pkg: MarketplaceEntry,
        loading_row,
        content_area,
    ):
        """Fetch overview content async and populate the content_area."""
        content = await self._fetch_marketplace_overview(pkg)
        loading_row.set_visibility(False)
        with content_area:
            if content:
                ui.markdown(content).classes('w-full')
            else:
                ui.label('No overview available for this package.').classes(
                    'text-gray-400 text-sm italic'
                )
                if pkg.source_url:
                    ui.link(
                        'View source repository →',
                        pkg.source_url,
                        new_tab=True,
                    ).classes('text-xs text-blue-500 mt-1')
