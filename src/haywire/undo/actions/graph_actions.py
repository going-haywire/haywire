"""
Graph-specific actions for the Haywire undo system.

This module contains actions that operate on the graph structure,
including node and edge manipulation, positioning, and selection.
"""

import time
from typing import Optional, Dict, Any, List, Tuple
from dataclasses import dataclass

from haywire.core.node.node_factory import NodeFactory
from haywire.core.node.node_wrapper import NodeWrapper

from ..base_action import ActionBase, CompositeAction
from ...core.graph.graph import HaywireGraph, Edge
from ...core.node.node import BaseNode
from ...ui.utils import generate_connection_uuid


class AddNodeAction(ActionBase):
    """Action for adding a node to the graph."""

    def __init__(
            self, 
            graph: HaywireGraph, 
            registry_key: str, 
            node_factory: 'NodeFactory', 
            position: Tuple[float, float] = (100, 100),
            description: Optional[str] = None):
        """
        Initialize the add node action.
        
        Args:
            graph: The graph to add the node to
            node: The node to add
            description: Optional description override
        """
        # Use library label if available, otherwise fallback to identity name or node_id or class name
        super().__init__(description or f"Add node '{registry_key}'")
        self.graph = graph
        self.registry_key = registry_key
        self.node_factory = node_factory
        self.position = position
        self.wrapper = None

    def _execute_impl(self) -> None:
        """Add the node to the graph."""
        self.wrapper = NodeWrapper(registry_key=self.registry_key, node_factory=self.node_factory, position=self.position)
        self.wrapper.register(self.graph)
    
    def _undo_impl(self) -> None:
        """Remove the node from the graph."""
        self.graph.remove_node_wrapper(self.wrapper)

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
                node.ui_state.posX += self.deltaX
                node.ui_state.posY += self.deltaY
    
    def _undo_impl(self) -> None:
        """Move all nodes back by subtracting the delta amounts."""
        for node_id in self.nodes:
            node = self.graph.get_node(node_id)
            if node:
                node.ui_state.posX -= self.deltaX
                node.ui_state.posY -= self.deltaY
    
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

class RemoveElementsAction(ActionBase):
    """Action for removing multiple nodes and connections in a single operation."""
    
    def __init__(self, graph: HaywireGraph, nodes: List[str] = None, connections: List[str] = None,
                 description: Optional[str] = None):
        """
        Initialize the remove elements action.
        
        Args:
            graph: The graph to remove elements from
            nodes: List of node IDs to remove
            connections: List of connection UUIDs to remove
            description: Optional description override
        """
        nodes = nodes or []
        connections = connections or []
        
        total_count = len(nodes) + len(connections)
        if total_count == 0:
            raise ValueError("Must specify at least one node or connection to remove")
        elif total_count == 1:
            if nodes:
                super().__init__(description or f"Remove node '{nodes[0]}'")
            else:
                super().__init__(description or f"Remove connection")
        else:
            super().__init__(description or f"Remove {total_count} elements")
        
        self.graph = graph
        self.nodes = nodes
        self.connections = connections
        
        # Store removed elements for restoration
        self.removed_wrappers: Dict[str, NodeWrapper] = {}
        self.removed_edges: Dict[str, Edge] = {}
        self.node_connected_edges: Dict[str, List[Edge]] = {}  # node_id -> edges that were connected to it
    
    def _execute_impl(self) -> None:
        """Remove all specified elements and store them for undo."""
        # First, store and remove connections
        for connection_uuid in self.connections:
            edge = self.graph.get_edge(connection_uuid)
            if edge:
                self.removed_edges[connection_uuid] = edge
                self.graph.remove_edge_by_uuid(connection_uuid)
        
        # Then, store and remove nodes (which will also remove any remaining connected edges)
        for node_id in self.nodes:
            wrapper = self.graph.get_node_wrapper(node_id)
            if wrapper:
                self.removed_wrappers[node_id] = wrapper
                
                # Store all edges connected to this node for restoration
                connected_edges = []
                for edge in list(self.graph.edges.values()):
                    if edge.input_node_id == node_id or edge.output_node_id == node_id:
                        connected_edges.append(edge)
                
                self.node_connected_edges[node_id] = connected_edges
                
                # Remove the node wrapper (this will also remove connected edges)
                self.graph.remove_node_wrapper(wrapper)
    
    def _undo_impl(self) -> None:
        """Restore all removed elements."""
        # First, restore node wrappers
        for node_id, wrapper in self.removed_wrappers.items():
            self.graph.add_node_wrapper(wrapper)
            
            # Restore edges that were connected to this node
            for edge in self.node_connected_edges.get(node_id, []):
                # Only restore if both nodes still exist
                if (self.graph.get_node(edge.input_node_id) and 
                    self.graph.get_node(edge.output_node_id)):
                    self.graph.add_edge(
                        edge.output_node_id,
                        edge.outlet_pin_id,
                        edge.input_node_id,
                        edge.inlet_pin_id
                    )
        
        # Then, restore standalone connections (that weren't connected to removed nodes)
        for connection_uuid, edge in self.removed_edges.items():
            # Only restore if both nodes still exist
            if (self.graph.get_node(edge.input_node_id) and 
                self.graph.get_node(edge.output_node_id)):
                self.graph.add_edge(
                    edge.output_node_id,
                    edge.outlet_pin_id,
                    edge.input_node_id,
                    edge.inlet_pin_id
                )


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
        new_node.ui_state.posX = source_node.ui_state.posX + offset_x
        new_node.ui_state.posY = source_node.ui_state.posY + offset_y
        
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


@dataclass
class ClipboardData:
    """Session-specific clipboard containing actual node and edge instances"""
    
    # Core data - actual instances, not serialized data
    nodes: Dict[str, BaseNode]  # new_node_id -> node_instance
    edges: Dict[str, Edge]      # new_connection_uuid -> edge_instance
    
    # Mapping for paste operations
    original_to_new_ids: Dict[str, str]  # original_node_id -> new_node_id
    
    # Positioning data
    bounding_box: Dict[str, float]  # min_x, min_y, max_x, max_y
    
    # Metadata
    timestamp: float
    source_session_id: str
    
    def get_paste_offset(self, target_x: float, target_y: float) -> Tuple[float, float]:
        """Calculate offset to position upper-left corner at target position"""
        return (target_x - self.bounding_box['min_x'], 
                target_y - self.bounding_box['min_y'])


class PasteClipboardAction(CompositeAction):
    """Composite action for pasting clipboard contents."""
    
    def __init__(self, graph: HaywireGraph, clipboard_data: 'ClipboardData', 
                 paste_x: float, paste_y: float, description: Optional[str] = None):
        """
        Initialize the paste clipboard action.
        
        Args:
            graph: The graph to paste into
            clipboard_data: The clipboard data containing nodes and edges
            paste_x: X position where to paste (upper-left corner)
            paste_y: Y position where to paste (upper-left corner)
            description: Optional description override
        """
        self.clipboard_data = clipboard_data
        self.paste_position = (paste_x, paste_y)
        
        # Calculate position offset
        offset_x, offset_y = clipboard_data.get_paste_offset(paste_x, paste_y)
        
        # Create sub-actions for each node and edge
        actions = []
        
        # Add node actions
        for node_id, node in clipboard_data.nodes.items():
            # Apply position offset
            node.ui_state.posX += offset_x
            node.ui_state.posY += offset_y
            
            # Set graph reference
            node.graph = graph
            
            # Create add node action
            actions.append(AddNodeAction(graph, node, f"Paste node '{node.identity.label}'"))
        
        # Add edge actions
        for connection_uuid, edge in clipboard_data.edges.items():
            actions.append(AddEdgeAction(graph, edge, f"Paste connection"))
        
        # Determine description
        node_count = len(clipboard_data.nodes)
        edge_count = len(clipboard_data.edges)
        if description is None:
            if node_count > 0 and edge_count > 0:
                description = f"Paste {node_count} nodes and {edge_count} connections"
            elif node_count > 0:
                description = f"Paste {node_count} {'node' if node_count == 1 else 'nodes'}"
            else:
                description = "Paste clipboard contents"
        
        super().__init__(actions, description)

