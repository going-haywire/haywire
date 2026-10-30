"""A path picker holding a very long path does not set its node's minimum width; its status line crops."""

import pytest
from playwright.sync_api import Page

from tests.ui.harness.nav import goto_ready
from tests.ui.harness.probe import attr

pytestmark = pytest.mark.ui


def _open(page: Page, harness) -> tuple[str, str]:
    goto_ready(page, f"{harness}/graph-path-demo")
    page.wait_for_selector("[data-node-id] .ui-node-slot")
    page.wait_for_timeout(800)
    return attr(page, "#path-node-id", "data-node"), page.inner_text("#path-full")


def _floor_width(page: Page, node_id: str) -> int:
    """The node's content floor, read in manual mode the way the resize gadget reads it."""
    return page.evaluate(
        """(nid) => {
            const slot = document.querySelector(`[data-node-id="${nid}"] .ui-node-slot`);
            const prevMode = slot.getAttribute('data-node-props-size-adapt') || 'auto';
            const prevW = slot.style.minWidth;
            slot.setAttribute('data-node-props-size-adapt', 'manual');
            slot.style.minWidth = '';
            const width = slot.offsetWidth;
            slot.style.minWidth = prevW;
            slot.setAttribute('data-node-props-size-adapt', prevMode);
            return width;
        }""",
        node_id,
    )


def _status_line(page: Page, full: str) -> dict:
    return page.evaluate(
        """full => {
            const line = [...document.querySelectorAll('.hw-path-fit')].find(l => l.title === full);
            if (!line) return null;
            return {text: line.textContent, scroll: line.scrollWidth, client: line.clientWidth};
        }""",
        full,
    )


def test_a_long_path_does_not_widen_the_node(page: Page, harness):
    node_id, full = _open(page, harness)
    full_width = page.evaluate(
        """full => {
            const c = document.createElement('canvas').getContext('2d');
            c.font = '12px monospace';
            return c.measureText(full).width;
        }""",
        full,
    )
    floor = _floor_width(page, node_id)
    assert floor < 600, f"floor {floor}px follows the {len(full)}-char path"
    assert full_width > 2 * floor, "fixture path is not long enough to prove anything"


def test_the_status_line_crops_the_middle_and_keeps_the_file_name(page: Page, harness):
    _, full = _open(page, harness)
    page.wait_for_function(
        """full => {
            const line = [...document.querySelectorAll('.hw-path-fit')].find(l => l.title === full);
            return line && line.textContent.includes('..');
        }""",
        arg=full,
        timeout=5000,
    )
    line = _status_line(page, full)
    assert line is not None
    assert line["text"] != full
    assert line["text"].rstrip("…").endswith("picture.png") or "picture" in line["text"]
