"""A card that changes size by itself must repaint the edges of the pins it moved — and only then.

Content can grow a card with no server message at all: an image that loads, a
viewer that enlarges, a widget that appears. The slot's ResizeObserver is the
only thing that sees it, so it queues the node's edges for a repaint
(``_queueEdgesIfResized``).

A refresh per style change was removed once already because the hover
magnifier's transforms set it off on every crossing; the second test pins that
hovering queues no repaint.

Reuses the ``/graph-detail`` fixture: ``int_inlet`` is the only wired pin.
"""

import pytest
from playwright.sync_api import Page

from tests.ui.harness.nav import goto_ready, wait_for_canvas_settled
from tests.ui.harness.test_graph_node_detail import _edge_end, _pin

_PATH = "/graph-detail"

pytestmark = pytest.mark.ui


def _open(page: Page, harness) -> None:
    goto_ready(page, f"{harness}{_PATH}")
    page.wait_for_selector("[data-node-id]")
    page.wait_for_selector("path[data-edge-id]")
    wait_for_canvas_settled(page)
    page.evaluate("() => { window.__hwMeasureStats = { observed: 0, queued: 0, edgeRelayouts: 0 }; }")


def _grow_above(page: Page, pin_id: str, height: int) -> None:
    """Insert a spacer above the pin's row, in the browser only: no server message."""
    page.evaluate(
        """([pinId, height]) => {
            const pin = [...document.querySelectorAll('.connection-pin')]
                .find(e => e.dataset.pinId === pinId && e.dataset.pinDir === 'inlet');
            let row = pin;
            while (row.parentElement && !row.parentElement.matches('.ui-node-slot, [data-node-id]')
                   && row.parentElement.children.length < 2) row = row.parentElement;
            const spacer = document.createElement('div');
            spacer.style.height = height + 'px';
            spacer.dataset.testSpacer = '1';
            row.parentElement.insertBefore(spacer, row);
        }""",
        [pin_id, height],
    )
    page.wait_for_timeout(300)  # ResizeObserver, then one rAF


def _make_manual(page: Page, pin_id: str) -> None:
    """Size the pin's card by hand, in the browser: a manual card reports no size to the server.

    An auto-sized card's measurement round-trips through the server and the reply
    repaints its edges anyway; a manual one has nothing but the ResizeObserver.
    """
    page.evaluate(
        """(pinId) => {
            const pin = [...document.querySelectorAll('.connection-pin')]
                .find(e => e.dataset.pinId === pinId && e.dataset.pinDir === 'inlet');
            const node = pin.closest('[data-node-id]');
            const slot = pin.closest('.ui-node-slot') || node.querySelector('.ui-node-slot');
            if (!slot) throw new Error('no .ui-node-slot around the pin');
            slot.setAttribute('data-node-props-size-adapt', 'manual');
        }""",
        pin_id,
    )
    page.wait_for_timeout(300)
    page.evaluate("() => { window.__hwMeasureStats.edgeRelayouts = 0; }")


def test_edge_end_follows_a_pin_that_content_growth_moved(page: Page, harness) -> None:
    _open(page, harness)
    _make_manual(page, "int_inlet")
    before = _pin(page, "int_inlet")

    _grow_above(page, "int_inlet", 120)

    after = _pin(page, "int_inlet")
    assert after["y"] - before["y"] > 60, (
        f"the spacer should push the pin down (y {before['y']:.1f} -> {after['y']:.1f}); "
        "without that this test proves nothing"
    )
    end = _edge_end(page)
    assert abs(end["y"] - after["ey"]) < 12, (
        f"edge end {end['y']:.1f} should track the pin's new edge {after['ey']:.1f} "
        f"(it was at {before['ey']:.1f}) — the card grew but its edges were not repainted"
    )
    assert page.evaluate("() => window.__hwMeasureStats.edgeRelayouts") >= 1


def test_hovering_the_cards_queues_no_edge_repaint(page: Page, harness) -> None:
    _open(page, harness)
    boxes = page.evaluate(
        """() => [...document.querySelectorAll('[data-node-id]')].map(n => {
            const r = n.getBoundingClientRect();
            return { x: r.left + r.width / 2, y: r.top + r.height / 2 };
        })"""
    )
    assert boxes, "the fixture has cards to hover"

    for _ in range(5):
        for box in boxes:
            page.mouse.move(box["x"], box["y"], steps=4)
            page.wait_for_timeout(120)
        page.mouse.move(5, 5, steps=4)
        page.wait_for_timeout(120)

    assert page.evaluate("() => window.__hwMeasureStats.edgeRelayouts") == 0
