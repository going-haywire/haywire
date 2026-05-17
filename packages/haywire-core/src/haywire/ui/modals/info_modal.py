# packages/haywire-core/src/haywire/ui/modals/info_modal.py
"""Info modal — icon + title + one or more message lines + an OK button.

Use for non-destructive notifications where no decision is required from
the user (blocked actions, explanatory messages, status reports).
"""

from nicegui import ui

from haywire.ui.components.popup import Popup


def info_modal(
    *,
    title: str,
    message: str,
    detail: str = "",
    icon: str = "info",
    ok_label: str = "OK",
) -> Popup:
    """Open an informational modal and return the opened :class:`Popup`.

    Args:
        title: Dialog title shown in the popup header.
        message: Primary body text (shown in ``hw-text-muted``).
        detail: Optional secondary line shown below message (``hw-text-dim italic``).
        icon: Material icon name shown next to the title inside the card body.
        ok_label: Label for the dismiss button.

    Returns:
        The opened :class:`Popup`.
    """
    popup = Popup(
        title=title,
        width="380px",
        closable=True,
        backdrop_click_close=True,
        escape_close=True,
        backdrop_color="transparent",
    )

    with popup:
        with ui.row().classes("items-start gap-3 w-full"):
            ui.icon(icon, size="20px").classes("hw-text-warning flex-shrink-0 mt-0.5")
            with ui.column().classes("gap-1 min-w-0"):
                ui.label(message).classes("text-sm hw-text-muted")
                if detail:
                    ui.label(detail).classes("text-xs hw-text-dim italic")

        with ui.row().classes("w-full justify-end mt-3"):
            ui.button(ok_label, on_click=popup.close).props("flat dense")

    popup.open()
    return popup
