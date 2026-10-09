"""The selection toolbar over edges: shown for an edge selection; its Style icon follows the form rule."""

import pytest
from playwright.sync_api import Page

from tests.ui.harness.nav import goto_ready, wait_for_canvas_settled

_PATH = "/graph-edge-appearance"
_STYLED = 'path.hw-edge[data-edge-id*="[note_out]->"]'
_COMPUTED = 'path.hw-edge[data-edge-id*="[result]->"]'
_TOOLBAR = ".hw-selection-toolbar"

pytestmark = pytest.mark.ui


def _open(page: Page, harness) -> None:
    goto_ready(page, f"{harness}{_PATH}")
    page.wait_for_selector(_STYLED)
    wait_for_canvas_settled(page)


def _midpoint(page: Page, selector: str) -> list[float]:
    return page.evaluate(
        """(sel) => {
            const path = document.querySelector(sel);
            const ctm = path.ownerSVGElement.getScreenCTM();
            const p = path.getPointAtLength(path.getTotalLength() / 2);
            return [p.x * ctm.a + ctm.e, p.y * ctm.d + ctm.f];
        }""",
        selector,
    )


def _click(page: Page, selector: str, *, shift: bool = False) -> None:
    x, y = _midpoint(page, selector)
    if shift:
        page.keyboard.down("Shift")
    page.mouse.click(x, y)
    if shift:
        page.keyboard.up("Shift")


def _style_state(page: Page) -> str:
    """'live', 'greyed' or 'absent': the Style icon is a button whose glyph reads "style",
    greyed inside a ``hw-disabled`` wrapper. Read once the toolbar has re-rendered."""
    page.wait_for_selector(_TOOLBAR, state="visible", timeout=5000)
    page.wait_for_timeout(300)
    toolbar = page.locator(_TOOLBAR)
    if toolbar.locator(".hw-disabled").filter(has_text="style").count():
        return "greyed"
    if toolbar.locator(".q-btn").filter(has_text="style").count():
        return "live"
    return "absent"


def test_selecting_one_styled_edge_shows_the_toolbar_with_style(page: Page, harness) -> None:
    _open(page, harness)
    _click(page, _STYLED)
    assert _style_state(page) == "live"


def test_a_styled_and_an_unstyled_edge_grey_style_with_a_reason(page: Page, harness) -> None:
    _open(page, harness)
    _click(page, _STYLED)
    _click(page, _COMPUTED, shift=True)
    assert _style_state(page) == "greyed"


def test_an_unstyled_edge_alone_shows_the_toolbar_without_style(page: Page, harness) -> None:
    _open(page, harness)
    _click(page, _COMPUTED)
    assert _style_state(page) == "absent"
