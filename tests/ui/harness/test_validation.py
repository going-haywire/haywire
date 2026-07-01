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


def test_string_field_invalid_shows_error(page: Page, harness):
    """Emptying validated_string surfaces the panel's data-error element.

    (Validation display is now uniform across widget types via the panel's
    error container, not the string widget's own Quasar inline message.)
    """
    page.goto(_NODE_URL)
    page.wait_for_selector("[data-field]")

    row = page.locator('[data-field="validated_string"]')
    edit_input = row.locator("input")
    edit_input.click()
    edit_input.fill("")
    edit_input.press("Enter")
    page.wait_for_timeout(300)

    expect(page.locator('[data-error="true"]').first).to_be_visible()


def test_string_field_valid_clears_error(page: Page, harness):
    """Fixing validated_string after an error clears the panel's data-error element."""
    page.goto(_NODE_URL)
    page.wait_for_selector("[data-field]")

    row = page.locator('[data-field="validated_string"]')
    edit_input = row.locator("input")

    # Produce error
    edit_input.click()
    edit_input.fill("")
    edit_input.press("Enter")
    page.wait_for_timeout(300)
    expect(page.locator('[data-error="true"]').first).to_be_visible()

    # Fix it
    edit_input.click()
    edit_input.fill("valid text")
    edit_input.press("Enter")
    page.wait_for_timeout(300)
    expect(page.locator('[data-error="true"]')).not_to_be_attached()
