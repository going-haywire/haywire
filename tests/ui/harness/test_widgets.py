"""
Widget coverage tests: verify that every widget branch in _render_widget_impl
renders the correct DOM and carries the correct initial data-value.

Full matrix for SettingsNode.example:
  type     | direct          | mirror       | mirror + read_only
  ---------|-----------------|--------------|-------------------
  float    | example_float   | intensity    | intensity_ro
  int      | example_int     | count_mirror | count_ro
  str      | example_string  | label_mirror | label_ro
  bool     | example_bool    | enabled      | enabled_ro
  choices  | example_choices | mode         | mode_ro
  color    | example_color   | tint         | tint_ro

Uses two routes:
  /schema?class=haywire.core.di.test_config.TestingWidgetSettings
      — FrameworkSettings with one field per widget type
  /node?class=...SettingsNode&bag=example
      — NodeSettings covering the full matrix above
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
    """A bool field renders a ui.switch (not a NumberDrag or text input)."""
    page.goto(_WIDGET_SCHEMA_URL)
    page.wait_for_selector("[data-field]")

    row = page.locator('[data-field="flag"]')
    expect(row.locator("[data-value]")).to_be_attached()
    expect(row.locator("[data-number_drag]")).not_to_be_attached()
    expect(row.locator('[role="switch"]')).to_be_attached()


def test_bool_field_default_data_value(page: Page, harness):
    """Bool field data-value reflects the default (true)."""
    page.goto(_WIDGET_SCHEMA_URL)
    page.wait_for_selector("[data-field]")

    expect(page.locator('[data-field="flag"] [data-value]')).to_have_attribute("data-value", "true")


def test_int_field_renders_number_drag(page: Page, harness):
    """An int field (count) renders a NumberDrag widget."""
    page.goto(_WIDGET_SCHEMA_URL)
    page.wait_for_selector("[data-field]")

    expect(page.locator('[data-field="count"] [data-number_drag]')).to_be_attached()


def test_int_field_default_data_value(page: Page, harness):
    """Int field data-value shows the default (3) with no decimal point."""
    page.goto(_WIDGET_SCHEMA_URL)
    page.wait_for_selector("[data-field]")

    val = page.locator('[data-field="count"] [data-number_drag]').get_attribute("data-value")
    assert val == "3", f"expected '3', got {val!r}"
    assert "." not in val, f"int field should have no decimal point, got {val!r}"


def test_float_field_renders_number_drag(page: Page, harness):
    """A float field (ratio) renders a NumberDrag widget."""
    page.goto(_WIDGET_SCHEMA_URL)
    page.wait_for_selector("[data-field]")

    expect(page.locator('[data-field="ratio"] [data-number_drag]')).to_be_attached()


def test_float_field_default_data_value(page: Page, harness):
    """Float field data-value shows the default (0.5)."""
    page.goto(_WIDGET_SCHEMA_URL)
    page.wait_for_selector("[data-field]")

    expect(page.locator('[data-field="ratio"] [data-number_drag]')).to_have_attribute("data-value", "0.5")


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

    expect(page.locator('[data-field="label"] [data-value]')).to_have_attribute("data-value", "hello")


def test_choices_field_renders_select(page: Page, harness):
    """A choices field (mode) renders a ui.select dropdown."""
    page.goto(_WIDGET_SCHEMA_URL)
    page.wait_for_selector("[data-field]")

    row = page.locator('[data-field="mode"]')
    expect(row.locator("[data-number_drag]")).not_to_be_attached()
    expect(row.locator(".q-select")).to_be_attached()


def test_choices_field_default_data_value(page: Page, harness):
    """Choices field data-value shows the default ('fast')."""
    page.goto(_WIDGET_SCHEMA_URL)
    page.wait_for_selector("[data-field]")

    expect(page.locator('[data-field="mode"] [data-value]')).to_have_attribute("data-value", "fast")


def test_color_field_renders_color_input(page: Page, harness):
    """A color field (tint) renders a ui.color_input."""
    page.goto(_WIDGET_SCHEMA_URL)
    page.wait_for_selector("[data-field]")

    row = page.locator('[data-field="tint"]')
    expect(row.locator("[data-number_drag]")).not_to_be_attached()
    expect(row.locator("input")).to_be_attached()


def test_color_field_default_data_value(page: Page, harness):
    """Color field data-value shows the default ('#ff0000')."""
    page.goto(_WIDGET_SCHEMA_URL)
    page.wait_for_selector("[data-field]")

    expect(page.locator('[data-field="tint"] [data-value]')).to_have_attribute("data-value", "#ff0000")


# ---------------------------------------------------------------------------
# TestingSettings schema — all fields present
# ---------------------------------------------------------------------------


def test_testing_schema_all_fields_present(page: Page, harness):
    """All TestingSettings fields render in the /schema route."""
    page.goto(_TESTING_SCHEMA_URL)
    page.wait_for_selector("[data-field]")

    for field in [
        "default_intensity",
        "default_count",
        "default_label",
        "default_enabled",
        "default_mode",
        "default_color",
    ]:
        expect(page.locator(f'[data-field="{field}"]')).to_be_visible()


# ---------------------------------------------------------------------------
# SettingsNode.example — direct fields
# ---------------------------------------------------------------------------


def test_direct_string_field(page: Page, harness):
    """example_string renders as text input with correct default."""
    page.goto(_NODE_URL)
    page.wait_for_selector("[data-field]")

    row = page.locator('[data-field="example_string"]')
    expect(row.locator("input")).to_be_attached()
    expect(row.locator("[data-value]")).to_have_attribute("data-value", "default string")


def test_direct_int_field(page: Page, harness):
    """example_int renders as NumberDrag with correct default."""
    page.goto(_NODE_URL)
    page.wait_for_selector("[data-field]")

    nd = page.locator('[data-field="example_int"] [data-number_drag]')
    expect(nd).to_be_attached()
    val = nd.get_attribute("data-value")
    assert val == "3", f"expected '3', got {val!r}"
    assert "." not in val


def test_direct_float_field(page: Page, harness):
    """example_float renders as NumberDrag."""
    page.goto(_NODE_URL)
    page.wait_for_selector("[data-field]")

    expect(page.locator('[data-field="example_float"] [data-number_drag]')).to_be_attached()


def test_direct_bool_field(page: Page, harness):
    """example_bool renders as switch with default false."""
    page.goto(_NODE_URL)
    page.wait_for_selector("[data-field]")

    row = page.locator('[data-field="example_bool"]')
    expect(row.locator('[role="switch"]')).to_be_attached()
    expect(row.locator("[data-value]")).to_have_attribute("data-value", "false")


def test_direct_choices_field(page: Page, harness):
    """example_choices renders as dropdown with default 'fast'."""
    page.goto(_NODE_URL)
    page.wait_for_selector("[data-field]")

    row = page.locator('[data-field="example_choices"]')
    expect(row.locator(".q-select")).to_be_attached()
    expect(row.locator("[data-value]")).to_have_attribute("data-value", "fast")


def test_direct_color_field(page: Page, harness):
    """example_color renders as color input with default '#00ff00'."""
    page.goto(_NODE_URL)
    page.wait_for_selector("[data-field]")

    row = page.locator('[data-field="example_color"]')
    expect(row.locator("input")).to_be_attached()
    expect(row.locator("[data-value]")).to_have_attribute("data-value", "#00ff00")


# ---------------------------------------------------------------------------
# SettingsNode.example — mirror fields (plain)
# ---------------------------------------------------------------------------


def test_float_mirror_shows_global_default(page: Page, harness):
    """intensity mirror shows the library default (0.5)."""
    page.goto(_NODE_URL)
    page.wait_for_selector("[data-field]")

    expect(page.locator('[data-field="intensity"] [data-number_drag]')).to_have_attribute(
        "data-value", "0.5"
    )


def test_int_mirror_shows_global_default(page: Page, harness):
    """count_mirror shows the library default (7)."""
    page.goto(_NODE_URL)
    page.wait_for_selector("[data-field]")

    val = page.locator('[data-field="count_mirror"] [data-number_drag]').get_attribute("data-value")
    assert val == "7", f"expected '7', got {val!r}"


def test_str_mirror_shows_global_default(page: Page, harness):
    """label_mirror shows the library default ('default label')."""
    page.goto(_NODE_URL)
    page.wait_for_selector("[data-field]")

    expect(page.locator('[data-field="label_mirror"] [data-value]')).to_have_attribute(
        "data-value", "default label"
    )


def test_bool_mirror_shows_global_default(page: Page, harness):
    """enabled mirror shows the library default (true)."""
    page.goto(_NODE_URL)
    page.wait_for_selector("[data-field]")

    expect(page.locator('[data-field="enabled"] [data-value]')).to_have_attribute("data-value", "true")


def test_choices_mirror_shows_global_default(page: Page, harness):
    """mode mirror renders as dropdown and shows the library default ('fast')."""
    page.goto(_NODE_URL)
    page.wait_for_selector("[data-field]")

    row = page.locator('[data-field="mode"]')
    expect(row.locator(".q-select")).to_be_attached()
    expect(row.locator("[data-value]")).to_have_attribute("data-value", "fast")


def test_color_mirror_shows_global_default(page: Page, harness):
    """tint mirror shows the library default ('#ff0000')."""
    page.goto(_NODE_URL)
    page.wait_for_selector("[data-field]")

    expect(page.locator('[data-field="tint"] [data-value]')).to_have_attribute("data-value", "#ff0000")


# ---------------------------------------------------------------------------
# SettingsNode.example — read-only mirror fields not rendered
# ---------------------------------------------------------------------------


def test_read_only_mirror_fields_not_rendered(page: Page, harness):
    """All read-only mirror fields are absent from the rendered panel."""
    page.goto(_NODE_URL)
    page.wait_for_selector("[data-field]")

    for field in ["intensity_ro", "count_ro", "label_ro", "enabled_ro", "mode_ro", "tint_ro"]:
        expect(page.locator(f'[data-field="{field}"]')).not_to_be_attached()
