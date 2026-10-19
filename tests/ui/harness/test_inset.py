"""An Inset in a real browser: its widgets operate, everything else is the host card's.

The ``/graph-inset`` route draws a Group card with the Inset skin; its interior
puts a Float Slider on stage. Polled echoes show the slider's value and whether
the host history can undo.
"""

from __future__ import annotations

import pytest
from playwright.sync_api import FloatRect, Locator, Page, expect

from tests.ui.harness.nav import goto_ready, wait_for_canvas_settled
from tests.ui.harness.probe import attr

_PATH = "/graph-inset"

pytestmark = pytest.mark.ui


def _open(page: Page, harness, mode: str) -> str:
    """Open the page in ``mode``; return the Inset card's id."""
    goto_ready(page, f"{harness}{_PATH}?mode={mode}")
    page.wait_for_selector("[data-hw-inset] .q-slider")
    wait_for_canvas_settled(page)
    return attr(page, '[data-testid="inset-card-id"]', "data-node")


def _slider(page: Page) -> Locator:
    return page.locator("[data-hw-inset] .q-slider").first


def _drag_slider_right(page: Page) -> None:
    slider = _slider(page)
    slider.scroll_into_view_if_needed()
    found = slider.bounding_box()
    assert found is not None
    y = found["y"] + found["height"] / 2
    page.mouse.move(found["x"] + 2, y)
    page.mouse.down()
    page.mouse.move(found["x"] + found["width"] + 20, y, steps=8)
    page.mouse.up()


def _body_box(page: Page) -> FloatRect:
    body = page.locator("[data-hw-inset]").first
    body.scroll_into_view_if_needed()
    found = body.bounding_box()
    assert found is not None
    return found


def _expect_selected(page: Page, node_id: str) -> None:
    """The canvas's server-side selection is exactly ``node_id``."""
    expect(page.locator('[data-testid="echo-selection"]')).to_have_text(node_id)


def test_a_slider_in_an_inset_writes_the_interior_value(page: Page, harness):
    _open(page, harness, "operate")

    _drag_slider_right(page)

    expect(page.locator('[data-testid="echo-inset-value"]')).to_have_text("1.0")


def test_an_inset_write_in_edit_is_an_undo_step(page: Page, harness):
    _open(page, harness, "edit")
    expect(page.locator('[data-testid="echo-undo"]')).to_have_text("False")

    _drag_slider_right(page)

    expect(page.locator('[data-testid="echo-inset-value"]')).to_have_text("1.0")
    expect(page.locator('[data-testid="echo-undo"]')).to_have_text("True")


def test_a_view_session_cannot_move_the_inset_slider(page: Page, harness):
    _open(page, harness, "view")
    before = page.locator('[data-testid="echo-inset-value"]').inner_text()

    _drag_slider_right(page)
    page.wait_for_timeout(500)

    expect(page.locator('[data-testid="echo-inset-value"]')).to_have_text(before)


def test_a_press_on_the_body_selects_the_host_card(page: Page, harness):
    card_id = _open(page, harness, "edit")
    body = _body_box(page)

    # Low in the body, clear of the slider widget and of the card's resize grip.
    page.mouse.click(body["x"] + body["width"] / 2, body["y"] + body["height"] - 25)

    _expect_selected(page, card_id)


def test_a_press_on_an_interior_card_selects_the_host_card(page: Page, harness):
    card_id = _open(page, harness, "edit")
    label = page.locator("[data-hw-inset] [data-widget-node-label]").first
    label.scroll_into_view_if_needed()
    found = label.bounding_box()
    assert found is not None

    page.mouse.click(found["x"] + found["width"] / 2, found["y"] + found["height"] / 2)

    _expect_selected(page, card_id)


def test_box_select_takes_the_inset_card_not_its_interior(page: Page, harness):
    card_id = _open(page, harness, "edit")
    card = page.locator(f'[data-node-id="{card_id}"] .ui-node-slot').first
    card.scroll_into_view_if_needed()
    found = card.bounding_box()
    assert found is not None

    page.mouse.move(found["x"] - 30, found["y"] - 30)
    page.mouse.down()
    page.mouse.move(found["x"] + found["width"] + 30, found["y"] + found["height"] + 30, steps=10)
    page.mouse.up()

    _expect_selected(page, card_id)


def test_a_press_on_an_interior_card_hits_the_body_not_the_card(page: Page, harness):
    _open(page, harness, "edit")
    note = page.locator("[data-hw-inset] [data-hw-inset-node]").nth(1)
    note.scroll_into_view_if_needed()

    hits_interior = page.evaluate(
        """(note) => {
            const r = note.getBoundingClientRect();
            const el = document.elementFromPoint(r.x + r.width / 2, r.y + r.height / 2);
            return !!el && !!el.closest('[data-hw-inset-node]');
        }""",
        note.element_handle(),
    )

    assert hits_interior is False


def test_inset_pins_are_not_displayed(page: Page, harness):
    _open(page, harness, "edit")

    displays = page.evaluate(
        "() => Array.from(document.querySelectorAll('[data-hw-inset] [data-pin-id]'))"
        ".map(p => getComputedStyle(p).display)"
    )

    assert displays
    assert set(displays) == {"none"}


def test_a_manually_sized_inset_keeps_its_interior_cards_shape(page: Page, harness):
    goto_ready(page, f"{harness}{_PATH}?mode=edit&size=manual")
    page.wait_for_selector("[data-hw-inset] .q-slider")
    wait_for_canvas_settled(page)

    # The widget-node face floors its card at 180px; the host's manual size must not release it.
    min_width = page.evaluate(
        "() => getComputedStyle(document.querySelector('[data-hw-inset] .node-card')).minWidth"
    )

    assert min_width == "180px"


def test_culling_keeps_an_inset_s_interior_drawn(page: Page, harness):
    goto_ready(page, f"{harness}{_PATH}?mode=edit&cull=1")
    page.wait_for_selector("[data-hw-inset] .q-slider")
    wait_for_canvas_settled(page)

    page.locator('[data-testid="enable-culling"]').click()
    page.wait_for_timeout(500)

    # The host card is in view, so what it draws stays drawn.
    expect(_slider(page)).to_be_visible()


@pytest.mark.parametrize("view", ["patch", "stage"])
def test_the_body_fills_a_manually_sized_card(page: Page, harness, view: str):
    goto_ready(page, f"{harness}{_PATH}?mode=edit&size=manual&view={view}")
    page.wait_for_selector("[data-hw-inset] .q-slider")
    wait_for_canvas_settled(page)

    sizes = page.evaluate(
        """() => {
            const body = document.querySelector('[data-hw-inset]');
            const card = body.closest('.node-card');
            const b = body.getBoundingClientRect(), c = card.getBoundingClientRect();
            return {bw: b.width, bh: b.height, cw: c.width, ch: c.height,
                    gapRight: c.right - b.right, gapBottom: c.bottom - b.bottom};
        }"""
    )

    # The body reaches (within the card's padding) the card's right and bottom edges.
    assert sizes["gapRight"] < 40, sizes
    assert sizes["gapBottom"] < 40, sizes
