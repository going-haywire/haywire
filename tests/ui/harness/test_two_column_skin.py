"""A multi-column skin's columns follow the flow direction.

Flipping only the pin sides under R2L strands each pin on the far side of its
own label: an inlet's pin protrudes from the card's right edge while its label
sits in the left column, and edges arriving from the right cross back over the
whole card to reach the column their labels live in.

The rule this pins down — "the inlet column is whichever side inlets' pins
protrude from" — is stated in docs/components/skins/skin-canon.md and applies
to any multi-column skin, not just SplitNodeSkin.
"""

import pytest
from playwright.sync_api import Page

from tests.ui.harness.nav import goto_ready

_URL = "http://localhost:8090/graph-two-column"

pytestmark = pytest.mark.ui


def _open(page: Page) -> None:
    goto_ready(page, _URL)
    page.wait_for_selector("[data-node-id]")
    page.wait_for_selector(".connection-pin")
    page.wait_for_timeout(1000)


def _switch(page: Page, testid: str) -> None:
    page.click(f'[data-testid="{testid}"]')
    page.wait_for_timeout(900)


def _column_headings_in_order(page: Page) -> list[str]:
    """The 'Inputs'/'Outputs' captions, left to right on screen."""
    return page.evaluate(
        """() => [...document.querySelectorAll('.split-node-card .font-bold')]
            .filter(e => ['Inputs', 'Outputs'].includes(e.textContent.trim()))
            .map(e => ({ t: e.textContent.trim(), x: e.getBoundingClientRect().left }))
            .sort((a, b) => a.x - b.x)
            .map(e => e.t)"""
    )


def _pin_side(page: Page, pin_dir: str) -> str:
    """Which card edge a pin of this direction offsets toward."""
    return page.evaluate(
        """(dir) => {
            const pin = [...document.querySelectorAll('.split-node-card .connection-pin')]
                .find(e => e.dataset.pinDir === dir);
            if (!pin) throw new Error('no pin with dir ' + dir);
            const s = getComputedStyle(pin);
            return ['left', 'right'].find(k => s[k] !== 'auto' && parseFloat(s[k]) < 0);
        }""",
        pin_dir,
    )


def _label_centre_x(page: Page, heading: str) -> float:
    return page.evaluate(
        """(h) => {
            const el = [...document.querySelectorAll('.split-node-card .font-bold')]
                .find(e => e.textContent.trim() === h);
            const r = el.getBoundingClientRect();
            return r.left + r.width / 2;
        }""",
        heading,
    )


def _card_centre_x(page: Page) -> float:
    return page.evaluate(
        """() => {
            const r = document.querySelector('.split-node-card').getBoundingClientRect();
            return r.left + r.width / 2;
        }"""
    )


def test_the_fixture_really_uses_the_two_column_skin(page: Page, harness) -> None:
    """Guard the premise — otherwise this silently tests the default skin."""
    _open(page)
    assert page.evaluate("() => !!document.querySelector('.split-node-card')")
    assert _column_headings_in_order(page) == ["Inputs", "Outputs"]


def test_l2r_puts_inputs_on_the_left(page: Page, harness) -> None:
    _open(page)
    _switch(page, "set-l2r")
    assert _column_headings_in_order(page) == ["Inputs", "Outputs"]
    assert _pin_side(page, "inlet") == "left"


def test_r2l_swaps_the_columns_with_the_pins(page: Page, harness) -> None:
    _open(page)
    _switch(page, "set-r2l")
    assert _pin_side(page, "inlet") == "right", "inlet pins should protrude right under r2l"
    assert _column_headings_in_order(page) == ["Outputs", "Inputs"], (
        "columns must follow the pins — leaving them in place strands each pin "
        "on the far side of its own label"
    )


@pytest.mark.parametrize(
    ("testid", "heading", "pin_dir"),
    [
        ("set-l2r", "Inputs", "inlet"),
        ("set-l2r", "Outputs", "outlet"),
        ("set-r2l", "Inputs", "inlet"),
        ("set-r2l", "Outputs", "outlet"),
    ],
)
def test_each_column_sits_on_the_same_side_as_its_own_pins(
    page: Page, harness, testid, heading, pin_dir
) -> None:
    """The property that actually matters, stated directly."""
    _open(page)
    _switch(page, testid)

    side = _pin_side(page, pin_dir)
    label_x = _label_centre_x(page, heading)
    card_x = _card_centre_x(page)

    if side == "left":
        assert label_x < card_x, f"{testid}: {heading} column should be left of card centre"
    else:
        assert label_x > card_x, f"{testid}: {heading} column should be right of card centre"
