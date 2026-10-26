"""Browser tests for the Properties editor's inspector tabs below edit (ADR 0060).

Drives the ``/inspector-gate`` harness route: the Node, Settings and Ports tabs of
one selected node, drawn into a session scope column under the page's AccessGate.
Below edit the tabs still draw; their writers are greyed and inert, and their
read-only rows stay live. F8, F9 and F10 move the session mode to ``view``,
``operate`` and ``edit``.
"""

from __future__ import annotations

import pytest
from playwright.sync_api import Page

from tests.ui.harness.nav import goto_ready

_PATH = "/inspector-gate"
_GREYED = {"opacity": "0.5", "pointer": "none"}
_LIVE = {"opacity": "1", "pointer": "auto"}

pytestmark = pytest.mark.ui


def _open(page: Page, harness, mode: str) -> None:
    goto_ready(page, f"{harness}{_PATH}?mode={mode}")
    page.wait_for_selector('[data-testid="panel-NodePortsPanel"] [data-hw-requires="edit"]')
    page.wait_for_function("(mode) => document.documentElement.dataset.hwSessionMode === mode", arg=mode)


def _panel(name: str) -> str:
    return f'[data-testid="panel-{name}"]'


def _styles(page: Page, selector: str) -> list[dict]:
    """The computed opacity and pointer-events of every element matching ``selector``."""
    return page.evaluate(
        """(sel) => [...document.querySelectorAll(sel)].map((el) => {
            const style = getComputedStyle(el);
            return { opacity: style.opacity, pointer: style.pointerEvents };
        })""",
        selector,
    )


def _takes_focus(page: Page, selector: str) -> bool:
    """Whether focusing the first input under ``selector`` from script leaves focus inside it."""
    return page.evaluate(
        """async (sel) => {
            const scope = document.querySelector(sel);
            const input = scope.querySelector('input, textarea, [tabindex="0"]');
            input.focus();
            await new Promise((done) => requestAnimationFrame(() => requestAnimationFrame(done)));
            return scope.contains(document.activeElement);
        }""",
        selector,
    )


_SETTINGS_WIDGET = f'{_panel("NodePropertiesPanel")} [data-field] [data-hw-requires="edit"]'
_PORT_WRITERS = f'{_panel("NodePortsPanel")} [data-hw-requires="edit"]'


@pytest.mark.parametrize("mode", ["view", "operate"])
def test_the_tabs_draw_below_edit(page: Page, harness, mode: str):
    _open(page, harness, mode)

    for name in ("NodeInfoPanel", "NodePropertiesPanel", "NodeStatusPanel", "NodePortsPanel"):
        assert page.locator(_panel(name)).count() == 1, name


@pytest.mark.parametrize("mode", ["view", "operate"])
def test_writers_are_greyed_and_inert_below_edit(page: Page, harness, mode: str):
    _open(page, harness, mode)

    settings = _styles(page, _SETTINGS_WIDGET)
    ports = _styles(page, _PORT_WRITERS)
    assert settings
    # The pen, the reorder grips and the port widgets.
    assert len(ports) >= 3
    assert all(style == _GREYED for style in settings + ports)
    assert not _takes_focus(page, _SETTINGS_WIDGET)


def test_writers_are_live_in_edit(page: Page, harness):
    _open(page, harness, "edit")

    writers = _styles(page, _SETTINGS_WIDGET) + _styles(page, _PORT_WRITERS)
    assert len(writers) >= 4
    assert all(style == _LIVE for style in writers)
    assert _takes_focus(page, _SETTINGS_WIDGET)


def test_read_only_rows_stay_live_in_view(page: Page, harness):
    _open(page, harness, "view")
    info = _panel("NodeInfoPanel")

    assert page.locator(info).get_by_text("Class").is_visible()
    # The info rows' copy buttons, and everything else in the panel, take input.
    assert page.evaluate(
        "(sel) => [...document.querySelectorAll(sel + ' *')].every((el) => !window.hwAccess.isGated(el))",
        info,
    )


def _open_row_menu(page: Page) -> None:
    page.locator(f"{_panel('NodePropertiesPanel')} [data-field] .sf-label").first.click(button="right")
    page.wait_for_selector('[data-row-menu] .q-item:has-text("Develop")')


_ROW_MENU_WRITERS = '[data-row-menu] [data-hw-requires="edit"]'


def _gated(page: Page, selector: str) -> list[bool]:
    """Whether the gate refuses input to each element matching ``selector``."""
    return page.evaluate(
        "(sel) => [...document.querySelectorAll(sel)].map((el) => window.hwAccess.isGated(el))", selector
    )


def test_row_menu_writers_are_greyed_below_edit_and_developer_stays_live(page: Page, harness):
    _open(page, harness, "view")
    _open_row_menu(page)

    # Promote to and Reset (Reset is also Quasar-disabled while the row is clean, at its own opacity).
    assert len(_gated(page, _ROW_MENU_WRITERS)) >= 2
    assert all(_gated(page, _ROW_MENU_WRITERS))
    assert all(style["pointer"] == "none" for style in _styles(page, _ROW_MENU_WRITERS))
    assert _styles(page, f"{_ROW_MENU_WRITERS}:not(.disabled)")[0] == _GREYED
    developer = page.locator('[data-row-menu] .q-item:has-text("Develop")').first
    assert developer.evaluate("(el) => !window.hwAccess.isGated(el)")
    assert developer.evaluate("(el) => getComputedStyle(el).pointerEvents") == "auto"
    developer.hover()
    page.locator('.q-menu .q-item:has-text("Settings source")').first.wait_for(state="visible", timeout=3000)


def test_row_menu_writers_are_live_in_edit(page: Page, harness):
    _open(page, harness, "edit")
    _open_row_menu(page)

    assert _gated(page, _ROW_MENU_WRITERS)
    assert not any(_gated(page, _ROW_MENU_WRITERS))
    assert all(style["pointer"] == "auto" for style in _styles(page, _ROW_MENU_WRITERS))


def _hover_promote_anchor(page: Page) -> None:
    """Move the pointer onto the row menu's "Promote to" anchor, gated or not."""
    anchor = page.locator('[data-row-menu] .q-item:has-text("Promote to")').first
    anchor.wait_for(state="visible")
    found = anchor.bounding_box()
    assert found is not None
    page.mouse.move(found["x"] + found["width"] / 2, found["y"] + found["height"] / 2, steps=4)


_PROMOTE_DIRECTION = '.q-menu .q-item:has-text("outlet"):visible'


def test_the_promote_flyout_opens_on_hover_in_edit(page: Page, harness):
    _open(page, harness, "edit")
    _open_row_menu(page)

    _hover_promote_anchor(page)

    page.locator(_PROMOTE_DIRECTION).first.wait_for(timeout=3000)


def test_the_greyed_promote_anchor_keeps_its_flyout_shut_below_edit(page: Page, harness):
    _open(page, harness, "view")
    _open_row_menu(page)

    _hover_promote_anchor(page)
    # The edit test above opens the flyout well within this time.
    page.wait_for_timeout(800)

    assert page.locator(_PROMOTE_DIRECTION).count() == 0
