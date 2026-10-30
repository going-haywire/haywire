"""The path-fit script shows the longest rendering that fits its line, and chooses again on resize."""

from __future__ import annotations

from html import escape
from pathlib import PurePosixPath

import pytest
from playwright.sync_api import Page

from haywire.ui.elements.path_fit import _SCRIPT, FIT_ATTR, FIT_CLASS, PATH_FIT_CSS, crop_candidates

pytestmark = pytest.mark.browser

_PATH = PurePosixPath("/Volumes/Ddrive/06_open_tracking_tool/haywire/haywire-repo")
# Monospace keeps every width below well away from a candidate's own width (~7.2 px a character).
_LINE_STYLE = "font: 12px monospace; height: 16px"


def _page_with_lines(page: Page, widths: list[int]) -> None:
    candidates = "".join(f"<div>{escape(c)}</div>" for c in crop_candidates(_PATH))
    lines = "".join(
        f'<div id="w{w}" class="{FIT_CLASS}" style="{_LINE_STYLE}; width: {w}px">{candidates}</div>'
        for w in widths
    )
    page.set_content(f"<html><head><style>{PATH_FIT_CSS}</style></head><body>{lines}</body></html>")
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


def test_a_line_mounted_after_install_is_fitted_without_another_scan(page: Page) -> None:
    _page_with_lines(page, [600])
    _wait_fit(page, "w600", "0")
    # No second install: a panel mounting later must still be picked up, also nested in a wrapper.
    page.evaluate(
        "html => document.body.insertAdjacentHTML('beforeend', html)",
        '<section id="panel"><div id="late" class="'
        + FIT_CLASS
        + f'" style="{_LINE_STYLE}; width: 200px">'
        + "".join(f"<div>{escape(c)}</div>" for c in crop_candidates(_PATH))
        + "</div></section>",
    )
    _wait_fit(page, "late", "2")


def test_a_line_whose_renderings_are_replaced_chooses_again(page: Page) -> None:
    _page_with_lines(page, [200])
    _wait_fit(page, "w200", "2")
    # A new path at the same width: no resize, only the line's children change.
    page.evaluate(
        "() => { document.querySelector('#w200').replaceChildren("
        "Object.assign(document.createElement('div'), {textContent: '/short'})); }"
    )
    _wait_fit(page, "w200", "0")
