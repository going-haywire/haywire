"""Waiting on another thread's state in plain tests, the counterpart of ``tests.ui.user_wait.eventually``."""

from __future__ import annotations

import time
from collections.abc import Callable


def wait_until(check: Callable[[], object], timeout_s: float = 10.0, interval_s: float = 0.005) -> bool:
    """Poll *check* until it returns something true, or *timeout_s* has passed; return whether it did.

    For a result a worker thread, a timer or a server delivers: how long that takes varies
    with the machine's load, so a fixed sleep is either too short or wasted. The timeout only
    bounds a failing run, so make it generous. Running out of time does not raise: the
    test's own assertion then reports what is there.

    Not for asserting that nothing happens: there a fixed sleep is the only choice.

    Example::

        runner.start()
        wait_until(lambda: len(ran) == 3)
        assert ran == ["a", "b", "c"]
    """
    deadline = time.monotonic() + timeout_s
    while True:
        if check():
            return True
        if time.monotonic() >= deadline:
            return False
        time.sleep(interval_s)
