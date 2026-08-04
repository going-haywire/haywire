"""Popup entry point and step→panel wiring for the Share Project wizard.

The progress bar, error banner and warning rows are the shared stepper
chrome; what stays here is the share-specific part — the panel map and the
structured ``PreconditionFailure`` rows that replace the generic one-line
error message.
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Callable

from nicegui import ui

from haywire.ui.components.stepper import Panel, show_step_flow
from haywire_studio.packaging.share.pipeline import SharePipeline

from ._state import ShareWizard
from .panels import (
    _panel_checked,
    _panel_commit,
    _panel_docs,
    _panel_done,
    _panel_drift,
    _panel_framework,
    _panel_preconditions,
    _panel_push,
    _panel_version,
    _render_fix,
)

if TYPE_CHECKING:
    from haybale_marketplace.library_manager import LibraryManager


def show_share_wizard(
    repo_root: Path,
    *,
    manager: "LibraryManager | None" = None,
    on_done: Callable[[], None] | None = None,
) -> ShareWizard:
    """Open the Share Project wizard and return its state machine.

    Not closable mid-flight past the commit step: the popup's own close button
    stays available (the wizard mutates nothing that needs undoing), but the
    step buttons are the intended path.

    *manager* lets the version-bump step hot-swap the live registry after
    writing new @library(version=...) decorators (see
    ShareWizard._hot_swap_bumped_libraries). Pass None to skip that — the
    bump is then file-only, exactly as before.
    """
    wizard = ShareWizard(pipeline=SharePipeline(repo_root), popup=None, manager=manager)

    panels: dict[str, Panel[ShareWizard]] = {
        "preconditions": _panel_preconditions,
        "checked": _panel_checked,
        "drift": _panel_drift,
        "framework": _panel_framework,
        "version": _panel_version,
        "docs": _panel_docs,
        "commit": _panel_commit,
        "push": _panel_push,
        # on_done fires from the popup's close handler below, so the Done
        # button only has to dismiss — otherwise closing after Done would run
        # the callback twice.
        "done": lambda flow, _rerender: _panel_done(flow, None),
    }

    wizard.popup = show_step_flow(
        wizard,
        panels,
        title="Share Project",
        width="620px",
        on_done=on_done,
        error_detail=_render_precondition_failures,
    )
    return wizard


def _render_precondition_failures(flow: ShareWizard, rerender: Callable[[], None]) -> bool:
    """Render each structured failure as its own message/remedy row.

    A multi-line remedy (install commands, etc.) stays readable this way
    instead of collapsing into ``flow.error``'s one line. Returns False when
    the wizard has no structured failures, which leaves the shared chrome to
    render the plain message.
    """
    if not flow.precondition_failures:
        return False
    with ui.column().classes("gap-2 w-full"):
        for failure in flow.precondition_failures:
            with ui.column().classes("gap-0.5"):
                ui.label(failure.message).classes("text-xs hw-text-danger whitespace-pre-line")
                if failure.remedy:
                    ui.label(failure.remedy).classes("text-xs hw-text-dim font-mono whitespace-pre-line")
                if failure.fix_id:
                    _render_fix(flow, rerender, failure)
    return True
