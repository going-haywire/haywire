# packages/haywire-core/src/haywire/ui/modals/text_modal.py
"""Text modal — full-size multi-line editor for a single string value.

The expand-to-full counterpart to a compact inline text input: the caller shows
a one-line field, this pops out an ``autogrow`` textarea so long or multi-line
values can be edited comfortably, then hands the confirmed text back via
``on_confirm``. The caller owns where that text goes (a port cell, a setting);
the modal is purely an editing surface and holds no value of its own.
"""

from typing import Callable, Optional

from nicegui import ui

from haywire.ui.components.popup import Popup


def text_modal(
    *,
    title: str,
    value: str,
    placeholder: str = "",
    confirm_label: str = "OK",
    width: str = "480px",
    on_confirm: Callable[[str], None],
    on_cancel: Optional[Callable[[], None]] = None,
) -> Popup:
    """Open a multi-line text editor modal and return the opened :class:`Popup`.

    Args:
        title: Dialog title shown in the popup header.
        value: Initial text seeded into the textarea.
        placeholder: Placeholder shown while the textarea is empty.
        confirm_label: Label for the confirm button (default ``"OK"``).
        width: Popup width as a CSS length (default ``"480px"``).
        on_confirm: Called with the textarea's text when the user confirms. The
            popup closes automatically after ``on_confirm`` returns.
        on_cancel: Called with no arguments when the user cancels (Cancel button,
            backdrop click, or Escape). Optional.

    Returns:
        The opened :class:`Popup`.
    """
    popup = Popup(
        title=title,
        width=width,
        closable=True,
        backdrop_click_close=True,
        escape_close=True,
    )

    # Guard so on_cancel doesn't also fire on a successful confirm (the popup's
    # close callback runs on every close, confirm included). Mirrors rename_modal.
    confirmed = {"value": False}

    if on_cancel is not None:

        def _maybe_cancel() -> None:
            if not confirmed["value"]:
                on_cancel()

        popup.on_close(_maybe_cancel)

    with popup:
        textarea = (
            ui.textarea(value=value, placeholder=placeholder)
            .classes("w-full text-xs")
            .props("dense autogrow")
        )

        def _do_confirm() -> None:
            confirmed["value"] = True
            on_confirm(textarea.value)
            popup.close()

        with ui.row().classes("w-full justify-end gap-2 mt-2"):
            ui.button("Cancel", on_click=popup.close).props("flat dense")
            ui.button(confirm_label, on_click=_do_confirm).props("flat dense").style(
                "color: var(--hw-positive);"
            )

    popup.open()
    return popup
