"""The Refresh Libraries flow's state machine, free of NiceGUI calls.

Three steps over the three phases of the marketstall refresh pipeline:

    sources   read the config, list what will be contacted   → Fetch
    fetched   per-source outcome, nothing written yet        → Resolve
    resolved  the deltas a write would produce               → Apply
    applied   terminal

The split exists so the user sees "3 libraries will go stale, 2 sources were
unreachable" *before* the project cache is overwritten. Abandoning the flow at
any step before Apply leaves the project file exactly as it was.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Optional, Protocol

from haywire.core.marketstall import (
    FetchedSources,
    MalformedMarketplaceError,
    MarketplaceFile,
    RefreshReport,
    ResolvedCatalog,
)
from haywire.ui.components.popup import Popup
from haywire.ui.components.stepper import StepFlow

from .copy import STEP_TITLES, STEPS

logger = logging.getLogger(__name__)


class RefreshSource(Protocol):
    """The slice of :class:`MarketplaceState` this flow drives.

    Narrowed to a protocol so the flow depends on the four phase methods
    rather than on the state class and everything it pulls in (DI, the
    workspace root) — which also lets the tests drive it with test-owned
    paths.
    """

    def get_global(self) -> MarketplaceFile | None: ...

    def fetch_sources(self) -> FetchedSources | None: ...

    def resolve(self, fetched: FetchedSources) -> ResolvedCatalog: ...

    def apply_refresh(self, fetched: FetchedSources, resolved: ResolvedCatalog) -> RefreshReport: ...

    def prefer_source(self, name: str, *, source_url: str) -> None: ...


class RefreshFlow(StepFlow):
    """Linear, resumable state machine for the Refresh Libraries flow."""

    STEPS = STEPS
    STEP_TITLES = STEP_TITLES

    def __init__(self, *, state: RefreshSource, popup: Optional[Popup] = None) -> None:
        super().__init__()
        self.state = state
        self.popup = popup

        self.fetched: FetchedSources | None = None
        self.resolved: ResolvedCatalog | None = None
        self.report: RefreshReport | None = None
        #: Set when the global marketplace file is malformed — the one failure
        #: the user repairs in an editor rather than by retrying.
        self.malformed: bool = False

    def retry(self) -> None:
        super().retry()
        self.malformed = False

    def fail(self, exc: BaseException) -> None:
        super().fail(exc)
        self.malformed = isinstance(exc, MalformedMarketplaceError)

    async def advance_from_sources(self) -> None:
        """Fetch every subscription. One HTTP round-trip per source, so: a thread.

        On the event loop these would starve NiceGUI's heartbeat and the
        browser would show "connection lost" — the same reason the share
        wizard threads its ``git ls-remote``.
        """
        self.retry()
        try:
            self.fetched = await asyncio.to_thread(self.state.fetch_sources)
        except MalformedMarketplaceError as exc:
            self.fail(exc)
            return
        except Exception as exc:  # noqa: BLE001 — surfaced inline, never swallowed
            self.fail(exc)
            return
        if self.fetched is None:
            self.error = "No project open — refresh works on a haywire project directory."
            return
        self.step = "fetched"

    async def advance_from_fetched(self) -> None:
        """Resolve the catalog. Pure and fast, so it stays on the event loop."""
        self.retry()
        fetched = self.fetched
        if fetched is None:  # pragma: no cover — unreachable via the panels
            self.error = "Nothing fetched yet."
            return
        try:
            self.resolved = self.state.resolve(fetched)
        except Exception as exc:  # noqa: BLE001 — surfaced inline, never swallowed
            self.fail(exc)
            return
        self.step = "resolved"

    def prefer_source(self, name: str, *, source_url: str) -> None:
        """Resolve a standing collision by naming the source that should win.

        Writes `preference` on the chosen source, then re-resolves in place so
        the panel immediately reflects it. Stays on the `resolved` step: this
        changes what a refresh *would* do, it does not perform one, and the
        project cache is still untouched.

        The re-resolve reads the global file again rather than reusing the
        parsed copy on `fetched` — that copy predates the write and would
        resolve to the same winner, making the click look inert. Only the cheap
        parse is redone; the fetched bodies are reused, so no source is
        contacted a second time.
        """
        self.retry()
        fetched = self.fetched
        if fetched is None:  # pragma: no cover — unreachable via the panels
            self.error = "Nothing fetched yet."
            return
        try:
            self.state.prefer_source(name, source_url=source_url)
            reparsed = self.state.get_global()
            if reparsed is not None:
                fetched.global_file = reparsed
            self.resolved = self.state.resolve(fetched)
        except Exception as exc:  # noqa: BLE001 — surfaced inline, never swallowed
            self.fail(exc)

    async def advance_from_resolved(self) -> None:
        """Write the project cache. The only step that mutates anything."""
        self.retry()
        fetched, resolved = self.fetched, self.resolved
        if fetched is None or resolved is None:  # pragma: no cover
            self.error = "Nothing resolved yet."
            return
        try:
            self.report = await asyncio.to_thread(self.state.apply_refresh, fetched, resolved)
        except Exception as exc:  # noqa: BLE001 — surfaced inline, never swallowed
            self.fail(exc)
            return
        if resolved.newly_stale:
            self.warnings.append(
                f"{len(resolved.newly_stale)} librar"
                + ("y is" if len(resolved.newly_stale) == 1 else "ies are")
                + " no longer offered by any source and stay listed as stale."
            )
        self.step = "applied"
