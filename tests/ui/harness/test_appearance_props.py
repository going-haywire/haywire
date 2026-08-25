"""NodeProperties appearance fields, driven through a real browser.

These cover the half that headless tests structurally cannot: the model is
written by the *browser*, through Quasar controls and the widget's own event
wiring. A value can render correctly and still never reach the model — which
is exactly how the ``#ffffffff`` reset bug survived a green headless suite.

The page echoes ``value|set``/``unset`` from the bag itself (see the
``/node-appearance`` route), and a FILL echoes as the CSS it renders to, so
every assertion here is about the model rather than about what a control
happens to display.
"""

import re

import pytest
from playwright.sync_api import Page, expect

from tests.ui.harness.nav import goto_ready

_URL = "http://localhost:8090/node-appearance"

pytestmark = pytest.mark.ui


def _echo(page: Page, field: str):
    return page.locator(f'[data-testid="echo-{field}"]')


def _swatch(page: Page, index: int = 0):
    """Stop *index*'s colour button. The swatch IS the control — it shows the
    colour and opens the picker; there is no separate hex field."""
    return page.locator(f'[data-fill-stop-color="{index}"]').first


def _pick_color(page: Page, index: int = 0, *, x: int = 30, y: int = 30) -> str:
    """Pick a colour from the popup's spectrum and return what the model got.

    Not the popup's hex field: Quasar commits that on neither Enter nor blur
    (verified — the field takes the text and QColor's ``change`` never fires),
    so a test driving it would assert against a value the widget never saw.
    The spectrum is the interaction that actually emits.
    """
    _swatch(page, index).click()
    spectrum = page.locator(".q-color-picker__spectrum").first
    expect(spectrum).to_be_visible()
    spectrum.click(position={"x": x, "y": y})
    page.keyboard.press("Escape")
    return page.locator('[data-testid="echo-body_fill"]').inner_text()


def _set_kind(page: Page, label: str) -> None:
    page.locator("[data-fill-kind]").first.click()
    page.get_by_role("option", name=label).click()


def test_fields_start_unset(page: Page, harness):
    """A freshly rendered node inherits the skin — nothing is locally set.

    The regression this pins: the props defaulted to None, the converter
    substituted the widget's own #ffffffff, and the browser echoed it back as
    a real edit, so merely opening a node styled it.
    """
    goto_ready(page, _URL)
    page.wait_for_selector("[data-field]")

    for field in ("body_fill", "border_color", "border_thickness", "border_roundness"):
        expect(_echo(page, field)).to_contain_text("unset")
    expect(_echo(page, "body_fill")).not_to_contain_text("#ffffffff")


def test_picking_a_colour_reaches_the_model(page: Page, harness):
    """A colour chosen in the picker must be stored, not just displayed.

    The picker's ``on_pick`` rides the QColor's own ``change`` event, so unlike
    a ColorInput — whose popup calls a *server-side* ``set_value`` that emits no
    browser event — this path notifies without extra wiring.
    """
    goto_ready(page, _URL)
    page.wait_for_selector("[data-field]")

    _swatch(page).click()
    page.locator(".q-color-picker__spectrum").first.click(position={"x": 30, "y": 30})
    page.keyboard.press("Escape")

    expect(_echo(page, "body_fill")).to_contain_text("set")
    expect(_echo(page, "body_fill")).not_to_contain_text("unset")


def test_a_picked_colour_carries_alpha(page: Page, harness):
    """Alpha rides inside the colour (#rrggbbaa) — no separate opacity field.

    The picker is pinned to ``format-model=hexa``, so what it emits is the
    8-digit form; a 6-digit value would mean the format never took.
    """
    goto_ready(page, _URL)
    page.wait_for_selector("[data-field]")

    echo = _pick_color(page)

    css = echo.split("|")[0]
    assert re.fullmatch(r"#[0-9a-fA-F]{8}", css), f"expected an 8-digit hexa colour, got {css!r}"


def test_switching_to_linear_produces_a_gradient(page: Page, harness):
    """The capability FILL exists for: a per-node gradient, from the UI.

    Solid carries one stop; a gradient needs two, so the widget promotes the
    lone stop rather than opening on something that cannot render as a
    gradient.
    """
    goto_ready(page, _URL)
    page.wait_for_selector("[data-field]")

    _set_kind(page, "Linear")

    expect(_echo(page, "body_fill")).to_contain_text("linear-gradient")
    expect(_echo(page, "body_fill")).to_contain_text("set")


def test_switching_to_radial_produces_a_radial_gradient(page: Page, harness):
    goto_ready(page, _URL)
    page.wait_for_selector("[data-field]")

    _set_kind(page, "Radial")

    expect(_echo(page, "body_fill")).to_contain_text("radial-gradient")


def test_the_angle_row_belongs_to_linear_alone(page: Page, harness):
    """Angle is meaningless for solid and radial, so it is hidden — not
    redrawn, which would drop focus from the control that switched kind."""
    goto_ready(page, _URL)
    page.wait_for_selector("[data-field]")

    angle = page.locator("[data-fill-angle-row]")
    expect(angle).not_to_be_visible()

    _set_kind(page, "Linear")
    expect(angle).to_be_visible()

    _set_kind(page, "Radial")
    expect(angle).not_to_be_visible()


def test_a_stop_percentage_is_actually_readable(page: Page, harness):
    """The number must fit its box.

    A dense QInput lays the spinner and any suffix out ahead of the native
    input, and at this width they left ~17px for the digits — "100" rendered
    as "10". Asserting the *value* would have passed throughout; only the
    rendered width catches it.
    """
    goto_ready(page, _URL)
    page.wait_for_selector("[data-field]")
    _set_kind(page, "Linear")

    last = page.locator("[data-fill-stop-at]").last
    expect(last).to_have_value("100")
    box = last.bounding_box()
    assert box is not None
    assert box["width"] >= 34, f"stop-position input is {box['width']}px — '100' will be clipped"


def test_the_swatch_stays_slim_vertically(page: Page, harness):
    """Height is fixed even though width is not.

    A Quasar QBtn floors at min-height 42px unless overridden inline — its own
    rule beats a class — which would make every stop row taller than the fields
    beside it.
    """
    goto_ready(page, _URL)
    page.wait_for_selector("[data-field]")

    box = _swatch(page).bounding_box()
    assert box is not None
    assert box["height"] <= 30, f"swatch is {box['height']}px tall — Quasar's 42px floor is winning"


def test_the_swatch_fills_the_row(page: Page, harness):
    """The swatch absorbs the row's spare width.

    It is the only flexible element: the position box and the remove button are
    pinned (`shrink-0 grow-0`), so everything left over is colour. Without
    `min-width: 0` on the swatch a flex item's default `min-width: auto` would
    floor it at its content and push the row into overflow instead.
    """
    goto_ready(page, _URL)
    page.wait_for_selector("[data-field]")
    _set_kind(page, "Linear")

    row = page.locator('[data-fill-stop="0"]').bounding_box()
    swatch = _swatch(page).bounding_box()
    position = page.locator("[data-fill-stop-at]").first.bounding_box()
    assert row is not None
    assert swatch is not None
    assert position is not None

    assert swatch["width"] > position["width"], (
        f"swatch ({swatch['width']}px) should take more of the row than the "
        f"fixed position box ({position['width']}px)"
    )
    # And it must not spill past the row it lives in.
    assert swatch["x"] + swatch["width"] <= row["x"] + row["width"] + 1


def test_the_swatch_shrinks_with_a_narrow_panel(page: Page, harness):
    """`min-width: 0` is load-bearing — without it the row overflows."""
    goto_ready(page, _URL)
    page.wait_for_selector("[data-field]")
    _set_kind(page, "Linear")

    wide = _swatch(page).bounding_box()
    page.evaluate("() => { document.querySelector('[data-field=\"body_fill\"]').style.width = '160px'; }")
    page.wait_for_timeout(250)
    narrow = _swatch(page).bounding_box()

    assert wide is not None
    assert narrow is not None
    assert narrow["width"] < wide["width"], "swatch did not shrink with its panel"


def test_number_fields_carry_no_native_spinner(page: Page, harness):
    """The up/down arrows belong to the browser's `type=number` control, and
    Quasar's hide-spin-buttons never reaches them from NiceGUI — the props go
    onto the <input> as plain attributes. A text input has none to hide."""
    goto_ready(page, _URL)
    page.wait_for_selector("[data-field]")
    _set_kind(page, "Linear")

    assert page.locator("[data-fill-stop-at]").first.get_attribute("type") == "text"
    assert page.locator("[data-fill-angle]").first.get_attribute("type") == "text"


def test_the_angle_still_writes_through_as_a_number(page: Page, harness):
    """Text input, integer model — the handler parses and clamps."""
    goto_ready(page, _URL)
    page.wait_for_selector("[data-field]")
    _set_kind(page, "Linear")

    angle = page.locator("[data-fill-angle]").first
    angle.click()
    angle.fill("")
    page.keyboard.type("90")
    page.keyboard.press("Tab")

    expect(_echo(page, "body_fill")).to_contain_text("linear-gradient(90deg")


def test_a_stop_swatch_takes_the_colour_it_holds(page: Page, harness):
    """The swatch is tinted with its own stop's colour — it is the only place
    that colour is shown, now that the hex field is gone.

    ``ColorInput(preview=True)`` could not have served: it matches 3- and
    6-digit hex only, so every #rrggbbaa value falls through to transparent —
    blank for exactly the values this widget produces.
    """
    goto_ready(page, _URL)
    page.wait_for_selector("[data-field]")

    echo = _pick_color(page)
    picked = echo.split("|")[0]

    # Whatever the spectrum produced must be the colour painted on the swatch —
    # asserting a hardcoded colour would only pin the click coordinates.
    r, g, b = (int(picked[i : i + 2], 16) for i in (1, 3, 5))
    page.wait_for_function(
        """([sel, rgb]) => {
            const el = document.querySelector(sel);
            return el && getComputedStyle(el).backgroundImage.includes(rgb);
        }""",
        arg=['[data-fill-stop-color="0"]', f"rgb({r}, {g}, {b})"],
    )
