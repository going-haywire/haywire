"""Browser tests for stacking order: overlapping cards paint by it, and only the patch lifts on hover.

Drives the ``/graph-stack`` harness route: two overlapping on-stage nodes, ``back`` (z 0) under
``front`` (z 1), on a canvas of the requested channel.
"""

import pytest
from playwright.sync_api import FloatRect, Page

from tests.ui.harness.nav import goto_ready, wait_for_canvas_settled
from tests.ui.harness.probe import attr

pytestmark = pytest.mark.ui


def _open(page: Page, harness, channel: str) -> tuple[str, str]:
    goto_ready(page, f"{harness}/graph-stack?channel={channel}")
    page.wait_for_selector("[data-node-id]")
    wait_for_canvas_settled(page)
    return attr(page, "#stack-ids", "data-back"), attr(page, "#stack-ids", "data-front")


def _box(page: Page, node_id: str) -> FloatRect:
    box = page.locator(f'[data-node-id="{node_id}"]').first.bounding_box()
    assert box is not None, node_id
    return box


def _overlap_centre(page: Page, back: str, front: str) -> tuple[float, float]:
    b, f = _box(page, back), _box(page, front)
    left, top = max(b["x"], f["x"]), max(b["y"], f["y"])
    right = min(b["x"] + b["width"], f["x"] + f["width"])
    bottom = min(b["y"] + b["height"], f["y"] + f["height"])
    assert right > left, "the fixture's cards must overlap"
    assert bottom > top, "the fixture's cards must overlap"
    return (left + right) / 2, (top + bottom) / 2


def _card_at(page: Page, x: float, y: float) -> str | None:
    return page.evaluate(
        """([x, y]) => {
            const hit = document.elementFromPoint(x, y);
            const card = hit && hit.closest('[data-node-id]');
            return card ? card.getAttribute('data-node-id') : null;
        }""",
        [x, y],
    )


@pytest.mark.parametrize("channel", ["patch", "stage"])
def test_the_higher_card_paints_on_top(page: Page, harness, channel: str):
    back, front = _open(page, harness, channel)
    page.mouse.move(5, 5)
    assert _card_at(page, *_overlap_centre(page, back, front)) == front


@pytest.mark.parametrize("channel", ["patch", "stage"])
def test_a_card_below_zero_still_paints_under_the_card_above(page: Page, harness, channel: str):
    """A Send to Back writes negative values; the card stays drawn, only beneath the others."""
    goto_ready(page, f"{harness}/graph-stack?channel={channel}&negative=1")
    page.wait_for_selector("[data-node-id]")
    wait_for_canvas_settled(page)
    back, front = attr(page, "#stack-ids", "data-back"), attr(page, "#stack-ids", "data-front")
    page.mouse.move(5, 5)

    assert _card_at(page, *_overlap_centre(page, back, front)) == front
    b = _box(page, back)
    assert _card_at(page, b["x"] + 10, b["y"] + 10) == back  # its own corner, clear of the front card


@pytest.mark.parametrize(("channel", "on_top"), [("patch", "back"), ("stage", "front")])
def test_hover_lifts_a_back_card_in_the_patch_only(page: Page, harness, channel: str, on_top: str):
    back, front = _open(page, harness, channel)
    point = _overlap_centre(page, back, front)
    b = _box(page, back)
    page.mouse.move(b["x"] + 12, b["y"] + 12)  # back's exposed upper left
    page.wait_for_timeout(100)
    assert _card_at(page, *point) == {"back": back, "front": front}[on_top]


def test_a_stage_drag_keeps_the_stacking_order(page: Page, harness):
    back, front = _open(page, harness, "stage")
    b = _box(page, back)
    sx, sy = b["x"] + 30, b["y"] + 14
    page.mouse.move(sx, sy)
    page.mouse.down()
    page.mouse.move(sx + 10, sy + 10, steps=5)
    page.mouse.up()
    page.mouse.move(5, 5)
    page.wait_for_timeout(200)
    assert _card_at(page, *_overlap_centre(page, back, front)) == front


@pytest.mark.parametrize(("channel", "on_top"), [("patch", "back"), ("stage", "front")])
def test_a_dragged_back_card_lifts_in_the_patch_only(page: Page, harness, channel: str, on_top: str):
    back, front = _open(page, harness, channel)
    b = _box(page, back)
    sx, sy = b["x"] + 30, b["y"] + 14
    page.mouse.move(sx, sy)
    page.mouse.down()
    page.mouse.move(sx + 10, sy + 10, steps=5)
    page.wait_for_timeout(100)
    try:
        assert _card_at(page, *_overlap_centre(page, back, front)) == {"back": back, "front": front}[on_top]
    finally:
        page.mouse.up()
