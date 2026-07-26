"""Browser tests for a widget's declared size box (``@widget(min_width=, min_height=)``).

A node's size floor is produced by CSS, not by Haywire: the resize gadget writes
a ``min-width``/``min-height`` onto the host slot and reads ``offsetWidth`` back,
so the floor is the max-content size of the card subtree. A widget holding a
replaced element at its natural 1280x720 therefore floors its node at that size,
and the gadget can grow the node but not shrink it. A declared box replaces that
content vote with CSS size containment.

Only a real browser can show this — it is entirely a question of what the layout
engine computes. The ``/graph-widget-box`` route puts the SAME oversized ``<img>``
on three nodes, differing only in what their widget declares.

Two things make the measurements delicate, and both are load-bearing:

- The floor must be read in MANUAL mode. At rest the skin's ``max-w-sm`` clamps
  the card to 384px whatever its content is, which is exactly why the bug is
  invisible until you drag. See :func:`_floor`.
- Widget containers collapse to ``max-height: 0`` unless their node is selected,
  so anything about widget geometry must be measured while selected.
"""

import pytest
from playwright.sync_api import Page

from haybale_testing.widgets.oversized_content_widget import (
    BOX_HEIGHT,
    BOX_WIDTH,
    CONTENT_WIDTH,
)
from tests.ui.harness.nav import goto_ready

_URL = "http://localhost:8090/graph-widget-box"

pytestmark = pytest.mark.ui


def _node_id(page: Page, which: str) -> str:
    return page.get_attribute(f"#{which}-node-id", "data-node")


def _slot_box(page: Page, node_id: str) -> dict:
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


def _floor(page: Page, node_id: str) -> dict:
    """The node's true content floor, measured the way canvas.vue measures it.

    Mirrors the commit-time measurement in ``onResizeGripDown``'s ``onUp``: clear
    the inline minimum and read the content-driven size back. Crucially it reads
    in MANUAL mode — the skin's ``min-w-64 max-w-sm`` clamp is released there
    (the card-fill CSS keys off ``data-size-adapt``), so a node with oversized
    content only reveals its real floor once manual mode unlocks it. Measured in
    ``auto`` this returns 384px, the ``max-w-sm`` clamp, whatever the content is.
    """
    return page.evaluate(
        """(nid) => {
            const container = document.querySelector(`[data-node-id="${nid}"]`);
            const slot = container && container.querySelector('.ui-node-slot');
            if (!slot) return null;
            const prevMode = slot.getAttribute('data-size-adapt') || 'auto';
            const prevW = slot.style.minWidth, prevH = slot.style.minHeight;
            slot.setAttribute('data-size-adapt', 'manual');
            slot.style.minWidth = ''; slot.style.minHeight = '';
            const out = { width: slot.offsetWidth, height: slot.offsetHeight };
            slot.style.minWidth = prevW; slot.style.minHeight = prevH;
            slot.setAttribute('data-size-adapt', prevMode);
            return out;
        }""",
        node_id,
    )


def _widget_box(page: Page, node_id: str) -> dict:
    """Geometry + stamped declaration of the node's widget container."""
    return page.evaluate(
        """(nid) => {
            const el = document.querySelector(`[data-node-id="${nid}"] .widget-container`);
            if (!el) return null;
            const cs = getComputedStyle(el);
            return {
                width: el.offsetWidth,
                height: el.offsetHeight,
                boxAttr: el.getAttribute('data-hw-widget-box'),
                inlineBoxAttr: el.getAttribute('data-hw-widget-inline-box'),
                minWidthVar: cs.getPropertyValue('--hw-widget-min-width').trim(),
                minHeightVar: cs.getPropertyValue('--hw-widget-min-height').trim(),
                contain: cs.contain,
            };
        }""",
        node_id,
    )


def _set_attr(page: Page, node_id: str, name: str, present: bool) -> None:
    """Toggle a containment marker in place — same DOM, containment on/off."""
    page.evaluate(
        """([nid, name, present]) => {
            const el = document.querySelector(`[data-node-id="${nid}"] .widget-container`);
            if (present) el.setAttribute(name, '1');
            else el.removeAttribute(name);
        }""",
        [node_id, name, present],
    )
    page.wait_for_timeout(150)


def _is_selected(page: Page, node_id: str) -> bool:
    return page.evaluate(
        """(nid) => document.querySelector(`[data-node-id="${nid}"]`)
                        .classList.contains('node-selected')""",
        node_id,
    )


def _select(page: Page, node_id: str) -> None:
    box = _slot_box(page, node_id)
    page.mouse.click(box["sx"] + 30, box["sy"] + 14)  # node header
    page.wait_for_timeout(500)


def _open(page: Page) -> None:
    goto_ready(page, _URL)
    page.wait_for_selector("[data-node-id]")
    page.wait_for_selector(".ui-node-slot")
    page.wait_for_timeout(800)


# ---------------------------------------------------------------------------
# The declaration reaches the DOM
# ---------------------------------------------------------------------------


def test_declared_box_reaches_the_dom(page: Page, harness):
    """@widget(min_width=, min_height=) → marker + custom props on the container.

    End-to-end through the real skin funnel (BaseSkin.render_widget), which is
    what makes the feature work for any skin without cooperation.
    """
    _open(page)
    nid = _node_id(page, "fixed")
    _select(page, nid)

    w = _widget_box(page, nid)
    assert w is not None, "boxed node rendered no widget container"
    assert w["boxAttr"], f"containment marker missing: {w}"
    assert w["minWidthVar"] == f"{BOX_WIDTH}px", f"min-width var not stamped: {w}"
    assert w["minHeightVar"] == f"{BOX_HEIGHT}px", f"min-height var not stamped: {w}"
    assert "size" in w["contain"], f"size containment not applied: {w}"


def test_width_only_declaration_contains_the_inline_axis(page: Page, harness):
    """min_width alone → inline-axis containment, leaving the block axis to content."""
    _open(page)
    nid = _node_id(page, "aspect")
    _select(page, nid)

    w = _widget_box(page, nid)
    assert w["inlineBoxAttr"], f"inline containment marker missing: {w}"
    assert not w["boxAttr"], f"width-only declaration must not contain both axes: {w}"
    assert "inline-size" in w["contain"], f"inline-size containment not applied: {w}"


# ---------------------------------------------------------------------------
# The floor
# ---------------------------------------------------------------------------


def test_content_sized_widget_floors_its_node_at_its_content(page: Page, harness):
    """The control, and the reported bug: content with no declared box IS the floor.

    Such a node can be grown by the gadget but not shrunk — the floor it measures
    at commit is the content's own natural size.
    """
    _open(page)
    nid = _node_id(page, "content")
    _select(page, nid)

    floor = _floor(page, nid)
    assert floor["width"] >= CONTENT_WIDTH, (
        f"fixture is not actually oversized — floor {floor['width']}px < content {CONTENT_WIDTH}px"
    )


@pytest.mark.parametrize("which", ["aspect", "fixed"])
def test_declared_box_frees_the_node_to_shrink(page: Page, harness, which):
    """Same content behind a declaration: the node is no longer floored by it."""
    _open(page)
    nid = _node_id(page, which)
    _select(page, nid)

    floor = _floor(page, nid)
    assert floor["width"] < CONTENT_WIDTH / 2, (
        f"{which} node still floored near its content size: {floor['width']}px"
    )


@pytest.mark.parametrize(
    "which,attr",
    [("aspect", "data-hw-widget-inline-box"), ("fixed", "data-hw-widget-box")],
)
def test_removing_the_marker_restores_the_content_floor(page: Page, harness, which, attr):
    """Containment is what frees the node — toggling it on the same DOM proves it."""
    _open(page)
    nid = _node_id(page, which)
    _select(page, nid)

    contained = _floor(page, nid)["width"]
    _set_attr(page, nid, attr, False)
    uncontained = _floor(page, nid)["width"]
    _set_attr(page, nid, attr, True)
    restored = _floor(page, nid)["width"]

    assert uncontained >= CONTENT_WIDTH, f"marker removal did not restore the content floor: {uncontained}px"
    assert contained < uncontained / 2, f"containment made no difference: {contained} vs {uncontained}"
    assert abs(restored - contained) < 2.0, f"floor did not return on restore: {restored} vs {contained}"


# ---------------------------------------------------------------------------
# Growth — containment must not cap it
# ---------------------------------------------------------------------------


def test_aspect_widget_grows_proportionally_with_the_card(page: Page, harness):
    """Inline-axis containment leaves the block axis to content, so aspect wins.

    This is the behaviour that must survive the fix: a frame viewer gets taller
    as its node gets wider, because the image's aspect ratio still drives the
    container's height. Full size containment would flatten it to a fixed box.
    """
    _open(page)
    nid = _node_id(page, "aspect")
    _select(page, nid)

    before = _widget_box(page, nid)
    page.click('[data-testid="aspect-grow"]')  # size_adapt=manual, 520x420
    page.wait_for_timeout(600)

    slot = _slot_box(page, nid)
    assert slot["width"] >= 518.0, f"node did not take the manual width: {slot}"

    # Clicking a control outside the canvas can drop the selection, and the
    # container collapses to max-height: 0 when it does.
    if not _is_selected(page, nid):
        _select(page, nid)

    after = _widget_box(page, nid)
    assert after["width"] > before["width"] + 50, (
        f"widget did not widen with the card: {before['width']} -> {after['width']}"
    )
    assert after["height"] > before["height"] + 20, (
        f"widget height did not follow its aspect ratio: {before['height']} -> {after['height']}"
    )


def test_fixed_box_widget_widens_but_keeps_its_declared_height(page: Page, harness):
    """Both axes contained: the width still stretches, the height stays declared.

    Documented, not incidental — a fully contained widget trades proportional
    growth for a floor in both axes. Declare min_width alone to keep the aspect.
    """
    _open(page)
    nid = _node_id(page, "fixed")
    _select(page, nid)

    before = _widget_box(page, nid)
    page.click('[data-testid="fixed-grow"]')
    page.wait_for_timeout(600)
    if not _is_selected(page, nid):
        _select(page, nid)

    after = _widget_box(page, nid)
    assert after["width"] > before["width"] + 50, (
        f"contained widget did not widen with the card: {before['width']} -> {after['width']}"
    )
    assert abs(after["height"] - BOX_HEIGHT) < 2.0, (
        f"contained widget height should stay at its declared box: {after['height']}"
    )
