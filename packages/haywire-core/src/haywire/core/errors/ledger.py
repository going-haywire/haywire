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

import threading
from collections import deque
from dataclasses import dataclass
from typing import TYPE_CHECKING, Optional

from haywire.core.di.context import get_error_ledger, set_error_ledger

if TYPE_CHECKING:
    from haywire.core.errors.haywire_exception import HaywireException

__all__ = ["ErrorLedger", "LedgerPage", "get_error_ledger", "set_error_ledger"]


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

    @property
    def current_seq(self) -> int:
        return self._seq

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
            return self._seq

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
