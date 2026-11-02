"""A data node runs its worker at least once per instance, then only while a port is dirty (ADR 0070)."""

import importlib
import json
import threading
from typing import Any
from unittest.mock import MagicMock

import pytest

from haywire.core.assembly.flow_assembly_manager import FlowAssemblyManager
from haywire.core.execution.event_source import Trigger
from haywire.core.execution.vm import HaywireVM
from haywire.core.graph.base import BaseGraph
from haywire.core.graph.scheduler import SyncScheduler
from tests.conftest import make_node

pytestmark = pytest.mark.integration

_BENCH = "haybale_testing.nodes.benchmark"


def _add(graph: Any, module: str, name: str) -> Any:
    cls = getattr(importlib.import_module(module), name)
    wrapper = make_node(graph, cls.class_identity.registry_key, position=(0, 0))
    assert isinstance(wrapper.node, cls), "an unknown key yields an ErrorNode"
    return wrapper.node


def _node_of(graph: Any, node_id: str) -> Any:
    wrapper = graph.get_node_wrapper(node_id)
    assert wrapper is not None
    return wrapper.node


def test_a_fresh_data_node_runs_once_then_waits_for_a_dirty_port(graph_with_library_system):
    node = _add(graph_with_library_system, f"{_BENCH}.bench_data_pass_node", "BenchDataPassNode")
    node.ports["x"].set_value(2.0)
    node._has_dirty_ports.clear()  # a fresh node: nothing but the first run is owed
    context = MagicMock()

    assert node._execute(context) is None
    assert node.ports["y"].get_value() == 3.0

    node.ports["y"].set_value(-1.0)  # a second run would overwrite this
    node._execute(context)
    assert node.ports["y"].get_value() == -1.0

    node.ports["x"].set_value(5.0)
    node._execute(context)
    assert node.ports["y"].get_value() == 6.0


def test_run_again_makes_a_clean_data_node_run_once_more(graph_with_library_system):
    node = _add(graph_with_library_system, f"{_BENCH}.bench_data_pass_node", "BenchDataPassNode")
    node.ports["x"].set_value(2.0)
    node._has_dirty_ports.clear()
    context = MagicMock()
    node._execute(context)

    node.ports["y"].set_value(-1.0)
    node.run_again()
    node._execute(context)
    assert node.ports["y"].get_value() == 3.0

    node.ports["y"].set_value(-1.0)  # the extra run is owed once only
    node._execute(context)
    assert node.ports["y"].get_value() == -1.0


def test_a_first_run_that_raises_runs_again_without_a_dirty_port(graph_with_library_system):
    node = _add(graph_with_library_system, f"{_BENCH}.bench_data_pass_node", "BenchDataPassNode")
    node._has_dirty_ports.clear()  # no dirty inlet, as for a node with no data inlets
    real = node.worker
    calls: list[int] = []

    def flaky(context: Any, x: float) -> None:
        calls.append(1)
        if len(calls) == 1:
            raise RuntimeError("first run fails")
        real(context, x)

    node.worker = flaky
    context = MagicMock()

    with pytest.raises(RuntimeError):
        node._execute(context)
    assert node._has_run is False

    node._has_dirty_ports.clear()
    node._execute(context)
    assert len(calls) == 2
    assert node.ports["y"].get_value() == 1.0
    assert node._has_run is True


def test_a_loaded_data_node_computes_on_its_first_run(graph_with_library_system, monkeypatch):
    graph = graph_with_library_system
    begin = _add(graph, "haybale_core.nodes.events.begin_play", "BeginPlayNode")
    compute = _add(graph, f"{_BENCH}.bench_data_pass_node", "BenchDataPassNode")
    printer = _add(graph, "haybale_core.nodes.print", "PrintNode")
    graph.create_edge_wrapper(begin.node_id, "exec", printer.node_id, "exec")
    graph.create_edge_wrapper(compute.node_id, "y", printer.node_id, "message")
    compute.ports["x"].set_value(4.0)

    saved = json.loads(json.dumps(graph.to_dict(include_data=True)))
    loaded = BaseGraph(filestem="Loaded", validation_scheduler=SyncScheduler())
    assert loaded.load_from_dict(saved)
    begin = _node_of(loaded, begin.node_id)
    compute = _node_of(loaded, compute.node_id)
    printer = _node_of(loaded, printer.node_id)
    assert compute._has_run is False

    seen: list[Any] = []

    def record(context: Any) -> str:
        seen.append(printer.value("message"))
        return "done"

    monkeypatch.setattr(printer, "worker", record)
    loaded.force_validation()
    flows = FlowAssemblyManager().assemble_graph(loaded)
    flow = next(f for f in flows if f.get_entry_node_id() == begin.node_id)
    trigger = Trigger(source_key=flow.get_subscription_key(), payload={}, timestamp=0.0)
    runner = threading.Thread(target=lambda: HaywireVM().execute_control_flow(flow, trigger))
    runner.start()
    runner.join()

    assert seen == ["5.0"], seen
    assert compute._has_run is True
