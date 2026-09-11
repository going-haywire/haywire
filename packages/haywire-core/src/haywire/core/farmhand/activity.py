"""What each agent principal is doing right now, and what it just did.

Answers the question ``auth/presence.py`` cannot: an agent's tool calls mutate
graphs under a human collaborator's cursor, and this attributes the change and
records what the call sent and got back.

Every call is recorded by the Farmhand host's ``call_tool`` wrapper, the only
layer that knows the calling principal — tools receive a ``FarmhandContext``,
not a request — so read-only tools and tools from third-party barn libraries
are covered with no per-tool opt-in.

Records land in two places:

* a bounded in-memory history, this module's ``ActivityTracker``, wiped on
  restart;
* an append-only JSONL audit log, written whenever
  ``ActivitySettings.log_path`` is non-empty. Nothing here ever trims it: a UI
  clear and the history cap both leave it alone.

Arguments and results are stored as JSON text, truncated to
``PAYLOAD_CHAR_CAP``, and are not redacted — a VIEW principal can already
inspect graph contents and library state by other means.

Reach the process-wide tracker through ``activity_tracker()`` in
``core/di/context.py``, never as a module-level instance here, so tests can
swap it and construction waits for a settings registry. Mutations run on the
NiceGUI event loop from the MCP request task; work a tool sends to a thread
with ``ctx.offload`` must not touch the tracker.
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

#: Fallback cap on remembered finished calls, used when no settings registry
#: offers an ``ActivitySettings.history_size`` to override it.
HISTORY_LIMIT = 50

#: Arguments and result text longer than this is cut and marked, in the
#: in-memory record and the persisted log line alike.
PAYLOAD_CHAR_CAP = 4000
_TRUNCATION_MARKER = "...[truncated]"

#: Zero-arg callback fired after each state change. It carries no payload;
#: listeners re-read the tracker.
ActivityListener = Callable[[], None]


def _serialize(value: Any) -> str:
    """JSON-encode a value, truncating past ``PAYLOAD_CHAR_CAP``.

    Never raises: a value JSON cannot encode degrades to its ``repr``, and an
    encoder failure comes back as a quoted error string.
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

    ``started_at`` and ``finished_at`` are ``time.monotonic()`` seconds: use
    them for durations, never as timestamps, since they mean nothing across a
    restart. ``started_wall`` is the ``time.time()`` companion a log line
    shows.

    ``arguments`` and ``result`` are JSON text, already truncated to
    ``PAYLOAD_CHAR_CAP``, never raw objects.
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
        """Wall-clock finish time, or ``None`` while the call is running.

        Derived as ``started_wall + elapsed()``, so it never disagrees with
        :meth:`elapsed` even if the system clock stepped mid-call.
        """
        if self.finished_at is None:
            return None
        return self.started_wall + self.elapsed()


@dataclass
class ActivityTracker:
    """In-flight and recently-finished tool calls, process-wide.

    :meth:`start` returns a token to pass to :meth:`finish`; several calls may
    be in flight for one principal at once, so :meth:`current` answers with
    the most recently started of them and :meth:`running_calls` lists them all.
    """

    _running: dict[int, ActivityRecord] = field(default_factory=dict)
    _history: Deque[ActivityRecord] = field(default_factory=lambda: deque(maxlen=HISTORY_LIMIT))
    _tokens: Iterator[int] = field(default_factory=lambda: itertools.count(1))
    # Per-instance, so a fresh tracker starts with no listeners.
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
        """Fire every listener. One that raises is logged and the rest still run.

        A listener may unsubscribe from inside the callback.
        """
        # Snapshot, so unsubscribing mid-notify cannot mutate the iteration.
        for listener in tuple(self._listeners):
            try:
                listener()
            except Exception:
                logger.debug("ActivityTracker listener %r raised; continuing", listener, exc_info=True)

    def start(self, principal: Optional[str], tool: str, arguments: Any = None) -> int:
        """Record a call beginning. Returns the token to pass to :meth:`finish`.

        Args:
            arguments: The tool's raw call arguments, serialized and truncated
                immediately so no stored record holds a live object.

        Fires listeners.
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
        """Record a call ending, appending it to the history and the audit log.

        A token that is unknown or already finished is ignored, and no
        listener fires — safe to call from an ``except`` block that is about
        to re-raise.

        Args:
            result: The tool's raw return value, serialized and truncated like
                ``arguments``.
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
        """Resize the history to a changed ``ActivitySettings.history_size``.

        Leaves the current size in place when the settings can't be reached,
        so a tracker built before the registry exists still works.
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

        Call from a ``finally`` to catch a cancelled request, whose
        ``CancelledError`` unwinds past both the success and failure paths and
        would otherwise leave the call pinned as forever-running.
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
        """Every call currently in flight, newest first, across all principals."""
        return sorted(self._running.values(), key=lambda r: r.started_at, reverse=True)

    def recent(self, limit: Optional[int] = None) -> list[ActivityRecord]:
        """Finished calls, newest first.

        Args:
            limit: How many to return at most. ``None`` returns the whole
                remembered history, itself capped at
                ``ActivitySettings.history_size``.
        """
        items = list(reversed(self._history))
        return items if limit is None else items[:limit]

    def clear(self) -> None:
        """Drop every record, in-flight calls included, without firing listeners.

        For teardown: a studio restart in-process, or a test. The UI's Clear
        button calls :meth:`clear_history` instead.
        """
        self._running.clear()
        self._history.clear()

    def clear_history(self) -> None:
        """Drop finished calls, backing the Activity editor's Clear button.

        In-flight calls survive, so each is still seen finishing, and the
        persisted audit log is never touched. Fires listeners, so other open
        sessions stop showing history that is gone.
        """
        self._history.clear()
        self._notify()

    def resize_history(self, maxlen: int) -> None:
        """Change the history cap, dropping the oldest records that no longer fit."""
        self._history = deque(self._history, maxlen=maxlen)

    def _persist(self, record: ActivityRecord) -> None:
        """Append ``record`` to the audit log, if one is configured.

        Never raises: a misconfigured path or a full disk is logged and
        skipped. The path is resolved per call, so a settings edit takes
        effect on the next one.
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

    Resolves ``ActivitySettings.log_path`` against the workspace root; an
    empty setting means off, as does any failure to reach the settings, which
    is logged rather than raised.
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
