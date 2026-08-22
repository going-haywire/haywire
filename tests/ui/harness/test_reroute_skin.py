"""Browser tests for the reroute skin's pin placement under resize.

A reroute is a resizable node like any other, and ``RerouteSkin`` places its
inlet and outlet against opposite card edges. Both pins used to sit in one
centered flex row, which lands them on the borders only while the card is at
its intrinsic dot size — grow the card and the row stayed centered, leaving
both pins floating in the middle of the box.

Measuring in a browser is the only way to see it: the placement is pure CSS
(absolute positioning against the card's padding box), so the server-side DOM
says nothing about where a pin actually lands. Assertions compare each pin's
center to the card's own bounding box, before and after a manual resize.

Deliberately ONE test. Browser tests are the slowest tier, and the resize case
is the only one that discriminates: the old centered-flex-row layout also put
the pins on the borders at the intrinsic dot size, so a default-size assertion
passes against the bug and earns nothing for its runtime. This test checks the
edges before growing the card anyway, so that case stays covered.
"""

import pytest
from playwright.sync_api import Page

from tests.ui.harness.nav import goto_ready
from tests.ui.harness.probe import attr

_URL = "http://localhost:8090/graph-reroute"

# The pin is offset outward by card_padding + gutter//2, so its center sits ON
# the border line. Allow a couple of px for rounding through the zoom transform.
_TOL = 3.0

pytestmark = pytest.mark.ui


def _node_id(page: Page) -> str:
    return attr(page, "#reroute-node-id", "data-node")


def _geometry(page: Page, node_id: str) -> dict:
    """The reroute card's box plus each pin's center, all in screen px."""
    return page.evaluate(
        """(nid) => {
            const card = document.querySelector(`[data-node-id="${nid}"] .node-card`);
            if (!card) return null;
            const cr = card.getBoundingClientRect();
            const pins = {};
            card.querySelectorAll('.connection-pin').forEach((p) => {
                const r = p.getBoundingClientRect();
                pins[p.getAttribute('data-pin-dir')] = {
                    cx: r.left + r.width / 2,
                    cy: r.top + r.height / 2,
                };
            });
            return {
                card: { left: cr.left, right: cr.right, top: cr.top, bottom: cr.bottom,
                        width: cr.width, height: cr.height },
                pins,
            };
        }""",
        node_id,
    )


def _open(page: Page) -> None:
    goto_ready(page, _URL)
    page.wait_for_selector("[data-node-id]")
    page.wait_for_selector(".connection-pin")
    page.wait_for_timeout(800)  # let the graph sync + center


def _assert_pins_on_edges(geo: dict, where: str) -> None:
    """Inlet on the left border, outlet on the right, both vertically centered.

    The fixture graph is left-to-right (the default), so the inlet's edge is
    `left` and the outlet's is `right`.
    """
    card, pins = geo["card"], geo["pins"]
    assert set(pins) == {"inlet", "outlet"}, f"{where}: expected both pins, got {sorted(pins)}"

    assert abs(pins["inlet"]["cx"] - card["left"]) < _TOL, (
        f"{where}: inlet not on the left border — pin cx={pins['inlet']['cx']} card={card}"
    )
    assert abs(pins["outlet"]["cx"] - card["right"]) < _TOL, (
        f"{where}: outlet not on the right border — pin cx={pins['outlet']['cx']} card={card}"
    )

    mid_y = (card["top"] + card["bottom"]) / 2
    for name in ("inlet", "outlet"):
        assert abs(pins[name]["cy"] - mid_y) < _TOL, (
            f"{where}: {name} not centered on its border — cy={pins[name]['cy']} mid={mid_y}"
        )


def test_pins_follow_the_borders_when_resized(page: Page, harness):
    """Growing the reroute moves its pins out with the borders.

    The regression: an in-flow centered pin row stays put while the card grows,
    so both pins end up floating inside the box instead of on its edges. The
    pre-resize check makes the intrinsic dot size a precondition of the same
    test rather than a second browser launch.
    """
    _open(page)
    nid = _node_id(page)

    before = _geometry(page, nid)
    _assert_pins_on_edges(before, "default size")

    page.click('[data-testid="reroute-grow"]')
    page.wait_for_timeout(600)
    after = _geometry(page, nid)

    assert after["card"]["width"] > before["card"]["width"] + 40, (
        f"card did not grow: before={before['card']} after={after['card']}"
    )
    assert after["card"]["height"] > before["card"]["height"] + 30, (
        f"card did not grow vertically: before={before['card']} after={after['card']}"
    )

    _assert_pins_on_edges(after, "after resize")
