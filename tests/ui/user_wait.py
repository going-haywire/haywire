"""Waiting in NiceGUI user-simulation tests, the counterpart of ``tests.ui.harness.nav.wait_until``."""

import asyncio
import time
from collections.abc import Callable


async def eventually(check: Callable[[], object], timeout_s: float = 5.0, interval_s: float = 0.01) -> bool:
    """Poll *check* until it returns something true, or *timeout_s* has passed; return whether it did.

    For a result that a ``ui.timer`` or an event handler delivers on the event loop: how
    long that takes varies with the machine, so a fixed sleep is either too short or wasted.
    Running out of time does not raise: the test's own assertion then reports what is there.

    Not for asserting that nothing happens: there a fixed sleep is the only choice.

    Example::

        _hover(user, row._row)
        await eventually(lambda: row._menu.value is True)
        assert row._menu.value is True
    """
    deadline = time.monotonic() + timeout_s
    while True:
        if check():
            return True
        if time.monotonic() >= deadline:
            return False
        await asyncio.sleep(interval_s)
