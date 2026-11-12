"""Core support for drain inlets: the field hooks, ``NodeData.drain``, and the edge lock and refusal.

The inlet here is an ordinary Add input whose field is made to answer ``queues_values()``,
standing in for a drain field so these cover core without any library type.
"""

from __future__ import annotations

import pytest

from haywire.core.graph.base import BaseGraph
from haywire.core.types import Drained, Propagation

from tests.conftest import make_node

_ADD = "haybale-testing:node:TestAddFloatNode"

pytestmark = [pytest.mark.integration]


def _make_queueing(port) -> None:
    """Make *port*'s field answer as a drain field does."""
    port.data.queues_values = lambda: True
    port.data.take = lambda: Drained([1.0, 2.0], dropped=3)


def _pipe_modes(outlet) -> list[bool]:
    """``is_lazy`` of every live pipe on ``outlet``."""
    if outlet._pipes is None:
        return []
    return [pipe.is_lazy for pipe in outlet._pipes._pipes.values()]


@pytest.fixture
def drain_edge(graph_with_library_system: BaseGraph):
    """An Add whose `value_a` queues, fed by another Add's result, validated."""
    graph = graph_with_library_system
    source, sink = make_node(graph, _ADD), make_node(graph, _ADD)
    _make_queueing(sink.node.ports["value_a"])
    edge = graph.create_edge_wrapper(source.node_id, "result", sink.node_id, "value_a")
    assert edge is not None
    graph.force_validation()
    return source, sink, edge


class TestDrained:
    def test_is_a_list_of_the_values(self):
        batch = Drained([1, 2, 3], dropped=2)

        assert batch == [1, 2, 3]
        assert batch.dropped == 2

    def test_defaults_to_empty_with_nothing_dropped(self):
        batch = Drained()

        assert batch == []
        assert batch.dropped == 0


class TestFieldHooks:
    def test_an_ordinary_field_does_not_queue(self, graph_with_library_system):
        node = make_node(graph_with_library_system, _ADD)
        port = node.node.ports["value_a"]

        assert port.data.queues_values() is False
        assert port.queues_values is False

    def test_an_ordinary_field_refuses_take(self, graph_with_library_system):
        node = make_node(graph_with_library_system, _ADD)

        with pytest.raises(TypeError, match="does not queue values"):
            node.node.ports["value_a"].data.take()


class TestNodeDrain:
    def test_returns_what_the_field_takes(self, graph_with_library_system):
        node = make_node(graph_with_library_system, _ADD)
        _make_queueing(node.node.ports["value_a"])

        batch = node.node.drain("value_a")

        assert batch == [1.0, 2.0]
        assert batch.dropped == 3

    def test_an_unknown_port_raises_key_error(self, graph_with_library_system):
        node = make_node(graph_with_library_system, _ADD)

        with pytest.raises(KeyError):
            node.node.drain("nope")

    def test_a_port_that_does_not_queue_raises_type_error(self, graph_with_library_system):
        node = make_node(graph_with_library_system, _ADD)

        with pytest.raises(TypeError):
            node.node.drain("value_a")


class TestTheEdgeIntoADrainInlet:
    def test_is_locked_eager(self, drain_edge):
        source, _sink, edge = drain_edge

        assert edge.locked_propagation is Propagation.EAGER
        assert edge.propagation is Propagation.EAGER
        assert _pipe_modes(source.node.ports["result"]) == [False]

    def test_refuses_lazy(self, drain_edge):
        _source, _sink, edge = drain_edge

        with pytest.raises(ValueError, match="locked"):
            edge.propagation = Propagation.LAZY

    def test_stays_eager_when_saved_lazy(self, drain_edge):
        _source, _sink, edge = drain_edge

        edge._edge.propagation = Propagation.LAZY

        assert edge.propagation is Propagation.EAGER

    def test_an_ordinary_edge_is_not_locked(self, graph_with_library_system):
        graph = graph_with_library_system
        source, sink = make_node(graph, _ADD), make_node(graph, _ADD)
        edge = graph.create_edge_wrapper(source.node_id, "result", sink.node_id, "value_a")
        graph.force_validation()

        assert edge.locked_propagation is None


class TestAPromotedOutletIntoADrainInlet:
    @pytest.fixture
    def edge(self, graph_with_library_system):
        from haybale_testing.nodes.testbed.settings_node import SettingsNode
        from haywire.core.node.promotion import promote_setting
        from haywire.core.types.enums import PortType

        graph = graph_with_library_system
        src = graph.create_node_wrapper(SettingsNode.class_identity.registry_key, position=(0, 0))
        sink = make_node(graph, _ADD)
        _make_queueing(sink.node.ports["value_a"])
        promote_setting(src.node, "example", "example_float", direction=PortType.OUTLET)
        pid = type(src.node.example).__dict__["example_float"].storage_key
        edge = graph.create_edge_wrapper(src.node_id, pid, sink.node_id, "value_a")
        assert edge is not None
        graph.force_validation()
        return edge

    def test_fails_validation(self, edge):
        assert not edge.state.is_formally_validated
        assert edge.state.error_formal is not None
        assert "needs every value" in str(edge.state.error_formal)
