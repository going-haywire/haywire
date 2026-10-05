"""A port's immediacy and link limits come from its wire type, never from a saved flow."""

import pytest

from tests.conftest import make_node

pytestmark = pytest.mark.integration


def test_a_saved_flow_is_ignored_on_load(graph_with_library_system):
    from haybale_testing.nodes.testbed.math_op_node import TestAddFloatNode

    from haywire.barn.builtin.wires import DataWire

    graph = graph_with_library_system
    node = make_node(graph, TestAddFloatNode.class_identity.registry_key)
    data = graph.to_dict()
    ports = data["nodes"][node.node_id]["node_data"]["ports"]
    for spec in ports.values():
        spec["kwargs"]["flow_type"] = "callback"

    graph.clear()
    graph.load_from_dict(data)
    port = graph.node_wrappers[node.node_id].node.ports["value_a"]

    assert port.wire_type.id == DataWire.id
    assert not port.is_immediate


def test_a_config_port_of_a_callback_type_is_not_immediate(graph_with_library_system):
    from haybale_testing.nodes.testbed.emit_callback_node import TestEmitCallbackNode

    node = make_node(graph_with_library_system, TestEmitCallbackNode.class_identity.registry_key).node
    configs = [p for p in node.ports.values() if p.is_config()]

    assert configs
    assert not any(p.is_immediate for p in configs)


def test_link_limits_follow_the_role(graph_with_library_system):
    from haybale_testing.nodes.testbed.add_port_test import AddPortTestNode
    from haybale_testing.nodes.testbed.emit_callback_node import TestEmitCallbackNode
    from haybale_testing.nodes.testbed.math_op_node import TestAddFloatNode

    graph = graph_with_library_system
    add = make_node(graph, TestAddFloatNode.class_identity.registry_key).node
    emit = make_node(graph, TestEmitCallbackNode.class_identity.registry_key).node
    slots = make_node(graph, AddPortTestNode.class_identity.registry_key).node

    assert add.ports["result"].allow_multiple_links is True
    assert add.ports["value_a"].allow_multiple_links is False
    assert emit.ports["exec"].allow_multiple_links is False
    assert emit.ports["execute"].allow_multiple_links is True
    assert emit.ports["edge_callback"].allow_multiple_links is True
    # A bare ADD outlet slot keeps a data outlet's limit, as before.
    assert slots.ports["add_out_0"].allow_multiple_links is True
