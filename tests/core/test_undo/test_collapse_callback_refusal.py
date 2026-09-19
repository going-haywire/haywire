"""Collapse refuses a selection a callback edge would cross.

A callback edge carries its subscription as a port value, read from the sink's
pool. No boundary node can relay it — the copy re-keys the pool entry by its
own edge, so unlinking the outer edge leaves the interior subscribed to a
listener that is gone. Collapsing across one would build a Group that can
never work, so the action refuses before it mints an interface.
"""

from __future__ import annotations

import pytest

from haywire.core.graph.base import BaseGraph
from haywire.core.undo.actions.graph_actions import CollapseToGraphNodeAction

from tests.conftest import make_node

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


@pytest.fixture
def listener_and_emitter(graph_with_library_system: BaseGraph):
    """An event node wired to a callback consumer, both in the host graph."""
    graph = graph_with_library_system
    listener = make_node(graph, _LISTEN)
    emitter = make_node(graph, _EMIT)
    graph.create_edge_wrapper(listener.node_id, "listen_callback", emitter.node_id, "edge_callback")
    graph.force_validation()
    return graph, listener, emitter


class TestRefusal:
    def test_collapsing_only_the_consumer_is_refused(self, listener_and_emitter):
        graph, _listener, emitter = listener_and_emitter

        with pytest.raises(ValueError, match="callback edge"):
            _collapse(graph, [emitter.node_id])

    def test_collapsing_only_the_event_node_is_refused(self, listener_and_emitter):
        """Both directions: a Group can no more export a callback than import one."""
        graph, listener, _emitter = listener_and_emitter

        with pytest.raises(ValueError, match="callback edge"):
            _collapse(graph, [listener.node_id])

    def test_the_message_names_the_node_at_the_other_end(self, listener_and_emitter):
        graph, listener, emitter = listener_and_emitter

        with pytest.raises(ValueError, match=listener.node_id):
            _collapse(graph, [emitter.node_id])

    def test_the_message_says_how_to_proceed(self, listener_and_emitter):
        graph, _listener, emitter = listener_and_emitter

        with pytest.raises(ValueError, match="Add the node at the other end"):
            _collapse(graph, [emitter.node_id])

    def test_a_refused_collapse_leaves_the_graph_untouched(self, listener_and_emitter):
        """Refused before anything is built: no Subgraph, no card, no moved nodes."""
        graph, _listener, emitter = listener_and_emitter
        before = set(graph.node_wrappers)

        with pytest.raises(ValueError, match="callback edge"):
            _collapse(graph, [emitter.node_id])

        assert set(graph.node_wrappers) == before
        assert graph.subgraphs == {}


class TestWhatIsStillAllowed:
    def test_collapsing_both_ends_together_is_allowed(self, listener_and_emitter):
        """The edge becomes internal to the Group, crossing nothing."""
        graph, listener, emitter = listener_and_emitter

        action = _collapse(graph, [listener.node_id, emitter.node_id])

        definition = graph.get_subgraph(action.subgraph_key)
        assert definition is not None
        assert listener.node_id in definition.node_wrappers
        assert emitter.node_id in definition.node_wrappers

    def test_an_interior_callback_edge_moves_in_intact(self, listener_and_emitter):
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
        """The guard must not disturb the ordinary case."""
        graph = graph_with_library_system
        a, b = make_node(graph, _PRINT), make_node(graph, _PRINT)
        graph.create_edge_wrapper(a.node_id, "done", b.node_id, "exec")
        graph.force_validation()

        action = _collapse(graph, [a.node_id, b.node_id])

        assert graph.get_subgraph(action.subgraph_key) is not None


class TestNoCallbackInterfacePortIsEverMinted:
    """The refusal exists to keep this true; the growing slot already is.

    ``_BuildSubgraphAction`` and ``hb_grow`` are the only two paths that create
    an interface port. The slot is ``FlowType.DATA``, so formal edge validation
    rejects a callback into it; collapse had no such check until now.
    """

    def test_a_callback_edge_into_the_growing_slot_is_rejected(self, graph_with_library_system):
        from haywire.core.graph.scheduler import SyncScheduler
        from haywire.core.graph.subgraph import SubgraphDefinition
        from haywire.barn.builtin.nodes.graph_node import SUBGRAPH_KEY

        graph = graph_with_library_system
        definition = graph.add_subgraph(
            SubgraphDefinition(key="sg_slot", label="G", validation_scheduler=SyncScheduler())
        )
        output_node = make_node(definition, _OUTPUT)
        make_node(graph, _CARD, node_data={"store": {SUBGRAPH_KEY: definition.key}})
        listener = make_node(definition, _LISTEN)
        slot = next(p for p in output_node.node.ports.values() if p.id.startswith("slot_"))

        edge = definition.create_edge_wrapper(
            listener.node_id, "listen_callback", output_node.node_id, slot.id
        )
        definition.force_validation()

        assert edge is not None
        assert edge.state.is_formally_validated is False
        assert not any(p.flow_type.value == "callback" for p in output_node.node.ports.values())
