"""Unit tests for FlowScheduler.wait_for_completion timeout behaviour.

Regression for the TickEmit shutdown deadlock: ``wait_for_completion`` used a
bare ``Queue.join()`` that ignored its ``timeout`` argument. When a producer
(e.g. a TickEmit thread) keeps feeding the trigger queue, the queue never
reaches zero unfinished tasks, so the join — and therefore ``stop_execution`` —
hung forever. These tests pin the bounded-timeout contract directly at the
scheduler level, independent of node/VM timing.

Import order: editor first, per the repo test convention (avoids circular
imports when pulling in haywire execution modules).
"""

import threading
import time

import pytest

from haywire.core.execution.scheduler import FlowScheduler
from haywire.core.execution.event_source import Trigger


class _StubFlow:
    """Minimal stand-in: wait_for_completion only reads flow_id for logging."""

    flow_id = "stub_flow"


def _make_scheduler() -> FlowScheduler:
    # vm is unused by wait_for_completion / enqueue paths exercised here.
    return FlowScheduler(flow=_StubFlow(), vm=None)  # type: ignore[arg-type]


def _trigger() -> Trigger:
    return Trigger(source_key="callback:stub", payload=None, timestamp=time.time())


@pytest.mark.unit
def test_wait_for_completion_returns_true_when_drained():
    """An empty/drained queue completes immediately and returns True."""
    sched = _make_scheduler()
    assert sched.wait_for_completion(timeout=1.0) is True


@pytest.mark.unit
def test_wait_for_completion_times_out_under_continuous_producer():
    """A continuously-fed queue must NOT hang: returns False within ~timeout.

    This is the core regression. With the old bare ``join()`` this call never
    returned while the producer kept enqueuing.
    """
    sched = _make_scheduler()
    stop = threading.Event()

    def producer():
        # Feed faster than we ever drain (we never call task_done here),
        # so unfinished_tasks stays > 0 for the whole wait.
        while not stop.is_set():
            sched.trigger_queue.put(_trigger())
            time.sleep(0.001)

    producer_thread = threading.Thread(target=producer, daemon=True)
    producer_thread.start()
    try:
        start = time.monotonic()
        result = sched.wait_for_completion(timeout=0.5)
        elapsed = time.monotonic() - start
    finally:
        stop.set()
        producer_thread.join(timeout=1.0)

    assert result is False  # timed out rather than completed
    # Returned near the deadline, not hung and not instant.
    assert 0.5 <= elapsed < 2.0


@pytest.mark.unit
def test_wait_for_completion_returns_true_once_backlog_clears():
    """A finite backlog that gets drained returns True before the timeout."""
    sched = _make_scheduler()
    for _ in range(5):
        sched.trigger_queue.put(_trigger())

    def drainer():
        time.sleep(0.05)
        for _ in range(5):
            sched.trigger_queue.get()
            sched.trigger_queue.task_done()

    drain_thread = threading.Thread(target=drainer, daemon=True)
    drain_thread.start()
    try:
        assert sched.wait_for_completion(timeout=2.0) is True
    finally:
        drain_thread.join(timeout=1.0)
