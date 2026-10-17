"""Browser tests for the canvas lock: no gesture that changes the graph starts.

Drives the ``/graph-lock`` harness route: one node on a real GraphCanvasManager
dropped to level mode operate; ``refresh_mode`` pushes the ``levelMode`` prop to canvas.vue.
"""

import pytest
from playwright.sync_api import Page

from tests.ui.harness.nav import goto_ready, wait_for_canvas_settled
from tests.ui.harness.probe import attr

_PATH = "/graph-lock"

pytestmark = pytest.mark.ui


def _open(page: Page, harness, query: str = "") -> str:
    goto_ready(page, f"{harness}{_PATH}{query}")
    page.wait_for_selector("[data-node-id]")
    wait_for_canvas_settled(page)
    return attr(page, '[data-testid="lock-node-id"]', "data-node")


def _left(page: Page, node_id: str) -> str:
    return page.evaluate(
        '(nid) => document.querySelector(`[data-node-id="${nid}"]`).style.left',
        node_id,
    )


def _header(page: Page, node_id: str) -> tuple[float, float]:
    box = page.locator(f'[data-node-id="{node_id}"] .ui-node-slot').bounding_box()
    assert box is not None
    return box["x"] + 30, box["y"] + 14


def _model_pos(page: Page) -> str:
    return page.locator('[data-testid="lock-node-pos"]').inner_text()


def _drag_100px(page: Page, node_id: str) -> None:
    x, y = _header(page, node_id)
    page.mouse.move(x, y)
    page.mouse.down()
    page.mouse.move(x + 100, y, steps=8)
    page.mouse.up()
    # Long enough for a drag's events to reach the server and the polled label to refresh.
    page.wait_for_timeout(600)


def test_locked_canvas_blocks_drag(page: Page, harness):
    """Dragging a node 100px on a locked canvas moves neither its card nor its model position."""
    node_id = _open(page, harness)
    left_before = _left(page, node_id)
    pos_before = _model_pos(page)

    _drag_100px(page, node_id)

    assert _left(page, node_id) == left_before
    assert _model_pos(page) == pos_before


def test_locked_server_snaps_back_a_stale_drag(page: Page, harness):
    """A drag the browser still allows is refused by the server, and the card moves back."""
    node_id = _open(page, harness, "?stale=true")
    left_before = _left(page, node_id)
    pos_before = _model_pos(page)

    _drag_100px(page, node_id)

    page.wait_for_function(
        '([nid, left]) => document.querySelector(`[data-node-id="${nid}"]`).style.left === left',
        arg=[node_id, left_before],
    )
    assert _model_pos(page) == pos_before


def _slot_size_state(page: Page, node_id: str) -> dict:
    return page.evaluate(
        """(nid) => {
            const slot = document.querySelector(`[data-node-id="${nid}"] .ui-node-slot`);
            return {
                minWidth: slot.style.minWidth,
                sizeAdapt: slot.getAttribute('data-node-props-size-adapt'),
            };
        }""",
        node_id,
    )


def test_locked_server_restores_the_size_of_a_stale_resize(page: Page, harness):
    """A resize the browser still allows is refused by the server, and the card returns to its size."""
    node_id = _open(page, harness, "?stale=true")
    before = _slot_size_state(page, node_id)

    x, y = _header(page, node_id)
    page.mouse.click(x, y)
    grip = page.locator('.hw-resize-grip[data-handle="right"]')
    grip.wait_for()
    box = grip.bounding_box()
    assert box is not None
    gx, gy = box["x"] + box["width"] / 2, box["y"] + box["height"] / 2
    page.mouse.move(gx, gy)
    page.mouse.down()
    page.mouse.move(gx + 60, gy, steps=5)
    assert _slot_size_state(page, node_id)["minWidth"] != before["minWidth"]
    page.mouse.up()

    page.wait_for_function(
        """([nid, minWidth, sizeAdapt]) => {
            const slot = document.querySelector(`[data-node-id="${nid}"] .ui-node-slot`);
            return slot.style.minWidth === minWidth
                && slot.getAttribute('data-node-props-size-adapt') === sizeAdapt;
        }""",
        arg=[node_id, before["minWidth"], before["sizeAdapt"]],
    )


def test_a_locked_canvas_selects_without_resize_grips(page: Page, harness):
    """A click selects on a locked canvas, and no resize grips appear."""
    node_id = _open(page, harness)

    x, y = _header(page, node_id)
    page.mouse.click(x, y)
    page.wait_for_selector(f'[id="{node_id}"].node-selected')

    assert page.locator('[data-testid="resize-gadget"]').count() == 0
