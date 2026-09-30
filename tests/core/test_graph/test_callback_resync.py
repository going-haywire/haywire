"""Whenever a card and its interior meet, their immediate ports agree."""

import pytest

from tests.conftest import make_node
from tests.core.test_graph.callback_group import (
    EMIT,
    LISTEN,
    add_card,
    build_group,
    build_interior,
    subscriptions,
)

pytestmark = pytest.mark.integration


def test_a_card_placed_after_the_interior_is_wired_relays_through_it(graph_with_library_system):
    group = build_interior(graph_with_library_system)
    group.definition.create_edge_wrapper(
        group.input_node.node_id, "sub_in", group.output_node.node_id, "sub_out"
    )

    add_card(group)
    listener = make_node(group.graph, LISTEN)
    group.graph.create_edge_wrapper(listener.node_id, "listen_callback", group.card.node_id, "in_sub_in")
    emitter = make_node(group.graph, EMIT)
    group.graph.create_edge_wrapper(group.card.node_id, "out_sub_out", emitter.node_id, "edge_callback")

    assert subscriptions(emitter) == [listener.node.value("listen_callback")]


def test_a_subscription_through_a_group_survives_save_and_load(graph_with_library_system):
    group = build_group(graph_with_library_system)
    group.definition.create_edge_wrapper(
        group.input_node.node_id, "sub_in", group.output_node.node_id, "sub_out"
    )
    listener = make_node(group.graph, LISTEN)
    group.graph.create_edge_wrapper(listener.node_id, "listen_callback", group.card.node_id, "in_sub_in")
    emitter = make_node(group.graph, EMIT)
    group.graph.create_edge_wrapper(group.card.node_id, "out_sub_out", emitter.node_id, "edge_callback")
    name = listener.node.value("listen_callback")
    data = group.graph.to_dict()

    group.graph.clear()
    group.graph.load_from_dict(data)

    assert subscriptions(group.graph.node_wrappers[emitter.node_id]) == [name]


def test_a_reconcile_pushes_the_cards_subscription_into_a_reset_interior(graph_with_library_system):
    group = build_group(graph_with_library_system)
    emitter = make_node(group.definition, EMIT)
    group.definition.create_edge_wrapper(
        group.input_node.node_id, "sub_in", emitter.node_id, "edge_callback"
    )
    listener = make_node(group.graph, LISTEN)
    group.graph.create_edge_wrapper(listener.node_id, "listen_callback", group.card.node_id, "in_sub_in")
    group.input_node.node.ports["sub_in"].set_value("")  # as a rebuilt interior starts
    assert subscriptions(emitter) == []

    group.card.node.reconcile_interface()

    assert subscriptions(emitter) == [listener.node.value("listen_callback")]
