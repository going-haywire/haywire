"""Collapse and expand carry a callback edge across a Group's boundary (ADR 0041).

The subscription relays through the card at wiring time, so collapsing either
end keeps the emitter subscribed; removing the edge on either side of the card
unsubscribes, and undo or expand restores the direct edge.
"""

from __future__ import annotations

import pytest

from haywire.core.graph.base import BaseGraph
from haywire.core.undo.actions.graph_actions import CollapseToGraphNodeAction

from tests.conftest import make_node
from tests.core.test_graph.callback_group import subscriptions

pytestmark = [pytest.mark.integration]

_LISTEN = "haybale-testing:node:TestCustomCallbackNode"
_EMIT = "haybale-testing:node:TestEmitCallbackNode"
_PRINT = "haybale-testing:node:TestPrintNode"
_INPUT = "haywire-core:node:SubgraphInputNode"
_OUTPUT = "haywire-core:node:SubgraphOutputNode"
_CARD = "haywire-core:node:GraphNode"


def _collapse(graph: BaseGraph, node_ids, label: str = "Group") -> CollapseToGraphNodeAction:
    action = CollapseToGraphNodeAction(
        graph=graph,
        node_ids=list(node_ids),
        card_registry_key=_CARD,
        input_registry_key=_INPUT,
        output_registry_key=_OUTPUT,
        label=label,
    )
    action.execute()
    return action


def _find(graph, node_id):
    """The wrapper for ``node_id`` anywhere in the graph tree."""
    wrapper = graph.get_node_wrapper(node_id)
    if wrapper is not None:
        return wrapper
    for definition in graph.subgraphs.values():
        found = _find(definition, node_id)
        if found is not None:
            return found
    return None


def _subs(graph, emitter_id) -> list:
    return subscriptions(_find(graph, emitter_id))


@pytest.fixture
def listener_and_emitter(graph_with_library_system: BaseGraph):
    """An event node wired to a callback consumer, both in the host graph."""
    graph = graph_with_library_system
    listener = make_node(graph, _LISTEN)
    emitter = make_node(graph, _EMIT)
    graph.create_edge_wrapper(listener.node_id, "listen_callback", emitter.node_id, "edge_callback")
    graph.force_validation()
    return graph, listener, emitter


class TestCollapsingAcrossACallback:
    def test_collapsing_the_emitter_keeps_it_subscribed(self, listener_and_emitter):
        graph, listener, emitter = listener_and_emitter
        name = listener.node.value("listen_callback")

        _collapse(graph, [emitter.node_id])

        assert _subs(graph, emitter.node_id) == [name]

    def test_collapsing_a_reroute_on_the_path_keeps_the_emitter_subscribed(self, listener_and_emitter):
        """A listener cannot sit inside a Subgraph, so a subscription crosses outward on its way through."""
        from tests.core.test_edge.test_disconnect_semantics import _split_with_reroute

        graph, listener, emitter = listener_and_emitter
        edge = next(e for e in graph.edge_wrappers.values() if e.sink_node_id == emitter.node_id)
        reroute_id = _split_with_reroute(graph, edge.edge_id)

        _collapse(graph, [reroute_id])

        assert _subs(graph, emitter.node_id) == [listener.node.value("listen_callback")]

    def test_removing_the_outer_edge_after_collapse_unsubscribes(self, listener_and_emitter):
        graph, _listener, emitter = listener_and_emitter
        action = _collapse(graph, [emitter.node_id])
        outer = next(e for e in graph.edge_wrappers.values() if e.sink_node_id == action.card_node_id)

        graph.remove_edge_wrapper(outer.edge_id)

        assert _subs(graph, emitter.node_id) == []

    def test_removing_an_inner_edge_of_a_collapsed_reroute_unsubscribes(self, listener_and_emitter):
        from tests.core.test_edge.test_disconnect_semantics import _split_with_reroute

        graph, _listener, emitter = listener_and_emitter
        edge = next(e for e in graph.edge_wrappers.values() if e.sink_node_id == emitter.node_id)
        reroute_id = _split_with_reroute(graph, edge.edge_id)
        action = _collapse(graph, [reroute_id])
        definition = graph.get_subgraph(action.subgraph_key)
        inner = next(e for e in definition.edge_wrappers.values() if e.sink_node_id == reroute_id)

        definition.remove_edge_wrapper(inner.edge_id)

        assert _subs(graph, emitter.node_id) == []

    def test_undo_restores_the_direct_subscription(self, listener_and_emitter):
        graph, listener, emitter = listener_and_emitter
        action = _collapse(graph, [emitter.node_id])

        action.undo()

        assert _subs(graph, emitter.node_id) == [listener.node.value("listen_callback")]

    def test_expand_restores_the_direct_subscription(self, listener_and_emitter):
        from haywire.core.undo.actions.graph_actions import ExpandGraphNodeAction

        graph, listener, emitter = listener_and_emitter
        action = _collapse(graph, [emitter.node_id])

        ExpandGraphNodeAction(graph=graph, node_id=action.card_node_id).execute()

        assert graph.subgraphs == {}
        assert _subs(graph, emitter.node_id) == [listener.node.value("listen_callback")]


class TestWhatIsStillAllowed:
    def test_collapsing_both_ends_together_keeps_the_edge_internal(self, listener_and_emitter):
        graph, listener, emitter = listener_and_emitter

        action = _collapse(graph, [listener.node_id, emitter.node_id])

        definition = graph.get_subgraph(action.subgraph_key)
        callbacks = [
            e
            for e in definition.edge_wrappers.values()
            if e.source_node_id == listener.node_id and e.sink_node_id == emitter.node_id
        ]
        assert len(callbacks) == 1

    def test_a_selection_with_no_callback_edge_is_unaffected(self, graph_with_library_system):
        graph = graph_with_library_system
        a, b = make_node(graph, _PRINT), make_node(graph, _PRINT)
        graph.create_edge_wrapper(a.node_id, "done", b.node_id, "exec")
        graph.force_validation()

        action = _collapse(graph, [a.node_id, b.node_id])

        assert graph.get_subgraph(action.subgraph_key) is not None


def test_a_subscription_crosses_two_nested_cards(listener_and_emitter):
    graph, listener, emitter = listener_and_emitter
    name = listener.node.value("listen_callback")
    inner = _collapse(graph, [emitter.node_id], label="Inner")

    outer = _collapse(graph, [inner.card_node_id], label="Outer")

    assert _subs(graph, emitter.node_id) == [name]
    edge = next(e for e in graph.edge_wrappers.values() if e.sink_node_id == outer.card_node_id)
    graph.remove_edge_wrapper(edge.edge_id)
    assert _subs(graph, emitter.node_id) == []
