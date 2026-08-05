"""Popup entry point and step→panel wiring for the Share Project wizard.

The progress bar, error banner and warning rows are the shared stepper
chrome; what stays here is the share-specific part — the panel map, plus
``error_detail=_precondition_error_detail``, which turns the step-1 error
banner's default "Retry" into "Solve" (opens the remedy modal instead of
just clearing the error). Remedy modals (for step-1 failures) and the
rollback modal (for mid-pipeline failures) are opened from the panels
themselves, not from this shell — see ``remedy_modal.py`` and
``panels.py::_drain_pending_modal``/``_precondition_error_detail``.
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Callable

from haywire.ui.components.stepper import Panel, show_step_flow
from haywire.core.publishing.pipeline import SharePipeline

from ._state import ShareWizard
from .panels import (
    _panel_checked,
    _panel_commit,
    _panel_docs,
    _panel_done,
    _panel_confirm,
    _panel_detect,
    _panel_floors,
    _panel_framework,
    _panel_unused,
    _panel_undeclared,
    _panel_preconditions,
    _panel_push,
    _panel_version,
    _precondition_error_detail,
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
        "detect": _panel_detect,
        "framework": _panel_framework,
        "unused": _panel_unused,
        "undeclared": _panel_undeclared,
        "floors": _panel_floors,
        "confirm": _panel_confirm,
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
        error_detail=_precondition_error_detail,
    )
    return wizard
