"""Browser tests for the flow meter on a haystack row.

Two things only a real browser shows: the strip opens from the bar and keeps the worst Flow nearest
the end of the row, and a tooltip is filled when it opens (its ``before-show`` event), so the numbers
cost no traffic until someone hovers a bar.
"""

import pytest
from playwright.sync_api import Page, expect

from tests.ui.harness.nav import goto_ready

_PATH = "/flow-meter"

pytestmark = pytest.mark.ui


def test_hovering_the_collapsed_bar_shows_the_worst_flows_numbers(page: Page, harness):
    goto_ready(page, f"{harness}{_PATH}")
    page.locator("[data-hw-mark=flow-meter]").hover()
    tooltip = page.locator(".q-tooltip")
    expect(tooltip).to_contain_text("Tick (blocks when full)")
    expect(tooltip).to_contain_text("load 95%")
    expect(tooltip).to_contain_text("dropped 4 (just now)")


def test_clicking_the_bar_opens_a_strip_with_one_bar_per_flow(page: Page, harness):
    goto_ready(page, f"{harness}{_PATH}")
    expect(page.locator("[data-hw-mark=flow-bar]")).to_have_count(0)
    page.locator("[data-hw-mark=flow-meter]").click()
    bars = page.locator("[data-hw-mark=flow-bar]")
    expect(bars).to_have_count(3)

    meter = page.locator("[data-hw-mark=flow-meter]").bounding_box()
    boxes = [bars.nth(i).bounding_box() for i in range(3)]
    assert meter is not None
    assert all(b is not None for b in boxes)
    # Worst first, nearest the end of the row: the first bar is the rightmost.
    xs = [b["x"] for b in boxes if b is not None]
    assert xs[0] > xs[1] > xs[2]
    assert xs[0] < meter["x"]
    # The group gap sits between the first bar and the second.
    assert xs[0] - xs[1] > xs[1] - xs[2]


def test_a_bars_tooltip_is_filled_when_it_opens(page: Page, harness):
    goto_ready(page, f"{harness}{_PATH}")
    page.locator("[data-hw-mark=flow-meter]").click()
    page.locator("[data-hw-mark=flow-bar]").nth(1).hover()
    # The first tooltip may still be fading out, so pick the one for this bar.
    tooltip = page.get_by_role("tooltip").filter(has_text="node_source_a")
    expect(tooltip).to_contain_text("node_source_a (blocks when full)")
    expect(tooltip).to_contain_text("queue 3/100")


def test_clicking_the_bar_a_second_time_closes_the_strip(page: Page, harness):
    goto_ready(page, f"{harness}{_PATH}")
    meter = page.locator("[data-hw-mark=flow-meter]")
    meter.click()
    expect(page.locator("[data-hw-mark=flow-bar]").first).to_be_visible()
    meter.click()
    expect(page.locator("[data-hw-mark=flow-bar]").first).not_to_be_visible()
