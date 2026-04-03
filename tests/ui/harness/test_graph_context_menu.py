"""Regression tests for graph canvas context-menu routing through the zoom viewport."""

import pytest
from playwright.sync_api import Page, expect

_URL = "http://localhost:8090/graph-context-menu"

pytestmark = pytest.mark.ui


def test_right_click_on_viewport_background_emits_canvas_context_menu(page: Page, harness):
    """Right-clicking viewport background still reaches the graph canvas menu pipeline."""
    page.goto(_URL)
    page.wait_for_selector('[data-testid="zoom-pan-test"]')

    viewport = page.get_by_test_id("zoom-pan-test")
    box = viewport.bounding_box()
    assert box is not None

    page.mouse.click(
        box["x"] + box["width"] - 20,
        box["y"] + (box["height"] / 2),
        button="right",
    )

    expect(page.get_by_test_id("last-event")).to_have_text("contextMenuCanvas")
