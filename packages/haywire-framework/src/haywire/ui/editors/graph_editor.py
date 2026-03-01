# packages/haywire-framework/src/haywire/ui/editors/graph_editor.py
"""
GraphEditor — wraps the existing GraphCanvasManager as a BaseEditor.

This makes the graph canvas a first-class editor type that integrates with
the workspace layout system. It reads the project state from the session
context and instantiates a GraphCanvasManager inside the given container.
"""

import logging
from typing import TYPE_CHECKING, Optional

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

    Wraps the existing GraphCanvasManager and its Vue component.
    Owns the RendererRegistry consumption for node body rendering.

    Context changes this editor EMITS:
        - SELECTION_CHANGED: when user selects/deselects nodes or edges
        - MODE_CHANGED: when interaction mode changes
        - DATA_MUTATED: when graph structure changes (add/remove nodes/edges)

    Context changes this editor CONSUMES:
        - ACTIVE_GRAPH_CHANGED: swap to a different graph
        - DATA_MUTATED (from other sessions): sync graph changes

    Integration with existing code:
        - GraphCanvasManager → instantiated inside render(), stored as _canvas_manager
        - GraphCanvasVue → unchanged, still the Vue component
        - UINode → unchanged, still manages per-node UI lifecycle
        - RenderFactory → unchanged, still manages renderer instances
        - PopupContextMenu → unchanged, still the right-click menu

    The 'project_state' is expected in context.metadata, set by the haywire-app
    before calling AppShell.render(). It must have:
        - .editor       (Editor instance wrapping the shared graph)
        - .node_render_factory  (RenderFactory)
        - .node_factory         (NodeFactory)
    """

    def __init__(self):
        self._canvas_manager: Optional['GraphCanvasManager'] = None
        self._project_state = None

    def render(self, container, context: 'SessionContext') -> None:
        from nicegui import ui
        from haywire.ui.graph_canvas.graph_canvas_manager import GraphCanvasManager

        self._project_state = context.metadata.get('project_state')
        if self._project_state is None:
            with container:
                ui.label('GraphEditor: no project_state in context.metadata').classes(
                    'text-red-400 p-4'
                )
            logging.warning("GraphEditor.render(): project_state not found in context.metadata")
            return

        app = self._project_state
        with container:
            self._canvas_manager = GraphCanvasManager(
                editor=app.editor,
                node_render_factory=app.node_render_factory,
                node_factory=app.node_factory,
                session_id=context.session_id[:8],
            )

        # Sync the canvas with the existing graph state
        self._canvas_manager.sync_with_graph()
        logging.info(f"GraphEditor: canvas created for session {context.session_id[:8]}")

    def on_context_changed(self, event: 'ContextChangedEvent', context: 'SessionContext') -> None:
        """Sync canvas when graph data changes from another session."""
        if event.change_type == ContextChangeType.DATA_MUTATED:
            if self._canvas_manager:
                self._canvas_manager.sync_with_graph()

    def cleanup(self) -> None:
        """Clean up the underlying canvas manager."""
        if self._canvas_manager:
            try:
                self._canvas_manager.cleanup()
            except Exception as e:
                logging.error(f"GraphEditor.cleanup(): {e}")
            self._canvas_manager = None
