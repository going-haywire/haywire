# packages/haywire-core/src/haywire/ui/modals/rename_modal.py
"""Rename / Save-As modal — single-field name prompt with live classification.

The confirm button relabels itself on every keystroke based on the typed name:

  - empty                    → button disabled (label = classify["same"])
  - equal to ``value``       → classify["same"]      (positive color)
  - new (not in ``existing``)→ classify["changed"]   (positive color)
  - collides with existing   → classify["existing"]  (danger color)

Collision check is exact-match against ``existing`` and excludes the modal's
own initial ``value`` — re-confirming the same name is always "same", never
"existing".
"""

from typing import Callable, Iterable, Optional

from nicegui import ui

from haywire.ui import elements as hui
from haywire.ui.components.popup import Popup


DEFAULT_CLASSIFY = {
    "same": "Save",
    "changed": "Save As",
    "existing": "Overwrite",
}


def rename_modal(
    *,
    title: str,
    value: str,
    existing: Iterable[str] = (),
    classify: Optional[dict[str, str]] = None,
    allow_overwrite: bool = True,
    on_confirm: Callable[[str], None],
    on_cancel: Optional[Callable[[], None]] = None,
) -> Popup:
    """Open a name-prompt modal and return the opened :class:`Popup`.

    Args:
        title: Dialog title shown in the popup header.
        value: Initial value and the anchor for the "same" classification —
            re-typing this exact value is treated as "same", even if it
            also appears in ``existing``.
        existing: Names that already exist. A typed name equal to one of these
            (and not equal to ``value``) flips the modal into "overwrite" mode.
            Exact-match, case-sensitive.
        classify: Button labels for the three states. Defaults to
            ``{"same": "Save", "changed": "Save As", "existing": "Overwrite"}``.
            Partial overrides are merged with the defaults.
        allow_overwrite: When ``True`` (default), a collision lets the user
            confirm (button label = ``classify["existing"]``, red border).
            When ``False``, a collision disables the button — the user must
            choose a different name. Use for rename-style flows that should
            never silently replace an existing item.
        on_confirm: Called with the stripped name when the user confirms.
            Closing the popup is the caller's responsibility (the modal does
            it for you after ``on_confirm`` returns).
        on_cancel: Called with no arguments when the user cancels (Cancel
            button, backdrop click, or Escape). Optional.

    Returns:
        The opened :class:`Popup`. Callers usually don't need it, but it's
        returned for advanced use (e.g. programmatic close).
    """
    labels = {**DEFAULT_CLASSIFY, **(classify or {})}
    initial = value
    existing_set = set(existing)

    popup = Popup(
        title=title,
        width="320px",
        closable=True,
        backdrop_click_close=True,
        escape_close=True,
    )

    # Track whether the popup closed via on_confirm (so on_cancel is not
    # spuriously called when the user successfully confirmed).
    confirmed = {"value": False}

    if on_cancel is not None:

        def _maybe_cancel() -> None:
            if not confirmed["value"]:
                on_cancel()

        popup.on_close(_maybe_cancel)

    with popup:

        def _classify(name: str) -> str:
            # "same" | "changed" | "existing" | "empty"
            if not name:
                return "empty"
            if name == initial:
                return "same"
            if name in existing_set:
                return "existing"
            return "changed"

        def _refresh(_=None) -> None:
            name = (name_input.value or "").strip()
            mode = _classify(name)

            confirm_btn.text = labels[mode] if mode != "empty" else labels["same"]

            color = "var(--hw-danger)" if mode == "existing" else "var(--hw-positive)"
            confirm_btn.style(f"color: {color};")

            disabled = mode == "empty" or (mode == "existing" and not allow_overwrite)
            if disabled:
                confirm_btn.props("disable")
            else:
                confirm_btn.props(remove="disable")

        name_input = hui.input_field(label="Name", value=initial, autofocus=True, on_change=_refresh)

        with ui.row().classes("w-full justify-end gap-2 mt-2"):
            ui.button("Cancel", on_click=popup.close).props("flat dense")
            confirm_btn = ui.button(labels["same"]).props("flat dense")

        def _do_confirm() -> None:
            name = (name_input.value or "").strip()
            mode = _classify(name)
            if mode == "empty" or (mode == "existing" and not allow_overwrite):
                return
            confirmed["value"] = True
            on_confirm(name)
            popup.close()

        confirm_btn.on("click", _do_confirm)

        _refresh()

    popup.open()
    return popup
