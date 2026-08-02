"""The framework update flow, behind the shell's ⟳ control.

Pin-bump only — no in-process ``uv sync``. ``uv run`` syncs by default, so
``uv run haywire`` installs the new pin at launch. Deferring the sync collapses
the mixed-version window to zero and sidesteps the Windows lock on the running
``haywire.exe`` entirely (upgrading haywire-studio means replacing it while it
runs, and DeleteFileW fails on files with open handles).

Flow: check → what-happens explainer → conflict check → unsaved-work
confirmation → pin write → app.shutdown().
"""

from __future__ import annotations

import asyncio
from pathlib import Path

from nicegui import app, ui

from haywire.core.update import check_for_update, check_pin_conflict, rewrite_pins
from haywire.core.update.confirmed import confirm_update
from haywire.ui import elements as hui
from haywire.ui.components.popup import Popup


def open_update_dialog(project_root: Path) -> None:
    """Run the whole check-and-pin flow in one popup."""
    popup = Popup(
        title="Check for updates",
        width="420px",
        closable=True,
        backdrop_click_close=False,
        escape_close=False,
    )
    with popup:
        body = ui.column().classes("w-full gap-2")
    popup.open()

    async def _check() -> None:
        body.clear()
        with body:
            ui.label("Checking PyPI…").classes("text-sm hw-text-muted")
        status = await asyncio.to_thread(check_for_update)

        body.clear()
        with body:
            if not status.reachable:
                # "Couldn't reach PyPI" and "you're up to date" are different
                # answers; collapsing them would be a comforting lie.
                ui.label("Couldn't reach PyPI. Try again later.").classes("text-sm")
                ui.button("Close", on_click=popup.close).props("flat dense")
                return
            if not status.available:
                ui.label(f"Haywire {status.installed} — you're up to date.").classes("text-sm")
                ui.button("Close", on_click=popup.close).props("flat dense")
                return
            _render_explainer(status.installed, status.latest or "")

    def _render_explainer(installed: str, latest: str) -> None:
        ui.label(f"Haywire {latest} is available").classes("text-base font-bold")
        ui.label(f"You're on {installed}.").classes("text-xs hw-text-muted")
        hui.section_label("What happens")
        with ui.column().classes("gap-0.5 ml-1"):
            ui.label("1. Your pyproject.toml pin is updated").classes("text-xs")
            ui.label("2. Studio quits").classes("text-xs")
            ui.label("3. You run `uv run haywire` — the new version installs on launch").classes("text-xs")
        with ui.row().classes("w-full justify-end gap-2"):
            ui.button("Cancel", on_click=popup.close).props("flat dense")
            ui.button(
                "Continue",
                on_click=lambda: _run_conflict_check(installed, latest),
            ).props("flat dense").style("color: var(--hw-positive);")

    async def _run_conflict_check(installed: str, latest: str) -> None:
        body.clear()
        with body:
            ui.label("checking…").classes("text-sm hw-text-muted")
        result = await asyncio.to_thread(check_pin_conflict, project_root, latest)

        body.clear()
        with body:
            if not result.ok:
                ui.label("Update blocked").classes("text-base font-bold")
                ui.label(result.message).classes("text-xs font-mono whitespace-pre-wrap")
                ui.label("Update or remove the conflicting library first. Nothing was written.").classes(
                    "text-xs hw-text-muted"
                )
                ui.button("Close", on_click=popup.close).props("flat dense")
                return
            # Framing matters: resolution is not installation. The real sync
            # happens later inside `uv run`, unsupervised.
            ui.label("No conflicts found.").classes("text-sm")
            if result.changes:
                with ui.column().classes("gap-0 ml-1 max-h-40 overflow-auto"):
                    for line in result.changes:
                        ui.label(line).classes("text-xs font-mono hw-text-muted")
            ui.label("Unsaved work will be lost.").classes("text-xs").style("color: var(--hw-warning);")
            with ui.row().classes("w-full justify-end gap-2"):
                ui.button("Cancel", on_click=popup.close).props("flat dense")
                ui.button(
                    "Continue anyway",
                    on_click=lambda: _write_and_quit(installed, latest),
                ).props("flat dense").style("color: var(--hw-warning);")

    def _write_and_quit(installed: str, latest: str) -> None:
        pyproject = project_root / "pyproject.toml"
        pyproject.write_text(rewrite_pins(pyproject, latest), encoding="utf-8")
        # One flag, so the banner and the exit code cannot disagree.
        confirm_update(installed, latest)
        popup.close()
        # Graceful: under reload=False this takes the should_exit branch, so
        # lifespan handlers run and the Farmhand MCP host stops cleanly — the
        # exact path os.execv would have bypassed.
        app.shutdown()

    ui.timer(0.05, _check, once=True)
