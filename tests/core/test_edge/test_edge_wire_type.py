"""An edge's wire type comes from its ports, and nothing about it is saved."""

import pytest

from haywire.core.graph.subgraph import SubgraphDefinition

from tests.conftest import make_node

pytestmark = pytest.mark.integration

_ADD = "haybale-testing:node:TestAddFloatNode"
_INPUT = "haywire-core:node:SubgraphInputNode"
_EMIT = "haybale-testing:node:TestEmitCallbackNode"


def test_a_data_edge_carries_its_outlets_wire_type(graph_with_library_system):
    from haywire.barn.builtin.wires import DataWire

    graph = graph_with_library_system
    source, sink = make_node(graph, _ADD), make_node(graph, _ADD)
    edge = graph.create_edge_wrapper(source.node_id, "result", sink.node_id, "value_a")

    assert edge.wire_type.id == DataWire.id


def test_an_edge_out_of_a_bare_add_slot_carries_what_it_feeds(graph_with_library_system):
    from haywire.barn.builtin.wires import CallbackWire

    definition = graph_with_library_system.add_subgraph(SubgraphDefinition(key="sg_wire", label="G"))
    input_node = make_node(definition, _INPUT)
    emitter = make_node(definition, _EMIT)
    slot = next(p for p in input_node.node.ports.values() if p.id.startswith("slot_"))
    edge = definition.create_edge_wrapper(input_node.node_id, slot.id, emitter.node_id, "edge_callback")

    assert edge.wire_type.id == CallbackWire.id


def test_ports_on_different_wire_types_do_not_link(graph_with_library_system):
    graph = graph_with_library_system
    emit, add = make_node(graph, _EMIT), make_node(graph, _ADD)
    edge = graph.create_edge_wrapper(emit.node_id, "exec", add.node_id, "value_a")

    assert not edge.state.is_formally_validated
    assert "Wire type mismatch" in edge.state.get_error().message


def test_an_edge_with_a_missing_outlet_is_kept_and_takes_its_inlets_wire_type(graph_with_library_system):
    from haywire.barn.builtin.wires import DataWire

    graph = graph_with_library_system
    source, sink = make_node(graph, _ADD), make_node(graph, _ADD)
    edge = graph.create_edge_wrapper(source.node_id, "gone", sink.node_id, "value_a")

    assert edge is not None
    assert not edge.state.is_valid()
    assert edge.wire_type.id == DataWire.id


def test_an_edge_saves_no_wire_type_and_ignores_a_saved_edge_type(graph_with_library_system):
    from haywire.barn.builtin.wires import DataWire

    graph = graph_with_library_system
    source, sink = make_node(graph, _ADD), make_node(graph, _ADD)
    edge = graph.create_edge_wrapper(source.node_id, "result", sink.node_id, "value_a")
    data = graph.to_dict()
    assert "edge_type" not in data["edges"][edge.edge_id]

    data["edges"][edge.edge_id]["edge_type"] = "not-a-real-flow-type"
    graph.clear()
    graph.load_from_dict(data)

    graph.force_validation()
    assert graph.get_edge_wrapper(edge.edge_id) is not None
    assert graph.get_edge_wrapper(edge.edge_id).wire_type.id == DataWire.id
