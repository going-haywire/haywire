"""
Interaction tests: verify value write/read-back, mirror indicator (• prefix),
and the reset-to-global button.
"""

import pytest
from playwright.sync_api import Page, expect

_NODE_URL = (
    "http://localhost:8090/node?class=haybale_testing.nodes.testbed.settings_node.SettingsNode&bag=example"
)

pytestmark = pytest.mark.ui


def test_string_field_renders_with_default_data_value(page: Page, harness):
    """The example_string field renders with its default value in data-value."""
    page.goto(_NODE_URL)
    page.wait_for_selector("[data-field]")

    row = page.locator('[data-field="example_string"]')
    wrapper = row.locator("[data-value]")
    # Default value is "default string"
    expect(wrapper).to_have_attribute("data-value", "default string")


def test_float_field_renders_with_default_data_value(page: Page, harness):
    """The persistent_value NumberDrag field renders with its default value in data-value."""
    page.goto(_NODE_URL)
    page.wait_for_selector("[data-field]")

    row = page.locator('[data-field="persistent_value"]')
    nd = row.locator("[data-number_drag]")
    # Default value is 1.0
    expect(nd).to_have_attribute("data-value", "1.0")


def test_mirror_field_no_dot_prefix_initially(page: Page, harness):
    """The intensity mirror field label has no • prefix when not locally overridden."""
    page.goto(_NODE_URL)
    page.wait_for_selector("[data-field]")

    row = page.locator('[data-field="intensity"]')
    label_text = row.locator(".text-xs").first.inner_text()
    assert not label_text.startswith("•"), f"Expected no • prefix, got: {label_text!r}"


def test_mirror_field_dot_prefix_after_local_override(page: Page, harness):
    """Overriding the intensity mirror locally adds • to the label."""
    page.goto(_NODE_URL)
    page.wait_for_selector("[data-field]")

    row = page.locator('[data-field="intensity"]')
    # intensity is a mirror field rendered as a NumberDrag (float type)
    nd = row.locator("[data-number_drag]")
    nd.dblclick()
    edit_input = row.locator("input")
    edit_input.fill("0.3")
    edit_input.press("Enter")
    # Page re-renders the row after local override
    page.wait_for_timeout(600)

    updated_row = page.locator('[data-field="intensity"]')
    label_text = updated_row.locator(".text-xs").first.inner_text()
    assert label_text.startswith("•"), f"Expected • prefix after override, got: {label_text!r}"


def test_reset_button_appears_after_override(page: Page, harness):
    """After overriding intensity locally, the reset (restart_alt) button appears."""
    page.goto(_NODE_URL)
    page.wait_for_selector("[data-field]")

    row = page.locator('[data-field="intensity"]')
    # intensity is a mirror field rendered as a NumberDrag (float type)
    nd = row.locator("[data-number_drag]")
    nd.dblclick()
    edit_input = row.locator("input")
    edit_input.fill("0.3")
    edit_input.press("Enter")
    page.wait_for_timeout(600)

    updated_row = page.locator('[data-field="intensity"]')
    # NiceGUI renders Material icon buttons with the icon name as text content
    reset_btn = updated_row.locator('button:has-text("restart_alt")')
    expect(reset_btn).to_be_visible()


def test_reset_button_removes_dot_prefix(page: Page, harness):
    """Clicking the reset button on intensity removes the • prefix."""
    page.goto(_NODE_URL)
    page.wait_for_selector("[data-field]")

    # Override intensity via NumberDrag edit mode
    row = page.locator('[data-field="intensity"]')
    nd = row.locator("[data-number_drag]")
    nd.dblclick()
    edit_input = row.locator("input")
    edit_input.fill("0.2")
    edit_input.press("Enter")
    page.wait_for_timeout(600)

    # Click reset
    updated_row = page.locator('[data-field="intensity"]')
    reset_btn = updated_row.locator('button:has-text("restart_alt")')
    reset_btn.click()
    page.wait_for_timeout(600)

    # • prefix should be gone
    final_row = page.locator('[data-field="intensity"]')
    label_text = final_row.locator(".text-xs").first.inner_text()
    assert not label_text.startswith("•"), f"Expected no • after reset, got: {label_text!r}"


def test_color_mirror_dot_prefix_after_local_override(page: Page, harness):
    """Typing a color value into the tint mirror adds • to the label."""
    page.goto(_NODE_URL)
    page.wait_for_selector("[data-field]")

    row = page.locator('[data-field="tint"]')
    edit_input = row.locator("input").first
    edit_input.fill("#0000ff")
    edit_input.press("Tab")
    page.wait_for_timeout(600)

    updated_row = page.locator('[data-field="tint"]')
    label_text = updated_row.locator(".text-xs").first.inner_text()
    assert label_text.startswith("•"), f"Expected • prefix after color override, got: {label_text!r}"


def test_color_mirror_reset_button_appears_after_override(page: Page, harness):
    """After overriding tint locally, the reset button appears."""
    page.goto(_NODE_URL)
    page.wait_for_selector("[data-field]")

    row = page.locator('[data-field="tint"]')
    edit_input = row.locator("input").first
    edit_input.fill("#0000ff")
    edit_input.press("Tab")
    page.wait_for_timeout(600)

    updated_row = page.locator('[data-field="tint"]')
    expect(updated_row.locator('button:has-text("restart_alt")')).to_be_visible()


def test_color_mirror_reset_removes_dot_prefix(page: Page, harness):
    """Clicking reset on tint removes the • prefix."""
    page.goto(_NODE_URL)
    page.wait_for_selector("[data-field]")

    row = page.locator('[data-field="tint"]')
    edit_input = row.locator("input").first
    edit_input.fill("#0000ff")
    edit_input.press("Tab")
    page.wait_for_timeout(600)

    updated_row = page.locator('[data-field="tint"]')
    updated_row.locator('button:has-text("restart_alt")').click()
    page.wait_for_timeout(600)

    final_row = page.locator('[data-field="tint"]')
    label_text = final_row.locator(".text-xs").first.inner_text()
    assert not label_text.startswith("•"), f"Expected no • after reset, got: {label_text!r}"
