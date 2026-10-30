"""A worker exception is reported, retried next evaluation, and bails by the run policy (ADR 0066)."""

import importlib
from typing import Any, Callable, Optional

import pytest

from haywire.core.assembly.flow_assembly_manager import FlowAssemblyManager
from haywire.core.execution.event_source import Trigger
from haywire.core.execution.execution_context import ExecutionContext
from haywire.core.execution.vm import HaywireVM
from tests.conftest import make_node

pytestmark = pytest.mark.integration

_BENCH = "haybale_testing.nodes.benchmark"


def _add(graph: Any, module: str, name: str) -> Any:
    cls = getattr(importlib.import_module(module), name)
    wrapper = make_node(graph, cls.class_identity.registry_key, position=(0, 0))
    assert isinstance(wrapper.node, cls), "an unknown key yields an ErrorNode"
    return wrapper.node


def _begin(graph: Any) -> Any:
    return _add(graph, "haybale_core.nodes.events.begin_play", "BeginPlayNode")


def _loop(graph: Any) -> Any:
    return _add(graph, "haybale_core.nodes.for_loop", "ForLoopNode")


def _sink(graph: Any) -> Any:
    return _add(graph, f"{_BENCH}.bench_sink_node", "BenchSinkNode")


def _pass(graph: Any) -> Any:
    return _add(graph, f"{_BENCH}.bench_data_pass_node", "BenchDataPassNode")


def _odd_raiser(graph: Any) -> Any:
    """Raises on odd ``x``, passes even ``x`` to ``y``."""
    return _add(graph, f"{_BENCH}.bench_loop_raise_node", "BenchLoopRaiseNode")


def _edge(graph: Any, src: Any, outlet: str, dst: Any, inlet: str) -> None:
    graph.create_edge_wrapper(src.node_id, outlet, dst.node_id, inlet)


def _record_runs(node: Any) -> list:
    """Replace ``node``'s worker with one that records the ``x`` it ran with."""
    seen: list = []

    def worker(context: Any, x: float) -> None:
        seen.append(x)

    node.worker = worker
    return seen


class _Runner:
    """Assembles a graph once and fires its flows on one VM, keeping every frame's context."""

    def __init__(
        self,
        graph: Any,
        monkeypatch: Any,
        bail: Optional[str] = None,
        on_bail_run: Optional[Callable[[], None]] = None,
    ):
        graph.force_validation()
        self.flows = FlowAssemblyManager().assemble_graph(graph)
        self.vm = HaywireVM(
            exception_bail=(lambda: bail) if bail is not None else None,
            on_bail_run=on_bail_run,
        )
        self.contexts: list[ExecutionContext] = []
        original = HaywireVM._create_execution_context

        def capture(vm: Any, *args: Any, **kwargs: Any) -> ExecutionContext:
            ctx = original(vm, *args, **kwargs)
            self.contexts.append(ctx)
            return ctx

        monkeypatch.setattr(HaywireVM, "_create_execution_context", capture)

    def fire(self, entry: Any) -> ExecutionContext:
        flow = next(f for f in self.flows if f.get_entry_node_id() == entry.node_id)
        trigger = Trigger(source_key=flow.get_subscription_key(), payload={}, timestamp=0.0)
        self.vm.execute_control_flow(flow, trigger)
        return self.contexts[-1]


def _loop_graph(graph: Any) -> tuple[Any, Any, Any, list, list]:
    """BeginPlay → ForLoop(end=6); body: Sink fed by a node raising on odd indices; completed → After."""
    begin, loop, raiser, body, after = (
        _begin(graph),
        _loop(graph),
        _odd_raiser(graph),
        _sink(graph),
        _sink(graph),
    )
    _edge(graph, begin, "exec", loop, "execute")
    _edge(graph, loop, "loop_body", body, "exec_in")
    _edge(graph, loop, "index", raiser, "x")
    _edge(graph, raiser, "y", body, "x")
    _edge(graph, loop, "completed", after, "exec_in")
    loop.ports["end"].set_value(6)
    return begin, loop, raiser, _record_runs(body), _record_runs(after)


def test_branch_is_the_default_and_the_loop_goes_on(graph_with_library_system, monkeypatch):
    begin, _loop_node, raiser, body_runs, after_runs = _loop_graph(graph_with_library_system)
    run = _Runner(graph_with_library_system, monkeypatch)

    ctx = run.fire(begin)

    assert body_runs == [0.0, 2.0, 4.0]  # the failing iterations' body never ran on a stale value
    assert after_runs == [0.0]  # the loop completed
    assert [node.node_id for node, _ in ctx.failures] == [raiser.node_id] * 3
    assert all(isinstance(exc, Exception) for _, exc in ctx.failures)


def test_frame_ends_the_frame_at_the_first_exception(graph_with_library_system, monkeypatch):
    begin, _loop_node, raiser, body_runs, after_runs = _loop_graph(graph_with_library_system)
    run = _Runner(graph_with_library_system, monkeypatch, bail="frame")

    ctx = run.fire(begin)

    assert body_runs == [0.0]
    assert after_runs == []
    assert [node.node_id for node, _ in ctx.failures] == [raiser.node_id]


def test_run_ends_the_frame_and_asks_to_stop_the_run(graph_with_library_system, monkeypatch):
    begin, _loop_node, _raiser, body_runs, after_runs = _loop_graph(graph_with_library_system)
    stops: list[bool] = []
    run = _Runner(graph_with_library_system, monkeypatch, bail="run", on_bail_run=lambda: stops.append(True))

    run.fire(begin)

    assert body_runs == [0.0]
    assert after_runs == []
    assert stops == [True]


def test_an_unknown_policy_bails_the_branch(graph_with_library_system, monkeypatch):
    begin, _loop_node, _raiser, body_runs, _after = _loop_graph(graph_with_library_system)
    run = _Runner(graph_with_library_system, monkeypatch, bail="explode")

    run.fire(begin)

    assert body_runs == [0.0, 2.0, 4.0]


def test_a_raising_control_node_bails_by_the_policy(graph_with_library_system, monkeypatch):
    graph = graph_with_library_system
    begin, loop, body, after = _begin(graph), _loop(graph), _sink(graph), _sink(graph)
    _edge(graph, begin, "exec", loop, "execute")
    _edge(graph, loop, "loop_body", body, "exec_in")
    _edge(graph, loop, "completed", after, "exec_in")
    loop.ports["end"].set_value(3)
    calls = {"n": 0}

    def boom(context: Any, x: float) -> None:
        calls["n"] += 1
        raise RuntimeError("body failed")

    body.worker = boom
    after_runs = _record_runs(after)

    _Runner(graph, monkeypatch).fire(begin)
    assert (calls["n"], after_runs) == (3, [0.0])  # branch: every iteration tried, the loop completed

    calls["n"] = 0
    after_runs.clear()
    _Runner(graph, monkeypatch, bail="frame").fire(begin)
    assert (calls["n"], after_runs) == (1, [])


def test_a_failed_node_is_retried_without_an_edit(graph_with_library_system, monkeypatch):
    graph = graph_with_library_system
    begin, sink, source, middle = _begin(graph), _sink(graph), _pass(graph), _pass(graph)
    _edge(graph, begin, "exec", sink, "exec_in")
    _edge(graph, source, "y", middle, "x")
    _edge(graph, middle, "y", sink, "x")
    seen = _record_runs(sink)
    calls = {"n": 0}

    def flaky(context: Any, x: float) -> None:
        calls["n"] += 1
        if calls["n"] == 1:
            raise RuntimeError("out of memory")
        source.out("y", x)

    source.worker = flaky
    run = _Runner(graph, monkeypatch)
    source.ports["x"].set_value(4.0)

    run.fire(begin)
    run.fire(begin)  # nothing changed: the failed node's inlets were marked dirty again

    assert seen == [5.0]  # the retried source passes 4 on; the middle node adds 1
    assert calls["n"] == 2


def test_a_worker_error_is_cleared_at_the_start_of_the_next_frame(graph_with_library_system, monkeypatch):
    graph = graph_with_library_system
    begin, sink, raiser = _begin(graph), _sink(graph), _odd_raiser(graph)
    _edge(graph, begin, "exec", sink, "exec_in")
    _edge(graph, raiser, "y", sink, "x")
    run = _Runner(graph, monkeypatch)

    raiser.ports["x"].set_value(1.0)
    run.fire(begin)
    assert raiser.wrapper.state.error_runtime is not None

    raiser.ports["x"].set_value(3.0)
    run.fire(begin)
    assert raiser.wrapper.state.error_runtime is not None  # failed again in this frame

    raiser.ports["x"].set_value(2.0)
    run.fire(begin)
    assert raiser.wrapper.state.error_runtime is None


def test_a_frame_without_exceptions_records_no_failures(graph_with_library_system, monkeypatch):
    graph = graph_with_library_system
    begin, sink, raiser = _begin(graph), _sink(graph), _odd_raiser(graph)
    _edge(graph, begin, "exec", sink, "exec_in")
    _edge(graph, raiser, "y", sink, "x")
    seen = _record_runs(sink)
    raiser.ports["x"].set_value(2.0)

    ctx = _Runner(graph, monkeypatch).fire(begin)

    assert seen == [2.0]
    assert ctx.failures == []


def test_a_new_run_starts_without_the_last_runs_worker_errors(graph_with_library_system, monkeypatch):
    from haywire.core.execution.interpreter import Interpreter

    graph = graph_with_library_system
    begin, sink, raiser = _begin(graph), _sink(graph), _odd_raiser(graph)
    _edge(graph, begin, "exec", sink, "exec_in")
    _edge(graph, raiser, "y", sink, "x")
    raiser.ports["x"].set_value(1.0)
    _Runner(graph, monkeypatch).fire(begin)
    assert raiser.wrapper.state.error_runtime is not None

    interpreter = Interpreter()
    interpreter.load_graph(graph)
    monkeypatch.setattr(interpreter, "dispatch_system_event", lambda *_a, **_k: None)
    interpreter.start_execution()

    assert raiser.wrapper.state.error_runtime is None
    interpreter._executing = False
