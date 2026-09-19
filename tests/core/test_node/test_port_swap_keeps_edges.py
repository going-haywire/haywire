"""A port replaced by a rejig takes its edges' references with it.

``adopt_state_from`` transplants ``_linked_edges`` to the replacement port, but
an ``EdgeWrapper`` holds its endpoints by object reference. An edge left
pointing at the replaced port acts on a port that is no longer on the node:
``detach()`` unlinks the orphan and the live port stays linked for good — no
error, and nothing to see but a pin stuck in its linked rendering.

Only a node that rebuilds its ports while edges are attached hits this. The
Graph-node card is the one in the codebase: ``reconcile_interface`` rejigs its
pins whenever the Subgraph's interface changes.
"""

from __future__ import annotations

import pytest

from haywire.core.graph.base import BaseGraph

from tests.conftest import make_node

pytestmark = [pytest.mark.integration]

_ADD = "haybale-testing:node:TestAddFloatNode"


@pytest.fixture
def linked_pair(graph_with_library_system: BaseGraph):
    """Two nodes joined by one data edge, validated."""
    graph = graph_with_library_system
    source, sink = make_node(graph, _ADD), make_node(graph, _ADD)
    edge = graph.create_edge_wrapper(source.node_id, "result", sink.node_id, "value_a")
    assert edge is not None
    graph.force_validation()
    return graph, source, sink, edge


class TestReAddingAPortKeepsItsEdges:
    """``adopt_state_from`` re-points the edges it inherits.

    A node that rejigs itself outside a validation callback is covered anyway:
    ``add`` marks it structurally dirty, and the batch that follows revalidates
    its edges, which re-resolves every endpoint by id. These assert the
    invariant directly, so it holds whichever path gets there first —
    ``TestTheGraphNodeCard`` below is where only this re-pointing does.
    """

    def test_the_edge_points_at_the_replacement(self, linked_pair):
        from haywire.barn.builtin.types import FLOAT

        graph, _source, sink, edge = linked_pair
        original = sink.node.ports["value_a"]

        with sink.node.rejig(include=["value_a"]):
            sink.node.add(FLOAT.as_inlet("value_a"))

        replacement = sink.node.ports["value_a"]
        assert replacement is not original
        assert edge._inlet_port is replacement

    def test_an_outlet_is_re_pointed_too(self, linked_pair):
        from haywire.barn.builtin.types import FLOAT

        graph, source, _sink, edge = linked_pair
        original = source.node.ports["result"]

        with source.node.rejig(include=["result"]):
            source.node.add(FLOAT.as_outlet("result"))

        replacement = source.node.ports["result"]
        assert replacement is not original
        assert edge._outlet_port is replacement

    def test_the_replacement_is_linked(self, linked_pair):
        from haywire.barn.builtin.types import FLOAT

        graph, _source, sink, _edge = linked_pair

        with sink.node.rejig(include=["value_a"]):
            sink.node.add(FLOAT.as_inlet("value_a"))

        assert sink.node.ports["value_a"].is_linked() is True

    def test_removing_the_edge_afterwards_unlinks_the_live_port(self, linked_pair):
        from haywire.barn.builtin.types import FLOAT

        graph, _source, sink, edge = linked_pair
        with sink.node.rejig(include=["value_a"]):
            sink.node.add(FLOAT.as_inlet("value_a"))

        graph.remove_edge_wrapper(edge.edge_id)
        graph.force_validation()

        assert sink.node.ports["value_a"].is_linked() is False


class TestTheGraphNodeCard:
    """The node this actually bit: its pins rejig on every interface change."""

    @pytest.fixture
    def card_with_a_wired_pin(self, graph_with_library_system: BaseGraph):
        from haywire.barn.builtin.types import ADD, FLOAT
        from haywire.barn.builtin.widgets import NumberWidget
        from haywire.core.undo.actions.graph_actions import CollapseToGraphNodeAction

        graph = graph_with_library_system
        producer = make_node(graph, _ADD)
        consumer = make_node(graph, _ADD)
        with consumer.node.rejig():
            consumer.node.add(FLOAT.as_inlet("gain", label="Gain", widget=NumberWidget.config()))
        graph.create_edge_wrapper(producer.node_id, "result", consumer.node_id, "gain")
        graph.force_validation()

        action = CollapseToGraphNodeAction(
            graph=graph,
            node_ids=[consumer.node_id],
            card_registry_key="haywire-core:node:GraphNode",
            input_registry_key="haywire-core:node:SubgraphInputNode",
            output_registry_key="haywire-core:node:SubgraphOutputNode",
            label="G",
        )
        action.execute()
        graph.force_validation()
        definition = graph.get_subgraph(action.subgraph_key)
        definition.force_validation()

        card = graph.get_node_wrapper(action.card_node_id)
        interface = next(
            p
            for p in definition.input_node.node.get_all_ports()
            if p.type_cls is not None and not issubclass(p.type_cls, ADD)
        )
        edge = next(e for e in graph.edge_wrappers.values() if e.sink_node_id == card.node_id)
        return graph, card, f"in_{interface.id}", edge

    def test_a_reconcile_keeps_the_edge_on_the_live_pin(self, card_with_a_wired_pin):
        _graph, card, pin_id, edge = card_with_a_wired_pin

        card.node.reconcile_interface()

        assert edge._inlet_port is card.node.ports[pin_id]

    def test_unwiring_after_a_reconcile_shows_the_widget(self, card_with_a_wired_pin):
        """End to end: reconcile, unwire, and the pin offers its editor."""
        graph, card, pin_id, edge = card_with_a_wired_pin
        card.node.reconcile_interface()

        graph.remove_edge_wrapper(edge.edge_id)
        graph.force_validation()

        pin = card.node.ports[pin_id]
        assert pin.is_linked() is False
        assert pin.should_show_widget() is True


class TestAnOutletKeepsDelivering:
    """The other half of what a swap invalidates: the outlet's transport.

    ``_pipes`` is derived from the links and belongs to the port object, so a
    replacement starts with none. Nothing else rebuilds it in time for a node
    that rejigs inside a validation callback, and the failure is quieter than
    the stale-reference one: the outlet simply stops delivering, with nothing
    to see at either end.
    """

    def test_a_swapped_outlet_keeps_its_pipes(self, linked_pair):
        from haywire.barn.builtin.types import FLOAT

        _graph, source, _sink, _edge = linked_pair

        with source.node.rejig(include=["result"]):
            source.node.add(FLOAT.as_outlet("result"))

        pipes = source.node.ports["result"]._pipes
        assert pipes is not None
        assert len(pipes._pipes) == 1

    def test_a_value_still_reaches_the_sink(self, linked_pair):
        from haywire.barn.builtin.types import FLOAT

        _graph, source, sink, _edge = linked_pair
        with source.node.rejig(include=["result"]):
            source.node.add(FLOAT.as_outlet("result"))
        sink.node.ports["value_a"].set_value(0.0)

        source.node.ports["result"].set_value(42.0)

        assert sink.node.ports["value_a"].get_value() == pytest.approx(42.0)

    def test_the_card_outlet_still_delivers_after_a_reconcile(self, graph_with_library_system):
        """The path that has no validation batch to fall back on."""
        from haywire.core.undo.actions.graph_actions import CollapseToGraphNodeAction

        graph = graph_with_library_system
        producer = make_node(graph, _ADD)
        consumer = make_node(graph, _ADD)
        graph.create_edge_wrapper(producer.node_id, "result", consumer.node_id, "value_a")
        graph.force_validation()

        action = CollapseToGraphNodeAction(
            graph=graph,
            node_ids=[producer.node_id],
            card_registry_key="haywire-core:node:GraphNode",
            input_registry_key="haywire-core:node:SubgraphInputNode",
            output_registry_key="haywire-core:node:SubgraphOutputNode",
            label="G",
        )
        action.execute()
        graph.force_validation()
        graph.get_subgraph(action.subgraph_key).force_validation()
        card = graph.get_node_wrapper(action.card_node_id)
        pin_id = next(p.id for p in card.node.ports.values() if p.is_outlet() and p.id.startswith("out_"))

        card.node.reconcile_interface()
        consumer.node.ports["value_a"].set_value(0.0)
        card.node.ports[pin_id].set_value(7.0)

        assert consumer.node.ports["value_a"].get_value() == pytest.approx(7.0)
