"""The path-fit script shows the longest rendering that fits its line, and chooses again on resize."""

from __future__ import annotations

from html import escape
from pathlib import PurePosixPath

import pytest
from haybale_studio.editors.path_fit import FIT_ATTR, FIT_CLASS, _SCRIPT, crop_candidates
from playwright.sync_api import Page

pytestmark = pytest.mark.browser

_PATH = PurePosixPath("/Volumes/Ddrive/06_open_tracking_tool/haywire/haywire-repo")
# Monospace keeps every width below well away from a candidate's own width (~7.2 px a character).
_LINE_STYLE = "position: relative; overflow: hidden; white-space: nowrap; font: 12px monospace; height: 16px"


def _page_with_lines(page: Page, widths: list[int]) -> None:
    candidates = "".join(f"<div>{escape(c)}</div>" for c in crop_candidates(_PATH))
    lines = "".join(
        f'<div id="w{w}" class="{FIT_CLASS}" style="{_LINE_STYLE}; width: {w}px">{candidates}</div>'
        for w in widths
    )
    page.set_content(f"<html><body>{lines}</body></html>")
    page.evaluate(_SCRIPT)


def _fit(page: Page, line_id: str) -> str | None:
    return page.get_attribute(f"#{line_id}", FIT_ATTR)


def _wait_fit(page: Page, line_id: str, value: str) -> None:
    page.wait_for_function(
        f"() => document.querySelector('#{line_id}').getAttribute('{FIT_ATTR}') === '{value}'"
    )


def test_each_line_shows_the_longest_rendering_that_fits(page: Page) -> None:
    _page_with_lines(page, [600, 330, 200, 140, 50])
    for line_id, index in [("w600", "0"), ("w330", "1"), ("w200", "2"), ("w140", "4"), ("w50", "4")]:
        _wait_fit(page, line_id, index)
    visible = page.evaluate(
        "() => [...document.querySelectorAll('#w330 > div')]"
        ".filter(d => getComputedStyle(d).visibility === 'visible').map(d => d.textContent)"
    )
    assert visible == ["/Volumes/Ddrive/../haywire/haywire-repo"]


def test_a_resized_line_chooses_again(page: Page) -> None:
    _page_with_lines(page, [600])
    _wait_fit(page, "w600", "0")
    page.evaluate("() => { document.querySelector('#w600').style.width = '200px'; }")
    _wait_fit(page, "w600", "2")
    page.evaluate("() => { document.querySelector('#w600').style.width = '600px'; }")
    _wait_fit(page, "w600", "0")


def test_a_second_install_fits_lines_added_since(page: Page) -> None:
    _page_with_lines(page, [600])
    _wait_fit(page, "w600", "0")
    page.evaluate(
        "html => document.body.insertAdjacentHTML('beforeend', html)",
        f'<div id="late" class="{FIT_CLASS}" style="{_LINE_STYLE}; width: 200px">'
        + "".join(f"<div>{escape(c)}</div>" for c in crop_candidates(_PATH))
        + "</div>",
    )
    page.evaluate(_SCRIPT)
    _wait_fit(page, "late", "2")
    assert _fit(page, "w600") == "0"
