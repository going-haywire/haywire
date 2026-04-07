"""
Tests for IContextMenuProvider protocol and ContextMenuHandlers.

ContextMenuHandlers translates canvas events into intent calls on an
IContextMenuProvider. The provider decides how to surface the menu
(currently PopupContextMenu; future: session-context-driven panels).
"""

import pytest
from unittest.mock import MagicMock

from haywire.ui.graph_canvas.handlers.context_menu import (
    ContextMenuHandlers,
    IContextMenuProvider,
)
from haywire.ui.graph_canvas.event_definitions import (
    ContextMenuCanvasEvent,
    ContextMenuNodeEvent,
    ContextMenuEdgeEvent,
    ContextMenuSelectedEvent,
)
from haywire.ui.graph_canvas.event_handlers import build_event_handler_map

pytestmark = pytest.mark.unit


# ---------------------------------------------------------------------------
# Spy provider — records intent calls
# ---------------------------------------------------------------------------


class SpyProvider(IContextMenuProvider):
    def __init__(self):
        self.canvas_calls = []
        self.node_calls = []
        self.edge_calls = []
        self.selection_calls = []

    def on_canvas_context(self, pos, canvas_pos, pending_connection=None):
        self.canvas_calls.append((pos, canvas_pos))

    def on_node_context(self, pos, node_id):
        self.node_calls.append((pos, node_id))

    def on_edge_context(self, pos, edge_id, edge, state, at_sink_end=False):
        self.edge_calls.append((pos, edge_id, edge, state))

    def on_selection_context(self, pos, nodes, edges):
        self.selection_calls.append((pos, nodes, edges))


@pytest.fixture
def provider():
    return SpyProvider()


@pytest.fixture
def visual_layer():
    vl = MagicMock()
    vl.get_edge.return_value = None  # default: edge not found
    return vl


@pytest.fixture
def handler(visual_layer, provider):
    return ContextMenuHandlers(visual_layer=visual_layer, provider=provider)


# ---------------------------------------------------------------------------
# Canvas context menu
# ---------------------------------------------------------------------------


def test_canvas_event_calls_on_canvas_context(handler, provider):
    handler.process_context_menu(ContextMenuCanvasEvent(screenX=10, screenY=20, canvasX=100, canvasY=200))
    assert len(provider.canvas_calls) == 1
    pos, canvas_pos = provider.canvas_calls[0]
    assert pos == (10, 20)
    assert canvas_pos == (100, 200)


# ---------------------------------------------------------------------------
# Node context menu
# ---------------------------------------------------------------------------


def test_node_event_calls_on_node_context(handler, provider):
    handler.process_context_menu(
        ContextMenuNodeEvent(screenX=5, screenY=6, canvasX=50, canvasY=60, nodeId="n1")
    )
    assert len(provider.node_calls) == 1
    pos, node_id = provider.node_calls[0]
    assert pos == (5, 6)
    assert node_id == "n1"


# ---------------------------------------------------------------------------
# Edge context menu
# ---------------------------------------------------------------------------


def test_edge_event_reads_visual_layer(handler, visual_layer):
    """ContextMenuHandlers calls visual_layer.get_edge to look up UIEdge data."""
    handler.process_context_menu(
        ContextMenuEdgeEvent(screenX=0, screenY=0, canvasX=0, canvasY=0, edge_id="e1")
    )
    visual_layer.get_edge.assert_called_once_with("e1")


def test_edge_event_calls_on_edge_context_when_found(handler, provider, visual_layer):
    """When the edge is found, on_edge_context is called with edge + state."""
    mock_ui_edge = MagicMock()
    mock_ui_edge.wrapper.edge = "fake-edge-obj"
    mock_ui_edge.wrapper.get_state.return_value = "fake-state"
    visual_layer.get_edge.return_value = mock_ui_edge

    handler.process_context_menu(
        ContextMenuEdgeEvent(screenX=1, screenY=2, canvasX=10, canvasY=20, edge_id="e1")
    )
    assert len(provider.edge_calls) == 1
    pos, edge_id, edge, state = provider.edge_calls[0]
    assert edge_id == "e1"
    assert edge == "fake-edge-obj"
    assert state == "fake-state"


def test_edge_event_does_not_call_provider_when_edge_missing(handler, provider, visual_layer):
    """When the edge is not in visual_layer, provider is not called (nothing to show)."""
    visual_layer.get_edge.return_value = None
    handler.process_context_menu(
        ContextMenuEdgeEvent(screenX=0, screenY=0, canvasX=0, canvasY=0, edge_id="e_missing")
    )
    assert len(provider.edge_calls) == 0


# ---------------------------------------------------------------------------
# Selection context menu
# ---------------------------------------------------------------------------


def test_selection_event_calls_on_selection_context(handler, provider):
    handler.process_context_menu(
        ContextMenuSelectedEvent(
            screenX=3,
            screenY=4,
            canvasX=30,
            canvasY=40,
            selectedNodes=["n1", "n2"],
            selectedEdges=["e1"],
        )
    )
    assert len(provider.selection_calls) == 1
    pos, nodes, edges = provider.selection_calls[0]
    assert nodes == ["n1", "n2"]
    assert edges == ["e1"]


# ---------------------------------------------------------------------------
# Protocol structure
# ---------------------------------------------------------------------------


def test_provider_protocol_has_intent_methods():
    """IContextMenuProvider declares all four intent methods."""
    import inspect

    members = {name for name, _ in inspect.getmembers(IContextMenuProvider)}
    assert "on_canvas_context" in members
    assert "on_node_context" in members
    assert "on_edge_context" in members
    assert "on_selection_context" in members


# ---------------------------------------------------------------------------
# Handler registration
# ---------------------------------------------------------------------------


def test_all_context_menu_events_are_registered(handler):
    result = build_event_handler_map([handler])
    assert "contextMenuCanvas" in result
    assert "contextMenuNode" in result
    assert "contextMenuEdge" in result
    assert "contextMenuSelected" in result
