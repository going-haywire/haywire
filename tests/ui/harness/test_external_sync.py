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
