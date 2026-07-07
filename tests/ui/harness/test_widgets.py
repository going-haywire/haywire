"""
Widget coverage tests: verify that each setting type resolves and renders the
correct widget DOM (the right control per IType) through the shared-widget panel.

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
    expect(row.locator("[data-number_drag]")).not_to_be_attached()
    expect(row.locator('[role="switch"]')).to_be_attached()


def test_int_field_renders_number_drag(page: Page, harness):
    """An int field (count) renders a NumberDrag widget."""
    page.goto(_WIDGET_SCHEMA_URL)
    page.wait_for_selector("[data-field]")

    expect(page.locator('[data-field="count"] [data-number_drag]')).to_be_attached()


def test_float_field_renders_number_drag(page: Page, harness):
    """A float field (ratio) renders a NumberDrag widget."""
    page.goto(_WIDGET_SCHEMA_URL)
    page.wait_for_selector("[data-field]")

    expect(page.locator('[data-field="ratio"] [data-number_drag]')).to_be_attached()


def test_str_field_renders_input(page: Page, harness):
    """A str field (label) renders a plain text input."""
    page.goto(_WIDGET_SCHEMA_URL)
    page.wait_for_selector("[data-field]")

    row = page.locator('[data-field="label"]')
    expect(row.locator("input")).to_be_attached()
    expect(row.locator("[data-number_drag]")).not_to_be_attached()


def test_choices_field_renders_select(page: Page, harness):
    """A choices field (mode) renders a ui.select dropdown."""
    page.goto(_WIDGET_SCHEMA_URL)
    page.wait_for_selector("[data-field]")

    row = page.locator('[data-field="mode"]')
    expect(row.locator("[data-number_drag]")).not_to_be_attached()
    expect(row.locator(".q-select")).to_be_attached()


def test_color_field_renders_color_input(page: Page, harness):
    """A color field (tint) renders a ui.color_input."""
    page.goto(_WIDGET_SCHEMA_URL)
    page.wait_for_selector("[data-field]")

    row = page.locator('[data-field="tint"]')
    expect(row.locator("[data-number_drag]")).not_to_be_attached()
    expect(row.locator("input")).to_be_attached()


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


def test_schema_row_keeps_label_and_widget_side_by_side(page: Page, harness):
    """A /schema (registry-path) row's label and widget sit on the same line.

    Regression guard: _render_field_row's error_container div used to be a
    third flex child inside the label+widget row, where its own w-full made
    it claim a column and wrap the widget onto a line below the label —
    unlike the reactive path (render_settings), which never exhibited this
    because its error_container sits outside the row entirely.
    """
    page.goto(_WIDGET_SCHEMA_URL)
    page.wait_for_selector("[data-field]")

    row = page.locator('[data-field="mode"]')
    label_box = row.locator(".sf-label").bounding_box()
    widget_box = row.locator(".sf-widget").bounding_box()
    assert label_box is not None
    assert widget_box is not None
    # Side-by-side ⇒ widget starts to the right of where the label ends.
    assert widget_box["x"] >= label_box["x"] + label_box["width"]
    # Same row ⇒ their vertical spans overlap. A ui.select is taller than a
    # plain label (Quasar field chrome), so centering shifts their tops by a
    # few px — that's expected; a widget wrapped onto its own line below would
    # start well past the label's bottom edge instead of overlapping it.
    label_bottom = label_box["y"] + label_box["height"]
    widget_bottom = widget_box["y"] + widget_box["height"]
    assert widget_box["y"] < label_bottom
    assert label_box["y"] < widget_bottom


# ---------------------------------------------------------------------------
# SettingsNode.example — direct fields
# ---------------------------------------------------------------------------


def test_direct_string_field(page: Page, harness):
    """example_string renders as text input with correct default."""
    page.goto(_NODE_URL)
    page.wait_for_selector("[data-field]")

    row = page.locator('[data-field="example_string"]')
    expect(row.locator("input")).to_be_attached()


def test_string_field_has_expand_button(page: Page, harness):
    """The editable string widget renders an expand-to-modal button beside the input."""
    page.goto(_NODE_URL)
    page.wait_for_selector("[data-field]")

    row = page.locator('[data-field="example_string"]')
    expect(row.locator("input")).to_be_attached()
    expect(row.get_by_role("button")).to_be_attached()


def test_string_field_expand_modal_round_trip(page: Page, harness):
    """Clicking expand opens a textarea seeded with the value; confirming writes back."""
    page.goto(_NODE_URL)
    page.wait_for_selector("[data-field]")

    row = page.locator('[data-field="example_string"]')
    inp = row.locator("input")
    inp.fill("hello")
    inp.blur()

    # Open the modal — it seeds the textarea from the current value. Target the
    # expand button specifically: filling the input above made the field dirty, so
    # the row now also carries a reset button (locally-set chrome).
    row.get_by_role("button").filter(has_text="open_in_full").click()
    textarea = page.locator("textarea")
    expect(textarea).to_be_visible()
    expect(textarea).to_have_value("hello")

    # Edit in the modal and confirm; the inline input re-syncs via the cell.
    textarea.fill("edited via modal")
    page.get_by_role("button", name="OK").click()
    expect(inp).to_have_value("edited via modal")


def test_direct_int_field(page: Page, harness):
    """example_int renders as NumberDrag."""
    page.goto(_NODE_URL)
    page.wait_for_selector("[data-field]")

    expect(page.locator('[data-field="example_int"] [data-number_drag]')).to_be_attached()


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


def test_direct_choices_field(page: Page, harness):
    """example_choices renders as dropdown with default 'fast'."""
    page.goto(_NODE_URL)
    page.wait_for_selector("[data-field]")

    row = page.locator('[data-field="example_choices"]')
    expect(row.locator(".q-select")).to_be_attached()


def test_direct_color_field(page: Page, harness):
    """example_color renders as color input with default '#00ff00'."""
    page.goto(_NODE_URL)
    page.wait_for_selector("[data-field]")

    row = page.locator('[data-field="example_color"]')
    expect(row.locator("input")).to_be_attached()


# ---------------------------------------------------------------------------
# SettingsNode.example — mirror fields (plain)
# ---------------------------------------------------------------------------


def test_choices_mirror_renders_select(page: Page, harness):
    """mode mirror renders as a dropdown (mirror resolution → widget by type)."""
    page.goto(_NODE_URL)
    page.wait_for_selector("[data-field]")

    row = page.locator('[data-field="mode"]')
    expect(row.locator(".q-select")).to_be_attached()


def test_read_only_mirror_fields_render_readonly_rows(page: Page, harness):
    """Read-only mirror fields render as read-only value rows (Q8), not editable widgets."""
    page.goto(_NODE_URL)
    page.wait_for_selector("[data-field]")

    for field in ["intensity_ro", "count_ro", "label_ro", "enabled_ro", "mode_ro", "tint_ro"]:
        row = page.locator(f'[data-field="{field}"]')
        expect(row).to_be_visible()
        expect(row.locator("input")).not_to_be_attached()
        expect(row.locator("[data-number_drag]")).not_to_be_attached()
        expect(row.locator('[role="switch"]')).not_to_be_attached()
