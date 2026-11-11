"""Shows what holds the process when every thread stops for a moment.

A pause of tens of milliseconds that hits every thread at once means one thread holds the interpreter lock:
a long C call, a large serialisation, a garbage collection. A thread cannot report on itself while it holds
the lock, so the watchdog arms ``faulthandler`` before each short sleep. ``faulthandler`` runs on its own
C thread without the lock, and when the watchdog thread is not back in time it prints the stack of every
thread as it is at that moment.
"""

import faulthandler
import logging
import threading
import time
from typing import IO

logger = logging.getLogger(__name__)


class StallWatchdog:
    """Prints every thread's stack when the process is held up longer than ``threshold_ms``.

    Each beat re-arms ``faulthandler``, which starts a short-lived C thread, so the cost is small but not
    zero (about 80 beats per second at 50 ms). Meant to be switched on while chasing a pause.

    Example::

        watchdog = StallWatchdog(50)
        watchdog.start()   # a pause over 50 ms now prints the stacks to stderr and logs a warning
        watchdog.stop()
    """

    def __init__(self, threshold_ms: int, file: IO[str] | None = None) -> None:
        """Create a watchdog; ``file`` receives the stacks (default: the process's real stderr)."""
        self._threshold = max(0.02, threshold_ms / 1000)
        self._beat = self._threshold / 4
        self._file = file
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None

    @property
    def running(self) -> bool:
        return self._thread is not None and self._thread.is_alive()

    def start(self) -> None:
        """Start watching. Does nothing if already running."""
        if self.running:
            return
        self._stop.clear()
        self._thread = threading.Thread(target=self._run, name="stall-watchdog", daemon=True)
        self._thread.start()

    def stop(self) -> None:
        """Stop watching and disarm the pending dump."""
        self._stop.set()
        if self._thread is not None and self._thread is not threading.current_thread():
            self._thread.join(timeout=2.0)
        self._thread = None
        faulthandler.cancel_dump_traceback_later()

    def _run(self) -> None:
        stream = self._file if self._file is not None else _stderr()
        if stream is None:
            logger.warning("Stall watchdog: no stderr to write to")
            return
        while not self._stop.is_set():
            armed = time.monotonic()
            faulthandler.dump_traceback_later(self._threshold, file=stream)
            self._stop.wait(self._beat)
            faulthandler.cancel_dump_traceback_later()
            elapsed = time.monotonic() - armed
            if elapsed > self._threshold:
                logger.warning("Stall watchdog: the process was held up for about %.0f ms", elapsed * 1000)


def _stderr() -> IO[str] | None:
    import sys

    return sys.__stderr__
