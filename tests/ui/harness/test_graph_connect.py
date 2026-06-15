"""Connection-interaction tests for the graph canvas (canvas.vue).

The graph/validation engine already covers *which* connections are legal
(tests/core/test_graph/test_edges.py — direction, flow type, duplicates,
self-loops, dynamic-port edge survival). These tests cover the layer that lives
only in canvas.vue and only exists in a browser: the user-facing entry paths
that turn pin clicks into an ``edgeCreated``.

Connection model (current canvas.vue): purely *click-click*. A mousedown on a
pin enters active-connection mode; the next mousedown commits. There is no
press-drag-release path (``handleMouseUp`` does not commit). Covered here:

- click-click: click outlet, click inlet → edge
- reverse: click inlet, click outlet → same correctly-oriented edge
- proximity-snap: click outlet, click empty canvas near a compatible inlet → edge
- rejection: clicking two outlets makes no edge (canvas honors validity)
"""

import re

import pytest
from playwright.sync_api import Page

_URL = "http://localhost:8090/graph-connect"

pytestmark = pytest.mark.ui

# Edge between the source's exec outlet and the sink's exec inlet, oriented
# outlet→inlet regardless of which end the user clicked first.
_EXPECTED_EDGE_RE = r"^edge::exec@TestBeginPlayNode_.+>>exec@TestPrintNode_.+$"


def _pin_center(page: Page, id_fragment: str) -> dict:
    """Screen-space center of the first connection pin whose id contains the fragment."""
    return page.evaluate(
        """(frag) => {
            const pin = [...document.querySelectorAll('.connection-pin')]
                .find(e => e.id.includes(frag));
            if (!pin) throw new Error('pin not found: ' + frag);
            const r = pin.getBoundingClientRect();
            return { x: r.left + r.width/2, y: r.top + r.height/2 };
        }""",
        id_fragment,
    )


def _edge_ids(page: Page) -> list[str]:
    """Distinct data-edge-id values currently in the SVG (path + hitarea share an id)."""
    return page.evaluate(
        "() => [...new Set([...document.querySelectorAll('path[data-edge-id]')]"
        ".map(e => e.getAttribute('data-edge-id')))]"
    )


def _open(page: Page) -> None:
    page.goto(_URL)
    page.wait_for_selector("[data-node-id]")
    page.wait_for_selector(".connection-pin")
    page.wait_for_timeout(1200)  # let the graph sync + center
    assert _edge_ids(page) == [], "fixture should start with no edges"


def _click_pin(page: Page, id_fragment: str) -> dict:
    pos = _pin_center(page, id_fragment)
    page.mouse.move(pos["x"], pos["y"])  # register hover before the commit click
    page.mouse.click(pos["x"], pos["y"])
    page.wait_for_timeout(250)
    return pos


def test_click_click_outlet_then_inlet_creates_edge(page: Page, harness):
    """Click the outlet, then the inlet → a single correctly-oriented edge."""
    _open(page)
    _click_pin(page, "exec@TestBeginPlay")  # outlet
    _click_pin(page, "exec@TestPrint")  # inlet
    page.wait_for_timeout(400)

    edges = _edge_ids(page)
    assert len(edges) == 1, f"expected exactly one edge, got {edges}"
    assert re.match(_EXPECTED_EDGE_RE, edges[0]), f"edge mis-oriented: {edges[0]}"


def test_reverse_inlet_then_outlet_creates_oriented_edge(page: Page, harness):
    """Click the inlet first, then the outlet → same outlet→inlet edge.

    Exercises direction normalization in _commitConnection (the source is always
    the outlet, regardless of click order).
    """
    _open(page)
    _click_pin(page, "exec@TestPrint")  # inlet first
    _click_pin(page, "exec@TestBeginPlay")  # outlet second
    page.wait_for_timeout(400)

    edges = _edge_ids(page)
    assert len(edges) == 1, f"expected exactly one edge, got {edges}"
    assert re.match(_EXPECTED_EDGE_RE, edges[0]), f"edge mis-oriented: {edges[0]}"


def test_proximity_snap_commits_to_nearest_compatible_pin(page: Page, harness):
    """Click the outlet, then click empty canvas near the inlet → snaps and connects."""
    _open(page)
    _click_pin(page, "exec@TestBeginPlay")  # start the active connection

    inlet = _pin_center(page, "exec@TestPrint")
    near_x, near_y = inlet["x"] - 25, inlet["y"] + 25  # empty canvas, within suggestion range
    page.mouse.move(near_x, near_y)
    page.wait_for_timeout(200)
    page.mouse.click(near_x, near_y)
    page.wait_for_timeout(400)

    edges = _edge_ids(page)
    assert len(edges) == 1, f"proximity snap should connect, got {edges}"
    assert re.match(_EXPECTED_EDGE_RE, edges[0]), f"edge mis-oriented: {edges[0]}"


def test_outlet_to_outlet_makes_no_edge(page: Page, harness):
    """Clicking two outlets is invalid → the canvas creates no edge.

    The engine enforces direction rules; this is a thin UI-level guard that the
    canvas honors them rather than emitting a bogus edgeCreated.
    """
    _open(page)
    _click_pin(page, "exec@TestBeginPlay")  # outlet
    _click_pin(page, "done@TestPrint")  # another outlet (EXEC.as_outlet "done")
    page.wait_for_timeout(400)

    assert _edge_ids(page) == [], "outlet→outlet must not create an edge"
