# packages/haywire-app/src/haywire_app/editors/file_browser.py
"""
FileBrowserEditor — project file tree for the left area.

Shows the workspace project folder as an expandable file tree.
Clicking a file opens it in the appropriate middle-area tab:
  - .haywire files  → load into GraphEditor (graph_editor tab)
  - all other files → display in FileViewerEditor (file_viewer tab)
"""

from pathlib import Path
from typing import TYPE_CHECKING, Optional

from haywire_app.app import HaywireApp
from nicegui import ui

from haywire.ui.editor.base import BaseEditor
from haywire.ui.editor.decorator import editor
from haywire.ui.context_events import ContextChangeType, ContextChangedEvent

if TYPE_CHECKING:
    from haywire.ui.context import SessionContext
    from haywire.ui.context_events import ContextChangedEvent as _CE


@editor(
    registry_id='file_browser',
    label='Files',
    icon='folder',
    default_area='left',
    description='Project file tree. Click a file to open it in the middle area.',
)
class FileBrowserEditor(BaseEditor):
    """
    Displays the project workspace as an expandable file tree.

    Selecting a file sets context.active_file and routes to the correct editor:
    .haywire → loads graph into graph_editor tab.
    Everything else → FILE_SELECTED event sent to file_viewer tab.
    """

    _EXCLUDE_DIRS: frozenset = frozenset({
        '__pycache__', '.venv', 'venv', 'node_modules', 'dist', 'build', '.git',
    })
    _GRAPH_EXTS: frozenset = frozenset({'.haywire'})
    _ICON_MAP: dict = {
        '.haywire': 'account_tree',
        '.py': 'code',
        '.json': 'data_object',
        '.toml': 'settings',
        '.md': 'description',
        '.yaml': 'tune',
        '.yml': 'tune',
        '.txt': 'text_snippet',
        '.sh': 'terminal',
    }

    def __init__(self):
        self._root_path: Optional[Path] = None
        self._tree_container = None

    def render(self, container, context: 'SessionContext') -> None:
        app = context.metadata.get('project_state')
        if app and hasattr(app, 'workspace_root'):
            self._root_path = Path(app.workspace_root)

        with container:
            with ui.column().classes('w-full h-full gap-0'):
                # Header
                with ui.row().classes(
                    'w-full items-center px-2 py-1.5 border-b flex-shrink-0 gap-1'
                ):
                    ui.icon('folder_open', size='16px').classes('text-gray-400')
                    name = self._root_path.name if self._root_path else 'No project'
                    ui.label(name).classes('text-sm font-medium text-gray-200 truncate flex-1')
                    ui.button(
                        icon='refresh',
                        on_click=lambda: self._refresh(context),
                    ).props('flat round dense size=xs color=grey').tooltip('Refresh tree')

                # Scrollable tree area
                with ui.scroll_area().classes('flex-1 w-full'):
                    self._tree_container = ui.column().classes('w-full p-1 gap-0')
                    self._render_tree(context)

    def _render_tree(self, context: 'SessionContext') -> None:
        if self._tree_container is None:
            return
        self._tree_container.clear()

        if self._root_path is None or not self._root_path.exists():
            with self._tree_container:
                ui.label('No project loaded').classes('text-xs text-gray-500 p-2')
            return

        nodes = self._build_tree_nodes(self._root_path)
        if not nodes:
            with self._tree_container:
                ui.label('Project folder is empty').classes('text-xs text-gray-500 p-2')
            return

        with self._tree_container:
            tree = ui.tree(
                nodes,
                label_key='label',
                node_key='id',
                on_select=lambda e: self._on_select(e.value, context),
            ).classes('w-full text-sm')
            tree.expand()

    def _build_tree_nodes(self, path: Path, depth: int = 0) -> list:
        """Recursively build ui.tree node dicts from the filesystem."""
        if depth > 3:
            return []
        items = []
        try:
            entries = sorted(
                path.iterdir(),
                key=lambda p: (not p.is_dir(), p.name.lower()),
            )
            for entry in entries:
                # Skip hidden except the .haywire config dir
                if entry.name.startswith('.') and entry.name != '.haywire':
                    continue
                if entry.is_dir() and entry.name in self._EXCLUDE_DIRS:
                    continue
                node: dict = {'id': str(entry), 'label': entry.name}
                if entry.is_dir():
                    node['children'] = self._build_tree_nodes(entry, depth + 1)
                items.append(node)
        except PermissionError:
            pass
        return items

    def _on_select(self, node_id: Optional[str], context: 'SessionContext') -> None:
        if not node_id:
            return
        path = Path(node_id)
        if not path.is_file():
            return  # directory selected — let the tree handle expand/collapse

        context.active_file = path

        if path.suffix.lower() in self._GRAPH_EXTS:
            self._open_graph_file(path, context)
        else:
            self._open_in_file_viewer(path, context)

    def _open_graph_file(self, path: Path, context: 'SessionContext') -> None:
        """Load a .haywire graph file and switch to the graph editor tab."""
        app: 'HaywireApp' = context.metadata.get('project_state')
        session = context.metadata.get('haywire_session')

        if app is not None and hasattr(app, 'open_graph_file') and session is not None:
            # Detach from whichever graph this session is currently viewing
            if context.active_graph_path is not None:
                prev_entry = app.graph_manager.get_by_path(context.active_graph_path)
            else:
                prev_entry = app.graph_manager.get_untitled()
            if prev_entry is not None:
                app.graph_manager.session_detach(prev_entry, session.session_id)

            # Open (or reuse) the graph entry and attach this session
            entry = app.open_graph_file(path, session.session_id)

            # Update context
            context.active_graph = entry.graph
            context.active_graph_path = path

            # Broadcast ACTIVE_GRAPH_CHANGED to all editors in this session
            session.notify_context_changed(
                ContextChangedEvent(
                    change_type=ContextChangeType.ACTIVE_GRAPH_CHANGED,
                    source_editor='file_browser',
                    detail=entry,
                )
            )
        elif app is not None and hasattr(app, '_do_load_graph'):
            # Fallback for backward compat (loads into shared untitled graph)
            app._do_load_graph(str(path))

        self._switch_middle_tab('__system__:editor:graph_editor', context)

    def _open_in_file_viewer(self, path: Path, context: 'SessionContext') -> None:
        """Switch to the file_viewer tab and broadcast FILE_SELECTED."""
        self._switch_middle_tab('__system__:editor:file_viewer', context)
        session = context.metadata.get('haywire_session')
        if session is not None:
            session.notify_context_changed(
                ContextChangedEvent(
                    change_type=ContextChangeType.FILE_SELECTED,
                    source_editor='file_browser',
                    detail=path,
                )
            )

    def _switch_middle_tab(self, editor_id: str, context: 'SessionContext') -> None:
        tabs = context.metadata.get('middle_tabs')
        if tabs is not None:
            try:
                tabs.set_value(editor_id)
            except Exception:
                pass

    def _refresh(self, context: 'SessionContext') -> None:
        self._render_tree(context)

    def on_context_changed(self, event: '_CE', context: 'SessionContext') -> None:
        pass  # FileBrowserEditor does not react to context changes
