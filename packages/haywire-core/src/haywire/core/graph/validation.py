# haywire/core/graph/validation.py
"""ValidationManager — the debounced validation pipeline behind ``BaseGraph``.

Tracks which nodes and edges are dirty and why, coalesces a burst of marks
into one batch, rebuilds whatever the batch requires, and notifies
subscribers with a ``ValidationResult``.
"""

import threading
import time
import logging
from typing import Dict, List, Callable, Optional, Any, Protocol, TYPE_CHECKING

from haywire.core.errors import report_failure
from .types import ChangeReason, ValidationResult
from .scheduler import ScheduleHandle, ThreadingTimerScheduler, ValidationScheduler

if TYPE_CHECKING:
    from .base import BaseGraph

logger = logging.getLogger(__name__)


# Type alias for validation callbacks
ValidationCallback = Callable[[ValidationResult], None]


class ExecutionHold(Protocol):
    """Parks a running graph at its frame barrier while a structural batch runs.

    Implemented by the Interpreter executing the graph tree. See ADR 0064.
    """

    def hold_for_batch(self) -> bool:
        """Park every execution group between frames; return ``False`` (no hold taken) if that is impossible.

        Implementations return ``False`` when called on one of their own runner
        threads, which cannot wait for its own frame to end.
        """
        ...

    def release_after_batch(self, requires_reassembly: bool) -> None:
        """End the hold ``hold_for_batch()`` took; with ``requires_reassembly`` the groups stay parked."""
        ...


class ValidationManager:
    """Runs a graph's validation pipeline: dirty tracking, debounce, batch, notify.

    Internal to ``BaseGraph``; external code goes through its public API
    (``subscribe_to_validation`` and the ``request_*`` methods).
    """

    def __init__(
        self,
        graph: "BaseGraph",
        debounce_ms: float = 50.0,
        scheduler: Optional[ValidationScheduler] = None,
    ):
        self._graph = graph
        self._debounce_ms = debounce_ms

        # Injected debounce strategy; see scheduler.py and ADR 0002.
        self._scheduler: ValidationScheduler = scheduler or ThreadingTimerScheduler()

        self._dirty_graph: ChangeReason | None = None
        """If the whole graph is dirty, reason for it"""

        self._dirty_nodes: Dict[str, ChangeReason] = {}
        """node_id -> reason for being dirty"""

        self._dirty_edges: Dict[str, ChangeReason] = {}
        """edge_id -> reason for being dirty"""

        # The lock guards every dirty-tracking mutation and is re-entrant, so a
        # synchronous scheduler can validate inside a mark_*_dirty call.
        self._pending_handle: Optional[ScheduleHandle] = None
        self._validation_lock = threading.RLock()

        # Lets _schedule_validation detect a batch that a synchronous scheduler
        # ran re-entrantly inside schedule().
        self._batch_generation = 0

        self._callbacks: List[ValidationCallback] = []

        self._execution_hold: Optional[ExecutionHold] = None

        self._validation_count = 0
        self._last_validation_time = 0.0
        self._total_validation_time_ms = 0.0

    def _set_reason(self, id: str, reason: ChangeReason, store: dict) -> None:
        """Record ``reason`` for ``id`` unless a higher-priority reason is already stored.

        An add after a removal replaces it: the element exists again, so the pass must
        treat it as added (an edge removed and re-linked to the same pins, an undone delete).
        """
        if id in store:
            existing_reason = store[id]
            readded = existing_reason.requires_removal() and reason.requires_adding()
            if existing_reason.has_higher_priority_than(reason) and not readded:
                return
        store[id] = reason

    def mark_graph_dirty(self, reason: ChangeReason) -> None:
        """Mark the whole graph as needing validation and restart the debounce.

        A lower-priority reason does not replace one already recorded for the
        graph, so a ``GRAPH_CONTENT_CHANGED`` cannot cancel a pending
        ``GRAPH_REQUIRE_REASSEMBLY``.
        """
        with self._validation_lock:
            if self._dirty_graph is None or not self._dirty_graph.has_higher_priority_than(reason):
                self._dirty_graph = reason
            self._schedule_validation()

            logger.info(f"Marked graph dirty (reason: {reason.value})")

    def mark_node_dirty(self, node_id: str, reason: ChangeReason) -> None:
        """Mark a node as needing validation and restart the debounce.

        A lower-priority reason does not replace one already recorded for it.
        """
        with self._validation_lock:
            self._set_reason(node_id, reason=reason, store=self._dirty_nodes)
            self._schedule_validation()

            logger.info(f"Marked node dirty: {node_id} (reason: {reason.value})")

    def mark_edge_dirty(self, edge_id: str, reason: ChangeReason) -> None:
        """Mark an edge as needing validation and restart the debounce.

        A lower-priority reason does not replace one already recorded for it.
        """
        with self._validation_lock:
            self._set_reason(id=edge_id, reason=reason, store=self._dirty_edges)
            self._schedule_validation()

            logger.info(f"Marked edge dirty: {edge_id} (reason: {reason.value})")

    def subscribe(self, callback: ValidationCallback) -> None:
        """Register ``callback`` to run after each validation batch that found changes.

        Registering the same callback twice still calls it once per batch.
        """
        if callback not in self._callbacks:
            self._callbacks.append(callback)
            logger.debug(f"Added validation subscriber: {getattr(callback, '__name__', repr(callback))}")

    def unsubscribe(self, callback: ValidationCallback) -> None:
        """Remove ``callback`` from the subscribers; a callback that isn't subscribed is ignored."""
        if callback in self._callbacks:
            self._callbacks.remove(callback)
            logger.debug(f"Removed validation subscriber: {getattr(callback, '__name__', repr(callback))}")

    def get_statistics(self) -> Dict[str, Any]:
        """Return the pipeline's counters.

        Returns:
            ``validation_count``, ``last_validation_time`` (epoch seconds of
            the last batch, ``0.0`` if none ran), ``average_validation_time_ms``,
            ``total_validation_time_ms``, ``debounce_ms``, ``dirty_nodes``,
            ``dirty_edges``, ``subscriber_count``, and ``pending_validation``
            (whether a debounced run is waiting).
        """
        with self._validation_lock:
            avg_time = (
                self._total_validation_time_ms / self._validation_count
                if self._validation_count > 0
                else 0.0
            )

            return {
                "validation_count": self._validation_count,
                "last_validation_time": self._last_validation_time,
                "average_validation_time_ms": avg_time,
                "total_validation_time_ms": self._total_validation_time_ms,
                "debounce_ms": self._debounce_ms,
                "dirty_nodes": len(self._dirty_nodes),
                "dirty_edges": len(self._dirty_edges),
                "subscriber_count": len(self._callbacks),
                "pending_validation": self._pending_handle is not None,
            }

    @property
    def lock(self) -> "threading.RLock":
        """The lock a validation batch holds while it builds and housekeeps nodes.

        Take it before a ``NodeWrapper``'s own lock, never after: a batch takes
        node locks while holding it.
        """
        return self._validation_lock

    def force_immediate_validation(self) -> Optional[ValidationResult]:
        """Run a validation batch now and cancel any pending debounced run.

        Returns:
            The batch result, or ``None`` when no node and no edge is dirty —
            a graph-only dirty mark on its own runs no batch.
        """
        with self._validation_lock:
            if self._pending_handle is not None:
                self._pending_handle.cancel()
                self._pending_handle = None

            if not self._dirty_nodes and not self._dirty_edges:
                return None

            return self._validate_batch()

    def set_execution_hold(self, hold: Optional[ExecutionHold]) -> None:
        """Make structural batches of this graph tree wait for ``hold``'s frame barrier; ``None`` ends it.

        Set on the root graph's manager; a Subgraph's batches read it from there.
        """
        self._execution_hold = hold

    def call_soon(self, fn: Callable[[], object]) -> None:
        """Run ``fn`` on this graph's validation scheduler, after the current batch."""
        self._scheduler.schedule(0.0, fn)

    def adopt_scheduler(self, scheduler: Optional[ValidationScheduler]) -> None:
        """Run future batches on ``scheduler``, cancelling any pending one.

        For a Subgraph joining a host: the two graphs' validations reach each
        other through the Graph-node card that spans them, so they must run on
        the same thread. A definition left on the default background timer
        while its host validates inline takes the card's ``NodeWrapper._lock``
        and the host's validation lock in the opposite order to the host — a
        deadlock that appears only under load. ``None`` leaves this manager's
        scheduler alone, since it means the host never chose one either.
        """
        if scheduler is None:
            return
        with self._validation_lock:
            if self._pending_handle is not None:
                self._pending_handle.cancel()
                self._pending_handle = None
            self._scheduler = scheduler

    def share_lock(self, lock: "threading.RLock") -> None:
        """Validate under ``lock`` from now on: the lock of the graph tree this graph joins.

        Graphs of one tree then validate one batch at a time, whatever thread
        runs it, so a Subgraph and its host may reach into each other inside a
        batch without a lock-order rule between them. Call it before this
        manager's lock is in use.
        """
        self._validation_lock = lock

    def clear(self) -> None:
        """Drop all dirty tracking and cancel any pending validation, without notifying subscribers."""
        with self._validation_lock:
            if self._pending_handle is not None:
                self._pending_handle.cancel()
                self._pending_handle = None

            self._dirty_nodes.clear()
            self._dirty_edges.clear()
            self._dirty_graph = None

            logger.debug("ValidationManager cleared")

    # =========================================================================
    # INTERNAL VALIDATION LOGIC
    # =========================================================================

    def _schedule_validation(self) -> None:
        """Schedule the batch, replacing any pending one, so marks inside the window validate once."""
        with self._validation_lock:
            # Cancelling the pending run first is what coalesces a burst of
            # marks into one batch.
            if self._pending_handle is not None:
                self._pending_handle.cancel()
            self._pending_handle = None

            # A synchronous scheduler runs _validate_batch inside schedule(),
            # which bumps the generation and clears _pending_handle; adopting
            # the inert handle it returns would make pending_validation lie.
            scheduled_generation = self._batch_generation
            delay_seconds = self._debounce_ms / 1000.0
            handle = self._scheduler.schedule(delay_seconds, self._validate_batch)
            if self._batch_generation == scheduled_generation:
                self._pending_handle = handle

            logger.debug(
                f"Scheduled validation in {self._debounce_ms}ms "
                f"({len(self._dirty_nodes)} nodes, {len(self._dirty_edges)} edges)"
            )

    def _tree_execution_hold(self) -> Optional[ExecutionHold]:
        root = self._graph.root_graph
        return root._validation._execution_hold if root is not self._graph else self._execution_hold

    def _pending_mutates_structure(self) -> bool:
        reasons = [*self._dirty_nodes.values(), *self._dirty_edges.values()]
        if self._dirty_graph is not None:
            reasons.append(self._dirty_graph)
        return any(reason.mutates_structure() for reason in reasons)

    def _validate_batch(self) -> ValidationResult:
        """Validate every dirty element and return the batch result.

        A batch that may change structure first parks the executing graph at
        its frame barrier (see ``set_execution_hold``), unless this thread
        already holds the validation lock; the validation lock is taken after
        the hold. See ``_run_batch_locked`` for what the batch does.
        """
        hold = self._tree_execution_hold()
        # A thread already inside the lock (inline validation, a forced batch)
        # must not wait for frames that may need that lock.
        reentrant = self._validation_lock._is_owned()  # type: ignore[attr-defined]
        held = False
        while True:
            with self._validation_lock:
                if held or hold is None or reentrant or not self._pending_mutates_structure():
                    result = self._run_batch_locked()
                    break
            held = hold.hold_for_batch()
            if not held:
                with self._validation_lock:
                    result = self._run_batch_locked()
                break
        if held:
            assert hold is not None
            hold.release_after_batch(
                requires_reassembly=result.graph is not None and result.graph.requires_graph_reassembly()
            )
        return result

    def _run_batch_locked(self) -> ValidationResult:
        """Validate every dirty element and return the batch result; the caller holds the validation lock.

        Rebuilds the nodes and edges whose reason calls for it, spreads a dirty
        node's reason to the edges attached to it, runs node housekeeping, and
        notifies subscribers when the result has changes. A failure on one
        element is logged and the batch continues; marks made during the batch
        are kept for the next one.
        """
        start_time = time.perf_counter()

        with self._validation_lock:
            # This run consumes the pending schedule, so a mark made during the
            # batch schedules a new one. The generation bump tells
            # _schedule_validation that a synchronous batch ran inside schedule().
            self._pending_handle = None
            self._batch_generation += 1

            dirty_nodes = dict(self._dirty_nodes)
            dirty_edges = dict(self._dirty_edges)
            dirty_graph = self._dirty_graph

            # Clear immediately so any dirty marks added during validation
            # (re-entrant via RLock) are preserved for the next batch.
            self._dirty_nodes.clear()
            self._dirty_edges.clear()
            self._dirty_graph = None

            logger.info(
                f"Starting validation batch: "
                f"{len(dirty_nodes)} nodes, {len(dirty_edges)} edges, "
                f"{dirty_graph.value if dirty_graph else 'no graph change'}"
            )

            validated_nodes: Dict[str, ChangeReason] = {}
            validated_edges: Dict[str, ChangeReason] = {}
            validated_graph: Optional[ChangeReason] = None

            if dirty_graph is not None:
                if dirty_graph.requires_graph_reassembly():
                    validated_graph = dirty_graph
                elif dirty_graph is ChangeReason.GRAPH_CONTENT_CHANGED:
                    # Reported as is: subscribers save; nothing here rebuilds for it.
                    validated_graph = dirty_graph
            # Validate nodes
            for node_id, reason in dirty_nodes.items():
                try:
                    if reason.requires_removal() or reason.requires_adding():
                        added_or_removed = self._graph.get_node_wrapper(node_id)
                        if added_or_removed is not None:
                            # A rebuild this reason outranked must not linger for a later one.
                            added_or_removed.take_rebuild_data()
                        validated_nodes[node_id] = reason
                        validated_graph = ChangeReason.GRAPH_REQUIRE_REASSEMBLY
                        continue

                    if reason.requires_rebuild():
                        node_wrapper = self._graph.get_node_wrapper(node_id)
                        if node_wrapper:
                            before = (
                                self._data_before_reload(node_wrapper)
                                if reason is ChangeReason.NODE_HOT_RELOADED
                                else None
                            )
                            # A requested rebuild may carry the exact data to restore (an undo).
                            node_wrapper.build(node_wrapper.take_rebuild_data())
                            if before is not None:
                                self._keep_previous_setup(node_wrapper, before)
                            edge_wrappers = self._graph._get_edge_wrappers_for_node(node_id)
                            for edge_wrapper in edge_wrappers:
                                # Attached edges revalidate too, at this reason's priority.
                                self._set_reason(id=edge_wrapper.edge_id, reason=reason, store=dirty_edges)
                            validated_nodes[node_id] = reason
                            validated_graph = ChangeReason.GRAPH_REQUIRE_REASSEMBLY
                            continue

                    if reason.requires_validation():
                        node_wrapper = self._graph.get_node_wrapper(node_id)
                        if node_wrapper:
                            edge_wrappers = self._graph._get_edge_wrappers_for_node(node_id)
                            for edge_wrapper in edge_wrappers:
                                # Attached edges revalidate too, at this reason's priority.
                                self._set_reason(id=edge_wrapper.edge_id, reason=reason, store=dirty_edges)
                            validated_nodes[node_id] = reason
                            validated_graph = ChangeReason.GRAPH_REQUIRE_REASSEMBLY
                            continue

                    if reason.requires_redraw():
                        validated_nodes[node_id] = reason
                        continue

                    if reason in (ChangeReason.NODE_VALUE_CHANGED, ChangeReason.NODE_STAGE_CHANGED):
                        # Reported as is: subscribers save; nothing here rebuilds for it.
                        validated_nodes[node_id] = reason
                        continue

                except Exception as e:
                    failed = self._graph.get_node_wrapper(node_id)
                    report_failure(
                        e,
                        operation="Validate node",
                        graph_id=self._graph.graph_id,
                        node_id=node_id,
                        reason=reason.name,
                        registry_key=failed.registry_key if failed else None,
                    )

            # Validate edges
            for edge_id, reason in dirty_edges.items():
                try:
                    if reason.requires_removal():
                        validated_edges[edge_id] = reason
                        validated_graph = ChangeReason.GRAPH_REQUIRE_REASSEMBLY
                        continue

                    if reason.requires_adding():
                        validated_edges[edge_id] = reason
                        validated_graph = ChangeReason.GRAPH_REQUIRE_REASSEMBLY
                        continue

                    found_edge_wrapper = self._graph.get_edge_wrapper(edge_id)
                    if reason.requires_rebuild() or reason.requires_validation():
                        # Rebuild unconditionally: the node may have changed the
                        # type of a port that kept its id.
                        if found_edge_wrapper:
                            was_functional = found_edge_wrapper.is_functional()
                            found_edge_wrapper.build()
                            if found_edge_wrapper.is_functional():
                                found_edge_wrapper.link()
                            elif was_functional:
                                found_edge_wrapper.unlink()
                            validated_edges[edge_id] = reason
                            validated_graph = ChangeReason.GRAPH_REQUIRE_REASSEMBLY
                            continue

                    if reason.requires_redraw():
                        validated_edges[edge_id] = reason
                        continue

                except Exception as e:
                    report_failure(
                        e,
                        operation="Validate edge",
                        graph_id=self._graph.graph_id,
                        edge_id=edge_id,
                        reason=reason.name,
                    )

            # Housekeeping runs only once every node and edge is validated.
            for node_id, _ in validated_nodes.items():
                node_wrapper = self._graph.get_node_wrapper(node_id)
                if node_wrapper:
                    node_wrapper._housekeeping()

            validation_time_ms = (time.perf_counter() - start_time) * 1000.0

            # Report each channel's canvas resize that BaseGraph flagged during this window.
            canvas_sizes = self._graph._take_canvas_size_changes()

            result = ValidationResult(
                nodes=validated_nodes,
                edges=validated_edges,
                graph=validated_graph,
                canvas_sizes=canvas_sizes,
                validation_time_ms=validation_time_ms,
            )

            self._validation_count += 1
            self._last_validation_time = time.time()
            self._total_validation_time_ms += validation_time_ms

            logger.info(
                f"Validation complete: {len(result.nodes)} nodes, {len(result.edges)} edges in "
                f"{validation_time_ms:.2f}ms"
            )

            if result.has_changes():
                self._notify_subscribers(result)

            return result

    @staticmethod
    def _data_before_reload(node_wrapper: Any) -> Optional[Dict[str, Any]]:
        """The node's data before its reload rebuild, or ``None`` for a stand-in or data that cannot be read.

        A stand-in's rebuild restores its kept data (ADR 0058), so it gets no previous setup.
        """
        if node_wrapper.is_stand_in:
            return None
        try:
            return dict(node_wrapper.serialize()["node_data"])
        except Exception:
            logger.debug(f"Reload of {node_wrapper.node_id}: data before rebuild not kept", exc_info=True)
            return None

    @staticmethod
    def _keep_previous_setup(node_wrapper: Any, before: Dict[str, Any]) -> None:
        """Hold the node's setup from before its reload when the rebuild changed it. See ADR 0062.

        A previous setup already held is kept over *before*, which is a rebuilt node's
        pristine data; it clears once the rebuild reproduces it. A reload that ends as
        a stand-in keeps what was held.
        """
        from haywire.core.node.previous_setup import (
            PREVIOUS_SETUP_KEY,
            differing_paths,
            report_previous_setup,
            restorable,
        )

        held = before.pop(PREVIOUS_SETUP_KEY, None)
        if node_wrapper.is_stand_in:
            node_wrapper.set_previous_setup(held)
            return
        try:
            after = node_wrapper.serialize()["node_data"]
        except Exception:
            logger.debug(f"Reload of {node_wrapper.node_id}: data after rebuild not compared", exc_info=True)
            node_wrapper.set_previous_setup(held)
            return
        after.pop(PREVIOUS_SETUP_KEY, None)
        candidate = held if held is not None else before
        differs = differing_paths(restorable(candidate), restorable(after))
        if not differs:
            node_wrapper.set_previous_setup(None)
            return
        node_wrapper.set_previous_setup(candidate)
        report_previous_setup(node_wrapper, operation="Hot reload", differs=differs)

    def _notify_subscribers(self, result: ValidationResult) -> None:
        """Call every subscriber with ``result``; an exception in one is logged and the rest still run."""
        logger.debug(f"Notifying {len(self._callbacks)} validation subscribers")

        # Iterate a copy: a callback may subscribe or unsubscribe.
        for callback in self._callbacks[:]:
            try:
                callback(result)
            except Exception as e:
                logger.error(
                    f"Validation callback error in {getattr(callback, '__name__', repr(callback))}: {e}",
                    exc_info=True,
                )
