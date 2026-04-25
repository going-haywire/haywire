"""
Tests for VisualLayerHandlers — the pure-Python parts that don't require NiceGUI.

NiceGUI-dependent methods (add_node_visual, update_node_position, etc.) are
exercised through the integration/harness tests. Here we verify:
- Initial state
- read accessor (get_edge)
- Handler registration
- on_validated dispatch for add/remove/moved/redraw cases
"""

import pytest
from unittest.mock import MagicMock, patch

from haywire.ui.graph_canvas.handlers.visual_layer import VisualLayerHandlers
from haywire.ui.graph_canvas.event_definitions import (
    ElementRedrawEvent,
    ElementResetEvent,
    ElementRevalidateEvent,
)
from haywire.ui.graph_canvas.event_handlers import build_event_handler_map
from haywire.core.graph.types import ChangeReason, ValidationResult

pytestmark = pytest.mark.unit


@pytest.fixture
def canvas_vue():
    return MagicMock()


@pytest.fixture
def graph():
    g = MagicMock()
    g.edge_wrappers = {}
    return g


@pytest.fixture
def handler(graph, canvas_vue):
    return VisualLayerHandlers(
        graph=graph,
        editor=MagicMock(),
        skin_factory=MagicMock(),
        canvas_vue=canvas_vue,
    )


# ---------------------------------------------------------------------------
# Initial state
# ---------------------------------------------------------------------------


def test_initial_node_panels_empty(handler):
    assert handler.node_panels == {}


def test_initial_edge_paths_empty(handler):
    assert handler.edge_paths == {}


# ---------------------------------------------------------------------------
# get_edge accessor
# ---------------------------------------------------------------------------


def test_get_edge_returns_registered_edge(handler):
    mock_edge = MagicMock()
    handler.edge_paths["e1"] = mock_edge
    assert handler.get_edge("e1") is mock_edge


def test_get_edge_returns_none_for_unknown_id(handler):
    assert handler.get_edge("does-not-exist") is None


# ---------------------------------------------------------------------------
# on_validated — node added
# ---------------------------------------------------------------------------


def test_on_validated_node_added_calls_add_node_visual(handler, graph):
    wrapper = MagicMock()
    wrapper.node.props.posX = 100.0
    wrapper.node.props.posY = 200.0
    graph.get_node_wrapper.return_value = wrapper

    with patch.object(handler, "add_node_visual") as mock_add:
        result = ValidationResult(
            nodes={"n1": ChangeReason.NODE_ADDED},
            edges={},
            canvas_size=None,
            validation_time_ms=0.0,
        )
        handler.on_validated(result)
        mock_add.assert_called_once_with(wrapper.node, (100.0, 200.0))


def test_on_validated_skips_node_add_if_panel_exists(handler, graph):
    """If node already has a panel, don't add it again."""
    handler.node_panels["n1"] = MagicMock()
    wrapper = MagicMock()
    graph.get_node_wrapper.return_value = wrapper

    with patch.object(handler, "add_node_visual") as mock_add:
        result = ValidationResult(
            nodes={"n1": ChangeReason.NODE_ADDED},
            edges={},
            canvas_size=None,
            validation_time_ms=0.0,
        )
        handler.on_validated(result)
        mock_add.assert_not_called()


# ---------------------------------------------------------------------------
# on_validated — node removed
# ---------------------------------------------------------------------------


def test_on_validated_node_removed_calls_remove_node_visual(handler):
    handler.node_panels["n1"] = MagicMock()

    with patch.object(handler, "remove_node_visual") as mock_remove:
        result = ValidationResult(
            nodes={"n1": ChangeReason.NODE_REMOVED},
            edges={},
            canvas_size=None,
            validation_time_ms=0.0,
        )
        handler.on_validated(result)
        mock_remove.assert_called_once_with("n1")


def test_on_validated_skips_node_remove_if_no_panel(handler):
    with patch.object(handler, "remove_node_visual") as mock_remove:
        result = ValidationResult(
            nodes={"n_missing": ChangeReason.NODE_REMOVED},
            edges={},
            canvas_size=None,
            validation_time_ms=0.0,
        )
        handler.on_validated(result)
        mock_remove.assert_not_called()


# ---------------------------------------------------------------------------
# on_validated — edge added / removed
# ---------------------------------------------------------------------------


def test_on_validated_edge_added_calls_add_edge_visual(handler, graph):
    wrapper = MagicMock()
    graph.get_edge_wrapper.return_value = wrapper

    with patch.object(handler, "add_edge_visual") as mock_add:
        result = ValidationResult(
            nodes={},
            edges={"e1": ChangeReason.EDGE_ADDED},
            canvas_size=None,
            validation_time_ms=0.0,
        )
        handler.on_validated(result)
        mock_add.assert_called_once_with(wrapper)


def test_on_validated_edge_removed_calls_remove_edge_visual(handler):
    handler.edge_paths["e1"] = MagicMock()

    with patch.object(handler, "remove_edge_visual") as mock_remove:
        result = ValidationResult(
            nodes={},
            edges={"e1": ChangeReason.EDGE_REMOVED},
            canvas_size=None,
            validation_time_ms=0.0,
        )
        handler.on_validated(result)
        mock_remove.assert_called_once_with("e1")


# ---------------------------------------------------------------------------
# on_validated — canvas resize
# ---------------------------------------------------------------------------


def test_on_validated_applies_canvas_resize(handler, canvas_vue):
    with patch.object(handler, "_apply_canvas_resize") as mock_resize:
        result = ValidationResult(
            nodes={},
            edges={},
            canvas_size=(1920, 1080),
            validation_time_ms=0.0,
        )
        handler.on_validated(result)
        mock_resize.assert_called_once_with(1920, 1080)


def test_apply_canvas_resize_updates_canvas_and_zoom_container(handler, canvas_vue):
    """Canvas resize propagates to both the canvas and its zoom viewport."""
    zoom_container = MagicMock()
    canvas_vue.zoom_container = zoom_container

    handler._apply_canvas_resize(1920, 1080)

    canvas_vue.set_canvas_size.assert_called_once_with(1920, 1080)
    zoom_container.set_canvas_size.assert_called_once_with(1920, 1080)


def test_on_validated_no_resize_when_canvas_size_none(handler):
    with patch.object(handler, "_apply_canvas_resize") as mock_resize:
        result = ValidationResult(
            nodes={},
            edges={},
            canvas_size=None,
            validation_time_ms=0.0,
        )
        handler.on_validated(result)
        mock_resize.assert_not_called()


# ---------------------------------------------------------------------------
# ElementRedraw / Reset / Revalidate — graph request forwarding
# ---------------------------------------------------------------------------


def test_process_update_element_redraw_calls_graph(handler, graph):
    handler.process_update_element(ElementRedrawEvent(nodes=["n1"], edges=["e1"]))
    graph.request_node_redraw.assert_called_once_with("n1")
    graph.request_edge_redraw.assert_called_once_with("e1")


def test_process_update_element_reset_calls_graph(handler, graph):
    handler.process_update_element(ElementResetEvent(nodes=["n1"], edges=[]))
    graph.request_node_reset.assert_called_once_with("n1")


def test_process_update_element_revalidate_calls_graph(handler, graph):
    handler.process_update_element(ElementRevalidateEvent(nodes=[], edges=["e1"]))
    graph.request_edge_revalidation.assert_called_once_with("e1")


# ---------------------------------------------------------------------------
# Handler registration
# ---------------------------------------------------------------------------


def test_visual_layer_events_are_registered(handler):
    result = build_event_handler_map([handler])
    assert "userRemove" in result
    assert "nodeCreateRequest" in result
    assert "edgeCreated" in result
    assert "elementRedraw" in result
    assert "elementReset" in result
    assert "elementRevalidate" in result
