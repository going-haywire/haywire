"""
Graph-specific actions for the Haywire undo system.

This module contains actions that operate on the graph structure,
including node and edge manipulation, positioning, and selection.
"""

from typing import Optional, Dict, List, Tuple
from dataclasses import dataclass

from ...node import BaseNode, NodeWrapper
from ...graph.base import BaseGraph
from ...edge.edge_wrapper import EdgeWrapper, Edge
from ..base_action import ActionBase, CompositeAction

class AddNodeAction(ActionBase):
    """Action for adding a node to the graph."""

    def __init__(
            self, 
            graph: BaseGraph, 
            registry_key: str, 
            position: Tuple[float, float] = (100, 100),
            description: Optional[str] = None):
        """
        Initialize the add node action.
        
        Args:
            graph: The graph to add the node to
            registry_key: Node type to create
            position: Initial position for the node
            description: Optional description override
        """
        super().__init__(description or f"Add node '{registry_key}'")
        self.graph = graph
        self.registry_key = registry_key
        self.position = position
        self.wrapper = None

        self.undo_wrapper = None

    def _execute_impl(self) -> None:
        """Add the node to the graph."""
        if self.wrapper is None:
            # First execution: Create new wrapper via graph
            self.wrapper = self.graph.create_node_wrapper(
                registry_key=self.registry_key,
                position=self.position
            )
        else:
            # Redo: Re-add existing wrapper
            self.wrapper = self.graph.add_node_wrapper(self.wrapper)
        
        self.undo_wrapper = None

        if not self.wrapper:
            raise RuntimeError(
                f"Failed to create node wrapper '{self.registry_key}'"
            )
    
    def _undo_impl(self) -> None:
        """Remove the node from the graph."""
        if self.wrapper:
            self.undo_wrapper = self.graph.remove_node_wrapper(self.wrapper)

    def cleanup(self) -> None:
        """
        Clean up all undone elements when action is discarded.
        
        This is called when the action is removed from history and
        can no longer be undone. We now permanently cleanup all
        undone node wrappers.
        """
        if self.undo_wrapper:
            self.undo_wrapper.cleanup()

class AddEdgeAction(ActionBase):
    """Action for adding an edge to the graph using EdgeWrapper."""
    
    def __init__(
        self, 
        graph: BaseGraph,
        source_node_id: str,
        outlet_pin_id: str,
        sink_node_id: str,
        inlet_pin_id: str,
        description: Optional[str] = None
    ):
        """
        Initialize the add edge action.
        
        Args:
            graph: The graph to add the edge to
            source_node_id: Source node ID
            outlet_pin_id: Source outlet ID
            sink_node_id: Sink node ID
            inlet_pin_id: Sink inlet ID
            description: Optional description override
        """
        super().__init__(
            description or 
            f"Connect {source_node_id} to {sink_node_id}"
        )
        self.graph = graph
        self.source_node_id = source_node_id
        self.outlet_port_id = outlet_pin_id
        self.sink_node_id = sink_node_id
        self.inlet_port_id = inlet_pin_id
        
        # Wrapper created during execute
        self.wrapper: Optional[EdgeWrapper] = None

        self.undo_wrapper = None
    
    def _execute_impl(self) -> None:
        """Add the edge to the graph."""
        if self.wrapper is None:
            # First execution: Create new wrapper via graph
            self.wrapper = self.graph.create_edge_wrapper(
                self.source_node_id,
                self.outlet_port_id,
                self.sink_node_id,
                self.inlet_port_id
            )
        else:
            # Redo: Re-add existing wrapper
            self.wrapper = self.graph.add_edge_wrapper(self.wrapper)
        
        self.undo_wrapper = None

        if not self.wrapper:
            raise RuntimeError(
                f"Failed to create edge wrapper for connection "
                f"{self.source_node_id}:{self.outlet_port_id} -> "
                f"{self.sink_node_id}:{self.inlet_port_id}"
            )
    
    def _undo_impl(self) -> None:
        """Remove the edge from the graph."""
        if self.wrapper:
            self.undo_wrapper = self.graph.remove_edge_wrapper(self.wrapper.connection_uuid)

    def cleanup(self) -> None:
        """
        Clean up all undone elements when action is discarded.
        
        This is called when the action is removed from history and
        can no longer be undone. We now permanently cleanup all
        undone edge wrappers.
        """
        if self.undo_wrapper:
            self.undo_wrapper.cleanup()



class MoveNodesAction(ActionBase):
    """Action for moving one or multiple nodes using delta values."""
    
    def __init__(self, graph: BaseGraph, nodes: List[str], deltaX: float, deltaY: float, 
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
            node = self.graph.get_node_wrapper(node_id).node
            if node:
                node.ui.state.posX += self.deltaX
                node.ui.state.posY += self.deltaY
    
    def _undo_impl(self) -> None:
        """Move all nodes back by subtracting the delta amounts."""
        for node_id in self.nodes:
            node = self.graph.get_node_wrapper(node_id).node
            if node:
                node.ui.state.posX -= self.deltaX
                node.ui.state.posY -= self.deltaY
    
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
        
        merged = MoveNodesAction(
            self.graph,
            self.nodes,
            combined_deltaX,
            combined_deltaY,
            description
        )
        
        return merged

class RemoveElementsAction(ActionBase):
    """
    Action for removing multiple nodes and connections in a single
    operation.
    """
    
    def __init__(
        self, 
        graph: BaseGraph, 
        nodes: List[str] = None, 
        connections: List[str] = None,
        description: Optional[str] = None
    ):
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
            raise ValueError(
                "Must specify at least one node or connection to remove"
            )
        elif total_count == 1:
            if nodes:
                super().__init__(
                    description or f"Remove node '{nodes[0]}'"
                )
            else:
                super().__init__(description or "Remove connection")
        else:
            super().__init__(
                description or f"Remove {total_count} elements"
            )
        
        self.graph = graph
        self.nodes = nodes
        self.connections = connections
        
        # Store removed elements for restoration
        self.removed_node_wrappers: Dict[str, NodeWrapper] = {}
        self.removed_edge_wrappers: Dict[str, EdgeWrapper] = {}
        # node_id -> edge wrappers that were connected to it
        self.node_connected_edge_wrappers: Dict[str, EdgeWrapper] = {}
    
    def _execute_impl(self) -> None:
        """Remove all specified elements and store them for undo."""
        # First, store and remove connections
        for connection_uuid in self.connections:
            edge_wrapper = self.graph.get_edge_wrapper(connection_uuid)
            if edge_wrapper:
                self.removed_edge_wrappers[connection_uuid] = edge_wrapper
                self.graph.remove_edge_wrapper(connection_uuid)
        
        # Then, store and remove nodes
        for node_id in self.nodes:
            node_wrapper = self.graph.get_node_wrapper(node_id)
            if node_wrapper:
                self.removed_node_wrappers[node_id] = node_wrapper
                
                all_edges = self.graph._get_all_edges(node_id)

                for edge in all_edges:
                    self.node_connected_edge_wrappers[edge.connection_uuid] = edge
                    # Remove the connected edge wrapper
                    self.graph.remove_edge_wrapper(edge.connection_uuid)
                
                # Remove the node wrapper
                self.graph.remove_node_wrapper(node_wrapper)
    
    def _undo_impl(self) -> None:
        """Restore all removed elements."""
        # First, restore node wrappers
        for node_id, node_wrapper in self.removed_node_wrappers.items():
            self.graph.add_node_wrapper(node_wrapper)

        # then, restore all edges connected to restored nodes
        for connection_uuid, edge_wrapper in self.node_connected_edge_wrappers.items():
            # Re-add existing wrapper
            self.graph.add_edge_wrapper(edge_wrapper)
                
        # Then, restore standalone connections
        # (that weren't connected to removed nodes)
        for connection_uuid, edge_wrapper in self.removed_edge_wrappers.items():
            self.graph.add_edge_wrapper(edge_wrapper)
    
        # Clear away store after restoration otherwise
        # they are cleaned-up when the action is discarded
        self.removed_edge_wrappers.clear()
        self.removed_node_wrappers.clear()
        self.node_connected_edge_wrappers.clear()

    def cleanup(self) -> None:
        """
        Clean up all removed elements when action is discarded.
        
        This is called when the action is removed from history and
        can no longer be undone. We now permanently cleanup all
        removed node and edge wrappers.
        """
        # Cleanup all removed edge wrappers
        for edge_wrapper in self.removed_edge_wrappers.values():
            edge_wrapper.cleanup()
        
        # Cleanup all edge wrappers connected to removed nodes
        for edge_wrapper in self.node_connected_edge_wrappers.values():
            edge_wrapper.cleanup()
        
        # Cleanup all removed node wrappers
        for wrapper in self.removed_node_wrappers.values():
            wrapper.cleanup()
        
        # Clear the storage dictionaries
        self.removed_node_wrappers.clear()
        self.removed_edge_wrappers.clear()
        self.node_connected_edge_wrappers.clear()


@dataclass
class SelectionState:
    """Represents a selection state."""
    selected_nodes: set[str]
    selected_connections: set[str]  # Connection UUIDs


class ChangeSelectionAction(ActionBase):
    """Action for changing the selection state."""
    
    def __init__(self, graph: BaseGraph, new_selection: SelectionState, 
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
    
    def __init__(self, graph: BaseGraph, source_node_id: str, new_node_id: str,
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
        source_node = graph.get_node_wrapper(source_node_id).node
        if source_node is None:
            raise ValueError(f"Source node {source_node_id} not found")
        
        # Create the duplicated node (this would need proper cloning logic)
        # For now, we'll assume there's a clone method
        new_node = self._clone_node(source_node, new_node_id)
        new_node.ui.state.posX = source_node.ui.state.posX + offset_x
        new_node.ui.state.posY = source_node.ui.state.posY + offset_y
        
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
    
    def __init__(self, graph: BaseGraph, clipboard_data: 'ClipboardData', 
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
            node.ui.state.posX += offset_x
            node.ui.state.posY += offset_y
            
            # Set graph reference
            node.graph = graph
            
            # Create add node action
            actions.append(AddNodeAction(graph, node, f"Paste node '{node.identity.label}'"))
        
        # Add edge actions
        for connection_uuid, edge in clipboard_data.edges.items():
            actions.append(AddEdgeAction(graph, edge, "Paste connection"))
        
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

