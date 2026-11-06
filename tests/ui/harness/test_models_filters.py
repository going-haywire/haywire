"""Browser regression for the Models editor's filter section: a real menu, real dropdowns."""

import re

import pytest
from playwright.sync_api import Page, expect

from tests.ui.harness.nav import goto_ready

pytestmark = pytest.mark.ui


def _toggle_section(page: Page) -> None:
    page.locator(".q-btn", has_text="filter_alt").click()


def _add(page: Page, label: str) -> None:
    page.locator(".q-btn", has_text=re.compile("^add$")).click()
    page.locator(".q-menu").get_by_text(label, exact=True).click()


def test_plus_adds_a_field_and_its_dropdown_stays_open_between_picks(page: Page, harness: str) -> None:
    goto_ready(page, f"{harness}/models-filters")
    aaa, bbb = page.get_by_text("Aaa", exact=True), page.get_by_text("Bbb", exact=True)
    expect(aaa).to_be_visible()
    expect(page.locator(".q-select")).to_have_count(0)

    _toggle_section(page)
    expect(page.locator(".q-select")).to_have_count(0)
    _add(page, "Tags")
    page.locator(".q-select").click()
    page.locator(".q-menu .q-item", has_text="anime").click()
    expect(bbb).to_have_count(0)
    # A rebuilt select would have closed this dropdown after the first pick.
    page.locator(".q-menu .q-item", has_text="photo").click()
    expect(bbb).to_be_visible()
    expect(page.locator(".q-select .q-chip")).to_have_count(2)


def test_closing_switches_filters_off_and_reopening_restores_them(page: Page, harness: str) -> None:
    goto_ready(page, f"{harness}/models-filters")
    bbb = page.get_by_text("Bbb", exact=True)
    _toggle_section(page)
    _add(page, "Tags")
    page.locator(".q-select").click()
    page.locator(".q-menu .q-item", has_text="anime").click()
    expect(bbb).to_have_count(0)
    page.keyboard.press("Escape")
    page.locator(".q-btn", has_text="search").click()
    page.get_by_placeholder("Search models…").fill("aaa")

    _toggle_section(page)
    expect(page.locator(".q-select")).to_have_count(0)
    expect(bbb).to_be_visible()

    _toggle_section(page)
    expect(page.locator(".q-select .q-chip", has_text="anime")).to_be_visible()
    expect(page.get_by_placeholder("Search models…")).to_have_value("aaa")
    expect(bbb).to_have_count(0)


def test_a_selected_filter_chip_stands_out_and_keeps_its_width(page: Page, harness: str) -> None:
    goto_ready(page, f"{harness}/filter-chip")
    chip = page.locator(".q-chip", has_text="probe")
    style = "e => [getComputedStyle(e).backgroundColor, e.getBoundingClientRect().width]"
    rest = chip.evaluate(style)
    chip.click()
    expect(chip).to_have_class(re.compile("q-chip--selected"))
    picked = chip.evaluate(style)
    assert picked[0] != rest[0]
    assert picked[1] == rest[1]
