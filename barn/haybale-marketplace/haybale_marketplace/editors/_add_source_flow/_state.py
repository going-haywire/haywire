"""The Add Source flow's state machine, free of NiceGUI calls.

Five steps, of which the last two mutate:

    input      paste a URL or a TOML block                  -> Probe
    probed     what the source is and what it offers        -> Continue
    resolved   per-name choice where it collides            -> Subscribe
    added      the subscription is written                  -> Refresh
    refreshed  terminal

The order is the point. The old dialog wrote the subscription *first* and
only then fetched the source to look for conflicts, which meant cancelling
the conflict prompt left a live subscription behind with its collisions
unresolved, and an unreachable source got subscribed anyway. Here nothing is
written until the user has seen what the source offers.

Two mutating steps is a deliberate exception to the one-mutation rule.
Subscribing and refreshing are independent operations — a refresh can fail,
or be declined, without making the subscription wrong — so ``added`` is
terminal-capable: it offers Refresh, but closing there is a legitimate end.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Optional, Protocol

from haywire.core.marketstall import (
    BareRepoUrlRejectedError,
    Haybale,
    RefreshReport,
    ResolvedSource,
    SubscribeError,
    SubscriptionConflict,
)
from haywire.ui.components.popup import Popup
from haywire.ui.components.stepper import StepFlow

from .copy import STEP_TITLES, STEPS

logger = logging.getLogger(__name__)

#: Per-conflict decision. "existing" keeps what is already resolved and tells
#: the NEW source to step aside; "new" does the reverse.
KEEP_EXISTING = "existing"
USE_NEW = "new"


class AddSourceTarget(Protocol):
    """The slice of the marketplace this flow drives.

    Narrowed to a protocol so the flow depends on five operations rather than
    on MarketplaceState, the global config paths and DI — which also lets the
    tests drive it with their own directories.
    """

    def resolve_source(self, user_input: str) -> ResolvedSource: ...

    def existing_haybales(self) -> list[Haybale]: ...

    def subscribe(self, resolved: ResolvedSource) -> str: ...

    def record_ignore(self, source_url: str, haybale_name: str) -> None: ...

    def refresh(self) -> RefreshReport: ...


class AddSourceFlow(StepFlow):
    """Linear, resumable state machine for the Add Source flow."""

    STEPS = STEPS
    STEP_TITLES = STEP_TITLES

    def __init__(self, *, target: AddSourceTarget, popup: Optional[Popup] = None) -> None:
        super().__init__()
        self.target = target
        self.popup = popup

        self.user_input: str = ""
        self.resolved: ResolvedSource | None = None
        self.conflicts: list[SubscriptionConflict] = []
        #: haybale name -> KEEP_EXISTING | USE_NEW. Defaults to keeping what
        #: is already there: the safe answer, and the one the old dialog
        #: pre-selected.
        self.choices: dict[str, str] = {}
        self.persist_url: str = ""
        self.report: RefreshReport | None = None
        #: Set when the input was a bare repo URL — a wrong-shape input the
        #: user fixes by editing the field, not by retrying.
        self.rejected_input: bool = False

    @property
    def new_names(self) -> list[str]:
        """Names the source offers, in the order it lists them."""
        if self.resolved is None:
            return []
        return [h.name for h in self.resolved.haybales]

    def retry(self) -> None:
        super().retry()
        self.rejected_input = False

    async def advance_from_input(self, user_input: str) -> None:
        """Fetch and classify the source. Writes nothing.

        A network round-trip, so it runs in a thread rather than starving
        NiceGUI's heartbeat.
        """
        self.retry()
        text = (user_input or "").strip()
        if not text:
            self.error = "Paste a URL or a TOML block first."
            return
        self.user_input = text
        try:
            self.resolved = await asyncio.to_thread(self.target.resolve_source, text)
        except BareRepoUrlRejectedError as exc:
            # Wrong shape of input rather than a failure: retrying verbatim
            # cannot help, so the panel keeps the field and says what to fix.
            self.rejected_input = True
            self.fail(exc)
            return
        except SubscribeError as exc:
            self.fail(exc)
            return
        except Exception as exc:  # noqa: BLE001 — surfaced inline, never swallowed
            self.fail(exc)
            return

        self._detect_conflicts()
        self.step = "probed"

    def _detect_conflicts(self) -> None:
        """Compare what the source offers against what is already resolved."""
        from haywire.core.marketstall import detect_subscription_conflicts

        resolved = self.resolved
        if resolved is None:  # pragma: no cover — guarded by the caller
            return
        for pkg in resolved.haybales:
            if not pkg.source_origin:
                pkg.source_origin = resolved.persist_url or "(pasted block)"
        self.conflicts = detect_subscription_conflicts(self.target.existing_haybales(), resolved.haybales)
        # Keeping what is already installed is the conservative default.
        self.choices = {c.name: KEEP_EXISTING for c in self.conflicts}

    async def advance_from_probed(self) -> None:
        """Move to the conflict decision. Always shown, even when clean."""
        self.retry()
        self.step = "resolved"

    def choose(self, name: str, choice: str) -> None:
        """Record the per-conflict decision from the panel's radio."""
        self.choices[name] = choice

    async def advance_from_resolved(self) -> None:
        """Write the subscription and any ignores. First mutating step."""
        self.retry()
        resolved = self.resolved
        if resolved is None:  # pragma: no cover — unreachable via the panels
            self.error = "Nothing resolved yet."
            return
        try:
            self.persist_url = await asyncio.to_thread(self.target.subscribe, resolved)
            self._apply_conflict_choices()
        except Exception as exc:  # noqa: BLE001 — surfaced inline, never swallowed
            self.fail(exc)
            return
        self.step = "added"

    def _apply_conflict_choices(self) -> None:
        """Tell the losing source to ignore each contested name.

        Recorded against whichever side lost, exactly as the old dialog did:
        keeping the existing entry means the NEW subscription steps aside,
        and vice versa.
        """
        for conflict in self.conflicts:
            if self.choices.get(conflict.name, KEEP_EXISTING) == KEEP_EXISTING:
                loser = conflict.new_source or self.persist_url
            else:
                loser = conflict.existing_source
            if not loser:
                continue
            try:
                self.target.record_ignore(loser, conflict.name)
            except Exception:
                # A failed ignore leaves a live collision, which refresh
                # resolves first-come-first-served. Worth a warning, not
                # worth undoing a subscription the user asked for.
                logger.exception("Failed to record ignore for %s", conflict.name)
                self.warnings.append(
                    f"Could not record the choice for {conflict.name}; "
                    "the first source to offer it will win."
                )

    async def advance_from_added(self) -> None:
        """Refresh so the new source's packages reach the library list.

        Second mutating step, and deliberately separate: the subscription is
        already correct, so a refresh failure is retryable here without
        casting doubt on what came before.
        """
        self.retry()
        try:
            self.report = await asyncio.to_thread(self.target.refresh)
        except Exception as exc:  # noqa: BLE001 — surfaced inline, never swallowed
            self.fail(exc)
            return
        self.step = "refreshed"
