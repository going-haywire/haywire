"""A styled edge's Style fields in its context menu: a picker opened there works and keeps the menu open."""

import pytest
from playwright.sync_api import Page

from tests.ui.harness.nav import goto_ready, wait_for_canvas_settled
from tests.ui.harness.test_edge_appearance import _computed

_PATH = "/graph-edge-appearance"
_STYLED = 'path.hw-edge[data-edge-id*="[note_out]->"]'
_POPUP = ".hw-popup-card"

pytestmark = pytest.mark.ui


def _open_edge_menu(page: Page) -> None:
    point = page.evaluate(
        """(sel) => {
            const path = document.querySelector(sel);
            const pt = path.getPointAtLength(path.getTotalLength() * 0.5);
            const m = path.getScreenCTM();
            return { x: m.a*pt.x + m.c*pt.y + m.e, y: m.b*pt.x + m.d*pt.y + m.f };
        }""",
        _STYLED,
    )
    page.mouse.click(point["x"], point["y"], button="right")
    page.wait_for_selector(f"{_POPUP} >> text=Dash")


def _open(page: Page, harness) -> None:
    goto_ready(page, f"{harness}{_PATH}")
    page.wait_for_selector(_STYLED)
    wait_for_canvas_settled(page)
    _open_edge_menu(page)


def test_a_select_in_the_edge_menu_applies_and_keeps_the_menu_open(page: Page, harness) -> None:
    _open(page, harness)
    page.locator(f"{_POPUP} .q-select").first.click()
    page.locator(".q-menu .q-item", has_text="Dotted").click()
    page.wait_for_function(
        "(sel) => getComputedStyle(document.querySelector(sel)).strokeDasharray.startsWith('2')",
        arg=_STYLED,
        timeout=5000,
    )
    assert page.locator(_POPUP).is_visible()


def test_the_head_picker_in_the_edge_menu_applies_and_keeps_the_menu_open(page: Page, harness) -> None:
    _open(page, harness)
    assert "-arrow" in _computed(page, _STYLED, "markerEnd")
    # The last two buttons in the Style fields are the start and end head pickers.
    page.locator(f"{_POPUP} .q-btn").filter(has=page.locator("svg")).last.click()
    menu = page.locator(".q-menu").last
    menu.wait_for()
    # Grid order: None, then the four common heads (arrow, sharp, open, triangle).
    menu.locator(".q-btn").nth(3).click()
    page.wait_for_function(
        "(sel) => getComputedStyle(document.querySelector(sel)).markerEnd.includes('-open')",
        arg=_STYLED,
        timeout=5000,
    )
    assert page.locator(_POPUP).is_visible()


def test_the_colour_field_in_the_edge_menu_applies_and_keeps_the_menu_open(page: Page, harness) -> None:
    _open(page, harness)
    field = page.locator(f"{_POPUP} input").first
    field.fill("#ff0000")
    field.press("Enter")
    page.wait_for_function(
        "(sel) => getComputedStyle(document.querySelector(sel)).stroke === 'rgb(255, 0, 0)'",
        arg=_STYLED,
        timeout=5000,
    )
    # The colour input's picker button opens a picker over the menu.
    page.locator(f"{_POPUP} .q-field").first.locator(".q-btn, .q-icon").last.click()
    page.wait_for_selector(".q-color-picker", state="visible", timeout=5000)
    assert page.locator(_POPUP).is_visible()
