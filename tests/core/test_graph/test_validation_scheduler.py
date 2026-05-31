"""Unit tests for the injectable validation scheduler.

The scheduler is the debounce strategy for ``ValidationManager``. These tests
pin the three behaviors the rest of the system relies on:

* the default is the legacy background ``threading.Timer`` (no behavior change
  for callers that don't inject);
* ``SyncScheduler`` validates inline, so a mark is observable immediately
  without ``force_immediate_validation`` — the determinism win for tests;
* a fresh mark cancels the pending run (the actual debounce).
"""

from __future__ import annotations

from typing import Callable, List

from haywire.core.graph.base import BaseGraph
from haywire.core.graph.scheduler import (
    SyncScheduler,
    ThreadingTimerScheduler,
    ValidationScheduler,
)
from haywire.core.graph.types import ChangeReason


def test_default_scheduler_is_threading_timer():
    """A graph built without a scheduler keeps the legacy timer behavior."""
    graph = BaseGraph("g", "G")
    assert isinstance(graph._validation._scheduler, ThreadingTimerScheduler)


def test_sync_scheduler_validates_inline():
    """With SyncScheduler a dirty mark runs validation immediately.

    No timer, no force_immediate_validation: the subscriber fires within the
    mark_*_dirty call itself.
    """
    graph = BaseGraph("g", "G", validation_scheduler=SyncScheduler())
    seen: List[int] = []
    graph.subscribe_to_validation(lambda result: seen.append(result.total_changes))

    # Marking a (non-existent-but-tracked) node dirty with a redraw reason is
    # enough to drive a batch; redraw reasons don't need a real wrapper.
    graph._validation.mark_node_dirty("n1", ChangeReason.NODE_REDRAW_REQUESTED)

    assert seen, "SyncScheduler should validate inline on mark"
    assert graph._validation.get_statistics()["pending_validation"] is False


def test_scheduler_protocol_is_runtime_checkable():
    """Both built-in schedulers satisfy the ValidationScheduler protocol."""
    assert isinstance(SyncScheduler(), ValidationScheduler)
    assert isinstance(ThreadingTimerScheduler(), ValidationScheduler)


def test_reschedule_cancels_previous_handle():
    """A second schedule cancels the first — the debounce contract.

    Uses a recording scheduler that captures handles so we can assert the
    earlier one was cancelled when a new mark arrives before it fired.
    """

    class _RecordingHandle:
        def __init__(self) -> None:
            self.cancelled = False

        def cancel(self) -> None:
            self.cancelled = True

    class _RecordingScheduler:
        def __init__(self) -> None:
            self.handles: List[_RecordingHandle] = []
            self.fns: List[Callable[[], object]] = []

        def schedule(self, delay_seconds: float, fn: Callable[[], object]) -> _RecordingHandle:
            # Capture but do NOT run fn — we want a "pending" run to cancel.
            handle = _RecordingHandle()
            self.handles.append(handle)
            self.fns.append(fn)
            return handle

    sched = _RecordingScheduler()
    graph = BaseGraph("g", "G", validation_scheduler=sched)

    graph._validation.mark_node_dirty("n1", ChangeReason.NODE_REDRAW_REQUESTED)
    graph._validation.mark_node_dirty("n2", ChangeReason.NODE_REDRAW_REQUESTED)

    assert len(sched.handles) == 2
    assert sched.handles[0].cancelled is True, "first pending run must be cancelled on reschedule"
    assert sched.handles[1].cancelled is False
