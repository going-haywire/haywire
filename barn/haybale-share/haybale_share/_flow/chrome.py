"""Popup entry point and step→panel wiring for the Share flow."""

from __future__ import annotations

from pathlib import Path
from typing import Callable

from haywire.core.publishing.pipeline import SharePipeline
from haywire.ui.components.stepper import Panel, show_step_flow

from ._state import ShareFlow
from .panels import panel_done, panel_preflight, panel_publish, panel_review


def show_share_flow(
    repo_root: Path,
    *,
    on_done: Callable[[], None] | None = None,
) -> ShareFlow:
    """Open the Share flow and return its state machine.

    ``auto_start`` runs preflight the moment the popup opens: it only checks,
    writes nothing, and the user already expressed the intent by opening this.
    A "Check" button there would ask them to confirm it twice.

    No ``error_detail`` override. The predecessor relabelled the error banner's
    button "Solve" and opened a remedy modal from it; preflight now renders its
    own failures inline, so the banner is only ever reached by a step that has
    a plain retry.
    """
    flow = ShareFlow(pipeline=SharePipeline(repo_root))

    panels: dict[str, Panel[ShareFlow]] = {
        "preflight": panel_preflight,
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
        auto_start=True,
    )
    return flow
