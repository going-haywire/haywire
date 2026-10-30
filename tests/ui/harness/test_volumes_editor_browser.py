"""The Volumes editor's rows are exactly as wide as their slot, and the location line crops to fit it."""

import pytest
from playwright.sync_api import Page

from tests.ui.harness.nav import goto_ready

pytestmark = pytest.mark.ui

_HOST = '[data-testid="volumes-host"]'
_LONG = "/Volumes/Ddrive/06_open_tracking_tool/haywire/haywire-repo"


def _geometry(page: Page) -> dict:
    return page.evaluate(
        """([host, long]) => {
            const box = document.querySelector(host).getBoundingClientRect();
            const rows = [...document.querySelectorAll(host + ' .hw-list-item-hover')];
            const row = rows.find(r => r.querySelector(`.hw-path-fit[title="${long}"]`));
            const b = row.querySelector('button').getBoundingClientRect();
            return {
                hostLeft: box.left, hostRight: box.right,
                rows: rows.map(r => {
                    const rb = r.getBoundingClientRect();
                    return {left: rb.left, right: rb.right, scroll: r.scrollWidth, client: r.clientWidth};
                }),
                buttonLeft: b.left, buttonRight: b.right, buttonWidth: b.width,
            };
        }""",
        [_HOST, _LONG],
    )


def _shown_location(page: Page) -> str:
    return page.evaluate(
        """long => {
            const line = [...document.querySelectorAll('.hw-path-fit')].find(l => l.title === long);
            return line.textContent;
        }""",
        _LONG,
    )


def test_rows_fit_a_narrow_slot_and_refit_when_it_widens(page: Page, harness) -> None:
    goto_ready(page, f"{harness}/volumes-editor?width=300")
    page.wait_for_function("() => document.querySelector('.hw-path-fit[data-hw-fit]') !== null")

    geo = _geometry(page)
    assert geo["rows"], "no rows rendered"
    for row in geo["rows"]:
        assert row["right"] <= geo["hostRight"] + 0.5, row
        assert row["scroll"] <= row["client"], row
    assert geo["buttonWidth"] > 0
    assert geo["hostLeft"] <= geo["buttonLeft"], geo
    assert geo["buttonRight"] <= geo["hostRight"] + 0.5, geo
    page.wait_for_function(
        "long => { const l = [...document.querySelectorAll('.hw-path-fit')].find(l => l.title === long);"
        " return l.getAttribute('data-hw-fit') === 'crop'; }",
        arg=_LONG,
    )
    assert _shown_location(page) != _LONG

    page.evaluate("host => { document.querySelector(host).style.width = '900px'; }", _HOST)
    page.wait_for_function(
        "long => { const l = [...document.querySelectorAll('.hw-path-fit')].find(l => l.title === long);"
        " return l.getAttribute('data-hw-fit') === 'full'; }",
        arg=_LONG,
    )
    assert _shown_location(page) == _LONG
