"""Popup entry point, progress bar, error banner, and step dispatch."""

from __future__ import annotations

from pathlib import Path
from typing import Callable

from nicegui import ui

from haywire.ui import elements as hui
from haywire.ui.components.popup import Popup
from haywire_studio.packaging.share.pipeline import SharePipeline

from .copy import STEPS, _STEP_TITLES
from .panels import (
    _panel_checked,
    _panel_commit,
    _panel_docs,
    _panel_done,
    _panel_drift,
    _panel_preconditions,
    _panel_push,
    _panel_version,
    _render_fix,
)
from ._state import ShareWizard


def show_share_wizard(
    repo_root: Path,
    *,
    on_done: Callable[[], None] | None = None,
) -> ShareWizard:
    """Open the Share Project wizard and return its state machine.

    Not closable mid-flight past the commit step: the popup's own close button
    stays available (the wizard mutates nothing that needs undoing), but the
    step buttons are the intended path.
    """
    popup = Popup(
        title="Share Project",
        width="620px",
        closable=True,
        backdrop_click_close=False,
        escape_close=False,
    )
    wizard = ShareWizard(pipeline=SharePipeline(repo_root), popup=popup)

    with popup:
        body = ui.column().classes("w-full gap-2")

    def _render() -> None:
        body.clear()
        with body:
            _render_progress(wizard)
            _render_step(wizard, _render, on_done)

    wizard.on_render = _render
    _render()
    popup.open()
    return wizard


def _render_progress(wizard: ShareWizard) -> None:
    """A one-line step indicator. Colours come from --hw-* tokens only."""
    index = STEPS.index(wizard.step)
    with ui.row().classes("w-full items-center gap-1"):
        for position, name in enumerate(STEPS[:-1]):
            done = position < index
            active = position == index
            colour = "var(--hw-positive)" if done else ("var(--hw-accent)" if active else "var(--hw-border)")
            ui.element("div").classes("flex-1 rounded").style(f"height: 3px; background: {colour};").tooltip(
                _STEP_TITLES[name]
            )
    ui.label(_STEP_TITLES[wizard.step]).classes("text-sm font-medium")


def _render_error(wizard: ShareWizard, rerender: Callable[[], None]) -> None:
    """Inline error banner with a Retry button. Same visual as the progress modal."""
    if wizard.error is None:
        return
    with (
        ui.row()
        .classes("w-full items-start gap-2 p-2 rounded")
        .style("border-left: 3px solid var(--hw-danger); background: var(--hw-danger-bg);")
    ):
        ui.icon("error", size="16px").classes("hw-text-danger flex-shrink-0 mt-0.5")
        with ui.column().classes("gap-1 flex-1"):
            if wizard.precondition_failures:
                # Structured failures: each gets its own message + remedy row
                # so a multi-line remedy (install commands, etc.) stays
                # readable instead of collapsing into wizard.error's one line.
                with ui.column().classes("gap-2 w-full"):
                    for failure in wizard.precondition_failures:
                        with ui.column().classes("gap-0.5"):
                            ui.label(failure.message).classes("text-xs hw-text-danger whitespace-pre-line")
                            if failure.remedy:
                                ui.label(failure.remedy).classes(
                                    "text-xs hw-text-dim font-mono whitespace-pre-line"
                                )
                            if failure.fix_id:
                                _render_fix(wizard, rerender, failure)
            else:
                ui.label(wizard.error).classes("text-xs hw-text-danger whitespace-pre-line")
            if wizard.manual_command:
                hui.code_snippet(wizard.manual_command)

    def _retry() -> None:
        wizard.retry()
        rerender()

    ui.button("Retry", on_click=_retry).props("flat dense")


def _render_warnings(wizard: ShareWizard) -> None:
    for warning in wizard.warnings:
        with ui.row().classes("w-full items-start gap-2"):
            ui.icon("warning", size="14px").classes("flex-shrink-0 mt-0.5").style(
                "color: var(--hw-warning);"
            )
            ui.label(warning).classes("text-xs hw-text-muted")


def _render_step(
    wizard: ShareWizard,
    rerender: Callable[[], None],
    on_done: Callable[[], None] | None,
) -> None:
    """Dispatch to the current step's panel."""
    _render_warnings(wizard)
    _render_error(wizard, rerender)

    if wizard.step == "preconditions":
        _panel_preconditions(wizard, rerender)
    elif wizard.step == "checked":
        _panel_checked(wizard, rerender)
    elif wizard.step == "drift":
        _panel_drift(wizard, rerender)
    elif wizard.step == "version":
        _panel_version(wizard, rerender)
    elif wizard.step == "docs":
        _panel_docs(wizard, rerender)
    elif wizard.step == "commit":
        _panel_commit(wizard, rerender)
    elif wizard.step == "push":
        _panel_push(wizard, rerender)
    else:
        _panel_done(wizard, on_done)
