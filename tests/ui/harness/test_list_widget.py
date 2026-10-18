"""TextWidget's commit mode and ArrayWidget, driven through a real browser.

The ``/list-widget`` route echoes what each port's model holds, so these assert
what reached the model, not what a control displays. The text echo is
``"<value>|<writes>"``.
"""

import pytest
from playwright.sync_api import Page, expect

from tests.ui.harness.nav import goto_ready, wait_for_canvas_settled

_PATH = "/list-widget"

pytestmark = pytest.mark.ui


def _echo(page: Page, port_id: str):
    return page.locator(f'[data-testid="echo-{port_id}"]')


def _text_input(page: Page):
    return page.locator('[data-field="text_commit"] input').first


def _open(page: Page, harness) -> None:
    goto_ready(page, f"{harness}{_PATH}")
    page.wait_for_selector("[data-field]")


# ---------------------------------------------------------------------------
# TextWidget commit mode
# ---------------------------------------------------------------------------


def test_enter_writes_once(page: Page, harness):
    _open(page, harness)
    field = _text_input(page)
    field.click()
    field.press_sequentially("/data/scene.json")
    # Past one echo poll: nothing typed so far may have reached the model.
    page.wait_for_timeout(500)
    expect(_echo(page, "text_commit")).to_have_text("|0")

    field.press("Enter")
    expect(_echo(page, "text_commit")).to_have_text("/data/scene.json|1")


def test_blur_commits(page: Page, harness):
    _open(page, harness)
    field = _text_input(page)
    field.click()
    field.press_sequentially("abc")
    page.locator("body").click(position={"x": 5, "y": 5})
    expect(_echo(page, "text_commit")).to_have_text("abc|1")


def test_a_blur_without_change_writes_nothing(page: Page, harness):
    _open(page, harness)
    field = _text_input(page)
    field.click()
    page.locator("body").click(position={"x": 5, "y": 5})
    page.wait_for_timeout(500)
    expect(_echo(page, "text_commit")).to_have_text("|0")


# ---------------------------------------------------------------------------
# ArrayWidget
# ---------------------------------------------------------------------------


def _row(page: Page, port_id: str, index: int):
    return page.locator(f'[data-field="{port_id}"] [data-array-row="{index}"]')


def _control(page: Page, port_id: str, hook: str):
    return page.locator(f'[data-field="{port_id}"] [{hook}]').first


def test_a_string_row_edit_reaches_the_model(page: Page, harness):
    _open(page, harness)
    _row(page, "strings", 1).locator("input").first.fill("Deux")
    expect(_echo(page, "strings")).to_have_text("['One', 'Deux', 'Three']")


def test_add_and_remove_in_the_browser(page: Page, harness):
    _open(page, harness)
    _control(page, "ints", "data-array-add").click()
    expect(_echo(page, "ints")).to_have_text("[1, 2, 3, 0]")
    _control(page, "ints", 'data-array-remove="0"').click()
    expect(_echo(page, "ints")).to_have_text("[2, 3, 0]")


def test_a_grip_drag_reorders_the_list(page: Page, harness):
    _open(page, harness)
    _control(page, "strings", 'data-array-grip="0"').drag_to(_row(page, "strings", 2))
    expect(_echo(page, "strings")).to_have_text("['Two', 'Three', 'One']")
    # The rows are redrawn from the model, so they read in the new order.
    inputs = page.locator('[data-field="strings"] [data-array-row] input')
    expect(inputs).to_have_count(3)
    assert [inputs.nth(i).input_value() for i in range(3)] == ["Two", "Three", "One"]


def test_a_float_row_takes_typed_input(page: Page, harness):
    _open(page, harness)
    _row(page, "floats", 0).locator(".number-drag__center").click()
    page.keyboard.press("ControlOrMeta+A")
    page.keyboard.type("2.5")
    page.keyboard.press("Enter")
    expect(_echo(page, "floats")).to_have_text("[2.5, 1.5]")


def test_the_settings_panel_draws_list_rows(page: Page, harness):
    node = "haybale_testing.nodes.testbed.settings_node.SettingsNode"
    goto_ready(page, f"{harness}/node?class={node}&bag=example")
    page.wait_for_selector("[data-field]")
    expect(page.locator('[data-field="example_string_list"] [data-array-row]')).to_have_count(3)


# ---------------------------------------------------------------------------
# ArrayWidget on a node card, on a zoomed canvas
# ---------------------------------------------------------------------------


def test_a_grip_drag_on_a_zoomed_card_reorders_without_moving_the_node(page: Page, harness):
    goto_ready(page, f"{harness}/graph-list-widget")
    page.wait_for_selector(".ui-node-slot")
    wait_for_canvas_settled(page)
    node_id = page.locator('[data-testid="node-id"]').get_attribute("data-node")
    card = page.locator(f'[id="{node_id}"]')
    page.evaluate(
        """(nid) => {
            const r = document.querySelector(`[data-node-id="${nid}"]`).getBoundingClientRect();
            document.querySelector('.zoom-pan-container')._zoomPanControls.setZoom(0.75, r.left, r.top);
        }""",
        node_id,
    )
    wait_for_canvas_settled(page)
    scale = page.evaluate(
        "() => new DOMMatrix(getComputedStyle(document.querySelector('.zoom-pan-content')).transform).a"
    )
    assert abs(scale - 0.75) < 0.01, scale
    # Card widgets show only on a selected node.
    box = card.bounding_box()
    assert box is not None
    page.mouse.click(box["x"] + 30, box["y"] + 10)
    grip = card.locator('[data-array-grip="0"]')
    expect(grip).to_be_visible()
    before = card.bounding_box()

    grip.drag_to(card.locator('[data-array-row="2"]'))

    expect(page.locator('[data-testid="echo-list"]')).to_have_text("['Two', 'Three', 'One']")
    after = card.bounding_box()
    assert before is not None
    assert after is not None
    assert (round(after["x"]), round(after["y"])) == (round(before["x"]), round(before["y"]))
