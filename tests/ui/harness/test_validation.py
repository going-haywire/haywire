"""
Validation tests: verify that invalid values surface a data-error DOM element.
"""

import pytest
from playwright.sync_api import Page, expect

_NODE_URL = (
    "http://localhost:8090/node?class=haybale_testing.nodes.testbed.settings_node.SettingsNode&bag=example"
)

pytestmark = pytest.mark.ui


def test_odd_integer_fails_validator(page: Page, harness):
    """Setting even_int to 3 (odd) produces a data-error element."""
    page.goto(_NODE_URL)
    page.wait_for_selector("[data-field]")

    row = page.locator('[data-field="even_int"]')
    nd = row.locator("[data-number_drag]")
    nd.dblclick()
    edit_input = row.locator("input")
    edit_input.fill("3")
    edit_input.press("Enter")
    page.wait_for_timeout(300)

    expect(page.locator('[data-error="true"]').first).to_be_visible()


def test_negative_clamped_positive_fails_validator(page: Page, harness):
    """Setting clamped_positive to -1 (negative) produces a data-error element."""
    page.goto(_NODE_URL)
    page.wait_for_selector("[data-field]")

    row = page.locator('[data-field="clamped_positive"]')
    nd = row.locator("[data-number_drag]")
    nd.dblclick()
    edit_input = row.locator("input")
    edit_input.fill("-1")
    edit_input.press("Enter")
    page.wait_for_timeout(300)

    expect(page.locator('[data-error="true"]').first).to_be_visible()


def test_valid_value_clears_error(page: Page, harness):
    """After fixing even_int to 4 (even), the data-error element disappears."""
    page.goto(_NODE_URL)
    page.wait_for_selector("[data-field]")

    # First produce an error
    row = page.locator('[data-field="even_int"]')
    nd = row.locator("[data-number_drag]")
    nd.dblclick()
    edit_input = row.locator("input")
    edit_input.fill("3")
    edit_input.press("Enter")
    page.wait_for_timeout(300)
    expect(page.locator('[data-error="true"]').first).to_be_visible()

    # Now fix it
    nd.dblclick()
    edit_input = row.locator("input")
    edit_input.fill("4")
    edit_input.press("Enter")
    page.wait_for_timeout(300)

    expect(page.locator('[data-error="true"]')).not_to_be_attached()


def test_float_exceeding_max_is_clamped(page: Page, harness):
    """example_float with max=1.0: setting 2.0 should be clamped to 1.0 by NumberDrag."""
    page.goto(_NODE_URL)
    page.wait_for_selector("[data-field]")

    row = page.locator('[data-field="example_float"]')
    nd = row.locator("[data-number_drag]")
    nd.dblclick()
    edit_input = row.locator("input")
    edit_input.fill("2.0")
    edit_input.press("Enter")
    page.wait_for_timeout(300)

    # NumberDrag clamps at max — data-value should be "1.0", not "2.0"
    val = nd.get_attribute("data-value")
    assert float(val) <= 1.0, f"Expected clamped value ≤ 1.0, got {val!r}"


def test_string_field_invalid_shows_quasar_error(page: Page, harness):
    """Emptying validated_string shows Quasar native inline error (ui.input validation=)."""
    page.goto(_NODE_URL)
    page.wait_for_selector("[data-field]")

    row = page.locator('[data-field="validated_string"]')
    edit_input = row.locator("input")
    edit_input.fill("")
    edit_input.press("Tab")
    page.wait_for_timeout(300)

    # Quasar renders two .q-field__messages divs during transitions; target the one with text
    expect(row.locator(".q-field__messages:has-text('Invalid value')")).to_be_visible()


def test_string_field_valid_clears_quasar_error(page: Page, harness):
    """Fixing validated_string after an error clears the Quasar inline error."""
    page.goto(_NODE_URL)
    page.wait_for_selector("[data-field]")

    row = page.locator('[data-field="validated_string"]')
    edit_input = row.locator("input")

    # Produce error
    edit_input.fill("")
    edit_input.press("Tab")
    page.wait_for_timeout(300)
    expect(row.locator(".q-field__messages:has-text('Invalid value')")).to_be_visible()

    # Fix it
    edit_input.fill("valid text")
    edit_input.press("Tab")
    page.wait_for_timeout(300)
    expect(row.locator(".q-field__messages:has-text('Invalid value')")).not_to_be_visible()
