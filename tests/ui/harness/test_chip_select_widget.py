"""Browser tests for a chip select and a long status label on node cards.

Two silent failures, both visible only to a layout engine:

- A chip select's wrapped chips must not be clipped by ``compact-fields``' fixed 26px
  field height.
- A widget whose root is a Quasar field (a ``ui.select``) must get the size box it
  declares: Quasar keeps only ``class`` and ``style`` on a field's root, so the marker
  has to be a class.

And one floor: a ``LabelWidget`` holding a long status line must not set how narrow its
node can be, nor resize it when the text changes.

Floors are read in manual mode, as ``test_widget_size_box.py`` explains.
"""

from __future__ import annotations

import pytest
from playwright.sync_api import Page

from haybale_testing.widgets.chip_select_widget import CHIP_FIELD_MIN_WIDTH
from haywire.barn.builtin.widgets.basic_widgets import WRAPPED_LABEL_MAX_HEIGHT
from tests.ui.harness.nav import goto_ready, wait_for_canvas_settled
from tests.ui.harness.probe import attr

pytestmark = pytest.mark.ui

_PATH = "/graph-chip-field"
_COMPACT_FIELD_H = 26


def _node_id(page: Page, which: str) -> str:
    return attr(page, f"#{which}-node-id", "data-node")


def _open(page: Page, harness) -> None:
    goto_ready(page, f"{harness}{_PATH}")
    page.wait_for_selector("[data-node-id] .ui-node-slot")
    page.wait_for_selector("[data-node-id] .q-select--with-chips .q-chip")
    wait_for_canvas_settled(page)


def _select(page: Page, node_id: str) -> None:
    box = page.evaluate(
        """(nid) => {
            const slot = document.querySelector(`[data-node-id="${nid}"] .ui-node-slot`);
            const r = slot.getBoundingClientRect();
            return { x: r.left, y: r.top };
        }""",
        node_id,
    )
    page.mouse.click(box["x"] + 30, box["y"] + 14)  # node header
    page.wait_for_function(
        "(nid) => document.querySelector(`[data-node-id=\"${nid}\"]`).classList.contains('node-selected')",
        arg=node_id,
    )


def _floor(page: Page, node_id: str) -> dict:
    """The node's content floor, read in manual mode the way the resize gadget reads it."""
    return page.evaluate(
        """(nid) => {
            const slot = document.querySelector(`[data-node-id="${nid}"] .ui-node-slot`);
            const prevMode = slot.getAttribute('data-node-props-size-adapt') || 'auto';
            const prevW = slot.style.minWidth, prevH = slot.style.minHeight;
            slot.setAttribute('data-node-props-size-adapt', 'manual');
            slot.style.minWidth = ''; slot.style.minHeight = '';
            const out = { width: slot.offsetWidth, height: slot.offsetHeight };
            slot.style.minWidth = prevW; slot.style.minHeight = prevH;
            slot.setAttribute('data-node-props-size-adapt', prevMode);
            return out;
        }""",
        node_id,
    )


def _chip_field(page: Page, node_id: str) -> dict:
    """Where the chip field's container, markers and chips are, and how big."""
    return page.evaluate(
        """(nid) => {
            const card = document.querySelector(`[data-node-id="${nid}"]`);
            const field = card.querySelector('.q-select--with-chips');
            const control = field.querySelector('.q-field__control');
            const cr = control.getBoundingClientRect();
            const chips = [...field.querySelectorAll('.q-chip')].map((c) => c.getBoundingClientRect());
            return {
                fieldIsContainer: field.classList.contains('widget-container'),
                fieldHasMarker: field.classList.contains('hw-widget-inline-box'),
                contain: getComputedStyle(field).contain,
                controlHeight: control.offsetHeight,
                chipRows: new Set(chips.map((r) => Math.round(r.top))).size,
                chipsInside: chips.every((r) => r.bottom <= cr.bottom + 0.5),
                chipsOneRowWidth: chips.reduce((sum, r) => sum + r.width, 0),
            };
        }""",
        node_id,
    )


def _plain_control_height(page: Page, node_id: str) -> int:
    return page.evaluate(
        """(nid) => document.querySelector(
            `[data-node-id="${nid}"] .q-select--without-chips .q-field__control`).offsetHeight""",
        node_id,
    )


def _label(page: Page, node_id: str) -> dict:
    return page.evaluate(
        """(nid) => {
            const container = document.querySelector(`[data-node-id="${nid}"] .widget-container`);
            const label = container.firstElementChild;
            const slot = document.querySelector(`[data-node-id="${nid}"] .ui-node-slot`);
            return {
                text: label.textContent,
                tip: label.getAttribute('data-hw-tip'),
                scroll: label.scrollWidth,
                client: label.clientWidth,
                height: label.offsetHeight,
                containerHeight: container.offsetHeight,
                lineHeight: parseFloat(getComputedStyle(label).lineHeight),
                nodeWidth: slot.offsetWidth,
                nodeHeight: slot.offsetHeight,
            };
        }""",
        node_id,
    )


# ---------------------------------------------------------------------------
# The size box reaches a Quasar root
# ---------------------------------------------------------------------------


def test_the_size_box_reaches_a_select_root(page: Page, harness):
    """The select's outer field is the widget container, carries the marker and is contained."""
    _open(page, harness)
    nid = _node_id(page, "chips")
    _select(page, nid)

    field = _chip_field(page, nid)
    assert field["fieldIsContainer"], f"widget-container is not on the outer field: {field}"
    assert field["fieldHasMarker"], f"size-box marker is not on the outer field: {field}"
    assert "inline-size" in field["contain"], f"the chip field is not contained: {field}"


def test_a_chip_field_does_not_floor_its_node_at_one_row(page: Page, harness):
    _open(page, harness)
    nid = _node_id(page, "chips")
    _select(page, nid)

    floor = _floor(page, nid)["width"]
    one_row = _chip_field(page, nid)["chipsOneRowWidth"]
    assert one_row > 3 * CHIP_FIELD_MIN_WIDTH, f"fixture chips are too few to prove anything: {one_row}px"
    assert floor < one_row / 2, f"node floored near one row of chips: floor {floor}px, one row {one_row}px"


# ---------------------------------------------------------------------------
# Chips wrap in compact-fields
# ---------------------------------------------------------------------------


def test_wrapped_chips_grow_the_field_instead_of_being_clipped(page: Page, harness):
    _open(page, harness)
    nid = _node_id(page, "chips")
    _select(page, nid)

    field = _chip_field(page, nid)
    assert field["chipRows"] > 1, f"fixture chips did not wrap: {field}"
    assert field["controlHeight"] > _COMPACT_FIELD_H, f"field kept the fixed height: {field}"
    assert field["chipsInside"], f"wrapped chips are clipped below the field: {field}"


def test_a_plain_select_keeps_the_compact_height(page: Page, harness):
    _open(page, harness)
    nid = _node_id(page, "chips")
    _select(page, nid)

    assert _plain_control_height(page, nid) == _COMPACT_FIELD_H


# ---------------------------------------------------------------------------
# A long status label
# ---------------------------------------------------------------------------


def test_a_long_status_does_not_floor_its_node(page: Page, harness):
    _open(page, harness)
    nid = _node_id(page, "label")
    _select(page, nid)

    label = _label(page, nid)
    floor = _floor(page, nid)["width"]
    assert label["scroll"] > 2 * floor, f"fixture status is not long enough: {label}, floor {floor}px"
    assert label["scroll"] > label["client"], f"status line is not cut: {label}"
    assert label["tip"] == label["text"], f"hovering does not show the whole status: {label}"


def test_a_longer_status_does_not_resize_the_node(page: Page, harness):
    _open(page, harness)
    nid = _node_id(page, "label")
    _select(page, nid)

    before = _label(page, nid)
    page.get_by_test_id("longer-status").click()
    page.wait_for_function(
        """([nid, n]) => document.querySelector(`[data-node-id="${nid}"] .widget-container`)
                            .querySelector('.truncate').textContent.length > n""",
        arg=[nid, len(before["text"])],
    )
    after = _label(page, nid)
    assert after["nodeWidth"] == before["nodeWidth"], f"node widened: {before} -> {after}"
    assert after["nodeHeight"] == before["nodeHeight"], f"node grew taller: {before} -> {after}"
    assert after["height"] == before["height"], f"status line changed height: {before} -> {after}"
    assert after["tip"] == after["text"], f"the hover tip did not follow the status: {after}"


# ---------------------------------------------------------------------------
# A label that wraps
# ---------------------------------------------------------------------------


def test_a_wrapping_label_breaks_its_text_onto_more_lines(page: Page, harness):
    _open(page, harness)
    nid = _node_id(page, "wrapped")
    _select(page, nid)

    label = _label(page, nid)
    floor = _floor(page, nid)["width"]
    assert label["scroll"] <= label["client"], f"wrapped text overflows sideways: {label}"
    assert label["height"] > 2 * label["lineHeight"], f"text did not wrap onto more lines: {label}"
    assert floor < 400, f"wrapped text floors its node: {floor}px"


def test_a_wrapping_label_stops_growing_at_its_height_limit(page: Page, harness):
    _open(page, harness)
    nid = _node_id(page, "wrapped")
    _select(page, nid)

    short = _label(page, nid)
    page.get_by_test_id("longer-wrapped").click()
    page.wait_for_function(
        """([nid, n]) => document.querySelector(`[data-node-id="${nid}"] .widget-container`)
                            .firstElementChild.textContent.length > n""",
        arg=[nid, len(short["text"])],
    )
    label = _label(page, nid)
    assert label["height"] > WRAPPED_LABEL_MAX_HEIGHT, f"fixture text too short to reach the limit: {label}"
    assert label["containerHeight"] == WRAPPED_LABEL_MAX_HEIGHT, f"label not clipped at the limit: {label}"
