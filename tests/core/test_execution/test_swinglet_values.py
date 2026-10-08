"""Swinglet values: an edge write stops at the swinglet, the node's own write passes on (Q100-Q108)."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

import pytest

from haywire.core.graph.base import BaseGraph
from haywire.core.graph.scheduler import SyncScheduler
from haywire.core.types import DataPort, PortType, Propagation
from haywire.core.undo.actions.graph_actions import CollapseToGraphNodeAction

from tests.conftest import make_edge, make_node, run_frame

pytestmark = [pytest.mark.integration]

_INPUT = "haywire-core:node:SubgraphInputNode"
_OUTPUT = "haywire-core:node:SubgraphOutputNode"
_CARD = "haywire-core:node:GraphNode"


def _key(name: str) -> str:
    from haybale_testing.nodes.testbed import swinglet_probe

    return getattr(swinglet_probe, name).class_identity.registry_key


def _port(type_cls, port_type, **kwargs) -> DataPort:
    return DataPort(
        registry_id="p",
        registry_key=type_cls.class_identity.registry_key,
        label="P",
        id="p",
        type_cls=type_cls,
        port_type=port_type,
        **kwargs,
    )


@pytest.fixture
def chain(graph_with_library_system: BaseGraph) -> Callable[..., tuple[Any, ...]]:
    """Build Begin -> Print with Add(1, 2) -> middle.s -> Add2.value_a (value_b 100) -> Print.message."""
    graph = graph_with_library_system

    def build(middle: str, lazy_in=False, lazy_out=False, with_feed=True):
        from haybale_testing.nodes.testbed.begin_play_node import TestBeginPlayNode
        from haybale_testing.nodes.testbed.math_op_node import TestAddFloatNode
        from haybale_testing.nodes.testbed.print_node import TestPrintNode

        begin = make_node(graph, TestBeginPlayNode.class_identity.registry_key)
        printer = make_node(graph, TestPrintNode.class_identity.registry_key)
        add_key = TestAddFloatNode.class_identity.registry_key
        a = make_node(graph, add_key)
        p = make_node(graph, _key(middle))
        b = make_node(graph, add_key)
        a.node.ports["value_a"].set_value(1.0)
        a.node.ports["value_b"].set_value(2.0)
        b.node.ports["value_b"].set_value(100.0)
        make_edge(graph, begin.node_id, "exec", printer.node_id, "exec")
        e_in = make_edge(graph, a.node_id, "result", p.node_id, "s") if with_feed else None
        e_out = make_edge(graph, p.node_id, "s", b.node_id, "value_a")
        make_edge(graph, b.node_id, "result", printer.node_id, "message")
        if lazy_in and e_in is not None:
            e_in.propagation = Propagation.LAZY
        if lazy_out:
            e_out.propagation = Propagation.LAZY
        graph.force_validation()
        return graph, a, p, b, e_in, p.node.ports["s"]

    return build


@pytest.mark.parametrize(
    ("lazy_in", "lazy_out"), [(False, False), (True, False), (False, True), (True, True)]
)
def test_the_nodes_write_is_passed_on(chain, lazy_in, lazy_out):
    graph, _a, p, b, _e, s = chain("SwingletPassProbeNode", lazy_in, lazy_out)
    run_frame(graph)
    assert p.node.seen == [3.0]
    assert b.node.ports["result"].get_value() == 130.0  # 3 * 10 + 100
    assert s.get_value() == 3.0
    assert s.get_own_value() == 30.0


@pytest.mark.parametrize(("lazy_in", "lazy_out"), [(False, False), (True, True)])
def test_an_arriving_value_stops_at_the_swinglet(chain, lazy_in, lazy_out):
    graph, _a, p, b, _e, _s = chain("SwingletStopProbeNode", lazy_in, lazy_out)
    run_frame(graph)
    assert p.node.seen == [3.0]
    assert b.node.ports["result"].get_value() == 100.0


def test_an_unfed_data_node_reads_its_own_last_write_when_it_runs_again(chain):
    graph, _a, p, b, _e, s = chain("SwingletPassProbeNode", with_feed=False)
    s.set_value(1.0)  # a widget write marks the port dirty
    run_frame(graph)
    run_frame(graph)  # nothing dirty: a data node does not run again
    assert p.node.seen == [1.0]
    p.node.mark_port_as_dirty(s)
    run_frame(graph)
    assert p.node.seen == [1.0, 10.0]
    assert b.node.ports["result"].get_value() == 200.0


def test_removing_the_feed_shows_the_nodes_last_write(chain):
    graph, _a, p, b, e_in, s = chain("SwingletPassProbeNode")
    run_frame(graph)
    graph.remove_edge_wrapper(e_in.edge_id)
    graph.force_validation()
    assert not s._data.has_linked_value()
    run_frame(graph)
    assert p.node.seen == [3.0, 30.0]
    assert b.node.ports["result"].get_value() == 400.0


def test_an_arriving_value_keeps_the_node_set_mark(chain):
    graph, a, _p, _b, _e, s = chain("SwingletPassProbeNode")
    run_frame(graph)
    a.node.out("result", 5.0)
    assert s._is_set_by_node is True


@pytest.mark.unit
def test_an_edge_write_to_an_immediate_swinglet_fires_immediately(monkeypatch):
    from haywire.barn.builtin.types import CALLBACK

    port = _port(CALLBACK, PortType.SWINGLET)
    fired = []
    monkeypatch.setattr(port, "_fire_immediate", lambda store, value: fired.append(value))
    port.set_value("sub", edge_id="e")
    assert fired == ["sub"]


def test_a_swinglet_round_trips_with_both_edges_and_its_own_value(chain):
    graph, _a, p, _b, _e, _s = chain("SwingletPassProbeNode")
    run_frame(graph)
    loaded = BaseGraph(filestem="g2", validation_scheduler=SyncScheduler())
    assert loaded.load_from_dict(graph.to_dict(include_data=True)) is True
    loaded.force_validation()
    wrapper = loaded.get_node_wrapper(p.node_id)
    assert wrapper is not None
    s2 = wrapper.node.ports["s"]
    assert s2.get_own_value() == 30.0
    assert len(s2.incoming.linked) == 1
    assert len(s2.outgoing.linked) == 1


@pytest.mark.unit
def test_a_swinglet_saves_its_own_value_because_the_node_set_it():
    """NODE_SET alone (no widget): the own value is saved after `out()` and not before."""
    from haywire.barn.builtin.types import FLOAT
    from haywire.core.types.enums import StoreStrategy

    port = _port(FLOAT, PortType.SWINGLET, store_strategy=StoreStrategy.NODE_SET)

    assert "field_data" not in port.to_dict(include_data=True)
    port.set_value(7.0)  # an own write that is not the node's does not set the mark
    assert "field_data" not in port.to_dict(include_data=True)
    port._emit(7.0)
    assert "field_data" in port.to_dict(include_data=True)


def test_on_change_reports_what_arrives_not_the_nodes_own_write(chain):
    graph, _a, p, b, _e, _s = chain("SwingletEchoProbeNode")
    run_frame(graph)
    assert p.node.changes == [3.0]  # once: the handler's own out() did not fire it again
    assert b.node.ports["result"].get_value() == 104.0  # (3 + 1) + 100


@pytest.mark.unit
def test_an_outlet_refuses_on_change():
    from haywire.barn.builtin.types import FLOAT

    with pytest.raises(ValueError, match="on_change"):
        FLOAT.as_outlet("o", on_change="hb_o")


def test_a_collapsed_swinglet_node_still_passes_its_write_on(graph_with_library_system):
    from haybale_testing.nodes.testbed.begin_play_node import TestBeginPlayNode
    from haybale_testing.nodes.testbed.math_op_node import TestAddFloatNode
    from haybale_testing.nodes.testbed.print_node import TestPrintNode

    graph = graph_with_library_system
    begin = make_node(graph, TestBeginPlayNode.class_identity.registry_key)
    printer = make_node(graph, TestPrintNode.class_identity.registry_key)
    a = make_node(graph, TestAddFloatNode.class_identity.registry_key)
    p = make_node(graph, _key("SwingletPassProbeNode"))
    b = make_node(graph, TestAddFloatNode.class_identity.registry_key)
    a.node.ports["value_a"].set_value(1.0)
    a.node.ports["value_b"].set_value(2.0)
    b.node.ports["value_b"].set_value(100.0)
    make_edge(graph, begin.node_id, "exec", printer.node_id, "exec")
    make_edge(graph, a.node_id, "result", p.node_id, "s")
    make_edge(graph, p.node_id, "s", b.node_id, "value_a")
    make_edge(graph, b.node_id, "result", printer.node_id, "message")
    graph.force_validation()

    action = CollapseToGraphNodeAction(
        graph=graph,
        node_ids=[p.node_id],
        card_registry_key=_CARD,
        input_registry_key=_INPUT,
        output_registry_key=_OUTPUT,
        label="Group",
    )
    action.execute()
    graph.force_validation()
    definition = graph.get_subgraph(action.subgraph_key)
    assert definition is not None
    definition.force_validation()
    run_frame(graph)

    inner = definition.get_node_wrapper(p.node_id)
    assert inner is not None
    assert inner.node.seen == [3.0]
    assert b.node.ports["result"].get_value() == 130.0
