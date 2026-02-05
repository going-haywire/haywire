# haywire/core/graph/types.py
"""
Shared types for graph validation system.
"""
from dataclasses import dataclass, field
from enum import Enum
from typing import Dict


class ChangeReason(Enum):
    """
    Reasons for element changes.
    
    Subscribers can use these to decide how to handle updates:
    - Some reasons require full UI redraw (ADDED, HOT_RELOADED)
    - Some only need visual updates (MOVED, SELECTED)
    - Some need removal (REMOVED)
    
    Priority order (highest to lowest):
    REMOVED > ADDED > HOT_RELOADED/ADAPTERS_RELOADED > VALIDATION_REQUESTED > REDRAW > GRAPH_REQUIRE_REASSEMBLY
    """
    
    # Graph reasons
    GRAPH_REQUIRE_REASSEMBLY = "graph_require_assembly"
    """Aspects of the graph have changed that require it to be reassembled."""

    # Node reasons - structural changes (require redraw)
    NODE_ADDED = "node_added"
    NODE_REMOVED = "node_removed"
    NODE_HOT_RELOADED = "node_hot_reloaded"
    NODE_HOT_RELOAD_ERROR = "node_error"
    NODE_REDRAW_REQUESTED = "node_redraw_requested"
    NODE_VALIDATION_REQUESTED = "node_validation_requested"
    
    # Node reasons - visual only (no redraw needed)
    NODE_MOVED = "node_moved"
    NODE_SELECTED = "node_selected"
    NODE_DESELECTED = "node_deselected"
    
    # Edge reasons - structural changes (require redraw)
    EDGE_ADDED = "edge_added"
    EDGE_REMOVED = "edge_removed"
    EDGE_ADAPTERS_RELOADED = "edge_adapters_reloaded"
    EDGE_HOT_RELOAD_ERROR = "edge_error"
    EDGE_VALIDATION_REQUESTED = "edge_validation_requested"
    
    # Edge reasons - visual only (no redraw needed)
    EDGE_PORT_CHANGED = "edge_port_changed"
    EDGE_SELECTED = "edge_selected"
    EDGE_DESELECTED = "edge_deselected"
    EDGE_REDRAW_REQUESTED = "edge_redraw_requested"

    def requires_adding(self) -> bool:
        adding_reasons = {
            ChangeReason.NODE_ADDED,
            ChangeReason.EDGE_ADDED,
        }
        return self in adding_reasons

    def requires_removal(self) -> bool:
        removal_reasons = {
            ChangeReason.NODE_REMOVED,
            ChangeReason.EDGE_REMOVED,
        }
        return self in removal_reasons


    def requires_rebuild(self) -> bool:
        validation_reasons = {
            ChangeReason.NODE_HOT_RELOADED,
            ChangeReason.EDGE_ADAPTERS_RELOADED,
        }
        return self in validation_reasons

    def requires_validation(self) -> bool:
        validation_reasons = {
            ChangeReason.NODE_VALIDATION_REQUESTED,
            ChangeReason.EDGE_VALIDATION_REQUESTED,
        }
        return self in validation_reasons

    def requires_redraw(self) -> bool:
        """Check if this reason requires full UI redraw"""
        redraw_reasons = {
            ChangeReason.NODE_HOT_RELOADED,
            ChangeReason.NODE_HOT_RELOAD_ERROR,
            ChangeReason.NODE_MOVED,
            ChangeReason.NODE_SELECTED,
            ChangeReason.NODE_DESELECTED,
            ChangeReason.NODE_REDRAW_REQUESTED,
            ChangeReason.NODE_VALIDATION_REQUESTED,
            ChangeReason.EDGE_ADAPTERS_RELOADED,
            ChangeReason.EDGE_HOT_RELOAD_ERROR,
            ChangeReason.EDGE_SELECTED,
            ChangeReason.EDGE_DESELECTED,
            ChangeReason.EDGE_REDRAW_REQUESTED,
            ChangeReason.EDGE_VALIDATION_REQUESTED,
        }
        return self in redraw_reasons
    
    def requires_graph_reassembly(self) -> bool:
        """Check if this reason requires graph reassembly"""
        reassembly_reasons = {
            ChangeReason.NODE_ADDED,
            ChangeReason.EDGE_ADDED,
            ChangeReason.NODE_REMOVED,
            ChangeReason.EDGE_REMOVED,
            ChangeReason.NODE_HOT_RELOADED,
            ChangeReason.NODE_HOT_RELOAD_ERROR,
            ChangeReason.NODE_VALIDATION_REQUESTED,
            ChangeReason.EDGE_HOT_RELOAD_ERROR,
            ChangeReason.EDGE_VALIDATION_REQUESTED,
            ChangeReason.GRAPH_REQUIRE_REASSEMBLY,
        }        
        return self in reassembly_reasons
    
    def get_priority(self) -> int:
        """
        Get the priority level of this reason.
        Higher numbers = higher priority (processed first, not overridden).
        
        Priority levels:
        100: REMOVED (highest - always wins)
        90:  ADDED
        80:  HOT_RELOADED/ADAPTERS_RELOADED (rebuild)
        70:  VALIDATION_REQUESTED
        60:  REDRAW_REQUESTED
        50:  Visual changes (MOVED, SELECTED, etc.) - lowest
        """
        # Removal has highest priority
        if self.requires_removal():
            return 100
        
        # Adding has second highest
        if self.requires_adding():
            return 90
        
        # Rebuild has third
        if self.requires_rebuild():
            return 80
        
        # Validation has fourth
        if self.requires_validation():
            return 70
        
        # Redraw has fifth
        if self.requires_redraw():
            return 60
        
        if self.requires_graph_reassembly():
            return 50
        
        # Everything else (visual changes)
        return 40

    def has_higher_priority_than(self, other: 'ChangeReason') -> bool:
        """Check if this reason has higher priority than another."""
        return self.get_priority() > other.get_priority()


@dataclass
class ValidationResult:
    """
    Result of a validation batch with reason-based changes.
    
    Subscribers receive dictionaries mapping element IDs to their change reasons,
    allowing flexible handling based on the type of change.
    """

    graph: ChangeReason | None = None
    """Reason for whole graph change, if applicable"""
    
    nodes: Dict[str, ChangeReason] = field(default_factory=dict)
    """Map of node_id -> reason for change"""
    
    edges: Dict[str, ChangeReason] = field(default_factory=dict)
    """Map of connection_uuid -> reason for change"""
    
    # Metadata
    validation_time_ms: float = 0.0
    """Time taken for validation in milliseconds"""
    
    @property
    def total_changes(self) -> int:
        """Total number of changes in this batch"""
        return len(self.nodes) + len(self.edges) + (1 if self.graph is not None else 0)
    
    def has_changes(self) -> bool:
        """Check if this validation found any changes"""
        return bool(self.nodes or self.edges or self.graph is not None)
    
    def get_nodes_by_reason(self, reason: ChangeReason) -> list[str]:
        """Get all node IDs that changed for a specific reason"""
        return [
            node_id for node_id, r in self.nodes.items() 
            if r == reason
        ]
    
    def get_edges_by_reason(self, reason: ChangeReason) -> list[str]:
        """Get all edge UUIDs that changed for a specific reason"""
        return [
            edge_id for edge_id, r in self.edges.items() 
            if r == reason
        ]
    
    def get_nodes_requiring_redraw(self) -> list[str]:
        """Get all node IDs that need UI redraw"""
        return [
            node_id for node_id, reason in self.nodes.items()
            if reason.requires_redraw()
        ]
    
    def get_edges_requiring_redraw(self) -> list[str]:
        """Get all edge UUIDs that need UI redraw"""
        return [
            edge_id for edge_id, reason in self.edges.items()
            if reason.requires_redraw()
        ]
    
    def get_removed_nodes(self) -> list[str]:
        """Get all node IDs that were removed"""
        return self.get_nodes_by_reason(ChangeReason.NODE_REMOVED)
    
    def get_removed_edges(self) -> list[str]:
        """Get all edge UUIDs that were removed"""
        return self.get_edges_by_reason(ChangeReason.EDGE_REMOVED)