# haywire/core/graph/types.py
"""Change reasons and batch results shared by the graph validation pipeline."""

from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, Optional, Tuple


class ChangeReason(Enum):
    """Why a node, edge or graph was marked dirty.

    Subscribers read it to decide how to react. The ``requires_*`` methods
    group the reasons, and ``get_priority`` orders them when two marks land on
    one element: removal, then adding, rebuild, validation, redraw, graph
    reassembly, and everything else last.
    """

    # Graph reasons
    GRAPH_REQUIRE_REASSEMBLY = "graph_require_assembly"
    """Aspects of the graph have changed that require it to be reassembled."""

    # Node reasons that rebuild or revalidate the node
    NODE_ADDED = "node_added"
    NODE_REMOVED = "node_removed"
    NODE_HOT_RELOADED = "node_hot_reloaded"
    NODE_HOT_RELOAD_ERROR = "node_error"
    NODE_REDRAW_REQUESTED = "node_redraw_requested"
    NODE_VALIDATION_REQUESTED = "node_validation_requested"
    NODE_RESET_REQUESTED = "node_reset_requested"

    # Node reason that changes no structure
    NODE_MOVED = "node_moved"

    # Edge reasons that rebuild or revalidate the edge
    EDGE_ADDED = "edge_added"
    EDGE_REMOVED = "edge_removed"
    EDGE_ADAPTERS_RELOADED = "edge_adapters_reloaded"
    EDGE_HOT_RELOAD_ERROR = "edge_error"
    EDGE_VALIDATION_REQUESTED = "edge_validation_requested"
    EDGE_RESET_REQUESTED = "edge_reset_requested"

    # Edge reasons that change no structure
    EDGE_PORT_CHANGED = "edge_port_changed"
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
            ChangeReason.NODE_RESET_REQUESTED,
            ChangeReason.EDGE_ADAPTERS_RELOADED,
            ChangeReason.EDGE_RESET_REQUESTED,
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
            ChangeReason.NODE_REDRAW_REQUESTED,
            ChangeReason.NODE_VALIDATION_REQUESTED,
            ChangeReason.EDGE_ADAPTERS_RELOADED,
            ChangeReason.EDGE_HOT_RELOAD_ERROR,
            ChangeReason.EDGE_REDRAW_REQUESTED,
            ChangeReason.EDGE_VALIDATION_REQUESTED,
        }
        return self in redraw_reasons

    def is_visual_only(self) -> bool:
        """Return whether this reason repaints the UI without changing data a save records.

        An app layer must not mark the file unsaved or announce a data
        mutation for one. ``NODE_MOVED`` is not visual-only: a move repaints,
        but position is persisted as ``props.posX``/``posY``.
        """
        visual_reasons = {
            ChangeReason.NODE_REDRAW_REQUESTED,
            ChangeReason.EDGE_REDRAW_REQUESTED,
        }
        return self in visual_reasons

    def requires_graph_reassembly(self) -> bool:
        """Check if this reason requires graph reassembly"""
        reassembly_reasons = {
            ChangeReason.NODE_ADDED,
            ChangeReason.EDGE_ADDED,
            ChangeReason.NODE_REMOVED,
            ChangeReason.EDGE_REMOVED,
            ChangeReason.NODE_HOT_RELOADED,
            ChangeReason.NODE_HOT_RELOAD_ERROR,
            ChangeReason.NODE_RESET_REQUESTED,
            ChangeReason.NODE_VALIDATION_REQUESTED,
            ChangeReason.EDGE_HOT_RELOAD_ERROR,
            ChangeReason.EDGE_RESET_REQUESTED,
            ChangeReason.EDGE_VALIDATION_REQUESTED,
            ChangeReason.GRAPH_REQUIRE_REASSEMBLY,
        }
        return self in reassembly_reasons

    def get_priority(self) -> int:
        """Return this reason's priority; the higher number wins when two marks collide.

        Returns:
            100 for a removal, 90 adding, 80 rebuild, 70 validation, 60
            redraw, 50 graph reassembly, 40 for anything else.
        """
        if self.requires_removal():
            return 100

        if self.requires_adding():
            return 90

        if self.requires_rebuild():
            return 80

        if self.requires_validation():
            return 70

        if self.requires_redraw():
            return 60

        if self.requires_graph_reassembly():
            return 50

        return 40

    def has_higher_priority_than(self, other: "ChangeReason") -> bool:
        """Check if this reason has higher priority than another."""
        return self.get_priority() > other.get_priority()


@dataclass
class ValidationResult:
    """What one validation batch changed, as maps of element ID to change reason."""

    graph: ChangeReason | None = None
    """Reason for whole graph change, if applicable"""

    nodes: Dict[str, ChangeReason] = field(default_factory=dict)
    """Map of node_id -> reason for change"""

    edges: Dict[str, ChangeReason] = field(default_factory=dict)
    """Map of connection_uuid -> reason for change"""

    canvas_size: Optional[Tuple[int, int]] = None
    """New (width, height) of the canvas if it was resized during this batch, else None."""

    validation_time_ms: float = 0.0
    """Time taken for validation in milliseconds"""

    @property
    def total_changes(self) -> int:
        """Total number of changes in this batch"""
        return len(self.nodes) + len(self.edges) + (1 if self.graph is not None else 0)

    def has_changes(self) -> bool:
        """Check if this validation found any changes"""
        return bool(self.nodes or self.edges or self.graph is not None or self.canvas_size is not None)

    def get_nodes_by_reason(self, reason: ChangeReason) -> list[str]:
        """Get all node IDs that changed for a specific reason"""
        return [node_id for node_id, r in self.nodes.items() if r == reason]

    def get_edges_by_reason(self, reason: ChangeReason) -> list[str]:
        """Get all edge UUIDs that changed for a specific reason"""
        return [edge_id for edge_id, r in self.edges.items() if r == reason]

    def get_nodes_requiring_redraw(self) -> list[str]:
        """Get all node IDs that need UI redraw"""
        return [node_id for node_id, reason in self.nodes.items() if reason.requires_redraw()]

    def get_edges_requiring_redraw(self) -> list[str]:
        """Get all edge UUIDs that need UI redraw"""
        return [edge_id for edge_id, reason in self.edges.items() if reason.requires_redraw()]

    def get_removed_nodes(self) -> list[str]:
        """Get all node IDs that were removed"""
        return self.get_nodes_by_reason(ChangeReason.NODE_REMOVED)

    def get_removed_edges(self) -> list[str]:
        """Get all edge UUIDs that were removed"""
        return self.get_edges_by_reason(ChangeReason.EDGE_REMOVED)
