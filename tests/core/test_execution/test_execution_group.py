"""ExecutionGroup: one runner per group, per-flow queue policy, shared data nodes, lifecycle.

Uses the real ``HaywireVM`` lifecycle and data-flow paths with stub flows and
stub nodes; a recording VM subclass replaces only ``execute_control_flow``,
running each stub flow's ``frame`` callable as its frame. See ADR 0064.
"""

import threading
import time
from types import SimpleNamespace
from typing import Any, Callable, List, Optional, Sequence

import pytest

from haywire.core.execution.event_source import Trigger
from haywire.core.execution.execution_group import ExecutionGroup, shared_data_node_ids
from haywire.core.execution.flow import LocalizedDataFlow
from haywire.core.execution.flow_queue import FlowQueue, QueueMode
from haywire.core.execution.vm import HaywireVM
from haywire.core.node.base import BaseNode
from haywire.core.node.node_wrapper import NodeWrapper

pytestmark = pytest.mark.unit


def _wrapper() -> NodeWrapper:
    """A NodeWrapper carrying only its run-lifecycle state."""
    wrapper = NodeWrapper.__new__(NodeWrapper)
    wrapper.exec_lock = threading.Lock()
    wrapper._run_refs = 0
    return wrapper


class _Node:
    """Stub node: hooks default to BaseNode's, so override detection sees none."""

    on_startup = BaseNode.on_startup
    on_shutdown = BaseNode.on_shutdown
    on_frame_start = BaseNode.on_frame_start
    on_frame_end = BaseNode.on_frame_end

    def __init__(self, node_id: str):
        self.node_id = node_id
        self.wrapper = _wrapper()


class _LifecycleNode(_Node):
    def __init__(self, node_id: str, events: List[str]):
        super().__init__(node_id)
        self.events = events
        self.threads: List[str] = []

    def on_startup(self, context):  # type: ignore[override]
        self.events.append("startup")
        self.threads.append(threading.current_thread().name)

    def on_shutdown(self, context):  # type: ignore[override]
        self.events.append("shutdown")
        self.threads.append(threading.current_thread().name)


class _DataNode(_LifecycleNode):
    """A data node that computes once per dirtying, optionally parking inside its worker."""

    def __init__(self, node_id: str, events: List[str]):
        super().__init__(node_id, events)
        self.dirty = True
        self.value: Optional[str] = None
        self.worker_runs = 0
        self.inside = threading.Event()
        self.release_worker = threading.Event()
        self.release_worker.set()

    def _execute(self, context) -> None:
        if not self.dirty:
            return None
        self.worker_runs += 1
        self.events.append(f"worker:{context.trigger.source_key}")
        self.inside.set()
        self.release_worker.wait(5.0)
        self.value = f"computed-by-{context.trigger.source_key}"
        self.dirty = False
        return None


class _Flow:
    def __init__(
        self,
        flow_id: str,
        nodes: Sequence[Any] = (),
        control: Sequence[str] = (),
        frame: Optional[Callable[[HaywireVM, Trigger], None]] = None,
    ):
        self.flow_id = flow_id
        self._nodes = list(nodes)
        self._control = list(control)
        self.frame = frame or (lambda vm, trigger: None)
        self.graph_ref = SimpleNamespace(variables={})
        self.queue: Optional[FlowQueue] = None
        self.shared_node_ids: frozenset = frozenset()

    def get_entry_node_id(self) -> str:
        return f"entry_{self.flow_id}"

    def get_control_node_ids(self) -> List[str]:
        return list(self._control)

    def get_all_nodes(self) -> List[Any]:
        return list(self._nodes)


class _Vm(HaywireVM):
    def execute_control_flow(self, flow, trigger, frame_number=0, cancel=None):  # type: ignore[override]
        flow.frame(self, trigger)
        return 1


def _group(
    flows: List[_Flow], vm: HaywireVM, gid: str = "g", mode=QueueMode.BLOCK, size: int = 100
) -> ExecutionGroup:
    for flow in flows:
        flow.queue = FlowQueue(flow, vm, queue_mode=mode, max_queue_size=size)  # type: ignore[arg-type]
    group = ExecutionGroup(gid, flows, vm)  # type: ignore[arg-type]
    for flow in flows:
        assert flow.queue is not None
        flow.queue.group = group
    return group


def _trigger(key: str) -> Trigger:
    return Trigger(source_key=key, payload=None, timestamp=time.time())


def _enqueue(flow: _Flow, key: str) -> bool:
    assert flow.queue is not None
    return flow.queue.enqueue_trigger(_trigger(key))


def _wait(flow: _Flow, timeout_s: float = 2.0) -> bool:
    assert flow.queue is not None
    return flow.queue.wait_for_completion(timeout_s)


def _evaluate(vm: HaywireVM, flow: _Flow, trigger: Trigger, node: Any) -> None:
    ctx = vm._create_execution_context(flow, trigger)  # type: ignore[arg-type]
    vm._evaluate_data_flow(LocalizedDataFlow(f"c_{flow.flow_id}", [node]), ctx, flow.shared_node_ids)


def test_frames_of_one_group_never_overlap():
    vm = _Vm()
    lock = threading.Lock()
    state = {"active": 0, "max": 0}

    def frame(vm, trigger):
        with lock:
            state["active"] += 1
            state["max"] = max(state["max"], state["active"])
        time.sleep(0.001)
        with lock:
            state["active"] -= 1

    a, b = _Flow("A", frame=frame), _Flow("B", frame=frame)
    group = _group([a, b], vm)
    group.start()
    try:
        for i in range(20):
            assert _enqueue(a, f"A{i}")
            assert _enqueue(b, f"B{i}")
        assert _wait(a)
        assert _wait(b)
    finally:
        assert group.stop()
    assert state["max"] == 1


def test_frames_run_in_arrival_order():
    vm = _Vm()
    seen: List[str] = []
    a = _Flow("A", frame=lambda vm, t: seen.append(t.source_key))
    b = _Flow("B", frame=lambda vm, t: seen.append(t.source_key))
    group = _group([a, b], vm)
    expected: List[str] = []
    group.start()
    try:
        for i in range(10):
            for flow in (a, b, b, a) if i % 2 else (a, b):
                key = f"{flow.flow_id}{len(expected)}"
                expected.append(key)
                assert _enqueue(flow, key)
        assert _wait(a)
        assert _wait(b)
    finally:
        group.stop()
    assert seen == expected


def test_two_groups_run_concurrently():
    vm = _Vm()
    barrier = threading.Barrier(2, timeout=2.0)
    broken: List[bool] = []

    def frame(vm, trigger):
        try:
            barrier.wait()
        except threading.BrokenBarrierError:
            broken.append(True)

    a, b = _Flow("A", frame=frame), _Flow("B", frame=frame)
    ga, gb = _group([a], vm, "ga"), _group([b], vm, "gb")
    ga.start()
    gb.start()
    try:
        _enqueue(a, "A")
        _enqueue(b, "B")
        assert _wait(a)
        assert _wait(b)
    finally:
        ga.stop()
        gb.stop()
    assert broken == []


def test_drop_keeps_newest_pending():
    vm = _Vm()
    seen: List[str] = []
    inside, gate = threading.Event(), threading.Event()

    def frame(vm, trigger):
        seen.append(trigger.source_key)
        if trigger.source_key == "t0":
            inside.set()
            gate.wait(2.0)

    a = _Flow("A", frame=frame)
    group = _group([a], vm, mode=QueueMode.DROP, size=1)
    group.start()
    try:
        assert _enqueue(a, "t0")
        assert inside.wait(2.0)
        assert [_enqueue(a, k) for k in ("t1", "t2", "t3")] == [True, True, True]
        assert a.queue is not None
        assert a.queue.get_queue_size() == 1
        gate.set()
        assert a.queue.wait_for_completion(1.0) is True
    finally:
        group.stop()
    assert seen == ["t0", "t3"]


def test_emit_from_own_runner_never_blocks():
    vm = _Vm()
    results: List[bool] = []
    elapsed: List[float] = []
    b = _Flow("B")

    def frame_a(vm, trigger):
        start = time.monotonic()
        results.extend(_enqueue(b, f"b{i}") for i in range(3))
        elapsed.append(time.monotonic() - start)

    a = _Flow("A", frame=frame_a)
    for flow, size in ((a, 100), (b, 1)):
        flow.queue = FlowQueue(flow, vm, max_queue_size=size)  # type: ignore[arg-type]
    group = ExecutionGroup("g", [a, b], vm)  # type: ignore[arg-type, list-item]
    for flow in (a, b):
        assert flow.queue is not None
        flow.queue.group = group
    group.start()
    try:
        _enqueue(a, "a")
        assert _wait(a)
        assert _wait(b)
    finally:
        group.stop()
    assert results == [True, False, False]
    assert elapsed[0] < 0.2


def test_startup_and_shutdown_once_per_node():
    vm = _Vm()
    events: List[str] = []
    x = _LifecycleNode("x", events)
    a, b = _Flow("A", [x], ["x"]), _Flow("B", [x], ["x"])
    group = _group([a, b], vm)
    group.start()
    try:
        _enqueue(a, "a")
        _enqueue(b, "b")
        assert _wait(a)
        assert _wait(b)
    finally:
        assert group.stop()
    assert events == ["startup", "shutdown"]
    assert x.threads == ["FlowExec-g", "FlowExec-g"]


def test_retain_release_counts():
    wrapper = _wrapper()
    assert [wrapper.retain(), wrapper.retain()] == [True, False]
    assert [wrapper.release(), wrapper.release()] == [False, True]
    assert wrapper.release() is False
    assert wrapper._run_refs == 0


def _two_groups_sharing(vm: HaywireVM, s: _DataNode):
    a = _Flow("A", [s], ["ca"], frame=lambda vm, t: _evaluate(vm, a, t, s))
    b = _Flow("B", [s], ["cb"], frame=lambda vm, t: _evaluate(vm, b, t, s))
    shared = shared_data_node_ids([[a], [b]])
    assert shared == {"s"}
    a.shared_node_ids = b.shared_node_ids = shared
    return a, b, _group([a], vm, "ga"), _group([b], vm, "gb")


def test_shared_data_node_started_before_either_groups_first_frame():
    vm = _Vm()
    events: List[str] = []
    s = _DataNode("s", events)
    a, b, ga, gb = _two_groups_sharing(vm, s)
    ga.start()
    gb.start()
    try:
        _enqueue(a, "a")
        _enqueue(b, "b")
        assert _wait(a)
        assert _wait(b)
    finally:
        ga.stop()
        gb.stop()
    assert events.count("startup") == 1
    assert events[0] == "startup"
    assert any(e.startswith("worker:") for e in events)


def test_shared_data_node_stopped_after_both_groups():
    vm = _Vm()
    events: List[str] = []
    s = _DataNode("s", events)
    a, b, ga, gb = _two_groups_sharing(vm, s)
    ga.start()
    gb.start()
    _enqueue(a, "a")
    assert _wait(a)
    s.dirty = True
    _enqueue(b, "b")
    assert _wait(b)
    assert ga.stop()
    assert "shutdown" not in events
    s.dirty = True
    _enqueue(b, "b2")
    assert _wait(b)
    assert gb.stop()
    assert events.count("shutdown") == 1
    assert events[-1] == "shutdown"
    assert events.index("worker:b2") < events.index("shutdown")


def test_shared_data_node_computed_once_and_read_fresh():
    vm = _Vm()
    events: List[str] = []
    s = _DataNode("s", events)
    read: dict = {}

    def frame_for(flow_name):
        def frame(vm, trigger):
            _evaluate(vm, flows[flow_name], trigger, s)
            read[flow_name] = s.value

        return frame

    flows = {
        "A": _Flow("A", [s], ["ca"], frame=frame_for("A")),
        "B": _Flow("B", [s], ["cb"], frame=frame_for("B")),
    }
    a, b = flows["A"], flows["B"]
    a.shared_node_ids = b.shared_node_ids = shared_data_node_ids([[a], [b]])
    ga, gb = _group([a], vm, "ga"), _group([b], vm, "gb")
    s.release_worker.clear()
    ga.start()
    gb.start()
    try:
        _enqueue(a, "a")
        assert s.inside.wait(2.0)
        _enqueue(b, "b")
        time.sleep(0.1)
        assert "B" not in read  # B waits for s while A computes it
        s.release_worker.set()
        assert _wait(a)
        assert _wait(b)
    finally:
        ga.stop()
        gb.stop()
    assert s.worker_runs == 1
    assert read == {"A": "computed-by-a", "B": "computed-by-a"}


class _RecordingLock:
    def __init__(self):
        self.acquired = 0
        self._lock = threading.Lock()

    def acquire(self, *args, **kwargs):
        self.acquired += 1
        return self._lock.acquire(*args, **kwargs)

    def release(self):
        self._lock.release()

    def __enter__(self):
        self.acquire()
        return self

    def __exit__(self, *exc):
        self.release()


def test_unshared_data_node_takes_no_lock():
    vm = _Vm()
    events: List[str] = []
    s = _DataNode("s", events)

    def frame(vm, trigger):
        s.dirty = True
        _evaluate(vm, a, trigger, s)

    a = _Flow("A", [s], ["ca"], frame=frame)
    a.shared_node_ids = shared_data_node_ids([[a]])
    assert a.shared_node_ids == frozenset()
    group = _group([a], vm)
    group.start()
    try:
        _enqueue(a, "warmup")
        assert _wait(a)  # startup is over: only frames run from here
        real_lock, recording = s.wrapper.exec_lock, _RecordingLock()
        s.wrapper.exec_lock = recording  # type: ignore[assignment]
        for i in range(5):
            _enqueue(a, f"a{i}")
        assert _wait(a)
        s.wrapper.exec_lock = real_lock
    finally:
        group.stop()
    assert recording.acquired == 0
    assert s.worker_runs == 6


def test_in_group_emit_runs_after_current_frame():
    vm = _Vm()
    order: List[str] = []
    b = _Flow("B", frame=lambda vm, t: order.append("B-start"))

    def frame_a(vm, trigger):
        order.append("A-start")
        _enqueue(b, "b")
        time.sleep(0.05)
        order.append("A-end")

    a = _Flow("A", frame=frame_a)
    group = _group([a, b], vm)
    group.start()
    try:
        _enqueue(a, "a")
        assert _wait(a)
        assert _wait(b)
    finally:
        group.stop()
    assert order == ["A-start", "A-end", "B-start"]


def test_hold_is_bounded_by_a_stuck_frame():
    """A frame that never ends cannot keep a structural batch (on the UI loop) waiting forever."""
    from haywire.core.execution.interpreter import Interpreter

    vm = _Vm()
    inside, stuck = threading.Event(), threading.Event()

    def frame(vm, trigger):
        inside.set()
        stuck.wait(5.0)

    a = _Flow("A", frame=frame)
    group = _group([a], vm)
    interpreter = Interpreter()
    interpreter.groups = [group]
    group.start()
    try:
        _enqueue(a, "a")
        assert inside.wait(2.0)
        start = time.monotonic()
        assert group.hold(timeout_s=0.2) is False
        assert interpreter.hold_for_batch(timeout_s=0.2) is True
        assert time.monotonic() - start < 1.0
        interpreter.release_after_batch(requires_reassembly=False)
    finally:
        stuck.set()
        group.stop()
