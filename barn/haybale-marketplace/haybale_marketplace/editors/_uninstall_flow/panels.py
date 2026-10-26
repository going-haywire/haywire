"""Per-step body content for the Uninstall Library flow."""

from __future__ import annotations

from typing import Callable

from nicegui import ui

from haywire.ui import elements as hui

from haywire.ui.components.stepper import advance, busy_advance
from haywire.ui.modals import restart_affordance

from haybale_marketplace.editors._uninstall_flow._state import UninstallFlow


def _plural(count: int, singular: str, plural: str | None = None) -> str:
    return f"{count} {singular if count == 1 else (plural or singular + 's')}"


def _panel_selected(flow: UninstallFlow, rerender: Callable[[], None]) -> None:
    """What is about to be removed. Nothing has been read or written yet."""
    hui.hint(
        "This removes the library from the environment. Checking first which graphs use it "
        "and which installed packages depend on it — neither check changes anything."
    )

    with hui.action_row():
        check = hui.confirm_button("Check impact")
        check.on_click(lambda: busy_advance(rerender, check, flow.advance_from_selected))


def _panel_impact(flow: UninstallFlow, rerender: Callable[[], None]) -> None:
    """Graph usage and pip reverse-dependencies. Informs; never blocks."""
    impact = flow.impact
    if impact is None:  # pragma: no cover — unreachable via the flow
        return

    clean = not impact.graphs and not impact.pip_dependents
    if clean and impact.graphs_scanned:
        with ui.row().classes("w-full items-center gap-2"):
            ui.icon("check_circle", size="16px").style("color: var(--hw-positive);")
            ui.label("Nothing else refers to this library.").classes("text-sm").style(
                "color: var(--hw-positive);"
            )

    if impact.graphs:
        with ui.row().classes("w-full items-center gap-2"):
            ui.icon("warning", size="16px").style("color: var(--hw-warning);")
            ui.label(
                f"{_plural(len(impact.graphs), 'graph')} use this library "
                f"({_plural(impact.total_references, 'reference')})."
            ).classes("text-sm").style("color: var(--hw-warning);")
        with hui.indented():
            for usage in impact.graphs:
                hui.hint(f"{usage.name} — {_plural(usage.references, 'reference')}").classes("font-mono")
        hui.hint("Those nodes will fail to load until the library is installed again.")

    if not impact.graphs_scanned:
        hui.hint(
            "No project open, so graphs were not scanned — graphs elsewhere may still use this library."
        )

    if impact.pip_dependents:
        with ui.row().classes("w-full items-center gap-2 mt-1"):
            ui.icon("error", size="16px").classes("hw-text-danger")
            ui.label(
                f"{_plural(len(impact.pip_dependents), 'installed package')} "
                f"{'requires' if len(impact.pip_dependents) == 1 else 'require'} "
                f"{impact.dist_name}."
            ).classes("text-sm hw-text-danger")
        with hui.indented():
            for name in impact.pip_dependents:
                ui.label(name).classes("text-xs font-mono hw-text-danger")
        hui.hint("Removing it anyway will break those packages until they are reinstalled.")

    if impact.is_editable:
        hui.hint("This is an editable install — the source folder on disk is left untouched.")

    with hui.action_row():
        ui.button(
            "Continue",
            on_click=lambda: advance(rerender, flow.advance_from_impact),
        ).props("flat dense")


def _panel_confirm(flow: UninstallFlow, rerender: Callable[[], None]) -> None:
    """The decision point. The next click is the destructive one."""
    impact = flow.impact

    ui.label(f"Remove {flow.label} from the environment?").classes("text-sm")

    if impact is not None and impact.dist_name:
        hui.hint(f"uv uninstall {impact.dist_name}").classes("font-mono")

    consequences: list[str] = []
    if impact is not None:
        if impact.graphs:
            consequences.append(f"{_plural(len(impact.graphs), 'graph')} will show missing nodes")
        if impact.pip_dependents:
            consequences.append(
                f"{_plural(len(impact.pip_dependents), 'installed package')} will lose a dependency"
            )
    if consequences:
        hui.hint("After this: " + ", ".join(consequences) + ".")

    hui.hint("This cannot be undone from here — reinstall from the marketplace to get it back.")

    with hui.action_row():
        uninstall = ui.button("Uninstall").props("flat dense").style("color: var(--hw-danger);")
        uninstall.on_click(lambda: busy_advance(rerender, uninstall, flow.advance_from_confirm))


def _panel_removed(flow: UninstallFlow, on_done: Callable[[], None] | None) -> None:
    with ui.row().classes("w-full items-center gap-2"):
        ui.icon("check_circle", size="16px").style("color: var(--hw-positive);")
        ui.label(f"{flow.label} uninstalled.").classes("text-sm").style("color: var(--hw-positive);")

    if flow.log_lines:
        with ui.expansion("Output").classes("w-full"):
            log = ui.log(max_lines=200).classes("w-full h-32")
            for line in flow.log_lines:
                log.push(line)

    restart_affordance(
        reason=(
            f"Uninstalling {flow.label} left the loaded registry holding components "
            "that are no longer installed."
        ),
        compact=True,
    )

    def _close() -> None:
        if flow.popup is not None:
            flow.popup.close()

    with hui.action_row():
        hui.confirm_button("Done", on_click=_close)
