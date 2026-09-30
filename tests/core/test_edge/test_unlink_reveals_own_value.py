"""Removing an inlet's last edge shows its own value, and the node hears of it through its propagation."""

from typing import Any, cast

import pytest

from haywire.barn.builtin.types import FLOAT
from haywire.core.types import DataPort, FlowType, PortType, Propagation


@pytest.fixture
def linked_pair(graph_with_library_system, library_system):
    """Two Adds joined by an eager data edge; the sink's own value is 7.0 and the edge delivered 42.0."""
    from haybale_testing.nodes.testbed.math_op_node import TestAddFloatNode

    graph = graph_with_library_system
    key = TestAddFloatNode.class_identity.registry_key
    source = graph.create_node_wrapper(key, position=(0, 0))
    sink = graph.create_node_wrapper(key, position=(300, 0))
    inlet = sink.node.ports["value_a"]
    inlet.set_value(7.0)
    edge = graph.create_edge_wrapper(source.node_id, "result", sink.node_id, "value_a")
    source.node.out("result", 42.0)
    assert inlet.get_value() == 42.0
    return graph, source, sink, edge


@pytest.mark.integration
class TestUnlinking:
    def test_the_own_value_shows_and_the_node_is_marked(self, linked_pair):
        graph, _source, sink, edge = linked_pair
        sink.node._has_dirty_ports.clear()

        graph.remove_edge_wrapper(edge.edge_id)

        assert sink.node.ports["value_a"].get_value() == 7.0
        assert "value_a" in sink.node._has_dirty_ports

    def test_an_own_write_while_linked_shows_after_unlinking(self, linked_pair):
        graph, _source, sink, edge = linked_pair
        inlet = sink.node.ports["value_a"]

        inlet.set_value(5.0)

        assert inlet.get_value() == 42.0
        graph.remove_edge_wrapper(edge.edge_id)
        assert inlet.get_value() == 5.0

    def test_an_own_write_while_linked_does_not_mark_the_node(self, linked_pair):
        _graph, _source, sink, _edge = linked_pair
        sink.node._has_dirty_ports.clear()

        sink.node.ports["value_a"].set_value(5.0)

        assert "value_a" not in sink.node._has_dirty_ports

    def test_a_pending_lazy_pull_is_dropped_with_its_edge(self, linked_pair):
        graph, source, sink, edge = linked_pair
        edge.propagation = Propagation.LAZY
        inlet = sink.node.ports["value_a"]
        source.node.out("result", 99.0)
        assert len(inlet._pending_lazy_pipes) == 1

        graph.remove_edge_wrapper(edge.edge_id)
        inlet.resolve_dirty_data()

        assert inlet._pending_lazy_pipes == set()
        assert inlet.get_value() == 7.0


def _inlet() -> DataPort:
    return DataPort(
        registry_id="float",
        registry_key="haybale_core:type:float",
        label="F",
        id="v",
        type_cls=FLOAT,
        port_type=PortType.INLET,
        flow_type=FlowType.DATA,
    )


@pytest.mark.unit
def test_an_inlet_fed_by_two_edges_keeps_the_linked_value_until_the_last_goes():
    port = _inlet()
    port.allow_multiple_links = True
    port.set_value(1.0)
    port._linked_edges["a"] = cast(Any, object())
    port._linked_edges["b"] = cast(Any, object())
    port.set_value(9.0, edge_id="a")

    port._linked_edges.pop("a")
    port._reveal_own_value_if_unlinked()
    assert port.get_value() == 9.0

    port._linked_edges.pop("b")
    port._reveal_own_value_if_unlinked()
    assert port.get_value() == 1.0
