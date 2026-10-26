"""Browser tests for the level-mode gate on card content.

Drives the ``/graph-level-mode`` harness route: a Group card whose interface
inlet shows a number widget, a Fold Probe card with fold headers, and a card
with a comment and a warning, on a canvas in level mode ``?mode=``. Below
``edit`` card content takes no pointer input except readable elements, which
take it in every mode, and operable elements, which take it in ``operate``.
"""

from __future__ import annotations

import pytest
from playwright.sync_api import Locator, Page

from tests.ui.harness.nav import goto_ready, wait_for_canvas_settled
from tests.ui.harness.probe import attr, box

_PATH = "/graph-level-mode"

pytestmark = pytest.mark.ui


def _open(page: Page, harness, mode: str) -> tuple[str, str]:
    """Open the page in ``mode``; return the Group card's and the Fold Probe card's ids."""
    goto_ready(page, f"{harness}{_PATH}?mode={mode}")
    page.wait_for_selector("[data-node-enterable] .number-drag__center")
    page.wait_for_selector("[data-hw-fold-id]")
    wait_for_canvas_settled(page)
    card_id = attr(page, '[data-testid="level-card-id"]', "data-node")
    fold_id = attr(page, '[data-testid="level-fold-id"]', "data-node")
    return card_id, fold_id


def _centre(locator: Locator, what: str) -> tuple[float, float]:
    locator.scroll_into_view_if_needed()
    found = box(locator, what)
    return found["x"] + found["width"] / 2, found["y"] + found["height"] / 2


def _hit(page: Page, locator: Locator, what: str, test: str) -> bool:
    """Evaluate ``test`` (a JS expression over ``el``) on the element hit at ``locator``'s centre."""
    x, y = _centre(locator, what)
    return page.evaluate(
        f"([x, y]) => {{ const el = document.elementFromPoint(x, y); return !!el && ({test}); }}",
        [x, y],
    )


def _widget(page: Page, card_id: str) -> Locator:
    return page.locator(f'[data-node-id="{card_id}"] .number-drag__center')


def _title(page: Page, card_id: str) -> Locator:
    return page.locator(f'[data-node-id="{card_id}"] .text-h6')


def _badge_card(page: Page) -> str:
    """The id of the card drawing the comment and the diagnostics badge, once both are drawn."""
    page.wait_for_selector("[data-hw-requires=view].q-btn")
    return attr(page, '[data-testid="level-badge-id"]', "data-node")


def _diagnostics_badge(page: Page, card_id: str) -> Locator:
    return page.locator(f'[data-node-id="{card_id}"] .q-btn[data-hw-requires=view]:has(.q-badge)')


def _comment_badge(page: Page, card_id: str) -> Locator:
    return page.locator(f'[data-node-id="{card_id}"] .q-btn[data-hw-requires=view]:not(:has(.q-badge))')


def _log(page: Page) -> str:
    return page.locator('[data-testid="enter-log"]').inner_text()


def _wait_for_enter(page: Page, card_id: str) -> None:
    page.wait_for_function(
        "(nid) => document.querySelector('[data-testid=\"enter-log\"]').innerText === nid",
        arg=card_id,
    )


def test_view_card_content_takes_no_pointer_input(page: Page, harness):
    card_id, _ = _open(page, harness, "view")
    assert _hit(page, _widget(page, card_id), "number widget", "el.closest('.widget-container') === null")


def test_operate_widgets_take_pointer_input(page: Page, harness):
    card_id, _ = _open(page, harness, "operate")
    assert _hit(
        page, _widget(page, card_id), "number widget", "el.closest('[data-hw-requires=operate]') !== null"
    )


def test_operate_card_text_takes_no_pointer_input(page: Page, harness):
    """The title passes the press to the card: the hit is the slot or the card root."""
    card_id, _ = _open(page, harness, "operate")
    assert _hit(
        page,
        _title(page, card_id),
        "card title",
        f"!el.matches('.ui-node-slot *') && el.closest('[data-node-id]')?.dataset.nodeId === {card_id!r}",
    )


def test_operate_fold_header_toggles(page: Page, harness):
    _, fold_id = _open(page, harness, "operate")
    header = page.locator(f'[data-node-id="{fold_id}"] [data-hw-fold-id]').first
    fold_port = header.get_attribute("data-hw-fold-id")
    was_open = header.get_attribute("data-hw-fold-open")
    assert fold_port is not None and was_open is not None  # noqa: PT018

    x, y = _centre(header, "fold header")
    page.mouse.click(x, y)

    page.wait_for_function(
        """([nid, port, was]) => {
            const h = document.querySelector(`[data-node-id="${nid}"] [data-hw-fold-id="${port}"]`);
            return !!h && h.getAttribute('data-hw-fold-open') !== was;
        }""",
        arg=[fold_id, fold_port, was_open],
    )


def test_view_double_click_does_not_enter(page: Page, harness):
    card_id, _ = _open(page, harness, "view")
    x, y = _centre(_title(page, card_id), "card title")

    page.mouse.dblclick(x, y)
    page.wait_for_timeout(600)

    assert _log(page) == ""


def test_operate_double_click_on_a_widget_does_not_enter(page: Page, harness):
    """The widget takes the double-click; the card's title still enters."""
    card_id, _ = _open(page, harness, "operate")
    x, y = _centre(_widget(page, card_id), "number widget")

    page.mouse.dblclick(x, y)
    page.wait_for_timeout(600)

    assert _log(page) == ""

    tx, ty = _centre(_title(page, card_id), "card title")
    page.mouse.dblclick(tx, ty)
    _wait_for_enter(page, card_id)


def test_edit_card_content_takes_pointer_input(page: Page, harness):
    card_id, _ = _open(page, harness, "edit")
    assert _hit(page, _widget(page, card_id), "number widget", "el.closest('.widget-container') !== null")


def test_operate_gate_leaves_widget_internals_alone(page: Page, harness):
    """A widget's own pointer-events rule stands: its centre set to none passes the press to its frame.

    The widget still takes input, and the card's title still does not.
    """
    card_id, _ = _open(page, harness, "operate")
    page.evaluate(
        '(nid) => { document.querySelector(`[data-node-id="${nid}"] .number-drag__center`)'
        ".style.pointerEvents = 'none'; }",
        card_id,
    )

    assert _hit(
        page,
        _widget(page, card_id),
        "number widget",
        "el.closest('.number-drag__center') === null && el.closest('[data-hw-requires=operate]') !== null",
    )
    assert _hit(page, _title(page, card_id), "card title", "!el.matches('.ui-node-slot *')")


def test_view_diagnostics_badge_opens_its_menu(page: Page, harness):
    _open(page, harness, "view")
    badge = _diagnostics_badge(page, _badge_card(page))
    assert _hit(page, badge, "diagnostics badge", "el.closest('[data-hw-requires=view]') !== null")

    x, y = _centre(badge, "diagnostics badge")
    page.mouse.click(x, y)

    page.get_by_text("Harness warning").wait_for(state="visible")


def test_view_comment_badge_shows_its_comment(page: Page, harness):
    _open(page, harness, "view")
    comment = _comment_badge(page, _badge_card(page))
    assert _hit(page, comment, "comment badge", "el.closest('[data-hw-requires=view]') !== null")

    x, y = _centre(comment, "comment badge")
    page.mouse.move(x, y)

    page.get_by_text("Harness comment").wait_for(state="visible")


def test_view_pin_shows_its_tooltip_and_starts_no_edge(page: Page, harness):
    _open(page, harness, "view")
    pin = page.locator(f'[data-node-id="{_badge_card(page)}"] .connection-pin[data-hw-requires=view]').first
    assert _hit(page, pin, "pin", "el.closest('[data-hw-requires=view]') !== null")

    x, y = _centre(pin, "pin")
    page.mouse.move(x, y)
    page.locator(".q-tooltip").first.wait_for(state="visible")

    page.mouse.down()
    page.mouse.move(x + 60, y + 40)
    page.mouse.up()
    assert page.locator(".graph-canvas.edge-dragging").count() == 0


@pytest.mark.parametrize(
    ("mode", "cursor"), [("view", "default"), ("operate", "default"), ("edit", "crosshair")]
)
def test_a_pin_shows_the_crosshair_only_in_edit(page: Page, harness, mode: str, cursor: str):
    """Below edit a pin starts no edge, so it does not promise one."""
    _open(page, harness, mode)
    pin = page.locator(f'[data-node-id="{_badge_card(page)}"] .connection-pin[data-hw-requires=view]').first

    assert pin.evaluate("el => getComputedStyle(el).cursor") == cursor


@pytest.mark.parametrize(("mode", "hit"), [("view", False), ("operate", False), ("edit", True)])
def test_a_ghost_pin_takes_pointer_input_only_in_edit(page: Page, harness, mode: str, hit: bool):
    """A pin without its own tooltip is gated, despite .connection-pin's own !important rule."""
    _open(page, harness, mode)
    ghost = page.locator(f'[data-node-id="{_badge_card(page)}"] [data-pin-ghost]').first
    assert _hit(
        page, ghost, "ghost pin", f"(el.closest('[data-pin-ghost]') !== null) === {str(hit).lower()}"
    )


def _selected(page: Page, node_id: str) -> bool:
    return (
        page.locator(f'[data-node-id="{node_id}"].node-selected, [id="{node_id}"].node-selected').count() > 0
    )


def _wait_selected(page: Page, node_id: str) -> None:
    page.wait_for_function(
        "(nid) => !!document.querySelector("
        '`[id="${nid}"].node-selected, [data-node-id="${nid}"].node-selected`)',
        arg=node_id,
    )


def test_a_box_selection_under_way_survives_a_lock(page: Page, harness):
    """Selecting is looking: the level locks mid-drag and releasing still selects."""
    card_id, _ = _open(page, harness, "edit")
    card = box(page.locator(f'[data-node-id="{card_id}"]').first, "group card")
    page.mouse.move(card["x"] - 40, card["y"] - 40)
    page.mouse.down()
    page.mouse.move(card["x"] + card["width"] + 20, card["y"] + card["height"] + 20, steps=8)
    page.wait_for_selector(".graph-canvas.box-selecting")

    page.keyboard.press("F9")
    page.wait_for_selector('.graph-canvas[data-hw-level-mode="operate"]', timeout=10_000)
    page.mouse.up()

    _wait_selected(page, card_id)


def test_view_click_selects_and_moves_nothing(page: Page, harness):
    card_id, _ = _open(page, harness, "view")
    card = page.locator(f'[data-node-id="{card_id}"]').first
    before = box(card, "group card")
    x, y = _centre(_title(page, card_id), "card title")

    page.mouse.move(x, y)
    page.mouse.down()
    # Past the 5px drag threshold: a press that moves but drags nothing still selects.
    page.mouse.move(x + 12, y + 8, steps=4)
    page.mouse.up()

    _wait_selected(page, card_id)
    after = box(card, "group card")
    assert (after["x"], after["y"]) == (before["x"], before["y"])
    assert page.locator('[data-testid="resize-gadget"]').count() == 0
    assert not page.locator(".hw-selection-toolbar").is_visible()


def test_view_box_select_selects(page: Page, harness):
    card_id, _ = _open(page, harness, "view")
    card = box(page.locator(f'[data-node-id="{card_id}"]').first, "group card")
    page.mouse.move(card["x"] - 40, card["y"] - 40)
    page.mouse.down()
    page.mouse.move(card["x"] + card["width"] + 20, card["y"] + card["height"] + 20, steps=8)
    page.mouse.up()

    _wait_selected(page, card_id)


def test_operate_click_on_a_widget_does_not_select(page: Page, harness):
    card_id, _ = _open(page, harness, "operate")
    x, y = _centre(_widget(page, card_id), "number widget")
    page.mouse.click(x, y)
    page.wait_for_timeout(400)
    assert not _selected(page, card_id)

    tx, ty = _centre(_title(page, card_id), "card title")
    page.mouse.click(tx, ty)
    _wait_selected(page, card_id)


def test_unlocking_shows_the_toolbar_for_a_kept_selection(page: Page, harness):
    card_id, _ = _open(page, harness, "edit")
    tx, ty = _centre(_title(page, card_id), "card title")
    page.mouse.click(tx, ty)
    page.wait_for_selector(".hw-selection-toolbar")

    page.keyboard.press("F9")
    page.wait_for_selector('.graph-canvas[data-hw-level-mode="operate"]', timeout=10_000)
    page.wait_for_selector(".hw-selection-toolbar", state="hidden", timeout=10_000)
    assert _selected(page, card_id)

    page.keyboard.press("F10")
    page.wait_for_selector('.graph-canvas[data-hw-level-mode="edit"]', timeout=10_000)
    page.wait_for_selector(".hw-selection-toolbar", state="visible", timeout=10_000)
    page.wait_for_selector('[data-testid="resize-gadget"]', timeout=10_000)


def test_view_fold_header_does_not_toggle(page: Page, harness):
    _, fold_id = _open(page, harness, "view")
    header = page.locator(f'[data-node-id="{fold_id}"] [data-hw-fold-id]').first
    was_open = header.get_attribute("data-hw-fold-open")

    x, y = _centre(header, "fold header")
    page.mouse.click(x, y)
    page.wait_for_timeout(600)
    wait_for_canvas_settled(page)

    assert header.get_attribute("data-hw-fold-open") == was_open


def _note(page: Page) -> tuple[str, Locator]:
    note_id = attr(page, '[data-testid="level-note-id"]', "data-node")
    label = page.locator(f'[data-node-id="{note_id}"] .zoom-pan-lod1', has_text="Harness note")
    label.wait_for()
    return note_id, label


def _note_editor(page: Page, note_id: str) -> Locator:
    return page.locator(f'[data-node-id="{note_id}"] .hw-note-editor textarea')


def test_edit_annotation_double_click_edits_the_text(page: Page, harness):
    _open(page, harness, "edit")
    note_id, label = _note(page)
    x, y = _centre(label, "note text")

    page.mouse.dblclick(x, y)
    editor = _note_editor(page, note_id)
    editor.wait_for(state="visible")
    page.wait_for_function(
        "(nid) => document.activeElement === "
        'document.querySelector(`[data-node-id="${nid}"] .hw-note-editor textarea`)',
        arg=note_id,
    )
    page.keyboard.press("End")
    page.keyboard.type(" more")
    page.keyboard.press("Control+Enter")

    page.locator(f'[data-node-id="{note_id}"] .zoom-pan-lod1', has_text="Harness note more").wait_for()
    assert editor.is_hidden()


def test_operate_annotation_double_click_opens_no_editor(page: Page, harness):
    _open(page, harness, "operate")
    note_id, label = _note(page)
    x, y = _centre(label, "note text")

    assert _hit(page, label, "note text", "!el.matches('.ui-node-slot *')")
    page.mouse.dblclick(x, y)
    page.wait_for_timeout(600)

    assert _note_editor(page, note_id).is_hidden()


def test_a_note_drags_by_its_text(page: Page, harness):
    _open(page, harness, "edit")
    note_id, label = _note(page)
    card = page.locator(f'[data-node-id="{note_id}"]').first
    before = box(card, "note card")
    x, y = _centre(label, "note text")

    page.mouse.move(x, y)
    page.mouse.down()
    page.mouse.move(x + 40, y + 30, steps=8)
    page.mouse.up()
    wait_for_canvas_settled(page)

    after = box(card, "note card")
    assert after["x"] > before["x"] + 20
    assert after["y"] > before["y"] + 15


def test_the_note_editor_keeps_the_note_s_look(page: Page, harness):
    _open(page, harness, "edit")
    note_id, label = _note(page)
    x, y = _centre(label, "note text")

    page.mouse.dblclick(x, y)
    editor = _note_editor(page, note_id)
    editor.wait_for(state="visible")

    look = "(el) => { const s = getComputedStyle(el); return [s.fontSize, s.color, s.textDecorationLine]; }"
    assert editor.evaluate(look) == label.evaluate(look) == ["30px", "rgb(255, 0, 0)", "underline"]


@pytest.mark.parametrize(("mode", "cursor"), [("view", "default"), ("operate", "default"), ("edit", "move")])
def test_a_card_shows_the_move_cursor_only_in_edit(page: Page, harness, mode: str, cursor: str):
    """Below edit a card selects but does not move, so it does not offer the move cursor."""
    card_id, _ = _open(page, harness, mode)
    card = page.locator(f'[id="{card_id}"]').first
    assert card.evaluate("(el) => getComputedStyle(el).cursor") == cursor


def _canvas_events(page: Page) -> list[str]:
    """Collect the console lines of every event the canvas emits to the server, from now on."""
    lines: list[str] = []
    page.on("console", lambda msg: lines.append(msg.text) if "Vue→Python Event" in msg.text else None)
    return lines


def test_view_right_click_keeps_selection_and_opens_no_menu(page: Page, harness):
    card_id, _ = _open(page, harness, "view")
    note_id, label = _note(page)
    tx, ty = _centre(_title(page, card_id), "card title")
    page.mouse.click(tx, ty)
    _wait_selected(page, card_id)
    page.evaluate(
        "() => { window.__hwNativeMenu = null; document.addEventListener('contextmenu', "
        "(e) => { window.__hwNativeMenu = !e.defaultPrevented; }); }"
    )
    events = _canvas_events(page)

    x, y = _centre(label, "note text")
    page.mouse.click(x, y, button="right")
    # The document listener runs after the canvas's, so any event it emitted is logged by now;
    # console messages arrive in order, so the fence arriving means every earlier line has.
    page.wait_for_function("() => window.__hwNativeMenu !== null")
    with page.expect_console_message(lambda msg: msg.text == "hw-fence"):
        page.evaluate("() => console.log('hw-fence')")

    assert page.evaluate("() => window.__hwNativeMenu") is False
    assert _selected(page, card_id)
    assert not _selected(page, note_id)
    assert not [line for line in events if "contextMenu" in line or "selectionChanged" in line]
    assert page.locator(".q-menu").count() == 0


def test_view_press_and_move_emits_no_drag_start(page: Page, harness):
    card_id, _ = _open(page, harness, "view")
    events = _canvas_events(page)
    x, y = _centre(_title(page, card_id), "card title")

    page.mouse.move(x, y)
    page.mouse.down()
    page.mouse.move(x + 12, y + 8, steps=4)
    page.mouse.up()
    _wait_selected(page, card_id)

    assert not [line for line in events if "userDrag" in line]


def test_an_unknown_gesture_type_is_refused_and_logged(page: Page, harness):
    _open(page, harness, "edit")
    errors: list[str] = []
    page.on("console", lambda msg: errors.append(msg.text) if msg.type == "error" else None)

    allowed = page.evaluate(
        """() => {
            for (let i = 0; i < 5000; i++) {
                const c = getElement(i);
                if (c && c.$el && c.$el.dataset && c.$el.dataset.testid === 'level-canvas') {
                    return c._allows('noSuchEvent');
                }
            }
            throw new Error('no level canvas');
        }"""
    )

    assert allowed is False
    assert any("[GraphCanvas]" in line and "noSuchEvent" in line for line in errors)
