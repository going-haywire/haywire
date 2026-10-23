"""KeymapListener in a real browser: target resolution, key combos, native-key guard, paste.

The ``/keymap`` page mounts one listener (``platform="other"``, so Control is
``Mod``) over three slots: ``edit`` with editor roots ``ed::one`` and
``ed::two``, ``context`` with ``ed::ctx``, and ``info`` with no editor.
``#command-log`` lists every command that reached Python, so a test that
expects *no* command ends with a sentinel command and asserts the log holds
only that.
"""

import pytest
from playwright.sync_api import Page, expect

from tests.ui.harness.nav import goto_ready, wait_for_canvas_settled

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
            if (e.key === 'k') window.__hwProbe = e.defaultPrevented;
        })"""
    )
    _click_root(page, _TWO)

    page.keyboard.press("Control+k")

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


def _dispatch_paste(page: Page, text: str, target: str = "document.body") -> bool:
    """Dispatch a ``paste`` event holding ``text`` on ``target``; return whether it was not prevented."""
    return page.evaluate(
        f"""(text) => {{
            const dt = new DataTransfer();
            dt.setData('text/plain', text);
            return {target}.dispatchEvent(new ClipboardEvent('paste', {{
                clipboardData: dt, bubbles: true, cancelable: true,
            }}));
        }}""",
        text,
    )


def test_mod_v_reaches_paste_event(page: Page, harness):
    _open(page, harness)
    page.evaluate(
        """() => window.addEventListener('keydown', e => {
            if (e.key === 'v' && e.ctrlKey) window.__hwProbe = e.defaultPrevented;
        })"""
    )
    _click_root(page, _ONE)

    page.keyboard.press("Control+v")
    _dispatch_paste(page, "hello")

    assert page.evaluate("() => window.__hwProbe") is False
    expect(page.locator("#last-command")).to_have_text("paste@ed::one")
    expect(page.locator("#last-payload")).to_have_text("[12, 34]|hello")


def test_paste_in_text_field_is_native(page: Page, harness):
    _open(page, harness)
    field = page.locator(f"{_ONE} input")
    field.focus()

    not_prevented = _dispatch_paste(page, "hello", target="document.activeElement")

    assert not_prevented is True
    _expect_only_sentinel(page)


# ---------------------------------------------------------------------------
# /graph-keymap: a real graph canvas under a KeymapListener with the graph
# editor's keymap; the page runs copy and paste on the canvas manager.
# ---------------------------------------------------------------------------


def _node_ids(page: Page) -> list[str]:
    """The ids of the nodes on the canvas (pins carry ``data-node-id`` too, so ids repeat)."""
    return page.evaluate(
        """() => [...new Set([...document.querySelectorAll('.graph-canvas [data-node-id]')]
            .map(el => el.dataset.nodeId))]"""
    )


def test_graph_keyboard_paste_lands_at_pointer(page: Page, harness):
    goto_ready(page, f"{harness}/graph-keymap")
    wait_for_canvas_settled(page)
    (original,) = _node_ids(page)
    card = page.locator(f'[id="{original}"] .ui-node-slot').bounding_box()
    assert card is not None

    page.mouse.click(card["x"] + 30, card["y"] + 14)
    expect(page.locator(".node-selected")).to_have_count(1)
    page.keyboard.press("Control+c")
    expect(page.locator("#clipboard-json")).not_to_have_text("")
    copied = page.locator("#clipboard-json").inner_text()

    target_x, target_y = card["x"] + 40, card["y"] + card["height"] + 120
    page.mouse.move(target_x, target_y)
    _dispatch_paste(page, copied)

    page.wait_for_function(
        "() => new Set([...document.querySelectorAll('.graph-canvas [data-node-id]')]"
        ".map(el => el.dataset.nodeId)).size === 2"
    )
    (pasted,) = [node_id for node_id in _node_ids(page) if node_id != original]
    selected = page.locator(".node-selected")
    expect(selected).to_have_count(1)
    expect(selected).to_have_attribute("data-node-id", pasted)
    box = page.locator(f'[id="{pasted}"]').bounding_box()
    assert box is not None
    assert abs(box["x"] - target_x) < 3, (box, target_x)
    assert abs(box["y"] - target_y) < 3, (box, target_y)


def test_keys_native_inside_dialog(page: Page, harness):
    _open(page, harness)
    _click_root(page, _TWO)
    page.evaluate(
        """() => window.addEventListener('keydown', e => {
            if (e.key === 'a' && e.ctrlKey) window.__hwProbe = e.defaultPrevented;
        })"""
    )

    page.locator("#dialog-button").focus()
    page.keyboard.press("Control+a")

    assert page.evaluate("() => window.__hwProbe") is False
    _expect_only_sentinel(page)


def test_paste_inside_dialog_is_native(page: Page, harness):
    _open(page, harness)
    _click_root(page, _ONE)
    page.locator("#dialog-button").focus()

    not_prevented = _dispatch_paste(page, "hello", target="document.activeElement")

    assert not_prevented is True
    _expect_only_sentinel(page)


def test_hidden_target_falls_back_to_edit_slot(page: Page, harness):
    _open(page, harness)
    _click_root(page, _TWO)
    expect(page.locator("#last-target")).to_have_text("ed::two")

    page.evaluate(f"() => document.querySelector('{_TWO}').style.display = 'none'")
    page.keyboard.press("Delete")

    expect(page.locator("#last-command")).to_have_text("delete@ed::one")


def _dispatch_keydown(page: Page, init: str) -> None:
    """Dispatch a ``keydown`` on the body with the given ``KeyboardEvent`` init fields (a JS object body)."""
    page.evaluate(
        f"""() => document.body.dispatchEvent(new KeyboardEvent('keydown', {{
            {init}, bubbles: true, cancelable: true,
        }}))"""
    )


def test_non_latin_layout_uses_physical_key(page: Page, harness):
    _open(page, harness)
    _click_root(page, _TWO)

    _dispatch_keydown(page, "key: '\\u0441', code: 'KeyC', ctrlKey: true")

    expect(page.locator("#last-command")).to_have_text("copy@ed::two")


def test_altgr_character_keeps_its_glyph(page: Page, harness):
    """Ctrl+Alt outside macOS is AltGr: the composed character names the key, not the physical one."""
    _open(page, harness)
    _click_root(page, _TWO)

    _dispatch_keydown(page, "key: '\\u0142', code: 'KeyL', ctrlKey: true, altKey: true")

    _expect_only_sentinel(page)


def _probe_default_prevented(page: Page, key: str) -> None:
    page.evaluate(
        """(key) => window.addEventListener('keydown', e => {
            if (e.key === key && e.ctrlKey) window.__hwProbe = e.defaultPrevented;
        })""",
        key,
    )


def test_save_fires_inside_a_text_field(page: Page, harness):
    _open(page, harness)
    _probe_default_prevented(page, "s")

    page.locator(f"{_ONE} input").first.focus()
    page.keyboard.press("Control+s")

    expect(page.locator("#last-command")).to_have_text("save@ed::one")
    assert page.evaluate("() => window.__hwProbe") is True


def test_save_stays_with_a_native_keys_element(page: Page, harness):
    """``data-hw-native-keys`` keeps every key, a command marked ``in_text_fields`` too."""
    _open(page, harness)
    _probe_default_prevented(page, "s")

    page.locator("#native-keys").focus()
    page.keyboard.press("Control+s")

    assert page.evaluate("() => window.__hwProbe") is False
    _expect_only_sentinel(page)


def test_save_blurs_the_field_before_the_command(page: Page, harness):
    _open(page, harness)
    field = page.locator("#commit-field")

    field.focus()
    page.keyboard.type("new value")
    page.keyboard.press("Control+s")

    expect(page.locator("#command-log")).to_have_text("blur,save@ed::one")
    assert field.evaluate("el => document.activeElement === el")


def test_save_keeps_focus_in_a_code_editor(page: Page, harness):
    _open(page, harness)
    code = page.locator("#code-field")

    code.focus()
    page.keyboard.press("Control+s")

    expect(page.locator("#command-log")).to_have_text("save@ed::one")
    assert code.evaluate("el => document.activeElement === el")


def test_save_in_a_popup_field_is_native(page: Page, harness):
    """A haywire Popup is a dialog too, though it carries no ``.q-dialog``."""
    _open(page, harness)
    page.locator("#open-popup").click()
    field = page.locator(".popup-field input")
    expect(field).to_be_visible()

    field.focus()
    page.keyboard.press("Control+s")
    page.locator("#close-popup").click()

    _expect_only_sentinel(page)


def test_save_inside_a_dialog_is_native(page: Page, harness):
    _open(page, harness)

    page.locator("#dialog-button").focus()
    page.keyboard.press("Control+s")

    _expect_only_sentinel(page)


# ---------------------------------------------------------------------------
# The active slot
# ---------------------------------------------------------------------------


def _active_slot(page: Page) -> str:
    return page.evaluate("() => document.documentElement.dataset.hwActiveSlot")


def test_the_edit_slot_is_active_at_load(page: Page, harness):
    _open(page, harness)

    assert _active_slot(page) == "edit"


def test_a_click_on_a_slot_bar_activates_that_slot(page: Page, harness):
    _open(page, harness)

    page.locator("#ctx-bar").click()
    page.keyboard.press("Control+s")

    expect(page.locator("#last-command")).to_have_text("save@ed::ctx")
    expect(page.locator("#last-target")).to_have_text("ed::ctx")
    assert _active_slot(page) == "context"


def test_a_slot_without_an_editor_is_not_activated(page: Page, harness):
    _open(page, harness)
    _click_root(page, "#ctx-root")

    page.locator("#info-bar").click()
    page.keyboard.press("Delete")

    expect(page.locator("#last-command")).to_have_text("delete@ed::ctx")
    assert _active_slot(page) == "context"


def test_a_hidden_active_editor_falls_back_to_the_edit_slot(page: Page, harness):
    _open(page, harness)
    _click_root(page, "#ctx-root")
    page.locator("#ctx-root").evaluate("el => { el.style.display = 'none'; }")

    page.keyboard.press("Delete")

    expect(page.locator("#last-command")).to_have_text("delete@ed::one")
    assert _active_slot(page) == "edit"


def test_a_hidden_active_editor_lights_the_edit_slot_at_once(page: Page, harness):
    """Folding or closing the active slot's editor moves the highlight without waiting for a key."""
    _open(page, harness)
    _click_root(page, "#ctx-root")

    page.locator("#ctx-root").evaluate("el => { el.style.display = 'none'; }")

    page.wait_for_function("() => document.documentElement.dataset.hwActiveSlot === 'edit'", timeout=2000)


def test_a_bar_click_moves_no_target_until_a_key(page: Page, harness):
    """A bar click activates the slot only: the server's target editor stays until a key resolves it."""
    _open(page, harness)
    _click_root(page, _ONE)
    expect(page.locator("#last-target")).to_have_text("ed::one")

    page.locator("#ctx-bar").click()
    page.wait_for_timeout(300)
    expect(page.locator("#last-target")).to_have_text("ed::one")

    page.keyboard.press("Delete")
    expect(page.locator("#last-command")).to_have_text("delete@ed::ctx")
    expect(page.locator("#last-target")).to_have_text("ed::ctx")


def test_a_click_in_a_popup_keeps_the_active_slot(page: Page, harness):
    _open(page, harness)
    _click_root(page, "#ctx-root")

    page.locator("#open-popup").click()
    page.locator(".popup-field input").click()
    page.locator("#close-popup").click()

    assert _active_slot(page) == "context"


def test_the_active_slot_bar_is_lighter(page: Page, harness):
    _open(page, harness)

    page.locator("#ctx-bar").click()

    expect(page.locator("#ctx-bar")).to_have_css("background-color", "rgb(80, 80, 80)")
    expect(page.locator("#edit-bar")).to_have_css("background-color", "rgb(16, 16, 16)")
