"""Consumers of a failed node are blocked instead of running on its stale outlet (ADR 0066)."""

import importlib
from typing import Any

import pytest

from haywire.core.assembly.flow_assembly_manager import FlowAssemblyManager
from haywire.core.execution.event_source import Trigger
from haywire.core.execution.execution_context import ExecutionContext
from haywire.core.execution.vm import HaywireVM
from haywire.core.execution.failures import failure_counts
from tests.conftest import make_node

pytestmark = pytest.mark.integration


@pytest.fixture(autouse=True)
def _release_failures(graph_with_library_system):
    """Clear every node's failed/blocked state after a test: the test graph is not cleaned up."""
    before = (failure_counts.failed, failure_counts.flagged)
    yield
    for wrapper in list(graph_with_library_system.node_wrappers.values()):
        if not wrapper.is_cleaned_up:
            wrapper.node._clear_failed()
            wrapper.node._clear_blocked()
    assert (failure_counts.failed, failure_counts.flagged) == before


_BENCH = "haybale_testing.nodes.benchmark"


def _add(graph: Any, module: str, name: str) -> Any:
    cls = getattr(importlib.import_module(module), name)
    wrapper = make_node(graph, cls.class_identity.registry_key, position=(0, 0))
    assert isinstance(wrapper.node, cls), "an unknown key yields an ErrorNode"
    return wrapper.node


def _begin(graph: Any) -> Any:
    return _add(graph, "haybale_core.nodes.events.begin_play", "BeginPlayNode")


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
    """Assembles a graph once and fires its flows, keeping every frame's context."""

    def __init__(self, graph: Any, monkeypatch: Any):
        graph.force_validation()
        self.flows = FlowAssemblyManager().assemble_graph(graph)
        self.vm = HaywireVM()
        self.contexts: list[ExecutionContext] = []
        original = HaywireVM._create_execution_context

        def capture(vm: Any, *args: Any, **kwargs: Any) -> ExecutionContext:
            ctx = original(vm, *args, **kwargs)
            self.contexts.append(ctx)
            return ctx

        monkeypatch.setattr(HaywireVM, "_create_execution_context", capture)

    def fire(self, entry: Any) -> ExecutionContext:
        flow = next(f for f in self.flows if f.get_entry_node_id() == entry.node_id)
        self.vm.execute_control_flow(
            flow, Trigger(source_key=flow.get_subscription_key(), payload={}, timestamp=0.0)
        )
        return self.contexts[-1]


def _warnings(node: Any, kind: str = "blocked") -> list[str]:
    return [w.message for w in node.wrapper.state.warnings if w.kind == kind]


@pytest.fixture
def count_before():
    return failure_counts.failed


def _chain(graph: Any) -> tuple[Any, Any, Any, Any]:
    """BeginPlay → Sink, data: Raiser → Pass → Sink."""
    begin, sink, raiser, middle = _begin(graph), _sink(graph), _odd_raiser(graph), _pass(graph)
    _edge(graph, begin, "exec", sink, "exec_in")
    _edge(graph, raiser, "y", middle, "x")
    _edge(graph, middle, "y", sink, "x")
    return begin, sink, raiser, middle


def test_a_consumer_never_runs_on_the_stale_value(graph_with_library_system, monkeypatch, count_before):
    begin, sink, raiser, _middle = _chain(graph_with_library_system)
    seen = _record_runs(sink)
    run = _Runner(graph_with_library_system, monkeypatch)

    for frame in (40.0, 41.0, 42.0):
        raiser.ports["x"].set_value(frame)
        run.fire(begin)

    # Frame 41 failed: the sink did not run on frame 40's value again (the img_042 bug).
    assert seen == [41.0, 43.0]


def test_blocking_is_transitive_and_recovers(graph_with_library_system, monkeypatch, count_before):
    begin, sink, raiser, middle = _chain(graph_with_library_system)
    _record_runs(sink)
    run = _Runner(graph_with_library_system, monkeypatch)

    raiser.ports["x"].set_value(1.0)
    run.fire(begin)

    assert raiser.failed
    label = raiser.identity.label
    assert _warnings(middle) == [f"skipped: {label} failed"]
    assert _warnings(sink) == [f"skipped: {label} failed"]

    raiser.ports["x"].set_value(2.0)
    run.fire(begin)

    assert not raiser.failed
    assert _warnings(middle) == []
    assert _warnings(sink) == []
    assert middle.ports["y"].get_value() == 3.0


def test_a_transient_failure_recovers_without_an_edit(graph_with_library_system, monkeypatch, count_before):
    begin, sink, raiser, _middle = _chain(graph_with_library_system)
    seen = _record_runs(sink)
    calls = {"n": 0}

    def flaky(context: Any, x: float) -> None:
        calls["n"] += 1
        if calls["n"] == 1:
            raise RuntimeError("out of memory")
        raiser.out("y", x)

    raiser.worker = flaky
    run = _Runner(graph_with_library_system, monkeypatch)
    raiser.ports["x"].set_value(4.0)

    run.fire(begin)
    run.fire(begin)  # nothing changed: the failed node is still dirty and retries

    assert seen == [5.0]
    assert not raiser.failed


def test_a_poisoned_control_node_skips_its_worker_and_the_loop_goes_on(
    graph_with_library_system, monkeypatch, count_before
):
    graph = graph_with_library_system
    begin = _begin(graph)
    loop = _add(graph, "haybale_core.nodes.for_loop", "ForLoopNode")
    raiser, sink = _odd_raiser(graph), _sink(graph)
    _edge(graph, begin, "exec", loop, "execute")
    _edge(graph, loop, "loop_body", sink, "exec_in")
    _edge(graph, loop, "index", raiser, "x")
    _edge(graph, raiser, "y", sink, "x")
    loop.ports["end"].set_value(6)
    seen = _record_runs(sink)
    run = _Runner(graph, monkeypatch)

    ctx = run.fire(begin)

    assert seen == [0.0, 2.0, 4.0]
    raised = [entry for entry in ctx.failures if entry[1] != "blocked"]
    blocked = [entry for entry in ctx.failures if entry[1] == "blocked"]
    assert [node_id for node_id, _ in raised] == [raiser.node_id] * 3
    assert blocked == [(sink.node_id, "blocked")] * 3
    assert raiser.failed  # index 5 was the last run, and it failed
    raiser._clear_failed()


def test_a_failed_control_node_poisons_its_data_outlet(graph_with_library_system, monkeypatch, count_before):
    graph = graph_with_library_system
    first, second = _begin(graph), _begin(graph)
    loop = _add(graph, "haybale_core.nodes.for_loop", "ForLoopNode")
    middle, sink = _pass(graph), _sink(graph)
    _edge(graph, first, "exec", loop, "execute")
    _edge(graph, second, "exec", sink, "exec_in")
    _edge(graph, loop, "index", middle, "x")
    _edge(graph, middle, "y", sink, "x")

    def write_then_raise(context: Any) -> None:
        loop.out("index", 7)
        raise RuntimeError("after writing")

    loop.worker = write_then_raise
    seen = _record_runs(sink)
    run = _Runner(graph, monkeypatch)

    run.fire(first)
    ctx = run.fire(second)

    assert loop.failed
    assert seen == []
    assert (sink.node_id, "blocked") in ctx.failures
    loop._clear_failed()


def test_a_failure_does_not_poison_through_exec_edges(graph_with_library_system, monkeypatch, count_before):
    graph = graph_with_library_system
    begin = _begin(graph)
    loop = _add(graph, "haybale_core.nodes.for_loop", "ForLoopNode")
    failing, after = _sink(graph), _sink(graph)
    clean = _pass(graph)
    _edge(graph, begin, "exec", loop, "execute")
    _edge(graph, loop, "loop_body", failing, "exec_in")
    _edge(graph, loop, "completed", after, "exec_in")
    _edge(graph, clean, "y", after, "x")
    loop.ports["end"].set_value(1)

    def boom(context: Any, x: float) -> None:
        raise RuntimeError("body failed")

    failing.worker = boom
    seen = _record_runs(after)
    run = _Runner(graph, monkeypatch)
    clean.ports["x"].set_value(1.0)

    run.fire(begin)

    assert failing.failed
    assert seen == [2.0]
    failing._clear_failed()


def test_the_happy_path_never_reads_the_sources(graph_with_library_system, monkeypatch, count_before):
    begin, sink, raiser, _middle = _chain(graph_with_library_system)
    run = _Runner(graph_with_library_system, monkeypatch)

    class _Untouchable(dict):
        def get(self, *args: Any) -> Any:
            raise AssertionError("upstream read while nothing failed")

        __getitem__ = get

    for flow in run.flows:
        assert flow.control_graph is not None
        for info in flow.control_graph.control_nodes.values():
            if info.localized_data_flow is not None:
                info.localized_data_flow.upstream = _Untouchable()
    assert failure_counts.flagged == 0
    raiser.ports["x"].set_value(2.0)

    run.fire(begin)


def test_a_blocked_control_node_poisons_its_data_outlet(
    graph_with_library_system, monkeypatch, count_before
):
    graph = graph_with_library_system
    first, second = _begin(graph), _begin(graph)
    loop = _add(graph, "haybale_core.nodes.for_loop", "ForLoopNode")
    raiser, middle, sink = _odd_raiser(graph), _pass(graph), _sink(graph)
    _edge(graph, first, "exec", loop, "execute")
    _edge(graph, raiser, "y", loop, "end")
    _edge(graph, second, "exec", sink, "exec_in")
    _edge(graph, loop, "index", middle, "x")
    _edge(graph, middle, "y", sink, "x")
    seen = _record_runs(sink)
    run = _Runner(graph, monkeypatch)
    raiser.ports["x"].set_value(1.0)

    run.fire(first)  # the raiser fails, so the loop is blocked and never writes its index
    ctx = run.fire(second)

    assert loop.blocked
    assert seen == []
    assert (sink.node_id, "blocked") in ctx.failures


def test_a_shared_node_is_cleared_before_its_lock_is_released(graph_with_library_system, monkeypatch):
    raiser = _odd_raiser(graph_with_library_system)
    raiser.ports["x"].set_value(1.0)
    vm = HaywireVM()
    ctx = ExecutionContext(global_ctx={}, local_ctx={})
    assert vm._execute_shared_data_node(raiser, ctx) is False
    assert raiser.failed

    lock = raiser.wrapper.exec_lock
    seen_at_release: list[bool] = []
    real_release = lock.release

    class _Spy:
        def __getattr__(self, name: str) -> Any:
            return getattr(lock, name)

        def release(self) -> None:
            seen_at_release.append(raiser.failed)
            real_release()

    monkeypatch.setattr(raiser.wrapper, "exec_lock", _Spy())
    raiser.ports["x"].set_value(2.0)

    assert vm._execute_shared_data_node(raiser, ctx) is True
    # Another group taking the lock after this point must already see the node as recovered.
    assert seen_at_release == [False]


def test_removing_a_failed_node_releases_the_counts(graph_with_library_system, monkeypatch, count_before):
    begin, _sink_node, raiser, middle = _chain(graph_with_library_system)
    run = _Runner(graph_with_library_system, monkeypatch)
    raiser.ports["x"].set_value(1.0)
    run.fire(begin)
    assert failure_counts.flagged > 0

    graph_with_library_system.remove_node_wrapper(middle.wrapper)
    graph_with_library_system.remove_node_wrapper(raiser.wrapper)
    graph_with_library_system.remove_node_wrapper(_sink_node.wrapper)

    assert (raiser.failed, middle.blocked) == (False, False)
    assert failure_counts.flagged == 0
