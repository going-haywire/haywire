"""Keyboard focus inside the graph canvas: Tab order across NumberDrag widgets,
and the pan/zoom model staying true to what is drawn while focus moves.

A focused off-screen field makes the browser scroll the ``overflow: hidden``
zoom-pan container to reveal it. That scroll is invisible to the pan/zoom
model, so the zoom anchor drifts from the pointer until the scroll is reset.
"""

import pytest
from playwright.sync_api import Page

from tests.ui.harness.nav import goto_ready, wait_for_canvas_settled

pytestmark = pytest.mark.ui

_PATH = "/graph-edge-appearance"


def _focus_state(page: Page) -> dict:
    """Which NumberDrag holds focus (DOM index, -1 for none), the container's scroll, and visibility."""
    return page.evaluate(
        """() => {
            const zp = document.querySelector('.zoom-pan-container');
            const a = document.activeElement;
            const drags = [...document.querySelectorAll('[data-number_drag]')];
            const r = a.getBoundingClientRect(), c = zp.getBoundingClientRect();
            return {
                tag: a.tagName,
                idx: drags.findIndex(d => d.contains(a)),
                scroll: [zp.scrollLeft, zp.scrollTop],
                inView: r.left >= c.left && r.right <= c.right && r.top >= c.top && r.bottom <= c.bottom,
            };
        }"""
    )


def _drawn_vs_model_offset(page: Page) -> list[float]:
    """Pixel gap between where the content layer is drawn and where pan says it is."""
    return page.evaluate(
        """() => {
            const zp = document.querySelector('.zoom-pan-container');
            const r = zp.getBoundingClientRect(), p = zp._zoomPanControls.getPan();
            const drawn = zp.querySelector('.zoom-pan-content').getBoundingClientRect();
            return [drawn.left - (r.left + p.x), drawn.top - (r.top + p.y)];
        }"""
    )


def _park_first_node_mid_view(page: Page) -> None:
    """Zoom 1, first NumberDrag's node 450px from the left — its right-hand neighbour starts off-screen."""
    for _ in range(10):
        settled = page.evaluate(
            """() => {
                const c = document.querySelector('.zoom-pan-container')._zoomPanControls;
                let h = document.querySelector('[data-number_drag]').closest('[data-node-id]');
                let up;
                while ((up = h.parentElement.closest('[data-node-id]'))) h = up;
                const x = -parseFloat(h.style.left) + 450, y = -parseFloat(h.style.top) + 20;
                const p = c.getPan();
                if (c.getZoom() === 1 && p.x === x && p.y === y) return true;
                c.setZoom(1); c.setPan(x, y);
                return false;
            }"""
        )
        if settled:
            return
        # The canvas's own fit-to-content can land after our pan; set it again until it holds.
        page.wait_for_timeout(200)
    raise AssertionError("viewport did not settle at the parked position")


def _open(page: Page, harness) -> None:
    goto_ready(page, f"{harness}{_PATH}")
    page.wait_for_selector("[data-number_drag]")
    wait_for_canvas_settled(page)
    _park_first_node_mid_view(page)
    page.locator("[data-number_drag]").first.locator(".number-drag__center").click()
    state = _focus_state(page)
    assert (state["tag"], state["idx"]) == ("INPUT", 0), state


def test_tab_moves_to_the_next_number_widget(page: Page, harness) -> None:
    _open(page, harness)
    for expected in (1, 2):
        page.keyboard.press("Tab")
        page.wait_for_timeout(150)
        state = _focus_state(page)
        assert (state["tag"], state["idx"]) == ("INPUT", expected), state


def test_shift_tab_moves_to_the_previous_number_widget(page: Page, harness) -> None:
    _open(page, harness)
    page.keyboard.press("Tab")
    page.wait_for_timeout(150)
    page.keyboard.press("Shift+Tab")
    page.wait_for_timeout(150)
    state = _focus_state(page)
    assert (state["tag"], state["idx"]) == ("INPUT", 0), state


def test_tab_to_off_screen_field_pans_instead_of_scrolling(page: Page, harness) -> None:
    _open(page, harness)
    for _ in range(2):
        page.keyboard.press("Tab")
        page.wait_for_timeout(150)
        state = _focus_state(page)
        assert state["scroll"] == [0, 0], state
        assert state["inView"], state
    offset = _drawn_vs_model_offset(page)
    assert max(abs(v) for v in offset) < 1, offset


def test_shift_tab_reveals_field_left_of_view(page: Page, harness) -> None:
    _open(page, harness)
    for _ in range(2):
        page.keyboard.press("Tab")
        page.wait_for_timeout(150)
    page.keyboard.press("Shift+Tab")
    page.wait_for_timeout(200)
    state = _focus_state(page)
    assert (state["idx"], state["inView"], state["scroll"]) == (1, True, [0, 0]), state
