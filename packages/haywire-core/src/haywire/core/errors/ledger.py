"""Bounded, sequence-numbered in-memory error ledger.

Every HaywireException registers here at .log() time. Registry-scan import
errors flow through the same path because the scan failure handlers .log()
their exceptions. First consumers: Farmhand's studio_get_errors and
studio_verify_component tools.

The ledger stores the live ``HaywireException`` objects — not serialized
snapshots. This is the exception's afterlife: once logged, it is otherwise
discarded, so the ledger keeps it whole (traceback frames, source context,
node_id, ...) for the Errors editor's rich detail popup and future
jump-to-component navigation. ``record()`` stamps the object's ``ledger_seq``
(monotonic, unique) and clears ``seen``; it is idempotent — an exception whose
``ledger_seq`` is already set is not recorded twice. Serialization for JSON
boundaries (the farmhand) goes through ``HaywireException.to_dict()``.

The ambient accessor lives in haywire.core.di.context alongside the other
get_*/set_* ambient singletons (get_workspace_root, get_node_factory, ...) —
one ambient surface, not two. Re-exported here so call sites are unaffected
by the move — see .insights/project_di_context.md.

Entries carry a per-record ``seen`` flag; the ledger exposes mark_seen /
mark_unseen / mark_all_seen / delete to triage them (keyed by the stable,
unique ``ledger_seq``). None of these touch ``current_seq``, so the farmhand's
incremental ``since_seq`` cursor stays monotonic and delete-safe. The ledger
is UI-ignorant: it fires a zero-arg listener on record() (bridged to the
ErrorLogged signal by the studio app) but knows nothing about signals or
sessions — triage-driven UI refresh (ErrorLedgerChanged) is the caller's job.

The listener seam is load-bearing here, not stylistic: ``.log()`` fires from
watchdog and timer threads (hence the lock below), while
``SessionManager.broadcast`` dispatches synchronously into the single-threaded
SignalBus. This store therefore *cannot* broadcast for itself — from a watchdog
thread there is no running loop to fetch — so the studio-side bridge owns the
``call_soon_threadsafe`` hop. ``ActivityTracker``, the other observable store,
is only ever touched from the loop and could self-broadcast, but is bridged
identically so that the shape safe to copy is the only shape present.
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
    """One page of ledger entries plus cursor and retained-window markers.

    ``entries`` are the live ``HaywireException`` objects (serialize with
    ``.to_dict()`` at a JSON boundary).

    ``cursor`` is ``current_seq`` — the highest seq ever assigned, monotonic and
    never reset (survives eviction, clear(), and delete()). Farmhand clients poll
    with ``since_seq=<cursor>`` for "everything new since last time".

    ``first_retained_seq`` is the smallest seq still present (0 when empty). Entries
    with a lower seq are gone — evicted by the bounded window or explicitly deleted —
    so a client that expected to page back to them knows history was dropped.
    """

    entries: list["HaywireException"]
    total: int
    cursor: int
    first_retained_seq: int


class ErrorLedger:
    """Bounded collection of live HaywireException objects (their afterlife)."""

    def __init__(self, max_entries: int = 500):
        self._entries: deque["HaywireException"] = deque(maxlen=max_entries)
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
        """Record ``exc`` (stamping its ledger_seq) and return that seq.

        Idempotent: if ``exc.ledger_seq`` is already set (nonzero), the exception
        has been recorded before — return its existing seq and do nothing else
        (no duplicate append, no seq bump, no listener fire, so a stray double
        ``.log()`` can't spuriously flash the unseen badge). Once set, an
        exception's ledger identity is permanent.
        """
        if exc.ledger_seq != 0:
            return exc.ledger_seq
        with self._lock:
            self._seq += 1
            exc.ledger_seq = self._seq
            exc.seen = False
            self._entries.append(exc)
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
            # Min surviving seq across the WHOLE deque (before filtering), so the
            # marker reflects what history is actually retained, not what this
            # filtered page happens to include. Entries are seq-ordered, so the
            # first is the smallest.
            first_retained = rows[0].ledger_seq if rows else 0
        if since_seq is not None:
            rows = [r for r in rows if r.ledger_seq > since_seq]
        if library is not None:
            rows = [r for r in rows if (r.library_identity.name if r.library_identity else None) == library]
        if registry_key is not None:
            rows = [r for r in rows if r.registry_key == registry_key]
        return LedgerPage(
            entries=rows[offset : offset + limit],
            total=len(rows),
            cursor=self._seq,
            first_retained_seq=first_retained,
        )

    def clear(self) -> None:
        """Drop all entries. Sequence numbers keep climbing from later record() calls."""
        with self._lock:
            self._entries.clear()

    # ------------------------------------------------------------------
    # Seen-state lifecycle + deletion (keyed by the stable, unique ledger_seq).
    #
    # All mutate under the lock; none touch _seq, so the farmhand cursor
    # (current_seq) stays monotonic and delete-safe. Callers that need
    # cross-session UI refresh publish ErrorLedgerChanged themselves — the
    # ledger is UI-ignorant and only mutates state here.
    # ------------------------------------------------------------------

    def mark_seen(self, seq: int) -> None:
        """Mark the entry with this ledger_seq as seen. No-op if not present."""
        self._set_seen(seq, True)

    def mark_unseen(self, seq: int) -> None:
        """Mark the entry with this ledger_seq as unseen. No-op if not present."""
        self._set_seen(seq, False)

    def _set_seen(self, seq: int, value: bool) -> None:
        with self._lock:
            for entry in self._entries:
                if entry.ledger_seq == seq:
                    entry.seen = value
                    return

    def mark_all_seen(self) -> None:
        """Mark every retained entry as seen."""
        with self._lock:
            for entry in self._entries:
                entry.seen = True

    def delete(self, seq: int) -> None:
        """Remove the entry with this ledger_seq. No-op if not present.

        current_seq is untouched, so incremental since_seq polling stays
        correct — a deleted entry is simply absent, exactly like an evicted one.
        """
        with self._lock:
            for i, entry in enumerate(self._entries):
                if entry.ledger_seq == seq:
                    del self._entries[i]
                    return
