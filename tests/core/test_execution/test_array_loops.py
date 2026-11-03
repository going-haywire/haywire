"""List Files, Loop Array and Step Array: list a folder, then go through the list at once or step by step."""

import importlib
from typing import Any, Optional

import pytest

from haywire.core.assembly.flow_assembly_manager import FlowAssemblyManager
from haywire.core.execution.event_source import Trigger
from haywire.core.execution.vm import HaywireVM
from haywire.core.volumes import VolumePath, get_volume_store
from tests.conftest import make_node

pytestmark = pytest.mark.integration

SCANS = "user:volume:scans"
SINK = ("haybale_testing.nodes.benchmark.bench_sink_node", "BenchSinkNode")


def _add(graph: Any, module: str, name: str) -> Any:
    cls = getattr(importlib.import_module(module), name)
    wrapper = make_node(graph, cls.class_identity.registry_key, position=(0, 0))
    assert isinstance(wrapper.node, cls), "an unknown key yields an ErrorNode"
    return wrapper.node


def _edge(graph: Any, src: Any, outlet: str, dst: Any, inlet: str) -> None:
    graph.create_edge_wrapper(src.node_id, outlet, dst.node_id, inlet)


class _Runner:
    """Assembles a graph once and fires its flows on one VM."""

    def __init__(self, graph: Any, bail: Optional[str] = None):
        graph.force_validation()
        self.flows = FlowAssemblyManager().assemble_graph(graph)
        self.vm = HaywireVM(exception_bail=(lambda: bail) if bail is not None else None)

    def fire(self, entry: Any, times: int = 1) -> None:
        flow = next(f for f in self.flows if f.get_entry_node_id() == entry.node_id)
        for _ in range(times):
            trigger = Trigger(source_key=flow.get_subscription_key(), payload={}, timestamp=0.0)
            self.vm.execute_control_flow(flow, trigger)


@pytest.fixture
def scans(tmp_path):
    for name in ("a.png", "b.png", "sub/c.png", "d.txt"):
        path = tmp_path / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(b"x")
    get_volume_store().add(SCANS, label="Scans", description="", location=tmp_path)
    return tmp_path


def _list_files(graph: Any, pattern: str = "*.png") -> Any:
    lister = _add(graph, "haybale_core.nodes.list_files", "ListFilesNode")
    lister.ports["folder"].set_value(VolumePath(SCANS, ""))
    lister.listing.pattern = pattern
    lister.listing.recursive = True
    return lister


# ---------------------------------------------------------------- List Files


def test_list_files_shows_only_pattern_on_a_new_card(graph_with_library_system):
    from haywire.core.types.enums import PortType

    lister = _add(graph_with_library_system, "haybale_core.nodes.list_files", "ListFilesNode")

    kinds = {pid: lister.ports[pid].port_type for pid in lister.ports if pid.startswith("listing.")}
    assert kinds == {"listing.pattern": PortType.CONFIG}


def test_list_files_takes_a_promoted_pattern_from_an_edge(graph_with_library_system, scans):
    from haywire.core.node.promotion import demote_setting, promote_setting
    from haywire.core.types.enums import PortType

    graph = graph_with_library_system
    lister = _list_files(graph)
    demote_setting(lister, "listing.pattern")
    promote_setting(lister, "listing", "pattern", PortType.INLET)
    source = _add(graph, "haybale_core.nodes.split_path", "SplitPathNode")
    graph.create_edge_wrapper(source.node_id, "extension", lister.node_id, "listing.pattern")
    source.ports["extension"].set_value("*.txt")
    lister.ports["listing.pattern"].resolve_dirty_data()

    lister.worker(None)

    assert [p.relative for p in lister.ports["files"].get_value()] == ["d.txt"]


def test_list_files_saves_its_options_but_never_the_total(graph_with_library_system, scans):
    lister = _list_files(graph_with_library_system)
    lister.worker(None)

    values = lister.listing._to_dict()["values"]

    assert values == {"pattern": "*.png", "recursive": True}


def test_list_files_lists_paths_in_name_order(graph_with_library_system, scans):
    lister = _list_files(graph_with_library_system)

    assert lister.worker(None) == "next"

    assert [p.relative for p in lister.ports["files"].get_value()] == ["a.png", "b.png", "sub/c.png"]
    assert lister.listing.total == 3


def test_list_files_paths_keep_the_folder(graph_with_library_system, scans):
    (scans / "sub" / "d.png").write_bytes(b"x")
    lister = _list_files(graph_with_library_system)
    lister.ports["folder"].set_value(VolumePath(SCANS, "sub"))

    lister.worker(None)

    assert lister.ports["files"].get_value() == [
        VolumePath(SCANS, "sub/c.png"),
        VolumePath(SCANS, "sub/d.png"),
    ]
    assert {p.base for p in lister.ports["files"].get_value()} == {"sub"}


def test_list_files_limit(graph_with_library_system, scans):
    lister = _list_files(graph_with_library_system)
    lister.listing.limit = 2

    lister.worker(None)

    assert lister.listing.total == 2


def test_list_files_reads_the_folder_on_every_run(graph_with_library_system, scans):
    lister = _list_files(graph_with_library_system)
    lister.worker(None)
    (scans / "e.png").write_bytes(b"x")

    lister.worker(None)

    assert lister.listing.total == 4


def test_list_files_missing_folder_raises(graph_with_library_system, scans):
    lister = _list_files(graph_with_library_system)
    lister.ports["folder"].set_value(VolumePath(SCANS, "nope"))

    with pytest.raises(NotADirectoryError, match="does not exist"):
        lister.worker(None)


# ---------------------------------------------------------------- Loop Array


class _Loop:
    """BeginPlay → List Files → Loop Array; body, completed and stopped → sinks."""

    def __init__(self, graph: Any):
        self.begin = _add(graph, "haybale_core.nodes.events.begin_play", "BeginPlayNode")
        self.lister = _list_files(graph)
        self.loop = _add(graph, "haybale_core.nodes.loop_array", "LoopArrayNode")
        self.body, self.after, self.halt = _add(graph, *SINK), _add(graph, *SINK), _add(graph, *SINK)
        _edge(graph, self.begin, "exec", self.lister, "execute")
        _edge(graph, self.lister, "next", self.loop, "execute")
        _edge(graph, self.lister, "files", self.loop, "array")
        _edge(graph, self.loop, "loop_body", self.body, "exec_in")
        _edge(graph, self.loop, "completed", self.after, "exec_in")
        _edge(graph, self.loop, "stopped", self.halt, "exec_in")
        self.seen: list[tuple[str, int, int]] = []
        self.completed: list[list[Any]] = []
        self.stopped: list[list[Any]] = []
        self.fail_on: set[str] = set()
        self.body.worker = self._body
        self.after.worker = lambda context, x: self.completed.append(self.loop.ports["failed"].get_value())
        self.halt.worker = lambda context, x: self.stopped.append(self.loop.ports["failed"].get_value())

    def _body(self, context: Any, x: float) -> None:
        item = self.loop.ports["item"].get_value()
        self.seen.append(
            (item.relative, self.loop.ports["index"].get_value(), self.loop.ports["total"].get_value())
        )
        if item.relative in self.fail_on:
            raise RuntimeError(f"cannot process {item.relative}")


def test_loop_array_takes_its_types_from_the_wired_array(graph_with_library_system, scans):
    from haybale_core.types import ArrayType
    from haywire.barn.builtin.types import FILE_PATH

    loop = _Loop(graph_with_library_system).loop

    assert issubclass(loop.ports["array"].type_cls, ArrayType)
    assert loop.ports["array"].type_cls.element_type_cls is FILE_PATH
    assert loop.ports["item"].type_cls is FILE_PATH
    assert loop.ports["failed"].type_cls.element_type_cls is FILE_PATH


def test_loop_array_keeps_its_types_through_save_and_load(graph_with_library_system, scans, tmp_path):
    from haywire.barn.builtin.types import FILE_PATH
    from haywire.core.graph.base import BaseGraph
    from haywire.core.graph.scheduler import SyncScheduler

    loop = _Loop(graph_with_library_system).loop
    path = tmp_path / "loop.haywire"
    assert graph_with_library_system.save_to_file(str(path))

    reloaded = BaseGraph(filestem="loop", validation_scheduler=SyncScheduler())
    assert reloaded.load_from_file(str(path))
    reloaded.force_validation()

    wrapper = reloaded.get_node_wrapper(loop.node_id)
    assert wrapper is not None
    node = wrapper.node
    assert node.ports["item"].type_cls is FILE_PATH
    assert node.ports["array"].is_linked()


def test_loop_array_keeps_on_error_in_the_properties(graph_with_library_system):
    loop = _add(graph_with_library_system, "haybale_core.nodes.loop_array", "LoopArrayNode")

    assert "errors.on_error" not in loop.ports
    assert "on_error" not in loop.ports
    assert loop.errors.on_error == "continue"


def test_loop_array_goes_through_every_item(graph_with_library_system, scans):
    batch = _Loop(graph_with_library_system)

    _Runner(graph_with_library_system).fire(batch.begin)

    assert batch.seen == [("a.png", 0, 3), ("b.png", 1, 3), ("sub/c.png", 2, 3)]
    assert batch.completed == [[]]
    assert batch.stopped == []


def test_loop_array_empty_array_completes_at_once(graph_with_library_system, scans):
    batch = _Loop(graph_with_library_system)
    batch.lister.listing.pattern = "*.jpg"

    _Runner(graph_with_library_system).fire(batch.begin)

    assert batch.seen == []
    assert batch.completed == [[]]


def test_loop_array_continue_records_failed(graph_with_library_system, scans):
    batch = _Loop(graph_with_library_system)
    batch.fail_on = {"b.png"}

    _Runner(graph_with_library_system, bail="branch").fire(batch.begin)

    assert [s[0] for s in batch.seen] == ["a.png", "b.png", "sub/c.png"]
    assert batch.completed == [[VolumePath(SCANS, "b.png")]]


def test_loop_array_stop_ends_through_stopped(graph_with_library_system, scans):
    batch = _Loop(graph_with_library_system)
    batch.fail_on = {"a.png"}
    batch.loop.errors.on_error = "stop"

    _Runner(graph_with_library_system, bail="branch").fire(batch.begin)

    assert [s[0] for s in batch.seen] == ["a.png"]
    assert batch.stopped == [[VolumePath(SCANS, "a.png")]]
    assert batch.completed == []


def test_loop_array_without_an_array_completes(graph_with_library_system):
    graph = graph_with_library_system
    begin = _add(graph, "haybale_core.nodes.events.begin_play", "BeginPlayNode")
    loop = _add(graph, "haybale_core.nodes.loop_array", "LoopArrayNode")
    body, after = _add(graph, *SINK), _add(graph, *SINK)
    _edge(graph, begin, "exec", loop, "execute")
    _edge(graph, loop, "loop_body", body, "exec_in")
    _edge(graph, loop, "completed", after, "exec_in")
    ran: list[str] = []
    body.worker = lambda context, x: ran.append("body")
    after.worker = lambda context, x: ran.append("completed")

    _Runner(graph).fire(begin)

    assert ran == ["completed"]


# ---------------------------------------------------------------- Step Array


class _Steps:
    """BeginPlay → List Files → Step Array.Start; Tick Event → Next; step and completed → sinks."""

    def __init__(self, graph: Any, mode: str):
        self.begin = _add(graph, "haybale_core.nodes.events.begin_play", "BeginPlayNode")
        self.tick = _add(graph, "haybale_core.nodes.events.tick_event", "TickEventNode")
        self.lister = _list_files(graph)
        self.steps = _add(graph, "haybale_core.nodes.step_array", "StepArrayNode")
        self.on_step, self.on_done = _add(graph, *SINK), _add(graph, *SINK)
        _edge(graph, self.begin, "exec", self.lister, "execute")
        _edge(graph, self.lister, "next", self.steps, "start")
        _edge(graph, self.lister, "files", self.steps, "array")
        _edge(graph, self.tick, "exec", self.steps, "next")
        _edge(graph, self.steps, "step", self.on_step, "exec_in")
        _edge(graph, self.steps, "completed", self.on_done, "exec_in")
        self.steps.ports["mode"].set_value(mode)
        self.events: list[str] = []
        self.on_step.worker = lambda context, x: self.events.append(
            f"{self.steps.ports['index'].get_value()}:{self.steps.ports['item'].get_value().relative}"
        )
        self.on_done.worker = lambda context, x: self.events.append("done")


def test_step_array_takes_its_types_from_the_wired_array(graph_with_library_system, scans):
    from haywire.barn.builtin.types import FILE_PATH

    steps = _Steps(graph_with_library_system, "once").steps

    assert steps.ports["item"].type_cls is FILE_PATH


def test_step_array_once(graph_with_library_system, scans):
    s = _Steps(graph_with_library_system, "once")
    run = _Runner(graph_with_library_system)

    run.fire(s.begin)
    run.fire(s.tick, times=4)

    assert s.events == ["0:a.png", "1:b.png", "2:sub/c.png", "done"]


def test_step_array_loop_completes_each_round_before_the_first_item(graph_with_library_system, scans):
    s = _Steps(graph_with_library_system, "loop")
    run = _Runner(graph_with_library_system)

    run.fire(s.begin)
    run.fire(s.tick, times=4)

    assert s.events == ["0:a.png", "1:b.png", "2:sub/c.png", "done", "0:a.png", "1:b.png"]


def test_step_array_palindrome(graph_with_library_system, scans):
    s = _Steps(graph_with_library_system, "palindrome")
    run = _Runner(graph_with_library_system)

    run.fire(s.begin)
    run.fire(s.tick, times=6)

    assert [e.split(":")[0] for e in s.events] == ["0", "1", "2", "1", "done", "0", "1", "2"]


def test_step_array_next_before_start_does_nothing(graph_with_library_system, scans):
    s = _Steps(graph_with_library_system, "loop")

    _Runner(graph_with_library_system).fire(s.tick, times=2)

    assert s.events == []


def test_step_array_stop_forgets_the_array(graph_with_library_system, scans):
    s = _Steps(graph_with_library_system, "loop")
    halt = _add(graph_with_library_system, "haybale_core.nodes.events.shutdown", "ShutdownNode")
    _edge(graph_with_library_system, halt, "exec", s.steps, "stop")
    run = _Runner(graph_with_library_system)
    run.fire(s.begin)

    run.fire(halt)
    run.fire(s.tick, times=2)

    assert s.events == ["0:a.png"]


def test_step_array_single_item_loop_repeats_it(graph_with_library_system, scans):
    s = _Steps(graph_with_library_system, "loop")
    s.lister.listing.pattern = "a.png"
    run = _Runner(graph_with_library_system)

    run.fire(s.begin)
    run.fire(s.tick, times=2)

    assert s.events == ["0:a.png", "done", "0:a.png", "done", "0:a.png"]


def test_step_array_empty_array_completes_at_start(graph_with_library_system, scans):
    s = _Steps(graph_with_library_system, "loop")
    s.lister.listing.pattern = "*.jpg"
    run = _Runner(graph_with_library_system)

    run.fire(s.begin)
    run.fire(s.tick)

    assert s.events == ["done"]
