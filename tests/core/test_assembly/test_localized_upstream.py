"""A localized data flow knows each node's data sources, so the VM's poisoning check walks no edges."""

import importlib
from typing import Any

import pytest

from haywire.core.assembly.flow_assembly_manager import FlowAssemblyManager
from tests.conftest import make_node

pytestmark = pytest.mark.integration


def _cls(module: str, name: str) -> Any:
    return getattr(importlib.import_module(module), name)


def _add(graph: Any, module: str, name: str) -> Any:
    cls = _cls(module, name)
    wrapper = make_node(graph, cls.class_identity.registry_key, position=(0, 0))
    assert isinstance(wrapper.node, cls), "an unknown key yields an ErrorNode"
    return wrapper.node


_BENCH = "haybale_testing.nodes.benchmark"


def _pass(graph: Any) -> Any:
    return _add(graph, f"{_BENCH}.bench_data_pass_node", "BenchDataPassNode")


def _localized(graph: Any, control: Any) -> Any:
    graph.force_validation()
    for flow in FlowAssemblyManager().assemble_graph(graph):
        info = flow.control_graph.get_node_info(control.node_id) if flow.control_graph else None
        if info is not None and info.localized_data_flow is not None:
            return info.localized_data_flow
    raise AssertionError("control node not in any flow")


def _ids(nodes: tuple) -> list[str]:
    return [n.node_id for n in nodes]


def test_a_chain_lists_each_link_and_the_control_node(graph_with_library_system):
    graph = graph_with_library_system
    begin = _add(graph, "haybale_core.nodes.events.begin_play", "BeginPlayNode")
    sink = _add(graph, f"{_BENCH}.bench_sink_node", "BenchSinkNode")
    a, b, c = _pass(graph), _pass(graph), _pass(graph)
    graph.create_edge_wrapper(begin.node_id, "exec", sink.node_id, "exec_in")
    graph.create_edge_wrapper(a.node_id, "y", b.node_id, "x")
    graph.create_edge_wrapper(b.node_id, "y", c.node_id, "x")
    graph.create_edge_wrapper(c.node_id, "y", sink.node_id, "x")

    upstream = _localized(graph, sink).upstream

    assert upstream[a.node_id] == ()
    assert _ids(upstream[b.node_id]) == [a.node_id]
    assert _ids(upstream[c.node_id]) == [b.node_id]
    assert _ids(upstream[sink.node_id]) == [c.node_id]  # exec edge from BeginPlay is not a source


def test_a_fan_in_lists_both_sources_once(graph_with_library_system):
    graph = graph_with_library_system
    begin = _add(graph, "haybale_core.nodes.events.begin_play", "BeginPlayNode")
    sink = _add(graph, f"{_BENCH}.bench_sink_node", "BenchSinkNode")
    fan = _add(graph, f"{_BENCH}.bench_fan_in_node", "BenchFanInNode")
    a = _pass(graph)
    graph.create_edge_wrapper(begin.node_id, "exec", sink.node_id, "exec_in")
    graph.create_edge_wrapper(a.node_id, "y", fan.node_id, "a")
    graph.create_edge_wrapper(a.node_id, "y", fan.node_id, "b")
    graph.create_edge_wrapper(fan.node_id, "y", sink.node_id, "x")

    upstream = _localized(graph, sink).upstream

    assert _ids(upstream[fan.node_id]) == [a.node_id]


def test_a_control_node_feeding_data_is_a_source(graph_with_library_system):
    graph = graph_with_library_system
    begin = _add(graph, "haybale_core.nodes.events.begin_play", "BeginPlayNode")
    loop = _add(graph, "haybale_core.nodes.for_loop", "ForLoopNode")
    sink = _add(graph, f"{_BENCH}.bench_sink_node", "BenchSinkNode")
    body = _pass(graph)
    graph.create_edge_wrapper(begin.node_id, "exec", loop.node_id, "execute")
    graph.create_edge_wrapper(loop.node_id, "loop_body", sink.node_id, "exec_in")
    graph.create_edge_wrapper(loop.node_id, "index", body.node_id, "x")
    graph.create_edge_wrapper(body.node_id, "y", sink.node_id, "x")

    upstream = _localized(graph, sink).upstream

    assert _ids(upstream[body.node_id]) == [loop.node_id]
    assert _ids(upstream[sink.node_id]) == [body.node_id]


def test_a_control_node_without_data_inlets_has_no_sources(graph_with_library_system):
    graph = graph_with_library_system
    begin = _add(graph, "haybale_core.nodes.events.begin_play", "BeginPlayNode")
    loop = _add(graph, "haybale_core.nodes.for_loop", "ForLoopNode")
    graph.create_edge_wrapper(begin.node_id, "exec", loop.node_id, "execute")
    graph.force_validation()

    for flow in FlowAssemblyManager().assemble_graph(graph):
        info = flow.control_graph.get_node_info(loop.node_id) if flow.control_graph else None
        if info is not None:
            data_flow = info.localized_data_flow
            assert data_flow is None or data_flow.upstream.get(loop.node_id, ()) == ()
            return
    raise AssertionError("loop not in any flow")
