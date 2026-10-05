"""An edge's visual state: where its computed head sits, and no hard-coded state colour."""

import pytest

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
