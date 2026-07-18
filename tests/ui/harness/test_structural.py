"""
Structural tests: verify that the correct fields, widget types, and category
headings render for SettingsNode.example and TestingSettings.
"""

import pytest
from playwright.sync_api import Page, expect

from tests.ui.harness.nav import goto_ready

_NODE_URL = (
    "http://localhost:8090/node?class=haybale_testing.nodes.testbed.settings_node.SettingsNode&bag=example"
)
_SCHEMA_URL = "http://localhost:8090/schema?class=haybale_testing.settings.testing.TestingSettings"

pytestmark = pytest.mark.ui


def test_node_fields_present(page: Page, harness):
    """All non-mirror fields in SettingsNode.example appear as data-field rows."""
    goto_ready(page, _NODE_URL)
    page.wait_for_selector("[data-field]")

    expected_fields = [
        # direct fields
        "example_string",
        "example_int",
        "example_float",
        "example_bool",
        "example_choices",
        "example_color",
        # stored
        "persistent_value",
        # mirrors
        "intensity",
        "count_mirror",
        "label_mirror",
        "enabled",
        "mode",
        "tint",
        # validators
        "validated_string",
        "clamped_positive",
        "even_int",
    ]
    for field in expected_fields:
        expect(page.locator(f'[data-field="{field}"]')).to_be_visible()


def test_watch_field_renders_disabled_widget(page: Page, harness):
    """watch() fields render a real (disabled) widget now — ui_state=DISABLED
    is the general chrome mechanism, not a bespoke label-only path."""
    goto_ready(page, _NODE_URL)
    page.wait_for_selector("[data-field]")
    row = page.locator('[data-field="intensity_ro"]')
    expect(row).to_be_visible()
    expect(row).to_have_attribute("data-ui-state", "disabled")
    expect(row.locator("[data-number_drag]")).to_be_attached()


def test_float_field_uses_number_drag(page: Page, harness):
    """A float field (example_float) renders a NumberDrag widget (div[data-number_drag])."""
    goto_ready(page, _NODE_URL)
    page.wait_for_selector("[data-field]")
    row = page.locator('[data-field="example_float"]')
    # NumberDrag Vue component renders as a div with the data-number_drag marker attribute
    expect(row.locator("[data-number_drag]")).to_be_attached()
    expect(row.locator("input[type=text]")).not_to_be_attached()


def test_string_field_uses_input(page: Page, harness):
    """A string field (example_string) renders a plain text input."""
    goto_ready(page, _NODE_URL)
    page.wait_for_selector("[data-field]")
    row = page.locator('[data-field="example_string"]')
    expect(row.locator("input")).to_be_attached()
    expect(row.locator("[data-number_drag]")).not_to_be_attached()


def test_int_field_uses_number_drag(page: Page, harness):
    """An int field (even_int) renders a NumberDrag widget (not a text input)."""
    goto_ready(page, _NODE_URL)
    page.wait_for_selector("[data-field]")
    row = page.locator('[data-field="even_int"]')
    expect(row.locator("[data-number_drag]")).to_be_attached()
    expect(row.locator("input[type=text]")).not_to_be_attached()


def test_category_headings_present(page: Page, harness):
    """Category expansion headings Type, Stored, Mirrors, Validator are all visible."""
    goto_ready(page, _NODE_URL)
    page.wait_for_selector("[data-field]")
    for heading in ["Type", "Stored", "Mirrors", "Validator"]:
        expect(page.get_by_text(heading, exact=True).first).to_be_visible()


def test_schema_field_present(page: Page, harness):
    """TestingSettings.default_intensity field row appears in /schema route."""
    goto_ready(page, _SCHEMA_URL)
    page.wait_for_selector("[data-field]")
    expect(page.locator('[data-field="default_intensity"]')).to_be_visible()
