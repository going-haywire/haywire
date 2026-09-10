"""The settings-row "Promote to" flyout, in a real browser.

This CANNOT be covered in-process. A nested ``ui.menu`` that never opens, and an
anchor that greys itself, both render identically in the NiceGUI element tree —
``poll``/structure assertions pass straight through the breakage. Only a browser
shows it. See ``.insights/project_submenu_leaf_counting_traps.md``.

Two failure modes this pins down:

* **the greyed anchor** — a fully populated flyout that cannot be opened, with
  nothing in the DOM saying why beyond ``opacity: 0.4``;
* **the flyout that never opens** — hover does nothing, and the directions are
  unreachable.

Promotion entries are structural: they render only for a bag with an owning
node, which is why this uses ``/node-attached`` rather than ``/node``.
"""

import pytest
from playwright.sync_api import Page

from .nav import goto_ready

_URL = (
    "http://localhost:8090/node-attached"
    "?class=haybale_testing.nodes.testbed.settings_node.SettingsNode&bag=example"
)


def _open_row_menu(page: Page, field: str):
    goto_ready(page, _URL)
    row = page.locator(f'[data-field="{field}"]')
    row.locator(".sf-label").first.click(button="right")
    page.wait_for_selector(".q-menu")
    return row


def test_the_promote_anchor_is_not_greyed(page: Page, harness):
    """Regression: a submenu anchor whose body draws no counted leaf greys
    ITSELF retroactively — a menu you can see and cannot open."""
    _open_row_menu(page, "optional_int")
    anchor = page.locator('.q-menu .q-item:has-text("Promote to")').first

    assert anchor.is_visible()
    assert anchor.evaluate("e => getComputedStyle(e).opacity") == "1"
    assert "hw-disabled" not in (anchor.get_attribute("class") or "")


def test_hovering_the_anchor_opens_every_eligible_direction(page: Page, harness):
    _open_row_menu(page, "optional_int")
    page.locator('.q-menu .q-item:has-text("Promote to")').first.hover()

    for direction in ("inlet", "outlet", "config"):
        leaf = page.locator(f'.q-menu .q-item:has-text("{direction}")').last
        leaf.wait_for(state="visible", timeout=3000)


def test_promotion_nests_rather_than_flattening(page: Page, harness):
    """The top level carries ONE promotion entry, not one per direction."""
    _open_row_menu(page, "optional_int")
    # inner_text includes the Material icon's ligature name, so match on the
    # leading label rather than the whole string.
    items = [t.strip().splitlines()[0] for t in page.locator(".q-menu .q-item").all_inner_texts()]

    assert items.count("Promote to") == 1, f"expected one promotion entry: {items}"
    assert not [t for t in items if t.startswith("Promote to ")], (
        f"directions must live inside the flyout, not beside it: {items}"
    )


def test_an_absent_default_field_still_offers_set_to_none(page: Page, harness):
    """The reported trap, at the surface where it bit.

    "Set to none" was once hidden when the declared default was already absence,
    on the reasoning that Reset lands there anyway — but Reset greys while the
    field carries no local opinion, so that left no enabled route back at all.
    """
    _open_row_menu(page, "optional_int")
    texts = [t.strip() for t in page.locator(".q-menu .q-item").all_inner_texts()]
    assert "Set to none" in texts


@pytest.mark.parametrize("field", ["optional_int", "example_int"])
def test_reset_is_listed_for_every_row(page: Page, harness, field: str):
    """Listed permanently and greyed while clean — so the menu never renders
    empty and its shape does not shift with the current value."""
    _open_row_menu(page, field)
    texts = [t.strip() for t in page.locator(".q-menu .q-item").all_inner_texts()]
    assert "Reset to default" in texts
