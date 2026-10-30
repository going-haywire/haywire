"""An editor header's path crops its middle to fit a narrow slot, and shows in full once the slot widens."""

import pytest
from playwright.sync_api import Page

from tests.ui.harness.nav import goto_ready

pytestmark = pytest.mark.ui

_LINE = '[data-testid="header-host"] .hw-path-fit'


def _shown(page: Page) -> str:
    return page.evaluate(
        """sel => {
            return document.querySelector(sel).textContent;
        }""",
        _LINE,
    )


def _fit_is(page: Page, test: str) -> None:
    """Wait until the line's kind of rendering, ``fit`` (``full``, ``crop``, ``tail``), passes ``test``."""
    page.wait_for_function(
        f"sel => {{ const l = document.querySelector(sel); const fit = l && l.getAttribute('data-hw-fit');"
        f" return Boolean(l) && ({test}); }}",
        arg=_LINE,
    )


def test_the_header_path_crops_when_narrow_and_shows_in_full_when_wide(page: Page, harness) -> None:
    goto_ready(page, f"{harness}/code-editor-header?width=300")
    _fit_is(page, "fit === 'crop' || fit === 'tail'")
    full = page.get_attribute(_LINE, "title")
    assert full
    assert full.endswith("/projects/haywire/graphs/a_rather_long_file_name.txt")

    shown = _shown(page)
    assert shown != full
    assert ".." in shown
    assert shown.endswith("a_rather_long_file_name.txt")
    line_box = page.locator(_LINE).bounding_box()
    host_box = page.locator('[data-testid="header-host"]').bounding_box()
    assert line_box
    assert host_box
    assert line_box["x"] + line_box["width"] <= host_box["x"] + host_box["width"] + 0.5

    page.evaluate(
        "() => { document.querySelector('[data-testid=\"header-host\"]').style.width = '1400px'; }"
    )
    _fit_is(page, "fit === 'full'")
    assert _shown(page) == full
