"""Shortens the interpreter's thread switch interval while graphs run.

A thread that wants the interpreter lock waits for the running thread to hand it over, which happens after
the switch interval (5 ms by default) at the latest. A flow pass releases the lock at every numpy call, file
read and queue wait, and each time it must queue for it again. While the studio builds a large graph's
interface in a CPU-bound thread, every one of those waits costs a full interval, and a pass that makes ten
of them misses its block period by tens of milliseconds, with no single long hold for a watchdog to find.

The interval belongs to the process, so the count of running graphs is shared by every ``Interpreter``.
"""

import sys
import threading

#: Seconds a thread keeps the interpreter lock while another waits for it, during a run.
RUN_SWITCH_INTERVAL = 0.0005

_lock = threading.Lock()
_running = 0
_previous = 0.005


def shorten_for_run() -> None:
    """Set the short switch interval when the first graph starts running.

    Every call must be paired with one ``restore_after_run()``.
    """
    global _running, _previous
    with _lock:
        if _running == 0:
            _previous = sys.getswitchinterval()
            sys.setswitchinterval(RUN_SWITCH_INTERVAL)
        _running += 1


def restore_after_run() -> None:
    """Put the previous switch interval back when the last running graph stops."""
    global _running
    with _lock:
        if _running == 0:
            return
        _running -= 1
        if _running == 0:
            sys.setswitchinterval(_previous)


def running_graphs() -> int:
    """Return how many graphs currently hold the short interval."""
    return _running
