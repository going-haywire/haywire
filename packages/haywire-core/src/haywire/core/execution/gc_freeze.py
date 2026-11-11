"""Keeps the garbage collector off the long-lived heap while graphs run.

A full collection walks every tracked object in the process, which takes tens of milliseconds in a studio
with its libraries and UI loaded. Audio and video flows feel that as a pause. While at least one graph
runs, the objects alive at its start sit in the collector's permanent generation and later collections skip
them.

The collector belongs to the process, so the count of running graphs is shared by every ``Interpreter``.
"""

import gc
import threading
from collections.abc import Iterator
from contextlib import contextmanager

_lock = threading.Lock()
_running = 0
_pausers = 0
_was_enabled = True


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


@contextmanager
def collection_paused() -> Iterator[None]:
    """Keep the collector off while a burst of long-lived objects is built, such as a graph's UI.

    A collection during the burst rescans everything built so far and survives none of it. When the last
    overlapping pause ends, the collector runs again, and the new objects join the frozen heap if a
    graph is running. A collector that was already off stays off.
    """
    global _pausers, _was_enabled
    with _lock:
        if _pausers == 0:
            _was_enabled = gc.isenabled()
            gc.disable()
        _pausers += 1
    try:
        yield
    finally:
        with _lock:
            _pausers -= 1
            if _pausers == 0:
                if _running:
                    gc.freeze()
                if _was_enabled:
                    gc.enable()


def running_graphs() -> int:
    """Return how many graphs currently hold the freeze."""
    return _running
