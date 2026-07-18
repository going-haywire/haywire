"""Ghost-fallback rendering test for dynamic ports (canvas.vue).

When a node removes a port that an edge is linked to, the edge must not vanish —
the canvas falls its endpoint back to the node's invisible ghost pin
(``root_out`` / ``root_in``) via _findPinInHierarchy, so the connection stays
visible and re-links when the real port returns. The graph engine already
covers the *data* side of this survival (tests/core/test_graph/test_edges.py);
this covers the canvas's *rendering* fallback, which lives only in the browser.

The /graph-dynamic route wires a DynamicPortTestNode's ``dynamic_outlet_0`` to an
EdgeLinkTestNode and exposes drop-port / restore-port buttons that change
``port_count`` (0 removes the dynamic outlets, 2 restores them).
"""

import pytest
from playwright.sync_api import Page

from tests.ui.harness.nav import goto_ready

_URL = "http://localhost:8090/graph-dynamic"

pytestmark = pytest.mark.ui


def _edge_start_screen(page: Page) -> dict:
    """Screen-space start point of the visible edge path (its outlet end)."""
    return page.evaluate(
        """() => {
            const path = document.querySelector(
                "#connection-svg path[data-edge-id]:not([id$='_hitarea'])");
            if (!path) return null;
            const pt = path.getPointAtLength(0);
            const m = path.getScreenCTM();
            return { x: m.a*pt.x + m.c*pt.y + m.e, y: m.b*pt.x + m.d*pt.y + m.f };
        }"""
    )


def _pin_screen(page: Page, id_prefix: str) -> dict | None:
    """Screen-space center of the first connection pin whose id starts with id_prefix."""
    return page.evaluate(
        """(prefix) => {
            const pin = [...document.querySelectorAll('.connection-pin')]
                .find(p => p.id.startsWith(prefix));
            if (!pin) return null;
            const r = pin.getBoundingClientRect();
            return { x: r.left + r.width/2, y: r.top + r.height/2 };
        }""",
        id_prefix,
    )


def _edge_count(page: Page) -> int:
    return page.evaluate(
        "() => new Set([...document.querySelectorAll('path[data-edge-id]')]"
        ".map(e => e.getAttribute('data-edge-id'))).size"
    )


def _has_pin(page: Page, id_prefix: str) -> bool:
    return _pin_screen(page, id_prefix) is not None


def _close(a: dict, b: dict, tol: float = 4.0) -> bool:
    return abs(a["x"] - b["x"]) < tol and abs(a["y"] - b["y"]) < tol


def test_edge_falls_back_to_ghost_pin_then_reattaches(page: Page, harness):
    """Dropping the linked dynamic outlet moves the edge to the ghost outlet;
    restoring the port moves it back onto the real pin."""
    goto_ready(page, _URL)
    page.wait_for_selector("#connection-svg path[data-edge-id]")
    page.wait_for_timeout(1500)

    # Initially the edge renders at the real dynamic outlet.
    assert _edge_count(page) == 1
    assert _has_pin(page, "dynamic_outlet_0")
    start = _edge_start_screen(page)
    dyn_pin = _pin_screen(page, "dynamic_outlet_0")
    assert _close(start, dyn_pin), f"edge should start at the dynamic pin: {start} vs {dyn_pin}"

    # Drop the port (port_count → 0): the real outlet disappears...
    page.click('[data-testid="drop-port"]')
    page.wait_for_timeout(1200)
    assert not _has_pin(page, "dynamic_outlet_0"), "dynamic outlet should be removed"
    # ...but the edge survives and now renders at the node's ghost outlet.
    assert _edge_count(page) == 1, "edge must survive port removal (ghost fallback)"
    ghost_pin = _pin_screen(page, "root_out@DynamicPort")
    assert ghost_pin is not None, "ghost outlet pin should exist"
    start_dropped = _edge_start_screen(page)
    assert _close(start_dropped, ghost_pin), (
        f"edge should fall back to the ghost outlet: {start_dropped} vs {ghost_pin}"
    )

    # Restore the port (port_count → 2): the real outlet returns and the edge
    # snaps back onto it.
    page.click('[data-testid="restore-port"]')
    page.wait_for_timeout(1200)
    assert _has_pin(page, "dynamic_outlet_0"), "dynamic outlet should be restored"
    assert _edge_count(page) == 1
    start_restored = _edge_start_screen(page)
    dyn_pin_again = _pin_screen(page, "dynamic_outlet_0")
    assert _close(start_restored, dyn_pin_again), (
        f"edge should reattach to the restored pin: {start_restored} vs {dyn_pin_again}"
    )
