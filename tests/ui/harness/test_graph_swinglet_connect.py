"""Swinglet drags on the graph canvas (canvas.vue).

A swinglet pin (`data-pin-dir="swinglet"`) may be either end of an edge. These
cover what only the canvas decides: which end of a drop becomes the outlet end,
that a drop onto two pins already linked the other way is ignored, that a
reconnect keeps the anchor's role, and where a suggestion path meets a
swinglet. The graph's own rules for swinglet edges are covered in tests/core.

Connections are click-click, as in test_graph_connect.py: a click on a pin
starts the drag, the next click commits it.
"""

import json

import pytest
from playwright.sync_api import Page, WebSocket, expect

from tests.ui.harness.nav import goto_ready, wait_for_canvas_settled

_PATH = "/graph-swinglet"
_PROBES = ("v1", "v2", "v3", "p1", "p2", "add")

#: The context-menu popup, not the selection toolbar that a right-click selection also shows.
_MENU = ".hw-popup-card:not(:has(.hw-selection-toolbar))"

pytestmark = pytest.mark.ui


def _open(page: Page, harness) -> dict[str, str]:
    """Open the fixture and return each probe's node id by name (`v1`, ..., `add`)."""
    goto_ready(page, f"{harness}{_PATH}")
    page.wait_for_selector(".connection-pin")
    wait_for_canvas_settled(page)
    return {name: page.inner_text(f'[data-testid="probe-{name}"]') for name in _PROBES}


def _edge_id(source: str, outlet: str, sink: str, inlet: str) -> str:
    return f"{source}[{outlet}]->{sink}[{inlet}]"


def _pin_center(page: Page, node_id: str, pin_id: str) -> dict:
    return page.evaluate(
        """([node, pin]) => {
            const el = document.getElementById(`${pin}@${node}`);
            if (!el) throw new Error(`pin not found: ${pin}@${node}`);
            const r = el.getBoundingClientRect();
            return { x: r.left + r.width / 2, y: r.top + r.height / 2 };
        }""",
        [node_id, pin_id],
    )


def _click_pin(page: Page, node_id: str, pin_id: str) -> None:
    pos = _pin_center(page, node_id, pin_id)
    page.mouse.move(pos["x"], pos["y"])
    page.mouse.click(pos["x"], pos["y"])


def _drag(page: Page, start: tuple[str, str], end: tuple[str, str]) -> None:
    """Connect the pin `start` to the pin `end`, each a `(node_id, pin_id)`, in that order."""
    _click_pin(page, *start)
    page.wait_for_selector(".graph-canvas.edge-dragging")
    _click_pin(page, *end)
    page.wait_for_selector(".graph-canvas:not(.edge-dragging)")


def _expect_edges(page: Page, edge_ids: list[str]) -> None:
    """Wait until both the graph and the canvas hold exactly ``edge_ids``."""
    expect(page.get_by_test_id("server-edges")).to_have_text("|".join(sorted(edge_ids)))
    page.wait_for_function(
        """(want) => {
            const got = [...new Set([...document.querySelectorAll('#connection-svg path[data-edge-id]')]
                .map(e => e.getAttribute('data-edge-id')))].sort();
            return JSON.stringify(got) === JSON.stringify(want);
        }""",
        arg=sorted(edge_ids),
    )


def _edge_point_near(page: Page, node_id: str, pin_id: str) -> dict:
    """Screen coords of the point on the only edge nearest the pin, off the pin and every card.

    A right-click there opens the edge menu (a pin opens the pin menu, a card the
    selection menu) and counts as near that pin's end.
    """
    return page.evaluate(
        """([node, pin]) => {
            const path = document.querySelector("#connection-svg path[data-edge-id]:not([id$='_hitarea'])");
            const ctm = path.getScreenCTM();
            const r = document.getElementById(`${pin}@${node}`).getBoundingClientRect();
            const centre = { x: r.left + r.width / 2, y: r.top + r.height / 2 };
            const total = path.getTotalLength();
            let best = null;
            for (let i = 0; i <= 200; i++) {
                const q = path.getPointAtLength(total * i / 200);
                const p = { x: ctm.a * q.x + ctm.c * q.y + ctm.e, y: ctm.b * q.x + ctm.d * q.y + ctm.f };
                const d = Math.hypot(p.x - centre.x, p.y - centre.y);
                if (d < 20) continue;
                const hit = document.elementFromPoint(p.x, p.y);
                if (!hit || hit.closest('[data-node-id]')) continue;
                if (!best || d < best.d) best = { x: p.x, y: p.y, d };
            }
            if (!best) throw new Error('no point on the edge is clear of the cards');
            return best;
        }""",
        [node_id, pin_id],
    )


def _click_menu_item(page: Page, label: str) -> None:
    """Click a context-menu item by its (case-insensitive) text label."""
    pos = page.evaluate(
        """(label) => {
            const el = [...document.querySelectorAll('.hw-popup-card:not(:has(.hw-selection-toolbar)) *')]
                .find(x => (x.textContent || '').trim().toUpperCase() === label);
            if (!el) throw new Error('menu item not found: ' + label);
            const r = el.getBoundingClientRect();
            return { x: r.left + r.width / 2, y: r.top + r.height / 2 };
        }""",
        label.upper(),
    )
    page.mouse.click(pos["x"], pos["y"])


def test_a_drag_between_two_swinglets_follows_the_drag_order(page: Page, harness):
    ids = _open(page, harness)

    _drag(page, (ids["v1"], "note"), (ids["v2"], "note"))

    _expect_edges(page, [_edge_id(ids["v1"], "note", ids["v2"], "note")])


def test_a_drag_from_an_inlet_to_a_swinglet_makes_the_swinglet_the_outlet_end(page: Page, harness):
    ids = _open(page, harness)

    _drag(page, (ids["add"], "value_a"), (ids["p1"], "s"))

    _expect_edges(page, [_edge_id(ids["p1"], "s", ids["add"], "value_a")])


def test_a_reverse_drag_is_ignored(page: Page, harness):
    """A drop onto two pins already linked the other way sends no edge, so no notice comes back.

    Watched on the websocket: the canvas must send no `edgeCreated`, and the
    server no `notify`.
    """
    frames: list[str | bytes] = []

    def _record(frame: str | bytes) -> None:
        frames.append(frame)

    def _watch(ws: WebSocket) -> None:
        ws.on("framesent", _record)
        ws.on("framereceived", _record)

    page.on("websocket", _watch)
    ids = _open(page, harness)
    forward = _edge_id(ids["v1"], "note", ids["v2"], "note")
    _drag(page, (ids["v1"], "note"), (ids["v2"], "note"))
    _expect_edges(page, [forward])
    expect(page.get_by_text("Connection created")).to_be_visible()
    frames.clear()

    _drag(page, (ids["v2"], "note"), (ids["v1"], "note"))
    # A negative: nothing to wait for, so give a sent edge and its notice time to show up.
    page.wait_for_timeout(500)

    _expect_edges(page, [forward])
    text = [f for f in frames if isinstance(f, str)]
    assert not [f for f in text if "edgeCreated" in f], "the canvas sent the reverse edge"
    assert not [f for f in text if f.startswith('42["notify"')], "the drop drew a notice"


def test_reconnecting_the_outlet_end_of_a_swinglet_edge_keeps_its_direction(page: Page, harness):
    """Reconnect V1 -> V2 at V1 onto V3: V2 keeps the inlet end, so the edge is V3 -> V2."""
    ids = _open(page, harness)
    _drag(page, (ids["v1"], "note"), (ids["v2"], "note"))
    _expect_edges(page, [_edge_id(ids["v1"], "note", ids["v2"], "note")])

    click = _edge_point_near(page, ids["v1"], "note")
    page.mouse.click(click["x"], click["y"], button="right")
    page.wait_for_selector(_MENU)
    _click_menu_item(page, "Reconnect")
    page.wait_for_selector(".graph-canvas.edge-dragging")
    _click_pin(page, ids["v3"], "note")
    page.wait_for_selector(".graph-canvas:not(.edge-dragging)")

    _expect_edges(page, [_edge_id(ids["v3"], "note", ids["v2"], "note")])


def _canvas_menu_pending_dir(page: Page, harness, held: str) -> str:
    """Reconnect V1 -> V2 at the ``held`` end ('v1' is the outlet end), right-click the empty canvas.

    Returns the `pendingPinDir` the canvas sent with `contextMenuCanvas`.
    """
    sent: list[str] = []

    def _watch(ws: WebSocket) -> None:
        ws.on("framesent", lambda frame: sent.append(frame) if isinstance(frame, str) else None)

    page.on("websocket", _watch)
    ids = _open(page, harness)
    _drag(page, (ids["v1"], "note"), (ids["v2"], "note"))
    _expect_edges(page, [_edge_id(ids["v1"], "note", ids["v2"], "note")])

    # Right-clicking near an end makes the other end the anchor.
    click = _edge_point_near(page, ids[held], "note")
    page.mouse.click(click["x"], click["y"], button="right")
    page.wait_for_selector(_MENU)
    _click_menu_item(page, "Reconnect")
    page.wait_for_selector(".graph-canvas.edge-dragging")
    sent.clear()

    empty = page.evaluate(
        """() => {
            const canvas = document.querySelector('.graph-canvas');
            for (let y = innerHeight - 20; y > 0; y -= 20) {
                for (let x = innerWidth - 20; x > 0; x -= 20) {
                    const hit = document.elementFromPoint(x, y);
                    const empty = hit && canvas.contains(hit) && !hit.closest('[data-node-id]');
                    if (empty && hit.tagName !== 'path')
                        return { x, y };
                }
            }
            throw new Error('no empty canvas point');
        }"""
    )
    page.mouse.move(empty["x"], empty["y"])
    page.mouse.click(empty["x"], empty["y"], button="right")
    page.wait_for_timeout(500)  # a sent frame has no signal to await
    events = [json.loads(json.loads(f[2:])[1]["args"][0]) for f in sent if "contextMenuCanvas" in f]
    assert events, "no contextMenuCanvas frame was sent"
    return events[-1]["data"]["pendingPinDir"]


@pytest.mark.parametrize(("held", "role"), [("v1", "inlet"), ("v2", "outlet")])
def test_a_reconnect_paused_for_the_canvas_menu_sends_the_anchors_role(page: Page, harness, held, role):
    """The canvas menu carries the anchor's role, not its swinglet dir, so auto-wire keeps the direction."""
    assert _canvas_menu_pending_dir(page, harness, held) == role


def test_a_suggestion_path_meets_a_swinglet_from_its_own_side(page: Page, harness):
    """The suggestion's last control point lies along the target pin's own direction, outside its card."""
    ids = _open(page, harness)
    _click_pin(page, ids["v1"], "note")
    page.wait_for_selector(".graph-canvas.edge-dragging")

    target = _pin_center(page, ids["v2"], "note")
    page.mouse.move(target["x"] - 30, target["y"] + 30)
    page.wait_for_selector("#connection-svg path.connection-suggestion-nearest")

    # (endControl - end) . the pin's direction: positive when the path arrives from outside the card.
    along = page.evaluate(
        """([node, pin]) => {
            const d = document.querySelector('#connection-svg path.connection-suggestion-nearest')
                .getAttribute('d').match(/-?[\\d.]+(?:e-?\\d+)?/g).map(Number);
            const [c2x, c2y, ex, ey] = d.slice(4, 8);
            const el = document.getElementById(`${pin}@${node}`);
            return (c2x - ex) * parseFloat(el.dataset.pinDirX) + (c2y - ey) * parseFloat(el.dataset.pinDirY);
        }""",
        [ids["v2"], "note"],
    )
    assert along > 0, f"the suggestion meets the swinglet from inside its card ({along})"
