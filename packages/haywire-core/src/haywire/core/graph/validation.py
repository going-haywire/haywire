# haywire/core/graph/validation.py
"""
ValidationManager - Handles validation pipeline for graph changes.

Internal component used by BaseGraph. Manages:
- Dirty tracking (what needs validation)
- Change categorization (added/changed/removed)
- Debounced batch validation
- Subscriber notifications
"""

import threading
import time
import logging
from typing import Dict, List, Callable, Optional, Any, TYPE_CHECKING

from .types import ChangeReason, ValidationResult
from .scheduler import ScheduleHandle, ThreadingTimerScheduler, ValidationScheduler

if TYPE_CHECKING:
    from .base import BaseGraph

logger = logging.getLogger(__name__)

# Type alias for validation callbacks
ValidationCallback = Callable[[ValidationResult], None]


class ValidationManager:
    """
    Manages the validation pipeline for a graph.

    This is an internal component - external code should interact through
    BaseGraph's public API (subscribe_to_validation, etc).

    Responsibilities:
    - Track dirty nodes/edges with change reasons
    - Categorize changes (added/changed/removed)
    - Debounce validation with configurable delay
    - Execute batch validation
    - Notify subscribers with categorized results
    """

    def __init__(
        self,
        graph: "BaseGraph",
        debounce_ms: float = 50.0,
        scheduler: Optional[ValidationScheduler] = None,
    ):
        self._graph = graph
        self._debounce_ms = debounce_ms

        # Injected debounce strategy; defaults to the legacy threading.Timer.
        # See scheduler.py and ADR 0002.
        self._scheduler: ValidationScheduler = scheduler or ThreadingTimerScheduler()

        self._dirty_graph: ChangeReason | None = None
        """If the whole graph is dirty, reason for it"""

        # Simplified tracking - just map elements to reasons
        self._dirty_nodes: Dict[str, ChangeReason] = {}
        """node_id -> reason for being dirty"""

        self._dirty_edges: Dict[str, ChangeReason] = {}
        """edge_id -> reason for being dirty"""

        # Pending debounced validation (from the injected scheduler) and the
        # re-entrancy lock guarding all dirty-tracking mutation.
        self._pending_handle: Optional[ScheduleHandle] = None
        self._validation_lock = threading.RLock()

        # Monotonic batch counter. Lets _schedule_validation detect when a
        # synchronous scheduler ran the batch re-entrantly inside schedule().
        self._batch_generation = 0

        # Subscribers
        self._callbacks: List[ValidationCallback] = []

        # Statistics
        self._validation_count = 0
        self._last_validation_time = 0.0
        self._total_validation_time_ms = 0.0

    def _set_reason(self, id: str, reason: ChangeReason, store: dict) -> None:
        """Set the reason according to priority"""
        if id in store:
            existing_reason = store[id]
            if existing_reason.has_higher_priority_than(reason):
                return
        store[id] = reason

    def mark_graph_dirty(self, reason: ChangeReason) -> None:
        """
        Mark a graph as needing validation.

        Uses priority system - higher priority reasons override lower ones.
        """
        with self._validation_lock:
            self._dirty_graph = reason
            self._schedule_validation()

            logger.info(f"Marked graph dirty (reason: {reason.value})")

    def mark_node_dirty(self, node_id: str, reason: ChangeReason) -> None:
        """
        Mark a node as needing validation.

        Uses priority system - higher priority reasons override lower ones.
        """
        with self._validation_lock:
            self._set_reason(node_id, reason=reason, store=self._dirty_nodes)
            self._schedule_validation()

            logger.info(f"Marked node dirty: {node_id} (reason: {reason.value})")

    def mark_edge_dirty(self, edge_id: str, reason: ChangeReason) -> None:
        """
        Mark an edge as needing validation.

        Uses priority system - higher priority reasons override lower ones.
        """
        with self._validation_lock:
            self._set_reason(id=edge_id, reason=reason, store=self._dirty_edges)
            self._schedule_validation()

            logger.info(f"Marked edge dirty: {edge_id} (reason: {reason.value})")

    def subscribe(self, callback: ValidationCallback) -> None:
        """
        Subscribe to validation completion events.

        The callback will be invoked after each validation batch completes,
        receiving a ValidationResult with categorized changes.

        Args:
            callback: Callable that accepts ValidationResult
        """
        if callback not in self._callbacks:
            self._callbacks.append(callback)
            logger.debug(f"Added validation subscriber: {callback.__name__}")

    def unsubscribe(self, callback: ValidationCallback) -> None:
        """
        Unsubscribe from validation events.

        Args:
            callback: The callback to remove
        """
        if callback in self._callbacks:
            self._callbacks.remove(callback)
            logger.debug(f"Removed validation subscriber: {callback.__name__}")

    def get_statistics(self) -> Dict[str, Any]:
        """
        Get validation pipeline statistics.

        Returns:
            Dictionary with validation metrics
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

    def force_immediate_validation(self) -> Optional[ValidationResult]:
        """
        Force immediate validation without debouncing.

        Useful for testing or when you need synchronous validation.

        Returns:
            ValidationResult if there were dirty elements, None otherwise
        """
        with self._validation_lock:
            # Cancel any pending debounced run; we're validating now.
            if self._pending_handle is not None:
                self._pending_handle.cancel()
                self._pending_handle = None

            # Only validate if there are dirty elements
            if not self._dirty_nodes and not self._dirty_edges:
                return None

            # Run validation immediately
            return self._validate_batch()

    def clear(self) -> None:
        """
        Clear all dirty tracking and pending validations.

        Called when graph is cleared or reset.
        """
        with self._validation_lock:
            # Cancel pending validation
            if self._pending_handle is not None:
                self._pending_handle.cancel()
                self._pending_handle = None

            # Clear all tracking
            self._dirty_nodes.clear()
            self._dirty_edges.clear()
            self._dirty_graph = None

            logger.debug("ValidationManager cleared")

    # =========================================================================
    # INTERNAL VALIDATION LOGIC
    # =========================================================================

    def _schedule_validation(self) -> None:
        """
        Schedule a validation pass with debouncing.

        Multiple dirty marks within the debounce window will result in a
        single validation pass, improving efficiency.
        """
        with self._validation_lock:
            # Cancel any pending run before scheduling a fresh one — this is
            # what coalesces a burst of marks into a single batch. cancel() is
            # idempotent and a no-op if the previous run already fired.
            if self._pending_handle is not None:
                self._pending_handle.cancel()
            self._pending_handle = None

            # Bump the generation, then schedule. A synchronous scheduler runs
            # _validate_batch *inside* schedule(), which bumps the generation
            # again and clears _pending_handle. In that case we must not adopt
            # the (inert) returned handle, or pending_validation would lie.
            scheduled_generation = self._batch_generation
            delay_seconds = self._debounce_ms / 1000.0
            handle = self._scheduler.schedule(delay_seconds, self._validate_batch)
            if self._batch_generation == scheduled_generation:
                # No inline run happened — this is a genuinely pending handle.
                self._pending_handle = handle

            logger.debug(
                f"Scheduled validation in {self._debounce_ms}ms "
                f"({len(self._dirty_nodes)} nodes, {len(self._dirty_edges)} edges)"
            )

    def _validate_batch(self) -> ValidationResult:
        """
        Execute a validation batch for all dirty elements.

        Returns ValidationResult with element IDs mapped to their change reasons.
        """
        start_time = time.perf_counter()

        with self._validation_lock:
            # This run consumes the pending schedule. Clearing it here keeps
            # ``pending_validation`` honest and means a re-entrant mark during
            # this batch schedules a genuinely new run. (When invoked via
            # SyncScheduler the handle is already inert.) The generation bump
            # lets _schedule_validation see that a synchronous batch ran
            # inside its schedule() call.
            self._pending_handle = None
            self._batch_generation += 1

            # Snapshot dirty elements with their reasons
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

            # Result will contain all changed elements with their reasons
            validated_nodes: Dict[str, ChangeReason] = {}
            validated_edges: Dict[str, ChangeReason] = {}
            validated_graph: Optional[ChangeReason] = None

            if dirty_graph is not None:
                if dirty_graph.requires_graph_reassembly():
                    validated_graph = dirty_graph
            # Validate nodes
            for node_id, reason in dirty_nodes.items():
                try:
                    # For removal, just track it
                    if reason.requires_removal():
                        validated_nodes[node_id] = reason
                        validated_graph = ChangeReason.GRAPH_REQUIRE_REASSEMBLY
                        continue

                    if reason.requires_adding():
                        validated_nodes[node_id] = reason
                        validated_graph = ChangeReason.GRAPH_REQUIRE_REASSEMBLY
                        continue

                    if reason.requires_rebuild():
                        # For structural changes, validate
                        node_wrapper = self._graph.get_node_wrapper(node_id)
                        if node_wrapper:
                            node_wrapper.build()
                            edge_wrappers = self._graph._get_edge_wrappers_for_node(node_id)
                            for edge_wrapper in edge_wrappers:
                                # we add all the attached edges to this node to
                                # the list of edges that need to be validated
                                # we need to be carefull and
                                # adhere to the reason priorities
                                self._set_reason(id=edge_wrapper.edge_id, reason=reason, store=dirty_edges)
                            # Always include in result with its reason
                            validated_nodes[node_id] = reason
                            validated_graph = ChangeReason.GRAPH_REQUIRE_REASSEMBLY
                            continue

                    if reason.requires_validation():
                        # For structural changes, validate
                        node_wrapper = self._graph.get_node_wrapper(node_id)
                        if node_wrapper:
                            edge_wrappers = self._graph._get_edge_wrappers_for_node(node_id)
                            for edge_wrapper in edge_wrappers:
                                # we add all the attached edges to this node to
                                # the list of edges that need to be validated
                                # we need to be carefull and
                                # adhere to the reason priorities
                                self._set_reason(id=edge_wrapper.edge_id, reason=reason, store=dirty_edges)
                            # Always include in result with its reason
                            validated_nodes[node_id] = reason
                            validated_graph = ChangeReason.GRAPH_REQUIRE_REASSEMBLY
                            continue

                    # For visual-only changes, skip validation
                    if reason.requires_redraw():
                        validated_nodes[node_id] = reason
                        continue

                except Exception as e:
                    logger.error(f"Node validation failed: {node_id}", exc_info=e)

            # Validate edges
            for edge_id, reason in dirty_edges.items():
                try:
                    # For removal, just track it
                    if reason.requires_removal():
                        validated_edges[edge_id] = reason
                        validated_graph = ChangeReason.GRAPH_REQUIRE_REASSEMBLY
                        continue

                    if reason.requires_adding():
                        # Update port links (needs to be done after registration)
                        validated_edges[edge_id] = reason
                        validated_graph = ChangeReason.GRAPH_REQUIRE_REASSEMBLY
                        continue

                    found_edge_wrapper = self._graph.get_edge_wrapper(edge_id)
                    if reason.requires_rebuild() or reason.requires_validation():
                        # we play it safe - in case the node has changed the type of an
                        # existing port with the same id the edge is rebuild and validated
                        if found_edge_wrapper:
                            was_functional = found_edge_wrapper.is_functional()
                            found_edge_wrapper.build()
                            if found_edge_wrapper.is_functional():
                                found_edge_wrapper.link()
                            elif was_functional:
                                # Lost functionality during rebuild
                                found_edge_wrapper.unlink()
                            # Always include in result with its reason
                            validated_edges[edge_id] = reason
                            validated_graph = ChangeReason.GRAPH_REQUIRE_REASSEMBLY
                            continue

                    # For visual-only changes, skip validation
                    if reason.requires_redraw():
                        validated_edges[edge_id] = reason
                        continue

                except Exception as e:
                    logger.error(f"Edge validation failed: {edge_id}", exc_info=e)

            # Now that all nodes and edges are validated, we can
            # Do the housekeeping on nodes that require rebuild or validation
            for node_id, reason in validated_nodes.items():
                if reason.requires_adding() or reason.requires_rebuild() or reason.requires_validation():
                    node_wrapper = self._graph.get_node_wrapper(node_id)
                    if node_wrapper:
                        node_wrapper._housekeeping()

            # Build simplified result
            validation_time_ms = (time.perf_counter() - start_time) * 1000.0

            # Capture a pending canvas resize that was set by BaseGraph during
            # add/move/remove operations that happened in this validation window.
            canvas_size = None
            if self._graph._canvas_size_changed:
                canvas_size = (self._graph.canvas_width, self._graph.canvas_height)
                self._graph._canvas_size_changed = False

            result = ValidationResult(
                nodes=validated_nodes,
                edges=validated_edges,
                graph=validated_graph,
                canvas_size=canvas_size,
                validation_time_ms=validation_time_ms,
            )

            # Update statistics
            self._validation_count += 1
            self._last_validation_time = time.time()
            self._total_validation_time_ms += validation_time_ms

            logger.info(
                f"Validation complete: {len(result.nodes)} nodes, {len(result.edges)} edges in "
                f"{validation_time_ms:.2f}ms"
            )

            # Notify subscribers (only if there were changes)
            if result.has_changes():
                self._notify_subscribers(result)

            return result

    def _notify_subscribers(self, result: ValidationResult) -> None:
        """
        Notify all validation subscribers with the result.

        Args:
            result: ValidationResult with categorized changes
        """
        logger.debug(f"Notifying {len(self._callbacks)} validation subscribers")

        # Copy list to prevent modification during iteration
        for callback in self._callbacks[:]:
            try:
                callback(result)
            except Exception as e:
                logger.error(f"Validation callback error in {callback.__name__}: {e}", exc_info=True)
