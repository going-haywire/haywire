"""
Library manager page — VS Code-style 3-panel layout.

Left panel:   searchable / filterable library list (Enabled / Disabled / Available)
Center panel: unified library detail — marketplace header + optional installed tabs
Right panel:  per-component documentation (hidden until a node / widget is clicked)
"""

import asyncio
import re
from pathlib import Path

from nicegui import ui

from .library_manager import InstalledLibrary, LibraryManager, MarketplaceEntry


class _WidgetPreviewPort:
    """Minimal mock port used to render a live widget preview without binding."""
    id = 'preview'
    widget_config = {}




class LibraryManagerPage:
    """VS Code-style 3-panel library manager page."""

    def __init__(
        self,
        library_manager: LibraryManager,
        marketplace_path: str | None = None,
        node_registry=None,
        widget_registry=None,
        type_registry=None,
        adapter_registry=None,
        renderer_registry=None,
    ):
        self.manager = library_manager
        self.marketplace_path = marketplace_path
        self.node_registry = node_registry
        self.widget_registry = widget_registry
        self.type_registry = type_registry
        self.adapter_registry = adapter_registry
        self.renderer_registry = renderer_registry

        # Selection state
        self._selected_id: str | None = None
        self._selected_is_marketplace: bool = False

        # Filter / search state
        self._search_query: str = ''
        self._filter_enabled: bool = True
        self._filter_disabled: bool = True
        self._filter_available: bool = True

        # UI containers (assigned in create_page)
        self._left_container = None
        self._left_list_container = None   # rebuilt on search / refresh
        self._center_fixed = None          # header + metadata + tabs bar (non-scrolling)
        self._center_scroll = None         # tab panels / placeholder (scrolling)
        self._right_container = None
        self._status_label = None
        self._search_input = None
        self._filter_btns: dict[str, ui.button] = {}

        # Async-populated entries from remote [[sources]] in ~/.haywire/marketplace.toml
        self._extra_marketplace_entries: list[MarketplaceEntry] = []

        # Cache for local marketplace file reads; invalidated on refresh/install/rename
        self._marketplace_cache: list[MarketplaceEntry] | None = None

    # ─────────────────────────────────────────────────────────────────────────
    # Page structure
    # ─────────────────────────────────────────────────────────────────────────

    def create_page(self):
        """Build the /libraries page UI."""
        ui.add_css(
            '.nicegui-content { padding: 0 !important; max-width: none !important;'
            ' height: 100vh !important; overflow: hidden !important; }'
            # Center panel tabs: allow overflow so markdown / lists aren't clipped.
            ' .hw-center-tab-panels .q-panel-parent { overflow: visible !important; }'
            ' .hw-center-tab-panels .q-panel.scroll { overflow: visible !important; }'
            # Right panel tabs: thread height:100% through Quasar's q-panel.scroll
            # wrapper so the codemirror can fill the remaining space and the Save
            # button stays visible without requiring outer-panel scrolling.
            ' .hw-right-tab-panels > .q-panel.scroll'
            ' { height: 100%; overflow: hidden; }'
            ' .hw-panel-divider:hover { background-color: #93c5fd !important; }'
        )
        ui.add_head_html('''<script>
(function () {
  var drag = null;
  document.addEventListener("mousedown", function (e) {
    var divider = e.target.closest ? e.target.closest(".hw-panel-divider") : null;
    if (!divider) return;
    e.preventDefault();
    var prev = divider.previousElementSibling;
    var next = divider.nextElementSibling;
    if (!prev || !next) return;
    var container = divider.parentElement;
    Array.from(container.children).forEach(function (child) {
      if (!child.classList.contains("hw-panel-divider")) {
        var w = child.getBoundingClientRect().width;
        child.style.flex = "none";
        child.style.width = w + "px";
      }
    });
    drag = {
      prev: prev, next: next,
      startX: e.clientX,
      startPrevW: prev.getBoundingClientRect().width,
      startNextW: next.getBoundingClientRect().width
    };
    document.body.style.cursor = "col-resize";
    document.body.style.userSelect = "none";
  });
  document.addEventListener("mousemove", function (e) {
    if (!drag) return;
    var dx = e.clientX - drag.startX;
    var newPrevW = Math.max(150, drag.startPrevW + dx);
    var newNextW = Math.max(200, drag.startNextW - dx);
    drag.prev.style.width = newPrevW + "px";
    drag.next.style.width = newNextW + "px";
  });
  document.addEventListener("mouseup", function () {
    if (drag) {
      drag = null;
      document.body.style.cursor = "";
      document.body.style.userSelect = "";
    }
  });
})();
</script>''')

        with ui.column().classes('w-full h-full gap-0 overflow-hidden'):

            # ── Header ────────────────────────────────────────────────────────
            with ui.row().classes(
                'w-full px-4 py-2 border-b items-center justify-between flex-shrink-0'
            ):
                ui.label('Library Manager').classes('text-xl font-bold')
                self._status_label = ui.label('').classes(
                    'text-sm text-gray-400 flex-1 mx-4'
                )
                ui.button(
                    'Back',
                    icon='arrow_back',
                    on_click=lambda: ui.navigate.to('/'),
                ).props('flat size=sm')
                ui.button(
                    'Refresh',
                    icon='refresh',
                    on_click=self._refresh_all,
                ).props('flat size=sm')

            # ── 3-panel body ──────────────────────────────────────────────────
            with ui.row(wrap=False).classes('flex-1 gap-0 w-full overflow-hidden').style(
                'max-width: 1600px; margin: 0 auto;'
            ):

                # Left panel — 20%, fixed structure (search bar + scroll list)
                with ui.column().classes(
                    'flex-shrink-0 gap-0'
                ).style(
                    'width: 20%; height: 100%; display: flex; flex-direction: column; overflow: hidden;'
                ) as self._left_container:

                    # Fixed top: search input + filter toggles
                    with ui.column().classes('p-2 gap-1.5 border-b flex-shrink-0'):
                        self._search_input = (
                            ui.input(placeholder='Search libraries…')
                            .classes('w-full')
                            .props('dense outlined clearable')
                        )
                        self._search_input.on(
                            'update:model-value',
                            lambda e: self._on_search_update(e.args),
                        )
                        self._search_input.on(
                            'clear',
                            lambda e: self._on_search_update(''),
                        )

                        with ui.row().classes('items-center gap-0.5'):
                            ui.label('Show:').classes(
                                'text-xs text-gray-400 mr-1'
                            )
                            self._make_filter_toggle(
                                'enabled', 'green', 'check_circle', 'Enabled libraries'
                            )
                            self._make_filter_toggle(
                                'disabled', 'orange', 'pause_circle', 'Disabled libraries'
                            )
                            self._make_filter_toggle(
                                'available', 'teal', 'add_circle', 'Available in marketplace'
                            )

                    # Scrollable library list (rebuilt on every refresh)
                    self._left_list_container = ui.scroll_area().style(
                        'flex: 1; height: 0;'
                    )
                    with self._left_list_container:
                        self._render_left_list()

                # Divider between left and center
                ui.element('div').classes('hw-panel-divider flex-shrink-0').style(
                    'width: 5px; height: 100%; cursor: col-resize;'
                    ' border-left: 1px solid #e5e7eb; transition: background-color 0.15s;'
                )

                # Center panel — fixed top (header+tabs) + scrollable content
                with ui.element('div').classes('flex-shrink-0 overflow-hidden').style(
                    'width: 40%; height: 100%; display: flex; flex-direction: column;'
                ):
                    # Non-scrolling section: library header, metadata, tabs bar
                    self._center_fixed = ui.column().classes('flex-shrink-0 w-full gap-0')
                    # Scrollable section: tab panels / placeholder
                    with ui.element('div').style('flex: 1; height: 0; overflow: hidden;'):
                        self._center_scroll = ui.scroll_area().style('width: 100%; height: 100%;')
                    with self._center_scroll:
                        self._render_center_placeholder()

                # Divider between center and right
                ui.element('div').classes('hw-panel-divider flex-shrink-0').style(
                    'width: 5px; height: 100%; cursor: col-resize;'
                    ' border-left: 1px solid #e5e7eb; transition: background-color 0.15s;'
                )

                # Right panel — 40%.
                # Use a plain div (not scroll_area) so that overflow-x: hidden
                # references the parent's fixed 40% width, not the scroll
                # content width.  scroll_area's q-scrollarea__content is
                # position:absolute and grows with its children, meaning
                # width:100% inside it would resolve to the codemirror's
                # expanded width and cause tabs/text to reflow on tab switch.
                self._right_container = ui.element('div').classes(
                    'flex-shrink-0'
                ).style(
                    'width: 40%; height: 100%; overflow: hidden;'
                )
                with self._right_container:
                    self._render_right_placeholder()

        # Kick off async fetch of any HTTP sources in ~/.haywire/marketplace.toml
        asyncio.ensure_future(self._load_remote_sources())

    # ─────────────────────────────────────────────────────────────────────────
    # Left panel — filter controls (built once, updated reactively)
    # ─────────────────────────────────────────────────────────────────────────

    def _make_filter_toggle(
        self, attr: str, color: str, icon: str, tooltip: str
    ):
        """Create a persistent colored icon toggle button."""
        active = getattr(self, f'_filter_{attr}')
        btn_color = color if active else 'grey'
        btn = (
            ui.button(icon=icon)
            .props(f'flat round dense size=sm color={btn_color}')
            .tooltip(tooltip)
        )
        btn.on('click', lambda a=attr: self._toggle_filter(a))
        self._filter_btns[attr] = btn

    def _toggle_filter(self, attr: str):
        """Toggle a filter flag and refresh the list."""
        current = getattr(self, f'_filter_{attr}')
        setattr(self, f'_filter_{attr}', not current)
        colors = {'enabled': 'green', 'disabled': 'orange', 'available': 'teal'}
        new_color = colors[attr] if not current else 'grey'
        self._filter_btns[attr].props(f'color={new_color}')
        self._render_left_list()

    def _on_search_update(self, args=None):
        """Update search query from event args (avoids relying on .value timing)."""
        if args is None:
            value = self._search_input.value
        elif isinstance(args, (list, tuple)):
            value = args[0] if args else ''
        else:
            value = args
        self._search_query = value or ''
        self._render_left_list()

    # ─────────────────────────────────────────────────────────────────────────
    # Left panel — library list (rebuilt on every refresh / search)
    # ─────────────────────────────────────────────────────────────────────────

    def _render_left_list(self):
        """Rebuild the scrollable library list."""
        self._left_list_container.clear()

        libraries = self.manager.list_installed()
        q = self._search_query.lower().strip()

        def lib_matches(lib: InstalledLibrary) -> bool:
            if not q:
                return True
            return (
                q in lib.label.lower()
                or bool(lib.description and q in lib.description.lower())
                or any(q in t.lower() for t in (lib.tags or []))
            )

        def pkg_matches(pkg: MarketplaceEntry) -> bool:
            if not q:
                return True
            return (
                q in pkg.name.lower()
                or bool(pkg.description and q in pkg.description.lower())
                or any(q in t.lower() for t in (pkg.tags or []))
            )

        enabled = (
            sorted(
                [l for l in libraries if l.enabled and lib_matches(l)],
                key=lambda x: x.label,
            )
            if self._filter_enabled
            else []
        )
        disabled = (
            sorted(
                [l for l in libraries if not l.enabled and lib_matches(l)],
                key=lambda x: x.label,
            )
            if self._filter_disabled
            else []
        )
        marketplace = self._get_marketplace_packages()
        available = (
            sorted(
                [
                    p
                    for p in marketplace
                    if not self._is_pkg_installed(p, libraries) and pkg_matches(p)
                ],
                key=lambda x: x.name,
            )
            if self._filter_available
            else []
        )

        with self._left_list_container:
            if enabled:
                self._section_label('ENABLED')
                for lib in enabled:
                    self._left_item(
                        lib.label, lib.version, 'green', lib.library_id, False
                    )

            if disabled:
                self._section_label('DISABLED')
                for lib in disabled:
                    self._left_item(
                        lib.label, lib.version, 'orange', lib.library_id, False
                    )

            if available:
                self._section_label('AVAILABLE')
                for pkg in available:
                    self._left_item(
                        pkg.label or pkg.name, pkg.version, 'teal', pkg.name, True,
                        source_label=pkg.source_label,
                    )

            if not enabled and not disabled and not available:
                with ui.column().classes('w-full items-center py-8 gap-2'):
                    ui.icon('search_off', size='32px').classes('text-gray-300')
                    ui.label('No libraries found').classes(
                        'text-xs text-gray-400 italic'
                    )

    def _section_label(self, title: str):
        ui.label(title).classes(
            'text-xs font-bold text-gray-400 px-2 pt-3 pb-1 tracking-wider'
        )

    def _left_item(
        self,
        label: str,
        version: str,
        dot_color: str,
        item_id: str,
        is_marketplace: bool,
        source_label: str = '',
    ):
        """Render a single clickable row in the library list."""
        is_active = item_id == self._selected_id
        bg = 'bg-blue-50' if is_active else 'hover:bg-gray-100'
        text_cls = 'text-blue-700 font-medium' if is_active else ''
        with ui.row().classes(
            f'w-full items-center gap-2 px-2 py-1.5 rounded cursor-pointer {bg}'
        ).on(
            'click',
            lambda lid=item_id, mp=is_marketplace: self._select(lid, mp),
        ):
            ui.icon('circle', size='xs').classes(
                f'text-{dot_color}-500 flex-shrink-0'
            )
            ui.label(label).classes(f'text-sm flex-1 truncate {text_cls}')
            if source_label:
                ui.label(source_label).classes(
                    'text-xs text-gray-300 flex-shrink-0 font-light'
                )
            if version:
                ui.label(f'v{version}').classes(
                    'text-xs text-gray-400 flex-shrink-0'
                )

    # ─────────────────────────────────────────────────────────────────────────
    # Selection dispatcher
    # ─────────────────────────────────────────────────────────────────────────

    def _select(self, item_id: str, is_marketplace: bool):
        """Resolve installed + marketplace data, then render the center panel."""
        self._selected_id = item_id
        self._selected_is_marketplace = is_marketplace
        self._render_right_placeholder()

        all_installed = self.manager.list_installed()

        if is_marketplace:
            pkg = self._find_marketplace_pkg(item_id)
            installed_lib = (
                self._find_installed_for_pkg(pkg, all_installed) if pkg else None
            )
        else:
            installed_lib = next(
                (l for l in all_installed if l.library_id == item_id), None
            )
            pkg = (
                self._find_marketplace_pkg_for_lib(installed_lib)
                if installed_lib
                else None
            )

        self._render_center(installed_lib, pkg)
        self._render_left_list()

    # ─────────────────────────────────────────────────────────────────────────
    # Center panel — unified renderer
    # ─────────────────────────────────────────────────────────────────────────

    def _render_center_placeholder(self):
        """Placeholder shown when nothing is selected."""
        self._center_fixed.clear()
        self._center_scroll.clear()
        with self._center_scroll:
            with ui.column().classes(
                'w-full items-center justify-center gap-2 py-32'
            ):
                ui.icon('library_books', size='48px').classes('text-gray-300')
                ui.label('Select a library to view details').classes(
                    'text-gray-400 text-sm'
                )

    def _render_center(
        self,
        installed_lib: InstalledLibrary | None,
        marketplace_pkg: MarketplaceEntry | None,
    ):
        """
        Unified center panel renderer.

        - installed_lib only  → installed header + tabs (FOLDER / local libs with no marketplace entry)
        - installed_lib + pkg → marketplace header with installed badges + tabs
        - pkg only            → marketplace header + Install button, no tabs
        """
        if not installed_lib and not marketplace_pkg:
            self._render_center_placeholder()
            return

        self._center_fixed.clear()
        self._center_scroll.clear()

        # Determine display properties
        if installed_lib:
            name = installed_lib.label
            version = installed_lib.version
            description = installed_lib.description
            author = installed_lib.author
            # Fall back to marketplace tags when the installed identity has none
            tags = installed_lib.tags or (marketplace_pkg.tags if marketplace_pkg else []) or []
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
        t_types = t_adapters = t_renderers = None

        # ── Fixed section: header + metadata + tabs bar ───────────────────────
        with self._center_fixed:
            with ui.column().classes('w-full px-6 pt-6 min-w-0 gap-1'):

                # ── Header ────────────────────────────────────────────────────
                with ui.row().classes('w-full items-start justify-between mb-2'):
                    with ui.column().classes('gap-0.5 min-w-0 flex-1'):
                        _title_url = (installed_lib.url if installed_lib else '') or ''
                        if _title_url.startswith('http'):
                            with ui.row().classes('items-center gap-1'):
                                ui.label(name).classes('text-2xl font-bold')
                                with ui.link(target=_title_url, new_tab=True).style('line-height:0'):
                                    ui.icon('open_in_new', size='16px').classes('text-blue-400 opacity-60')
                        else:
                            ui.label(name).classes('text-2xl font-bold break-words')
                        with ui.row().classes('items-center gap-2 mt-1 flex-wrap'):
                            ui.label(f'v{version}').classes('text-sm text-gray-400')
                            _dist_name = (
                                (installed_lib.distribution_name if installed_lib else None)
                                or (marketplace_pkg.name if marketplace_pkg else None)
                            )
                            if _dist_name:
                                ui.label(_dist_name).classes('text-xs text-gray-300 font-mono')
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

                    # ── Action buttons ────────────────────────────────────────
                    with ui.row().classes('gap-1 flex-shrink-0 items-center'):
                        if installed_lib:
                            # Enable / Disable toggle
                            if installed_lib.enabled:
                                ui.button(
                                    'Disable',
                                    icon='pause',
                                    on_click=lambda lid=installed_lib.library_id: (
                                        self._disable_library(lid)
                                    ),
                                ).props('size=sm color=orange flat')
                            else:
                                ui.button(
                                    'Enable',
                                    icon='play_arrow',
                                    on_click=lambda lid=installed_lib.library_id: (
                                        self._enable_library(lid)
                                    ),
                                ).props('size=sm color=green flat')

                            # Rename (project lib) or Uninstall (other removable installs)
                            if self._is_project_library(installed_lib):
                                ui.button(
                                    'Edit',
                                    icon='edit',
                                    on_click=lambda _lib=installed_lib: (
                                        self._build_edit_dialog(_lib).open()
                                    ),
                                ).props('size=sm color=blue flat')
                            elif installed_lib.install_type in ('REGULAR', 'EDITABLE'):
                                with ui.row().classes('gap-0 items-center'):
                                    ui.button(
                                        'Uninstall',
                                        on_click=lambda lid=installed_lib.library_id, ln=installed_lib.label: (
                                            self._confirm_uninstall(lid, ln)
                                        ),
                                    ).props('size=sm color=negative flat')
                                    with ui.button(icon='arrow_drop_down').props(
                                        'size=sm color=negative flat'
                                    ):
                                        with ui.menu():
                                            if update_available and marketplace_pkg:
                                                ui.menu_item(
                                                    f'Update to v{marketplace_pkg.version}',
                                                    on_click=lambda e, spec=marketplace_pkg.install_spec, n=marketplace_pkg.name: (
                                                        self._install_package(spec, n, e.sender)
                                                    ),
                                                )
                                            if marketplace_pkg:
                                                ui.menu_item(
                                                    'Install specific version…',
                                                    on_click=lambda p=marketplace_pkg: (
                                                        self._open_version_picker(p)
                                                    ),
                                                )
                                            ui.separator()
                                            ui.menu_item(
                                                'Uninstall permanently',
                                                on_click=lambda lid=installed_lib.library_id, ln=installed_lib.label: (
                                                    self._confirm_uninstall(lid, ln)
                                                ),
                                            )
                        else:
                            # Not installed — simple Install button
                            ui.button(
                                'Install',
                                icon='download',
                                on_click=lambda e, spec=marketplace_pkg.install_spec, n=marketplace_pkg.name: (
                                    self._install_package(spec, n, e.sender)
                                ),
                            ).props('color=primary size=sm')

                # ── Metadata ──────────────────────────────────────────────────
                if description:
                    ui.label(description).classes('text-gray-600 text-sm mb-1')
                if author:
                    _author_url = (installed_lib.author_url if installed_lib else '') or ''
                    if _author_url.startswith('http'):
                        with ui.row().classes('items-center gap-1'):
                            ui.label('By').classes('text-xs text-gray-400')
                            ui.link(author, _author_url, new_tab=True).classes('text-xs text-blue-400')
                    else:
                        ui.label(f'By {author}').classes('text-xs text-gray-400')
                # Collect relevant links: source repo, docs (website is on the title icon)
                _links: list[tuple[str, str]] = []
                if marketplace_pkg and marketplace_pkg.source_url:
                    _links.append(('Source', marketplace_pkg.source_url))
                if (marketplace_pkg and marketplace_pkg.docs_url
                        and marketplace_pkg.docs_url.startswith('http')):
                    _links.append(('Docs', marketplace_pkg.docs_url))
                if _links:
                    with ui.row().classes('items-center gap-3 mt-1 flex-wrap'):
                        for _lbl, _href in _links:
                            with ui.row().classes('items-center gap-0.5'):
                                ui.link(_lbl, _href, new_tab=True).classes('text-xs text-blue-400')
                                ui.icon('open_in_new', size='10px').classes('text-blue-300')
                if tags:
                    with ui.row().classes('gap-1 mt-2 flex-wrap'):
                        for tag in tags:
                            ui.badge(tag).props('outline color=grey')
                if marketplace_pkg and marketplace_pkg.source_label:
                    with ui.row().classes('items-center gap-1 mt-2 flex-wrap'):
                        ui.label('Feed:').classes('text-xs text-gray-400')
                        ui.button(
                            marketplace_pkg.source_label,
                            icon='edit',
                            on_click=lambda sf=marketplace_pkg.source_file,
                                        so=marketplace_pkg.source_origin: (
                                self._open_source_editor(sf, so)
                            ),
                        ).props('flat dense size=xs color=blue-grey')
                        if marketplace_pkg.source_origin:
                            ui.label(f'→ {marketplace_pkg.source_origin}').classes(
                                'text-xs text-gray-400 truncate'
                            )

                # ── Tabs bar (only when library is installed) ─────────────────
                if installed_lib:
                    ui.separator().classes('mt-4')
                    with ui.tabs().classes('w-full').props('dense') as tabs:
                        t_overview  = ui.tab('Overview',  icon='description')
                        t_nodes     = ui.tab('Nodes',     icon='account_tree')
                        t_widgets   = ui.tab('Widgets',   icon='widgets')
                        t_types     = ui.tab('Types',     icon='category')
                        t_adapters  = ui.tab('Adapters',  icon='swap_horiz')
                        t_renderers = ui.tab('Renderers', icon='brush')

        # ── Scrollable section: tab panels / placeholder ──────────────────────
        with self._center_scroll:
            if installed_lib and tabs is not None:
                with ui.tab_panels(tabs, value=t_overview).classes(
                    'w-full hw-center-tab-panels'
                ).style('overflow: visible !important;'):
                    with ui.tab_panel(t_overview):
                        with ui.column().classes('w-full p-6 gap-1'):
                            self._render_overview(installed_lib)
                    with ui.tab_panel(t_nodes):
                        with ui.column().classes('w-full p-6 gap-1'):
                            self._render_nodes_tab(installed_lib)
                    with ui.tab_panel(t_widgets):
                        with ui.column().classes('w-full p-6 gap-1'):
                            self._render_widgets_tab(installed_lib)
                    with ui.tab_panel(t_types):
                        with ui.column().classes('w-full p-6 gap-1'):
                            self._render_generic_component_tab(installed_lib, self.type_registry, 'types')
                    with ui.tab_panel(t_adapters):
                        with ui.column().classes('w-full p-6 gap-1'):
                            self._render_generic_component_tab(
                                installed_lib, self.adapter_registry, 'adapters'
                            )
                    with ui.tab_panel(t_renderers):
                        with ui.column().classes('w-full p-6 gap-1'):
                            self._render_generic_component_tab(
                                installed_lib, self.renderer_registry, 'renderers'
                            )

            elif marketplace_pkg and not installed_lib:
                # Marketplace-only: async-load OVERVIEW.md from source repo
                with ui.column().classes('w-full p-6 gap-2'):
                    loading_row = ui.row().classes('items-center gap-2')
                    with loading_row:
                        ui.spinner(size='sm')
                        ui.label('Loading overview…').classes(
                            'text-sm text-gray-400'
                        )
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
        """Render OVERVIEW.md or a helpful fallback.

        lib.source_path is the Python package directory itself
        (e.g. .../haybale_visiongraph/), so OVERVIEW.md is directly inside it.
        """
        source = Path(lib.source_path) if lib.source_path else None
        overview = source / 'OVERVIEW.md' if source else None

        if overview and overview.exists():
            ui.markdown(overview.read_text()).classes('w-full')
        else:
            with ui.column().classes('gap-2 py-4'):
                ui.label('No OVERVIEW.md found.').classes(
                    'text-gray-400 italic text-sm'
                )
                ui.label(
                    'Run /docs to generate library documentation.'
                ).classes('text-xs text-gray-400')

    def _render_nodes_tab(self, lib: InstalledLibrary):
        """Render the node list grouped by menu category."""
        if not self.node_registry:
            ui.label('Node registry not available.').classes(
                'text-gray-400 italic text-sm'
            )
            return

        prefix = f'{lib.library_id}:node:'
        items = [
            (k, self.node_registry.get(k))
            for k in self.node_registry.list_names()
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
                'text-gray-400 italic text-sm py-4'
            )
            return

        categories: dict[str, list] = {}
        for key, cls in items:
            menu = getattr(cls.class_identity, 'menu', '') or ''
            cat = menu.split('/')[0].title() if menu else 'Other'
            categories.setdefault(cat, []).append((key, cls))

        for cat in sorted(categories):
            ui.label(cat).classes(
                'text-xs font-bold text-gray-500 mt-4 mb-1 uppercase tracking-wider'
            )
            for key, cls in sorted(
                categories[cat],
                key=lambda x: x[1].class_identity.label or '',
            ):
                ident = cls.class_identity
                class_name = key.split(':')[-1]
                with ui.row().classes(
                    'w-full items-start gap-3 px-3 py-2 rounded'
                    ' hover:bg-gray-50 cursor-pointer'
                ).on(
                    'click',
                    lambda cn=class_name, l=lib: self._select_component(
                        l, cn, 'nodes'
                    ),
                ):
                    with ui.column().classes('gap-0 flex-1 min-w-0'):
                        ui.label(ident.label or class_name).classes(
                            'text-sm font-medium'
                        )
                        if ident.description:
                            ui.label(ident.description).classes(
                                'text-xs text-gray-400 truncate'
                            )

    def _render_widgets_tab(self, lib: InstalledLibrary):
        """Render the widget list with a live preview of each widget."""
        if not self.widget_registry:
            ui.label('Widget registry not available.').classes(
                'text-gray-400 italic text-sm'
            )
            return

        prefix = f'{lib.library_id}:widget:'
        items = [
            (k, self.widget_registry.get(k))
            for k in self.widget_registry.list_names()
            if k.startswith(prefix)
        ]
        items = [
            (k, c)
            for k, c in items
            if c and hasattr(c, 'class_identity') and c.class_identity
        ]

        if not items:
            ui.label('No widgets registered for this library.').classes(
                'text-gray-400 italic text-sm py-4'
            )
            return

        for key, cls in sorted(
            items, key=lambda x: x[1].class_identity.label or ''
        ):
            ident = cls.class_identity
            class_name = key.split(':')[-1]
            with ui.row().classes(
                'w-full items-center gap-4 px-3 py-2 rounded'
                ' hover:bg-gray-50 cursor-pointer'
            ).on(
                'click',
                lambda cn=class_name, l=lib: self._select_component(
                    l, cn, 'widgets'
                ),
            ):
                with ui.column().classes('gap-0 flex-1 min-w-0'):
                    ui.label(ident.label or class_name).classes(
                        'text-sm font-medium'
                    )
                    if ident.description:
                        ui.label(ident.description).classes(
                            'text-xs text-gray-400 truncate'
                        )
                # Live widget preview — uniform fixed-width box
                with ui.element('div').classes(
                    'flex-shrink-0 border rounded-sm bg-white'
                ).style('width: 11rem; min-height: 2.5rem; padding: 4px; overflow: hidden;'):
                    if not hasattr(cls, 'create_element'):
                        # Widget uses render() only (e.g. streaming viewers)
                        with ui.column().classes('w-full items-center py-1 gap-0.5'):
                            ui.icon('videocam', size='18px').classes('text-gray-300')
                            ui.label('live only').classes('text-xs text-gray-300 italic')
                    else:
                        try:
                            mock_port = _WidgetPreviewPort()
                            instance = cls(mock_port)
                            instance.create_element()
                        except Exception:
                            with ui.column().classes('w-full items-center py-1'):
                                ui.label('—').classes('text-xs text-gray-300 italic')

    def _render_generic_component_tab(self, lib: InstalledLibrary, registry, comp_type: str):
        """Render a flat component list (types, adapters, renderers) for this library."""
        comp_singular = comp_type.removesuffix('s')
        if not registry:
            ui.label(f'{comp_singular.title()} registry not available.').classes(
                'text-gray-400 italic text-sm'
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
                'text-gray-400 italic text-sm py-4'
            )
            return

        for key, cls in sorted(items, key=lambda x: x[1].class_identity.label or ''):
            ident = cls.class_identity
            class_name = key.split(':')[-1]
            with ui.row().classes(
                'w-full items-start gap-3 px-3 py-2 rounded hover:bg-gray-50 cursor-pointer'
            ).on(
                'click',
                lambda cn=class_name, lib=lib, ct=comp_type: self._select_component(lib, cn, ct),
            ):
                with ui.column().classes('gap-0 flex-1 min-w-0'):
                    ui.label(ident.label or class_name).classes('text-sm font-medium')
                    if ident.description:
                        ui.label(ident.description).classes('text-xs text-gray-400 truncate')
                    ui.label(key).classes('text-xs text-gray-300 font-mono')

    # ─────────────────────────────────────────────────────────────────────────
    # Right panel — component documentation
    # ─────────────────────────────────────────────────────────────────────────

    def _render_right_placeholder(self):
        """Placeholder shown in the right panel when no component is selected."""
        self._right_container.clear()
        with self._right_container:
            with ui.column().classes(
                'w-full items-center justify-center gap-2 py-24'
            ):
                ui.icon('menu_book', size='40px').classes('text-gray-300')
                ui.label('Click a node or widget').classes(
                    'text-gray-400 text-sm text-center'
                )
                ui.label('to view its documentation').classes(
                    'text-gray-300 text-xs text-center'
                )

    def _render_component_info_header(
        self,
        lib: InstalledLibrary,
        class_name: str,
        comp_type: str,
        registry_key: str,
        cls,
    ):
        """Render per-class identity info + copy snippets at the top of the right panel."""
        import json as _json

        ident = getattr(cls, 'class_identity', None) if cls else None
        module_path = getattr(cls, '__module__', None) if cls else None
        actual_name = getattr(cls, '__name__', class_name) if cls else class_name

        def _copy_btn(value: str):
            v = value
            return (
                ui.button(
                    icon='content_copy',
                    on_click=lambda _v=v: ui.run_javascript(
                        f'navigator.clipboard.writeText({_json.dumps(_v)})'
                    ),
                )
                .props('flat round dense size=xs color=grey')
                .tooltip('Copy to clipboard')
            )

        def _info_row(label: str, display: str, full_value: str | None = None):
            v = full_value if full_value is not None else display
            with ui.row().classes('w-full items-center gap-1 py-0.5'):
                _copy_btn(v)
                ui.label(label).classes('text-xs text-gray-400 w-16 flex-shrink-0')
                ui.label(display).classes('text-xs font-mono min-w-0 truncate')

        def _code_row(code: str, label: str | None = None):
            with ui.column().classes('w-full gap-0.5 py-1'):
                if label:
                    ui.label(label).classes('text-xs text-gray-400')
                with ui.row().classes('w-full items-center gap-1 overflow-hidden'):
                    _copy_btn(code)
                    with ui.element('div').classes(
                        'min-w-0 bg-gray-50 rounded px-2 py-1 border overflow-hidden'
                    ):
                        ui.label(code).classes('text-xs font-mono')

        def _section(text: str):
            ui.label(text).classes(
                'text-xs font-bold text-gray-400 uppercase tracking-wider mt-3 mb-1'
            )

        # ── Title ─────────────────────────────────────────────────────────────
        label = (getattr(ident, 'label', None) or actual_name) if ident else actual_name
        description = getattr(ident, 'description', None) if ident else None

        with ui.column().classes('w-full gap-0.5 mb-2'):
            ui.label(label).classes('text-base font-bold')
            if description:
                ui.label(description).classes('text-xs text-gray-500')

        # ── Tags ──────────────────────────────────────────────────────────────
        tags = getattr(ident, 'tags', None) if ident else None
        if tags and isinstance(tags, (list, tuple)):
            with ui.row().classes('gap-1 flex-wrap mb-2'):
                for tag in tags:
                    ui.badge(str(tag)).props('outline color=grey')

        # ── Identifiers ───────────────────────────────────────────────────────
        _section('Identifiers')
        _info_row('Key', registry_key)
        _info_row('Class', actual_name)
        if module_path:
            short = (module_path[:48] + '…') if len(module_path) > 50 else module_path
            _info_row('Module', short, module_path)

        # ── Node-specific info ────────────────────────────────────────────────
        if comp_type == 'nodes' and ident:
            menu = getattr(ident, 'menu', None)
            if menu:
                _info_row('Menu', menu)

        # ── Usage snippets ────────────────────────────────────────────────────
        if comp_type == 'types':
            type_var = actual_name
            _section('Usage')
            if module_path:
                _code_row(f'from {module_path} import {type_var}', 'Import')
            _code_row(
                f"self.add({type_var}.as_inlet('id', label='Label'))", 'Inlet port'
            )
            _code_row(
                f"self.add({type_var}.as_outlet('id', label='Label'))", 'Outlet port'
            )
            _code_row(
                f"self.add({type_var}.as_config('id', label='Label', default=...))",
                'Config port',
            )

        elif comp_type == 'widgets':
            _section('Usage')
            if module_path:
                _code_row(f'from {module_path} import {actual_name}', 'Import')
            _code_row(
                f'widget={actual_name}.config(properties={{}})', 'Widget config'
            )

        elif comp_type == 'nodes' and module_path:
            _section('Import')
            _code_row(f'from {module_path} import {actual_name}')

    def _select_component(
        self, lib: InstalledLibrary, class_name: str, comp_type: str
    ):
        """Show per-component info and docs in the right panel."""
        self._right_container.clear()

        # Look up the class from the appropriate registry
        comp_singular = {
            'nodes': 'node', 'widgets': 'widget', 'types': 'type',
            'adapters': 'adapter', 'renderers': 'renderer',
        }.get(comp_type, comp_type)
        registry_key = f'{lib.library_id}:{comp_singular}:{class_name}'
        registry = {
            'nodes': self.node_registry,
            'widgets': self.widget_registry,
            'types': self.type_registry,
            'adapters': self.adapter_registry,
            'renderers': self.renderer_registry,
        }.get(comp_type)
        cls = registry.get(registry_key) if registry else None

        source = Path(lib.source_path) if lib.source_path else None
        doc_file = (
            source / 'docs' / comp_type / f'{class_name}.md'
            if source
            else None
        )

        # Resolve the source file via inspect (most reliable)
        src_file: Path | None = None
        if cls:
            try:
                import inspect
                src_file = Path(inspect.getfile(cls))
            except (TypeError, OSError):
                pass

        is_editable = lib.install_type == 'EDITABLE'

        with self._right_container:
            # height:100% + flex column so tab_panels can fill remaining space.
            with ui.column().classes('w-full p-4 gap-0').style('height: 100%;'):
                # ── Header bar ─────────────────────────────────────────────
                with ui.row().classes('w-full items-center justify-between mb-3'):
                    ui.label(comp_singular.upper()).classes(
                        'text-xs text-gray-400 font-bold tracking-wider'
                    )
                    ui.button(
                        icon='close',
                        on_click=lambda: self._render_right_placeholder(),
                    ).props('flat round size=xs').tooltip('Close')

                # ── Class info header ──────────────────────────────────────
                self._render_component_info_header(
                    lib, class_name, comp_type, registry_key, cls
                )

                # ── Tabs: Docs / Source ────────────────────────────────────
                ui.separator().classes('mt-3')
                with ui.tabs().classes('w-full').props('dense') as tabs:
                    t_docs = ui.tab('Docs', icon='description')
                    if src_file and src_file.exists():
                        t_source = ui.tab('Source', icon='code')
                    else:
                        t_source = None

                # flex:1 + min-height:0 makes this fill all remaining vertical
                # space in the column; each panel handles its own scrolling.
                with ui.tab_panels(tabs, value=t_docs).classes(
                    'w-full hw-right-tab-panels'
                ).style('flex: 1; min-height: 0; overflow: hidden;'):

                    # Docs: scroll internally so long markdown is reachable.
                    with ui.tab_panel(t_docs).style(
                        'height: 100%; overflow-y: auto; padding: 0;'
                    ):
                        if doc_file and doc_file.exists():
                            doc_text = doc_file.read_text()
                            lines = doc_text.split('\n')
                            if lines and lines[0].startswith('<!--'):
                                doc_text = '\n'.join(lines[2:])
                            ui.markdown(doc_text).classes('w-full text-sm')
                        else:
                            ui.label('No documentation file found.').classes(
                                'text-gray-400 text-sm'
                            )
                            ui.label('Run /docs to generate per-component docs.').classes(
                                'text-xs text-gray-400 italic mt-1'
                            )

                    if t_source:
                        # Source: flex column — codemirror grows, Save button
                        # stays pinned at bottom, no outer-panel scroll needed.
                        with ui.tab_panel(t_source).style(
                            'height: 100%; padding: 0;'
                            ' display: flex; flex-direction: column; overflow: hidden;'
                        ):
                            ui.label(src_file.name).classes(
                                'text-xs font-mono text-gray-400'
                            ).style('flex-shrink: 0; padding-bottom: 8px;')
                            editor = ui.codemirror(
                                src_file.read_text(),
                                language='Python',
                                theme='vscodeDark',
                            ).style('flex: 1; min-height: 0; width: 100%;')
                            if is_editable:
                                def _save(p=src_file):
                                    try:
                                        p.write_text(editor.value)
                                        ui.notify('Saved.', type='positive')
                                    except Exception as exc:
                                        ui.notify(f'Save failed: {exc}', type='negative')
                                ui.button('Save', icon='save', on_click=_save).props(
                                    'color=primary size=sm'
                                ).style('flex-shrink: 0; margin-top: 8px;')

    # ─────────────────────────────────────────────────────────────────────────
    # Marketplace overview fetch (async)
    # ─────────────────────────────────────────────────────────────────────────

    async def _fetch_marketplace_overview(
        self, pkg: MarketplaceEntry
    ) -> 'str | None':
        """
        Fetch OVERVIEW.md (or README fallback) for a marketplace-only package.

        Priority:
        1. ``docs_url`` field — explicit raw URL to OVERVIEW.md or to the
           directory that contains it (e.g. a GitHub raw content URL).
           If the URL ends with a filename it is fetched directly; otherwise
           OVERVIEW.md and QUICKREF.md are appended and tried in order.
        2. Heuristic GitHub lookup — derived from ``source_url`` or
           ``install_spec``, for both pypi and git sources.  The module name
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

        # ── 1. Explicit docs_url ──────────────────────────────────────────
        if pkg.docs_url:
            # Local filesystem path
            p = Path(pkg.docs_url)
            if p.is_dir():
                for candidate in (p / 'OVERVIEW.md', p / 'QUICKREF.md'):
                    if candidate.exists():
                        return candidate.read_text()
            elif p.is_file():
                return p.read_text()
            # Remote URL
            elif pkg.docs_url.startswith('http'):
                url = pkg.docs_url.rstrip('/')
                if url.endswith('.md'):
                    candidates = [url]
                else:
                    candidates = [f'{url}/OVERVIEW.md', f'{url}/QUICKREF.md']
                content = await asyncio.to_thread(_try_urls, candidates)
                if content:
                    return content

        # ── 2. Heuristic: derive raw GitHub URL ───────────────────────────
        module_name = pkg.name.replace('-', '_')

        subdir = ''
        if pkg.install_spec and '#subdirectory=' in pkg.install_spec:
            subdir = pkg.install_spec.split('#subdirectory=')[-1].strip('/')

        def _github_raw_base(url: str) -> 'str | None':
            url = url.rstrip('/').removesuffix('.git')
            if 'github.com' not in url:
                return None
            return url.replace('https://github.com/', 'https://raw.githubusercontent.com/')

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
            # repo/subdir-root fallbacks
            for branch in ('main', 'master'):
                prefix = f'{raw_base}/{branch}'
                if subdir:
                    candidates.append(f'{prefix}/{subdir}/OVERVIEW.md')
                candidates.append(f'{prefix}/OVERVIEW.md')

            content = await asyncio.to_thread(_try_urls, candidates)
            if content:
                return content

        # ── 3. PyPI long_description fallback ────────────────────────────
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

    # ─────────────────────────────────────────────────────────────────────────
    # Marketplace source editor + remote source loader
    # ─────────────────────────────────────────────────────────────────────────

    def _open_source_editor(self, source_file: str, source_origin: str = ''):
        """Open a dialog to edit the local marketplace TOML file."""
        if not source_file:
            ui.notify('No editable source file found.', type='warning')
            return
        p = Path(source_file)
        if not p.exists():
            ui.notify(f'File not found: {source_file}', type='negative')
            return

        with ui.dialog() as dialog, ui.card().classes('w-full').style('max-width: 780px;'):
            # Header
            with ui.row().classes('w-full items-start justify-between mb-1'):
                with ui.column().classes('gap-0 min-w-0 flex-1'):
                    ui.label(str(p)).classes('text-xs font-mono text-gray-600 break-all')
                    if source_origin:
                        with ui.row().classes('items-center gap-1 mt-0.5'):
                            ui.icon('arrow_forward', size='12px').classes('text-gray-400')
                            ui.label(source_origin).classes(
                                'text-xs text-gray-400 truncate'
                            )
                ui.button(icon='close', on_click=dialog.close).props(
                    'flat round dense size=sm'
                )

            editor = (
                ui.textarea(value=p.read_text())
                .classes('w-full')
                .props(
                    'outlined rows=24'
                    ' input-style="font-family: monospace; font-size: 12px; line-height: 1.5;"'
                )
            )

            with ui.row().classes('w-full justify-end gap-2 mt-2'):
                ui.button('Cancel', on_click=dialog.close).props('flat')

                def _save(p=p, dlg=dialog):
                    try:
                        p.write_text(editor.value)
                        ui.notify('Saved.', type='positive')
                        dlg.close()
                        # Re-read local sources immediately; clear + re-fetch remote ones
                        self._marketplace_cache = None
                        self._extra_marketplace_entries.clear()
                        self._render_left_list()
                        asyncio.ensure_future(self._load_remote_sources())
                    except Exception as exc:
                        ui.notify(f'Save failed: {exc}', type='negative')

                ui.button('Save', icon='save', on_click=_save).props('color=primary')

        dialog.open()

    async def _load_remote_sources(self):
        """Fetch HTTP marketplace sources and refresh the left list when done."""
        from .config import GLOBAL_CONFIG_DIR, get_marketplace_sources
        global_file = str(GLOBAL_CONFIG_DIR / 'marketplace.toml')
        any_new = False
        for src in get_marketplace_sources():
            name = src.get('name', 'global')
            url = src.get('url', '')
            if not url or not url.startswith('http'):
                continue
            fetched = await asyncio.to_thread(self.manager._fetch_remote_marketplace, url)
            for e in fetched:
                e.source_label = name
                e.source_file = global_file
                e.source_origin = url
            if fetched:
                self._extra_marketplace_entries.extend(fetched)
                any_new = True
        if any_new:
            self._render_left_list()

    # ─────────────────────────────────────────────────────────────────────────
    # Marketplace helpers
    # ─────────────────────────────────────────────────────────────────────────

    def _get_marketplace_packages(self) -> list[MarketplaceEntry]:
        if self._marketplace_cache is None:
            self._marketplace_cache = self._load_local_marketplace_packages()
        # Remote entries are appended separately (populated async by _load_remote_sources)
        return self._marketplace_cache + self._extra_marketplace_entries

    def _load_local_marketplace_packages(self) -> list[MarketplaceEntry]:
        """Read and parse all local marketplace files (project + local-path sources)."""
        from .config import get_marketplace_sources
        entries: list[MarketplaceEntry] = []

        # 1. Project-level .haywire/marketplace.toml
        if self.marketplace_path:
            for e in self.manager.load_marketplace(self.marketplace_path):
                e.source_label = 'project'
                e.source_file = self.marketplace_path
                entries.append(e)

        # 2. Local-path sources listed in ~/.haywire/marketplace.toml [[sources]]
        for src in get_marketplace_sources():
            name = src.get('name', 'global')
            url = src.get('url', '')
            if not url:
                continue
            p = Path(url)
            if p.exists():
                for e in self.manager.load_marketplace(str(p)):
                    e.source_label = name
                    e.source_file = str(p)
                    entries.append(e)

        return entries

    @staticmethod
    def _normalize_pkg_id(name: str) -> str:
        """Normalize a package name to a comparable library ID (strips haybale- prefix)."""
        return name.removeprefix('haybale-').lower()

    def _is_pkg_installed(
        self,
        pkg: MarketplaceEntry,
        libraries: list[InstalledLibrary] | None = None,
    ) -> bool:
        if libraries is None:
            libraries = self.manager.list_installed()
        installed_ids = {lib.library_id.lower() for lib in libraries}
        installed_dist = {
            lib.distribution_name.lower()
            for lib in libraries
            if lib.distribution_name
        }
        pkg_id = self._normalize_pkg_id(pkg.name)
        return (
            pkg_id in installed_ids
            or pkg.name.lower() in installed_ids
            or pkg.name.lower() in installed_dist
        )

    def _is_project_library(self, lib: InstalledLibrary) -> bool:
        """Return True if lib is the local project library (lives under workspace/libs/)."""
        if not self.marketplace_path or not lib.source_path:
            return False
        workspace_root = Path(self.marketplace_path).parent.parent
        return Path(lib.source_path).is_relative_to(workspace_root / 'libs')

    def _find_marketplace_pkg(self, name: str) -> MarketplaceEntry | None:
        return next(
            (p for p in self._get_marketplace_packages() if p.name == name),
            None,
        )

    def _find_marketplace_pkg_for_lib(
        self, lib: InstalledLibrary
    ) -> MarketplaceEntry | None:
        """Find the marketplace entry matching an installed library (if any)."""
        for pkg in self._get_marketplace_packages():
            pkg_id = self._normalize_pkg_id(pkg.name)
            if (
                pkg_id == lib.library_id.lower()
                or pkg.name.lower() == lib.library_id.lower()
                or (
                    lib.distribution_name
                    and pkg.name.lower() == lib.distribution_name.lower()
                )
            ):
                return pkg
        return None

    def _find_installed_for_pkg(
        self,
        pkg: MarketplaceEntry,
        libraries: list[InstalledLibrary] | None = None,
    ) -> InstalledLibrary | None:
        """Find the installed library matching a marketplace package (if any)."""
        if libraries is None:
            libraries = self.manager.list_installed()
        pkg_id = self._normalize_pkg_id(pkg.name)
        for lib in libraries:
            if (
                lib.library_id.lower() == pkg_id
                or lib.library_id.lower() == pkg.name.lower()
                or (
                    lib.distribution_name
                    and lib.distribution_name.lower() == pkg.name.lower()
                )
            ):
                return lib
        return None

    # ─────────────────────────────────────────────────────────────────────────
    # Status and refresh
    # ─────────────────────────────────────────────────────────────────────────

    def _set_status(self, message: str, msg_type: str = 'info'):
        if self._status_label:
            self._status_label.text = message
        color_map = {
            'info': 'info',
            'success': 'positive',
            'error': 'negative',
            'warning': 'warning',
        }
        ui.notify(message, type=color_map.get(msg_type, 'info'))

    def _refresh_all(self):
        self._marketplace_cache = None
        if self._selected_id:
            self._select(self._selected_id, self._selected_is_marketplace)
        else:
            self._render_left_list()
        self._set_status('Refreshed')

    # ─────────────────────────────────────────────────────────────────────────
    # Enable / Disable
    # ─────────────────────────────────────────────────────────────────────────

    def _enable_library(self, library_id: str):
        self.manager.enable_library(library_id)
        self._set_status(f'Enabled: {library_id}', 'success')
        self._refresh_all()

    def _disable_library(self, library_id: str):
        self.manager.disable_library(library_id)
        self._set_status(f'Disabled: {library_id}', 'warning')
        self._refresh_all()

    # ─────────────────────────────────────────────────────────────────────────
    # Uninstall
    # ─────────────────────────────────────────────────────────────────────────

    def _confirm_uninstall(self, library_id: str, label: str):
        """Show confirmation dialog, then uninstall."""
        with ui.dialog() as dialog, ui.card():
            ui.label(f'Uninstall {label}?').classes('text-lg font-bold')
            ui.label(
                'This will disable the library and remove it from the venv. '
                'Any graph nodes using this library will show as errors.'
            ).classes('text-gray-600 mb-4')

            async def confirm_and_uninstall():
                dialog.close()
                await self._do_uninstall(library_id, label)

            with ui.row().classes('w-full justify-end gap-2'):
                ui.button('Cancel', on_click=dialog.close)
                ui.button(
                    'Uninstall', on_click=confirm_and_uninstall
                ).props('color=negative')

        dialog.open()

    @staticmethod
    def _create_log_in_card(container, title: str) -> ui.log:
        """Append an expandable terminal log inside a container."""
        with container:
            with ui.expansion(title, icon='terminal', value=True).classes(
                'w-full min-w-0'
            ):
                log = ui.log(max_lines=50).classes('w-full h-32')
        return log

    async def _do_uninstall(self, library_id: str, label: str):
        """Perform uninstall with streaming log output."""
        self._set_status(f'Uninstalling {label}…', 'info')
        log = self._create_log_in_card(
            self._center_fixed, f'Uninstalling {label}…'
        )

        success, message = await self.manager.uninstall_streaming(
            library_id, log.push
        )

        if success:
            log.push(f'--- {label} uninstalled successfully ---')
            self._set_status(f'Uninstalled: {label}', 'success')
        else:
            log.push(f'--- ERROR: {message} ---')
            self._set_status(message, 'error')

        self._selected_id = None
        self._render_right_placeholder()
        self._render_center_placeholder()
        self._render_left_list()

    # ─────────────────────────────────────────────────────────────────────────
    # Edit (project library identity + optional rename)
    # ─────────────────────────────────────────────────────────────────────────

    def _build_edit_dialog(self, lib: InstalledLibrary) -> 'ui.dialog':
        """Build the Edit dialog — all identity fields are immediately editable.

        The package name field is locked behind a padlock icon.  Clicking the
        padlock shows a warning dialog; if the user confirms, the name field
        becomes editable and saving triggers a full rename.  When only identity
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
                    await self._do_rename(lib, new_name, identity)
                else:
                    await self._do_update_identity(lib, identity)

            with ui.row().classes('w-full justify-end gap-2 mt-2'):
                ui.button('Cancel', on_click=edit_dialog.close).props('flat size=sm')
                ui.button('Save Changes', on_click=_save).props('color=primary size=sm')

        # ── Warning dialog (sibling to edit_dialog, opened by lock click) ──────
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

    async def _do_update_identity(self, lib: InstalledLibrary, identity: dict[str, str]):
        """Save identity fields, then rescan so the in-memory identity is refreshed."""
        if not self.marketplace_path:
            self._set_status('No project workspace set.', 'error')
            return
        workspace_root = str(Path(self.marketplace_path).parent.parent)

        # Write __init__.py + marketplace.toml; also disables lib + ejects module
        success, message = await asyncio.to_thread(
            self.manager.update_library_identity,
            lib.library_id,
            workspace_root,
            identity,
        )
        if not success:
            self._set_status(message, 'error')
            return

        # Rescan so the updated @library decorator values are loaded into the registry
        self.manager._invalidate_caches()
        await asyncio.to_thread(self.manager.registry.scan_for_libraries)
        self.manager.registry.enable_all_libraries()

        self._marketplace_cache = None
        self._set_status(f'Saved: {identity.get("label", lib.label)}', 'success')
        if self._selected_id:
            self._select(self._selected_id, self._selected_is_marketplace)
        else:
            self._render_left_list()

    async def _do_rename(
        self,
        lib: InstalledLibrary,
        new_name: str,
        new_identity: dict[str, str] | None = None,
    ):
        """Perform rename with streaming log output."""
        old_library_id = lib.library_id  # capture before rename
        self._set_status(f'Renaming {lib.label}…', 'info')
        log = self._create_log_in_card(
            self._center_fixed, f'Renaming to haybale-{new_name}…'
        )
        workspace_root = str(Path(self.marketplace_path).parent.parent)

        success, message = await self.manager.rename_project_library_streaming(
            library_id=lib.library_id,
            new_name=new_name,
            workspace_root=workspace_root,
            on_output=log.push,
            new_identity=new_identity,
        )

        if success:
            log.push(f'--- Renamed to haybale-{new_name} ---')
            self._set_status(f'Renamed to haybale-{new_name}', 'success')
        else:
            log.push(f'--- ERROR: {message} ---')
            self._set_status(message, 'error')

        # Build the patch dialog NOW (while the slot context is still clean)
        # so _render_* calls below don't interfere with dialog creation.
        patch_dialog = (
            self._build_graph_patch_dialog(old_library_id, new_name, workspace_root)
            if success
            else None
        )

        self._selected_id = None
        self._marketplace_cache = None
        self._render_right_placeholder()
        self._render_center_placeholder()
        self._render_left_list()

        if patch_dialog is not None:
            patch_dialog.open()

    # ─────────────────────────────────────────────────────────────────────────
    # Graph file patching (post-rename)
    # ─────────────────────────────────────────────────────────────────────────

    def _build_graph_patch_dialog(
        self, old_library_id: str, new_library_id: str, workspace_root: str
    ) -> 'ui.dialog | None':
        """Build (but don't open) a dialog offering to patch graph files.

        Returns None if there is nothing to patch.
        """
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
            # File list (max 6 shown, then ellipsis)
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
        self, install_spec: str, name: str, button: ui.button | None
    ):
        """Install a package with streaming log output."""
        if button:
            button.disable()
            button.props('loading')
        self._set_status(f'Installing {name}…', 'info')
        log = self._create_log_in_card(
            self._center_fixed, f'Installing {name}…'
        )

        success, message = await self.manager.install_streaming(
            install_spec, log.push
        )

        if success:
            log.push(f'--- {name} installed successfully ---')
            self._set_status(f'Installed: {name}', 'success')
        else:
            log.push(f'--- ERROR: {message} ---')
            self._set_status(message, 'error')

        self._refresh_all()

    def _open_version_picker(self, pkg: MarketplaceEntry):
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
            status = ui.label('Fetching versions…').classes(
                'text-xs text-gray-400'
            )

            async def load_versions():
                versions = await self.manager.fetch_versions(pkg)
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
                spec = self.manager.build_versioned_spec(pkg, selected)
                await self._install_package(spec, pkg.name, None)

            with ui.row().classes('w-full justify-end gap-2 mt-4'):
                ui.button('Cancel', on_click=dialog.close).props('flat')
                ui.button(
                    'Install', on_click=install_selected
                ).props('color=primary')

        dialog.open()
        asyncio.ensure_future(load_versions())
