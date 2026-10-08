"""A swinglet links at either end of an edge; one edge joins two pins, whichever way they were dragged."""

import pytest
from haybale_testing.nodes.testbed.swinglet_probe import (
    SwingletControlProbeNode,
    SwingletPassProbeNode,
    SwingletVisualProbeNode,
)

from tests.conftest import make_edge, make_node

pytestmark = pytest.mark.integration


@pytest.fixture
def graph(graph_with_library_system):
    return graph_with_library_system


def _key(cls):
    return cls.class_identity.registry_key


def _add(graph):
    from haybale_testing.nodes.testbed.math_op_node import TestAddFloatNode

    return make_node(graph, _key(TestAddFloatNode))


def test_a_swinglet_takes_either_end_of_a_data_edge(graph):
    a, p, b = _add(graph), make_node(graph, _key(SwingletPassProbeNode)), _add(graph)
    e_in = make_edge(graph, a.node_id, "result", p.node_id, "s")
    e_out = make_edge(graph, p.node_id, "s", b.node_id, "value_a")
    graph.force_validation()
    s = p.node.ports["s"]
    assert e_in.is_valid()
    assert e_out.is_valid()
    assert list(s.incoming.linked) == [e_in.edge_id]
    assert list(s.outgoing.linked) == [e_out.edge_id]


def test_two_swinglets_link_on_a_visual_wire_in_drag_order(graph):
    v1, v2 = (make_node(graph, _key(SwingletVisualProbeNode)) for _ in range(2))
    edge = make_edge(graph, v1.node_id, "note", v2.node_id, "note")
    graph.force_validation()
    assert edge.is_valid()
    assert not edge.carries_values
    assert (edge.source_node_id, edge.sink_node_id) == (v1.node_id, v2.node_id)


def test_a_second_incoming_data_edge_displaces_only_the_first(graph):
    a1, a2, p, b = _add(graph), _add(graph), make_node(graph, _key(SwingletPassProbeNode)), _add(graph)
    first = make_edge(graph, a1.node_id, "result", p.node_id, "s")
    out = make_edge(graph, p.node_id, "s", b.node_id, "value_a")
    second = make_edge(graph, a2.node_id, "result", p.node_id, "s")
    graph.force_validation()
    assert not first.is_valid()
    assert second.is_valid()
    assert out.is_valid()


def test_a_control_swinglet_keeps_one_outgoing_edge_and_many_incoming(graph):
    c, i1, i2, o1, o2 = (make_node(graph, _key(SwingletControlProbeNode)) for _ in range(5))
    in1 = make_edge(graph, i1.node_id, "flow", c.node_id, "flow")
    in2 = make_edge(graph, i2.node_id, "flow", c.node_id, "flow")
    out1 = make_edge(graph, c.node_id, "flow", o1.node_id, "flow")
    out2 = make_edge(graph, c.node_id, "flow", o2.node_id, "flow")
    graph.force_validation()
    assert in1.is_valid()
    assert in2.is_valid()
    assert not out1.is_valid()
    assert out2.is_valid()


def test_removing_a_swinglet_detaches_both_sets(graph):
    a, p, b = _add(graph), make_node(graph, _key(SwingletPassProbeNode)), _add(graph)
    e_in = make_edge(graph, a.node_id, "result", p.node_id, "s")
    e_out = make_edge(graph, p.node_id, "s", b.node_id, "value_a")
    graph.force_validation()
    with p.node.rejig(include=["s"]):
        pass
    graph.force_validation()
    assert a.node.ports["result"].outgoing.linked == {}
    assert not e_in.is_valid()
    assert not e_out.is_valid()


def test_a_reverse_visual_edge_is_refused(graph):
    v1, v2 = (make_node(graph, _key(SwingletVisualProbeNode)) for _ in range(2))
    make_edge(graph, v1.node_id, "note", v2.node_id, "note")
    graph.force_validation()
    with pytest.raises(ValueError, match="other way"):
        graph.create_edge_wrapper(v2.node_id, "note", v1.node_id, "note")


def test_a_reverse_control_edge_is_refused_too(graph):
    c1, c2 = (make_node(graph, _key(SwingletControlProbeNode)) for _ in range(2))
    make_edge(graph, c1.node_id, "flow", c2.node_id, "flow")
    with pytest.raises(ValueError, match="other way"):
        graph.create_edge_wrapper(c2.node_id, "flow", c1.node_id, "flow")


def test_undo_restores_a_deleted_visual_swinglet_edge(graph):  # Review Focus 2
    from haywire.core.undo.actions.graph_actions import RemoveElementsAction

    v1, v2 = (make_node(graph, _key(SwingletVisualProbeNode)) for _ in range(2))
    edge = make_edge(graph, v1.node_id, "note", v2.node_id, "note")
    graph.force_validation()
    action = RemoveElementsAction(graph=graph, edges=[edge.edge_id])
    action.execute()
    action.undo()
    graph.force_validation()
    assert graph.get_edge_wrapper(edge.edge_id).is_valid()


class _ParkedHandle:
    def cancel(self) -> None:
        return None


class _ParkedScheduler:
    """Holds every scheduled validation and never runs it."""

    def schedule(self, delay_seconds, fn):
        return _ParkedHandle()


def test_a_retyped_swinglet_keeps_both_edges(library_system):  # Review Focus 1
    """Pinned on a graph that never revalidates by itself.

    A scheduler that runs validation would re-resolve both edge ends by id
    when the rejig exits, and the test would pass without the re-pointing in
    ``adopt_state_from``.
    """
    from haywire.barn.builtin.types import INT
    from haywire.core.graph.base import BaseGraph

    graph = BaseGraph(filestem="Parked Graph", validation_scheduler=_ParkedScheduler())
    a, p, b = _add(graph), make_node(graph, _key(SwingletPassProbeNode)), _add(graph)
    e_in = make_edge(graph, a.node_id, "result", p.node_id, "s")
    e_out = make_edge(graph, p.node_id, "s", b.node_id, "value_a")
    graph.force_validation()
    old = p.node.ports["s"]
    with p.node.rejig(include=["s"]):
        p.node.add(INT.as_swinglet("s"))
    new = p.node.ports["s"]
    assert new is not old
    assert e_in._inlet_port is new
    assert e_out._outlet_port is new
    assert e_in.edge_id in new.incoming.all
    assert e_out.edge_id in new.outgoing.all
