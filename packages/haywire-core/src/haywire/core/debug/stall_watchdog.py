"""Shows what holds the process when every thread stops for a moment.

A pause of tens of milliseconds that hits every thread at once means one thread holds the interpreter lock:
a long C call, a large serialisation, a garbage collection. A thread cannot report on itself while it holds
the lock, so the watchdog arms ``faulthandler`` before each short sleep. ``faulthandler`` runs on its own
C thread without the lock, and when the watchdog thread is not back in time it writes the stack of every
thread as it is at that moment. The report keeps the threads that were running code and leaves out the
ones parked in a wait.
"""

import faulthandler
import logging
import re
import tempfile
import threading
import time
from typing import IO

logger = logging.getLogger(__name__)

#: A thread whose newest frame is in one of these files is parked in a wait, not holding the process.
_IDLE_FRAME_FILES = (
    "/threading.py",
    "/queue.py",
    "/selectors.py",
    "/concurrent/futures/thread.py",
    "/site-packages/watchdog/",
    "/site-packages/websockets/",
)
_THREAD_HEADER = re.compile(r"^(Current thread|Thread) 0x[0-9a-f]+ \(most recent call first\):$")


def condense_dump(dump: str) -> tuple[str, int]:
    """Return the stacks of a ``faulthandler`` dump's busy threads and the count of parked ones left out.

    The dump's own ``Timeout (...)!`` line is dropped. Each kept thread keeps its full stack.
    """
    kept: list[str] = []
    omitted = 0
    for block in dump.strip().split("\n\n"):
        lines = [line for line in block.splitlines() if not line.startswith("Timeout (")]
        if not lines or not _THREAD_HEADER.match(lines[0]):
            continue
        top = lines[1] if len(lines) > 1 else ""
        if any(path in top for path in _IDLE_FRAME_FILES):
            omitted += 1
        else:
            kept.append("\n".join(lines))
    return "\n\n".join(kept), omitted


class StallWatchdog:
    """Reports the running threads' stacks when the process is held up longer than ``threshold_ms``.

    The report is logged as a warning, which reaches the terminal and the Log panel. Each beat re-arms
    ``faulthandler``, which starts a short-lived C thread, so the cost is small but not zero (about 80
    beats per second at 50 ms). Meant to be switched on while chasing a pause.

    Example::

        watchdog = StallWatchdog(50)
        watchdog.start()   # a pause over 50 ms now logs a warning with the stacks of the busy threads
        watchdog.stop()
    """

    def __init__(self, threshold_ms: int, file: IO[str] | None = None) -> None:
        """Create a watchdog; ``file``, when given, also receives each report."""
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
        with tempfile.TemporaryFile("w+") as dump:
            while not self._stop.is_set():
                armed = time.monotonic()
                faulthandler.dump_traceback_later(self._threshold, file=dump)
                self._stop.wait(self._beat)
                faulthandler.cancel_dump_traceback_later()
                elapsed = time.monotonic() - armed
                if elapsed > self._threshold:
                    self._report(dump, elapsed)

    def _report(self, dump: IO[str], elapsed: float) -> None:
        dump.seek(0)
        stacks, omitted = condense_dump(dump.read())
        dump.seek(0)
        dump.truncate()
        report = (
            f"Stall watchdog: the process was held up for about {elapsed * 1000:.0f} ms "
            f"({omitted} parked threads left out)\n{stacks}"
        )
        logger.warning(report)
        if self._file is not None:
            self._file.write(report + "\n")
            self._file.flush()
