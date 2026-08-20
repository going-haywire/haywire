"""What each agent principal is doing right now, and what it just did.

The studio already answers "who is connected" two different ways, because the
two kinds of principal offer different liveness signals (see
``auth/presence.py``). This module adds the third question the presence row
could not answer at all: **what is that agent actually doing?**

A browser principal's actions are visible as they happen — the human doing them
is looking at the same screen. An agent's are not: its tool calls mutate graphs
under a human collaborator's cursor with nothing on screen to explain the
change. Every mutating Farmhand tool already broadcasts ``GraphDataMutated``, so
the *data* refreshes live; what was missing is *attribution* — and, now,
*content*: what the call actually sent and got back.

Recording happens in one place — the Farmhand host's ``call_tool`` wrapper —
rather than in the tools. That is deliberate:

* the host is the only layer that knows the calling principal (tools receive a
  ``FarmhandContext``, not a request), and
* one call site covers read-only tools, tools from third-party barn libraries,
  and tools that do not exist yet, with no per-tool opt-in to forget.

Threading: every mutation runs on the NiceGUI event loop, from the MCP request
task. Tools may ``ctx.offload`` blocking work to a thread, but the tracker is
never touched from inside that work. Reached through the ambient accessor in
``core/di/context.py`` (a module-level global rather than a ContextVar, for the
reason in ``.insights/project_di_context.md``) — never as a module-level
instance here, so a test can swap it and so construction is deferred until a
settings registry exists.

**Observable store.** This is the second implementation of the pattern
``ErrorLedger`` established, and the two are deliberately identical in shape:
an ambient ``get_/set_`` accessor that survives hot-reload, a zero-arg listener
list fired on every state change, an app-side bridge that turns those fires
into a cross-session signal, and a payload-free signal whose subscribers
re-read this store.

Why the listener seam rather than having this store call
``get_session_manager().broadcast(...)`` itself — which it *could*, since
``FarmhandContext.broadcast`` does exactly that from this same package:

* **Thread safety by default.** ``SessionManager.broadcast`` dispatches
  synchronously into the single-threaded SignalBus. This tracker happens to be
  touched only from the loop, but ``ErrorLedger`` is not — ``.log()`` fires
  from watchdog and timer threads, which is why it holds a lock and this does
  not. A self-broadcasting store would have to capture an event loop at startup
  and hold it as state. Keeping the hop in the bridge means the *pattern* is
  safe wherever it is copied, instead of safe only where someone checked.
* **Isolation.** A bare ``ActivityTracker()`` is inert — no session manager, no
  DI, no running loop — so the tests exercise ``start``/``finish`` directly.
* **Signal choice is the application's.** The store records that state changed;
  that this means ``FarmhandActivity``, cross-session, to every open browser is
  a policy a headless embedding or a second host may answer differently.

What this store deliberately does *not* copy from ``ErrorLedger`` is the triage
half: no ``seen`` flag, no stable per-record sequence, no second "triage
changed" signal. An error is a task — someone must notice and act on it, so
"have I acknowledged this" is real state. A finished tool call is a fact; there
is nothing to acknowledge.

Two tiers of record (settled 2026-08-18, see
``docs/superpowers/plans/2026-08-18-farmhand-activity-expansion.md``):

* An in-memory, bounded history (this module's ``ActivityTracker``) — serves
  live-awareness and short-term debugging. Wiped on restart.
* An optional, per-project, append-only JSONL audit log, written alongside
  the in-memory record whenever ``ActivitySettings.log_path`` is non-empty.
  Never trimmed by anything in this module — a UI "clear" or a history-size
  cap must never touch it, or it stops being an audit trail.

Arguments/result are stored as already-JSON-serialized text (the same
``json.dumps(..., default=str)`` shape the host computes for the MCP
response), truncated to a fixed character cap. No redaction: VIEW-tier access
to this data discloses nothing a VIEW principal could not already inspect by
other means (graph contents, library state, …).
"""

from __future__ import annotations

import itertools
import json
import logging
import time
from collections import deque
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Deque, Iterator, Optional

from haywire.core.di.context import activity_tracker, set_activity_tracker

logger = logging.getLogger(__name__)

#: Default cap on remembered finished calls — overridden per-instance by
#: ``ActivitySettings.history_size`` where a registry is available (the
#: process-wide tracker picks it up in ``activity_tracker()``). Kept as a
#: plain constant so a bare ``ActivityTracker()`` (tests, embedding without
#: the studio settings registry) still behaves sensibly.
HISTORY_LIMIT = 50

#: Arguments/result text longer than this is cut, with a marker appended.
#: Applies uniformly to the in-memory record and the persisted log line —
#: there is no framework-level cap upstream of this on the Farmhand call
#: path (tool-level pagination like ``truncation_note`` is opt-in, not a
#: guarantee), so this is the first real backstop.
PAYLOAD_CHAR_CAP = 4000
_TRUNCATION_MARKER = "...[truncated]"

# A tracker listener is a zero-arg callback fired after each state change
# (start / finish / clear). It carries no payload — listeners re-read the
# tracker, matching the "signals carry no payload, subscribers re-read state"
# convention shared with ErrorLedger and the SignalBus.
ActivityListener = Callable[[], None]


def _serialize(value: Any) -> str:
    """JSON-encode arguments/result the same way the host encodes tool results.

    ``default=str`` mirrors ``host.py``'s own serialization (see its
    docstring on why: a non-serializable value like a mesh or frame degrades
    to a repr instead of raising).
    """
    try:
        text = json.dumps(value, default=str)
    except Exception as exc:  # pragma: no cover - defensive; json.dumps(default=str) rarely raises
        return f'"<unserializable: {exc}>"'
    if len(text) > PAYLOAD_CHAR_CAP:
        return text[:PAYLOAD_CHAR_CAP] + _TRUNCATION_MARKER
    return text


@dataclass(frozen=True)
class ActivityRecord:
    """One Farmhand tool call by one principal.

    ``started_at``/``finished_at`` are ``time.monotonic()`` — correct for
    elapsed-time math (immune to clock adjustments) but meaningless across a
    restart. ``started_wall`` is a ``time.time()`` companion, carried only so
    a persisted log line has a real-world timestamp to show; nothing in this
    module does duration math with it.

    ``arguments``/``result`` are pre-serialized JSON text (see ``_serialize``),
    already truncated to ``PAYLOAD_CHAR_CAP`` — never raw Python objects, so
    every consumer (in-memory render, JSONL line, popup) treats them
    uniformly as strings.
    """

    principal: Optional[str]
    tool: str
    started_at: float
    started_wall: float
    arguments: str = "{}"
    finished_at: Optional[float] = None
    ok: bool = True
    error: Optional[str] = None
    result: Optional[str] = None

    @property
    def running(self) -> bool:
        return self.finished_at is None

    def elapsed(self, now: Optional[float] = None) -> float:
        """Seconds this call has been running, or took."""
        end = self.finished_at if self.finished_at is not None else (now or time.monotonic())
        return max(0.0, end - self.started_at)

    def to_json_line(self) -> str:
        """This record as one JSONL line for the persisted audit log."""
        return json.dumps(
            {
                "principal": self.principal,
                "tool": self.tool,
                "started_at": self.started_wall,
                "finished_at": self.finished_wall,
                "ok": self.ok,
                "error": self.error,
                "arguments": self.arguments,
                "result": self.result,
            }
        )

    @property
    def finished_wall(self) -> Optional[float]:
        """Wall-clock finish time, derived from the monotonic elapsed duration.

        There is no separately-stored ``finished_at`` wall-clock field —
        deriving it from ``started_wall + elapsed()`` avoids a second
        ``time.time()`` call that could disagree with ``elapsed()`` if the
        system clock stepped between the two calls.
        """
        if self.finished_at is None:
            return None
        return self.started_wall + self.elapsed()


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
    # Instance state (not a module global) so a fresh ActivityTracker per test
    # starts with no listeners — leakage across tests is structurally
    # impossible. Mirrors ErrorLedger._listeners for the same reason.
    _listeners: list[ActivityListener] = field(default_factory=list)

    def add_listener(self, listener: ActivityListener) -> None:
        """Register a zero-arg callback fired after each state change. Idempotent per object."""
        if listener not in self._listeners:
            self._listeners.append(listener)

    def remove_listener(self, listener: ActivityListener) -> None:
        """Unregister a previously added listener. No-op if not present."""
        try:
            self._listeners.remove(listener)
        except ValueError:
            pass

    def _notify(self) -> None:
        """Fire every listener, isolating failures.

        Snapshot the list so a listener that unsubscribes mid-notify cannot
        mutate what we are iterating. Each listener is isolated — one raising
        must not abort the rest, and must never turn a successful tool call
        into a failed one (this runs inside the host's call path).
        """
        for listener in tuple(self._listeners):
            try:
                listener()
            except Exception:
                logger.debug("ActivityTracker listener %r raised; continuing", listener, exc_info=True)

    def start(self, principal: Optional[str], tool: str, arguments: Any = None) -> int:
        """Record a call beginning. Returns the token to pass to :meth:`finish`.

        ``arguments`` is the tool's raw call arguments (a dict off the MCP
        transport); serialized+truncated immediately so every stored record —
        running or finished — carries text, never a live object.
        """
        token = next(self._tokens)
        self._running[token] = ActivityRecord(
            principal=principal,
            tool=tool,
            started_at=time.monotonic(),
            started_wall=time.time(),
            arguments=_serialize(arguments if arguments is not None else {}),
        )
        self._notify()
        return token

    def finish(
        self,
        token: int,
        *,
        ok: bool = True,
        error: Optional[str] = None,
        result: Any = None,
    ) -> None:
        """Record a call ending. Unknown tokens are ignored.

        Tolerating an unknown token keeps a bookkeeping slip from turning into a
        second exception on the failure path, where ``finish`` is called from an
        ``except`` block that is about to re-raise the real error.

        ``result`` is the tool's raw return value; serialized+truncated the
        same way as ``arguments``. Appends to the in-memory history and, if
        persistence is configured, to the audit log — in that order, so a
        write failure in one never blocks the other.

        Listeners fire only when a call actually moved from running to
        finished: an unknown token returns before any state changed, so it
        must not wake subscribers to re-read an unchanged store.
        """
        record = self._running.pop(token, None)
        if record is None:
            return
        finished = ActivityRecord(
            principal=record.principal,
            tool=record.tool,
            started_at=record.started_at,
            started_wall=record.started_wall,
            arguments=record.arguments,
            finished_at=time.monotonic(),
            ok=ok,
            error=error,
            result=_serialize(result) if result is not None else None,
        )
        self._sync_history_size()
        self._history.append(finished)
        self._persist(finished)
        self._notify()

    def _sync_history_size(self) -> None:
        """Pick up a live ``ActivitySettings.history_size`` edit before the next append.

        Checked per-append rather than via a settings subscription: this
        tracker is a bare module-level global constructed at import time,
        before ``ActivitySettings`` is necessarily registered, so a
        subscription would have nowhere reliable to attach at construction.
        Resolving lazily (and tolerating absence, like ``_resolve_log_path``)
        avoids that ordering problem entirely.
        """
        try:
            from .settings import ActivitySettings

            configured = ActivitySettings().history_size
        except Exception:
            return
        if configured != self._history.maxlen:
            self.resize_history(configured)

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

    def recent(self, limit: Optional[int] = None) -> list[ActivityRecord]:
        """Finished calls, newest first.

        ``limit`` caps the returned page; ``None`` (default) returns
        everything ``_history`` holds, which is itself already capped at
        ``ActivitySettings.history_size`` (synced on every :meth:`finish`).
        """
        items = list(reversed(self._history))
        return items if limit is None else items[:limit]

    def clear(self) -> None:
        """Drop all state — for tests, and for a studio restart in-process.

        Wipes ``_running`` too — unlike :meth:`clear_history`, which the UI's
        Clear button calls. This one is not reachable from the UI.

        Deliberately does NOT notify: this is teardown, not a state change any
        subscriber should redraw for, and firing here would push a listener
        registered by a previous app instance during test teardown.
        """
        self._running.clear()
        self._history.clear()

    def clear_history(self) -> None:
        """Drop finished calls only — what the Activity editor's Clear button does.

        Deliberately leaves ``_running`` untouched: clearing an in-flight call
        out from under itself would strand it with no way to ever be seen
        finishing. Never touches the persisted audit log (see module
        docstring) — a UI action that could erase durable audit history would
        defeat the reason that log exists.

        Notifies: the clearing session redraws itself, but every *other* open
        session is showing history that no longer exists.
        """
        self._history.clear()
        self._notify()

    def resize_history(self, maxlen: int) -> None:
        """Rebuild ``_history`` with a new cap, keeping the most recent entries.

        Called when ``ActivitySettings.history_size`` changes. ``deque`` has
        no in-place maxlen change, so this replaces the deque, keeping
        whichever tail still fits.
        """
        self._history = deque(self._history, maxlen=maxlen)

    def _persist(self, record: ActivityRecord) -> None:
        """Append ``record`` to the audit log, if one is configured.

        Best-effort: a misconfigured path or a full disk must not turn a
        successful tool call into a failed one. Resolves the path fresh on
        every call rather than caching it, so a live settings edit (path
        changed, or cleared to turn logging off) takes effect on the very
        next call with no restart.
        """
        path = _resolve_log_path()
        if path is None:
            return
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            with path.open("a", encoding="utf-8") as f:
                f.write(record.to_json_line() + "\n")
        except Exception as exc:
            logger.debug(f"Farmhand activity: audit log write skipped: {exc}")


def _resolve_log_path() -> Optional[Path]:
    """The audit log's absolute path, or ``None`` when logging is off.

    ``ActivitySettings.log_path`` is empty-means-off, non-empty-means-a-path-
    relative-to-the-workspace-root (see ``settings.py``). Reached via DI
    rather than threaded through every ``finish()`` call, matching how
    ``host.py``'s own ``_publish_activity`` reaches ``get_session_manager()``
    lazily and tolerates its absence.
    """
    try:
        from haywire.core.di.context import get_workspace_root

        from .settings import ActivitySettings

        relative = ActivitySettings().log_path
        if not relative:
            return None
        return (get_workspace_root() / relative).resolve()
    except Exception as exc:
        logger.debug(f"Farmhand activity: audit log path unavailable: {exc}")
        return None


__all__ = [
    "ActivityListener",
    "ActivityRecord",
    "ActivityTracker",
    "HISTORY_LIMIT",
    "PAYLOAD_CHAR_CAP",
    "activity_tracker",
    "set_activity_tracker",
]
