"""
ContextMenuHandlers, IContextMenuProvider, and SessionContextMenuProvider.

ContextMenuHandlers translates canvas context-menu events into provider intent
calls.  The provider decides how to surface the menu.

Design:
- IContextMenuProvider defines *intent* methods, not imperative "show" calls.
- SessionContextMenuProvider is the panel-driven implementation: it updates
  SessionContext, queries PanelRegistry for registered panels
  (editor='context_menu', scope=trigger), and draws those that pass poll()
  into a Popup.
- ContextMenuHandlers accepts any IContextMenuProvider and never imports
  concrete implementations directly.
"""

import logging
from typing import Any, Callable, Optional, Tuple, TYPE_CHECKING

from ..event_definitions import (
    ContextMenuCanvasEvent,
    ContextMenuNodeEvent,
    ContextMenuEdgeEvent,
    ContextMenuSelectedEvent,
    ContextMenuCustomEvent,
    ContextMenuPortEvent,
    SyncEdgeConnectResumeEvent,
)
from ..event_handlers import handles_event
from haywire.ui.panel.base import PanelLayout
from haywire.ui.components.popup import Popup

if TYPE_CHECKING:
    from haywire.ui.graph_canvas.handlers.visual_layer import VisualLayerHandlers
    from haywire.ui.context import SessionContext
    from haywire.ui.session import Session
    from haywire.ui.panel.registry import PanelRegistry

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Protocol
# ---------------------------------------------------------------------------

# hardcoded scope for built-in context menu types.
SCOPE_CANVAS = "canvas"
SCOPE_NODE = "node"
SCOPE_EDGE = "edge"
SCOPE_SELECTION = "selection"

EDITOR_CONTEXT_MENU = "context_menu"


class IContextMenuProvider:
    """
    Intent-based interface for surfacing context menus.

    Implementors receive *what* the user wants and decide *how* to show it.
    The method signatures use plain positional tuples for positions so
    implementations are not coupled to canvas-specific types.
    """

    def on_canvas_context(
        self,
        pos: Tuple[float, float],
        canvas_pos: Tuple[float, float],
        pending_connection: Optional[dict] = None,
    ) -> None:
        """User right-clicked on empty canvas space."""
        ...

    def on_node_context(
        self,
        pos: Tuple[float, float],
        node_id: str,
    ) -> None:
        """User right-clicked on a node."""
        ...

    def on_edge_context(
        self,
        pos: Tuple[float, float],
        edge_id: str,
        edge: Any,
        state: Any,
        at_sink_end: bool = False,
    ) -> None:
        """User right-clicked on an edge."""
        ...

    def on_selection_context(
        self,
        pos: Tuple[float, float],
        nodes: list,
        edges: list,
    ) -> None:
        """User right-clicked on a multi-element selection."""
        ...

    def on_custom_context(
        self,
        pos: Tuple[float, float],
        node_id: str,
        scope: str,
    ) -> None:
        """User right-clicked a custom-scope element (data-hw-custom-menu-scope)."""
        ...

    def on_port_context(
        self,
        pos: Tuple[float, float],
        node_id: str,
        port_id: str,
        scope: str,
    ) -> None:
        """User right-clicked a port-scope element (data-hw-port-menu-scope)."""
        ...


# ---------------------------------------------------------------------------
# Session-context-driven provider
# ---------------------------------------------------------------------------


class SessionContextMenuProvider(IContextMenuProvider):
    """
    Panel-driven IContextMenuProvider implementation.

    On each intent call this provider:
    1. Updates SessionContext (active_node/edge, context_menu_trigger).
    2. Queries PanelRegistry for panels with editor=EDITOR_CONTEXT_MENU and
       the matching scope, filters by poll(), and draws matching panels into
       a Popup produced by popup_factory.
    3. Registers a close callback that clears context_menu_trigger and
       drains popup-internal metadata keys.
    """

    def __init__(
        self,
        context: "SessionContext",
        session: "Session",
        panel_registry: "PanelRegistry",
        on_emit_event: Optional[Callable] = None,
        on_emit_sync_event: Optional[Callable] = None,
    ):
        self._context = context
        self._session = session
        self._panel_registry = panel_registry
        self._on_emit_event = on_emit_event
        self._on_emit_sync_event = on_emit_sync_event

    def _open_menu(
        self,
        trigger: str,
        pos: Tuple[float, float],
    ) -> None:
        """Common logic: set trigger, build popup, draw panels, register close."""
        self._context.context_menu_trigger = trigger

        popup = Popup(position_x=pos[0], position_y=pos[1], backdrop_click_close=True)

        def _emit_and_close(event):
            # Emit first so handlers can still read metadata (e.g. pending_connection),
            # then close so _on_close cleanup runs after the event is processed.
            if self._on_emit_event:
                self._on_emit_event(event)
            popup.close()

        self._context.metadata["on_emit_event"] = _emit_and_close

        def _on_close():
            self._context.context_menu_trigger = None
            self._context.active_port = None
            self._context.active_edge = None
            self._context.metadata.pop("on_emit_event", None)
            self._context.metadata.pop("edge_state", None)
            self._context.metadata.pop("context_menu_screen_pos", None)
            self._context.metadata.pop("edge_reconnect_end", None)
            # If pending_connection is still set, no node was created — resume the drag.
            if self._context.metadata.pop("pending_connection", None) is not None:
                self._on_emit_sync_event(SyncEdgeConnectResumeEvent())

        popup.on_close(_on_close)

        # Query panels matching editor/scope, filter by poll(), and draw into popup
        panel_classes = self._panel_registry.get_panels(EDITOR_CONTEXT_MENU, trigger)
        visible = [cls for cls in panel_classes if cls.poll(self._context)]
        if visible:
            layout = PanelLayout(popup.content)
            for cls in visible:
                try:
                    cls().draw(self._context, layout)
                except Exception as exc:
                    logger.exception(f"Error drawing context menu panel {cls.__name__}: {exc}")
            popup.open()

    def on_canvas_context(self, pos, canvas_pos, pending_connection=None):
        self._context.metadata["canvas_position"] = {"x": canvas_pos[0], "y": canvas_pos[1]}
        if pending_connection:
            self._context.metadata["pending_connection"] = pending_connection
        self._open_menu(SCOPE_CANVAS, pos)

    def on_node_context(self, pos, node_id):
        # Set active_node so that panel poll() checks pass even when
        # the right-clicked node is not currently selected.
        if self._context.active_graph is not None:
            wrapper = self._context.active_graph.get_node_wrapper(node_id)
            if wrapper is not None:
                self._context.active_node = wrapper
        self._open_menu(SCOPE_NODE, pos)

    def on_edge_context(self, pos, edge_id, edge, state, at_sink_end=False):
        if self._context.active_graph is not None:
            wrapper = self._context.active_graph.get_edge_wrapper(edge_id)
            if wrapper is not None:
                self._context.active_edge = wrapper
        self._context.metadata["edge_state"] = state
        self._context.metadata["context_menu_screen_pos"] = pos
        self._context.metadata["edge_reconnect_end"] = at_sink_end
        self._open_menu(SCOPE_EDGE, pos)

    def on_port_context(self, pos, node_id, port_id, scope):
        if self._context.active_graph is not None:
            wrapper = self._context.active_graph.get_node_wrapper(node_id)
            if wrapper is not None:
                self._context.active_node = wrapper
                self._context.active_port = wrapper.node.ports.get(port_id)
        self._open_menu(scope, pos)

    def on_selection_context(self, pos, nodes, edges):
        self._open_menu(SCOPE_SELECTION, pos)

    def on_custom_context(self, pos, node_id, scope):
        if self._context.active_graph is not None:
            wrapper = self._context.active_graph.get_node_wrapper(node_id)
            if wrapper is not None:
                self._context.active_node = wrapper
        self._open_menu(scope, pos)


# ---------------------------------------------------------------------------
# Handler
# ---------------------------------------------------------------------------


class ContextMenuHandlers:
    """
    Handle context-menu canvas events.

    Reads edge data from VisualLayerHandlers (via the get_edge accessor) and
    delegates all menu-surface decisions to an IContextMenuProvider.
    """

    def __init__(
        self,
        visual_layer: "VisualLayerHandlers",
        provider: IContextMenuProvider,
    ):
        self.visual_layer = visual_layer
        self.provider = provider

    @handles_event(
        ContextMenuCanvasEvent,
        ContextMenuNodeEvent,
        ContextMenuEdgeEvent,
        ContextMenuSelectedEvent,
        ContextMenuCustomEvent,
        ContextMenuPortEvent,
    )
    def process_context_menu(self, event):
        """Route context-menu events to the provider as intent calls."""
        if isinstance(event, ContextMenuCanvasEvent):
            logger.debug(f"Canvas context menu at ({event.screenX}, {event.screenY})")
            pending = None
            if event.pendingPinId:
                pending = {
                    "pin_id": event.pendingPinId,
                    "node_id": event.pendingNodeId,
                    "pin_dir": event.pendingPinDir,
                    "flow_type": event.pendingFlowType,
                    "data_type": event.pendingDataType,
                }
            self.provider.on_canvas_context(
                (event.screenX, event.screenY),
                (event.canvasX, event.canvasY),
                pending_connection=pending,
            )

        elif isinstance(event, ContextMenuNodeEvent):
            logger.debug(f"Node context menu for {event.nodeId} at ({event.screenX}, {event.screenY})")
            self.provider.on_node_context(
                (event.screenX, event.screenY),
                event.nodeId,
            )

        elif isinstance(event, ContextMenuEdgeEvent):
            logger.debug(f"Edge context menu for {event.edge_id} at ({event.screenX}, {event.screenY})")
            ui_edge = self.visual_layer.get_edge(event.edge_id)
            if ui_edge and ui_edge.wrapper:
                self.provider.on_edge_context(
                    (event.screenX, event.screenY),
                    event.edge_id,
                    ui_edge.wrapper.edge,
                    ui_edge.wrapper.get_state(),
                    at_sink_end=event.atSinkEnd,
                )

        elif isinstance(event, ContextMenuSelectedEvent):
            logger.debug(
                f"Selection context menu at ({event.screenX}, {event.screenY}) "
                f"for {len(event.selectedNodes)} nodes, {len(event.selectedEdges)} connections"
            )
            self.provider.on_selection_context(
                (event.screenX, event.screenY),
                event.selectedNodes,
                event.selectedEdges,
            )

        elif isinstance(event, ContextMenuCustomEvent):
            logger.debug(
                f"Custom context menu scope={event.scope!r} "
                f"for node {event.nodeId} at ({event.screenX}, {event.screenY})"
            )
            self.provider.on_custom_context(
                (event.screenX, event.screenY),
                event.nodeId,
                event.scope,
            )

        elif isinstance(event, ContextMenuPortEvent):
            logger.debug(
                f"Port context menu scope={event.scope!r} "
                f"for port {event.portId} on node {event.nodeId} at ({event.screenX}, {event.screenY})"
            )
            self.provider.on_port_context(
                (event.screenX, event.screenY),
                event.nodeId,
                event.portId,
                event.scope,
            )
