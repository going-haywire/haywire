"""Browser-side keyboard-shortcut listener: one per page, reporting commands for the target editor."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from nicegui import events, ui

from haywire.ui.editor.identity import SlotName


class KeymapListener(ui.element, component="keymap_listener.vue"):
    """Listen for key presses and pastes anywhere on the page and report them as editor commands.

    The active slot is the last ``[data-hw-slot]`` that took a pointer-down
    and shows an editor root, or comes to show one before the next pointer-down
    (a collapsed rail expanding); the listener writes it to ``<html
    data-hw-active-slot>``, where the shell CSS lights its bars. The target
    editor is the root under that pointer-down, else the slot's visible root.
    A key combo found in the target editor's keymap is reported
    through ``on_command`` and its browser default is suppressed; a combo whose
    command is a native-event command (see ``EditorCommand.native_event``) is
    left to the browser and reported from that event instead. Keys and pastes
    inside a text field (``input``, ``textarea``, ``select``,
    ``[contenteditable]``, ``.cm-editor``) stay with the field, except a command
    marked ``EditorCommand.in_text_fields``; inside a ``[data-hw-native-keys]``
    subtree every key and paste stays with the element. Before
    reporting one, the listener sends a focused ``input`` or ``textarea`` a
    bubbling ``hw-commit`` DOM event, so a widget that commits on blur listens
    for ``hw-commit`` too. Keys inside a dialog or a ``Popup`` stay with the
    page. A key goes to the target editor while it is visible in the active
    slot, else to the slot's visible root; when the active slot shows none, the
    first visible root in ``fallback_slot`` receives it and that slot becomes
    active. ``fallback_slot`` is also the active slot at load.

    Args:
        on_command: Called with ``{"command_id", "binding_id", "position",
            "text"}``. ``position`` is ``[x, y]`` from the root's
            ``[data-hw-pointer-local]`` hook on a paste, else ``None``;
            ``text`` is the pasted plain text, else ``""``.
        on_target: Called with ``{"binding_id"}`` when a pointer-down moves the
            target to another editor.
        fallback_slot: ``SlotName`` value of the slot active at load and
            whenever the active slot shows no editor.
        platform: ``"mac"`` (Cmd is ``Mod``, Control is ``Ctrl``), any other
            value for Control as ``Mod``, or ``"auto"`` to detect from the
            browser.

    Example::

        listener = KeymapListener(on_command=dispatch, on_target=retarget)
        listener.set_keymap(keymap.to_client())
    """

    def __init__(
        self,
        *,
        on_command: Callable[[dict[str, Any]], None],
        on_target: Callable[[dict[str, Any]], None],
        fallback_slot: str = SlotName.EDIT.value,
        platform: str = "auto",
    ) -> None:
        super().__init__()
        self._on_command = on_command
        self._on_target = on_target
        self._props["keymap"] = {"editors": {}, "native": {}, "text_fields": []}
        self._props["fallback-slot"] = fallback_slot
        self._props["platform"] = platform
        self.on("hw-command", self._handle_command)
        self.on("hw-target", self._handle_target)

    def set_keymap(self, client_keymap: dict[str, Any]) -> None:
        """Replace the keymap the browser resolves key presses against.

        Args:
            client_keymap: The shape returned by ``Keymap.to_client``.
        """
        self._props["keymap"] = client_keymap
        self.update()

    def _handle_command(self, e: events.GenericEventArguments) -> None:
        self._on_command(e.args)

    def _handle_target(self, e: events.GenericEventArguments) -> None:
        self._on_target(e.args)
