"""Browser tests for the stage origin: the corner-bracket marker and the drag clamp.

Drives the ``/graph-stage`` harness route: one on-stage node at stage ``(0, 0)`` on a canvas of
the requested channel.
"""

import pytest
from playwright.sync_api import Page

from tests.ui.harness.nav import goto_ready, wait_for_canvas_settled
from tests.ui.harness.probe import attr

pytestmark = pytest.mark.ui

_MARKER = '[data-testid="stage-origin"]'


def _open(page: Page, harness, channel: str) -> None:
    goto_ready(page, f"{harness}/graph-stage?channel={channel}")
    page.wait_for_selector("[data-node-id]")
    wait_for_canvas_settled(page)


def _top_left(page: Page, selector: str) -> tuple[float, float]:
    box = page.locator(selector).first.bounding_box()
    assert box is not None, selector
    return box["x"], box["y"]


def test_a_stage_canvas_marks_its_origin_at_the_node_at_stage_zero(page: Page, harness):
    _open(page, harness, "stage")
    page.wait_for_selector(_MARKER)
    node_id = attr(page, "#stage-node-id", "data-node")
    mx, my = _top_left(page, _MARKER)
    nx, ny = _top_left(page, f'[data-node-id="{node_id}"]')
    # A node at stage (0, 0) sits exactly on the bracket's corner.
    assert abs(mx - nx) < 1.0 and abs(my - ny) < 1.0, ((mx, my), (nx, ny))  # noqa: PT018


def test_a_patch_canvas_has_no_marker(page: Page, harness):
    _open(page, harness, "patch")
    assert page.locator(_MARKER).count() == 0


def test_dragging_a_stage_node_up_and_left_stops_at_the_origin(page: Page, harness):
    _open(page, harness, "stage")
    page.wait_for_selector(_MARKER)
    node_id = attr(page, "#stage-node-id", "data-node")
    nx, ny = _top_left(page, f'[data-node-id="{node_id}"]')
    # Start on the node's header, then drag far up and left of the origin.
    sx, sy = nx + 30, ny + 14
    page.mouse.move(sx, sy)
    page.mouse.down()
    page.mouse.move(sx - 400, sy - 400, steps=10)
    page.mouse.up()
    page.wait_for_timeout(200)
    mx, my = _top_left(page, _MARKER)
    ex, ey = _top_left(page, f'[data-node-id="{node_id}"]')
    assert abs(ex - mx) < 1.0 and abs(ey - my) < 1.0, ((ex, ey), (mx, my))  # noqa: PT018


def test_resizing_a_stage_node_from_its_top_left_stops_at_the_origin(page: Page, harness):
    _open(page, harness, "stage")
    page.wait_for_selector(_MARKER)
    node_id = attr(page, "#stage-node-id", "data-node")
    selector = f'[data-node-id="{node_id}"]'
    before = page.locator(selector).first.bounding_box()
    assert before is not None
    page.mouse.click(before["x"] + 30, before["y"] + 14)
    page.wait_for_selector('.hw-resize-grip[data-handle="top-left"]')
    grip = page.locator('.hw-resize-grip[data-handle="top-left"]').bounding_box()
    assert grip is not None
    gx, gy = grip["x"] + grip["width"] / 2, grip["y"] + grip["height"] / 2

    page.mouse.move(gx, gy)
    page.mouse.down()
    page.mouse.move(gx - 150, gy - 150, steps=10)
    page.mouse.up()
    page.wait_for_timeout(500)

    mx, my = _top_left(page, _MARKER)
    after = page.locator(selector).first.bounding_box()
    assert after is not None
    # The node's top-left stays on the origin, and the opposite (bottom-right) corner stays put.
    assert abs(after["x"] - mx) < 1.0 and abs(after["y"] - my) < 1.0, (after, (mx, my))  # noqa: PT018
    assert abs((after["x"] + after["width"]) - (before["x"] + before["width"])) < 1.0, (before, after)
    assert abs((after["y"] + after["height"]) - (before["y"] + before["height"])) < 1.0, (before, after)
