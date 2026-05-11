# packages/haywire-core/src/haywire/ui/modals/save_as_modal.py
"""Save-As modal — workspace-rooted path input with suffix selector.

Shape:

  ┌────────────────────────────────────┐
  │ Save Graph As                  ✕   │
  ├────────────────────────────────────┤
  │ 📁 /workspace/root/                │
  │ [ graphs/my_graph          ] [.haywire ▼] │
  │                       Cancel · Save │
  └────────────────────────────────────┘

The suffix selector is rendered as:
  - nothing, if ``suffixes`` is empty
  - a static label, if ``suffixes`` has one entry
  - a dropdown, if ``suffixes`` has more than one entry

On confirm the modal builds the absolute path, appends the selected suffix
if the typed path doesn't already end with it, and calls ``on_confirm``
with the resolved :class:`pathlib.Path` and the raw input string. The raw
input is useful for re-opening the modal after a stacked confirm-cancel.
"""

from pathlib import Path
from typing import Callable, Optional, Sequence

from nicegui import ui

from haywire.ui import elements as hui
from haywire.ui.components.popup import Popup


def save_as_modal(
    *,
    title: str,
    workspace_root: Path,
    initial_path: str,
    suffixes: Sequence[str] = (),
    on_confirm: Callable[[Path, str], None],
    on_cancel: Optional[Callable[[], None]] = None,
) -> Popup:
    """Open a Save-As modal and return the opened :class:`Popup`.

    Args:
        title: Dialog title.
        workspace_root: Absolute path shown as the non-editable prefix.
            All typed paths are interpreted relative to this root.
        initial_path: Pre-filled value, relative to ``workspace_root``.
            Also serves as the "same" anchor for collision classification —
            typing exactly this string is treated as "Save", regardless of
            whether the file exists on disk.
        suffixes: File suffixes to choose from (e.g. ``(".haywire",)``).
            Empty → no suffix UI. One → static label. Multiple → dropdown.
            On confirm, the selected suffix is appended to the path unless
            the typed path already ends with that exact suffix.
        on_confirm: Called with ``(absolute_path, raw_input)`` when the
            user confirms. ``absolute_path`` is fully resolved with suffix
            applied; ``raw_input`` is the relative string the user typed
            (useful for re-opening the modal after a stacked confirm).
            The popup closes automatically after ``on_confirm`` returns.
        on_cancel: Called with no arguments when the user cancels.

    Returns:
        The opened :class:`Popup`.
    """
    popup = Popup(
        title=title,
        width="460px",
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

    # Initial-anchor resolved path: typing exactly `initial_path` should be
    # classified as "Save", not "Overwrite", even if that file exists on disk.
    initial_resolved = (workspace_root / initial_path).resolve() if initial_path else None
    selected_suffix = suffixes[0] if suffixes else ""

    def _resolve(raw: str) -> Path:
        """Apply the workspace root + selected suffix to a raw input string.

        The suffix is *appended* (not substituted) when the typed name
        doesn't already end with it — typing ``loop.dep`` with suffix
        ``.haywire`` produces ``loop.dep.haywire``, not ``loop.haywire``.
        ``Path.with_suffix`` would do the wrong thing here.
        """
        if selected_suffix and not raw.endswith(selected_suffix):
            raw = raw + selected_suffix
        return (workspace_root / raw).resolve()

    def _classify(raw: str) -> str:
        # "save" | "overwrite" | "empty"
        if not raw:
            return "empty"
        if raw == initial_path:
            return "save"
        target = _resolve(raw)
        if initial_resolved is not None and target == initial_resolved:
            return "save"
        if target.exists():
            return "overwrite"
        return "save"

    with popup:
        # Workspace-root prefix chip
        with (
            ui.row()
            .classes("w-full items-center gap-1 px-1")
            .style("background: var(--hw-bg-page); border-radius: 4px; border: 1px solid var(--hw-border);")
        ):
            ui.icon("folder", size="14px").classes("hw-text-dim flex-shrink-0")
            ui.label(str(workspace_root).rstrip("/") + "/").classes(
                "text-xs font-mono hw-text-dim truncate py-1"
            )

        def _refresh(_=None) -> None:
            raw = (path_input.value or "").strip()
            mode = _classify(raw)
            if mode == "overwrite":
                confirm_btn.text = "Overwrite"
                confirm_btn.style("color: var(--hw-danger);")
            else:
                confirm_btn.text = "Save"
                confirm_btn.style("color: var(--hw-positive);")
            if mode == "empty":
                confirm_btn.props("disable")
            else:
                confirm_btn.props(remove="disable")
            # Hide the redundant static suffix label when the typed path
            # already ends with it. Dropdown stays visible always — the user
            # needs the affordance to switch.
            if suffix_label is not None:
                suffix_label.set_visibility(not raw.endswith(selected_suffix))

        # Path input + optional suffix selector, side by side
        suffix_label: Optional[ui.label] = None
        with ui.row().classes("w-full items-center gap-2 flex-nowrap"):
            path_input = hui.input_field(
                label="Path within workspace",
                value=initial_path,
                autofocus=True,
                on_change=_refresh,
            )
            # hui.input_field hard-codes w-full; remove it so the input flexes
            # within the row instead of pushing the suffix selector to a new line.
            path_input.classes(remove="w-full", add="flex-1 min-w-0")
            if len(suffixes) > 1:

                def _on_suffix_change(e) -> None:
                    nonlocal selected_suffix
                    selected_suffix = e.value
                    _refresh()

                ui.select(
                    options=list(suffixes),
                    value=selected_suffix,
                    on_change=_on_suffix_change,
                ).props("dense").classes("flex-shrink-0")
            elif len(suffixes) == 1:
                suffix_label = ui.label(suffixes[0]).classes("text-xs font-mono hw-text-dim flex-shrink-0")

        with ui.row().classes("w-full justify-end gap-2 mt-1"):
            ui.button("Cancel", on_click=popup.close).props("flat dense")
            confirm_btn = ui.button("Save").props("flat dense")

        def _do_confirm() -> None:
            raw = (path_input.value or "").strip()
            if _classify(raw) == "empty":
                return
            confirmed["value"] = True
            on_confirm(_resolve(raw), raw)
            popup.close()

        confirm_btn.on("click", _do_confirm)

        _refresh()

    popup.open()
    return popup
