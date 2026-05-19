# packages/haywire-core/src/haywire/ui/modals/diff_modal.py
"""Diff modal — preview proposed changes and pick an action.

Display-only modal: it shows one or more :class:`DiffSection` blocks with
additions and removals colour-coded by ``--hw-positive`` / ``--hw-danger``,
then offers up to two action buttons plus Cancel.

Designed for any "here are the changes I would make — apply how?" surface:

  - Detect-dependencies preview (Union / Replace)
  - Pre-publish drift report (Auto-fix / Continue anyway)
  - Migration previews
  - any future "review changes before applying" UI

When every section is empty (no additions, no removals), the action buttons
are disabled and an ``empty_message`` is shown — the caller doesn't need to
short-circuit before opening.
"""

from dataclasses import dataclass, field
from typing import Callable, Optional, Sequence

from nicegui import ui

from haywire.ui import elements as hui
from haywire.ui.components.popup import Popup


@dataclass(frozen=True)
class DiffSection:
    """One labelled diff block inside a :func:`diff_modal`."""

    title: str
    additions: Sequence[str] = field(default_factory=tuple)
    removals: Sequence[str] = field(default_factory=tuple)
    unchanged: Sequence[str] = field(default_factory=tuple)
    note: str = ""


def diff_modal(
    *,
    title: str,
    sections: Sequence[DiffSection],
    primary_label: str,
    on_primary: Callable[[], None],
    secondary_label: Optional[str] = None,
    on_secondary: Optional[Callable[[], None]] = None,
    on_cancel: Optional[Callable[[], None]] = None,
    width: str = "480px",
    empty_message: str = "No changes to apply.",
) -> Popup:
    """Open a diff-preview modal and return the opened :class:`Popup`.

    Args:
        title: Dialog title shown in the popup header.
        sections: Ordered :class:`DiffSection` blocks. Empty sections still
            render their title so the user sees that a category was checked
            and had nothing to change.
        primary_label: Label for the primary action button.
        on_primary: Called with no arguments when the user clicks the primary
            action. The popup closes automatically after the callback returns.
        secondary_label: Optional second action label (e.g. ``"Replace"``
            alongside ``primary_label="Union"``). When ``None``, only the
            primary action and Cancel are shown.
        on_secondary: Required when ``secondary_label`` is set; ignored
            otherwise.
        on_cancel: Called with no arguments when the user cancels (Cancel
            button, backdrop click, or Escape). Optional.
        width: CSS width for the popup. Defaults to ``"480px"``.
        empty_message: Text shown when every section has no additions and
            no removals. Action buttons are disabled in that case.

    Returns:
        The opened :class:`Popup`.

    Raises:
        ValueError: If ``secondary_label`` is set without ``on_secondary``,
            or vice versa.
    """
    if (secondary_label is None) != (on_secondary is None):
        raise ValueError("diff_modal: secondary_label and on_secondary must be set together")

    has_changes = any(s.additions or s.removals for s in sections)

    popup = Popup(
        title=title,
        width=width,
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
        if not has_changes:
            ui.label(empty_message).classes("text-sm hw-text-dim italic")
        else:
            for section in sections:
                _render_section(section)

        def _do(callback: Callable[[], None]) -> Callable[[], None]:
            def _wrapped() -> None:
                confirmed["value"] = True
                callback()
                popup.close()

            return _wrapped

        with ui.row().classes("w-full justify-end gap-2 mt-3"):
            ui.button("Cancel", on_click=popup.close).props("flat dense")
            if secondary_label is not None and on_secondary is not None:
                sec_btn = (
                    ui.button(secondary_label, on_click=_do(on_secondary))
                    .props("flat dense")
                    .style("color: var(--hw-warning);")
                )
                if not has_changes:
                    sec_btn.props("disable")
            prim_btn = (
                ui.button(primary_label, on_click=_do(on_primary))
                .props("flat dense")
                .style("color: var(--hw-positive);")
            )
            if not has_changes:
                prim_btn.props("disable")

    popup.open()
    return popup


def _render_section(section: DiffSection) -> None:
    """Render one DiffSection block: title, +/-/= lines, optional note."""
    hui.section_label(section.title)
    if not (section.additions or section.removals or section.unchanged):
        ui.label("(no changes)").classes("text-xs hw-text-dim italic ml-1")
    else:
        with ui.column().classes("gap-0.5 ml-1"):
            for line in section.additions:
                ui.label(f"+ {line}").classes("text-xs font-mono").style("color: var(--hw-positive);")
            for line in section.removals:
                ui.label(f"− {line}").classes("text-xs font-mono").style("color: var(--hw-danger);")
            for line in section.unchanged:
                ui.label(f"  {line}").classes("text-xs font-mono hw-text-dim")
    if section.note:
        ui.label(section.note).classes("text-xs hw-text-dim italic ml-1 mt-0.5")
