"""Popup entry point, step→panel wiring, and the marketplace adapter."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Callable, Optional

from nicegui import ui

from haywire.core.library.haybale import Haybale
from haywire.core.marketstall import RefreshReport, ResolvedSource
from haywire.ui.components.stepper import Panel, show_step_flow

from ._state import AddSourceFlow, AddSourceTarget
from .panels import (
    _panel_added,
    _panel_input,
    _panel_probed,
    _panel_refreshed,
    _panel_resolved,
)

logger = logging.getLogger(__name__)


class MarketplaceAddSourceTarget:
    """Adapts the marketplace config + state to :class:`AddSourceTarget`.

    The five operations live in three different places — core's subscribe
    module, core's helpers, and MarketplaceState — so this gathers them
    rather than making the flow reach into all three.
    """

    def __init__(self, state) -> None:
        self._state = state

    @property
    def _global_path(self) -> Path:
        from haybale_marketplace.config import GLOBAL_MARKETPLACE_DIR

        return GLOBAL_MARKETPLACE_DIR / "marketplace.toml"

    @property
    def _paste_dir(self) -> Path:
        from haybale_marketplace.config import GLOBAL_MARKETPLACE_DIR

        return GLOBAL_MARKETPLACE_DIR / "stalls"

    def resolve_source(self, user_input: str) -> ResolvedSource:
        from haywire.core.marketstall import resolve_source

        return resolve_source(user_input)

    def existing_haybales(self) -> list[Haybale]:
        """What the project already resolves to — the collision baseline.

        This is the *last refresh's* result, so a source subscribed but not
        yet refreshed is invisible here and its collisions are not prompted for
        at add time. Narrowed rather than fixed: refresh now detects standing
        collisions across all subscribed sources and surfaces them on its
        resolved step, so anything missed here shows up on the next refresh
        instead of staying hidden. Closing the gap at *this* point would mean
        probing every subscribed source on add — see
        internals/handoff/marketplace-blocked-category-and-source-conflicts.md.
        """
        return self._state.get_project_haybales()

    def subscribe(self, resolved: ResolvedSource) -> str:
        from haywire.core.marketstall import subscribe

        result = subscribe(resolved, self._global_path, paste_dir=self._paste_dir)
        return result.persist_url

    def record_preference(self, source_url: str, haybale_name: str) -> None:
        from haywire.core.marketstall import record_preference

        record_preference(self._global_path, source_url=source_url, haybale_name=haybale_name)

    def refresh(self) -> RefreshReport:
        return self._state.refresh()


def show_add_source_flow(
    target: AddSourceTarget,
    *,
    on_done: Callable[[], None] | None = None,
) -> AddSourceFlow:
    """Open the Add Source flow and return its state machine.

    *on_done* fires when the popup closes — the caller re-renders its list
    there, since a completed flow may have added a source and refreshed.
    """
    flow = AddSourceFlow(target=target)

    panels: dict[str, Panel[AddSourceFlow]] = {
        "input": _panel_input,
        "probed": _panel_probed,
        "resolved": _panel_resolved,
        "added": _panel_added,
        # on_done fires from the popup's close handler, so Done only dismisses.
        "refreshed": lambda f, _rerender: _panel_refreshed(f, None),
    }

    flow.popup = show_step_flow(
        flow,
        panels,
        title="Add Source",
        width="620px",
        on_done=on_done,
        error_detail=_error_detail,
    )
    return flow


def _error_detail(flow: AddSourceFlow, _rerender: Callable[[], None]) -> bool:
    """Explain a rejected input, where Retry alone cannot help."""
    if not flow.rejected_input:
        return False
    ui.label(flow.error or "").classes("text-xs hw-text-danger whitespace-pre-line")
    ui.label("Edit the field above to point at the marketstall.toml itself, then probe again.").classes(
        "text-xs hw-text-dim"
    )
    return True


def build_target(context) -> Optional[MarketplaceAddSourceTarget]:
    """Adapter for *context*, or None when marketplace state is unavailable."""
    from haybale_marketplace.state.marketplace_state import MarketplaceState

    if context.app_data is None or MarketplaceState not in context.app_data:
        return None
    return MarketplaceAddSourceTarget(context.app_data[MarketplaceState])
