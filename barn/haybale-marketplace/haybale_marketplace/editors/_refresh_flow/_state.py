"""The Refresh Libraries flow's state machine, free of NiceGUI calls.

Steps over the three phases of the marketstall refresh pipeline:

    sources   read the config, list what will be contacted   → Fetch
    fetched   per-source outcome, nothing written yet        → Resolve
    conflicts several libraries claim one name (stopped at only then) → Settle
    resolved  the deltas a write would produce               → Apply
    applied   terminal

The split exists so the user sees "3 libraries will go stale, 2 sources were
unreachable" *before* the project cache is overwritten. Abandoning the flow at
any step before Apply leaves the project file exactly as it was.

The ``conflicts`` step is *stopped at* only when the resolve found several
different libraries claiming one name, which the marketplace has no namespace
to prevent. It stays in the step list either way so the progress bar keeps its
length for the whole run; the common path steps straight over it.
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass
from typing import Optional, Protocol

from haywire.core.library.haybale import Haybale
from haywire.core.marketstall import (
    FetchedSources,
    MalformedMarketplaceError,
    MarketplaceFile,
    RefreshReport,
    ResolvedCatalog,
    SourceCollision,
)
from haywire.ui.components.popup import Popup
from haywire.ui.components.stepper import StepFlow

from .copy import STEP_TITLES, STEPS

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class Claimant:
    """One source's claim on a contested library name.

    Rendered as a row in the name-conflict step. Blocked claimants stay in the
    list — that is what makes a block a reversible choice rather than the
    claimant having vanished — so the row carries both the current state and
    what may be done about it.
    """

    url: str
    """Where the copy came from, as shown to the user."""

    owner_url: str
    """The subscription a block writes against. Differs from ``url`` only for a
    stall discovered through an aggregator, which cannot be subscribed to
    directly."""

    version: str
    label: str
    origin: str
    blocked: bool
    installed: bool

    @property
    def can_block(self) -> bool:
        """False for the copy already installed here.

        Blocking it would leave the catalog offering another author's code
        under the name this environment is already running — the exact
        substitution the step exists to prevent. Uninstall first to switch.
        """
        return not self.installed


class RefreshSource(Protocol):
    """The slice of :class:`MarketplaceState` this flow drives.

    Narrowed to a protocol so the flow depends on the phase methods rather than
    on the state class and everything it pulls in (DI, the workspace root) —
    which also lets the tests drive it with test-owned paths.
    """

    def get_global(self) -> MarketplaceFile | None: ...

    def fetch_sources(self) -> FetchedSources | None: ...

    def resolve(self, fetched: FetchedSources) -> ResolvedCatalog: ...

    def apply_refresh(self, fetched: FetchedSources, resolved: ResolvedCatalog) -> RefreshReport: ...

    def prefer_source(self, name: str, *, source_url: str) -> None: ...

    def installed_row(self, name: str) -> Haybale | None: ...

    def block_source(self, name: str, *, source_url: str) -> None: ...

    def unblock_source(self, name: str, *, source_url: str) -> None: ...


class RefreshFlow(StepFlow):
    """Linear, resumable state machine for the Refresh Libraries flow.

    The step list is fixed for the whole run, including the ``conflicts`` step
    most refreshes never stop at — see :meth:`_route_after_resolve`.
    """

    STEPS = STEPS
    STEP_TITLES = STEP_TITLES

    def __init__(self, *, state: RefreshSource, popup: Optional[Popup] = None) -> None:
        super().__init__()
        self.state = state
        self.popup = popup

        self.fetched: FetchedSources | None = None
        self.resolved: ResolvedCatalog | None = None
        #: Name conflicts found by the resolve — several unrelated libraries
        #: claiming one name. Empty on the overwhelmingly common path, where
        #: the step they gate is stepped over rather than shown.
        self.conflicts: list[SourceCollision] = []
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
        self._route_after_resolve()

    def _route_after_resolve(self) -> None:
        """Stop at the conflicts step, or step over it when there is nothing to settle.

        The step is *skipped*, never removed: the progress bar is redrawn from
        ``STEPS`` on every render, so dropping a step here would shrink the bar
        mid-flow and dropping one in later would grow it. A fixed list costs a
        segment the common path walks straight past, which is much less
        confusing than a bar that changes length while you use it.

        A conflict already settled on a previous run still stops here — the
        blocks are read back from the global file and rendered as the choice
        that was made, so the user can see it and change their mind.
        """
        self.conflicts = self._detect_conflicts(self.resolved)
        self.step = "conflicts" if self.conflicts else "resolved"

    def _detect_conflicts(self, resolved: ResolvedCatalog | None) -> list[SourceCollision]:
        """Contested names, including ones a previous run already settled.

        The resolve only reports a collision while two claimants survive its
        filters, so a name settled by blocking every rival but one no longer
        collides — and would silently skip the step that records the decision.
        Re-checking the unfiltered candidates keeps a settled conflict visible
        and reversible instead of disappearing the moment it is resolved.
        """
        conflicts = [c for c in (resolved.collisions if resolved else []) if not c.same_library]
        seen = {c.name for c in conflicts}
        for name in self._settled_conflict_names():
            if name in seen:
                continue
            conflicts.append(
                SourceCollision(name=name, winner_url="", winner_version="", same_library=False)
            )
        return conflicts

    def _settled_conflict_names(self) -> list[str]:
        """Names whose rival claimants are all blocked — a settled conflict."""
        fetched = self.fetched
        if fetched is None:  # pragma: no cover — unreachable via the panels
            return []
        from haybale_marketplace.identity import identity_matches
        from haywire.core.marketstall import candidate_haybales

        by_name: dict[str, list[Haybale]] = {}
        for hb in candidate_haybales(fetched, honour_blocked=False):
            by_name.setdefault(hb.name, []).append(hb)

        return [
            name
            for name, group in by_name.items()
            if len(group) > 1 and not all(identity_matches(group[0], other) for other in group[1:])
        ]

    def claimants_for(self, name: str) -> list[Claimant]:
        """Every source offering *name*, blocked ones included.

        Read from the fetched bodies rather than the resolve, because the
        resolve drops blocked names: a claimant the user just blocked has to
        stay on screen for the block to read as a choice they can take back.
        """
        fetched = self.fetched
        if fetched is None:  # pragma: no cover — unreachable via the panels
            return []
        from haywire.core.marketstall import candidate_haybales

        blocked_by_url: dict[str, set[str]] = {
            sub.url: set(sub.blocked) for sub in [*fetched.global_file.markets, *fetched.global_file.stalls]
        }
        installed = self.state.installed_row(name)

        out: list[Claimant] = []
        for hb in candidate_haybales(fetched, honour_blocked=False):
            if hb.name != name:
                continue
            owner = hb.owner_url or hb.via
            out.append(
                Claimant(
                    url=hb.via,
                    owner_url=owner,
                    version=hb.version,
                    label=hb.label,
                    origin=hb.origin,
                    blocked=name in blocked_by_url.get(owner, set()),
                    installed=installed is not None and self._is_installed_copy(installed, hb),
                )
            )
        return out

    @staticmethod
    def _is_installed_copy(installed: Haybale, candidate: Haybale) -> bool:
        from haybale_marketplace.identity import identity_matches

        return identity_matches(installed, candidate)

    @property
    def conflicts_are_settled(self) -> bool:
        """True when every contested name has exactly one claimant left standing.

        Blocking *all* of them is as unresolved as blocking none: the name is
        still contested, it just resolves to nothing. Requiring exactly one
        makes the step a choice with an answer, rather than a subtraction the
        user can walk away from half-done and let the survivor win by
        attrition.
        """
        return all(
            sum(1 for c in self.claimants_for(conflict.name) if not c.blocked) == 1
            for conflict in self.conflicts
        )

    def block_claimant(self, name: str, *, source_url: str) -> None:
        """Reject one claimant of a contested name, then re-resolve in place.

        Writes `blocked` on the subscription the user rejected — never on their
        behalf, and never wider than they asked: one name, one source, so a
        feed that claims a name not its own stays trusted for everything else.
        Refuses the installed copy; see :attr:`Claimant.can_block`.
        """
        target = next((c for c in self.claimants_for(name) if c.owner_url == source_url), None)
        if target is not None and not target.can_block:
            self.retry()
            self.error = (
                f"{name} is installed from this source. Uninstall it first if you want a "
                f"different one — blocking it now would leave the catalog offering another "
                f"author's code under the same name."
            )
            return
        self._rewrite_blocks(lambda: self.state.block_source(name, source_url=source_url))

    def unblock_claimant(self, name: str, *, source_url: str) -> None:
        """Put a rejected claimant back in the running, then re-resolve in place."""
        self._rewrite_blocks(lambda: self.state.unblock_source(name, source_url=source_url))

    def _rewrite_blocks(self, write) -> None:
        """Run a block/unblock write, then re-read and re-resolve in place.

        The re-resolve reads the global file again rather than reusing the
        parsed copy on `fetched` — that copy predates the write and would
        resolve identically, making the click look inert. Only the cheap parse
        is redone; the fetched bodies are reused, so no source is contacted a
        second time, and the project cache is still untouched.
        """
        self.retry()
        fetched = self.fetched
        if fetched is None:  # pragma: no cover — unreachable via the panels
            self.error = "Nothing fetched yet."
            return
        try:
            write()
            reparsed = self.state.get_global()
            if reparsed is not None:
                fetched.global_file = reparsed
            self.resolved = self.state.resolve(fetched)
            self.conflicts = self._detect_conflicts(self.resolved)
        except Exception as exc:  # noqa: BLE001 — surfaced inline, never swallowed
            self.fail(exc)

    async def advance_from_conflicts(self) -> None:
        """Leave the conflicts step — only once every contested name has an answer."""
        self.retry()
        if not self.conflicts_are_settled:
            self.error = (
                "Each contested name needs exactly one source left unblocked. "
                "Block the claimants you do not want, or unblock one you do."
            )
            return
        self.step = "resolved"

    def prefer_source(self, name: str, *, source_url: str) -> None:
        """Resolve a standing collision by naming the source that should win.

        Writes `preference` on the chosen source, then re-resolves in place so
        the panel immediately reflects it. Stays on the `resolved` step: this
        changes what a refresh *would* do, it does not perform one, and the
        project cache is still untouched.
        """
        self._rewrite_blocks(lambda: self.state.prefer_source(name, source_url=source_url))

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
