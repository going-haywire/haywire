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
    """
    
    # Node reasons - structural changes (require redraw)
    NODE_ADDED = "node_added"
    NODE_REMOVED = "node_removed"
    NODE_HOT_RELOADED = "node_hot_reloaded"
    NODE_HOT_RELOAD_ERROR = "node_error"
    NODE_REDRAW_REQUESTED = "node_redraw_requested"
    
    # Node reasons - visual only (no redraw needed)
    NODE_MOVED = "node_moved"
    NODE_SELECTED = "node_selected"
    NODE_DESELECTED = "node_deselected"
    
    # Edge reasons - structural changes (require redraw)
    EDGE_ADDED = "edge_added"
    EDGE_REMOVED = "edge_removed"
    EDGE_ADAPTERS_RELOADED = "edge_adapters_reloaded"
    EDGE_HOT_RELOAD_ERROR = "edge_error"
    
    # Edge reasons - visual only (no redraw needed)
    EDGE_PORT_CHANGED = "edge_port_changed"
    EDGE_SELECTED = "edge_selected"
    EDGE_DESELECTED = "edge_deselected"
    EDGE_VALIDATION_CHANGE = "edge_validation_change"

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


    def requires_validation(self) -> bool:
        validation_reasons = {
            ChangeReason.NODE_HOT_RELOADED,
            ChangeReason.EDGE_ADAPTERS_RELOADED,
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
            ChangeReason.EDGE_ADAPTERS_RELOADED,
            ChangeReason.EDGE_HOT_RELOAD_ERROR,
            ChangeReason.EDGE_VALIDATION_CHANGE,
            ChangeReason.EDGE_SELECTED,
            ChangeReason.EDGE_DESELECTED
        }
        return self in redraw_reasons
        

@dataclass
class ValidationResult:
    """
    Result of a validation batch with reason-based changes.
    
    Subscribers receive dictionaries mapping element IDs to their change reasons,
    allowing flexible handling based on the type of change.
    """
    
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
        return len(self.nodes) + len(self.edges)
    
    def has_changes(self) -> bool:
        """Check if this validation found any changes"""
        return bool(self.nodes or self.edges)
    
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