"""Regression test for edge reconnection (canvas.vue).

Reconnecting an edge triggers a redraw of the anchor node, which rebuilds its
pin DOM. The canvas captured the *old* pin element in ``edgeDrag.anchorPin``;
once that element is detached by the rebuild, ``getBoundingClientRect()`` no
longer tracks the live pin and the anchor (non-dragged) end of the preview
drifts away from the outlet. ``_resolveAnchorPin()`` re-resolves the pin by id
so the anchor end stays glued to its pin.

This drives the full reconnect pipeline in a real browser against the
``/graph-reconnect`` harness route (two nodes + one control edge). The node
rebuild is simulated deterministically by replacing the anchor pin element with
a same-id clone mid-drag (``_replace_anchor_pin``) — that is exactly what a
NiceGUI node redraw does to the element the canvas is holding. Without the fix,
the preview anchor drifts a node's width away from the outlet; with it, the
re-resolve snaps it back.
"""

import pytest
from playwright.sync_api import Page

from tests.ui.harness.nav import goto_ready

_URL = "http://localhost:8090/graph-reconnect"

pytestmark = pytest.mark.ui

# Live-edge endpoint accessor: the first 'M x y' of the visible (non-hitarea)
# edge path is the outlet pin in canvas content-space — the anchor the preview
# must stay glued to after reconnect.
_LIVE_EDGE_START_JS = """() => {
    const path = document.querySelector(
        "#connection-svg path[data-edge-id]:not([id$='_hitarea'])");
    if (!path) return null;
    const m = path.getAttribute('d').match(/M\\s+([-\\d.]+)\\s+([-\\d.]+)/);
    return { x: parseFloat(m[1]), y: parseFloat(m[2]) };
}"""

# Start point of the dashed preview path (the in-progress reconnect).
_PREVIEW_START_JS = """() => {
    const dashed = [...document.querySelectorAll('#connection-svg path')]
        .find(p => p.getAttribute('stroke-dasharray'));
    if (!dashed) return null;
    const m = dashed.getAttribute('d').match(/M\\s+([-\\d.]+)\\s+([-\\d.]+)/);
    return { x: parseFloat(m[1]), y: parseFloat(m[2]) };
}"""


def _path_point(page: Page, frac: float) -> dict:
    """Screen coords of a point ``frac`` along the visible edge path.

    Sampling the path geometry (not its bounding box) keeps the right-click on
    the edge body rather than on a pin — a pin click opens the port info popup
    instead of the edge action menu.
    """
    return page.evaluate(
        """(frac) => {
            const path = document.querySelector(
                "#connection-svg path[data-edge-id]:not([id$='_hitarea'])");
            const pt = path.getPointAtLength(path.getTotalLength() * frac);
            const m = path.getScreenCTM();
            return { x: m.a*pt.x + m.c*pt.y + m.e, y: m.b*pt.x + m.d*pt.y + m.f };
        }""",
        frac,
    )


def _replace_anchor_pin(page: Page, node_substr: str) -> dict:
    """Replace the anchor node's pin element with a same-id clone.

    Detaches the element the canvas captured in ``edgeDrag.anchorPin``, mirroring
    what a NiceGUI node redraw does mid-reconnect. Returns the connectivity of
    the old and new elements so the test can assert the detach actually happened.
    """
    return page.evaluate(
        """(sub) => {
            const node = [...document.querySelectorAll('[data-node-id]')]
                .find(n => n.dataset.nodeId.includes(sub));
            const pin = document.getElementById('exec@' + node.dataset.nodeId);
            const clone = pin.cloneNode(true);
            pin.parentNode.replaceChild(clone, pin);
            return { oldConnected: pin.isConnected, newConnected: clone.isConnected };
        }""",
        node_substr,
    )


def _click_menu_item(page: Page, label: str) -> None:
    """Click a context-menu item by its (case-insensitive) text label."""
    page.evaluate(
        """(label) => {
            const el = [...document.querySelectorAll('.hw-popup-card *')]
                .find(x => (x.textContent || '').trim().toUpperCase() === label);
            if (!el) throw new Error('menu item not found: ' + label);
            const r = el.getBoundingClientRect();
            window.__menuItem = { x: r.left + r.width/2, y: r.top + r.height/2 };
        }""",
        label.upper(),
    )
    pos = page.evaluate("() => window.__menuItem")
    page.mouse.click(pos["x"], pos["y"])


def test_reconnect_anchor_stays_on_outlet_pin(page: Page, harness):
    """Reconnecting from the inlet side keeps the preview anchored to the outlet.

    Right-click the edge nearer the inlet → Reconnect → the inlet end follows
    the mouse while the outlet end must stay at the outlet pin. Without the fix,
    the stale held pin makes the anchor end drift off the outlet.
    """
    goto_ready(page, _URL)
    page.wait_for_selector("#connection-svg path[data-edge-id]")
    page.wait_for_timeout(1500)  # let the graph sync + center

    outlet = page.evaluate(_LIVE_EDGE_START_JS)
    assert outlet is not None, "live edge not rendered"

    # Right-click past the midpoint (nearer the inlet) so the outlet is the anchor.
    click = _path_point(page, 0.62)
    page.mouse.click(click["x"], click["y"], button="right")
    page.wait_for_selector(".hw-popup-card")
    _click_menu_item(page, "Reconnect")
    page.wait_for_timeout(200)

    # Simulate the node redraw that detaches the held pin element mid-drag.
    detach = _replace_anchor_pin(page, "BeginPlay")
    assert detach["oldConnected"] is False and detach["newConnected"] is True, (
        f"pin-replace did not detach as expected: {detach}"
    )

    # Move the pointer so _handleEdgeDragMove recomputes the anchor end against
    # the now-detached held element.
    page.mouse.move(click["x"] + 150, click["y"] - 120)
    page.mouse.move(click["x"] + 160, click["y"] - 130)
    page.wait_for_timeout(200)

    preview = page.evaluate(_PREVIEW_START_JS)
    assert preview is not None, "no preview path after reconnect"

    # Anchor end must stay on the outlet pin. Without _resolveAnchorPin the held
    # element is stale and the start drifts a node's width away (~350px here).
    assert abs(preview["x"] - outlet["x"]) < 5, (
        f"anchor X drifted from outlet (stale-pin bug): preview={preview} outlet={outlet}"
    )
    assert abs(preview["y"] - outlet["y"]) < 5, (
        f"anchor Y drifted from outlet (stale-pin bug): preview={preview} outlet={outlet}"
    )
