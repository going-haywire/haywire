"""A port's immediacy and link limits come from its wire type, never from a saved flow."""

import pytest

from tests.conftest import make_node

pytestmark = pytest.mark.integration


def test_a_saved_flow_is_ignored_on_load(graph_with_library_system):
    from haybale_testing.nodes.testbed.add_float_probe import AddFloatProbeNode

    from haywire.barn.builtin.wires import DataWire

    graph = graph_with_library_system
    node = make_node(graph, AddFloatProbeNode.class_identity.registry_key)
    data = graph.to_dict()
    ports = data["nodes"][node.node_id]["node_data"]["ports"]
    for spec in ports.values():
        spec["kwargs"]["flow_type"] = "callback"

    graph.clear()
    graph.load_from_dict(data)
    port = graph.node_wrappers[node.node_id].node.ports["value_a"]

    assert port.wire_type.id == DataWire.id
    assert not port.is_immediate
    # Every port, not just one: the saved flow is ignored across the whole node.
    for loaded in graph.node_wrappers[node.node_id].node.ports.values():
        assert loaded.wire_type is not None
        assert loaded.wire_type.id == DataWire.id
        assert not loaded.is_immediate


def test_a_config_port_of_a_callback_type_is_not_immediate(graph_with_library_system):
    from haybale_testing.nodes.testbed.callback_emit_probe import CallbackEmitProbeNode

    node = make_node(graph_with_library_system, CallbackEmitProbeNode.class_identity.registry_key).node
    configs = [p for p in node.ports.values() if p.is_config()]

    assert configs
    assert not any(p.is_immediate for p in configs)


def test_link_limits_follow_the_role(graph_with_library_system):
    from haybale_testing.nodes.testbed.add_port_probe import AddPortProbeNode
    from haybale_testing.nodes.testbed.callback_emit_probe import CallbackEmitProbeNode
    from haybale_testing.nodes.testbed.add_float_probe import AddFloatProbeNode

    graph = graph_with_library_system
    add = make_node(graph, AddFloatProbeNode.class_identity.registry_key).node
    emit = make_node(graph, CallbackEmitProbeNode.class_identity.registry_key).node
    slots = make_node(graph, AddPortProbeNode.class_identity.registry_key).node

    assert add.ports["result"].takes_many_links is True
    assert add.ports["value_a"].takes_many_links is False
    assert emit.ports["exec"].takes_many_links is False
    assert emit.ports["execute"].takes_many_links is True
    assert emit.ports["edge_callback"].takes_many_links is True
    # A bare ADD outlet slot keeps a data outlet's limit, as before.
    assert slots.ports["add_out_0"].takes_many_links is True

    from haybale_testing.nodes.testbed.callback_event_probe import CallbackEventProbeNode

    listener = make_node(graph, CallbackEventProbeNode.class_identity.registry_key).node
    assert listener.ports["listen_callback"].takes_many_links is True


def test_a_retyped_port_answers_its_new_wire_type(graph_with_library_system):
    from haybale_testing.nodes.testbed.add_float_probe import AddFloatProbeNode

    from haywire.barn.builtin.types import EXEC
    from haywire.barn.builtin.wires import ControlWire, DataWire

    node = make_node(graph_with_library_system, AddFloatProbeNode.class_identity.registry_key).node
    assert node.ports["value_a"].wire_key == DataWire.id

    with node.rejig(include=["value_a"]):
        node.add(EXEC.as_inlet("value_a"))

    port = node.ports["value_a"]
    assert port.type_cls is EXEC
    assert port.wire_type is not None
    assert port.wire_type.id == ControlWire.id
    assert port.wire_key == ControlWire.id
    assert port.has_role(ControlWire.role)
    assert not port.has_role(DataWire.role)


def test_a_refreshed_port_rederives_when_it_becomes_a_config_port(graph_with_library_system):
    from haybale_testing.nodes.testbed.add_float_probe import AddFloatProbeNode

    from haywire.barn.builtin.types import FLOAT

    node = make_node(graph_with_library_system, AddFloatProbeNode.class_identity.registry_key).node
    original = node.ports["value_a"]
    assert original.wire_type is not None

    with node.rejig(include=["value_a"]):
        node.add(FLOAT.as_config("value_a"))

    assert node.ports["value_a"] is original
    assert original.is_config()
    assert original.wire_type is None
    assert original.wire_key is None
