"""An open context menu takes no input outside its card: a press there closes it and reaches the page."""

import pytest
from playwright.sync_api import Page, expect

from tests.ui.harness.nav import goto_ready, wait_for_canvas_settled
from tests.ui.harness.test_edge_style_menu import _PATH, _POPUP, _STYLED, _open_edge_menu

#: A menu on screen; a closed one stays in the DOM, hidden.
_SHOWN = f"{_POPUP}:visible"

pytestmark = pytest.mark.ui


def _open(page: Page, harness) -> dict:
    """Open the styled edge's menu; return a point on the empty canvas, away from it."""
    goto_ready(page, f"{harness}{_PATH}")
    page.wait_for_selector(_STYLED)
    wait_for_canvas_settled(page)
    _open_edge_menu(page)
    return _empty_canvas_point(page)


def _empty_canvas_point(page: Page) -> dict:
    """The first point on screen, scanning from the bottom right, whose topmost element is
    the canvas itself: no node, edge, menu or overlay."""
    point = page.evaluate(
        """() => {
            for (let y = window.innerHeight - 20; y > 0; y -= 20) {
                for (let x = window.innerWidth - 20; x > 0; x -= 20) {
                    const el = document.elementFromPoint(x, y);
                    const onCanvas = el && el.closest('[data-canvas-ready]');
                    if (onCanvas && !el.closest('[data-node-id], .hw-edge, .hw-popup-overlay')) {
                        return { x, y };
                    }
                }
            }
            return null;
        }"""
    )
    assert point is not None, "no empty canvas on screen"
    return point


def test_a_press_outside_closes_the_menu(page: Page, harness) -> None:
    outside = _open(page, harness)

    page.mouse.click(outside["x"], outside["y"])

    expect(page.locator(_SHOWN)).to_have_count(0)


def test_a_press_outside_reaches_the_page(page: Page, harness) -> None:
    outside = _open(page, harness)
    page.evaluate(
        """() => {
            window.__hit = null;
            document.addEventListener('pointerdown', e => window.__hit = e.target.className, { once: true });
        }"""
    )

    page.mouse.click(outside["x"], outside["y"])

    assert "hw-popup" not in str(page.evaluate("() => window.__hit"))


def test_a_right_click_outside_opens_the_next_menu_in_one_gesture(page: Page, harness) -> None:
    outside = _open(page, harness)

    page.mouse.click(outside["x"], outside["y"], button="right")

    expect(page.locator(_SHOWN)).to_have_count(1)
    expect(page.locator(f"{_SHOWN} >> text=Style")).to_have_count(0)


def test_a_wheel_outside_closes_the_menu(page: Page, harness) -> None:
    outside = _open(page, harness)

    page.mouse.move(outside["x"], outside["y"])
    page.mouse.wheel(0, 120)

    expect(page.locator(_SHOWN)).to_have_count(0)
