"""
GraphCanvasManager — facade that wires handler objects to the Vue canvas.

Public API is unchanged; all event-handling and visual-management logic has
been moved into focused handler classes under handlers/.
"""

import logging
import traceback
from typing import Callable, Dict, Set
from nicegui import ui

from haywire.core.graph.editor import Editor

from ..components.zoom.pan import ZoomPanContainer
from ..components.graph.canvas import GraphCanvasVue
from .event_definitions import BaseGraphEvent, GRAPH_EVENT_REGISTRY
from .event_handlers import build_event_handler_map
from .handlers.interaction import InteractionHandlers
from .handlers.selection import SelectionHandlers
from .handlers.visual_layer import VisualLayerHandlers
from .handlers.context_menu import ContextMenuHandlers, SessionContextMenuProvider
from ..session import Session

logger = logging.getLogger(__name__)


class GraphCanvasManager:
    """
    Facade that wires canvas event handlers and the Vue component together.

    Responsibilities kept here:
    - Canvas/zoom/menu construction (_setup_canvas)
    - Building and connecting handler objects
    - Event dispatch (build_event_handler_map + _handle_canvas_event)
    - Public facade methods (sync_with_graph, cleanup, …)

    All domain logic lives in the handler sub-objects:
    - visual_layer  → VisualLayerHandlers
    - selection     → SelectionHandlers
    - interactions  → InteractionHandlers
    - context_menus → ContextMenuHandlers
    """

    def __init__(self, editor: Editor, skin_factory, node_factory, panel_registry, session: "Session"):
        self.editor = editor
        self.skin_factory = skin_factory
        self.node_factory = node_factory
        self._panel_registry = panel_registry
        self._session = session
        self.session_id = session.session_id[:8]

        self.graph = editor.graph

        # Vue component references built in _setup_canvas
        self.zoom_container, self.canvas_vue = self._setup_canvas()

        # Build handler objects
        self.visual_layer = VisualLayerHandlers(
            graph=self.graph,
            editor=self.editor,
            skin_factory=self.skin_factory,
            canvas_vue=self.canvas_vue,
            context=self._session.context,
        )
        self.selection = SelectionHandlers(
            graph=self.graph,
            editor=self.editor,
            session_id=self.session_id,
            session=self._session,
        )
        self.interactions = InteractionHandlers(editor=self.editor)

        context_menu_provider = SessionContextMenuProvider(
            context=self._session.context,
            session=self._session,
            panel_registry=self._panel_registry,
            on_emit_event=self._handle_canvas_event,
            on_emit_sync_event=self.canvas_vue.emit_sync_event,
        )

        self.context_menu_handlers = ContextMenuHandlers(
            visual_layer=self.visual_layer,
            provider=context_menu_provider,
        )

        # Build dispatch map from all handler sources
        self._event_handlers: Dict[str, Callable] = build_event_handler_map(
            [
                self.visual_layer,
                self.selection,
                self.interactions,
                self.context_menu_handlers,
            ]
        )

        self._validate_handler_coverage()

        # Subscribe for incremental validation updates
        self.graph.subscribe_to_validation(self.visual_layer.on_validated)

        logger.info(f"🔧 GraphCanvasManager for {self.session_id} is setup")

    # =========================================================================
    # Setup
    # =========================================================================

    def _setup_canvas(self) -> tuple[ZoomPanContainer, GraphCanvasVue]:
        """Create zoom container and Vue canvas component."""
        zoom_container = (
            ZoomPanContainer()
            .classes("w-full flex-grow")
            .style("border: 2px solid var(--hw-border);")
            .style("height: 100%;")
        )

        with zoom_container.content_container:
            canvas_vue = GraphCanvasVue(
                zoom_container=zoom_container,
                on_canvas_event=self._handle_canvas_event,
                canvas_width=self.graph.canvas_width,
                canvas_height=self.graph.canvas_height,
            )
        return zoom_container, canvas_vue

    def _validate_handler_coverage(self):
        """Warn if any user event lacks a registered handler."""
        user_events = [
            event_type
            for event_type, event_class in GRAPH_EVENT_REGISTRY.items()
            if getattr(event_class, "category", "user") == "user"
        ]
        missing = [et for et in user_events if et not in self._event_handlers]
        if missing:
            logger.warning(f"⚠️  Missing handlers for events: {missing}")
        else:
            logger.debug(f"✅ All {len(user_events)} user events have registered handlers")

    # =========================================================================
    # Event routing
    # =========================================================================

    def _handle_canvas_event(self, event: BaseGraphEvent):
        """Dispatch incoming canvas events to the appropriate handler."""
        event_type = event.event_type
        handler = self._event_handlers.get(event_type)

        if handler:
            logger.debug(f"🔧 Calling handler for {event_type}: {handler.__name__}")
            try:
                handler(event)
            except Exception as e:
                logger.error(f"❌ Error calling handler for {event_type}: {e}")
                ui.notify(f"Error while processing {event.description}: {e}", type="negative")
                traceback.print_exc()
        else:
            logger.warning(f"No handler found for event type: {event_type}")

    # =========================================================================
    # Public facade — unchanged external API
    # =========================================================================

    def sync_with_graph(self):
        """Synchronise visual representation with the current graph state."""
        self.visual_layer.sync_with_graph()

    def sync_selections(self):
        """Emit consolidated selection sync event to Vue."""
        self.visual_layer.sync_selections(
            self.selection.selected_nodes,
            self.selection.selected_edges,
        )

    def clear_all_visuals(self):
        """Clear all visual representations."""
        self.visual_layer.clear_all_visuals()
        self.selection.selected_nodes.clear()
        self.selection.selected_edges.clear()

    # Kept for callers that still reference these directly
    @property
    def node_panels(self) -> Dict:
        return self.visual_layer.node_panels

    @property
    def edge_paths(self) -> Dict:
        return self.visual_layer.edge_paths

    @property
    def selected_nodes(self) -> Set[str]:
        return self.selection.selected_nodes

    @property
    def selected_edges(self) -> Set[str]:
        return self.selection.selected_edges

    def _has_clipboard_content(self) -> bool:
        clipboard = self._session.context.clipboard.value
        return clipboard is not None and len(clipboard.nodes) > 0

    def cleanup(self):
        """Unsubscribe from graph validation and release resources."""
        logger.info(f"🔧 Shutting down GraphCanvasManager for {self.session_id} ...")

        try:
            self.graph.unsubscribe_from_validation(self.visual_layer.on_validated)
        except Exception as exc:
            logger.warning(f"GraphCanvasManager: unsubscribe error: {exc}")

        if self.canvas_vue:
            self.canvas_vue.cleanup()

        self.visual_layer.cleanup()

        logger.info(f"🔧 GraphCanvasManager for {self.session_id} is shut down")
