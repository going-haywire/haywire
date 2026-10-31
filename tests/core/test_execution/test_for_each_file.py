"""For Each File: a loop over a folder's files that records the files whose iteration failed (ADR 0066)."""

import importlib
from typing import Any, Callable, Optional

import pytest

from haywire.barn.builtin.types import PROGRESS
from haywire.core.assembly.flow_assembly_manager import FlowAssemblyManager
from haywire.core.execution.event_source import Trigger
from haywire.core.execution.execution_context import ExecutionContext
from haywire.core.execution.vm import HaywireVM
from haywire.core.volumes import VolumePath, VolumeUndefinedError, get_volume_store
from tests.conftest import make_node

pytestmark = pytest.mark.integration

SCANS = "user:volume:scans"


def _add(graph: Any, module: str, name: str) -> Any:
    cls = getattr(importlib.import_module(module), name)
    wrapper = make_node(graph, cls.class_identity.registry_key, position=(0, 0))
    assert isinstance(wrapper.node, cls), "an unknown key yields an ErrorNode"
    return wrapper.node


def _edge(graph: Any, src: Any, outlet: str, dst: Any, inlet: str) -> None:
    graph.create_edge_wrapper(src.node_id, outlet, dst.node_id, inlet)


class _Runner:
    """Assembles a graph once and fires its flows on one VM, keeping every frame's context."""

    def __init__(self, graph: Any, monkeypatch: Any, bail: Optional[str] = None):
        graph.force_validation()
        self.flows = FlowAssemblyManager().assemble_graph(graph)
        self.vm = HaywireVM(exception_bail=(lambda: bail) if bail is not None else None)
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


class _Batch:
    """BeginPlay → For Each File; body: a sink that records the path; completed and stopped → sinks."""

    def __init__(self, graph: Any):
        self.begin = _add(graph, "haybale_core.nodes.events.begin_play", "BeginPlayNode")
        self.each = _add(graph, "haybale_core.nodes.for_each_file", "ForEachFileNode")
        sink = ("haybale_testing.nodes.benchmark.bench_sink_node", "BenchSinkNode")
        self.body, self.after, self.halt = _add(graph, *sink), _add(graph, *sink), _add(graph, *sink)
        _edge(graph, self.begin, "exec", self.each, "execute")
        _edge(graph, self.each, "loop_body", self.body, "exec_in")
        _edge(graph, self.each, "completed", self.after, "exec_in")
        _edge(graph, self.each, "stopped", self.halt, "exec_in")
        self.each.ports["folder"].set_value(VolumePath(SCANS, ""))
        self.each.ports["pattern"].set_value("*.png")
        self.each.ports["recursive"].set_value(True)
        self.seen: list[tuple[str, str, int, int]] = []
        self.completed: list[list[VolumePath]] = []
        self.stopped: list[list[VolumePath]] = []
        self.fail_on: set[str] = set()
        self.body.worker = self._body
        self.after.worker = lambda context, x: self.completed.append(self.each.ports["failed"].get_value())
        self.halt.worker = lambda context, x: self.stopped.append(self.each.ports["failed"].get_value())

    def _body(self, context: Any, x: float) -> None:
        port: Callable[[str], Any] = lambda pid: self.each.ports[pid].get_value()  # noqa: E731
        path = port("path")
        self.seen.append((path.relative, port("subdir"), port("index"), port("total")))
        if path.relative in self.fail_on:
            raise RuntimeError(f"cannot process {path.relative}")


@pytest.fixture
def scans(tmp_path):
    for name in ("a.png", "b.png", "sub/c.png", "d.txt"):
        path = tmp_path / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(b"x")
    get_volume_store().add(SCANS, label="Scans", description="", location=tmp_path)
    return tmp_path


def test_iterates_matching_files_in_order(graph_with_library_system, monkeypatch, scans):
    batch = _Batch(graph_with_library_system)

    _Runner(graph_with_library_system, monkeypatch).fire(batch.begin)

    assert batch.seen == [("a.png", "", 0, 3), ("b.png", "", 1, 3), ("sub/c.png", "sub", 2, 3)]
    assert batch.completed == [[]]
    assert batch.each.ports["stem"].get_value() == "c"
    assert batch.each.ports["extension"].get_value() == ".png"


def test_limit(graph_with_library_system, monkeypatch, scans):
    batch = _Batch(graph_with_library_system)
    batch.each.ports["limit"].set_value(2)

    _Runner(graph_with_library_system, monkeypatch).fire(batch.begin)

    assert [s[0] for s in batch.seen] == ["a.png", "b.png"]
    assert batch.seen[-1][3] == 2
    assert len(batch.completed) == 1


def test_continue_records_failed_and_goes_on(graph_with_library_system, monkeypatch, scans):
    batch = _Batch(graph_with_library_system)
    batch.fail_on = {"b.png"}

    _Runner(graph_with_library_system, monkeypatch).fire(batch.begin)

    assert [s[0] for s in batch.seen] == ["a.png", "b.png", "sub/c.png"]
    assert batch.completed == [[VolumePath(SCANS, "b.png")]]


def test_stop_ends_at_first_failure(graph_with_library_system, monkeypatch, scans):
    batch = _Batch(graph_with_library_system)
    batch.fail_on = {"b.png"}
    batch.each.ports["on_error"].set_value("stop")

    _Runner(graph_with_library_system, monkeypatch).fire(batch.begin)

    assert [s[0] for s in batch.seen] == ["a.png", "b.png"]
    assert batch.completed == []
    assert batch.stopped == [[VolumePath(SCANS, "b.png")]]


def test_frame_bail_abandons_and_closes_progress(graph_with_library_system, monkeypatch, scans):
    batch = _Batch(graph_with_library_system)
    batch.fail_on = {"b.png"}

    _Runner(graph_with_library_system, monkeypatch, bail="frame").fire(batch.begin)

    assert [s[0] for s in batch.seen] == ["a.png", "b.png"]
    assert batch.completed == []
    assert batch.each.progress.main == PROGRESS()


def test_progress_is_idle_after_completion(graph_with_library_system, monkeypatch, scans):
    batch = _Batch(graph_with_library_system)

    _Runner(graph_with_library_system, monkeypatch).fire(batch.begin)

    assert batch.each.progress.main == PROGRESS()


def test_break_from_the_body_stops_the_loop(graph_with_library_system, monkeypatch, scans):
    graph = graph_with_library_system
    batch = _Batch(graph)
    body_edge = next(
        eid
        for eid, e in graph.edge_wrappers.items()
        if e.source_node_id == batch.each.node_id and "loop_body" in eid
    )
    graph.remove_edge_wrapper(body_edge)
    breaker = _add(graph, "haybale_core.nodes.print", "PrintNode")
    _edge(graph, batch.each, "loop_body", breaker, "exec")
    _edge(graph, breaker, "done", batch.each, "break_loop")

    _Runner(graph, monkeypatch).fire(batch.begin)

    assert batch.each.ports["index"].get_value() == 0
    assert batch.completed == []
    assert batch.stopped == [[]]


def test_second_run_starts_fresh(graph_with_library_system, monkeypatch, scans):
    batch = _Batch(graph_with_library_system)
    run = _Runner(graph_with_library_system, monkeypatch)
    batch.fail_on = {"b.png"}
    run.fire(batch.begin)

    batch.fail_on = set()
    batch.seen.clear()
    run.fire(batch.begin)

    assert batch.seen[0][2] == 0
    assert batch.completed[-1] == []


@pytest.mark.parametrize(
    ("folder", "error"),
    [
        (VolumePath("user:volume:nowhere", ""), VolumeUndefinedError),
        (VolumePath(SCANS, "missing"), NotADirectoryError),
        (VolumePath(SCANS, "a.png"), NotADirectoryError),
    ],
)
def test_unlistable_folder_raises(graph_with_library_system, monkeypatch, scans, folder, error):
    batch = _Batch(graph_with_library_system)
    batch.each.ports["folder"].set_value(folder)

    ctx = _Runner(graph_with_library_system, monkeypatch).fire(batch.begin)

    assert batch.seen == []
    assert [(node, type(exc)) for node, exc in ctx.failures] == [(batch.each, error)]
