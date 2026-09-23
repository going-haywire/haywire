"""
Interaction tests: verify value write/read-back, mirror indicator (• prefix),
and the Reset item in the row's right-click Setting-row menu.
"""

import re

import pytest
from playwright.sync_api import Page, expect

from tests.ui.harness.nav import goto_ready

_NODE_PATH = "/node?class=haybale_testing.nodes.testbed.settings_node.SettingsNode&bag=example"

pytestmark = pytest.mark.ui


def _expect_override(page: Page, field: str, overridden: bool) -> None:
    """Wait until *field*'s label shows (or stops showing) the • override marker.

    A local override round-trips to the server, which re-renders the row; the
    • prefix is the rendered evidence that it landed. Waiting on the marker
    itself replaces guessing how long that takes.
    """
    label = page.locator(f'[data-field="{field}"] .text-xs').first
    matcher = expect(label)
    (matcher.to_have_text if overridden else matcher.not_to_have_text)(re.compile(r"^\u2022"))


def test_mirror_field_no_dot_prefix_initially(page: Page, harness):
    """The intensity mirror field label has no • prefix when not locally overridden."""
    goto_ready(page, f"{harness}{_NODE_PATH}")
    page.wait_for_selector("[data-field]")

    row = page.locator('[data-field="intensity"]')
    label_text = row.locator(".text-xs").first.inner_text()
    assert not label_text.startswith("•"), f"Expected no • prefix, got: {label_text!r}"


def test_mirror_field_dot_prefix_after_local_override(page: Page, harness):
    """Overriding the intensity mirror locally adds • to the label."""
    goto_ready(page, f"{harness}{_NODE_PATH}")
    page.wait_for_selector("[data-field]")

    row = page.locator('[data-field="intensity"]')
    # intensity is a mirror field rendered as a NumberDrag (float type)
    nd = row.locator("[data-number_drag]")
    nd.dblclick()
    edit_input = row.locator("input")
    edit_input.fill("0.3")
    edit_input.press("Enter")
    _expect_override(page, "intensity", True)

    updated_row = page.locator('[data-field="intensity"]')
    label_text = updated_row.locator(".text-xs").first.inner_text()
    assert label_text.startswith("•"), f"Expected • prefix after override, got: {label_text!r}"


def test_reset_button_appears_after_override(page: Page, harness):
    """After overriding intensity locally, the row's Setting-row menu offers an
    enabled Reset item (right-click the label cell to open it)."""
    goto_ready(page, f"{harness}{_NODE_PATH}")
    page.wait_for_selector("[data-field]")

    row = page.locator('[data-field="intensity"]')
    # intensity is a mirror field rendered as a NumberDrag (float type)
    nd = row.locator("[data-number_drag]")
    nd.dblclick()
    edit_input = row.locator("input")
    edit_input.fill("0.3")
    edit_input.press("Enter")
    _expect_override(page, "intensity", True)

    updated_row = page.locator('[data-field="intensity"]')
    updated_row.locator(".sf-label").click(button="right")
    reset_item = page.locator('[data-row-menu] >> text="Reset to global default"')
    expect(reset_item).to_be_visible()
    assert "disabled" not in (reset_item.get_attribute("class") or "")


def test_reset_button_removes_dot_prefix(page: Page, harness):
    """Clicking the Reset menu item on intensity removes the • prefix."""
    goto_ready(page, f"{harness}{_NODE_PATH}")
    page.wait_for_selector("[data-field]")

    # Override intensity via NumberDrag edit mode
    row = page.locator('[data-field="intensity"]')
    nd = row.locator("[data-number_drag]")
    nd.dblclick()
    edit_input = row.locator("input")
    edit_input.fill("0.2")
    edit_input.press("Enter")
    _expect_override(page, "intensity", True)

    # Open the row menu and click Reset
    updated_row = page.locator('[data-field="intensity"]')
    updated_row.locator(".sf-label").click(button="right")
    page.locator('[data-row-menu] >> text="Reset to global default"').click()
    _expect_override(page, "intensity", False)

    # • prefix should be gone
    final_row = page.locator('[data-field="intensity"]')
    label_text = final_row.locator(".text-xs").first.inner_text()
    assert not label_text.startswith("•"), f"Expected no • after reset, got: {label_text!r}"


def test_color_mirror_dot_prefix_after_local_override(page: Page, harness):
    """Typing a color value into the tint mirror adds • to the label."""
    goto_ready(page, f"{harness}{_NODE_PATH}")
    page.wait_for_selector("[data-field]")

    row = page.locator('[data-field="tint"]')
    edit_input = row.locator("input").first
    edit_input.fill("#0000ff")
    edit_input.press("Tab")
    _expect_override(page, "tint", True)

    updated_row = page.locator('[data-field="tint"]')
    label_text = updated_row.locator(".text-xs").first.inner_text()
    assert label_text.startswith("•"), f"Expected • prefix after color override, got: {label_text!r}"


def test_color_mirror_reset_button_appears_after_override(page: Page, harness):
    """After overriding tint locally, the row's Setting-row menu offers an
    enabled Reset item."""
    goto_ready(page, f"{harness}{_NODE_PATH}")
    page.wait_for_selector("[data-field]")

    row = page.locator('[data-field="tint"]')
    edit_input = row.locator("input").first
    edit_input.fill("#0000ff")
    edit_input.press("Tab")
    _expect_override(page, "tint", True)

    updated_row = page.locator('[data-field="tint"]')
    updated_row.locator(".sf-label").click(button="right")
    reset_item = page.locator('[data-row-menu] >> text="Reset to global default"')
    expect(reset_item).to_be_visible()
    assert "disabled" not in (reset_item.get_attribute("class") or "")


def test_color_mirror_reset_removes_dot_prefix(page: Page, harness):
    """Clicking the Reset menu item on tint removes the • prefix."""
    goto_ready(page, f"{harness}{_NODE_PATH}")
    page.wait_for_selector("[data-field]")

    row = page.locator('[data-field="tint"]')
    edit_input = row.locator("input").first
    edit_input.fill("#0000ff")
    edit_input.press("Tab")
    _expect_override(page, "tint", True)

    updated_row = page.locator('[data-field="tint"]')
    updated_row.locator(".sf-label").click(button="right")
    page.locator('[data-row-menu] >> text="Reset to global default"').click()
    _expect_override(page, "tint", False)

    final_row = page.locator('[data-field="tint"]')
    label_text = final_row.locator(".text-xs").first.inner_text()
    assert not label_text.startswith("•"), f"Expected no • after reset, got: {label_text!r}"
