"""ShortcutsEditor: the keyboard shortcuts of every editor, grouped by editor."""

from __future__ import annotations

from typing import TYPE_CHECKING, Optional

from nicegui import ui

from haywire.core.session.context import SessionContext
from haywire.core.session.handlers import react_on, redraw_on
from haywire.ui import elements as hui
from haywire.ui.editor.base import BaseEditor
from haywire.ui.editor.decorator import editor
from haywire.ui.editor.identity import SlotName
from haywire.ui.editor.wrapper import EditorWrapper

if TYPE_CHECKING:
    from nicegui.element import Element

    from haywire.core.signals import EditorCommand
    from haywire.ui.keymap import Keymap


@editor(
    label="Shortcuts",
    icon=hui.icon.keyboard,
    default_slot=SlotName.CONTEXT,
    description="Keyboard shortcuts of every editor, grouped by editor.",
    order=60,
)
class ShortcutsEditor(BaseEditor):
    """Lists the keyboard shortcuts of every editor, one collapsible group per editor.

    The group of the editor that receives key presses opens and carries an
    `active` tag; the other groups close. Clicking into an editor without
    shortcuts, this one included, leaves the open group as it is. A command
    that loses a key to another command of the same editor is marked with the
    command that holds the key.
    """

    def __init__(self, wrapper: EditorWrapper) -> None:
        super().__init__(wrapper)
        # Editor key whose group was last opened by following the target editor.
        self._followed: Optional[str] = None
        # Group open state by editor key, kept across redraws.
        self._expanded: dict[str, bool] = {}

    @redraw_on(SessionContext.keymap)
    def _on_keymap(self, ctx: SessionContext, signal: object) -> None:
        pass

    @react_on(SessionContext.target_binding_id)
    def _on_target(self, ctx: SessionContext, signal: object) -> None:
        # A pointer-down in this editor retargets it; redrawing then would replace the
        # header under the pointer and swallow the click, so only a group change redraws.
        if self._follow(ctx.keymap, ctx.target_binding_id):
            self.wrapper.redraw()

    def _follow(self, keymap: Optional[Keymap], binding_id: Optional[str]) -> bool:
        """Open the target editor's group and close the others; return ``True`` if the groups changed.

        A target without a group changes nothing but lets the next target with one take over.
        """
        target_key = self._target_key(binding_id)
        if keymap is None or target_key is None or target_key not in keymap.editors:
            self._followed = None
            return False
        if target_key == self._followed:
            return False
        self._followed = target_key
        self._expanded = {target_key: True}
        return True

    def draw(self, context: SessionContext, container: Element) -> None:
        keymap = context.keymap
        with container:
            if keymap is None or not keymap.editors:
                hui.empty_state("No editor declares keyboard shortcuts.", icon=hui.icon.keyboard)
                return

            self._follow(keymap, context.target_binding_id)
            target_key = self._target_key(context.target_binding_id)

            with ui.column().classes("w-full gap-0"):
                for editor_key in sorted(keymap.editors, key=lambda k: (keymap.editor_labels[k], k)):
                    self._draw_group(keymap, editor_key, active=editor_key == target_key)

    @staticmethod
    def _target_key(binding_id: Optional[str]) -> Optional[str]:
        return EditorWrapper.split_id(binding_id)[0] if binding_id else None

    def _draw_group(self, keymap: Keymap, editor_key: str, *, active: bool) -> None:
        label = keymap.editor_labels[editor_key]
        with hui.expansion_section(
            label, default_open=False, state=self._expanded, panel_key=editor_key
        ) as group:
            with group.add_slot("header"):
                with ui.item_section():
                    ui.label(label).classes("truncate")
                if active:
                    with ui.item_section().props("side"):
                        hui.tag("active", color="primary")
            for command in keymap.editor_commands(editor_key):
                self._draw_row(keymap, editor_key, command)

    @staticmethod
    def _draw_row(keymap: Keymap, editor_key: str, command: type[EditorCommand]) -> None:
        entries = keymap.editors[editor_key]
        combos = [combo for combo, entry in entries.items() if entry.command is command]
        winners = [
            clash.winner
            for clash in keymap.clashes
            if clash.editor_key == editor_key and command in clash.losers
        ]
        with ui.row().classes("w-full items-center no-wrap px-2 py-1 gap-2"):
            with ui.column().classes("gap-0 min-w-0"):
                ui.label(command.label).classes("text-sm hw-text-body truncate")
                for winner in dict.fromkeys(winners):
                    hui.warning_label(f"Shadowed by {winner.label}").classes(remove="p-4 text-sm").classes(
                        "text-xs"
                    )
            with ui.element("div").classes("ml-auto flex items-center gap-2 flex-shrink-0"):
                for combo in combos:
                    hui.combo_hint(combo)
