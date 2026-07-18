"""
Mirror propagation tests: verify that changing a global LibrarySetting via
/api/set propagates to the mirrored NodeSettings field on re-render.
"""

import pytest
import requests
from playwright.sync_api import Page, expect

from tests.ui.harness.nav import goto_ready

_NODE_URL = (
    "http://localhost:8090/node?class=haybale_testing.nodes.testbed.settings_node.SettingsNode&bag=example"
)
_BASE_URL = "http://localhost:8090"

pytestmark = pytest.mark.ui


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
    goto_ready(page, _NODE_URL)
    page.wait_for_selector("[data-field]")

    # NumberDrag self-emits data-value, so the mirrored value is DOM-readable.
    nd = page.locator('[data-field="intensity"] [data-number_drag]')
    expect(nd).to_have_attribute("data-value", "0.9")
