"""For Loop: Break ends the loop through Stopped, running out ends it through Completed."""

import importlib
from typing import Any

import pytest

from haywire.core.assembly.flow_assembly_manager import FlowAssemblyManager
from haywire.core.execution.event_source import Trigger
from haywire.core.execution.vm import HaywireVM
from tests.conftest import make_node

pytestmark = pytest.mark.integration


def _add(graph: Any, module: str, name: str) -> Any:
    cls = getattr(importlib.import_module(module), name)
    wrapper = make_node(graph, cls.class_identity.registry_key, position=(0, 0))
    assert isinstance(wrapper.node, cls), "an unknown key yields an ErrorNode"
    return wrapper.node


def _run(graph: Any, wire_break: bool, monkeypatch: Any) -> tuple[list[str], Any, Any, Any]:
    begin = _add(graph, "haybale_core.nodes.events.begin_play", "BeginPlayNode")
    loop = _add(graph, "haybale_core.nodes.for_loop", "ForLoopNode")
    body = _add(graph, "haybale_core.nodes.print", "PrintNode")
    completed = _add(graph, "haybale_core.nodes.print", "PrintNode")
    stopped = _add(graph, "haybale_core.nodes.print", "PrintNode")
    graph.create_edge_wrapper(begin.node_id, "exec", loop.node_id, "execute")
    graph.create_edge_wrapper(loop.node_id, "loop_body", body.node_id, "exec")
    if wire_break:
        graph.create_edge_wrapper(body.node_id, "done", loop.node_id, "break_loop")
    graph.create_edge_wrapper(loop.node_id, "completed", completed.node_id, "exec")
    graph.create_edge_wrapper(loop.node_id, "stopped", stopped.node_id, "exec")
    loop.ports["end"].set_value(5)

    runs: list[str] = []
    for node in (body, completed, stopped):
        original = node._execute

        def recording(context: Any, _node: Any = node, _original: Any = original) -> Any:
            runs.append(_node.node_id)
            return _original(context)

        monkeypatch.setattr(node, "_execute", recording)

    graph.force_validation()
    flow = next(
        f for f in FlowAssemblyManager().assemble_graph(graph) if f.get_entry_node_id() == begin.node_id
    )
    HaywireVM().execute_control_flow(
        flow, Trigger(source_key=flow.get_subscription_key(), payload={}, timestamp=0.0)
    )
    return runs, body, completed, stopped


def test_running_out_fires_completed(graph_with_library_system, monkeypatch):
    runs, body, completed, stopped = _run(graph_with_library_system, False, monkeypatch)

    assert runs.count(body.node_id) == 5
    assert runs.count(completed.node_id) == 1
    assert runs.count(stopped.node_id) == 0


def test_break_from_the_body_fires_stopped(graph_with_library_system, monkeypatch):
    runs, body, completed, stopped = _run(graph_with_library_system, True, monkeypatch)

    assert runs.count(body.node_id) == 1
    assert runs.count(completed.node_id) == 0
    assert runs.count(stopped.node_id) == 1
