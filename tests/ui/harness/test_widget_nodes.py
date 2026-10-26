"""Widget nodes on a stage in level mode operate, driven through a real browser.

The ``/graph-widget-nodes`` route puts a Float Slider and a Menu on a stage canvas
and wires the slider into a Float Number off stage. Polled echoes show what the
number's inlet and the menu's outlet hold, so these assert what reached the model.
"""

import pytest
from playwright.sync_api import Page, expect

from tests.ui.harness.nav import goto_ready, wait_for_canvas_settled

_PATH = "/graph-widget-nodes"

pytestmark = pytest.mark.ui


def _open(page: Page, harness, mode: str = "operate") -> None:
    goto_ready(page, f"{harness}{_PATH}?mode={mode}")
    page.wait_for_selector(".ui-node-slot")
    wait_for_canvas_settled(page)
    # Fit-to-content zooms out as the stage fills; measure at zoom 1, the top-left in view.
    page.evaluate(
        """() => {
            const c = document.querySelector('.zoom-pan-container')._zoomPanControls;
            c.setZoom(1); c.setPan(0, 0);
        }"""
    )
    wait_for_canvas_settled(page)


def _card(page: Page, name: str):
    node_id = page.locator(f'[data-testid="{name}-node-id"]').get_attribute("data-node")
    return page.locator(f'[id="{node_id}"]')


def test_an_operator_drives_a_slider_on_a_locked_stage(page: Page, harness):
    _open(page, harness)
    slider = _card(page, "slider").locator(".q-slider").first
    expect(slider).to_be_visible()
    box = slider.bounding_box()
    assert box is not None
    y = box["y"] + box["height"] / 2
    page.mouse.move(box["x"] + 2, y)
    page.mouse.down()
    page.mouse.move(box["x"] + box["width"] + 20, y, steps=8)
    page.mouse.up()
    expect(page.locator('[data-testid="echo-downstream"]')).to_have_text("1.0")


def test_the_stage_shows_label_left_of_the_control(page: Page, harness):
    _open(page, harness)
    card = _card(page, "slider")
    label = card.locator("[data-widget-node-label]").bounding_box()
    control = card.locator(".q-slider").first.bounding_box()
    assert label is not None
    assert control is not None
    assert label["x"] + label["width"] <= control["x"]
    assert label["y"] < control["y"] + control["height"]
    assert control["y"] < label["y"] + label["height"]


def test_the_stage_card_has_no_pins(page: Page, harness):
    _open(page, harness)
    expect(_card(page, "slider").locator(".connection-pin")).to_have_count(0)


def test_a_menu_pick_on_stage_sends_the_item(page: Page, harness):
    _open(page, harness)
    _card(page, "menu").locator(".q-select").first.click()
    page.get_by_role("option", name="Two").click()
    expect(page.locator('[data-testid="echo-menu"]')).to_have_text("Two")


def _box(locator) -> dict:
    box = locator.bounding_box()
    assert box is not None
    return box


def test_a_tall_card_centres_label_and_control_vertically(page: Page, harness):
    _open(page, harness)
    card = _card(page, "slider")
    slot = _box(card.locator(".ui-node-slot").first)
    label = _box(card.locator("[data-widget-node-label]"))
    control = _box(card.locator(".q-slider").first)
    middle = slot["y"] + slot["height"] / 2
    assert slot["height"] >= 110, slot
    assert abs(label["y"] + label["height"] / 2 - middle) < 6
    assert abs(control["y"] + control["height"] / 2 - middle) < 10


def test_a_wide_card_gives_the_control_the_extra_width(page: Page, harness):
    # The settings panel's rule (app/shell.py): from 320px the label is 9rem.
    _open(page, harness)
    card = _card(page, "slider")
    label = _box(card.locator("[data-widget-node-label]"))
    control = _box(card.locator("[data-hw-requires=operate]").first)
    root_px = page.evaluate("() => parseFloat(getComputedStyle(document.documentElement).fontSize)")
    slot = _box(card.locator(".ui-node-slot").first)
    assert abs(label["width"] - 9 * root_px) < 2
    assert control["width"] > label["width"]
    assert label["width"] + control["width"] > slot["width"] - 12, "the control takes the rest"


def test_a_narrow_card_splits_label_and_control_evenly(page: Page, harness):
    _open(page, harness)
    card = _card(page, "narrow")
    label = _box(card.locator("[data-widget-node-label]"))
    control = _box(card.locator("[data-hw-requires=operate]").first)
    assert abs(label["width"] - control["width"]) < 4


def test_fields_render_at_the_compact_height(page: Page, harness):
    _open(page, harness)
    field = _box(_card(page, "menu").locator(".q-field__control").first)
    height = page.evaluate(
        "() => parseFloat(getComputedStyle(document.documentElement)"
        ".getPropertyValue('--hw-compact-field-h'))"
    )
    assert abs(field["height"] - height) < 1


def test_an_auto_sized_card_keeps_its_floor(page: Page, harness):
    # A size container ignores its content's width; the card's own floor holds it open.
    _open(page, harness)
    card = _card(page, "menu")
    assert _box(card.locator(".ui-node-slot").first)["width"] >= 180
    assert _box(card.locator("[data-hw-requires=operate]").first)["width"] > 40


def test_a_label_above_sits_over_its_control(page: Page, harness):
    _open(page, harness)
    card = _card(page, "styled")
    label = _box(card.locator("[data-widget-node-label]"))
    control = _box(card.locator(".q-slider").first)
    assert label["y"] + label["height"] <= control["y"] + 1
    assert label["width"] > 300
    assert control["width"] > 300


def test_a_max_label_width_caps_the_label(page: Page, harness):
    _open(page, harness)
    wide = _card(page, "capped")
    label = _box(wide.locator("[data-widget-node-label]"))
    control = _box(wide.locator("[data-hw-requires=operate]").first)
    assert abs(label["width"] - 80) < 2
    assert control["width"] > 250

    narrow = _card(page, "capped_narrow")
    label = _box(narrow.locator("[data-widget-node-label]"))
    control = _box(narrow.locator("[data-hw-requires=operate]").first)
    assert abs(label["width"] - control["width"]) < 4


def _press_and_drag(page: Page, locator, dx: float) -> None:
    locator.scroll_into_view_if_needed()
    box = _box(locator)
    x, y = box["x"] + box["width"] / 2, box["y"] + box["height"] / 2
    page.mouse.move(x, y)
    page.mouse.down()
    page.mouse.move(x + dx, y, steps=8)
    page.mouse.up()


def test_an_edit_widget_keeps_its_press_in_edit(page: Page, harness):
    _open(page, harness, "edit")
    card = _card(page, "locked")
    expect(card.locator(".q-slider[data-hw-requires=edit]")).to_have_count(1)
    card.scroll_into_view_if_needed()
    before = _box(card)

    _press_and_drag(page, card.locator(".q-slider").first, 60)
    page.wait_for_timeout(300)

    after = _box(card)
    assert (after["x"], after["y"]) == (before["x"], before["y"]), "the press dragged the card"


def test_the_label_of_a_widget_node_drags_the_card_in_edit(page: Page, harness):
    _open(page, harness, "edit")
    card = _card(page, "locked")
    card.scroll_into_view_if_needed()
    before = _box(card)

    _press_and_drag(page, card.locator("[data-widget-node-label]"), 60)

    page.wait_for_function(
        "([id, x]) => document.getElementById(id).getBoundingClientRect().x > x + 30",
        arg=[card.get_attribute("id"), before["x"]],
    )
