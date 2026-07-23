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

_URL = "http://localhost:8090/graph-size"

pytestmark = pytest.mark.ui


def _node_id(page: Page) -> str:
    return page.get_attribute("#size-node-id", "data-node")


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
    assert card_w is not None and abs(card_w - box["width"]) < 2.0, (
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
    assert card_w is not None and abs(card_w - 500.0) < 2.0, (
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
    zoom_box = page.locator('[data-testid="size-zoom"]').bounding_box()
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
        return page.locator('[data-testid="resize-gadget"]').bounding_box()

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
    grip = page.locator('.hw-resize-grip[data-handle="right"]').bounding_box()
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


# NOTE: the "shrink below floor → return to auto" behaviour is exercised in the
# real app (a node with an incompressible fixed-size widget, e.g. the frame
# view, provides a genuine content floor). It is deliberately NOT covered by a
# browser test here: the harness node's content compresses to ~1px, and a
# hand-injected fixed-width block does not survive the card's flex
# intrinsic-sizing under manual mode, so no reliable synthetic floor can be
# built. The commit-side recompose (per-axis floor detection → size_adapt) is a
# few lines of pure comparison in canvas.vue onResizeGripDown.
