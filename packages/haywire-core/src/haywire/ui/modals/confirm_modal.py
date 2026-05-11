# packages/haywire-core/src/haywire/ui/modals/confirm_modal.py
"""Confirm modal — short message with Confirm / Cancel buttons.

Lightweight by design: stacks cleanly over other popups (transparent backdrop
by default), no inputs, no validation.
"""

from typing import Callable, Optional

from nicegui import ui

from haywire.ui.components.popup import Popup


def confirm_modal(
    *,
    title: str,
    message: str,
    confirm_label: str = "Confirm",
    danger: bool = False,
    on_confirm: Callable[[], None],
    on_cancel: Optional[Callable[[], None]] = None,
) -> Popup:
    """Open a confirmation modal and return the opened :class:`Popup`.

    Args:
        title: Dialog title shown in the popup header.
        message: Body text shown above the buttons. Single line; pre-formatted
            by the caller.
        confirm_label: Label for the confirm button.
        danger: When ``True``, color the confirm button with ``--hw-danger``.
            Use for destructive actions (overwrite, discard, delete).
        on_confirm: Called with no arguments when the user confirms. The popup
            closes automatically after ``on_confirm`` returns.
        on_cancel: Called with no arguments when the user cancels (Cancel
            button, backdrop click, or Escape). Optional.

    Returns:
        The opened :class:`Popup`.
    """
    popup = Popup(
        title=title,
        width="360px",
        closable=True,
        backdrop_click_close=True,
        escape_close=True,
        backdrop_color="transparent",
    )

    confirmed = {"value": False}

    if on_cancel is not None:

        def _maybe_cancel() -> None:
            if not confirmed["value"]:
                on_cancel()

        popup.on_close(_maybe_cancel)

    with popup:
        ui.label(message).classes("text-sm")

        def _do_confirm() -> None:
            confirmed["value"] = True
            on_confirm()
            popup.close()

        color = "var(--hw-danger)" if danger else "var(--hw-positive)"

        with ui.row().classes("w-full justify-end gap-2 mt-3"):
            ui.button("Cancel", on_click=popup.close).props("flat dense")
            ui.button(confirm_label, on_click=_do_confirm).props("flat dense").style(f"color: {color};")

    popup.open()
    return popup
