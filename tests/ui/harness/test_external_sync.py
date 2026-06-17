"""
External-sync tests: a value changed on the Settings model from outside the
panel (another tab / worker / mirror) must update the rendered widget in place,
without a panel rebuild.
"""

import pytest
from playwright.sync_api import Page, expect

_LIVE_URL = (
    "http://localhost:8090/node-live"
    "?class=haybale_testing.nodes.testbed.settings_node.SettingsNode&bag=example"
)

pytestmark = pytest.mark.ui


def test_external_string_change_updates_widget(page: Page, harness):
    """setattr on the model (external write) updates the string field's data-value."""
    page.goto(_LIVE_URL)
    page.wait_for_selector("[data-field]")

    row = page.locator('[data-field="example_string"]')
    wrapper = row.locator("[data-value]")
    expect(wrapper).to_have_attribute("data-value", "default string")

    page.locator('[data-testid="ext-string"]').click()
    page.wait_for_timeout(300)

    expect(wrapper).to_have_attribute("data-value", "EXTERNAL")


def test_external_float_change_updates_numberdrag(page: Page, harness):
    """External setattr updates a NumberDrag float field's data-value."""
    page.goto(_LIVE_URL)
    page.wait_for_selector("[data-field]")

    nd = page.locator('[data-field="persistent_value"] [data-number_drag]')
    expect(nd).to_have_attribute("data-value", "1.0")

    page.locator('[data-testid="ext-float"]').click()
    page.wait_for_timeout(300)

    expect(nd).to_have_attribute("data-value", "9.0")


def test_external_bool_change_updates_switch(page: Page, harness):
    """External setattr updates a bool field's data-value wrapper."""
    page.goto(_LIVE_URL)
    page.wait_for_selector("[data-field]")

    wrapper = page.locator('[data-field="example_bool"] [data-value]')
    expect(wrapper).to_have_attribute("data-value", "false")

    page.locator('[data-testid="ext-bool"]').click()
    page.wait_for_timeout(300)

    expect(wrapper).to_have_attribute("data-value", "true")


def test_external_choice_change_updates_select(page: Page, harness):
    """External setattr updates a choices field's data-value wrapper."""
    page.goto(_LIVE_URL)
    page.wait_for_selector("[data-field]")

    wrapper = page.locator('[data-field="example_choices"] [data-value]')
    page.locator('[data-testid="ext-choice"]').click()
    page.wait_for_timeout(300)

    expect(wrapper).to_have_attribute("data-value", "quality")


def test_external_mirror_change_shows_dot_and_reset(page: Page, harness):
    """External local override of a mirror field adds • and reveals reset button."""
    page.goto(_LIVE_URL)
    page.wait_for_selector("[data-field]")

    row = page.locator('[data-field="intensity"]')
    label = row.locator(".text-xs").first
    assert not label.inner_text().startswith("•")

    page.locator('[data-testid="ext-mirror"]').click()
    page.wait_for_timeout(300)

    updated = page.locator('[data-field="intensity"]')
    assert updated.locator(".text-xs").first.inner_text().startswith("•")
    expect(updated.locator('button:has-text("restart_alt")')).to_be_visible()


def test_external_vec_change_updates_components(page: Page, harness):
    """External setattr on a vec field updates each component NumberDrag in place."""
    page.goto(_LIVE_URL)
    page.wait_for_selector("[data-field]")

    page.locator('[data-testid="ext-vec"]').click()
    page.wait_for_timeout(300)

    nds = page.locator('[data-field="example_vec3f"] [data-number_drag]')
    expect(nds.nth(0)).to_have_attribute("data-value", "4.0")
    expect(nds.nth(1)).to_have_attribute("data-value", "5.0")
    expect(nds.nth(2)).to_have_attribute("data-value", "6.0")


def test_vec_edit_after_external_change_preserves_other_components(page: Page, harness):
    """After an external vec write, editing one component keeps the others.

    Regression: _apply_vec must update the shared component list the per-component
    edit handlers close over, or a single-component edit reverts the others to
    stale values.
    """
    page.goto(_LIVE_URL)
    page.wait_for_selector("[data-field]")

    # External write: model -> (4, 5, 6)
    page.locator('[data-testid="ext-vec"]').click()
    page.wait_for_timeout(300)

    nds = page.locator('[data-field="example_vec3f"] [data-number_drag]')
    # Edit ONLY the X component to 9 via NumberDrag edit mode.
    nds.nth(0).dblclick()
    edit_input = page.locator('[data-field="example_vec3f"] input').first
    edit_input.fill("9")
    edit_input.press("Enter")
    page.wait_for_timeout(300)

    # Y and Z must still reflect the external write (5, 6), not the pre-write default (2, 3).
    nds_after = page.locator('[data-field="example_vec3f"] [data-number_drag]')
    expect(nds_after.nth(0)).to_have_attribute("data-value", "9.0")
    expect(nds_after.nth(1)).to_have_attribute("data-value", "5.0")
    expect(nds_after.nth(2)).to_have_attribute("data-value", "6.0")
