"""An edge's visual state: where its computed head sits, and no hard-coded state colour."""

import pytest

from haywire.core.edge.arrow_heads import DEFAULT_HEAD_SIZE

from haybale_graph_editor.editors.graph_canvas.ui_edge import edge_visual_state
from tests.conftest import make_edge, make_node

pytestmark = pytest.mark.integration


def test_a_data_edge_draws_its_head_at_the_inlet(graph_with_library_system):
    from haybale_testing.nodes.testbed.math_op_node import TestAddFloatNode

    graph = graph_with_library_system
    key = TestAddFloatNode.class_identity.registry_key
    source, sink = make_node(graph, key), make_node(graph, key)
    edge = make_edge(graph, source.node_id, "result", sink.node_id, "value_a")
    graph.force_validation()

    assert edge_visual_state(edge).arrow_at == "inlet"


def test_a_callback_edge_draws_its_head_at_the_outlet(graph_with_library_system):
    from haybale_testing.nodes.testbed.custom_callback_node import TestCustomCallbackNode
    from haybale_testing.nodes.testbed.emit_callback_node import TestEmitCallbackNode

    graph = graph_with_library_system
    listener = make_node(graph, TestCustomCallbackNode.class_identity.registry_key)
    emitter = make_node(graph, TestEmitCallbackNode.class_identity.registry_key)
    edge = make_edge(graph, listener.node_id, "listen_callback", emitter.node_id, "edge_callback")
    graph.force_validation()

    assert edge_visual_state(edge).arrow_at == "outlet"


def test_an_invalid_edge_leaves_its_colour_to_the_theme(graph_with_library_system):
    from haybale_testing.nodes.testbed.add_port_test import AddPortTestNode

    graph = graph_with_library_system
    key = AddPortTestNode.class_identity.registry_key
    source, sink = make_node(graph, key), make_node(graph, key)
    edge = graph.create_edge_wrapper(source.node_id, "add_out_0", sink.node_id, "add_in_0")
    assert edge is not None
    graph._validation.force_immediate_validation()

    state = edge_visual_state(edge)
    assert state.is_valid is False
    assert state.stroke_color == "auto"


def _styled_edge(graph, **values):
    """A visual edge on the test wire, its style bag holding *values*."""
    from haybale_testing.nodes.testbed.visual_probe import VisualProbeNode

    key = VisualProbeNode.class_identity.registry_key
    source, sink = make_node(graph, key), make_node(graph, key)
    edge = make_edge(graph, source.node_id, "note_out", sink.node_id, "note_in", style=values)
    graph.force_validation()
    return edge


def test_a_computed_edge_has_no_style(graph_with_library_system):
    from haybale_testing.nodes.testbed.math_op_node import TestAddFloatNode

    graph = graph_with_library_system
    key = TestAddFloatNode.class_identity.registry_key
    source, sink = make_node(graph, key), make_node(graph, key)
    edge = make_edge(graph, source.node_id, "result", sink.node_id, "value_a")
    graph.force_validation()

    state = edge_visual_state(edge)
    assert state.style == {}
    assert state.stroke_color == "auto"


def test_a_declared_colour_and_dash_replace_gradient_and_chain_dash(graph_with_library_system):
    state = edge_visual_state(_styled_edge(graph_with_library_system, color="#ff0000", dash="dotted"))
    assert state.stroke_color == "#ff0000"
    assert state.stroke_dasharray == "2,4"


def test_declared_width_and_heads_go_to_the_canvas_style(graph_with_library_system):
    edge = _styled_edge(graph_with_library_system, width=5.0, arrow_start="open", arrow_end_size="l")
    assert edge_visual_state(edge).style == {
        "width": 5.0,
        "arrowStart": "open",
        "arrowEnd": "arrow",
        "arrowStartSize": DEFAULT_HEAD_SIZE,
        "arrowEndSize": "l",
    }


def test_an_unknown_dash_keeps_the_chain_dash(graph_with_library_system):
    from haybale_graph_editor.editors.graph_canvas.ui_edge import calculate_dasharray

    edge = _styled_edge(graph_with_library_system, dash="wavy")
    assert edge_visual_state(edge).stroke_dasharray == calculate_dasharray(0)


def test_the_warning_state_keeps_its_dash_and_takes_the_colour(graph_with_library_system, monkeypatch):
    edge = _styled_edge(graph_with_library_system, color="#ff0000", dash="dotted")
    monkeypatch.setattr(type(edge.state), "has_warning", lambda self: True)

    state = edge_visual_state(edge)
    assert state.has_warning is True
    assert state.stroke_color == "#ff0000"
    assert state.stroke_dasharray == "2,2,2,2,2,5,5,5,5,5,5,5"


def test_a_style_change_alone_is_a_visual_change(graph_with_library_system):
    edge = _styled_edge(graph_with_library_system)
    before = edge_visual_state(edge)
    assert edge.style is not None
    edge.style.arrow_end = "bar"
    assert edge_visual_state(edge) != before
