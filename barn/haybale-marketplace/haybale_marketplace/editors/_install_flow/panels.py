"""Per-step body content for the Install / Update Library flow."""

from __future__ import annotations

from typing import Callable

from nicegui import ui

from haywire.core.library.identity import LibraryReloadAction
from haywire.ui import elements as hui
from haywire.ui.components.stepper import busy_advance
from haywire.ui.modals import restart_affordance

from ._state import InstallFlow


def _plural(count: int, singular: str, plural: str | None = None) -> str:
    return f"{count} {singular if count == 1 else (plural or singular + 's')}"


def _panel_selected(flow: InstallFlow, rerender: Callable[[], None]) -> None:
    """What is about to be installed, and from where. Nothing resolved yet."""
    verb = "Update" if flow.is_update else "Install"
    ui.label(f"{verb} {flow.name}").classes("text-sm font-medium")

    if flow.is_update and flow.target_version:
        ui.label(f"{flow.current_version} → {flow.target_version}").classes("text-xs font-mono hw-text-dim")
    elif flow.target_version:
        ui.label(f"version {flow.target_version}").classes("text-xs font-mono hw-text-dim")

    pkg = flow.package
    if pkg is not None and pkg.source_url:
        hui.info_row("Source", pkg.source_url)

    if not flow.is_update:
        ui.label(
            "Installing runs code from this source in your environment. Only install "
            "libraries from publishers you trust."
        ).classes("text-xs hw-text-muted")

    ui.label("Next: ask the resolver what this would change. That check installs nothing.").classes(
        "text-xs hw-text-dim"
    )

    with ui.row().classes("w-full justify-end gap-2"):
        check = ui.button("Check").props("flat dense").style("color: var(--hw-positive);")
        check.on_click(lambda: busy_advance(rerender, check, flow.advance_from_selected))


def _panel_checked(flow: InstallFlow, rerender: Callable[[], None]) -> None:
    """The resolver's answer — the informed-decision point."""
    removals = flow.removals or []

    if not removals:
        with ui.row().classes("w-full items-center gap-2"):
            ui.icon("check_circle", size="16px").style("color: var(--hw-positive);")
            ui.label("Resolved cleanly — nothing else changes.").classes("text-sm").style(
                "color: var(--hw-positive);"
            )
    else:
        with ui.row().classes("w-full items-center gap-2"):
            ui.icon("warning", size="16px").style("color: var(--hw-warning);")
            ui.label(f"{_plural(len(removals), 'other package')} will be replaced to make room.").classes(
                "text-sm"
            ).style("color: var(--hw-warning);")
        with ui.column().classes("gap-0.5 ml-1"):
            for name in removals:
                ui.label(name).classes("text-xs font-mono hw-text-dim")
        ui.label(
            "Those libraries are removed from the registry before the install and "
            "reloaded afterwards, so a restart is recommended when this finishes."
        ).classes("text-xs hw-text-muted")

    with ui.row().classes("w-full justify-end gap-2"):
        install = ui.button("Install").props("flat dense").style("color: var(--hw-positive);")
        install.on_click(lambda: busy_advance(rerender, install, flow.run_install))


def _panel_installing(flow: InstallFlow, rerender: Callable[[], None]) -> None:
    """Live uv output. Rendered mid-flight; the step has no button of its own.

    The spinner and elapsed counter are the liveness signal, and they are
    deliberately independent of the log: uv goes quiet for tens of seconds
    while a large package downloads, and a still log with nothing else moving
    is indistinguishable from a hang.
    """
    running = flow.error is None

    with ui.row().classes("w-full items-center gap-2"):
        if running:
            ui.spinner(size="sm")
        ui.label(f"Installing {flow.name}…").classes("text-sm font-medium")
        elapsed = ui.label("").classes("text-xs hw-text-dim ml-auto")

    def _tick() -> None:
        elapsed.text = f"{int(flow.elapsed)}s"

    _tick()
    if running:
        # Owned by this panel: the timer is deleted with it on the next
        # re-render, so it cannot outlive the step it is reporting on.
        ui.timer(1.0, _tick)

    log = ui.log(max_lines=200).classes("w-full h-40")
    for line in flow.log_lines:
        log.push(line)
    flow.attach_log(log)

    if running:
        ui.label("Large packages can take a minute, and uv stays quiet while it downloads.").classes(
            "text-xs hw-text-muted"
        )

    if flow.error is not None:
        # A failed install stays here; the shared chrome renders the message
        # and its Retry, which re-runs the install in place.
        with ui.row().classes("w-full justify-end gap-2"):
            retry = ui.button("Try again").props("flat dense")
            retry.on_click(lambda: busy_advance(rerender, retry, flow.advance_from_installing))


def _panel_done(flow: InstallFlow, on_done: Callable[[], None] | None) -> None:
    verb = "updated" if flow.is_update else "installed"
    with ui.row().classes("w-full items-center gap-2"):
        ui.icon("check_circle", size="16px").style("color: var(--hw-positive);")
        ui.label(f"{flow.name} {verb}.").classes("text-sm").style("color: var(--hw-positive);")

    if flow.log_lines:
        with ui.expansion("Output").classes("w-full"):
            log = ui.log(max_lines=200).classes("w-full h-32")
            for line in flow.log_lines:
                log.push(line)

    action = getattr(flow.hints, "action", LibraryReloadAction.NONE)
    if action is LibraryReloadAction.RESTART:
        restart_affordance(
            reason=f"{flow.name} cannot be loaded into the running Studio process.",
            compact=True,
        )
    elif action is LibraryReloadAction.REFRESH:
        with ui.row().classes("w-full items-center gap-2"):
            ui.icon("refresh", size="16px").classes("hw-text-muted")
            ui.label("Reload the page to use the new library.").classes("text-xs hw-text-muted")

    def _close() -> None:
        if flow.popup is not None:
            flow.popup.close()

    with ui.row().classes("w-full justify-end gap-2"):
        ui.button("Done", on_click=_close).props("flat dense").style("color: var(--hw-positive);")
