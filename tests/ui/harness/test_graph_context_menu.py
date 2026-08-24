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


def test_innermost_menu_surface_id_wins_over_an_outer_one(page: Page, harness):
    """canvas.vue's handleContextMenu uses closest('[data-hw-menu-surface-id]'),
    so nested annotations resolve to the INNERMOST one — the old priority-
    ordered port/custom pair let an outer marker beat a nearer one; one
    attribute with closest() semantics fixes that. Injects two nested
    elements directly (no real surface/panel needed — this is testing
    canvas.vue's own DOM routing, not the Python-side surface resolution)."""
    goto_ready(page, _URL)
    page.wait_for_selector("[data-canvas-ready]")

    viewport = page.get_by_test_id("zoom-pan-test")
    box = viewport.bounding_box()
    assert box is not None

    # Inject an outer element tagged "outer-surface" containing an inner one
    # tagged "inner-surface", both inside the canvas so the click hits both.
    # z-index: 2 (above .connection-svg's z-index: 1, its own stacking
    # context — later DOM order alone does not beat an explicit z-index).
    page.evaluate(
        """() => {
            const canvasEl = document.querySelector('[data-testid="graph-canvas-test"]');
            const outer = document.createElement('div');
            outer.setAttribute('data-hw-menu-surface-id', 'outer-surface');
            outer.style.cssText =
                'position: absolute; left: 10px; top: 10px; width: 200px; height: 150px; z-index: 2;';
            const inner = document.createElement('div');
            inner.setAttribute('data-hw-menu-surface-id', 'inner-surface');
            inner.setAttribute('data-testid', 'inner-surface-el');
            inner.style.cssText =
                'position: absolute; left: 20px; top: 20px; width: 100px; height: 80px; z-index: 2;';
            outer.appendChild(inner);
            canvasEl.appendChild(outer);
        }"""
    )

    inner_el = page.get_by_test_id("inner-surface-el")
    inner_box = inner_el.bounding_box()
    assert inner_box is not None

    page.mouse.click(
        inner_box["x"] + inner_box["width"] / 2,
        inner_box["y"] + inner_box["height"] / 2,
        button="right",
    )

    expect(page.get_by_test_id("last-context-menu")).to_have_text("contextMenuSurface")
    expect(page.get_by_test_id("last-surface-id")).to_have_text("inner-surface")
