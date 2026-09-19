"""Flipping ``EdgeWrapper.is_lazy`` reaches the live pipe.

A ``Pipe`` copies ``is_lazy`` at construction, so a propagation-mode change
has to rebuild it. The pin menu and the edge properties panel both write the
property directly, which is the path these cover.
"""

from __future__ import annotations

import pytest

from haywire.core.graph.base import BaseGraph

from tests.conftest import make_node

_ADD = "haybale-testing:node:TestAddFloatNode"

pytestmark = [pytest.mark.integration]


def _pipe_modes(outlet) -> list[bool]:
    """``is_lazy`` of every live pipe on ``outlet``."""
    if outlet._pipes is None:
        return []
    return [pipe.is_lazy for pipe in outlet._pipes._pipes.values()]


@pytest.fixture
def linked_pair(graph_with_library_system: BaseGraph):
    """Two Adds joined by one eager data edge, validated."""
    graph = graph_with_library_system
    source, sink = make_node(graph, _ADD), make_node(graph, _ADD)
    edge = graph.create_edge_wrapper(source.node_id, "result", sink.node_id, "value_a")
    assert edge is not None
    graph.force_validation()
    return graph, source, sink, edge


class TestTogglingLaziness:
    def test_a_fresh_edge_is_eager(self, linked_pair):
        _graph, source, _sink, _edge = linked_pair

        assert _pipe_modes(source.node.ports["result"]) == [False]

    def test_turning_it_lazy_reaches_the_pipe(self, linked_pair):
        _graph, source, _sink, edge = linked_pair

        edge.is_lazy = True

        assert _pipe_modes(source.node.ports["result"]) == [True]

    def test_turning_it_eager_again_reaches_the_pipe(self, linked_pair):
        _graph, source, _sink, edge = linked_pair

        edge.is_lazy = True
        edge.is_lazy = False

        assert _pipe_modes(source.node.ports["result"]) == [False]

    def test_a_lazy_edge_defers_the_write_instead_of_pushing(self, linked_pair):
        """The behaviour the flag buys: the sink is marked, not written."""
        _graph, source, sink, edge = linked_pair
        edge.is_lazy = True
        sink_port = sink.node.ports["value_a"]
        sink_port.set_value(0.0)

        source.node.ports["result"].set_value(42.0)

        assert sink_port.get_value() == pytest.approx(0.0)
        assert len(sink_port._pending_lazy_pipes) == 1

    def test_resolving_the_sink_then_pulls_it(self, linked_pair):
        _graph, source, sink, edge = linked_pair
        edge.is_lazy = True
        sink_port = sink.node.ports["value_a"]
        sink_port.set_value(0.0)
        source.node.ports["result"].set_value(42.0)

        sink_port.resolve_dirty_data()

        assert sink_port.get_value() == pytest.approx(42.0)

    def test_an_eager_edge_still_pushes_immediately(self, linked_pair):
        _graph, source, sink, _edge = linked_pair
        sink_port = sink.node.ports["value_a"]

        source.node.ports["result"].set_value(42.0)

        assert sink_port.get_value() == pytest.approx(42.0)

    def test_setting_the_same_value_is_a_no_op(self, linked_pair):
        """Re-asserting the current mode must not disturb the live pipe."""
        _graph, source, _sink, edge = linked_pair
        edge.is_lazy = True
        pipe_before = next(iter(source.node.ports["result"]._pipes._pipes.values()))

        edge.is_lazy = True

        pipe_after = next(iter(source.node.ports["result"]._pipes._pipes.values()))
        assert pipe_after is pipe_before

    def test_the_other_edges_on_the_outlet_keep_their_own_mode(self, linked_pair):
        """A rebuild re-reads every edge, so a sibling must not be flipped too."""
        graph, source, _sink, edge = linked_pair
        third = make_node(graph, _ADD)
        graph.create_edge_wrapper(source.node_id, "result", third.node_id, "value_a")
        graph.force_validation()

        edge.is_lazy = True

        assert sorted(_pipe_modes(source.node.ports["result"])) == [False, True]
