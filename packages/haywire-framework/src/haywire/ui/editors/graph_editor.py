# packages/haywire-framework/src/haywire/ui/editors/graph_editor.py
"""
GraphEditor — wraps GraphCanvasManager as a BaseEditor.

Supports multiple open graphs via the GraphManager in haywire-app.
When an ACTIVE_GRAPH_CHANGED event arrives the canvas is swapped out for
the new graph's canvas without re-creating the outer shell.

A slim header inside the tab panel shows the open file name and a Save button.
"""

import logging
from pathlib import Path
from typing import TYPE_CHECKING, Optional

from nicegui import ui

from haywire.ui.editor.decorator import editor
from haywire.ui.editor.base import BaseEditor
from haywire.ui.context_events import ContextChangeType

if TYPE_CHECKING:
    from haywire.ui.context import SessionContext
    from haywire.ui.context_events import ContextChangedEvent
    from haywire.ui.graph_canvas.graph_canvas_manager import GraphCanvasManager


@editor(
    registry_id='graph_editor',
    label='Graph Editor',
    icon='account_tree',
    default_area='middle',
    description='Visual node graph editor for wiring data processing pipelines.',
)
class GraphEditor(BaseEditor):
    """
    The graph canvas editor.

    Wraps GraphCanvasManager inside a thin chrome that includes a header bar
    with the open file name and a Save button.

    Context changes consumed:
        ACTIVE_GRAPH_CHANGED — swap to a different graph / file.
        DATA_MUTATED         — sync canvas from another session.

    Context changes emitted:
        SELECTION_CHANGED    — node / edge selection.
        MODE_CHANGED         — interaction mode.
        DATA_MUTATED         — graph structure changes.

    The 'project_state' entry in context.metadata is set by haywire-app and
    must expose:
        .graph_manager          (GraphManager)  — preferred
        .editor                 (Editor)        — fallback for untitled graph
        .node_render_factory    (RenderFactory)
        .node_factory           (NodeFactory)
    """

    def __init__(self):
        self._canvas_manager: Optional['GraphCanvasManager'] = None
        self._project_state = None
        self._canvas_wrapper = None      # ui.element — cleared on graph switch
        self._graph_name_label = None    # ui.label in the header

    # ------------------------------------------------------------------
    # render
    # ------------------------------------------------------------------

    def render(self, container, context: 'SessionContext') -> None:
        self._project_state = context.metadata.get('project_state')
        if self._project_state is None:
            with container:
                ui.label('GraphEditor: no project_state in context.metadata').classes(
                    'text-red-400 p-4'
                )
            logging.warning("GraphEditor.render(): project_state not found in context.metadata")
            return

        with container:
            with ui.column().classes('w-full gap-0').style('height: 100%; overflow: hidden;'):
                # ---- slim header bar ----
                with ui.row().classes(
                    'w-full items-center px-3 gap-2 flex-shrink-0 border-b'
                ).style('min-height: 32px; background: #1a1a2e;'):
                    ui.icon('account_tree', size='14px').classes('text-gray-500')
                    self._graph_name_label = ui.label('Untitled').classes(
                        'text-xs text-gray-400 truncate font-mono flex-1'
                    )
                    ui.button(
                        icon='save',
                        on_click=lambda: self._save_graph(context),
                    ).props('flat round dense size=xs color=grey').tooltip('Save graph')

                # ---- canvas area (swapped on ACTIVE_GRAPH_CHANGED) ----
                self._canvas_wrapper = ui.element('div').style(
                    'flex: 1; width: 100%; overflow: hidden; min-height: 0;'
                )
                with self._canvas_wrapper:
                    self._build_canvas(context)

        self._update_header(context)

    # ------------------------------------------------------------------
    # canvas build / swap
    # ------------------------------------------------------------------

    def _build_canvas(self, context: 'SessionContext') -> None:
        """Instantiate a GraphCanvasManager inside _canvas_wrapper."""
        from haywire.ui.graph_canvas.graph_canvas_manager import GraphCanvasManager

        app = self._project_state
        entry = self._get_entry(context)

        # Prefer the entry's editor; fall back to app.editor for untitled
        if entry is not None:
            graph_editor = entry.editor
        elif hasattr(app, 'editor'):
            graph_editor = app.editor
        else:
            ui.label('No graph loaded').classes('text-gray-500 p-4')
            return

        self._canvas_manager = GraphCanvasManager(
            editor=graph_editor,
            node_render_factory=app.node_render_factory,
            node_factory=app.node_factory,
            session_id=context.session_id[:8],
        )
        self._canvas_manager.sync_with_graph()
        logging.info(f"GraphEditor: canvas built for session {context.session_id[:8]}")

    def _get_entry(self, context: 'SessionContext'):
        """Look up the active GraphEntry from the graph_manager, if available."""
        app = self._project_state
        if app is None or not hasattr(app, 'graph_manager'):
            return None
        return app.graph_manager.get_by_path(context.active_graph_path)

    # ------------------------------------------------------------------
    # header
    # ------------------------------------------------------------------

    def _update_header(self, context: 'SessionContext') -> None:
        """Refresh the name label to reflect the current graph."""
        if self._graph_name_label is None:
            return
        entry = self._get_entry(context)
        if context.active_graph_path is not None:
            name = Path(context.active_graph_path).name
            unsaved = entry.unsaved if entry else False
            self._graph_name_label.text = ('● ' if unsaved else '') + name
            self._graph_name_label.classes(remove='text-gray-400', add='text-gray-200')
        else:
            self._graph_name_label.text = 'Untitled'
            self._graph_name_label.classes(remove='text-gray-200', add='text-gray-400')

    # ------------------------------------------------------------------
    # context changes
    # ------------------------------------------------------------------

    def on_context_changed(
        self, event: 'ContextChangedEvent', context: 'SessionContext'
    ) -> None:
        if event.change_type == ContextChangeType.ACTIVE_GRAPH_CHANGED:
            self._swap_canvas(context)
        elif event.change_type == ContextChangeType.DATA_MUTATED:
            if self._canvas_manager:
                self._canvas_manager.sync_with_graph()

    def _swap_canvas(self, context: 'SessionContext') -> None:
        """Tear down the old canvas and build a fresh one for the new graph."""
        if self._canvas_wrapper is None:
            return

        # Clean up existing canvas manager
        if self._canvas_manager:
            try:
                self._canvas_manager.cleanup()
            except Exception as exc:
                logging.warning(f"GraphEditor: cleanup error during swap: {exc}")
            self._canvas_manager = None

        self._canvas_wrapper.clear()
        with self._canvas_wrapper:
            self._build_canvas(context)

        self._update_header(context)

    # ------------------------------------------------------------------
    # save
    # ------------------------------------------------------------------

    def _save_graph(self, context: 'SessionContext') -> None:
        """Save the active graph to its file path."""
        app = context.metadata.get('project_state')
        if app is None or not hasattr(app, 'graph_manager'):
            ui.notify('Graph manager not available', type='warning')
            return

        entry = self._get_entry(context)
        if entry is None:
            ui.notify('No graph to save', type='warning')
            return

        if entry.path is None:
            ui.notify(
                'Graph is untitled — use Save As to choose a file location',
                type='info',
            )
            return

        success = app.graph_manager.save_graph(entry)
        if success:
            ui.notify(f'Saved: {entry.path.name}', type='positive', position='top-right')
            self._update_header(context)
        else:
            ui.notify('Save failed', type='negative', position='top-right')

    # ------------------------------------------------------------------
    # cleanup
    # ------------------------------------------------------------------

    def cleanup(self) -> None:
        if self._canvas_manager:
            try:
                self._canvas_manager.cleanup()
            except Exception as exc:
                logging.error(f"GraphEditor.cleanup(): {exc}")
            self._canvas_manager = None
