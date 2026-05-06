"""
ContextMenuHandlers, IContextMenuProvider, and SessionContextMenuProvider.

ContextMenuHandlers translates canvas context-menu events into provider intent
calls.  The provider decides how to surface the menu.

Design:
- IContextMenuProvider defines *intent* methods, not imperative "show" calls.
- SessionContextMenuProvider is the panel-driven implementation: it updates
  SessionContext, queries PanelRegistry for panels matching the actions
  provider and focus of the right-clicked element, and draws those that
  pass poll() into a Popup.
- ContextMenuHandlers accepts any IContextMenuProvider and never imports
  concrete implementations directly.
"""

import logging
from dataclasses import dataclass
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
from haywire.ui.panel.layout import PanelLayout
from haywire.ui.components.popup import Popup
from haybale_studio.state.edit_state import EditState

if TYPE_CHECKING:
    from haybale_studio.editors.graph_canvas.handlers.visual_layer import VisualLayerHandlers
    from haywire.ui.context import SessionContext
    from haywire.ui.session import Session
    from haywire.ui.panel.registry import PanelRegistry

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Protocol
# ---------------------------------------------------------------------------


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
        """User right-clicked a custom-scope element (data-hw-custom-menu-focus-id)."""
        ...

    def on_port_context(
        self,
        pos: Tuple[float, float],
        node_id: str,
        port_id: str,
        scope: str,
    ) -> None:
        """User right-clicked a port-scope element (data-hw-port-menu-focus-id)."""
        ...


# ---------------------------------------------------------------------------
# Per-popup gesture state
# ---------------------------------------------------------------------------


@dataclass
class _OpenMenuContext:
    """Per-popup gesture state held by SessionContextMenuProvider.

    Created when _open_menu opens a popup; cleared on popup close.
    Replaces several entries from the legacy metadata dict
    (canvas_position, canvas_x, canvas_y, edge_state,
    context_menu_screen_pos, edge_reconnect_end, pending_connection).

    Phase 1.5 of the panel-contract migration.
    """

    click_pos: Tuple[float, float]
    canvas_pos: Optional[Tuple[float, float]] = None
    pending_connection: Optional[dict] = None
    edge_state: Any = None
    edge_reconnect_end: bool = False


# ---------------------------------------------------------------------------
# Session-context-driven provider
# ---------------------------------------------------------------------------


class SessionContextMenuProvider(IContextMenuProvider):
    """
    Panel-driven IContextMenuProvider implementation.

    On each intent call this provider:
    1. Updates SessionContext (active_node/edge/port).
    2. Queries PanelRegistry for panels matching the actions provider and
       focus of the right-clicked element, filters by poll(), and draws
       matching panels into a Popup produced by popup_factory.
    3. Registers a close callback that clears active_port/active_edge and
       resumes any pending edge-drag connection.
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
        self._open_ctx: Optional[_OpenMenuContext] = None  # per-popup gesture state
        self._open_popup: Optional[Popup] = None  # currently-open menu popup, closed after any action

    def _build_popup(self, pos: Tuple[float, float]):
        """Build a Popup at the given position. Extracted for testability."""
        return Popup(position_x=pos[0], position_y=pos[1], backdrop_click_close=True)

    def _open_menu(
        self,
        action: type,
        focus: type,  # type[Focus] but loose to avoid circular import
        pos: Tuple[float, float],
    ) -> None:
        """Common logic: build popup, query panels for (action, focus), draw."""
        # Open _OpenMenuContext for this popup; the intent handlers above
        # (on_canvas_context, on_node_context, etc.) populated the rest of
        # its fields before calling _open_menu.
        if self._open_ctx is None:
            # Defensive: an intent handler called _open_menu without
            # building _open_ctx. Build a minimal one.
            self._open_ctx = _OpenMenuContext(click_pos=pos)
        else:
            self._open_ctx.click_pos = pos

        popup = self._build_popup(pos)
        self._open_popup = popup

        def _on_close():
            edit_state = self._context.data[EditState]
            edit_state.active_port.value = None
            edit_state.active_edge.value = None
            # Resume drag if pending_connection wasn't consumed
            pending = self._open_ctx.pending_connection if self._open_ctx else None
            self._open_ctx = None
            self._open_popup = None
            if pending is not None and self._on_emit_sync_event:
                self._on_emit_sync_event(SyncEdgeConnectResumeEvent())

        popup.on_close(_on_close)

        panel_classes = self._panel_registry.get_panels_for(actions_provider=self, focus=focus)

        visible = [cls for cls in panel_classes if cls.poll(self._context)]
        if not visible:
            return

        layout = PanelLayout(popup.content)
        for cls in visible:
            try:
                cls().draw(self._context, layout, self)
            except Exception as exc:
                logger.exception(f"Error drawing context menu panel {cls.__name__}: {exc}")
        popup.open()

    def on_canvas_context(self, pos, canvas_pos, pending_connection=None):
        from haybale_studio.focuses import CanvasFocus  # type: ignore[import-untyped]
        from haybale_studio.editors.graph_canvas.handlers.context_menu_actions import CanvasContextActions

        self._open_ctx = _OpenMenuContext(
            click_pos=pos,
            canvas_pos=canvas_pos,
            pending_connection=pending_connection,
        )
        self._open_menu(CanvasContextActions, CanvasFocus, pos)

    def on_node_context(self, pos, node_id):
        from haybale_studio.focuses import NodeFocus  # type: ignore[import-untyped]
        from haybale_studio.editors.graph_canvas.handlers.context_menu_actions import NodeContextActions

        graph = self._context.data[EditState].active_graph.value
        if graph is not None:
            wrapper = graph.get_node_wrapper(node_id)
            if wrapper is not None:
                self._context.data[EditState].active_node.value = wrapper

        self._open_ctx = _OpenMenuContext(click_pos=pos)
        self._open_menu(NodeContextActions, NodeFocus, pos)

    def on_edge_context(self, pos, edge_id, edge, state, at_sink_end=False):
        from haybale_studio.focuses import EdgeFocus  # type: ignore[import-untyped]
        from haybale_studio.editors.graph_canvas.handlers.context_menu_actions import EdgeContextActions

        graph = self._context.data[EditState].active_graph.value
        if graph is not None:
            wrapper = graph.get_edge_wrapper(edge_id)
            if wrapper is not None:
                self._context.data[EditState].active_edge.value = wrapper

        self._open_ctx = _OpenMenuContext(
            click_pos=pos,
            edge_state=state,
            edge_reconnect_end=at_sink_end,
        )
        self._open_menu(EdgeContextActions, EdgeFocus, pos)

    def on_port_context(self, pos, node_id, port_id, scope):
        from haybale_studio.focuses import PortFocus  # type: ignore[import-untyped]
        from haybale_studio.editors.graph_canvas.handlers.context_menu_actions import PortContextActions
        from haywire.ui.panel.focus import focus_by_id

        graph = self._context.data[EditState].active_graph.value
        if graph is not None:
            wrapper = graph.get_node_wrapper(node_id)
            if wrapper is not None:
                port = wrapper.node.ports.get(port_id)
                edit_state = self._context.data[EditState]
                edit_state.active_node.value = wrapper
                edit_state.active_port.value = port

        self._open_ctx = _OpenMenuContext(click_pos=pos)
        # Resolve the focus from the DOM-supplied id; fall back to PortFocus.
        focus = focus_by_id(scope) or PortFocus
        self._open_menu(PortContextActions, focus, pos)

    def on_selection_context(self, pos, nodes, edges):
        from haybale_studio.focuses import SelectionFocus  # type: ignore[import-untyped]
        from haybale_studio.editors.graph_canvas.handlers.context_menu_actions import SelectionContextActions

        self._open_ctx = _OpenMenuContext(click_pos=pos)
        self._open_menu(SelectionContextActions, SelectionFocus, pos)

    def on_custom_context(self, pos, node_id, scope):
        """Resolve the focus via Focus.id; uses NodeContextActions by default.

        Library authors can declare a custom focus and register panels
        against it; the DOM attribute carries the focus id.
        """
        from haybale_studio.focuses import NodeFocus  # type: ignore[import-untyped]
        from haybale_studio.editors.graph_canvas.handlers.context_menu_actions import NodeContextActions
        from haywire.ui.panel.focus import focus_by_id

        graph = self._context.data[EditState].active_graph.value
        if graph is not None:
            wrapper = graph.get_node_wrapper(node_id)
            if wrapper is not None:
                self._context.data[EditState].active_node.value = wrapper

        self._open_ctx = _OpenMenuContext(click_pos=pos)
        focus = focus_by_id(scope) or NodeFocus
        self._open_menu(NodeContextActions, focus, pos)

    # ------------------------------------------------------------------
    # ContextMenuActions Protocol implementations (Phase 1.5)
    # ------------------------------------------------------------------

    def _emit(self, event) -> None:
        """Emit an event from a context-menu action and close the popup.

        Action methods are invoked by panel buttons; selecting any item
        should dismiss the menu. Panels themselves don't have a popup
        handle, so closing centrally here keeps that contract.
        """
        if self._on_emit_event:
            self._on_emit_event(event)
        if self._open_popup is not None:
            self._open_popup.close()

    # CanvasContextActions

    def create_node_at_click(self, registry_key: str) -> None:
        """Emit NodeCreateRequestEvent at the click's canvas position.

        If the menu was opened mid-drag from a pin, the pending_connection
        dict is forwarded on the event so the visual layer can auto-wire
        the new node. Mark it consumed so the popup-close path does not
        also emit SyncEdgeConnectResumeEvent.
        """
        from haybale_studio.editors.graph_canvas.event_definitions import NodeCreateRequestEvent

        if self._open_ctx is None or self._open_ctx.canvas_pos is None:
            return
        x, y = self._open_ctx.canvas_pos
        pending = self._open_ctx.pending_connection
        self._open_ctx.pending_connection = None
        self._emit(
            NodeCreateRequestEvent(
                registryKey=registry_key,
                position={"x": x, "y": y},
                pending_connection=pending,
            )
        )

    def paste_at_click(self) -> None:
        """Emit UserPasteClipboardEvent at the click's canvas position."""
        from haybale_studio.editors.graph_canvas.event_definitions import UserPasteClipboardEvent

        if self._open_ctx is None or self._open_ctx.canvas_pos is None:
            return
        x, y = self._open_ctx.canvas_pos
        self._emit(UserPasteClipboardEvent(canvasX=x, canvasY=y))

    # NodeContextActions

    def delete_node(self, node_id: str) -> None:
        from haybale_studio.editors.graph_canvas.event_definitions import UserRemoveEvent

        self._emit(UserRemoveEvent(nodes=[node_id], edges=[]))

    def copy_node(self, node_id: str) -> None:
        from haybale_studio.editors.graph_canvas.event_definitions import UserCopySelectedEvent

        self._emit(UserCopySelectedEvent(selectedNodes=[node_id], selectedEdges=[]))

    def redraw_node(self, node_id: str) -> None:
        from haybale_studio.editors.graph_canvas.event_definitions import ElementRedrawEvent

        self._emit(ElementRedrawEvent(nodes=[node_id], edges=[]))

    def revalidate_node(self, node_id: str) -> None:
        from haybale_studio.editors.graph_canvas.event_definitions import ElementRevalidateEvent

        self._emit(ElementRevalidateEvent(nodes=[node_id], edges=[]))

    def reset_node(self, node_id: str) -> None:
        from haybale_studio.editors.graph_canvas.event_definitions import ElementResetEvent

        self._emit(ElementResetEvent(nodes=[node_id], edges=[]))

    # EdgeContextActions

    def delete_edge(self, edge_id: str) -> None:
        from haybale_studio.editors.graph_canvas.event_definitions import UserRemoveEvent

        self._emit(UserRemoveEvent(nodes=[], edges=[edge_id]))

    def reconnect_active_edge(self) -> None:
        """Emit SyncEdgeReconnectEvent for the active edge.

        Reads `ctx.data[EditState].active_edge.value` (the edge to reconnect)
        and `self._open_ctx.edge_reconnect_end` (which end was right-clicked)
        to compute the anchor pin. Panels never pass these as arguments —
        the provider holds them as gesture state.
        """
        from haybale_studio.editors.graph_canvas.event_definitions import SyncEdgeReconnectEvent

        wrapper = self._context.data[EditState].active_edge.value
        if wrapper is None or self._open_ctx is None:
            return

        at_sink_end = self._open_ctx.edge_reconnect_end
        if at_sink_end:
            # Clicked near inlet → anchor on outlet (source) side
            anchor_node_id = wrapper.source_node_id
            anchor_pin_id = wrapper.outlet_port_id
        else:
            # Clicked near outlet → anchor on inlet (sink) side
            anchor_node_id = wrapper.sink_node_id
            anchor_pin_id = wrapper.inlet_port_id

        self._emit(
            SyncEdgeReconnectEvent(
                edge_id=wrapper._edge_id,
                anchorNodeId=anchor_node_id,
                anchorPinId=anchor_pin_id,
            )
        )

    # SelectionContextActions

    def copy_selection(self) -> None:
        """Emit UserCopySelectedEvent for the current ctx.data[EditState] selection."""
        from haybale_studio.editors.graph_canvas.event_definitions import UserCopySelectedEvent

        edit = self._context.data[EditState]
        self._emit(
            UserCopySelectedEvent(
                selectedNodes=list(edit.selected_nodes.value),
                selectedEdges=list(edit.selected_edges.value),
            )
        )


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
