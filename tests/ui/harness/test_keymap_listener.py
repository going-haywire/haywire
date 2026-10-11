"""KeymapListener in a real browser: target resolution, key combos, native-key guard, paste.

The ``/keymap`` page mounts one listener (``platform="other"``, so Control is
``Mod``) over two editor roots, ``ed::one`` and ``ed::two``, inside
``#hw-slot-edit``. ``#command-log`` lists every command that reached Python, so
a test that expects *no* command ends with a sentinel command and asserts the
log holds only that.
"""

import pytest
from playwright.sync_api import Page, expect

from tests.ui.harness.nav import goto_ready

pytestmark = pytest.mark.ui

_PATH = "/keymap"
_ONE = '[data-hw-binding="ed::one"]'
_TWO = '[data-hw-binding="ed::two"]'


def _open(page: Page, harness: str) -> None:
    goto_ready(page, f"{harness}{_PATH}")


def _click_root(page: Page, selector: str) -> None:
    """Click a root at its top-left corner, clear of the input and pointer-hook children."""
    page.locator(selector).click(position={"x": 4, "y": 4})


def _expect_only_sentinel(page: Page) -> None:
    """Send ``Delete`` to ``ed::two`` and assert it is the only command that arrived."""
    _click_root(page, _TWO)
    page.keyboard.press("Delete")
    expect(page.locator("#last-command")).to_have_text("delete@ed::two")
    expect(page.locator("#command-log")).to_have_text("delete@ed::two")


def test_pointerdown_sets_target(page: Page, harness):
    _open(page, harness)

    _click_root(page, _TWO)

    expect(page.locator("#last-target")).to_have_text("ed::two")


def test_command_goes_to_target(page: Page, harness):
    _open(page, harness)

    _click_root(page, _TWO)
    page.keyboard.press("Control+a")

    expect(page.locator("#last-command")).to_have_text("select_all@ed::two")


def test_keys_native_inside_text_field(page: Page, harness):
    _open(page, harness)
    field = page.locator(f"{_ONE} input")

    page.evaluate(
        """() => window.addEventListener('keydown', e => {
            if (e.key === 'a' && e.ctrlKey) window.__hwProbe = e.defaultPrevented;
        })"""
    )

    field.focus()
    page.keyboard.type("abc")
    page.keyboard.press("Control+a")

    assert page.evaluate("() => window.__hwProbe") is False
    # The field's own Control+A ran: select-all, or caret-to-line-start on macOS.
    selection = field.evaluate("el => [el.selectionStart, el.selectionEnd]")
    assert selection in ([0, 3], [0, 0])
    _expect_only_sentinel(page)


def test_repeat_ignored(page: Page, harness):
    _open(page, harness)
    _click_root(page, _TWO)

    page.evaluate(
        """() => document.body.dispatchEvent(new KeyboardEvent('keydown', {
            key: 'a', code: 'KeyA', ctrlKey: true, repeat: true, bubbles: true, cancelable: true,
        }))"""
    )

    _expect_only_sentinel(page)


def test_unclaimed_key_not_prevented(page: Page, harness):
    _open(page, harness)
    page.evaluate(
        """() => window.addEventListener('keydown', e => {
            if (e.key === 's') window.__hwProbe = e.defaultPrevented;
        })"""
    )
    _click_root(page, _TWO)

    page.keyboard.press("Control+s")

    assert page.evaluate("() => window.__hwProbe") is False
    _expect_only_sentinel(page)


def test_falls_back_to_edit_slot_when_target_gone(page: Page, harness):
    _open(page, harness)
    _click_root(page, _TWO)
    expect(page.locator("#last-target")).to_have_text("ed::two")

    page.evaluate(f"() => document.querySelector('{_TWO}').remove()")
    page.keyboard.press("Delete")

    expect(page.locator("#last-command")).to_have_text("delete@ed::one")


def test_pointerdown_outside_roots_keeps_target(page: Page, harness):
    _open(page, harness)
    _click_root(page, _TWO)
    expect(page.locator("#last-target")).to_have_text("ed::two")

    page.locator("#outside").click()
    page.keyboard.press("Delete")

    expect(page.locator("#last-command")).to_have_text("delete@ed::two")
    expect(page.locator("#last-target")).to_have_text("ed::two")


def test_paste_carries_text_and_pointer_position(page: Page, harness):
    _open(page, harness)
    _click_root(page, _ONE)

    page.evaluate(
        """() => {
            const dt = new DataTransfer();
            dt.setData('text/plain', 'hello');
            document.body.dispatchEvent(new ClipboardEvent('paste', {
                clipboardData: dt, bubbles: true, cancelable: true,
            }));
        }"""
    )

    expect(page.locator("#last-command")).to_have_text("paste@ed::one")
    expect(page.locator("#last-payload")).to_have_text("[12, 34]|hello")
