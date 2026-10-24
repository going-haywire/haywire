"""Browser tests for ``AccessGate``, the page's level-mode gate on canvas cards and panels.

Drives the ``/access-gate`` harness route: a session scope column with an
unstamped input, one stamped ``operate`` and one stamped ``edit``, and a Group
card whose number widget is a card input, on a canvas. F8, F9 and F10 move
the session mode and the canvas to ``view``, ``operate`` and ``edit``.
"""

from __future__ import annotations

import pytest
from playwright.sync_api import Page

from tests.ui.harness.nav import goto_ready, wait_for_canvas_settled

_PATH = "/access-gate"
_KEYS = {"view": "F8", "operate": "F9", "edit": "F10"}

pytestmark = pytest.mark.ui


def _open(page: Page, harness, mode: str = "view") -> str:
    """Open the page in ``mode``; return the Group card's id."""
    goto_ready(page, f"{harness}{_PATH}?mode={mode}")
    page.wait_for_selector("[data-node-enterable] .number-drag__center")
    wait_for_canvas_settled(page)
    _wait_for_mode(page, mode)
    return page.locator('[data-testid="access-card-id"]').get_attribute("data-node") or ""


def _wait_for_mode(page: Page, mode: str) -> None:
    page.wait_for_function(
        """(mode) => document.documentElement.dataset.hwSessionMode === mode
            && document.querySelector('[data-hw-level-mode]').dataset.hwLevelMode === mode""",
        arg=mode,
    )


def _switch(page: Page, mode: str) -> None:
    page.keyboard.press(_KEYS[mode])
    _wait_for_mode(page, mode)


def _field(page: Page, testid: str) -> str:
    """A selector for the native input of the panel field ``testid`` (QInput puts the props on it)."""
    return f'input[data-testid="{testid}"]'


def _stamped(page: Page, testid: str) -> dict:
    """The computed opacity and pointer-events of the panel field ``testid``'s native input."""
    return page.evaluate(
        """(sel) => {
            const style = getComputedStyle(document.querySelector(sel));
            return { opacity: style.opacity, pointer: style.pointerEvents };
        }""",
        _field(page, testid),
    )


def _focused(page: Page, selector: str) -> bool:
    """Whether keyboard focus is on or inside ``selector``, once pending focus moves have run."""
    return page.evaluate(
        """async (sel) => {
            await new Promise((done) => requestAnimationFrame(() => requestAnimationFrame(done)));
            const el = document.querySelector(sel);
            return !!el && el.contains(document.activeElement);
        }""",
        selector,
    )


def _card_widget(card_id: str) -> str:
    return f'[data-node-id="{card_id}"] .number-drag'


def _focus(page: Page, selector: str) -> None:
    """Focus the first focusable element in ``selector`` from script, as a programmatic focus would."""
    page.evaluate(
        "(sel) => { const el = document.querySelector(sel); (el.matches('[tabindex], input') ? el"
        " : el.querySelector('[tabindex=\"0\"], input')).focus(); }",
        selector,
    )


def test_html_carries_the_session_mode(page: Page, harness):
    _open(page, harness, "view")
    assert page.evaluate("() => document.documentElement.dataset.hwSessionMode") == "view"

    page.keyboard.press("F10")

    page.wait_for_function("() => document.documentElement.dataset.hwSessionMode === 'edit'")


def test_stamped_panel_input_is_gated_and_greyed_in_view(page: Page, harness):
    _open(page, harness, "view")

    for testid in ("edit-input", "operate-input"):
        assert _stamped(page, testid) == {"opacity": "0.5", "pointer": "none"}


def test_operate_gates_only_the_edit_stamped_panel_input(page: Page, harness):
    _open(page, harness, "operate")

    assert _stamped(page, "edit-input") == {"opacity": "0.5", "pointer": "none"}
    assert _stamped(page, "operate-input") == {"opacity": "1", "pointer": "auto"}


def test_unstamped_panel_widget_stays_live_in_view(page: Page, harness):
    _open(page, harness, "view")

    assert _stamped(page, "free-input") == {"opacity": "1", "pointer": "auto"}
    page.locator(_field(page, "free-input")).click()
    page.keyboard.type("abc")
    assert page.locator(_field(page, "free-input")).input_value() == "abc"


@pytest.mark.parametrize(("mode", "focusable"), [("view", False), ("operate", False), ("edit", True)])
def test_panel_input_takes_focus_only_in_edit(page: Page, harness, mode: str, focusable: bool):
    _open(page, harness, mode)
    edit_input = _field(page, "edit-input")

    _focus(page, _field(page, "operate-input"))
    page.keyboard.press("Tab")
    assert _focused(page, edit_input) is focusable
    page.locator(edit_input).click(force=True)
    assert _focused(page, edit_input) is focusable
    _focus(page, edit_input)
    assert _focused(page, edit_input) is focusable


def test_lock_while_focused_blurs_the_panel_field(page: Page, harness):
    _open(page, harness, "edit")
    field = page.locator(_field(page, "edit-input"))
    field.click()
    page.keyboard.type("ab")

    _switch(page, "view")
    page.keyboard.type("cd")

    assert not _focused(page, _field(page, "edit-input"))
    assert field.input_value() == "ab"


def test_view_card_input_takes_no_keyboard_focus(page: Page, harness):
    card_id = _open(page, harness, "view")

    _focus(page, _card_widget(card_id))

    assert not _focused(page, _card_widget(card_id))


@pytest.mark.parametrize("mode", ["operate", "edit"])
def test_operable_card_input_takes_keyboard_focus_from_operate(page: Page, harness, mode: str):
    # The Group card's interface widget is operable (stamped operate).
    card_id = _open(page, harness, mode)

    _focus(page, _card_widget(card_id))

    assert _focused(page, _card_widget(card_id))


def test_lock_while_focused_blurs_the_card_input(page: Page, harness):
    card_id = _open(page, harness, "edit")
    _focus(page, _card_widget(card_id))
    assert _focused(page, _card_widget(card_id))

    _switch(page, "view")

    assert not _focused(page, _card_widget(card_id))


_PARITY_JS = """
(record) => {
    const els = [...document.querySelectorAll(
        '.ui-node-slot *, [data-hw-mode-scope="session"], [data-hw-mode-scope="session"] *')];
    if (record) {
        window.__hwBaseline = new WeakMap(els.map((el) => [el, getComputedStyle(el).pointerEvents]));
    }
    const describe = (el) => `${el.tagName.toLowerCase()}.${[...el.classList].join('.')}`
        + ` requires=${el.closest('[data-hw-requires]')?.dataset.hwRequires}`;
    const unknown = els.filter((el) => !window.__hwBaseline.has(el)).length;
    // An element its own rules make inert in edit (a focus helper) stays inert: the gate only adds none.
    const mismatches = els
        .filter((el) => {
            const none = getComputedStyle(el).pointerEvents === 'none';
            const own = window.__hwBaseline.get(el) === 'none';
            return none !== (window.hwAccess.isGated(el) || own);
        })
        .map(describe);
    const gated = els.filter((el) => window.hwAccess.isGated(el)).length;
    return { count: els.length, unknown, gated, mismatches };
}
"""


def test_css_and_isGated_agree(page: Page, harness):
    _open(page, harness, "edit")
    baseline = page.evaluate(_PARITY_JS, True)
    assert baseline["count"] > 20
    assert baseline["gated"] == 0
    assert baseline["mismatches"] == []

    for mode in ("operate", "view", "edit"):
        _switch(page, mode)
        result = page.evaluate(_PARITY_JS, False)
        assert result["unknown"] == 0, mode
        assert result["mismatches"] == [], mode
        if mode != "edit":
            assert result["gated"] > 0, mode
