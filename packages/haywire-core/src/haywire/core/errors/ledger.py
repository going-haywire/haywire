"""Bounded, sequence-numbered in-memory error ledger.

Every HaywireException registers here at .log() time. Registry-scan import
errors flow through the same path because the scan failure handlers .log()
their exceptions. First consumers: Farmhand's studio_get_errors and
studio_verify_component tools.

The ambient accessor lives in haywire.core.di.context alongside the other
get_*/set_* ambient singletons (get_workspace_root, get_node_factory, ...) —
one ambient surface, not two. Re-exported here so call sites are unaffected
by the move — see .insights/project_di_context.md.
"""

from __future__ import annotations

import logging
import threading
from collections import deque
from dataclasses import dataclass
from typing import TYPE_CHECKING, Callable, Optional

from haywire.core.di.context import get_error_ledger, set_error_ledger

if TYPE_CHECKING:
    from haywire.core.errors.haywire_exception import HaywireException

logger = logging.getLogger(__name__)

__all__ = ["ErrorLedger", "LedgerPage", "get_error_ledger", "set_error_ledger"]

# A ledger listener is a zero-arg callback fired after each record(). It carries
# no payload — listeners re-read the ledger (query()), matching the "signals
# carry no payload, subscribers re-read state" convention on the SignalBus.
LedgerListener = Callable[[], None]


@dataclass
class LedgerPage:
    """One page of ledger entries plus the current cursor."""

    entries: list[dict]
    total: int
    cursor: int


class ErrorLedger:
    """Bounded collection of serialized HaywireException snapshots."""

    def __init__(self, max_entries: int = 500):
        self._entries: deque[dict] = deque(maxlen=max_entries)
        self._seq = 0
        self._lock = threading.Lock()  # .log() fires from watchdog/timer threads too
        # Instance state (not a module global) so a fresh ErrorLedger per test
        # starts with no listeners — leakage across tests is structurally
        # impossible. Notified after record(), outside the lock.
        self._listeners: list[LedgerListener] = []

    @property
    def current_seq(self) -> int:
        return self._seq

    def add_listener(self, listener: LedgerListener) -> None:
        """Register a zero-arg callback fired after each record(). Idempotent per object."""
        if listener not in self._listeners:
            self._listeners.append(listener)

    def remove_listener(self, listener: LedgerListener) -> None:
        """Unregister a previously added listener. No-op if not present."""
        try:
            self._listeners.remove(listener)
        except ValueError:
            pass

    def record(self, exc: "HaywireException") -> int:
        with self._lock:
            self._seq += 1
            self._entries.append(
                {
                    "seq": self._seq,
                    "timestamp": exc.timestamp,
                    "message": exc.message,
                    "category": exc.category,
                    "severity": exc.severity.value if exc.severity else None,
                    "operation": exc.operation,
                    "registry_key": exc.registry_key,
                    "library": exc.library_identity.id if exc.library_identity else None,
                    "filename": exc.filename,
                    "line_number": exc.line_number,
                    "tags": list(exc.tags),
                    "suggestions": list(exc.suggestions),
                    "detail": exc.format_detailed(),
                }
            )
            seq = self._seq
        # Notify OUTSIDE the lock: a listener may re-enter the ledger (query())
        # or be slow, and holding the lock would deadlock/contend with concurrent
        # record()/query() from other threads. Snapshot the list so a listener
        # that unsubscribes mid-notify can't mutate what we're iterating. Each
        # listener is isolated — one raising must not abort the rest or bubble
        # up and break error reporting itself (see HaywireException.log).
        for listener in tuple(self._listeners):
            try:
                listener()
            except Exception:
                logger.debug("ErrorLedger listener %r raised; continuing", listener, exc_info=True)
        return seq

    def query(
        self,
        since_seq: Optional[int] = None,
        library: Optional[str] = None,
        registry_key: Optional[str] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> LedgerPage:
        with self._lock:
            rows = list(self._entries)
        if since_seq is not None:
            rows = [r for r in rows if r["seq"] > since_seq]
        if library is not None:
            rows = [r for r in rows if r["library"] == library]
        if registry_key is not None:
            rows = [r for r in rows if r["registry_key"] == registry_key]
        return LedgerPage(entries=rows[offset : offset + limit], total=len(rows), cursor=self._seq)

    def clear(self) -> None:
        """Drop all entries. Sequence numbers keep climbing from later record() calls."""
        with self._lock:
            self._entries.clear()
