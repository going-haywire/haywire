# packages/haywire-app/src/haywire_app/editors/graph_manager_editor.py
"""
GraphManagerEditor — open-graphs list for the left area.

Shows every graph currently loaded by GraphManager (open files + any new
untitled/unnamed graphs). The user can:
  - Click a row to make that graph active in the GraphEditor
  - Click the "+" button in the header to create a new unnamed graph

The list rebuilds on ACTIVE_GRAPH_CHANGED (to refresh the active highlight)
and DATA_MUTATED (to reflect unsaved/modified state).
"""

from pathlib import Path
from typing import TYPE_CHECKING

from nicegui import ui

from haywire.ui.editor.base import BaseEditor
from haywire.ui.editor.decorator import editor
from haywire.ui.context_events import ContextChangeType, ContextChangedEvent

if TYPE_CHECKING:
    from haywire.ui.context import SessionContext
    from haywire.ui.context_events import ContextChangedEvent as _CE
    from haywire_app.graph_manager import GraphEntry


_GRAPH_EDITOR_KEY = '__system__:editor:graph_editor'


def _workspace_rel_path(path: Path, workspace_root: 'Path | None') -> str:
    """Return path relative to workspace_root when possible, else absolute path."""
    if workspace_root is not None:
        try:
            return str(path.relative_to(workspace_root))
        except ValueError:
            pass
    return str(path)


@editor(
    registry_id='graph_manager',
    label='Graphs',
    icon='layers',
    default_area='left',
    description='All open graphs. Click to switch; "+" to create a new graph.',
)
class GraphManagerEditor(BaseEditor):
    """
    Left-area editor that lists all graphs tracked by GraphManager.

    One entry per open file or new unnamed graph.  Clicking an entry:
      1. Detaches the session from the current graph.
      2. Attaches the session to the selected graph.
      3. Updates context.active_graph / active_graph_path.
      4. Fires ACTIVE_GRAPH_CHANGED so GraphEditor swaps its canvas.
      5. Switches the middle-area tab to the GraphEditor.

    The "+" header button calls app.create_new_graph() and immediately
    activates the freshly created entry.
    """

    def __init__(self):
        self._list_container = None

    # ------------------------------------------------------------------
    # render
    # ------------------------------------------------------------------

    def render(self, container, context: 'SessionContext') -> None:
        with container:
            with ui.column().classes('w-full h-full gap-0'):
                self._render_header(context)
                with ui.scroll_area().classes('flex-1 w-full'):
                    self._list_container = ui.column().classes('w-full gap-0 p-1')
                    self._render_list(context)

    # ------------------------------------------------------------------
    # header
    # ------------------------------------------------------------------

    def _render_header(self, context: 'SessionContext') -> None:
        with ui.row().classes(
            'w-full items-center px-2 py-1.5 border-b flex-shrink-0 gap-1'
        ):
            ui.icon('layers', size='16px').classes('hw-text-dim')
            ui.label('GRAPHS').classes(
                'text-xs font-bold tracking-wider hw-text-dim flex-1'
            )
            ui.button(
                icon='add',
                on_click=lambda: self._on_new(context),
            ).props('flat round dense size=xs color=grey').tooltip('New graph')

    # ------------------------------------------------------------------
    # list
    # ------------------------------------------------------------------

    def _render_list(self, context: 'SessionContext') -> None:
        if self._list_container is None:
            return
        self._list_container.clear()

        app = context.app
        if app is None or not hasattr(app, 'graph_manager'):
            with self._list_container:
                ui.label('Graph manager not available').classes(
                    'text-xs hw-text-dim p-2 italic'
                )
            return

        entries = app.graph_manager.all_entries()
        if not entries:
            with self._list_container:
                ui.label('No graphs open').classes('text-xs hw-text-dim p-2 italic')
            return

        with self._list_container:
            for entry in entries.values():
                self._render_entry(entry, context)

    def _render_entry(self, entry: 'GraphEntry', context: 'SessionContext') -> None:
        is_active = entry.graph is context.active_graph
        # A graph with no path is definitionally unsaved (never written to disk).
        is_unsaved = entry.unsaved or entry.path is None

        row_classes = (
            'w-full px-2 py-1.5 cursor-pointer items-center gap-2 rounded '
            + ('bg-blue-900/40 ' if is_active else 'hover:bg-white/10 ')
        )

        with ui.row().classes(row_classes).on(
            'click', lambda e, en=entry: self._on_select(en, context)
        ):
            # Unsaved indicator dot — always shown for path-less graphs
            dot_color = 'bg-amber-400' if is_unsaved else 'bg-transparent'
            ui.element('div').classes(
                f'w-2 h-2 rounded-full flex-shrink-0 {dot_color}'
            ).style('border: 1px solid var(--hw-border);')

            # Name + subtitle
            with ui.column().classes('flex-1 gap-0 min-w-0'):
                name_classes = (
                    'text-sm truncate font-medium '
                    + ('hw-text-body' if is_active else 'hw-text-muted')
                )
                ui.label(entry.display_name).classes(name_classes)

                if entry.path is not None:
                    app = context.app
                    ws_root = (
                        Path(app.workspace_root)
                        if app and hasattr(app, 'workspace_root')
                        else None
                    )
                    ui.label(_workspace_rel_path(entry.path, ws_root)).classes(
                        'text-xs hw-text-dim truncate'
                    )
                else:
                    # No file path — always show the unsaved hint
                    ui.label('not saved').classes('text-xs text-amber-400/70')

            # Active indicator chevron
            if is_active:
                ui.icon('chevron_right', size='16px').classes(
                    'text-blue-400 flex-shrink-0'
                )

    # ------------------------------------------------------------------
    # actions
    # ------------------------------------------------------------------

    def _on_new(self, context: 'SessionContext') -> None:
        """Create a new unnamed graph and activate it."""
        app = context.app
        session = context.session
        if app is None or not hasattr(app, 'create_new_graph') or session is None:
            ui.notify('Graph manager not available', type='warning')
            return

        # Detach from current graph
        self._detach_current(app, context, session)

        # Create the new graph and attach this session
        entry = app.create_new_graph(session.session_id)

        # Update context
        context.active_graph = entry.graph
        context.active_graph_path = entry.path

        self._activate_entry(entry, context, session)

    def _on_select(self, entry: 'GraphEntry', context: 'SessionContext') -> None:
        """Activate an existing graph entry."""
        if entry.graph is context.active_graph:
            # Already active — just make sure GraphEditor is visible
            self._switch_to_graph_editor(context)
            return

        app = context.app
        session = context.session
        if app is None or session is None:
            return

        # Detach from current graph
        self._detach_current(app, context, session)

        # Attach to selected entry
        app.graph_manager.session_attach(entry, session.session_id)

        # Update context
        context.active_graph = entry.graph
        context.active_graph_path = entry.path

        self._activate_entry(entry, context, session)

    # ------------------------------------------------------------------
    # helpers
    # ------------------------------------------------------------------

    def _detach_current(self, app, context: 'SessionContext', session) -> None:
        """Detach the session from whatever graph it is currently viewing."""
        if context.active_graph_path is not None:
            current_entry = app.graph_manager.get_by_path(context.active_graph_path)
        elif context.active_graph is not None:
            # path=None covers both '__untitled__' and '__new_N__' — use identity
            current_entry = app.graph_manager.get_by_graph(context.active_graph)
        else:
            current_entry = None
        if current_entry is not None:
            app.graph_manager.session_detach(current_entry, session.session_id)

    def _activate_entry(
        self, entry: 'GraphEntry', context: 'SessionContext', session
    ) -> None:
        """Fire ACTIVE_GRAPH_CHANGED and switch to the graph editor tab."""
        session.notify_context_changed(
            ContextChangedEvent(
                change_type=ContextChangeType.ACTIVE_GRAPH_CHANGED,
                source_editor='graph_manager',
                detail=entry,
            )
        )
        self._switch_to_graph_editor(context)

    def _switch_to_graph_editor(self, context: 'SessionContext') -> None:
        tabs = context.metadata.get('middle_tabs')
        if tabs is not None:
            try:
                tabs.set_value(_GRAPH_EDITOR_KEY)
            except Exception:
                pass

    # ------------------------------------------------------------------
    # context changes
    # ------------------------------------------------------------------

    def on_context_changed(self, event: '_CE', context: 'SessionContext') -> None:
        if event.change_type in (
            ContextChangeType.ACTIVE_GRAPH_CHANGED,
            ContextChangeType.DATA_MUTATED,
        ):
            self._render_list(context)

    # ------------------------------------------------------------------
    # cleanup
    # ------------------------------------------------------------------

    def cleanup(self) -> None:
        self._list_container = None
