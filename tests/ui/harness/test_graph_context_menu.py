"""Regression tests for graph canvas context-menu routing through the zoom viewport."""

import pytest
from playwright.sync_api import Page, expect

from tests.ui.harness.nav import goto_ready

_URL = "http://localhost:8090/graph-context-menu"

pytestmark = pytest.mark.ui


def test_right_click_on_viewport_background_emits_canvas_context_menu(page: Page, harness):
    """Right-clicking viewport background still reaches the graph canvas menu pipeline."""
    goto_ready(page, _URL)
    # Wait for the canvas to finish mounting (listeners attached), not merely
    # for the viewport div to exist — otherwise the right-click can fire before
    # the contextmenu handler is wired and the event is lost (flaky).
    page.wait_for_selector("[data-canvas-ready]")

    viewport = page.get_by_test_id("zoom-pan-test")
    box = viewport.bounding_box()
    assert box is not None

    page.mouse.click(
        box["x"] + box["width"] - 20,
        box["y"] + (box["height"] / 2),
        button="right",
    )

    # Assert on the dedicated context-menu latch, not the shared last-event
    # label: a right-click also emits selectionBoundsHide, which would race to
    # overwrite last-event. last-context-menu is written only by context-menu
    # events, so this is deterministic.
    expect(page.get_by_test_id("last-context-menu")).to_have_text("contextMenuCanvas")
