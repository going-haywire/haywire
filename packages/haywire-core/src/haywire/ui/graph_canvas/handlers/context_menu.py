"""
ContextMenuHandlers and IContextMenuProvider.

ContextMenuHandlers translates canvas context-menu events into provider intent
calls.  The provider decides how to surface the menu — today that is
PopupContextMenuProvider (wrapping PopupContextMenu); in future it will be a
session-context-driven implementation that allows libraries to contribute panels.

Design:
- IContextMenuProvider defines *intent* methods, not imperative "show" calls.
- PopupContextMenuProvider wraps PopupContextMenu and implements the protocol.
- ContextMenuHandlers never imports PopupContextMenu directly.
"""

import logging
from typing import Any, Optional, Tuple, TYPE_CHECKING

from ..event_definitions import (
    ContextMenuCanvasEvent,
    ContextMenuNodeEvent,
    ContextMenuEdgeEvent,
    ContextMenuSelectedEvent,
)
from ..event_handlers import handles_event

if TYPE_CHECKING:
    from haywire.ui.graph_canvas.handlers.visual_layer import VisualLayerHandlers

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


# ---------------------------------------------------------------------------
# Adapter: PopupContextMenu → IContextMenuProvider
# ---------------------------------------------------------------------------


class PopupContextMenuProvider(IContextMenuProvider):
    """
    Adapter that wraps the existing PopupContextMenu behind IContextMenuProvider.

    This keeps ContextMenuHandlers decoupled from the NiceGUI popup implementation.
    """

    def __init__(self, popup_context_menu):
        self._menu = popup_context_menu

    def on_canvas_context(self, pos, canvas_pos):
        self._menu.show_canvas_menu(pos[0], pos[1], canvas_pos[0], canvas_pos[1])

    def on_node_context(self, pos, node_id):
        self._menu.show_node_menu(pos[0], pos[1], node_id)

    def on_edge_context(self, pos, edge_id, edge, state):
        self._menu.show_edge_menu(pos[0], pos[1], edge_id, edge, state)

    def on_selection_context(self, pos, nodes, edges):
        self._menu.show_selected_menu(pos[0], pos[1], nodes, edges)


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
    )
    def process_context_menu(self, event):
        """Route context-menu events to the provider as intent calls."""
        if isinstance(event, ContextMenuCanvasEvent):
            logger.debug(f"Canvas context menu at ({event.screenX}, {event.screenY})")
            self.provider.on_canvas_context(
                (event.screenX, event.screenY),
                (event.canvasX, event.canvasY),
            )

        elif isinstance(event, ContextMenuNodeEvent):
            logger.debug(
                f"Node context menu for {event.nodeId} at ({event.screenX}, {event.screenY})"
            )
            self.provider.on_node_context(
                (event.screenX, event.screenY),
                event.nodeId,
            )

        elif isinstance(event, ContextMenuEdgeEvent):
            logger.debug(
                f"Edge context menu for {event.edge_id} at ({event.screenX}, {event.screenY})"
            )
            ui_edge = self.visual_layer.get_edge(event.edge_id)
            if ui_edge and ui_edge.wrapper:
                self.provider.on_edge_context(
                    (event.screenX, event.screenY),
                    event.edge_id,
                    ui_edge.wrapper.edge,
                    ui_edge.wrapper.get_state(),
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
