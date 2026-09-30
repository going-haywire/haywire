"""What a port holds once the edge driving it is removed, and callbacks passing through reroutes.

The ``xfail(strict=True)`` tests describe the Blender model — an inlet keeps
the value the user gave it while linked and shows it again after unlinking.
Current code keeps the last edge-driven value instead (ADR 0014 §C3,
freeze-on-disconnect). Strict markers turn each into a failure the moment it
starts passing, so the marker is removed with the change that fixes it.
"""

from typing import Any, cast

import pytest

pytestmark = pytest.mark.integration


def _callback_pair(graph):
    """Create an event node and an emit node joined by a direct callback edge."""
    from haybale_testing.nodes.testbed.custom_callback_node import TestCustomCallbackNode
    from haybale_testing.nodes.testbed.emit_callback_node import TestEmitCallbackNode

    event = graph.create_node_wrapper(TestCustomCallbackNode.class_identity.registry_key, position=(0, 0))
    emit = graph.create_node_wrapper(TestEmitCallbackNode.class_identity.registry_key, position=(400, 0))
    edge = graph.create_edge_wrapper(event.node_id, "listen_callback", emit.node_id, "edge_callback")
    return event, emit, edge


def _subscriptions(emit) -> list:
    """Return the event names the emit node would emit to."""
    return list(emit.node.ports["edge_callback"].get_value().values())


def _split_with_reroute(graph, edge_id: str) -> str:
    """Split *edge_id* with a reroute node the way the canvas does, returning the reroute's id."""
    from haywire.barn.builtin.nodes.reroute import RerouteNode
    from haywire.core.undo.actions.graph_actions import SplitEdgeWithRerouteAction

    action = SplitEdgeWithRerouteAction(
        graph=cast(Any, graph),
        edge_id=edge_id,
        position=(200.0, 0.0),
        registry_key=RerouteNode.class_identity.registry_key,
    )
    action._execute_impl()
    reroute_id = action.reroute_node_id
    assert reroute_id is not None
    return reroute_id


@pytest.mark.xfail(
    strict=True,
    raises=AssertionError,
    reason="unlinking keeps the last edge-driven value (ADR 0014 §C3, freeze-on-disconnect)",
)
def test_unlinked_inlet_shows_the_value_it_had_before_linking(graph_with_library_system, library_system):
    from haybale_testing.nodes.testbed.math_op_node import TestAddFloatNode

    graph = graph_with_library_system
    key = TestAddFloatNode.class_identity.registry_key
    source = graph.create_node_wrapper(key, position=(0, 0))
    sink = graph.create_node_wrapper(key, position=(300, 0))
    inlet = sink.node.ports["value_a"]

    inlet.set_value(7.0)  # the user's widget value

    edge = graph.create_edge_wrapper(source.node_id, "result", sink.node_id, "value_a")
    assert edge.state.is_valid()
    source.node.out("result", 42.0)
    assert inlet.get_value() == 42.0  # while linked, the edge drives the inlet

    graph.remove_edge_wrapper(edge.edge_id)

    assert inlet.get_value() == 7.0


@pytest.mark.xfail(
    strict=True,
    raises=AssertionError,
    reason="a promoted inlet's setting cell holds the edge-driven value, and that is what saves (ADR 0014)",
)
def test_linked_promoted_setting_saves_the_users_value(graph_with_library_system, library_system):
    from haybale_testing.nodes.testbed.math_op_node import TestAddFloatNode
    from haywire.core.node.promotion import promote_setting

    graph = graph_with_library_system
    source = graph.create_node_wrapper(TestAddFloatNode.class_identity.registry_key, position=(0, 0))
    sink = graph.create_node_wrapper("haybale-testing:node:SettingsNode", position=(300, 0))
    node = sink.node

    node.example.example_float = 0.25  # the user's setting value
    promote_setting(node, "example", "example_float")
    pid = type(node.example).__dict__["example_float"].storage_key

    edge = graph.create_edge_wrapper(source.node_id, "result", sink.node_id, pid)
    assert edge.state.is_valid()
    source.node.out("result", 0.875)
    node.ports[pid].resolve_dirty_data()
    assert node.example.example_float == 0.875  # while linked, the edge drives the setting

    saved = node._to_dict()
    reloaded = graph.create_node_wrapper("haybale-testing:node:SettingsNode", position=(600, 0)).node
    reloaded._initialize_from_dict(saved)

    assert reloaded.example.example_float == 0.25


def test_direct_callback_edge_subscribes_and_unsubscribes(graph_with_library_system, library_system):
    graph = graph_with_library_system
    event, emit, edge = _callback_pair(graph)
    assert edge.state.is_valid()

    assert _subscriptions(emit) == [event.node.value("listen_callback")]

    graph.remove_edge_wrapper(edge.edge_id)

    assert _subscriptions(emit) == []


def test_callback_through_a_reroute_reaches_the_emit_node(graph_with_library_system, library_system):
    graph = graph_with_library_system
    event, emit, edge = _callback_pair(graph)

    _split_with_reroute(graph, edge.edge_id)

    assert all(e.state.is_valid() for e in graph.edge_wrappers.values())
    assert _subscriptions(emit) == [event.node.value("listen_callback")]


def test_removing_the_edge_before_a_reroute_unsubscribes_the_emit_node(
    graph_with_library_system, library_system
):
    graph = graph_with_library_system
    event, emit, edge = _callback_pair(graph)
    reroute_id = _split_with_reroute(graph, edge.edge_id)
    assert _subscriptions(emit) == [event.node.value("listen_callback")]

    upstream = next(e for e in graph.edge_wrappers.values() if e.sink_node_id == reroute_id)
    graph.remove_edge_wrapper(upstream.edge_id)

    assert _subscriptions(emit) == []


def _record_pair(graph):
    """Create a record event node and a record emit node joined by a direct callback edge."""
    from haybale_testing.nodes.testbed.record_callback_nodes import TestRecordEmitNode, TestRecordEventNode

    event = graph.create_node_wrapper(TestRecordEventNode.class_identity.registry_key, position=(0, 0))
    emit = graph.create_node_wrapper(TestRecordEmitNode.class_identity.registry_key, position=(400, 0))
    edge = graph.create_edge_wrapper(event.node_id, "subscription", emit.node_id, "subscriptions")
    return event, emit, edge


def test_a_displaced_edge_taking_over_keeps_the_emit_node_subscribed(
    graph_with_library_system, library_system
):
    from haybale_testing.nodes.testbed.custom_callback_node import TestCustomCallbackNode

    graph = graph_with_library_system
    first, emit, edge = _callback_pair(graph)
    reroute_id = _split_with_reroute(graph, edge.edge_id)
    second = graph.create_node_wrapper(TestCustomCallbackNode.class_identity.registry_key, position=(0, 200))
    newer = graph.create_edge_wrapper(second.node_id, "listen_callback", reroute_id, "in")
    assert _subscriptions(emit) == [second.node.value("listen_callback")]
    seen: list = []
    emit.node.ports["edge_callback"].data.add_observer(lambda change: seen.append(change.value))

    graph.remove_edge_wrapper(newer.edge_id)

    assert _subscriptions(emit) == [first.node.value("listen_callback")]
    assert all(seen), "the emit node's pool went empty while the displaced edge took over"


def test_a_dataclass_subscription_passes_through_a_reroute(graph_with_library_system, library_system):
    graph = graph_with_library_system
    event, emit, edge = _record_pair(graph)

    _split_with_reroute(graph, edge.edge_id)

    records = list(emit.node.ports["subscriptions"].get_value().values())
    assert [record.name for record in records] == [event.node_id]


def test_removing_the_edge_before_a_reroute_drops_a_dataclass_subscription(
    graph_with_library_system, library_system
):
    graph = graph_with_library_system
    _event, emit, edge = _record_pair(graph)
    reroute_id = _split_with_reroute(graph, edge.edge_id)
    upstream = next(e for e in graph.edge_wrappers.values() if e.sink_node_id == reroute_id)

    graph.remove_edge_wrapper(upstream.edge_id)

    assert emit.node.ports["subscriptions"].get_value() == {}


def test_a_graph_holding_an_absent_callback_saves_and_loads(graph_with_library_system, library_system):
    graph = graph_with_library_system
    _event, _emit, edge = _callback_pair(graph)
    reroute_id = _split_with_reroute(graph, edge.edge_id)
    upstream = next(e for e in graph.edge_wrappers.values() if e.sink_node_id == reroute_id)
    graph.remove_edge_wrapper(upstream.edge_id)
    data = graph.to_dict()

    graph.clear()
    graph.load_from_dict(data)

    assert graph.node_wrappers[reroute_id].node.ports["out"].get_value() is None
