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


def _title(page: Page, node_id: str):
    return page.locator(f'[data-node-id="{node_id}"] .text-h6')


def _log(page: Page) -> str:
    return page.locator('[data-testid="enter-log"]').inner_text()


def test_double_click_enters_a_group(page: Page, harness):
    """Double-clicking the card's title asks the session to open the Group on that node."""
    node_id = _open(page, harness)

    _title(page, node_id).dblclick()

    page.wait_for_function(
        "(nid) => document.querySelector('[data-testid=\"enter-log\"]').innerText === nid",
        arg=node_id,
    )


def test_double_click_enters_on_a_locked_level(page: Page, harness):
    """A canvas in level mode operate still lets a double-click enter."""
    node_id = _open(page, harness, "?mode=operate")

    # The title takes no pointer input below edit, so the press lands on the card under it.
    found = box(_title(page, node_id), "card title")
    page.mouse.dblclick(found["x"] + found["width"] / 2, found["y"] + found["height"] / 2)

    page.wait_for_function(
        "(nid) => document.querySelector('[data-testid=\"enter-log\"]').innerText === nid",
        arg=node_id,
    )


def test_double_click_on_a_widget_does_not_enter(page: Page, harness):
    """A double-click on the card's own number widget leaves the level unchanged."""
    node_id = _open(page, harness)
    widget = page.locator(f'[data-node-id="{node_id}"] .number-drag__center')
    widget.wait_for()

    widget.dblclick()
    page.wait_for_timeout(600)

    assert _log(page) == ""

    # The same card still enters from its title: the silence above is the guard,
    # not a card that cannot be entered.
    _title(page, node_id).dblclick()
    page.wait_for_function(
        "(nid) => document.querySelector('[data-testid=\"enter-log\"]').innerText === nid",
        arg=node_id,
    )
