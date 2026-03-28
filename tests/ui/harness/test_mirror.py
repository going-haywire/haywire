"""
Mirror propagation tests: verify that changing a global LibrarySetting via
/api/set propagates to the mirrored NodeSettings field on re-render.
"""

import pytest
import requests
from playwright.sync_api import Page, expect

_NODE_URL = (
    "http://localhost:8090/node?class=haybale_testing.nodes.testbed.settings_node.SettingsNode&bag=example"
)
_BASE_URL = "http://localhost:8090"

pytestmark = pytest.mark.ui


def test_intensity_mirror_shows_default_value(page: Page, harness, reset_setting):
    """intensity field shows the library default (0.5) when not locally overridden."""
    reset_setting("testing.default_intensity", 0.5)

    # Ensure default is set
    requests.post(f"{_BASE_URL}/api/set", params={"key": "testing.default_intensity", "value": "0.5"})

    page.goto(_NODE_URL)
    page.wait_for_selector("[data-field]")

    row = page.locator('[data-field="intensity"]')
    nd = row.locator("[data-number_drag]")
    expect(nd).to_have_attribute("data-value", "0.5")


def test_global_setting_change_propagates_to_mirror(page: Page, harness, reset_setting):
    """Changing testing.default_intensity to 0.9 and re-navigating shows 0.9 in intensity."""
    reset_setting("testing.default_intensity", 0.5)

    # Change global default
    r = requests.post(
        f"{_BASE_URL}/api/set",
        params={"key": "testing.default_intensity", "value": "0.9"},
    )
    assert r.json()["ok"] is True

    # Re-navigate to get a fresh render with the new global value
    page.goto(_NODE_URL)
    page.wait_for_selector("[data-field]")

    row = page.locator('[data-field="intensity"]')
    nd = row.locator("[data-number_drag]")
    expect(nd).to_have_attribute("data-value", "0.9")


def test_schema_page_shows_library_default(page: Page, harness, reset_setting):
    """TestingSettings schema page renders default_intensity with its current value."""
    reset_setting("testing.default_intensity", 0.5)

    requests.post(f"{_BASE_URL}/api/set", params={"key": "testing.default_intensity", "value": "0.5"})

    page.goto("http://localhost:8090/schema?class=haybale_testing.settings.testing.TestingSettings")
    page.wait_for_selector("[data-field]")

    row = page.locator('[data-field="default_intensity"]')
    nd = row.locator("[data-number_drag]")
    expect(nd).to_have_attribute("data-value", "0.5")


def test_schema_page_reflects_api_set_change(page: Page, harness, reset_setting):
    """After /api/set changes default_intensity to 0.7, schema page shows 0.7."""
    reset_setting("testing.default_intensity", 0.5)

    requests.post(f"{_BASE_URL}/api/set", params={"key": "testing.default_intensity", "value": "0.7"})

    page.goto("http://localhost:8090/schema?class=haybale_testing.settings.testing.TestingSettings")
    page.wait_for_selector("[data-field]")

    row = page.locator('[data-field="default_intensity"]')
    nd = row.locator("[data-number_drag]")
    expect(nd).to_have_attribute("data-value", "0.7")
