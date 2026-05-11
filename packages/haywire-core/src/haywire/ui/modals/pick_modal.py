# packages/haywire-core/src/haywire/ui/modals/pick_modal.py
"""Pick-one modal — single-select prompt with Confirm / Cancel.

A minimal "choose one of N" dialog. The select is pre-populated with the
first option; the caller's ``on_confirm`` receives the chosen string.
"""

from typing import Callable, Optional, Sequence

from nicegui import ui

from haywire.ui.components.popup import Popup


def pick_modal(
    *,
    title: str,
    options: Sequence[str],
    confirm_label: str = "OK",
    searchable: bool = False,
    on_confirm: Callable[[str], None],
    on_cancel: Optional[Callable[[], None]] = None,
) -> Popup:
    """Open a single-select modal and return the opened :class:`Popup`.

    Args:
        title: Dialog title shown in the popup header.
        options: Choices to present. Must be non-empty; the first entry is
            the initial selection.
        confirm_label: Label for the confirm button (e.g. ``"Load"``, ``"Open"``).
        searchable: When ``True``, the select accepts typed input to filter
            the option list (Quasar's ``use-input``). Use for lists of more
            than ~10 items.
        on_confirm: Called with the selected string when the user confirms.
            The popup closes automatically after ``on_confirm`` returns.
        on_cancel: Called with no arguments when the user cancels (Cancel
            button, backdrop click, or Escape). Optional.

    Returns:
        The opened :class:`Popup`. Callers usually don't need it.
    """
    if not options:
        raise ValueError("pick_modal requires at least one option")

    popup = Popup(
        title=title,
        width="320px",
        closable=True,
        backdrop_click_close=True,
        escape_close=True,
    )

    confirmed = {"value": False}

    if on_cancel is not None:

        def _maybe_cancel() -> None:
            if not confirmed["value"]:
                on_cancel()

        popup.on_close(_maybe_cancel)

    with popup:
        select = ui.select(
            options=list(options),
            value=options[0],
            with_input=searchable,
        ).classes("w-full mt-2")
        select.props("dense use-input" if searchable else "dense")

        def _do_confirm() -> None:
            value = select.value
            if value is None:
                return
            confirmed["value"] = True
            on_confirm(value)
            popup.close()

        with ui.row().classes("w-full justify-end gap-2 mt-2"):
            ui.button("Cancel", on_click=popup.close).props("flat dense")
            ui.button(confirm_label, on_click=_do_confirm).props("flat dense").style(
                "color: var(--hw-positive);"
            )

    popup.open()
    return popup
