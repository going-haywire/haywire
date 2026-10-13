"""Browser tests for entering a Graph-node card by double-click.

Drives the ``/graph-enter`` harness route: one Group card on a real
GraphCanvasManager. Entering publishes a ``SubgraphNavigation`` that the route
records into ``enter-log``.
"""

import pytest
from playwright.sync_api import Page

from tests.ui.harness.nav import goto_ready, wait_for_canvas_settled
from tests.ui.harness.probe import attr, box

_PATH = "/graph-enter"

pytestmark = pytest.mark.ui


def _open(page: Page, harness, query: str = "") -> str:
    goto_ready(page, f"{harness}{_PATH}{query}")
    page.wait_for_selector("[data-node-enterable]")
    wait_for_canvas_settled(page)
    return attr(page, '[data-testid="enter-card-id"]', "data-node")


def _title_point(page: Page, node_id: str) -> tuple[float, float]:
    slot = box(page.locator(f'[data-node-id="{node_id}"] .ui-node-slot'), "card slot")
    return slot["x"] + 30, slot["y"] + 14


def _log(page: Page) -> str:
    return page.locator('[data-testid="enter-log"]').inner_text()


def test_double_click_enters_a_group(page: Page, harness):
    """Double-clicking the card's title asks the session to open the Group on that node."""
    node_id = _open(page, harness)

    x, y = _title_point(page, node_id)
    page.mouse.dblclick(x, y)

    page.wait_for_function(
        "(nid) => document.querySelector('[data-testid=\"enter-log\"]').innerText === nid",
        arg=node_id,
    )


def test_double_click_enters_on_a_locked_level(page: Page, harness):
    """A locked canvas still lets a double-click enter: entering only views."""
    node_id = _open(page, harness, "?locked=true")

    x, y = _title_point(page, node_id)
    page.mouse.dblclick(x, y)

    page.wait_for_function(
        "(nid) => document.querySelector('[data-testid=\"enter-log\"]').innerText === nid",
        arg=node_id,
    )


def test_double_click_on_a_widget_does_not_enter(page: Page, harness):
    """A double-click on an interactive element inside the card leaves the level unchanged."""
    node_id = _open(page, harness)
    # An input stands in for a card widget (a slider, a text field): the guard keys off
    # the element kind, not off which skin drew it.
    page.evaluate(
        """(nid) => {
            const slot = document.querySelector(`[data-node-id="${nid}"] .ui-node-slot`);
            const input = document.createElement('input');
            input.setAttribute('data-testid', 'injected-input');
            slot.appendChild(input);
        }""",
        node_id,
    )

    page.locator('[data-testid="injected-input"]').dblclick()
    page.wait_for_timeout(600)

    assert _log(page) == ""
