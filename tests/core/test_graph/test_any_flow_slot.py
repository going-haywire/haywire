"""A boundary node's growing slot grows a port of whatever flow connects to it (ADR 0041)."""

import pytest

from haywire.core.graph.subgraph import SubgraphDefinition
from haywire.core.types import FlowType, Propagation

from tests.conftest import make_node

pytestmark = pytest.mark.integration

_INPUT = "haywire-core:node:SubgraphInputNode"
_OUTPUT = "haywire-core:node:SubgraphOutputNode"
_LISTEN = "haybale-testing:node:TestCustomCallbackNode"
_EMIT = "haybale-testing:node:TestEmitCallbackNode"
_BEGIN = "haybale-testing:node:TestBeginPlayNode"


def _slot(wrapper):
    return next(p for p in wrapper.node.ports.values() if p.id.startswith("slot_"))


@pytest.fixture
def definition(graph_with_library_system):
    return graph_with_library_system.add_subgraph(SubgraphDefinition(key="sg_any", label="G"))


def test_a_control_edge_into_the_output_slot_grows_a_control_inlet(definition):
    output_node = make_node(definition, _OUTPUT)
    begin = make_node(definition, _BEGIN)
    slot = _slot(output_node)

    edge = definition.create_edge_wrapper(begin.node_id, "exec", output_node.node_id, slot.id)
    definition.force_validation()

    assert edge.state.is_valid()
    assert output_node.node.ports[slot.id].flow_type is FlowType.CONTROL


def test_a_callback_edge_into_the_output_slot_grows_a_callback_inlet(definition):
    output_node = make_node(definition, _OUTPUT)
    listener = make_node(definition, _LISTEN)
    slot = _slot(output_node)

    edge = definition.create_edge_wrapper(listener.node_id, "listen_callback", output_node.node_id, slot.id)
    definition.force_validation()

    assert edge.state.is_valid()
    assert output_node.node.ports[slot.id].flow_type is FlowType.CALLBACK


def test_an_edge_out_of_the_input_slot_takes_the_inlets_flow(definition):
    input_node = make_node(definition, _INPUT)
    emitter = make_node(definition, _EMIT)
    slot = _slot(input_node)

    edge = definition.create_edge_wrapper(input_node.node_id, slot.id, emitter.node_id, "edge_callback")
    definition.force_validation()

    assert edge.edge_type is FlowType.CALLBACK
    assert edge.propagation is Propagation.IMMEDIATE
    assert input_node.node.ports[slot.id].flow_type is FlowType.CALLBACK
