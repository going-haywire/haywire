"""NodeProperties' appearance fields, driven through a real browser.

Covers the half headless tests structurally cannot: the model is written by the
*browser*, through Quasar controls and the widget's own event wiring. A value
can render correctly and still never reach the model — which is exactly how the
``#ffffffff`` reset bug survived a green headless suite.

The page echoes ``value|set``/``unset`` from the bag itself (see the
``/node-appearance`` route), so every assertion here is about the model rather
than about what a control happens to display.

Node colour is ONE field (``color_override``): the border and radius live in the
theme, and a node's whole look can be swapped with ``node_theme``. See ADR-0030.
The FILL widget moved to haybale-example — its browser tests are in
``test_fill_widget.py``.
"""

import re

import pytest
from playwright.sync_api import Page, expect

from tests.ui.harness.nav import goto_ready

_URL = "http://localhost:8090/node-appearance"

pytestmark = pytest.mark.ui


def _echo(page: Page, field: str):
    return page.locator(f'[data-testid="echo-{field}"]')


def _row(page: Page):
    """The color_override field's row.

    Scoped by name, not positional: the appearance category also renders skin,
    layout_direction and node_theme, so `.first` lands on whichever happens to
    draw first — historically a select's own readonly combobox input.
    """
    return page.locator('[data-field="color_override"]')


def _color_input(page: Page):
    return _row(page).locator("input").first


def _open_picker(page: Page) -> None:
    """Open the picker and click its spectrum — the interaction that emits.

    Not the popup's hex field: Quasar commits that on neither Enter nor blur,
    so a test driving it asserts against a value the widget never saw.
    """
    _row(page).locator(".q-field__append").first.click()
    spectrum = page.locator(".q-color-picker__spectrum").first
    expect(spectrum).to_be_visible()
    spectrum.click(position={"x": 30, "y": 30})
    page.keyboard.press("Escape")


def test_colour_starts_unset(page: Page, harness):
    """A freshly rendered node inherits the theme — nothing is locally set.

    The regression this pins: the prop defaulted to None, the converter
    substituted the widget's own #ffffffff, and the browser echoed it back as a
    real edit, so merely opening a node styled it. Emptiness is the whole
    "inherit" mechanism now, so an accidental write is still the failure mode.
    """
    goto_ready(page, _URL)
    page.wait_for_selector("[data-field]")

    expect(_echo(page, "color_override")).to_contain_text("unset")
    expect(_echo(page, "color_override")).not_to_contain_text("#ffffffff")


def test_picking_a_colour_reaches_the_model(page: Page, harness):
    """A colour chosen in the picker must be stored, not just displayed.

    ColorInput wires its popup to a *server-side* ``set_value``, which emits no
    browser event — so the binding's ``update:modelValue`` listener never sees
    it. ColorWidget bridges that with an explicit ``on_value_change``; without
    it, every picked colour is silently dropped.
    """
    goto_ready(page, _URL)
    page.wait_for_selector("[data-field]")

    _open_picker(page)

    expect(_echo(page, "color_override")).to_contain_text("set")
    expect(_echo(page, "color_override")).not_to_contain_text("unset")


def test_a_picked_colour_carries_alpha(page: Page, harness):
    """Alpha rides inside the colour (#rrggbbaa) — no separate opacity field.

    The picker is pinned to ``format-model=hexa``, so what it emits is the
    8-digit form; a 6-digit value would mean the format never took.
    """
    goto_ready(page, _URL)
    page.wait_for_selector("[data-field]")

    _open_picker(page)

    # Wait for the value to land before reading it: the pick is a round trip
    # through the server, so a bare inner_text() races it and reads the
    # still-unset model. expect() retries; inner_text() does not.
    expect(_echo(page, "color_override")).to_contain_text("set")

    css = _echo(page, "color_override").inner_text().split("|")[0]
    assert re.fullmatch(r"#[0-9a-fA-F]{8}", css), f"expected an 8-digit hexa colour, got {css!r}"


def test_clearing_the_colour_returns_to_inheriting(page: Page, harness):
    """Emptiness IS the unset signal — there is no separate reset affordance,
    and no is_locally_set question anywhere in the chain."""
    goto_ready(page, _URL)
    page.wait_for_selector("[data-field]")

    field = _color_input(page)
    field.fill("#123456ff")
    field.press("Enter")
    expect(_echo(page, "color_override")).to_contain_text("set")

    field.fill("")
    field.press("Enter")
    expect(_echo(page, "color_override")).to_contain_text("unset")
