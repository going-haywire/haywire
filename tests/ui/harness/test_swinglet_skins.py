"""A swinglet is drawn once per card, on the inlet side, whichever skin draws it.

The split and error skins used to draw a swinglet twice (it is both an inlet
and an outlet), and the stacked skin drew it not at all. Two pins sharing one
id also shadow each other in `getElementById`, which the edge layer relies on.
"""

import pytest
from playwright.sync_api import Page

from tests.ui.harness.nav import goto_ready, wait_for_canvas_settled

_PATH = "/graph-swinglet-skins"
_SKINS = ("default", "split", "stacked", "error")
# The two-column skins stamp their own card class; the others carry neither.
_SKIN_CARD = {"split": ".split-node-card", "error": ".error-node-card"}

pytestmark = pytest.mark.ui


def _open(page: Page, harness) -> None:
    goto_ready(page, f"{harness}{_PATH}")
    page.wait_for_selector(".connection-pin")
    wait_for_canvas_settled(page)


def _probe_ids(page: Page) -> dict[str, str]:
    """Node id of each probe, by name (`default`, `split`, ..., `glyphs`)."""
    return {n: page.inner_text(f'[data-testid="probe-{n}"]') for n in (*_SKINS, "glyphs")}


def _cards(page: Page) -> list[dict]:
    """Every card, left to right, with the swinglet pins `s` inside it."""
    return page.evaluate(
        """() => [...document.querySelectorAll('[data-node-id]')]
            .filter(e => !e.classList.contains('connection-pin') && e.querySelector('.connection-pin'))
            .map(card => {
                const r = card.getBoundingClientRect();
                const pins = [...card.querySelectorAll('.connection-pin[data-pin-id="s"]')].map(p => {
                    const b = p.getBoundingClientRect();
                    return {x: b.left + b.width / 2, dir: p.dataset.pinDir};
                });
                const skins = ['.split-node-card', '.error-node-card']
                    .filter(c => card.matches(c) || card.querySelector(c));
                return {id: card.dataset.nodeId, left: r.left, right: r.right, pins, skins};
            })
            .sort((a, b) => a.left - b.left)"""
    )


def test_every_skin_draws_the_swinglet_once_on_the_inlet_side(page: Page, harness) -> None:
    _open(page, harness)
    by_id = {card["id"]: card for card in _cards(page)}

    for name, node_id in _probe_ids(page).items():
        if name == "glyphs":
            continue
        card = by_id[node_id]
        expected = [_SKIN_CARD[name]] if name in _SKIN_CARD else []
        assert card["skins"] == expected, f"{name}: rendered with {card['skins']}, wanted {expected}"
        assert len(card["pins"]) == 1, f"{name}: expected one pin `s`, got {card['pins']}"
        pin = card["pins"][0]
        assert pin["dir"] == "swinglet", name
        middle = (card["left"] + card["right"]) / 2
        assert pin["x"] < middle, f"{name}: pin at {pin['x']} is not on the inlet (left) side of {card}"


def test_no_pin_id_appears_twice(page: Page, harness) -> None:
    _open(page, harness)
    ids = page.evaluate("() => [...document.querySelectorAll('.connection-pin')].map(e => e.id)")
    assert len(ids) == len(set(ids))


def test_a_card_with_several_swinglets_draws_each_once(page: Page, harness) -> None:
    _open(page, harness)
    glyph_id = _probe_ids(page)["glyphs"]
    # Ghost pins (`root_in`/`root_out`, edge-routing anchors) are on every card
    # and are not swinglet pins, so they are excluded.
    pin_ids = page.evaluate(
        """id => [...document.querySelectorAll(
                `[data-node-id="${id}"] .connection-pin:not([data-pin-ghost])`)]
            .map(p => p.dataset.pinId)""",
        glyph_id,
    )
    assert sorted(pin_ids) == ["flow", "hook", "s"]
