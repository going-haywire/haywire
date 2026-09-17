"""The blocking load overlay must come down when the graph is drawn, not on a timeout.

``_await_client_drawn`` holds the overlay until the browser confirms the edges.
Getting its condition wrong does not fail loudly — it waits out its own 20 s
deadline and then releases, so the only symptom is an overlay that sits there
long after the graph is visible behind it. Two ways that happened:

* counting drawn paths against the graph's edge total, which a culled node makes
  unreachable;
* waiting for an edge batch to arrive after the wait began, when the batch had
  already gone out — the validation scheduler is a daemon timer, so it emits the
  edges DURING the node loop, and the loop's own pass then emits nothing.

A wall-clock assertion, which this file otherwise avoids, because the failure IS
a duration: both bugs draw the right graph, just minutes of overlay later.
"""

import time

import pytest
from playwright.sync_api import Page

from tests.ui.harness.nav import goto_ready

_URL = "http://localhost:8090/graph-chunked-load"

pytestmark = pytest.mark.ui

#: The overlay's own deadline is 20 s. Anything at or past it is the bug; this
#: fixture draws in well under a second, so the margin is wide either way.
_MAX_OVERLAY_SECONDS = 12.0

_OVERLAY = "text=The canvas is locked until the graph is fully drawn."

#: Enough nodes to make a real chunked load out of.
_NODES = 80


def test_the_canvas_is_handed_back_promptly(page: Page, harness):
    """Timed from the navigation, not from the overlay appearing.

    Deliberately does not wait for the overlay to show first: on a warm server
    this fixture can load faster than Playwright can catch it, and an overlay
    too quick to see is the passing case, not a failure. What is being measured
    is the time to a usable canvas, which is what both bugs blew out.
    """
    started = time.monotonic()
    page.goto(f"{_URL}?nodes={_NODES}")
    page.wait_for_selector(_OVERLAY, state="detached", timeout=25_000)
    elapsed = time.monotonic() - started

    assert elapsed < _MAX_OVERLAY_SECONDS, (
        f"the load overlay stayed up {elapsed:.1f}s — it is waiting out its deadline, "
        "not waiting for the edges"
    )


def test_the_edges_are_on_screen_when_it_releases(page: Page, harness):
    """The overlay exists to hide a half-drawn canvas; releasing early defeats it."""
    goto_ready(page, f"{_URL}?nodes={_NODES}")
    page.wait_for_selector(_OVERLAY, state="detached", timeout=25_000)

    drawn = page.evaluate(
        """() => document.querySelectorAll(
            '.graph-canvas[data-testid="chunked-canvas"] .connection-svg path[data-edge-id]'
        ).length / 2"""
    )

    assert drawn == _NODES - 1
