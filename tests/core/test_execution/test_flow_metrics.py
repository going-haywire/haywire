"""FlowMeterSampler and the FlowQueue drop counter behind the flow meters.

Import order: editor first, per the repo test convention (avoids circular imports when pulling in
haywire execution modules).
"""

import time
from queue import Full
from typing import Any

import pytest

from haywire.core.execution.event_source import Trigger
from haywire.core.execution.flow_metrics import FlowMeterSampler, FlowSnapshot, Severity
from haywire.core.execution.flow_queue import FlowQueue, QueueMode

pytestmark = pytest.mark.unit

SECOND_NS = 1_000_000_000


def _snap(flow_id: str = "f", at: float = 0.0, **fields: Any) -> FlowSnapshot:
    values: dict[str, Any] = {
        "flow_id": flow_id,
        "entry_node_id": f"node_{flow_id}",
        "group_id": "g",
        "drop_mode": False,
        "queue_depth": 0,
        "queue_max": 100,
        "frames": 0,
        "busy_ns": 0,
        "dropped": 0,
        "executing": False,
        "taken_at": at,
    }
    values.update(fields)
    return FlowSnapshot(**values)


def _run(sampler: FlowMeterSampler, *steps: list[FlowSnapshot]):
    reading = None
    for snapshots in steps:
        reading = sampler.update(snapshots)
    return reading


def _only(reading):
    assert reading is not None
    assert len(reading.flows) == 1
    return reading.flows[0]


def test_the_first_sample_of_a_flow_reports_it_idle():
    reading = FlowMeterSampler().update([_snap(frames=500, busy_ns=9 * SECOND_NS, at=10.0)])
    flow = _only(reading)
    assert (flow.load, flow.severity) == (0.0, Severity.OK)


def test_no_running_flow_gives_an_empty_reading():
    reading = FlowMeterSampler().update([])
    assert reading.worst is None
    assert reading.flows == ()


@pytest.mark.parametrize(
    ("busy_share", "expected"),
    [(0.5, Severity.OK), (0.7, Severity.WARN), (0.89, Severity.WARN), (0.9, Severity.ALERT)],
)
def test_load_is_the_share_of_the_window_spent_in_frames(busy_share, expected):
    reading = _run(
        FlowMeterSampler(),
        [_snap(at=0.0)],
        [_snap(at=2.0, frames=100, busy_ns=int(busy_share * 2 * SECOND_NS))],
    )
    flow = _only(reading)
    assert flow.load == pytest.approx(busy_share)
    assert flow.frame_rate == pytest.approx(50.0)
    assert flow.severity == expected


def test_a_frame_that_spans_the_whole_window_counts_as_fully_busy():
    reading = _run(FlowMeterSampler(), [_snap(at=0.0)], [_snap(at=0.5, executing=True)])
    flow = _only(reading)
    assert (flow.load, flow.severity) == (1.0, Severity.ALERT)


def test_a_flow_inherits_the_load_of_its_group():
    reading = _run(
        FlowMeterSampler(),
        [_snap("a", 0.0), _snap("b", 0.0)],
        [
            _snap("a", 1.0, frames=10, busy_ns=int(0.95 * SECOND_NS)),
            _snap("b", 1.0, frames=10, busy_ns=int(0.01 * SECOND_NS)),
        ],
    )
    by_id = {f.flow_id: f for f in reading.flows}
    assert by_id["b"].load == pytest.approx(0.01)
    assert by_id["b"].group_load == pytest.approx(0.96)
    assert by_id["b"].severity == Severity.ALERT


def test_a_dropped_trigger_turns_a_block_flow_red_for_five_seconds():
    sampler = FlowMeterSampler()
    sampler.update([_snap(at=0.0)])
    assert _only(sampler.update([_snap(at=1.0, frames=5, dropped=1)])).severity == Severity.ALERT
    assert _only(sampler.update([_snap(at=5.9, frames=30, dropped=1)])).severity == Severity.ALERT
    healed = _only(sampler.update([_snap(at=6.1, frames=31, dropped=1)]))
    assert healed.recently_dropped is False
    assert healed.severity == Severity.OK


@pytest.mark.parametrize(
    ("depth", "expected"),
    [(10, Severity.OK), (50, Severity.WARN), (79, Severity.WARN), (80, Severity.ALERT)],
)
def test_queue_fill_grades_a_block_flow(depth, expected):
    reading = _run(FlowMeterSampler(), [_snap(at=0.0)], [_snap(at=1.0, frames=10, queue_depth=depth)])
    assert _only(reading).severity == expected


def test_drops_in_drop_mode_are_by_design_below_the_drop_rate_threshold():
    sampler = FlowMeterSampler()
    sampler.update([_snap(at=0.0, drop_mode=True, queue_max=1, queue_depth=1)])
    # 95 frames ran and 5 triggers were replaced: a 5% drop rate.
    reading = sampler.update(
        [_snap(at=1.0, drop_mode=True, queue_max=1, queue_depth=1, frames=95, dropped=5)]
    )
    flow = _only(reading)
    assert flow.drop_rate == pytest.approx(0.05)
    assert flow.severity == Severity.OK, "a full one-slot queue is normal in drop mode"


def test_a_drop_mode_flow_that_drops_much_is_amber():
    sampler = FlowMeterSampler()
    sampler.update([_snap(at=0.0, drop_mode=True, queue_max=1)])
    reading = sampler.update([_snap(at=1.0, drop_mode=True, queue_max=1, frames=30, dropped=30)])
    flow = _only(reading)
    assert flow.drop_rate == pytest.approx(0.5)
    assert flow.severity == Severity.WARN


def test_counters_that_restart_report_the_flow_idle_again():
    sampler = FlowMeterSampler()
    sampler.update([_snap(at=0.0)])
    sampler.update([_snap(at=1.0, frames=50, busy_ns=SECOND_NS)])
    flow = _only(sampler.update([_snap(at=2.0, frames=2, busy_ns=1000)]))
    assert (flow.load, flow.severity) == (0.0, Severity.OK)


def test_groups_and_flows_are_ordered_worst_first_with_groups_kept_together():
    sampler = FlowMeterSampler()
    sampler.update(
        [_snap(f, 0.0, group_id=g) for f, g in (("a1", "A"), ("a2", "A"), ("b1", "B"), ("c1", "C"))]
    )
    reading = sampler.update(
        [
            _snap("a1", 1.0, group_id="A", frames=5, busy_ns=int(0.05 * SECOND_NS)),
            _snap("a2", 1.0, group_id="A", frames=5, busy_ns=int(0.10 * SECOND_NS)),
            _snap("b1", 1.0, group_id="B", frames=5, busy_ns=int(0.50 * SECOND_NS), queue_depth=95),
            _snap("c1", 1.0, group_id="C", frames=5, busy_ns=int(0.30 * SECOND_NS)),
        ]
    )
    assert [g.group_id for g in reading.groups] == ["B", "C", "A"]
    assert [f.flow_id for f in reading.flows] == ["b1", "c1", "a2", "a1"]
    assert reading.worst is not None
    assert reading.worst.flow_id == "b1"


def test_a_flow_that_disappears_is_forgotten():
    sampler = FlowMeterSampler()
    sampler.update([_snap(at=0.0)])
    sampler.update([_snap(at=1.0, frames=5, dropped=1)])
    sampler.update([])
    sampler.update([_snap(at=2.0)])
    flow = _only(sampler.update([_snap(at=3.0, frames=5)]))
    assert flow.recently_dropped is False


class _StubFlow:
    flow_id = "stub_flow"

    def get_entry_node_id(self) -> str:
        return "entry_node"


class _StubGroup:
    group_id = "stub_group"

    def __init__(self, runner: bool) -> None:
        self._runner = runner
        self.posted = 0

    def is_stopping(self) -> bool:
        return False

    def is_runner_thread(self) -> bool:
        return self._runner

    def post(self, flow_queue: FlowQueue) -> None:
        self.posted += 1


def _queue(mode: QueueMode, size: int, group: _StubGroup | None = None) -> FlowQueue:
    return FlowQueue(flow=_StubFlow(), vm=None, queue_mode=mode, max_queue_size=size, group=group)  # type: ignore[arg-type]


def _trigger() -> Trigger:
    return Trigger(source_key="callback:stub", payload=None, timestamp=time.time())


def test_a_drop_mode_replacement_counts_as_a_drop():
    queue = _queue(QueueMode.DROP, 1, _StubGroup(runner=False))
    queue.enqueue_trigger(_trigger())
    assert queue.get_dropped_count() == 0
    queue.enqueue_trigger(_trigger())
    queue.enqueue_trigger(_trigger())
    assert queue.get_dropped_count() == 2


def test_a_trigger_refused_by_a_full_queue_inside_the_group_counts_as_a_drop():
    queue = _queue(QueueMode.BLOCK, 1, _StubGroup(runner=True))
    assert queue.enqueue_trigger(_trigger()) is True
    assert queue.enqueue_trigger(_trigger()) is False
    assert queue.get_dropped_count() == 1


def test_a_block_wait_that_times_out_counts_as_a_drop(monkeypatch):
    queue = _queue(QueueMode.BLOCK, 1, _StubGroup(runner=False))

    def full(*args: Any, **kwargs: Any) -> None:
        raise Full

    monkeypatch.setattr(queue.trigger_queue, "put", full)
    assert queue.enqueue_trigger(_trigger()) is False
    assert queue.get_dropped_count() == 1


def test_a_snapshot_carries_the_queues_counters():
    queue = _queue(QueueMode.DROP, 3, _StubGroup(runner=False))
    queue.enqueue_trigger(_trigger())
    snap = queue.snapshot()
    assert (snap.flow_id, snap.entry_node_id, snap.group_id) == ("stub_flow", "entry_node", "stub_group")
    assert (snap.drop_mode, snap.queue_depth, snap.queue_max) == (True, 1, 3)
    assert (snap.frames, snap.busy_ns, snap.dropped, snap.executing) == (0, 0, 0, False)
