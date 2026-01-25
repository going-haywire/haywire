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
from typing import Dict, List, Set, Callable, Optional, Any, TYPE_CHECKING

from haywire.core.node import node_wrapper

from .types import ChangeReason, ValidationResult

if TYPE_CHECKING:
    from .base import BaseGraph
    from ..node.node_wrapper import NodeWrapper
    from ..edge.edge_wrapper import EdgeWrapper

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
    
    def __init__(self, graph: 'BaseGraph', debounce_ms: float = 50.0):
        self._graph = graph
        self._debounce_ms = debounce_ms
        
        # Simplified tracking - just map elements to reasons
        self._dirty_nodes: Dict[str, ChangeReason] = {}
        """node_id -> reason for being dirty"""
        
        self._dirty_edges: Dict[str, ChangeReason] = {}
        """connection_uuid -> reason for being dirty"""
        
        # Timer and synchronization
        self._validation_timer: Optional[threading.Timer] = None
        self._validation_lock = threading.RLock()
        
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

    def mark_node_dirty(
        self,
        node_id: str,
        reason: ChangeReason
    ) -> None:
        """
        Mark a node as needing validation.
        
        Uses priority system - higher priority reasons override lower ones.
        """
        with self._validation_lock:
            self._set_reason(node_id, reason=reason, store=self._dirty_nodes)
            self._schedule_validation()
            
            logger.debug(
                f"Marked node dirty: {node_id} (reason: {reason.value})"
            )
    
    def mark_edge_dirty(
        self,
        connection_uuid: str,
        reason: ChangeReason
    ) -> None:
        """
        Mark an edge as needing validation.
        
        Uses priority system - higher priority reasons override lower ones.
        """
        with self._validation_lock:
            self._set_reason(id=connection_uuid, reason=reason, store=self._dirty_edges)
            self._schedule_validation()
            
            logger.debug(
                f"Marked edge dirty: {connection_uuid} "
                f"(reason: {reason.value})"
            )

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
                'validation_count': self._validation_count,
                'last_validation_time': self._last_validation_time,
                'average_validation_time_ms': avg_time,
                'total_validation_time_ms': self._total_validation_time_ms,
                'debounce_ms': self._debounce_ms,
                'dirty_nodes': len(self._dirty_nodes),
                'dirty_edges': len(self._dirty_edges),
                'subscriber_count': len(self._callbacks),
                'pending_validation': (
                    self._validation_timer is not None and 
                    self._validation_timer.is_alive()
                )
            }
    
    def force_immediate_validation(self) -> Optional[ValidationResult]:
        """
        Force immediate validation without debouncing.
        
        Useful for testing or when you need synchronous validation.
        
        Returns:
            ValidationResult if there were dirty elements, None otherwise
        """
        with self._validation_lock:
            # Cancel pending timer
            if self._validation_timer and self._validation_timer.is_alive():
                self._validation_timer.cancel()
            
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
            if self._validation_timer and self._validation_timer.is_alive():
                self._validation_timer.cancel()
                self._validation_timer = None
            
            # Clear all tracking
            self._dirty_nodes.clear()
            self._dirty_edges.clear()
            
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
            # Cancel existing timer if any
            if self._validation_timer and self._validation_timer.is_alive():
                self._validation_timer.cancel()
            
            # Schedule new validation
            delay_seconds = self._debounce_ms / 1000.0
            self._validation_timer = threading.Timer(
                delay_seconds,
                self._validate_batch
            )
            self._validation_timer.daemon = True
            self._validation_timer.start()
            
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
            # Snapshot dirty elements with their reasons
            dirty_nodes = dict(self._dirty_nodes)
            dirty_edges = dict(self._dirty_edges)
            
            logger.info(
                f"Starting validation batch: "
                f"{len(dirty_nodes)} nodes, {len(dirty_edges)} edges"
            )
            
            # Result will contain all changed elements with their reasons
            validated_nodes: Dict[str, ChangeReason] = {}
            validated_edges: Dict[str, ChangeReason] = {}
            
            # Validate nodes
            for node_id, reason in dirty_nodes.items():
                try:
                    # For removal, just track it
                    if reason.requires_removal():
                        validated_nodes[node_id] = reason
                        continue

                    if reason.requires_adding():
                        validated_nodes[node_id] = reason
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
                                self._set_reason(
                                    id=edge_wrapper.connection_uuid,
                                    reason=reason,
                                    store=dirty_edges)
                            # Always include in result with its reason
                            validated_nodes[node_id] = reason
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
                                self._set_reason(
                                    id=edge_wrapper.connection_uuid,
                                    reason=reason,
                                    store=dirty_edges)
                            continue                   

                    # For visual-only changes, skip validation
                    if reason.requires_redraw():
                        validated_nodes[node_id] = reason
                        continue
                    
                    
                except Exception as e:
                    logger.error(
                        f"Node validation failed: {node_id}",
                        exc_info=e
                    )
            
            # Validate edges
            for connection_uuid, reason in dirty_edges.items():
                try:
                    # For removal, just track it
                    if reason.requires_removal():
                        validated_edges[connection_uuid] = reason
                        continue

                    if reason.requires_adding():
                        # Update port links (needs to be done after registration)
                        validated_edges[connection_uuid] = reason
                        continue

                    edge_wrapper = self._graph.get_edge_wrapper(connection_uuid)
                    if reason.requires_rebuild() or \
                        reason.requires_validation():
                        # we play it safe - in case the node has changed the type of an 
                        # existing port with the same id the edge is rebuild and validated
                        if edge_wrapper:                            
                            edge_wrapper.build()
                            self._graph.update_port_link(edge_wrapper)
                            # Always include in result with its reason
                            validated_edges[connection_uuid] = reason
                            continue
                    
                    # For visual-only changes, skip validation
                    if reason.requires_redraw():
                        validated_edges[connection_uuid] = reason
                        continue

                except Exception as e:
                    logger.error(
                        f"Edge validation failed: {connection_uuid}",
                        exc_info=e
                    )
            
            # Now that all nodes and edges are validated, we can
            # Do the housekeeping on nodes that require rebuild or validation
            for node_id, reason in validated_nodes.items():
                if reason.requires_rebuild() or reason.requires_validation():
                    node_wrapper = self._graph.get_node_wrapper(node_id)
                    if node_wrapper:
                        node_wrapper._housekeeping()

            # Build simplified result
            validation_time_ms = (time.perf_counter() - start_time) * 1000.0
            
            result = ValidationResult(
                nodes=validated_nodes,
                edges=validated_edges,
                validation_time_ms=validation_time_ms
            )
            
            # Clear dirty tracking
            self._dirty_nodes.clear()
            self._dirty_edges.clear()
            
            # Update statistics
            self._validation_count += 1
            self._last_validation_time = time.time()
            self._total_validation_time_ms += validation_time_ms
            
            logger.info(
                f"Validation complete: {result.total_changes} changes in "
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
        logger.debug(
            f"Notifying {len(self._callbacks)} validation subscribers"
        )
        
        # Copy list to prevent modification during iteration
        for callback in self._callbacks[:]:
            try:
                callback(result)
            except Exception as e:
                logger.error(
                    f"Validation callback error in {callback.__name__}: {e}",
                    exc_info=True
                )