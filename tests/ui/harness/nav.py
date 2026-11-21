"""Navigation helper for harness Playwright tests."""

import time
from typing import Callable

from playwright.sync_api import Error as PlaywrightError
from playwright.sync_api import Page


def goto_ready(page: Page, url: str) -> None:
    """Navigate and wait until the NiceGUI client is actually interactive.

    A rendered DOM (``wait_for_selector``) does not mean the page is safe to
    interact with: ``updateValue`` sync messages queued during server-side
    render are flushed to the browser only after the websocket connects, and
    an edit typed before that flush lands gets stomped back to the server
    value (which re-emits the old value, silently reverting the edit
    server-side). Every harness page queues a ``data-hw-synced`` body stamp
    as its LAST message (see ``routes._stamp_synced``), so once it appears,
    all pending sync messages have been applied and input is safe.
    """
    page.goto(url)
    page.wait_for_function("() => document.body.dataset.hwSynced === '1'")


def wait_for_canvas_settled(page: Page, timeout: int = 10_000) -> None:
    """Wait until the canvas has centred itself and its pan/zoom transform stops changing.

    ``goto_ready`` returns once the server's messages are applied, but the
    canvas then centres itself (``ZoomPan.center_on_content`` →
    ``fitToContent``), which moves every pin. Geometry read before that
    settles is read mid-flight.

    The centring is a round trip through the server, so it can land any time
    after ``goto_ready``. A harness canvas marks it (``routes._centre_when_ready``):
    while a ``data-hw-fit-pending`` container lacks ``data-hw-fit-done``, this
    keeps waiting. Then it watches ``.zoom-pan-content``'s transform, held equal
    across two animation frames. Returns immediately on a page with no canvas.
    """
    page.wait_for_function(
        """() => {
            const pending = [...document.querySelectorAll('[data-hw-fit-pending]')];
            if (pending.some(e => !e.dataset.hwFitDone)) return false;
            const el = document.querySelector('.zoom-pan-content');
            if (!el) return true;
            const now = getComputedStyle(el).transform;
            const settled = window.__hwLastTransform === now;
            window.__hwLastTransform = now;
            return settled;
        }""",
        timeout=timeout,
    )


def next_frames(page: Page, frames: int = 2) -> None:
    """Return after the browser has run *frames* animation frames.

    For work the page defers to ``requestAnimationFrame`` (an edge repaint, a cull
    pass): a callback the page queued before this call runs before it returns,
    whatever the machine's load, because frame callbacks run in the order queued.
    Each extra frame covers one more hop of rAF-scheduling-rAF.
    """
    page.evaluate(
        """(n) => new Promise(done => {
            const step = (left) => left ? requestAnimationFrame(() => step(left - 1)) : done();
            step(n);
        })""",
        frames,
    )


def wait_until(page: Page, check: Callable[[], object], timeout: int = 5000, interval: int = 50) -> bool:
    """Poll *check* until it returns something true, or *timeout* ms have passed; return whether it did.

    For a result that arrives after a round trip to the server or a repaint: how long
    that takes varies with the machine, so a fixed wait is either too short or wasted.
    Running out of time does not raise: the test's own assertion then reports what is
    there. A *check* that fails on a page mid-redraw counts as not yet true.

    Not for asserting that nothing happens: there a fixed wait is the only choice.
    """
    deadline = time.monotonic() + timeout / 1000
    while True:
        try:
            if check():
                return True
        except (PlaywrightError, AssertionError):
            pass
        if time.monotonic() >= deadline:
            return False
        page.wait_for_timeout(interval)
