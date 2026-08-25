"""NodeProperties appearance fields, driven through a real browser.

These cover the half that headless tests structurally cannot: the model is
written by the *browser*, through Quasar's QColor and the binding's
``update:modelValue`` listener. A colour can render correctly and still never
reach the model — which is exactly how the ``#ffffffff`` reset bug survived a
green headless suite.

The page echoes ``value|set``/``unset`` from the bag itself (see the
``/node-appearance`` route), so every assertion here is about the model, never
about what the input happens to display.
"""

import pytest
from playwright.sync_api import Page, expect

from tests.ui.harness.nav import goto_ready

_URL = "http://localhost:8090/node-appearance"

pytestmark = pytest.mark.ui


def _echo(page: Page, field: str):
    return page.locator(f'[data-testid="echo-{field}"]')


def _open_picker(page: Page, field: str):
    """Open a colour field's QColor popup and return it."""
    page.locator(f'[data-field="{field}"] button').first.click()
    picker = page.locator(".q-color-picker").first
    expect(picker).to_be_visible()
    return picker


def test_fields_start_unset_and_not_white(page: Page, harness):
    """A freshly rendered node inherits the skin — nothing is locally set.

    The regression: the props defaulted to None, the converter substituted the
    widget's own #ffffffff, and the browser echoed it back as a real edit.
    """
    goto_ready(page, _URL)
    page.wait_for_selector("[data-field]")

    for field in ("body_color", "border_color", "border_thickness", "border_roundness"):
        expect(_echo(page, field)).to_contain_text("unset")
    expect(_echo(page, "body_color")).not_to_contain_text("#ffffffff")


def test_picking_a_colour_reaches_the_model(page: Page, harness):
    """The reported bug: a colour chosen in the picker was never stored."""
    goto_ready(page, _URL)
    page.wait_for_selector("[data-field]")

    _open_picker(page, "body_color")
    # Click into the saturation/value spectrum — a genuine pick, the same
    # interaction a user makes.
    page.locator(".q-color-picker__spectrum").first.click(position={"x": 30, "y": 30})
    page.keyboard.press("Escape")

    expect(_echo(page, "body_color")).to_contain_text("set")
    expect(_echo(page, "body_color")).not_to_contain_text("unset")


def test_typing_a_colour_keeps_focus_for_the_whole_value(page: Page, harness):
    """The second symptom: the field lost focus after a single character.

    Each keystroke wrote the model, the model change re-synced the view, and
    the re-render dropped the caret — so a colour could only be entered one
    character per click.
    """
    goto_ready(page, _URL)
    page.wait_for_selector("[data-field]")

    field = page.locator('[data-field="body_color"] input').first
    field.click()
    field.fill("")
    page.keyboard.type("#123456")

    expect(field).to_be_focused()
    expect(field).to_have_value("#123456")


def test_an_alpha_value_round_trips(page: Page, harness):
    """Alpha rides inside the value (#rrggbbaa) — it must survive the model."""
    goto_ready(page, _URL)
    page.wait_for_selector("[data-field]")

    field = page.locator('[data-field="body_color"] input').first
    field.click()
    field.fill("")
    page.keyboard.type("#11223344")
    page.keyboard.press("Tab")

    expect(_echo(page, "body_color")).to_contain_text("#11223344")
