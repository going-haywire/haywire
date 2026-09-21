# haywire/core/graph/scheduler.py
"""Injectable debounce strategy for the validation pipeline.

Three implementations of one protocol: :class:`SyncScheduler` for tests and
headless use, :class:`ThreadingTimerScheduler` as the default, and
:class:`LoopScheduler` for the running app. See ADR 0002.
"""

from __future__ import annotations

import asyncio
import logging
import threading
from typing import Callable, Optional, Protocol, runtime_checkable

logger = logging.getLogger(__name__)


class ScheduleHandle(Protocol):
    """Cancellable handle for a pending scheduled call.

    ``cancel()`` must be idempotent and safe to call after the scheduled
    function has already run, where it is a no-op.
    """

    def cancel(self) -> None: ...


@runtime_checkable
class ValidationScheduler(Protocol):
    """Schedules a single debounced call, returning a cancellable handle.

    Implementations arrange for ``fn`` to run once, ``delay_seconds`` from
    now. Re-scheduling is the caller's responsibility: the debounce comes from
    cancelling the previous handle and scheduling a fresh one.
    """

    def schedule(self, delay_seconds: float, fn: Callable[[], object]) -> ScheduleHandle: ...


class _CancelledHandle:
    """Inert handle for schedulers that run synchronously (nothing to cancel)."""

    def cancel(self) -> None:
        return None


class SyncScheduler:
    """Runs the callback immediately, ignoring the delay.

    Intended for tests and headless use: a ``mark_*_dirty`` validates inline,
    so assertions can follow a mutation without ``force_immediate_validation``.
    """

    def schedule(self, delay_seconds: float, fn: Callable[[], object]) -> ScheduleHandle:
        fn()
        return _CancelledHandle()


class ThreadingTimerScheduler:
    """Debounce via a daemon ``threading.Timer`` per scheduled call.

    ``ValidationManager``'s default scheduler.
    """

    def schedule(self, delay_seconds: float, fn: Callable[[], object]) -> ScheduleHandle:
        timer = threading.Timer(delay_seconds, fn)
        timer.daemon = True
        timer.start()
        return timer


class _LoopHandle:
    """Cancellable handle over a (possibly not-yet-created) loop timer.

    ``call_later`` runs on the loop thread, so the underlying
    ``asyncio.TimerHandle`` may not exist yet when ``cancel()`` is called.
    The cancel intent is recorded under a lock; if the timer already exists it
    is cancelled, otherwise the deferred creation observes the flag and skips
    arming. Idempotent and safe post-fire.
    """

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._timer: Optional[asyncio.TimerHandle] = None
        self._cancelled = False

    def _arm(self, timer: asyncio.TimerHandle) -> None:
        with self._lock:
            if self._cancelled:
                timer.cancel()
                return
            self._timer = timer

    def cancel(self) -> None:
        with self._lock:
            self._cancelled = True
            if self._timer is not None:
                self._timer.cancel()
                self._timer = None


class LoopScheduler:
    """Debounce validation on the NiceGUI event loop.

    The scheduler the running app injects, so validation — and the
    ``GraphDataMutated`` broadcast it triggers — runs on the main thread rather
    than a timer thread.

    ``schedule`` may be called from a non-loop thread (a hot-reload watcher
    marking nodes dirty), so it hops via ``call_soon_threadsafe``; the returned
    handle is cancellable from any thread. With no loop running yet — pre-
    ``ui.run`` graph construction — the callback runs inline, which forgoes
    debouncing for that window and is safe because validation is pure CPU work.
    """

    def schedule(self, delay_seconds: float, fn: Callable[[], object]) -> ScheduleHandle:
        from nicegui import core

        handle = _LoopHandle()
        loop = core.loop

        if loop is None or not loop.is_running():
            fn()
            return handle

        def _arm() -> None:
            timer = loop.call_later(delay_seconds, fn)
            handle._arm(timer)

        loop.call_soon_threadsafe(_arm)
        return handle
