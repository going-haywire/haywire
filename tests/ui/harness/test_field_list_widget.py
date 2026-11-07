"""The FIELD_LIST widget, driven through a real browser."""

import pytest
from playwright.sync_api import Page, expect

from tests.ui.harness.nav import goto_ready

_PATH = "/field-list-widget"

pytestmark = pytest.mark.ui


def _echo(page: Page):
    return page.locator('[data-testid="echo-fields"]')


def _key(page: Page):
    return page.locator("[data-field-key] input, input[data-field-key]").first


def _add(page: Page):
    return page.locator("[data-field-add]")


def test_adding_a_field_writes_it_to_the_model(page: Page, harness: str) -> None:
    goto_ready(page, f"{harness}{_PATH}")
    _key(page).fill("camera_t")
    expect(_add(page)).to_be_enabled()
    _add(page).click()
    expect(_echo(page)).to_have_text("first,camera_t")
    expect(page.locator('[data-field-remove="camera_t"]')).to_be_visible()
    expect(_key(page)).to_have_value("")


def test_removing_a_field_writes_it_to_the_model(page: Page, harness: str) -> None:
    goto_ready(page, f"{harness}{_PATH}")
    page.locator('[data-field-remove="first"]').click()
    expect(_echo(page)).to_have_text("")
    expect(page.locator('[data-field-remove="first"]')).to_have_count(0)


@pytest.mark.parametrize("key", ["a b", "a:b", "é", ""])
def test_a_bad_key_cannot_be_added(page: Page, harness: str, key: str) -> None:
    goto_ready(page, f"{harness}{_PATH}")
    _key(page).fill(key)
    expect(_add(page)).to_be_disabled()
    expect(_echo(page)).to_have_text("first")


def test_a_bad_key_says_why(page: Page, harness: str) -> None:
    goto_ready(page, f"{harness}{_PATH}")
    _key(page).fill("a b")
    expect(page.get_by_text("Letters, digits and _ only")).to_be_visible()


def test_a_duplicate_key_cannot_be_added(page: Page, harness: str) -> None:
    goto_ready(page, f"{harness}{_PATH}")
    _key(page).fill("first")
    expect(_add(page)).to_be_disabled()
    expect(_echo(page)).to_have_text("first")


def test_a_type_option_shows_the_hover_tip_with_class_library_and_description(
    page: Page, harness: str
) -> None:
    goto_ready(page, f"{harness}{_PATH}")
    page.locator("[data-field-type]").click()
    page.locator(".q-menu .q-item", has_text="Boolean").first.hover()
    tip = page.locator(".hw-hover-tip")
    expect(tip).to_be_visible()
    expect(tip).to_contain_text("Boolean: BOOL")
    expect(tip).to_contain_text("True or False")
    expect(tip).to_contain_text("Library: haywire-core")
    expect(page.locator(".q-menu .q-tooltip")).to_have_count(0)


def test_a_field_gets_the_type_picked_from_the_list(page: Page, harness: str) -> None:
    goto_ready(page, f"{harness}{_PATH}")
    page.locator("[data-field-type]").click()
    page.locator(".q-menu .q-item", has_text="Boolean").first.click()
    _key(page).fill("flag")
    _add(page).click()
    expect(page.locator('[data-field-remove="flag"]')).to_be_visible()
    expect(page.locator('[data-field="fields"]')).to_contain_text("Boolean")


def test_the_row_fits_a_narrow_panel(page: Page, harness: str) -> None:
    goto_ready(page, f"{harness}{_PATH}")
    add = _add(page).bounding_box()
    box = page.locator('[data-field="fields"]').bounding_box()
    assert add is not None
    assert box is not None
    assert add["x"] + add["width"] <= box["x"] + box["width"] + 1
