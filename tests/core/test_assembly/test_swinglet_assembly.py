"""A swinglet in assembly: every edge lookup names the end it means (Q109).

The lookup used to return the edges at BOTH ends of a port, so the assembly
read a swinglet's incoming edge as one of its outgoing edges and refused the
graph as an illegal cycle.
"""

from __future__ import annotations

import pytest
from haybale_testing.nodes.testbed.swinglet_probe import (
    SwingletControlProbeNode,
    SwingletStopProbeNode,
)

from haywire.core.graph.base import BaseGraph

from tests.conftest import make_edge, make_node, run_frame

pytestmark = [pytest.mark.integration]

_STOP = SwingletStopProbeNode.class_identity.registry_key
_CONTROL = SwingletControlProbeNode.class_identity.registry_key


def _testbed_keys() -> tuple[str, str, str]:
    """The registry keys of the Begin, Print and Add testbed nodes."""
    from haybale_testing.nodes.testbed.begin_play_node import TestBeginPlayNode
    from haybale_testing.nodes.testbed.math_op_node import TestAddFloatNode
    from haybale_testing.nodes.testbed.print_node import TestPrintNode

    return (
        TestBeginPlayNode.class_identity.registry_key,
        TestPrintNode.class_identity.registry_key,
        TestAddFloatNode.class_identity.registry_key,
    )


def test_the_edge_lookup_names_its_end(graph_with_library_system: BaseGraph):
    _begin, _print, add_key = _testbed_keys()
    graph = graph_with_library_system
    a = make_node(graph, add_key)
    p = make_node(graph, _STOP)
    b = make_node(graph, add_key)
    into = make_edge(graph, a.node_id, "result", p.node_id, "s")
    out_of = make_edge(graph, p.node_id, "s", b.node_id, "value_a")

    assert graph._get_edge_wrappers_for_port(p.node_id, "s", incoming=True) == [into]
    assert graph._get_edge_wrappers_for_port(p.node_id, "s", incoming=False) == [out_of]


def test_an_arriving_value_reaches_the_swinglets_worker(graph_with_library_system: BaseGraph):
    begin_key, print_key, add_key = _testbed_keys()
    graph = graph_with_library_system
    begin = make_node(graph, begin_key)
    printer = make_node(graph, print_key)
    add1 = make_node(graph, add_key)
    stop = make_node(graph, _STOP)
    add2 = make_node(graph, add_key)
    add1.node.ports["value_a"].set_value(1.0)
    add1.node.ports["value_b"].set_value(2.0)
    add2.node.ports["value_b"].set_value(100.0)
    make_edge(graph, begin.node_id, "exec", printer.node_id, "exec")
    make_edge(graph, add1.node_id, "result", stop.node_id, "s")
    make_edge(graph, stop.node_id, "s", add2.node_id, "value_a")
    make_edge(graph, add2.node_id, "result", printer.node_id, "message")

    run_frame(graph)

    assert isinstance(stop.node, SwingletStopProbeNode)
    assert stop.node.seen == [3.0]
    assert add2.node.ports["result"].get_value() == 100.0


def test_control_passes_through_a_control_swinglet(graph_with_library_system: BaseGraph):
    begin_key, print_key, add_key = _testbed_keys()
    graph = graph_with_library_system
    begin = make_node(graph, begin_key)
    c1 = make_node(graph, _CONTROL)
    c2 = make_node(graph, _CONTROL)
    make_edge(graph, begin.node_id, "exec", c1.node_id, "flow")
    make_edge(graph, c1.node_id, "flow", c2.node_id, "flow")

    run_frame(graph)

    assert isinstance(c1.node, SwingletControlProbeNode)
    assert isinstance(c2.node, SwingletControlProbeNode)
    assert c1.node.runs == 1
    assert c2.node.runs == 1


def _build_cycle(graph: BaseGraph, through_swinglet: bool) -> None:
    """Begin runs a Print fed from B, where B feeds A and A feeds B, directly or through a swinglet."""
    begin_key, print_key, add_key = _testbed_keys()
    begin = make_node(graph, begin_key)
    printer = make_node(graph, print_key)
    a = make_node(graph, add_key)
    b = make_node(graph, add_key)
    make_edge(graph, begin.node_id, "exec", printer.node_id, "exec")
    make_edge(graph, b.node_id, "result", printer.node_id, "message")
    if through_swinglet:
        s = make_node(graph, _STOP)
        make_edge(graph, a.node_id, "result", s.node_id, "s")
        make_edge(graph, s.node_id, "s", b.node_id, "value_a")
    else:
        make_edge(graph, a.node_id, "result", b.node_id, "value_a")
    make_edge(graph, b.node_id, "result", a.node_id, "value_a")


@pytest.mark.parametrize("through_swinglet", [False, True], ids=["plain", "swinglet"])
def test_a_data_cycle_is_refused_at_assembly(graph_with_library_system: BaseGraph, through_swinglet: bool):
    from haywire.core.assembly.flow_assembly_manager import FlowAssemblyManager

    graph = graph_with_library_system
    _build_cycle(graph, through_swinglet)

    with pytest.raises(RuntimeError, match="Illegal cycle detected in data flow"):
        FlowAssemblyManager().assemble_graph(graph)
