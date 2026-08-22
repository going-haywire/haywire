"""Error-skin DOM contracts.

The error skin is the fallback a user stares at while diagnosing a broken node,
and until now it had no DOM coverage at all. Two defects it shipped with:

1. Both port loops were unfiltered/half-filtered, so every outlet rendered
   TWICE. Pins carry `id=generate_pin_uuid(node_id, port.id)`, and the
   connection layer resolves them with getElementById — a duplicate does not
   merely look doubled, it shadows the real pin and edges attach to whichever
   comes first in document order.
2. The card's class list said `error-node-card` but never `node-card`. CSS
   class selectors match whole tokens, so none of the `.node-card` rules
   applied and a manual resize silently capped at max-w-sm (384px).
"""

import pytest
from playwright.sync_api import Page

from tests.ui.harness.nav import goto_ready

_URL = "http://localhost:8090/graph-error-skin"

pytestmark = pytest.mark.ui


def _open(page: Page) -> None:
    goto_ready(page, _URL)
    page.wait_for_selector("[data-node-id]")
    page.wait_for_selector(".connection-pin")
    page.wait_for_timeout(1000)


def _pin_ids(page: Page) -> list[str]:
    """Every rendered pin's DOM id, duplicates included."""
    return page.evaluate("() => [...document.querySelectorAll('.connection-pin')].map(e => e.id)")


def test_the_fixture_really_uses_the_error_skin(page: Page, harness) -> None:
    """Guard the premise — otherwise the rest silently tests the default skin."""
    _open(page)
    assert page.evaluate("() => !!document.querySelector('.error-node-card')")


def test_every_port_renders_exactly_one_pin(page: Page, harness) -> None:
    _open(page)
    ids = _pin_ids(page)

    duplicates = sorted({i for i in ids if ids.count(i) > 1})
    assert not duplicates, (
        f"port ids rendered more than once: {duplicates}. Two elements sharing "
        f"one id make getElementById return the wrong pin."
    )


def test_outlets_render_on_the_outlet_side(page: Page, harness) -> None:
    """The duplicate used to put a copy of every outlet on the inlet side."""
    _open(page)
    sides = page.evaluate(
        """() => [...document.querySelectorAll('.connection-pin')]
            .filter(e => e.dataset.pinDir === 'outlet')
            .map(e => {
                const s = getComputedStyle(e);
                return ['left', 'right'].find(k => s[k] !== 'auto' && parseFloat(s[k]) < 0);
            })"""
    )
    assert sides, "fixture node should expose at least one outlet"
    assert set(sides) == {"right"}, f"outlets must offset on the right edge, got {set(sides)}"


def test_card_carries_the_node_card_contract_class(page: Page, harness) -> None:
    _open(page)
    classes = page.evaluate("() => [...document.querySelector('.error-node-card').classList]")
    assert "node-card" in classes, (
        f"error card must carry the literal `node-card` token alongside `error-node-card` — got {classes}"
    )


def test_manual_resize_is_not_clamped(page: Page, harness) -> None:
    """The behaviour `node-card` actually buys: max-width released in manual mode."""
    _open(page)
    released = page.evaluate(
        """() => {
            const slot = document.querySelector('.ui-node-slot');
            const card = document.querySelector('.error-node-card');
            const prev = slot.getAttribute('data-size-adapt');
            slot.setAttribute('data-size-adapt', 'manual');
            const maxW = getComputedStyle(card).maxWidth;
            if (prev === null) slot.removeAttribute('data-size-adapt');
            else slot.setAttribute('data-size-adapt', prev);
            return maxW;
        }"""
    )
    assert released == "none", (
        f"in manual mode the card's max-width must be released, got {released!r} "
        f"— the card is capped and will stop growing mid-drag"
    )
