# barn/haybale-studio/haybale_studio/loop_scheduler.py
"""Event-loop-based validation scheduler.

Implements ``haywire.core.graph.scheduler.ValidationScheduler`` by debouncing
the validation pass on the NiceGUI event loop, so ``_validate_batch`` and its
UI subscribers (canvas redraw, the ``GraphDataMutated`` dirty broadcast) run
on the main thread. The application injects this at graph-construction time;
``haywire-core`` itself stays NiceGUI-free.

See ADR 0002 (docs/adr/0002-validation-scheduler-injection.md) for the design
rationale.
"""

from __future__ import annotations

import asyncio
import logging
import threading
from typing import Callable, Optional

from nicegui import core

logger = logging.getLogger(__name__)


class _LoopHandle:
    """Cancellable handle over a (possibly not-yet-created) loop timer.

    ``call_later`` runs on the loop thread, so the underlying
    ``asyncio.TimerHandle`` may not exist yet when ``cancel()`` is called.
    We record the cancel intent under a lock; if the timer has already been
    created we cancel it, otherwise the deferred creation observes the flag
    and skips arming. Idempotent and safe post-fire.
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

    Falls back to running the callback inline if no loop is available yet
    (e.g. graph construction during startup before ``ui.run`` installs the
    loop). Inline execution is safe because validation is pure CPU work; it
    only forgoes debouncing for that early window.
    """

    def schedule(self, delay_seconds: float, fn: Callable[[], object]) -> _LoopHandle:
        handle = _LoopHandle()
        loop = core.loop

        if loop is None or not loop.is_running():
            # No loop yet — run inline. Pre-loop graph construction (workspace
            # rehydrate) goes through here; there is nothing to debounce
            # against and validation must still happen.
            fn()
            return handle

        def _arm() -> None:
            timer = loop.call_later(delay_seconds, fn)
            handle._arm(timer)

        loop.call_soon_threadsafe(_arm)
        return handle
