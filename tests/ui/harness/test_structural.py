"""
Structural tests: verify that the correct fields, widget types, and category
headings render for SettingsNode.example and TestingSettings.
"""

import pytest
from playwright.sync_api import Page, expect

_NODE_URL = (
    "http://localhost:8090/node?class=haybale_testing.nodes.testbed.settings_node.SettingsNode&bag=example"
)
_SCHEMA_URL = "http://localhost:8090/schema?class=haybale_testing.settings.testing.TestingSettings"

pytestmark = pytest.mark.ui


def test_node_fields_present(page: Page, harness):
    """All non-read-only fields in SettingsNode.example appear as data-field rows."""
    page.goto(_NODE_URL)
    page.wait_for_selector("[data-field]")

    expected_fields = [
        "example_string",
        "example_float",
        "persistent_value",
        "transient_value",
        "intensity",
        "clamped_positive",
        "even_int",
    ]
    for field in expected_fields:
        expect(page.locator(f'[data-field="{field}"]')).to_be_visible()


def test_read_only_field_not_rendered(page: Page, harness):
    """read_only=True fields must NOT appear in the rendered panel."""
    page.goto(_NODE_URL)
    page.wait_for_selector("[data-field]")
    expect(page.locator('[data-field="read_only_value"]')).not_to_be_attached()


def test_float_field_uses_number_drag(page: Page, harness):
    """A float field (example_float) renders a NumberDrag widget (div[data-number_drag])."""
    page.goto(_NODE_URL)
    page.wait_for_selector("[data-field]")
    row = page.locator('[data-field="example_float"]')
    # NumberDrag Vue component renders as a div with the data-number_drag marker attribute
    expect(row.locator("[data-number_drag]")).to_be_attached()
    expect(row.locator("input[type=text]")).not_to_be_attached()


def test_string_field_uses_input(page: Page, harness):
    """A string field (example_string) renders a plain text input."""
    page.goto(_NODE_URL)
    page.wait_for_selector("[data-field]")
    row = page.locator('[data-field="example_string"]')
    expect(row.locator("input")).to_be_attached()
    expect(row.locator("[data-number_drag]")).not_to_be_attached()


def test_int_field_step_one(page: Page, harness):
    """An int field (even_int) renders a NumberDrag widget and displays an integer value."""
    page.goto(_NODE_URL)
    page.wait_for_selector("[data-field]")
    row = page.locator('[data-field="even_int"]')
    nd = row.locator("[data-number_drag]")
    expect(nd).to_be_attached()
    # data-value for an integer field should not contain a decimal point (e.g. "4" not "4.0")
    data_value = nd.get_attribute("data-value")
    assert data_value is not None, "expected data-value attribute on NumberDrag"
    assert "." not in data_value, f"expected integer data-value (no dot), got {data_value!r}"


def test_category_headings_present(page: Page, harness):
    """Category expansion headings Type, Stored, Mirrors, Validator are all visible."""
    page.goto(_NODE_URL)
    page.wait_for_selector("[data-field]")
    for heading in ["Type", "Stored", "Mirrors", "Validator"]:
        expect(page.get_by_text(heading, exact=True).first).to_be_visible()


def test_schema_field_present(page: Page, harness):
    """TestingSettings.default_intensity field row appears in /schema route."""
    page.goto(_SCHEMA_URL)
    page.wait_for_selector("[data-field]")
    expect(page.locator('[data-field="default_intensity"]')).to_be_visible()
