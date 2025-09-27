"""
Graph-specific actions for the Haywire undo system.

This module contains actions that operate on the graph structure,
including node and edge manipulation, positioning, and selection.
"""

from typing import Optional, Dict, Any, List, Tuple
from dataclasses import dataclass

from ..base_action import ActionBase, CompositeAction
from ...core.graph.graph import HaywireGraph, Edge
from ...core.node.node import BaseNode
from ...ui.utils import generate_connection_uuid


class AddNodeAction(ActionBase):
    """Action for adding a node to the graph."""
    
    def __init__(self, graph: HaywireGraph, node: BaseNode, description: Optional[str] = None):
        """
        Initialize the add node action.
        
        Args:
            graph: The graph to add the node to
            node: The node to add
            description: Optional description override
        """
        # Use node_label if available, otherwise fallback to node_id or class name
        node_name = getattr(node, 'node_label', None) or getattr(node, 'name', None) or node.node_id or node.__class__.__name__
        super().__init__(description or f"Add node '{node_name}'")
        self.graph = graph
        self.node = node
        self.node_id = node.node_id
    
    def _execute_impl(self) -> None:
        """Add the node to the graph."""
        self.graph.add_node(self.node)
    
    def _undo_impl(self) -> None:
        """Remove the node from the graph."""
        self.graph.remove_node(self.node_id)


class RemoveNodeAction(ActionBase):
    """Action for removing a node from the graph."""
    
    def __init__(self, graph: HaywireGraph, node_id: str, description: Optional[str] = None):
        """
        Initialize the remove node action.
        
        Args:
            graph: The graph to remove the node from
            node_id: ID of the node to remove
            description: Optional description override
        """
        super().__init__(description or f"Remove node '{node_id}'")
        self.graph = graph
        self.node_id = node_id
        
        # Store the node and its connections for restoration
        self.removed_node: Optional[BaseNode] = None
        self.removed_edges: List[Edge] = []
    
    def _execute_impl(self) -> None:
        """Remove the node and store it for undo."""
        # Store the node before removing it
        self.removed_node = self.graph.get_node(self.node_id)
        if self.removed_node is None:
            raise ValueError(f"Node {self.node_id} not found in graph")
        
        # Store all edges connected to this node
        self.removed_edges = []
        for edge in list(self.graph.edges.values()):  # Copy list to avoid modification during iteration
            if edge.input_node_id == self.node_id or edge.output_node_id == self.node_id:
                self.removed_edges.append(edge)
        
        # Remove the node (this should also remove connected edges)
        self.graph.remove_node(self.node_id)
    
    def _undo_impl(self) -> None:
        """Restore the node and its connections."""
        if self.removed_node is None:
            raise RuntimeError("Cannot undo: no node was stored")
        
        # Add the node back
        self.graph.add_node(self.removed_node)
        
        # Restore all edges
        for edge in self.removed_edges:
            self.graph.add_edge(
                edge.output_node_id,
                edge.outlet_pin_id,
                edge.input_node_id,
                edge.inlet_pin_id
            )


class AddEdgeAction(ActionBase):
    """Action for adding an edge to the graph."""
    
    def __init__(self, graph: HaywireGraph, edge: Edge, description: Optional[str] = None):
        """
        Initialize the add edge action.
        
        Args:
            graph: The graph to add the edge to
            edge: The edge to add
            description: Optional description override
        """
        super().__init__(description or f"Connect {edge.output_node_id} to {edge.input_node_id}")
        self.graph = graph
        self.edge = edge
        # Generate connection UUID for the new API
        self.connection_uuid = generate_connection_uuid(
            edge.output_node_id, edge.outlet_pin_id, 
            edge.input_node_id, edge.inlet_pin_id
        )
    
    def _execute_impl(self) -> None:
        """Add the edge to the graph."""
        self.graph.add_edge(
            self.edge.output_node_id,
            self.edge.outlet_pin_id,
            self.edge.input_node_id,
            self.edge.inlet_pin_id
        )
    
    def _undo_impl(self) -> None:
        """Remove the edge from the graph."""
        self.graph.remove_edge_by_uuid(self.connection_uuid)


class RemoveEdgeAction(ActionBase):
    """Action for removing an edge from the graph."""
    
    def __init__(self, graph: HaywireGraph, edge: Edge, description: Optional[str] = None):
        """
        Initialize the remove edge action.
        
        Args:
            graph: The graph to remove the edge from
            edge: The edge to remove
            description: Optional description override
        """
        super().__init__(description or f"Disconnect {edge.output_node_id} from {edge.input_node_id}")
        self.graph = graph
        self.edge = edge
        # Generate connection UUID for the new API
        self.connection_uuid = generate_connection_uuid(
            edge.output_node_id, edge.outlet_pin_id, 
            edge.input_node_id, edge.inlet_pin_id
        )
    
    def _execute_impl(self) -> None:
        """Remove the edge from the graph."""
        self.graph.remove_edge_by_uuid(self.connection_uuid)
    
    def _undo_impl(self) -> None:
        """Add the edge back to the graph."""
        self.graph.add_edge(
            self.edge.output_node_id,
            self.edge.outlet_pin_id,
            self.edge.input_node_id,
            self.edge.inlet_pin_id
        )


class MoveNodesAction(ActionBase):
    """Action for moving one or multiple nodes using delta values."""
    
    def __init__(self, graph: HaywireGraph, nodes: List[str], deltaX: float, deltaY: float, 
                 description: Optional[str] = None):
        """
        Initialize the move nodes action.
        
        Args:
            graph: The graph containing the nodes
            nodes: List of node IDs to move
            deltaX: Delta X amount to move all nodes
            deltaY: Delta Y amount to move all nodes
            description: Optional description override
        """
        node_count = len(nodes)
        if node_count == 1:
            super().__init__(description or f"Move node '{nodes[0]}'")
        else:
            super().__init__(description or f"Move {node_count} nodes")
        
        self.graph = graph
        self.nodes = nodes
        self.deltaX = deltaX
        self.deltaY = deltaY
    
    def _execute_impl(self) -> None:
        """Move all nodes by their delta amounts."""
        for node_id in self.nodes:
            node = self.graph.get_node(node_id)
            if node:
                node.ui_posX += self.deltaX
                node.ui_posY += self.deltaY
    
    def _undo_impl(self) -> None:
        """Move all nodes back by subtracting the delta amounts."""
        for node_id in self.nodes:
            node = self.graph.get_node(node_id)
            if node:
                node.ui_posX -= self.deltaX
                node.ui_posY -= self.deltaY
    
    def can_merge(self, other) -> bool:
        """Check if this move can be merged with another delta move of the same nodes."""
        return (isinstance(other, MoveNodesAction) and 
                set(other.nodes) == set(self.nodes) and
                super().can_merge(other))
    
    def merge(self, other) -> Optional['MoveNodesAction']:
        """Merge with another delta move action for the same nodes."""
        if not self.can_merge(other):
            return None
        
        # Combine the deltas
        combined_deltaX = self.deltaX + other.deltaX
        combined_deltaY = self.deltaY + other.deltaY
        
        # Create merged action with combined deltas but original starting positions
        node_count = len(self.nodes)
        if node_count == 1:
            description = f"Move node '{self.nodes[0]}'"
        else:
            description = f"Move {node_count} nodes"
        
        merged = MoveNodesAction(self.graph, self.nodes, combined_deltaX, combined_deltaY, description)
        
        return merged


@dataclass
class SelectionState:
    """Represents a selection state."""
    selected_nodes: set[str]
    selected_connections: set[str]  # Connection UUIDs


class ChangeSelectionAction(ActionBase):
    """Action for changing the selection state."""
    
    def __init__(self, graph: HaywireGraph, new_selection: SelectionState, 
                 description: Optional[str] = None):
        """
        Initialize the change selection action.
        
        Args:
            graph: The graph
            new_selection: The new selection state
            description: Optional description override
        """
        super().__init__(description or "Change selection")
        self.graph = graph
        self.new_selection = new_selection
        
        # Store current selection for undo
        self.old_selection = self._get_current_selection()
    
    def _get_current_selection(self) -> SelectionState:
        """Get the current selection state from the graph."""
        selected_nodes, selected_connections = self.graph.get_selection_state()
        return SelectionState(selected_nodes, selected_connections)
    
    def _apply_selection(self, selection: SelectionState) -> None:
        """Apply a selection state to the graph."""
        self.graph.set_selection_state(selection.selected_nodes, selection.selected_connections)
    
    def _execute_impl(self) -> None:
        """Apply the new selection."""
        self._apply_selection(self.new_selection)
    
    def _undo_impl(self) -> None:
        """Restore the old selection."""
        self._apply_selection(self.old_selection)


class DuplicateNodeAction(CompositeAction):
    """Composite action for duplicating a node."""
    
    def __init__(self, graph: HaywireGraph, source_node_id: str, new_node_id: str,
                 offset_x: float = 50.0, offset_y: float = 50.0):
        """
        Initialize the duplicate node action.
        
        Args:
            graph: The graph
            source_node_id: ID of the node to duplicate
            new_node_id: ID for the new node
            offset_x: X offset for the new node position
            offset_y: Y offset for the new node position
        """
        source_node = graph.get_node(source_node_id)
        if source_node is None:
            raise ValueError(f"Source node {source_node_id} not found")
        
        # Create the duplicated node (this would need proper cloning logic)
        # For now, we'll assume there's a clone method
        new_node = self._clone_node(source_node, new_node_id)
        new_node.ui_posX = source_node.ui_posX + offset_x
        new_node.ui_posY = source_node.ui_posY + offset_y
        
        # Create the sub-actions
        actions = [
            AddNodeAction(graph, new_node, f"Add duplicated node '{new_node_id}'")
        ]
        
        super().__init__(actions, f"Duplicate node '{source_node_id}' as '{new_node_id}'")
    
    def _clone_node(self, source_node: BaseNode, new_id: str) -> BaseNode:
        """Clone a node with a new ID."""
        # This is a placeholder - actual implementation would depend on the node structure
        # and would need to properly copy all node properties and state
        raise NotImplementedError("Node cloning not implemented yet")


class DeleteNodesWithEdgesAction(CompositeAction):
    """Composite action for deleting nodes and their connected edges."""
    
    def __init__(self, graph: HaywireGraph, node_ids: List[str]):
        """
        Initialize the delete nodes with edges action.
        
        Args:
            graph: The graph
            node_ids: List of node IDs to delete
        """
        actions = []
        
        # Create remove actions for each node
        # The RemoveNodeAction already handles connected edges
        for node_id in node_ids:
            actions.append(RemoveNodeAction(graph, node_id))
        
        description = f"Delete {len(node_ids)} node{'s' if len(node_ids) != 1 else ''}"
        super().__init__(actions, description)
