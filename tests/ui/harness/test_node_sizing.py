"""Browser tests for the node-sizing feature (host-slot size + resize gadget).

Drives the full editor stack via the ``/graph-size`` harness route (one node on
a real GraphCanvasManager). Covers the browser-only behaviours:

- ``UINode._apply_size`` writes a manual axis to the ``.ui-node-slot`` host slot
  as a MINIMUM (``min-width``/``min-height``): the node draws at the user size,
  but content needing more space expands it — nothing is ever clipped. An auto
  axis carries no inline size.
- The single-node 8-handle resize gadget in ``canvas.vue`` appears for a
  single-node selection, and dragging the right grip sets the width minimum and
  emits ``userResizeEnd`` (committed by ``process_resize_end``).

Assertions read the DOM (slot bounding box / inline style) rather than server
props, so no extra props endpoint is needed — the applied slot geometry is the
observable outcome of the whole write-back path.
"""

import pytest
from playwright.sync_api import Page

from tests.ui.harness.nav import goto_ready
from tests.ui.harness.probe import attr, box as probe_box

_URL = "http://localhost:8090/graph-size"

pytestmark = pytest.mark.ui


def _node_id(page: Page) -> str:
    return attr(page, "#size-node-id", "data-node")


def _slot_box(page: Page, node_id: str) -> dict:
    """The node's .ui-node-slot host slot geometry.

    ``width``/``height`` are offsetWidth/offsetHeight — content-space LAYOUT px
    (zoom-independent), which is the space size props live in. ``sx``/``sy`` are
    the screen-space top-left (for mouse targeting through the zoom transform).
    """
    return page.evaluate(
        """(nid) => {
            const container = document.querySelector(`[data-node-id="${nid}"]`);
            const slot = container && container.querySelector('.ui-node-slot');
            if (!slot) return null;
            const r = slot.getBoundingClientRect();
            return { sx: r.left, sy: r.top, width: slot.offsetWidth, height: slot.offsetHeight };
        }""",
        node_id,
    )


def _slot_style(page: Page, node_id: str) -> str:
    return page.evaluate(
        """(nid) => {
            const container = document.querySelector(`[data-node-id="${nid}"]`);
            const slot = container && container.querySelector('.ui-node-slot');
            return slot ? slot.style.cssText : '';
        }""",
        node_id,
    )


def _card_width(page: Page, node_id: str) -> float | None:
    return page.evaluate(
        """(nid) => {
            const c = document.querySelector(`[data-node-id="${nid}"] .node-card`);
            return c ? c.offsetWidth : null;
        }""",
        node_id,
    )


def _open(page: Page) -> None:
    goto_ready(page, _URL)
    page.wait_for_selector("[data-node-id]")
    page.wait_for_selector(".ui-node-slot")
    page.wait_for_timeout(800)  # let the graph sync + center


def test_manual_width_is_a_minimum(page: Page, harness):
    """manual_width + width=140 writes a min-width; the slot never goes below it
    and never clips — content wider than the minimum expands the node."""
    _open(page)
    nid = _node_id(page)

    page.click('[data-testid="size-manual-width"]')
    page.wait_for_timeout(400)

    style = _slot_style(page, nid)
    assert "min-width: 140" in style, f"slot did not get manual min-width: {style!r}"
    assert "overflow" not in style, f"manual slot must not clip: {style!r}"

    box = _slot_box(page, nid)
    assert box["width"] >= 140.0 - 1.0, f"slot below its minimum: {box}"

    # The card must FILL the slot: the skin's own clamps (min-w-64 max-w-sm)
    # are released by the data-size-adapt CSS, so card width == slot width.
    card_w = _card_width(page, nid)
    assert card_w is not None and abs(card_w - box["width"]) < 2.0, (  # noqa: PT018
        f"card does not fill the manual-width slot: card={card_w} slot={box['width']}"
    )


def test_manual_width_expands_past_skin_max(page: Page, harness):
    """A wide minimum (500px > max-w-sm 384px) drives both slot and card to it —
    proves the min governs and the skin's max-width clamp is released."""
    _open(page)
    nid = _node_id(page)

    page.click('[data-testid="size-manual-width-wide"]')
    page.wait_for_timeout(400)

    box = _slot_box(page, nid)
    assert abs(box["width"] - 500.0) < 2.0, f"slot not at its 500px minimum: {box}"
    card_w = _card_width(page, nid)
    assert card_w is not None and abs(card_w - 500.0) < 2.0, (  # noqa: PT018
        f"card stuck below the 500px minimum (max-w-sm not released?): card={card_w}"
    )


def test_auto_clears_inline_size(page: Page, harness):
    """Returning to auto clears the inline minimum so the slot hugs content again."""
    _open(page)
    nid = _node_id(page)

    page.click('[data-testid="size-manual-width"]')
    page.wait_for_timeout(300)
    page.click('[data-testid="size-auto"]')
    page.wait_for_timeout(300)

    style = _slot_style(page, nid)
    assert "width" not in style, f"auto slot still carries inline width: {style!r}"


def test_gadget_appears_for_single_selection(page: Page, harness):
    """Clicking the single node shows the 8-handle resize gadget; clearing hides it."""
    _open(page)
    nid = _node_id(page)

    assert page.locator('[data-testid="resize-gadget"]').count() == 0

    box = _slot_box(page, nid)
    page.mouse.click(box["sx"] + 30, box["sy"] + 14)  # click node header area
    page.wait_for_timeout(500)
    assert page.locator('[data-testid="resize-gadget"]').is_visible()
    assert page.locator(".hw-resize-grip").count() == 8

    # Deselect via an empty-area box-select drag near the zoom viewport's
    # top-left (clear of the node) → selection clears → gadget disappears.
    zoom_box = probe_box(page.locator('[data-testid="size-zoom"]'), "size-zoom")
    ex, ey = zoom_box["x"] + 20, zoom_box["y"] + 20
    page.mouse.move(ex, ey)
    page.mouse.down()
    page.mouse.move(ex + 40, ey + 40, steps=4)
    page.mouse.up()
    page.wait_for_timeout(600)
    assert page.locator('[data-testid="resize-gadget"]').count() == 0


def test_gadget_follows_node_drag(page: Page, harness):
    """Dragging the selected node moves the gadget with it (the drag writes
    style directly — the gadget must be refit per move, no observer fires)."""
    _open(page)
    nid = _node_id(page)

    box = _slot_box(page, nid)
    page.mouse.click(box["sx"] + 30, box["sy"] + 14)
    page.wait_for_timeout(500)
    assert page.locator('[data-testid="resize-gadget"]').is_visible()

    def gadget_box() -> dict:
        return probe_box(page.locator('[data-testid="resize-gadget"]'), "resize-gadget")

    g_before = gadget_box()
    n_before = _slot_box(page, nid)

    # Drag the node by its header (drag-handle area).
    page.mouse.move(box["sx"] + 30, box["sy"] + 14)
    page.mouse.down()
    page.mouse.move(box["sx"] + 30 + 80, box["sy"] + 14 + 50, steps=6)
    page.mouse.up()
    page.wait_for_timeout(400)

    n_after = _slot_box(page, nid)
    assert n_after["sx"] > n_before["sx"] + 40, f"node did not move: {n_before} -> {n_after}"

    g_after = gadget_box()
    assert g_after is not None, "gadget vanished after node drag"
    moved_x = g_after["x"] - g_before["x"]
    node_moved_x = n_after["sx"] - n_before["sx"]
    assert abs(moved_x - node_moved_x) < 3.0, (
        f"gadget did not follow the node: gadget dx={moved_x} node dx={node_moved_x}"
    )


def test_drag_right_grip_sets_width_minimum(page: Page, harness):
    """Dragging the right grip widens the slot (manual_width minimum) and it persists."""
    _open(page)
    nid = _node_id(page)

    box = _slot_box(page, nid)
    page.mouse.click(box["sx"] + 30, box["sy"] + 14)
    page.wait_for_timeout(500)
    page.wait_for_selector('.hw-resize-grip[data-handle="right"]')

    before = _slot_box(page, nid)
    grip = probe_box(page.locator('.hw-resize-grip[data-handle="right"]'), "right grip")
    gx, gy = grip["x"] + grip["width"] / 2, grip["y"] + grip["height"] / 2

    page.mouse.move(gx, gy)
    page.mouse.down()
    page.mouse.move(gx + 60, gy, steps=5)
    page.mouse.up()
    page.wait_for_timeout(500)  # commit → set_property → subscriber restyles slot

    after = _slot_box(page, nid)
    assert after["width"] > before["width"] + 20, (
        f"right-grip drag did not widen the slot: before={before} after={after}"
    )
    style = _slot_style(page, nid)
    assert "min-width" in style, f"resized slot missing min-width: {style!r}"
    assert "overflow" not in style, f"resized slot must not clip: {style!r}"


# NOTE: the "shrink below floor → return to auto" behaviour is not covered here —
# this route's node compresses to ~1px, so it has no floor to hit. A synthetic
# floor DOES exist now: test_widget_size_box.py hosts a 1280x720 replaced element
# (a hand-injected sized div did not survive the card's flex intrinsic-sizing;
# an <img> does, because a replaced element's natural size wins) and measures the
# floor the way canvas.vue does — in MANUAL mode, since `auto` just reads the
# skin's 384px max-w-sm clamp whatever the content is. Extend that route if the
# commit-side recompose (per-axis floor detection → size_adapt) ever needs
# browser coverage; it is a few lines of pure comparison in onResizeGripDown.


def test_pins_stay_clickable_under_the_resize_grips(page: Page, harness):
    """A pin under an edge grip must still receive the mousedown.

    The gadget paints ABOVE the node — it has to, or the edge grips are not
    hit-testable at all — and the edge grips span the card border for the
    node's whole height. That is exactly where pins live: they straddle the
    border by design, so on any node with pins the two overlap and no offset
    separates them.

    z-index cannot arbitrate. A pin's ``z-index: 10000`` is trapped inside the
    selected node's own stacking context (``.node-selected`` is
    ``z-index: 1000``), so it orders the pin only WITHIN its node, never
    against the gadget — a sibling of that node's container. ``canvas.vue``
    therefore hands the grips' hit area back to a hovered pin
    (``_syncGripPassthrough``).

    Without that handover the node still resizes and still looks right, and
    every other test here passes — the only symptom is that connections can no
    longer be drawn from half the pins. Hence this test.
    """
    _open(page)
    nid = _node_id(page)

    box = _slot_box(page, nid)
    page.mouse.click(box["sx"] + 30, box["sy"] + 14)
    page.wait_for_timeout(500)
    page.wait_for_selector('.hw-resize-grip[data-handle="right"]')

    # Record what each mousedown actually lands on, at the document level.
    page.evaluate(
        """() => {
            window.__hwSeen = [];
            document.addEventListener('mousedown', (e) => {
                const t = e.target;
                window.__hwSeen.push(
                    t.classList.contains('connection-pin') ? 'pin'
                    : (t.dataset && t.dataset.handle) ? 'grip' : 'other');
            }, true);
        }"""
    )

    pins = page.evaluate(
        """() => [...document.querySelectorAll('.connection-pin')]
            .filter(p => p.dataset.pinFlowType !== 'ghost')
            .map(p => { const r = p.getBoundingClientRect();
                        return {id: p.dataset.pinId,
                                x: r.left + r.width / 2, y: r.top + r.height / 2}; })"""
    )
    assert pins, "fixture node exposes no real pins — nothing to overlap"

    for pin in pins:
        page.mouse.move(pin["x"], pin["y"])   # hover first: the handover is on mousemove
        page.mouse.down()
        page.mouse.up()
        page.wait_for_timeout(120)

    seen = page.evaluate("() => window.__hwSeen")
    assert seen and all(t == "pin" for t in seen), (
        f"a grip swallowed a pin's mousedown: {seen} for pins "
        f"{[p['id'] for p in pins]} — connections cannot be drawn from those pins"
    )

    # And the node must not have been resized by any of that.
    assert _slot_style(page, nid) == "", (
        f"clicking a pin started a resize: {_slot_style(page, nid)!r}"
    )
