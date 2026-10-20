"""The text of an annotation note, shown on its card and edited in place."""

from __future__ import annotations

from typing import Any

from nicegui import ui

from haywire.ui.widget.base import BaseWidget
from haywire.ui.widget.decorator import widget

#: Shown in place of an empty note.
_HINT = "Double-click to write"

#: Stretches the editor's Quasar field to the card; the field's own sizes are a short strip.
#: Quasar's field wrappers set their own font size and colour, so each one inherits the note's.
_EDITOR_CSS = """
.hw-note-editor, .hw-note-editor .q-field__inner, .hw-note-editor .q-field__control,
.hw-note-editor .q-field__control-container { font: inherit; color: inherit; text-decoration: inherit; }
.hw-note-editor .q-field__inner, .hw-note-editor .q-field__control,
.hw-note-editor .q-field__control-container { height: 100%; min-height: 0; }
.hw-note-editor .q-field__control-container { padding: 0; }
.hw-note-editor textarea { height: 100%; min-height: 0; resize: none; padding: 0; }
"""

#: Keys stay in the editor. Tab types a tab; Shift+Tab leaves the field.
_TAB_JS = """(e) => {
    e.stopPropagation();
    if (e.key === 'Tab' && !e.shiftKey) {
        e.preventDefault();
        const t = e.target;
        t.setRangeText('\\t', t.selectionStart, t.selectionEnd, 'end');
        t.dispatchEvent(new Event('input', { bubbles: true }));
    }
}"""

#: The textarea inherits the note's look from the elements around it; Quasar's field sets its own font.
_INPUT_STYLE = (
    "height: 100%; min-height: 0; font: inherit; color: inherit; "
    "text-align: inherit; text-decoration: inherit;"
)


def _ensure_editor_css() -> None:
    """Add the editor stylesheet to the current page once."""
    client = ui.context.client
    if not getattr(client, "_hw_note_editor_css", False):
        ui.add_css(_EDITOR_CSS)
        client._hw_note_editor_css = True  # type: ignore[attr-defined]


@widget(description="Note text")
class NoteTextWidget(BaseWidget):
    """Shows a note's text on its card; double-click it to edit.

    While editing, Tab types a tab and Shift+Tab leaves the editor. Press
    Ctrl+Enter or click elsewhere to keep the new text, or Esc to discard it.
    Line breaks are kept. The text takes its font, size, colour, alignment and
    highlight from the card it sits on.
    """

    def build(self) -> Any:
        # Laid out by the card through inherited custom properties; the root stays
        # unpositioned so the editor's overlay covers the whole card.
        root = ui.element("div").style(
            "flex: 1 1 auto; width: 100%; display: flex; flex-direction: column; "
            "justify-content: var(--hw-note-justify, flex-start); "
            "align-items: var(--hw-note-align, flex-start); text-decoration: inherit;"
        )
        with root:
            self._label = ui.label("").classes("zoom-pan-lod1")
            self._label.style(
                "white-space: pre-wrap; word-break: break-word; padding: 2px 6px; max-width: 100%; "
                "text-decoration: inherit; "
                "background-color: var(--hw-note-highlight, transparent);"
            )
            self._editor = ui.textarea(placeholder="Write a note…")
            _ensure_editor_css()
            self._editor.classes("hw-note-editor")
            self._editor.props(f'borderless input-style="{_INPUT_STYLE}"').style(
                "position: absolute; inset: 0; z-index: 2; padding: 12px; background: var(--hw-node-bg);"
            )
            self._editor.set_visibility(False)
            self._editor.on("keydown", lambda _e: None, js_handler=_TAB_JS)
            for event in ("mousedown", "pointerdown", "wheel"):
                self._editor.on(event, lambda _e: None, js_handler="(e) => e.stopPropagation()")
            self._editor.on("blur", self._commit)
            self._editor.on("hw-commit", self._commit)
            self._editor.on("keydown.esc", self._cancel)
            self._editor.on("keydown.ctrl.enter", lambda _e: self._editor.run_method("blur"))
        root.on("dblclick", self._begin_edit)
        return root

    def _begin_edit(self, _event: Any = None) -> None:
        self._editor.set_value(self.get_value() or "")
        self._editor.set_visibility(True)
        # A focus call made while the element is still being shown is dropped.
        ui.timer(0.1, lambda: self._editor.run_method("focus"), once=True)

    def _commit(self, _event: Any = None) -> None:
        if not self._editor.visible:
            return
        self._editor.set_visibility(False)
        text = self._editor.value or ""
        if text != (self.get_value() or ""):
            self.set_value(text)

    def _cancel(self, _event: Any = None) -> None:
        self._editor.set_value(self.get_value() or "")
        self._editor.set_visibility(False)

    def on_model_changed(self, value: Any) -> None:
        """Show *value*, or a dimmed hint when the note is empty."""
        text = value or ""
        self._label.set_text(text or _HINT)
        if text:
            self._label.style(remove="opacity: 0.5; font-style: italic;")
        else:
            self._label.style(add="opacity: 0.5; font-style: italic;")
