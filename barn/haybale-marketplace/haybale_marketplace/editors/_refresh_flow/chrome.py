"""Popup entry point and step→panel wiring for the Refresh Libraries flow."""

from __future__ import annotations

from typing import Callable

from nicegui import ui

from haywire.ui.components.stepper import Panel, show_step_flow

from ._state import RefreshFlow, RefreshSource
from .panels import _panel_applied, _panel_fetched, _panel_resolved, _panel_sources


def show_refresh_flow(
    state: RefreshSource,
    *,
    on_done: Callable[[], None] | None = None,
    on_edit_global: Callable[[], None] | None = None,
) -> RefreshFlow:
    """Open the Refresh Libraries flow and return its state machine.

    *on_done* fires when the popup closes — the caller re-renders its list
    there, since an applied refresh rewrites the project cache the list reads
    from. *on_edit_global* wires the Edit File affordance the malformed-file
    error offers; omit it and that error renders as a plain message.
    """
    flow = RefreshFlow(state=state)

    panels: dict[str, Panel[RefreshFlow]] = {
        "sources": _panel_sources,
        "fetched": _panel_fetched,
        "resolved": _panel_resolved,
        "applied": lambda f, _rerender: _panel_applied(f, None),
    }

    def _error_detail(f: RefreshFlow, _rerender: Callable[[], None]) -> bool:
        """Offer Edit File for the one error a retry cannot fix."""
        if not f.malformed or on_edit_global is None:
            return False
        ui.label(f.error or "").classes("text-xs hw-text-danger whitespace-pre-line")
        ui.label("A malformed file stays malformed on retry — repair it first, then fetch again.").classes(
            "text-xs hw-text-dim"
        )

        def _edit() -> None:
            if flow.popup is not None:
                flow.popup.close()
            on_edit_global()

        ui.button("Edit File", on_click=_edit).props("flat dense")
        return True

    flow.popup = show_step_flow(
        flow,
        panels,
        title="Refresh Libraries",
        width="620px",
        on_done=on_done,
        error_detail=_error_detail,
    )
    return flow
