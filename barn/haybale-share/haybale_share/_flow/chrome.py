"""Popup entry point and step→panel wiring for the Share flow."""

from __future__ import annotations

from pathlib import Path
from typing import Callable

from haywire.core.publishing.pipeline import SharePipeline
from haywire.ui.components.stepper import Panel, show_step_flow

from ._state import ShareFlow
from .panels import (
    panel_done,
    panel_edit,
    panel_preflight,
    panel_publish,
    panel_review,
    suppress_duplicate_error,
)


def show_share_flow(
    repo_root: Path,
    *,
    on_done: Callable[[], None] | None = None,
) -> ShareFlow:
    """Open the Share flow and return its state machine.

    ``auto_start`` runs preflight the moment the popup opens: it only checks,
    writes nothing, and the user already expressed the intent by opening this.
    A "Check" button there would ask them to confirm it twice.

    ``error_detail`` suppresses the banner's message for the two states whose
    panels lay the failure out themselves — a preflight failure and a
    post-commit push failure. ``flow.error`` is ``str(exception)``, which for
    both is a CLI-shaped string already containing everything the panel just
    rendered as real UI, so letting the banner print it too showed every line
    twice. It does NOT relabel the button the way the predecessor did (that
    hook is gone from core); those two panels own their own buttons.
    """
    flow = ShareFlow(pipeline=SharePipeline(repo_root))

    panels: dict[str, Panel[ShareFlow]] = {
        "preflight": panel_preflight,
        "edit": panel_edit,
        "review": panel_review,
        "publish": panel_publish,
        "done": panel_done,
    }

    flow.popup = show_step_flow(
        flow,
        panels,
        title="Share Project",
        width="640px",
        on_done=on_done,
        error_detail=suppress_duplicate_error,
        auto_start=True,
    )
    return flow
