"""``setting[ArrayType[T]]`` — a setting that holds a list.

Pins the paths a list setting shares with every other setting: the cell, the
node's save/load, reset, promotion to each direction, a graph round trip, an
edge between promoted ports, and demotion. ``SettingsNode.example`` carries one
list field per tested item type.
"""

import pytest

from haywire.barn.builtin.types import STRING
from haywire.core.graph.base import BaseGraph
from haywire.core.node.promotion import demote_setting, promote_setting
from haywire.core.types.enums import PortType

pytestmark = pytest.mark.integration

SETTINGS_NODE = "haybale-testing:node:SettingsNode"
DEFAULT_STRINGS = ["One", "Two", "Three"]


def _node(graph: BaseGraph, x: float = 0):
    wrapper = graph.create_node_wrapper(SETTINGS_NODE, position=(x, 0))
    assert wrapper is not None, "SettingsNode creation failed"
    return wrapper


def _desc(node, field: str):
    return type(node.example).__dict__[field]


def _promote(node, field: str, direction: PortType) -> str:
    promote_setting(node, "example", field, direction=direction)
    return _desc(node, field).storage_key


def test_an_array_setting_reads_a_copy(graph_with_library_system):
    node = _node(graph_with_library_system).node
    read = node.example.example_string_list
    read.append("Four")
    assert node.example.example_string_list == DEFAULT_STRINGS


def test_two_nodes_never_share_a_list(graph_with_library_system):
    first = _node(graph_with_library_system, 0).node
    second = _node(graph_with_library_system, 100).node

    first.example.example_string_list = ["A"]
    assert second.example.example_string_list == DEFAULT_STRINGS

    first.example._reset("example_string_list")
    assert first.example.example_string_list == DEFAULT_STRINGS
    assert second.example.example_string_list == DEFAULT_STRINGS


def test_an_array_setting_round_trips_with_the_node(graph_with_library_system):
    graph = graph_with_library_system
    node = _node(graph, 0).node
    node.example.example_string_list = ["A", "B"]
    node.example.example_int_list = [4, 5]

    fresh = _node(graph, 100).node
    fresh._initialize_from_dict(node._to_dict())

    assert fresh.example.example_string_list == ["A", "B"]
    assert fresh.example.example_int_list == [4, 5]
    assert all(type(item) is int for item in fresh.example.example_int_list)


def test_a_default_list_saves_no_value(graph_with_library_system):
    node = _node(graph_with_library_system).node
    values = node._to_dict()["settings"]["example"]["values"]
    for field in ("example_string_list", "example_int_list", "example_float_list"):
        assert _desc(node, field).storage_key not in values
        assert field not in values


def test_a_promoted_list_port_carries_the_array_type(graph_with_library_system):
    from haybale_core.types import ArrayType

    node = _node(graph_with_library_system).node
    pid = _promote(node, "example_string_list", PortType.INLET)

    port = node.ports[pid]
    assert port.type_cls is ArrayType[STRING]
    assert port._data is node.example._cell_for(_desc(node, "example_string_list"))
    assert port.get_value() == DEFAULT_STRINGS


def test_a_promoted_list_survives_a_graph_round_trip(graph_with_library_system):
    graph = graph_with_library_system
    wrapper = _node(graph)
    pid = _promote(wrapper.node, "example_string_list", PortType.INLET)
    wrapper.node.example.example_string_list = ["A"]

    data = graph.to_dict()
    graph.clear()
    graph.load_from_dict(data)

    reloaded = graph.node_wrappers[wrapper.node_id].node
    assert pid in reloaded.ports
    assert reloaded.ports[pid].promoted is True
    assert reloaded.example.example_string_list == ["A"]
    assert reloaded.ports[pid].get_value() == ["A"]


@pytest.mark.parametrize(
    ("field", "value"),
    [("example_string_list", ["X", "Y"]), ("example_float_list", [2.5, 3.5])],
)
def test_a_list_flows_over_an_edge_between_promoted_ports(graph_with_library_system, field, value):
    graph = graph_with_library_system
    src = _node(graph, 0)
    sink = _node(graph, 200)
    pid = _promote(src.node, field, PortType.OUTLET)
    _promote(sink.node, field, PortType.INLET)

    edge = graph.create_edge_wrapper(src.node_id, pid, sink.node_id, pid)
    assert edge is not None
    assert edge.state.is_valid()

    setattr(src.node.example, field, value)
    sink_port = sink.node.ports[pid]
    sink_port.resolve_dirty_data()
    assert sink_port.get_value() == value


def test_demoting_a_list_keeps_its_value(graph_with_library_system):
    node = _node(graph_with_library_system).node
    pid = _promote(node, "example_string_list", PortType.INLET)
    node.example.example_string_list = ["A"]

    demote_setting(node, pid)

    assert pid not in node.ports
    assert node.example.example_string_list == ["A"]


def test_a_list_promotes_to_config(graph_with_library_system):
    node = _node(graph_with_library_system).node
    pid = _promote(node, "example_int_list", PortType.CONFIG)
    assert node.ports[pid].is_config()
    assert node.ports[pid].get_value() == [1, 2, 3]
