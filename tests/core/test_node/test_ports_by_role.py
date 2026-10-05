"""Port queries by wire role, and the one check for control crossing a node."""

import pytest

from haywire.core.types import PortType, WireRole

from tests.conftest import make_node

pytestmark = pytest.mark.integration


def test_get_ports_by_role(graph_with_library_system):
    from haybale_testing.nodes.testbed.emit_callback_node import TestEmitCallbackNode

    node = make_node(graph_with_library_system, TestEmitCallbackNode.class_identity.registry_key).node

    sequence = {p.id for p in node.get_ports(is_role=WireRole.SEQUENCE)}
    immediate = {p.id for p in node.get_ports(is_port_type=PortType.INLET, is_role=WireRole.IMMEDIATE)}

    assert sequence == {"execute", "exec"}
    assert immediate == {"edge_callback"}


def test_is_not_role_leaves_out_ports_without_a_wire_type(graph_with_library_system):
    from haybale_testing.nodes.testbed.add_port_test import AddPortTestNode

    node = make_node(graph_with_library_system, AddPortTestNode.class_identity.registry_key).node

    assert node.get_ports(is_not_role=WireRole.DEPENDENT, has_pin=True) == []


def test_has_sequence_pins(graph_with_library_system):
    from haybale_testing.nodes.testbed.emit_callback_node import TestEmitCallbackNode
    from haybale_testing.nodes.testbed.math_op_node import TestAddFloatNode

    graph = graph_with_library_system
    emit = make_node(graph, TestEmitCallbackNode.class_identity.registry_key).node
    add = make_node(graph, TestAddFloatNode.class_identity.registry_key).node

    assert emit.has_sequence_pins()
    assert not add.has_sequence_pins()


def test_a_data_node_whose_only_outlet_is_a_bare_add_slot_is_valid(graph_with_library_system):
    from haybale_testing.nodes.testbed.add_port_test import AddPortTestNode

    wrapper = make_node(graph_with_library_system, AddPortTestNode.class_identity.registry_key)
    graph_with_library_system.force_validation()

    assert wrapper.is_valid()
