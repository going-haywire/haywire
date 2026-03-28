"""
Widget coverage tests: verify that every widget branch in _render_widget_impl
renders the correct DOM and carries the correct initial data-value.

Uses two routes:
  /schema?class=haywire.core.di.test_config.TestingWidgetSettings
      — FrameworkSettings with one field per widget type (bool, int, float,
        str, choices, color)
  /node?class=...SettingsNode&bag=example
      — NodeSettings with plain and read-only mirror fields for each type
"""

import pytest
from playwright.sync_api import Page, expect

_WIDGET_SCHEMA_URL = "http://localhost:8090/schema?class=haywire.core.di.test_config.TestingWidgetSettings"
_NODE_URL = (
    "http://localhost:8090/node?class=haybale_testing.nodes.testbed.settings_node.SettingsNode&bag=example"
)
_TESTING_SCHEMA_URL = "http://localhost:8090/schema?class=haybale_testing.settings.testing.TestingSettings"

pytestmark = pytest.mark.ui


# ---------------------------------------------------------------------------
# TestingWidgetSettings — one field per widget branch
# ---------------------------------------------------------------------------


def test_bool_field_renders_switch(page: Page, harness):
    """A bool field renders a ui.switch (not a NumberDrag or input)."""
    page.goto(_WIDGET_SCHEMA_URL)
    page.wait_for_selector("[data-field]")

    row = page.locator('[data-field="flag"]')
    expect(row.locator("[data-value]")).to_be_attached()
    expect(row.locator("[data-number_drag]")).not_to_be_attached()
    expect(row.locator("input[type=text]")).not_to_be_attached()
    # ui.switch renders as a Quasar q-toggle/q-checkbox — no NumberDrag present
    expect(row.locator('[role="switch"]')).to_be_attached()


def test_bool_field_default_data_value(page: Page, harness):
    """Bool field data-value reflects the default (true)."""
    page.goto(_WIDGET_SCHEMA_URL)
    page.wait_for_selector("[data-field]")

    row = page.locator('[data-field="flag"]')
    wrapper = row.locator("[data-value]")
    expect(wrapper).to_have_attribute("data-value", "true")


def test_int_field_renders_number_drag(page: Page, harness):
    """An int field (count) renders a NumberDrag widget."""
    page.goto(_WIDGET_SCHEMA_URL)
    page.wait_for_selector("[data-field]")

    row = page.locator('[data-field="count"]')
    expect(row.locator("[data-number_drag]")).to_be_attached()


def test_int_field_default_data_value(page: Page, harness):
    """Int field data-value shows the default (3) with no decimal point."""
    page.goto(_WIDGET_SCHEMA_URL)
    page.wait_for_selector("[data-field]")

    nd = page.locator('[data-field="count"] [data-number_drag]')
    val = nd.get_attribute("data-value")
    assert val == "3", f"expected '3', got {val!r}"
    assert "." not in val, f"int field should have no decimal point, got {val!r}"


def test_float_field_renders_number_drag(page: Page, harness):
    """A float field (ratio) renders a NumberDrag widget."""
    page.goto(_WIDGET_SCHEMA_URL)
    page.wait_for_selector("[data-field]")

    row = page.locator('[data-field="ratio"]')
    expect(row.locator("[data-number_drag]")).to_be_attached()


def test_float_field_default_data_value(page: Page, harness):
    """Float field data-value shows the default (0.5)."""
    page.goto(_WIDGET_SCHEMA_URL)
    page.wait_for_selector("[data-field]")

    nd = page.locator('[data-field="ratio"] [data-number_drag]')
    expect(nd).to_have_attribute("data-value", "0.5")


def test_str_field_renders_input(page: Page, harness):
    """A str field (label) renders a plain text input."""
    page.goto(_WIDGET_SCHEMA_URL)
    page.wait_for_selector("[data-field]")

    row = page.locator('[data-field="label"]')
    expect(row.locator("input")).to_be_attached()
    expect(row.locator("[data-number_drag]")).not_to_be_attached()


def test_str_field_default_data_value(page: Page, harness):
    """Str field data-value shows the default ('hello')."""
    page.goto(_WIDGET_SCHEMA_URL)
    page.wait_for_selector("[data-field]")

    wrapper = page.locator('[data-field="label"] [data-value]')
    expect(wrapper).to_have_attribute("data-value", "hello")


def test_choices_field_renders_select(page: Page, harness):
    """A choices field (mode) renders a ui.select dropdown."""
    page.goto(_WIDGET_SCHEMA_URL)
    page.wait_for_selector("[data-field]")

    row = page.locator('[data-field="mode"]')
    expect(row.locator("[data-number_drag]")).not_to_be_attached()
    # Quasar select renders as a div with role=combobox or a .q-select element
    expect(row.locator(".q-select")).to_be_attached()


def test_choices_field_default_data_value(page: Page, harness):
    """Choices field data-value shows the default ('fast')."""
    page.goto(_WIDGET_SCHEMA_URL)
    page.wait_for_selector("[data-field]")

    wrapper = page.locator('[data-field="mode"] [data-value]')
    expect(wrapper).to_have_attribute("data-value", "fast")


def test_color_field_renders_color_input(page: Page, harness):
    """A color field (tint) renders a ui.color_input."""
    page.goto(_WIDGET_SCHEMA_URL)
    page.wait_for_selector("[data-field]")

    row = page.locator('[data-field="tint"]')
    expect(row.locator("[data-number_drag]")).not_to_be_attached()
    # NiceGUI color_input renders a text input with a color swatch button
    expect(row.locator("input")).to_be_attached()


def test_color_field_default_data_value(page: Page, harness):
    """Color field data-value shows the default ('#ff0000')."""
    page.goto(_WIDGET_SCHEMA_URL)
    page.wait_for_selector("[data-field]")

    wrapper = page.locator('[data-field="tint"] [data-value]')
    expect(wrapper).to_have_attribute("data-value", "#ff0000")


# ---------------------------------------------------------------------------
# TestingSettings schema — LibrarySettings with new fields
# ---------------------------------------------------------------------------


def test_testing_schema_bool_field_present(page: Page, harness):
    """TestingSettings.default_enabled renders in the /schema route."""
    page.goto(_TESTING_SCHEMA_URL)
    page.wait_for_selector("[data-field]")
    expect(page.locator('[data-field="default_enabled"]')).to_be_visible()


def test_testing_schema_choices_field_present(page: Page, harness):
    """TestingSettings.default_mode renders in the /schema route."""
    page.goto(_TESTING_SCHEMA_URL)
    page.wait_for_selector("[data-field]")
    expect(page.locator('[data-field="default_mode"]')).to_be_visible()


def test_testing_schema_color_field_present(page: Page, harness):
    """TestingSettings.default_color renders in the /schema route."""
    page.goto(_TESTING_SCHEMA_URL)
    page.wait_for_selector("[data-field]")
    expect(page.locator('[data-field="default_color"]')).to_be_visible()


# ---------------------------------------------------------------------------
# SettingsNode.example — mirror fields for each new type
# ---------------------------------------------------------------------------


def test_bool_mirror_field_present(page: Page, harness):
    """enabled mirror field renders in the node panel."""
    page.goto(_NODE_URL)
    page.wait_for_selector("[data-field]")
    expect(page.locator('[data-field="enabled"]')).to_be_visible()


def test_bool_mirror_shows_global_default(page: Page, harness):
    """enabled mirror shows the library default (true) when not locally overridden."""
    page.goto(_NODE_URL)
    page.wait_for_selector("[data-field]")

    wrapper = page.locator('[data-field="enabled"] [data-value]')
    expect(wrapper).to_have_attribute("data-value", "true")


def test_choices_mirror_field_present(page: Page, harness):
    """mode mirror field renders as a dropdown in the node panel."""
    page.goto(_NODE_URL)
    page.wait_for_selector("[data-field]")

    row = page.locator('[data-field="mode"]')
    expect(row).to_be_visible()
    expect(row.locator(".q-select")).to_be_attached()


def test_choices_mirror_shows_global_default(page: Page, harness):
    """mode mirror data-value shows the library default ('fast')."""
    page.goto(_NODE_URL)
    page.wait_for_selector("[data-field]")

    wrapper = page.locator('[data-field="mode"] [data-value]')
    expect(wrapper).to_have_attribute("data-value", "fast")


def test_color_mirror_field_present(page: Page, harness):
    """tint mirror field renders as a color input in the node panel."""
    page.goto(_NODE_URL)
    page.wait_for_selector("[data-field]")

    row = page.locator('[data-field="tint"]')
    expect(row).to_be_visible()
    expect(row.locator("input")).to_be_attached()


def test_color_mirror_shows_global_default(page: Page, harness):
    """tint mirror data-value shows the library default ('#ff0000')."""
    page.goto(_NODE_URL)
    page.wait_for_selector("[data-field]")

    wrapper = page.locator('[data-field="tint"] [data-value]')
    expect(wrapper).to_have_attribute("data-value", "#ff0000")


def test_read_only_mirror_fields_not_rendered(page: Page, harness):
    """Read-only mirror fields (intensity_ro, enabled_ro) do not appear in the panel."""
    page.goto(_NODE_URL)
    page.wait_for_selector("[data-field]")
    expect(page.locator('[data-field="intensity_ro"]')).not_to_be_attached()
    expect(page.locator('[data-field="enabled_ro"]')).not_to_be_attached()
