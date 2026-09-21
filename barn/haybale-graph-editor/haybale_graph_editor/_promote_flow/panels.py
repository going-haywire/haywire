"""Per-step body content for the Promote to Macro flow."""

from __future__ import annotations

from typing import Callable

from nicegui import ui

from haywire.ui.components.stepper import advance, busy_advance

from ._state import PromoteFlow


def _panel_name(flow: PromoteFlow, rerender: Callable[[], None]) -> None:
    """The macro's name and the library it goes into. Nothing written yet."""
    ui.label("Promote this Group into a macro").classes("text-sm font-medium")
    ui.label(
        "A macro lives in its own file and can be placed in any graph. This Group's card "
        "becomes the first placement."
    ).classes("text-xs hw-text-dim")

    if not flow.targets:
        with ui.row().classes("w-full items-center gap-2 mt-1"):
            ui.icon("error", size="16px").classes("hw-text-danger")
            ui.label("No library in this project can receive a macro.").classes("text-sm hw-text-danger")
        ui.label(
            "A macro needs a library installed with 'pip install -e' that registers a "
            "macros/ folder — otherwise its file could never be edited or scanned."
        ).classes("text-xs hw-text-muted")
        return

    name_input = ui.input(label="Macro name", value=flow.name).classes("w-full")
    name_input.props("dense outlined autofocus")

    refusal_label = ui.label("").classes("text-xs hw-text-danger")

    if len(flow.targets) > 1:
        options = {t.library_id: t.label for t in flow.targets}
        ui.select(
            options,
            label="Library",
            value=flow.target.library_id if flow.target else None,
            on_change=lambda e: _on_target(flow, e.value),
        ).classes("w-full").props("dense outlined")
    elif flow.target is not None:
        ui.label(f"Into {flow.target.label}").classes("text-xs hw-text-dim")

    with ui.row().classes("w-full justify-end gap-2"):
        plan_button = ui.button("Continue").props("flat dense").style("color: var(--hw-positive);")
        plan_button.on_click(lambda: busy_advance(rerender, plan_button, flow.advance_from_name))

    # Wired after both elements exist, since the handler writes to them.
    # on_change binds ui.input's own `update:value`; hand-wiring
    # `update:modelValue` here would drop every keystroke in the browser.
    name_input.on_value_change(lambda e: _on_name(flow, e.value, refusal_label, plan_button))

    # Reflect whatever the field opened with, so an unusable suggestion is
    # named before the user has typed anything.
    _on_name(flow, flow.name, refusal_label, plan_button)


def _on_name(flow: PromoteFlow, value: str, refusal_label, plan_button) -> None:
    """Live-validate the name, per decision 17 — the filestem is a registry key."""
    flow.name = (value or "").strip()
    refusal = flow.name_refusal
    refusal_label.set_text(refusal or "")
    plan_button.set_enabled(flow.can_plan)


def _on_target(flow: PromoteFlow, library_id: str) -> None:
    flow.target = next((t for t in flow.targets if t.library_id == library_id), flow.target)


def _panel_planned(flow: PromoteFlow, rerender: Callable[[], None]) -> None:
    """The file that would be written. The next click is the one that writes."""
    plan = flow.plan
    if plan is None:  # pragma: no cover — unreachable via the flow
        return

    ui.label("This will be written:").classes("text-sm font-medium")
    ui.label(str(plan.path)).classes("text-xs font-mono hw-text-dim")

    if plan.refusal is not None:
        with ui.row().classes("w-full items-center gap-2 mt-1"):
            ui.icon("error", size="16px").classes("hw-text-danger")
            ui.label(plan.refusal).classes("text-sm hw-text-danger")
        with ui.row().classes("w-full justify-end gap-2"):
            ui.button("Back", on_click=lambda: _back(flow, rerender)).props("flat dense")
        return

    node_count = len(plan.document.get("nodes", {}))
    ui.label(
        f"{node_count} node{'' if node_count == 1 else 's'}, including the two boundary nodes "
        "that define its interface."
    ).classes("text-xs hw-text-muted")
    ui.label("The Group's card becomes a placement. Undo puts the Group back and leaves the file.").classes(
        "text-xs hw-text-dim"
    )

    with ui.row().classes("w-full justify-end gap-2"):
        ui.button("Back", on_click=lambda: _back(flow, rerender)).props("flat dense")
        promote = ui.button("Promote").props("flat dense").style("color: var(--hw-positive);")
        promote.on_click(lambda: busy_advance(rerender, promote, flow.advance_from_planned))


def _back(flow: PromoteFlow, rerender: Callable[[], None]):
    """Return to the name step. Nothing was written, so there is nothing to undo."""

    async def _go() -> None:
        flow.retry()
        flow.step = "name"

    return advance(rerender, _go)


def _panel_promoted(flow: PromoteFlow, on_done: Callable[[], None] | None) -> None:
    with ui.row().classes("w-full items-center gap-2"):
        ui.icon("check_circle", size="16px").style("color: var(--hw-positive);")
        ui.label(f"{flow.name} is now a macro.").classes("text-sm").style("color: var(--hw-positive);")

    if flow.registry_key:
        ui.label(flow.registry_key).classes("text-xs font-mono hw-text-dim")
    ui.label("Find it in the add-node menu, under this library's macros.").classes("text-xs hw-text-muted")

    def _close() -> None:
        if flow.popup is not None:
            flow.popup.close()

    with ui.row().classes("w-full justify-end gap-2"):
        ui.button("Done", on_click=_close).props("flat dense").style("color: var(--hw-positive);")
