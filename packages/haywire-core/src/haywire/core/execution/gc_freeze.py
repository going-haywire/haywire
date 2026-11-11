"""Keeps the garbage collector off the long-lived heap while graphs run.

A full collection walks every tracked object in the process, which takes tens of milliseconds in a studio
with its libraries and UI loaded. Audio and video flows feel that as a pause. While at least one graph
runs, the objects alive at its start sit in the collector's permanent generation and later collections skip
them.

The collector belongs to the process, so the count of running graphs is shared by every ``Interpreter``.
"""

import gc
import threading

_lock = threading.Lock()
_running = 0


def freeze_for_run() -> None:
    """Move the live heap out of the collector's reach when the first graph starts running.

    Every call must be paired with one ``unfreeze_after_run()``.
    """
    global _running
    with _lock:
        if _running == 0:
            gc.collect()
            gc.freeze()
        _running += 1


def unfreeze_after_run() -> None:
    """Return the frozen heap to the collector when the last running graph stops."""
    global _running
    with _lock:
        if _running == 0:
            return
        _running -= 1
        if _running == 0:
            gc.unfreeze()
            gc.collect()


def running_graphs() -> int:
    """Return how many graphs currently hold the freeze."""
    return _running
