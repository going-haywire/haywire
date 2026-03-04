# packages/haywire-app/src/haywire_app/editors/library_browser.py
"""
LibraryBrowser — searchable library list editor for the left area.

Displays installed and marketplace libraries in a compact scrollable list.
Selecting a library updates context.active_library and fires ACTIVE_LIBRARY_CHANGED.
"""

import logging
from pathlib import Path
from typing import TYPE_CHECKING

from nicegui import ui

from haywire.ui.editor.decorator import editor
from haywire.ui.editor.base import BaseEditor
from haywire.ui.context_events import ContextChangeType, ContextChangedEvent

if TYPE_CHECKING:
    from haywire.ui.context import SessionContext
    from haywire.ui.context_events import ContextChangedEvent as _CE


@editor(
    registry_id='library_browser',
    label='Libraries',
    icon='widgets',
    default_area='left',
    description='Searchable list of installed and available libraries.',
)
class LibraryBrowser(BaseEditor):
    """
    Shows a searchable list of installed (enabled/disabled) libraries.

    On selection, updates context.active_library and notifies subscribers
    via ACTIVE_LIBRARY_CHANGED. The library_manager is retrieved from
    context.metadata['project_state'].library_manager.
    """

    def __init__(self):
        self._container = None
        self._list_container = None
        self._search_query: str = ''
        self._filter_enabled: bool = True
        self._filter_disabled: bool = True
        self._filter_available: bool = True

    def render(self, container, context: 'SessionContext') -> None:
        self._container = container
        with container:
            self._build_ui(context)

    def _build_ui(self, context: 'SessionContext') -> None:
        with ui.column().classes('w-full h-full gap-0'):
            # Search bar
            with ui.column().classes('p-2 gap-1 border-b flex-shrink-0'):
                search = (
                    ui.input(placeholder='Search libraries…')
                    .classes('w-full')
                    .props('dense outlined clearable')
                )
                search.on(
                    'update:model-value',
                    lambda e: self._on_search(e.args, context),
                )
                search.on('clear', lambda e: self._on_search('', context))

                # Filter toggles
                with ui.row().classes('items-center gap-0.5'):
                    ui.label('Show:').classes('text-xs hw-text-dim mr-1')
                    self._make_toggle('enabled', 'green', 'check_circle', 'Enabled', context)
                    self._make_toggle('disabled', 'orange', 'pause_circle', 'Disabled', context)
                    self._make_toggle(
                        'available', 'blue', 'cloud_download', 'Available in marketplace', context
                    )

            # Scrollable list
            with ui.scroll_area().classes('flex-1 w-full'):
                self._list_container = ui.column().classes('w-full gap-0 p-0')
                self._render_list(context)

    def _make_toggle(self, attr: str, color: str, icon: str, tooltip: str, context: 'SessionContext'):
        active = getattr(self, f'_filter_{attr}')
        btn = (
            ui.button(icon=icon)
            .props(f'flat round dense size=sm color={"" if not active else color}')
            .tooltip(tooltip)
        )
        if active:
            btn.props(f'color={color}')
        btn.on('click', lambda a=attr, b=btn, c=color, ctx=context: self._toggle(a, b, c, ctx))

    def _toggle(self, attr: str, btn, color: str, context: 'SessionContext'):
        current = getattr(self, f'_filter_{attr}')
        setattr(self, f'_filter_{attr}', not current)
        new_color = color if not current else 'grey'
        btn.props(f'color={new_color}')
        self._render_list(context)

    def _on_search(self, args, context: 'SessionContext'):
        if isinstance(args, (list, tuple)):
            value = args[0] if args else ''
        else:
            value = args
        self._search_query = value or ''
        self._render_list(context)

    def _render_list(self, context: 'SessionContext') -> None:
        if self._list_container is None:
            return
        self._list_container.clear()

        app = context.metadata.get('project_state')
        if app is None or not hasattr(app, 'library_manager'):
            with self._list_container:
                ui.label('Library manager not available').classes('text-xs hw-text-dim p-2')
            return

        try:
            libraries = app.library_manager.list_installed()
        except Exception as e:
            logging.warning(f'LibraryBrowser: failed to list libraries: {e}')
            with self._list_container:
                ui.label('Error loading libraries').classes('text-xs text-red-400 p-2')
            return

        q = self._search_query.lower().strip()

        def matches(lib) -> bool:
            if not q:
                return True
            label = getattr(lib, 'label', '') or getattr(lib, 'name', '')
            desc = getattr(lib, 'description', '') or ''
            tags = getattr(lib, 'tags', []) or []
            return (
                q in label.lower()
                or bool(desc and q in desc.lower())
                or any(q in t.lower() for t in tags)
            )

        enabled = (
            [lib for lib in libraries if getattr(lib, 'enabled', True) and matches(lib)]
            if self._filter_enabled else []
        )
        disabled = (
            [lib for lib in libraries if not getattr(lib, 'enabled', True) and matches(lib)]
            if self._filter_disabled else []
        )
        enabled.sort(key=lambda x: getattr(x, 'label', ''))
        disabled.sort(key=lambda x: getattr(x, 'label', ''))

        # Marketplace entries not yet installed
        available = []
        if self._filter_available:
            workspace_root = getattr(app, 'workspace_root', None)
            marketplace_path = (
                str(Path(workspace_root) / '.haywire' / 'marketplace.toml')
                if workspace_root else None
            )
            if marketplace_path:
                try:
                    from haywire_app.library_manager import LibraryManager
                    installed_names = {
                        lib.distribution_name for lib in libraries if lib.distribution_name
                    }
                    entries = LibraryManager.load_marketplace(marketplace_path)
                    available = [e for e in entries if e.name not in installed_names and matches(e)]
                    available.sort(key=lambda x: x.label or x.name)
                except Exception as e:
                    logging.warning(f'LibraryBrowser: failed to load marketplace: {e}')

        with self._list_container:
            if enabled:
                ui.label('ENABLED').classes(
                    'text-xs font-bold hw-text-dim px-2 pt-2 pb-1 tracking-wider'
                )
                for lib in enabled:
                    self._library_item(lib, 'green', context)

            if disabled:
                ui.label('DISABLED').classes(
                    'text-xs font-bold hw-text-dim px-2 pt-2 pb-1 tracking-wider'
                )
                for lib in disabled:
                    self._library_item(lib, 'orange', context)

            if available:
                ui.label('AVAILABLE').classes(
                    'text-xs font-bold hw-text-dim px-2 pt-2 pb-1 tracking-wider'
                )
                for entry in available:
                    self._library_item(entry, 'gray', context)

            if not enabled and not disabled and not available:
                with ui.column().classes('w-full items-center py-8 gap-2'):
                    ui.icon('search_off', size='28px').classes('hw-text-dim')
                    ui.label('No libraries found').classes('text-xs hw-text-muted italic')

    def _library_item(self, lib, dot_color: str, context: 'SessionContext'):
        label = getattr(lib, 'label', None) or getattr(lib, 'name', '?')
        version = getattr(lib, 'version', '')

        with ui.row().classes(
            'w-full px-2 py-1.5 cursor-pointer hover:bg-white/10 items-center gap-2 rounded'
        ).on('click', lambda entry=lib, ctx=context: self._select_library(entry, ctx)):
            ui.element('div').classes(f'w-2 h-2 rounded-full bg-{dot_color}-500 flex-shrink-0')
            with ui.column().classes('flex-1 gap-0 min-w-0'):
                ui.label(label).classes('text-sm font-medium truncate')
                if version:
                    ui.label(f'v{version}').classes('text-xs hw-text-dim')

    def _select_library(self, lib, context: 'SessionContext'):
        context.active_library = lib
        context.active_component = None

        # Switch middle tab to library_detail if it exists
        middle_tabs = context.metadata.get('middle_tabs')
        if middle_tabs is not None:
            try:
                middle_tabs.set_value('__system__:editor:library_detail')
            except Exception:
                pass

        session = context.metadata.get('haywire_session')
        if session is not None:
            session.notify_context_changed(
                ContextChangedEvent(
                    change_type=ContextChangeType.ACTIVE_LIBRARY_CHANGED,
                    source_editor='library_browser',
                )
            )

    def on_context_changed(self, event: '_CE', context: 'SessionContext') -> None:
        if event.change_type == ContextChangeType.ACTIVE_LIBRARY_CHANGED:
            self._render_list(context)
