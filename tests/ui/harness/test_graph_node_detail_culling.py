"""A NodeDetail rank change made while the node is CULLED must still repaint
its edges once the node scrolls back into view.

Companion to test_graph_node_detail.py, whose fixture keeps the sink node on
screen throughout. This file's fixture (/graph-detail-culled) forces viewport
culling on and starts the sink node far outside the viewport, so its card is
fully unmounted (see cull.vue) at the moment the detail rank changes.

That is a distinct failure mode from the plain (non-culled) case:
canvas.vue's data-node-props-detail MutationObserver only sees a mutation on
an element that exists — a culled node has no card in the DOM at all, so
nothing tells the canvas its pins moved. `_updateEdge` itself also assumes a
culled node "cannot move" (true for drag/position, not for a rank change) and
keeps drawing the pre-change geometry for that end. Without a fix, the edge
stays frozen at its pre-cull position even after the node is panned back into
view, until an incidental trigger (a hover, a drag) repaints it.
"""

import pytest
from playwright.sync_api import Page

from tests.ui.harness.nav import goto_ready
from tests.ui.harness.test_graph_node_detail import _edge_end, _pin

_URL = "http://localhost:8090/graph-detail-culled"

pytestmark = pytest.mark.ui

# The fixture's sink node sits at content (3980, 3700); the harness viewport
# is 800x600 at zoom 1. The harness starts panned at (0, 0) — already outside
# the CULL_DROP_MARGIN (1.0x viewport) band around the sink — so once culling
# is armed, staying at (0, 0) culls it with no further pan needed. Panning to
# _PAN_TO_SINK instead centres the node in the 800x600 view.
_PAN_AWAY = (0.0, 0.0)
_PAN_TO_SINK = (-3980.0 + 400.0, -3700.0 + 300.0)


def _set_pan(page: Page, x: float, y: float) -> None:
    """Move the viewport via the same handle _pin()'s zoom read uses.

    Deterministic and gesture-free: `setPan` runs `_setPanDirect` synchronously
    and schedules `_applyCulling` for the next frame, so a short wait after
    this settles both the transform and the cull pass.
    """
    page.evaluate(
        """([x, y]) => {
            const zp = document.querySelector('.zoom-pan-container');
            zp._zoomPanControls.setPan(x, y);
        }""",
        [x, y],
    )
    page.wait_for_timeout(300)


def _is_culled(page: Page, node_id: str) -> bool:
    return page.evaluate(
        """(nodeId) => {
            const holder = document.getElementById(nodeId);
            const cull = holder && holder.querySelector(':scope > .hw-node-cull');
            return !!(cull && cull._hwCull && !cull._hwCull.isVisible());
        }""",
        node_id,
    )


def _sink_node_id(page: Page) -> str:
    """The EdgeLinkTestNode id — the only node with a `.connection-pin[data-pin-id="int_inlet"]`."""
    return page.evaluate(
        """() => {
            const pin = [...document.querySelectorAll('.connection-pin')]
                .find(e => e.dataset.pinId === 'int_inlet' && e.dataset.pinDir === 'inlet');
            if (!pin) throw new Error('int_inlet pin not found');
            return pin.closest('[data-node-id]').getAttribute('data-node-id');
        }"""
    )


def _switch(page: Page, testid: str) -> None:
    page.click(f'[data-testid="{testid}"]')
    page.wait_for_timeout(900)


def _open(page: Page) -> str:
    """Load the fixture, arm culling, and return the sink node's id.

    Ends with the viewport back at _PAN_AWAY, which is already far from the
    sink at (3980, 3700) — so the node is CULLED once this returns. The node
    id is captured before culling is armed, while the viewport is parked on
    the sink (guaranteeing its card is mounted): a query made after would
    race the very unmount this fixture exists to test.
    """
    goto_ready(page, _URL)
    page.wait_for_selector("[data-node-id]")
    page.wait_for_selector("path[data-edge-id]")
    page.wait_for_timeout(1200)  # let the graph sync + settle

    _set_pan(page, *_PAN_TO_SINK)
    node_id = _sink_node_id(page)

    # pan.vue only arms culling on the reactive OFF->ON transition (or a
    # completed gesture) — never merely because the prop started true, since
    # the graph may still be mid-load at first render. Flip it here, after
    # the graph has settled, the way a user would from the settings panel.
    page.click('[data-testid="enable-culling"]')
    page.wait_for_timeout(300)

    # Pan away — enabling culling while parked on the sink (still near) does
    # not cull it by itself; this is what actually drops it out of the DOM.
    _set_pan(page, *_PAN_AWAY)
    assert _is_culled(page, node_id), "test setup: sink should be culled once panned away with culling armed"
    return node_id


def test_edge_repaints_after_detail_change_while_culled(page: Page, harness) -> None:
    node_id = _open(page)

    # Bring the node on screen first to read its FULL-rank pin position.
    _set_pan(page, *_PAN_TO_SINK)
    assert not _is_culled(page, node_id), "premise: node must be visible to read its FULL-rank pin position"
    before = _pin(page, "int_inlet")

    # Cull it again, then flip detail while it has no card in the DOM at all.
    _set_pan(page, *_PAN_AWAY)
    assert _is_culled(page, node_id), "premise: node must be culled before the detail change"
    _switch(page, "set-pins")

    # Reveal it again — no hover, no drag, no other incidental trigger.
    _set_pan(page, *_PAN_TO_SINK)
    assert not _is_culled(page, node_id), "premise: node must be visible again to check its edge"

    after = _pin(page, "int_inlet")
    assert abs(after["y"] - before["y"]) > 8, (
        f"PINS should have moved the linked pin once revealed (y {before['y']:.1f} -> "
        f"{after['y']:.1f}); it did not, so the edge check below proves nothing"
    )

    end = _edge_end(page)
    assert abs(end["y"] - after["y"]) < 12, (
        f"edge end {end['y']:.1f} should track the revealed pin's new centre {after['y']:.1f} "
        f"(it was at {before['y']:.1f} before the rank change) — a stale edge means the "
        "detail change made while culled never reached the node once it un-culled"
    )
    assert abs(end["x"] - after["x"]) < 12


def test_edge_repaints_on_the_return_trip_while_culled(page: Page, harness) -> None:
    """Same as above, flipping back to FULL while culled."""
    node_id = _open(page)

    _set_pan(page, *_PAN_TO_SINK)
    assert not _is_culled(page, node_id), "premise: node must be visible to set up the PINS starting state"
    _switch(page, "set-pins")
    lifted = _pin(page, "int_inlet")

    _set_pan(page, *_PAN_AWAY)
    assert _is_culled(page, node_id), "premise: node must be culled before the detail change"
    _switch(page, "set-full")

    _set_pan(page, *_PAN_TO_SINK)
    assert not _is_culled(page, node_id), "premise: node must be visible again to check its edge"

    restored = _pin(page, "int_inlet")
    assert abs(restored["y"] - lifted["y"]) > 8, "returning to FULL must move the pin back down"

    end = _edge_end(page)
    assert abs(end["y"] - restored["y"]) < 12, (
        f"edge end {end['y']:.1f} should track the restored pin {restored['y']:.1f}"
    )
