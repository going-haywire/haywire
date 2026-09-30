"""A subscription crosses a Group's boundary at wiring time, and unlinking either side unsubscribes."""

import pytest

from tests.conftest import make_node
from tests.core.test_graph.callback_group import EMIT, LISTEN, build_group, subscriptions

pytestmark = pytest.mark.integration


@pytest.fixture
def inward(graph_with_library_system):
    """A listener outside subscribed, through the card, to an emitter inside."""
    group = build_group(graph_with_library_system)
    emitter = make_node(group.definition, EMIT)
    group.definition.create_edge_wrapper(
        group.input_node.node_id, "sub_in", emitter.node_id, "edge_callback"
    )
    listener = make_node(group.graph, LISTEN)
    outer = group.graph.create_edge_wrapper(
        listener.node_id, "listen_callback", group.card.node_id, "in_sub_in"
    )
    return group, listener, emitter, outer


@pytest.fixture
def through(graph_with_library_system):
    """A listener and an emitter outside, the subscription passing through the Group.

    A listener cannot sit inside a Subgraph (containment rules out EVENT nodes), so
    a subscription crosses outward only on its way through.
    """
    group = build_group(graph_with_library_system)
    inner = group.definition.create_edge_wrapper(
        group.input_node.node_id, "sub_in", group.output_node.node_id, "sub_out"
    )
    listener = make_node(group.graph, LISTEN)
    group.graph.create_edge_wrapper(listener.node_id, "listen_callback", group.card.node_id, "in_sub_in")
    emitter = make_node(group.graph, EMIT)
    group.graph.create_edge_wrapper(group.card.node_id, "out_sub_out", emitter.node_id, "edge_callback")
    return group, listener, emitter, inner


class TestInward:
    def test_the_emitter_inside_hears_the_listener_outside(self, inward):
        _group, listener, emitter, _outer = inward

        assert subscriptions(emitter) == [listener.node.value("listen_callback")]

    def test_removing_the_outer_edge_unsubscribes(self, inward):
        group, _listener, emitter, outer = inward

        group.graph.remove_edge_wrapper(outer.edge_id)

        assert subscriptions(emitter) == []

    def test_the_card_inlet_relays(self, inward):
        from haywire.core.graph.subgraph_crossing import RELAY_HANDLER

        group, _listener, _emitter, _outer = inward

        assert group.card.node.ports["in_sub_in"].on_change == RELAY_HANDLER


class TestThrough:
    def test_the_emitter_outside_hears_the_listener_outside(self, through):
        _group, listener, emitter, _inner = through

        assert subscriptions(emitter) == [listener.node.value("listen_callback")]

    def test_removing_the_inner_edge_unsubscribes(self, through):
        group, _listener, emitter, inner = through

        group.definition.remove_edge_wrapper(inner.edge_id)

        assert subscriptions(emitter) == []


class TestGrowing:
    def test_a_callback_grown_into_the_output_relays_and_takes_no_default(self, graph_with_library_system):
        from haywire.core.graph.subgraph_crossing import RELAY_HANDLER

        group = build_group(graph_with_library_system)
        slot = next(p for p in group.output_node.node.ports.values() if p.id.startswith("slot_"))

        group.definition.create_edge_wrapper(
            group.input_node.node_id, "sub_in", group.output_node.node_id, slot.id
        )
        group.definition.force_validation()

        grown = group.output_node.node.ports[slot.id]
        assert grown.on_change == RELAY_HANDLER
        assert grown.data.get_own_value() == ""
