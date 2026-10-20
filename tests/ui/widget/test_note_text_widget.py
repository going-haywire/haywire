"""NoteTextWidget: a note's text, edited in place on a double-click and written once on commit."""

from __future__ import annotations

from typing import Any

import pytest
from nicegui import ui

from haywire.barn.builtin.types import STRING
from haywire.barn.builtin.widgets.note_text_widget import NoteTextWidget
from haywire.core.types.enums import PortType
from haywire.core.types.port import DataPort
from haywire.ui.panel.setting_widget_model import SettingWidgetModel

pytestmark = pytest.mark.unit


def _model(text: str, on_edit) -> SettingWidgetModel:
    port = DataPort(
        registry_id="text",
        registry_key=STRING.class_identity.registry_key,
        label="Text",
        id="text",
        type_cls=STRING,
        port_type=PortType.CONFIG,
    )
    port.data.set_value(text)
    return SettingWidgetModel(field_id="text", widget_config={}, cell=port.data, on_edit=on_edit)


def _fire(element: ui.element, event_type: str) -> None:
    listener = next(lis for lis in element._event_listeners.values() if lis.type == event_type)
    assert listener.handler is not None
    listener.handler(None)


def _editor(root: ui.element) -> ui.textarea:
    return next(e for e in root.descendants() if isinstance(e, ui.textarea))


def _label(root: ui.element) -> ui.label:
    return next(e for e in root.descendants() if isinstance(e, ui.label))


def test_double_click_opens_the_editor_with_the_text(nicegui_slot_context) -> None:
    root = NoteTextWidget(_model("Hello", lambda _v: None)).render()
    editor = _editor(root)
    assert editor.visible is False

    _fire(root, "dblclick")

    assert editor.visible is True
    assert editor.value == "Hello"


def test_commit_writes_the_new_text_once(nicegui_slot_context) -> None:
    writes: list[Any] = []
    root = NoteTextWidget(_model("Hello", writes.append)).render()
    editor = _editor(root)
    _fire(root, "dblclick")
    editor.value = "Hello world"

    _fire(editor, "blur")
    _fire(editor, "blur")

    assert writes == ["Hello world"]
    assert editor.visible is False


def test_the_save_key_commits(nicegui_slot_context) -> None:
    """The keymap listener sends ``hw-commit`` before Ctrl+S, where a Quasar blur never arrives."""
    writes: list[Any] = []
    root = NoteTextWidget(_model("Hello", writes.append)).render()
    editor = _editor(root)
    _fire(root, "dblclick")
    editor.value = "Hello world"

    _fire(editor, "hwCommit")  # NiceGUI stores ``.on("hw-commit")`` camel-cased

    assert writes == ["Hello world"]


def test_cancel_and_unchanged_commit_write_nothing(nicegui_slot_context) -> None:
    writes: list[Any] = []
    root = NoteTextWidget(_model("Hello", writes.append)).render()
    editor = _editor(root)

    _fire(root, "dblclick")
    editor.value = "Changed"
    _fire(editor, "keydown.esc")
    assert editor.visible is False
    assert _label(root).text == "Hello"

    _fire(root, "dblclick")
    assert editor.value == "Hello"
    _fire(editor, "blur")

    assert writes == []


def test_a_refused_commit_shows_the_stored_text(nicegui_slot_context) -> None:
    root = NoteTextWidget(_model("Hello", lambda _v: False)).render()
    editor = _editor(root)
    _fire(root, "dblclick")
    editor.value = "Refused"

    _fire(editor, "blur")

    assert _label(root).text == "Hello"


def test_empty_text_shows_the_hint(nicegui_slot_context) -> None:
    root = NoteTextWidget(_model("", lambda _v: None)).render()

    label = _label(root)
    assert label.text == "Double-click to write"
    assert "italic" in label._style.get("font-style", "")


def test_the_shown_text_is_not_a_widget_container(nicegui_slot_context) -> None:
    root = NoteTextWidget(_model("Hello", lambda _v: None)).render()

    assert all("widget-container" not in e._classes for e in [root, *root.descendants()])
