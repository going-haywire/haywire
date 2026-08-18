"""What each agent principal is doing right now, and what it just did.

The studio already answers "who is connected" two different ways, because the
two kinds of principal offer different liveness signals (see
``auth/presence.py``). This module adds the third question the presence row
could not answer at all: **what is that agent actually doing?**

A browser principal's actions are visible as they happen — the human doing them
is looking at the same screen. An agent's are not: its tool calls mutate graphs
under a human collaborator's cursor with nothing on screen to explain the
change. Every mutating Farmhand tool already broadcasts ``GraphDataMutated``, so
the *data* refreshes live; what was missing is *attribution*.

Recording happens in one place — the Farmhand host's ``call_tool`` wrapper —
rather than in the tools. That is deliberate:

* the host is the only layer that knows the calling principal (tools receive a
  ``FarmhandContext``, not a request), and
* one call site covers read-only tools, tools from third-party barn libraries,
  and tools that do not exist yet, with no per-tool opt-in to forget.

Threading: every mutation runs on the NiceGUI event loop, from the MCP request
task. Tools may ``ctx.offload`` blocking work to a thread, but the tracker is
never touched from inside that work. Module-level global rather than a
ContextVar, for the reason in ``.insights/project_di_context.md``.
"""

from __future__ import annotations

import itertools
import time
from collections import deque
from dataclasses import dataclass, field
from typing import Deque, Iterator, Optional

#: How many finished calls to remember. Feeds "what did it just do?" in the
#: presence tooltip; a fast tool would otherwise flash past unread.
HISTORY_LIMIT = 50


@dataclass(frozen=True)
class ActivityRecord:
    """One Farmhand tool call by one principal."""

    principal: Optional[str]
    tool: str
    started_at: float
    finished_at: Optional[float] = None
    ok: bool = True
    error: Optional[str] = None

    @property
    def running(self) -> bool:
        return self.finished_at is None

    def elapsed(self, now: Optional[float] = None) -> float:
        """Seconds this call has been running, or took."""
        end = self.finished_at if self.finished_at is not None else (now or time.monotonic())
        return max(0.0, end - self.started_at)


@dataclass
class ActivityTracker:
    """In-flight and recently-finished tool calls, process-wide.

    Concurrency: MCP permits several requests in flight at once, so calls are
    keyed by an opaque token rather than by principal. ``current`` therefore
    answers with the *most recently started* running call for a principal —
    which is what a one-line status chip can honestly show.
    """

    _running: dict[int, ActivityRecord] = field(default_factory=dict)
    _history: Deque[ActivityRecord] = field(default_factory=lambda: deque(maxlen=HISTORY_LIMIT))
    _tokens: Iterator[int] = field(default_factory=lambda: itertools.count(1))

    def start(self, principal: Optional[str], tool: str) -> int:
        """Record a call beginning. Returns the token to pass to :meth:`finish`."""
        token = next(self._tokens)
        self._running[token] = ActivityRecord(principal=principal, tool=tool, started_at=time.monotonic())
        return token

    def finish(self, token: int, *, ok: bool = True, error: Optional[str] = None) -> None:
        """Record a call ending. Unknown tokens are ignored.

        Tolerating an unknown token keeps a bookkeeping slip from turning into a
        second exception on the failure path, where ``finish`` is called from an
        ``except`` block that is about to re-raise the real error.
        """
        record = self._running.pop(token, None)
        if record is None:
            return
        self._history.append(
            ActivityRecord(
                principal=record.principal,
                tool=record.tool,
                started_at=record.started_at,
                finished_at=time.monotonic(),
                ok=ok,
                error=error,
            )
        )

    def finish_if_running(self, token: int, *, error: str = "cancelled") -> bool:
        """Close out a call only if nothing has closed it yet. Returns whether it did.

        The host calls this from a ``finally``, to catch the path neither the
        success nor the failure branch covers: a cancelled request. MCP requests
        run as tasks the SDK cancels when the client disconnects, and a
        ``CancelledError`` unwinds straight past both — leaving the call pinned
        as forever-running in the presence chip.
        """
        if token not in self._running:
            return False
        self.finish(token, ok=False, error=error)
        return True

    def current(self, principal: Optional[str]) -> Optional[ActivityRecord]:
        """The most recently started call still running for ``principal``."""
        candidates = [r for r in self._running.values() if r.principal == principal]
        if not candidates:
            return None
        return max(candidates, key=lambda r: r.started_at)

    def last(self, principal: Optional[str]) -> Optional[ActivityRecord]:
        """The most recently finished call for ``principal``, if any is remembered."""
        for record in reversed(self._history):
            if record.principal == principal:
                return record
        return None

    def running_calls(self) -> list[ActivityRecord]:
        """Every call currently in flight, newest first, across all principals.

        Distinct from :meth:`current`, which answers the one-line question a
        presence chip asks ("what is *this* principal doing?"). The activity
        editor lists them all, so concurrent calls are each visible instead of
        collapsing into the most recent.
        """
        return sorted(self._running.values(), key=lambda r: r.started_at, reverse=True)

    def recent(self, limit: int = HISTORY_LIMIT) -> list[ActivityRecord]:
        """Finished calls, newest first."""
        return list(reversed(self._history))[:limit]

    def clear(self) -> None:
        """Drop all state — for tests, and for a studio restart in-process."""
        self._running.clear()
        self._history.clear()


_tracker = ActivityTracker()


def activity_tracker() -> ActivityTracker:
    """The process-wide tracker. Mirrors ``auth.gate.last_seen()``'s shape."""
    return _tracker
