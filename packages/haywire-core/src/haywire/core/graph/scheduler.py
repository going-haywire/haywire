# haywire/core/graph/scheduler.py
"""Injectable debounce strategy for the validation pipeline.

``ValidationManager`` debounces validation — coalescing a burst of
``mark_*_dirty`` calls into one ``_validate_batch`` pass — via a scheduler it
is given rather than a hardcoded ``threading.Timer``. This lets the
application choose which thread validation runs on without ``haywire-core``
depending on NiceGUI or asyncio.

Built-ins: :class:`ThreadingTimerScheduler` (default; legacy behavior),
:class:`SyncScheduler` (inline; deterministic for tests). The studio supplies
a loop-based scheduler (``haybale_studio.loop_scheduler.LoopScheduler``).

See ADR 0002 (docs/adr/0002-validation-scheduler-injection.md) for why the
timer was replaced and why injection is the chosen shape.
"""

from __future__ import annotations

import threading
from typing import Callable, Protocol, runtime_checkable


class ScheduleHandle(Protocol):
    """Cancellable handle for a pending scheduled call.

    ``cancel()`` must be idempotent and safe to call after the scheduled
    function has already run (a no-op in that case) — ``ValidationManager``
    cancels unconditionally before rescheduling.
    """

    def cancel(self) -> None: ...


@runtime_checkable
class ValidationScheduler(Protocol):
    """Schedules a single debounced call, returning a cancellable handle.

    Implementations arrange for ``fn`` to run once, ``delay_seconds`` from
    now. Re-scheduling is the caller's responsibility: ``ValidationManager``
    cancels the previous handle and schedules a fresh one on every dirty mark,
    which is what produces the debounce.
    """

    def schedule(self, delay_seconds: float, fn: Callable[[], object]) -> ScheduleHandle: ...


class _CancelledHandle:
    """Inert handle for schedulers that run synchronously (nothing to cancel)."""

    def cancel(self) -> None:
        return None


class SyncScheduler:
    """Runs the callback immediately, ignoring the delay.

    Removes all timing nondeterminism — intended for tests and headless use.
    With this scheduler a ``mark_*_dirty`` validates inline, so assertions can
    follow a mutation without ``force_immediate_validation``.
    """

    def schedule(self, delay_seconds: float, fn: Callable[[], object]) -> ScheduleHandle:
        fn()
        return _CancelledHandle()


class ThreadingTimerScheduler:
    """Legacy debounce: a daemon ``threading.Timer`` per scheduled call.

    ``ValidationManager``'s default, so callers that don't inject a scheduler
    behave exactly as before this abstraction existed. See ADR 0002 for why
    application wiring prefers a loop-based scheduler instead.
    """

    def schedule(self, delay_seconds: float, fn: Callable[[], object]) -> ScheduleHandle:
        timer = threading.Timer(delay_seconds, fn)
        timer.daemon = True
        timer.start()
        return timer
