from __future__ import annotations
from typing import Any
from dataclasses import dataclass
from enum import Enum

from ..node.node import BaseNode
from ...ui.utils import generate_connection_uuid, parse_connection_uuid


# ============================================================================
# Edge Types and Data Structures
# ============================================================================

class EdgeType(Enum):
    """Types of edges in a Haywire graph"""
    CONTROL = "control"
    DATA = "data"
    CALLBACK = "callback"


@dataclass
class Edge:
    """Represents a connection between two nodes in a graph
    
    Based on the Haywire design specification, an Edge contains:
    - output-node's node-id, outlet-pin-id, outlet-pin-data-type
    - input-node's node-id, inlet-pin-id, inlet-pin-data-type
    """
    edge_type: EdgeType
    
    # Output node information
    output_node_id: str
    outlet_pin_id: str # also known as the id of an outlet
    
    # Input node information
    input_node_id: str
    inlet_pin_id: str # also known as the id of an inlet
    
    # Optional fields with defaults
    outlet_pin_data_type: str | None = None
    inlet_pin_data_type: str | None = None

    is_valid: bool = True
    
    def to_dict(self) -> dict[str, Any]:
        """Serialize edge to dictionary"""
        return {
            "edge_type": self.edge_type.value,
            "output_node_id": self.output_node_id,
            "outlet_pin_id": self.outlet_pin_id,
            "outlet_pin_data_type": self.outlet_pin_data_type,
            "input_node_id": self.input_node_id,
            "inlet_pin_id": self.inlet_pin_id,
            "inlet_pin_data_type": self.inlet_pin_data_type,
            "is_valid": self.is_valid
        }


@dataclass
class Variable:
    """Graph variable for maintaining state between execution runs
    
    Variables are exclusive to Graphs and allow statefulness during execution.
    They can be accessed by Control-nodes' worker functions.
    """
    name: str
    data_type: str
    default_value: Any = None
    current_value: Any = None
    description: str | None = None
    
    def __post_init__(self):
        """Initialize current_value with default_value if not set"""
        if self.current_value is None:
            self.current_value = self.default_value
    
    def reset_to_default(self):
        """Reset variable to its default value"""
        self.current_value = self.default_value
    
    def to_dict(self) -> dict[str, Any]:
        """Serialize variable to dictionary"""
        return {
            "name": self.name,
            "data_type": self.data_type,
            "default_value": self.default_value,
            "current_value": self.current_value,
            "description": self.description
        }


# ============================================================================
# Graph Class
# ============================================================================

class HaywireGraph:
    """Main Graph class for the Haywire system
    
    A Graph is a container that describes the flow of data and control between nodes.
    It contains:
    - Variables: for statefulness during execution runs
    - Nodes: instantiations of HaywireNode subclasses
    - Edges: connections between nodes (control, data, callback)
    
    Key properties:
    - A Graph can contain multiple disconnected node-trees (assembled into Flows)
    - A Graph cannot be executed directly (only Flows can be executed)
    - A Graph can be treated as a node (Graph-node) within another graph
    """
    
    def __init__(self, graph_id: str, name: str = ""):
        """Initialize a new Haywire graph
        
        Args:
            graph_id: Unique identifier for this graph
            name: Human-readable name for the graph
        """
        self.graph_id: str = graph_id
        self.name: str = name or f"Graph_{graph_id}"
        
        # Core containers
        self.nodes: dict[str, BaseNode] = {}
        self.edges: dict[str, Edge] = {}
        self.variables: dict[str, Variable] = {}
        
        # Selection state - shared across all sessions
        self.selected_nodes: set[str] = set()
        self.selected_connections: set[str] = set()  # Using connection uuids (edge keys)
        
        # Metadata
        self.description: str = ""
        self.version: str = "1.0.0"
        self.author: str = ""
        self.created_at: str | None = None
        self.modified_at: str | None = None
    
    # ========================================================================
    # Node Management
    # ========================================================================
    
    def add_node(self, node: BaseNode) -> BaseNode:
        """Add a node to the graph
        
        Args:
            node: HaywireNode instance to add
            
        Returns:
            The added node
            
        Raises:
            ValueError: If node_id already exists in graph
        """
        if node.node_id in self.nodes:
            raise ValueError(f"Node with ID '{node.node_id}' already exists in graph")
        
        self.nodes[node.node_id] = node
        return node
    
    def remove_node(self, node_id: str) -> BaseNode | None:
        """Remove a node from the graph
        
        Also removes all edges connected to this node.
        
        Args:
            node_id: ID of the node to remove
            
        Returns:
            The removed node, or None if not found
        """
        if node_id not in self.nodes:
            return None
        
        # Remove all edges connected to this node
        edges_to_remove = [
            connection_uuid for connection_uuid, edge in self.edges.items()
            if edge.input_node_id == node_id or edge.output_node_id == node_id
        ]
        for connection_uuid in edges_to_remove:
            self.edges.pop(connection_uuid)
        
        return self.nodes.pop(node_id)
    
    def get_node(self, node_id: str) -> BaseNode | None:
        """Get a node by its ID
        
        Args:
            node_id: ID of the node to retrieve
            
        Returns:
            The node if found, None otherwise
        """
        return self.nodes.get(node_id)
    
    def move_node(self, node_id: str, new_x: float, new_y: float) -> bool:
        """Move a node to a new position
        
        Args:
            node_id: ID of the node to move
            new_x: New X position
            new_y: New Y position
            
        Returns:
            True if node was moved, False if not found
        """
        node = self.nodes.get(node_id)
        if node is None:
            return False
        
        node.ui_state.posX = new_x
        node.ui_state.posY = new_y
        return True
    
    def get_nodes_by_type(self, registry_key: str) -> list[BaseNode]:
        """Get all nodes of a specific type
        
        Args:
            node_type: The node type to filter by
            
        Returns:
            List of nodes matching the type
        """
        return [
            node for node in self.nodes.values() 
            if hasattr(node, 'registry_key') and node.registry_key == registry_key
        ]

    def replace_nodes_of_type(self, registry_key: str, new_node: BaseNode):
        """Replace all nodes of a specific type with a new node
        
        Args:
            registry_key: The node type to replace
            new_node: The new node instance to use
            
        """   
        
                 
        pass


    # ========================================================================
    # Edge Management
    # ========================================================================
    
    def add_edge(self, output_node_id: str, outlet_pin_id: str, input_node_id: str, inlet_pin_id: str) -> str:
        """Add edge by node and pin identifiers and return its connection uuid
        
        Args:
            output_node_id: ID of the output node
            outlet_pin_id: ID of the outlet pin
            input_node_id: ID of the input node
            inlet_pin_id: ID of the inlet pin
            
        Returns:
            The connection uuid (UUID)
            
        Raises:
            ValueError: If referenced nodes don't exist or connection already exists
        """
        # Generate connection UUID from components
        connection_uuid = generate_connection_uuid(
            output_node_id, outlet_pin_id, input_node_id, inlet_pin_id
        )
        
        # Prevent duplicates
        if connection_uuid in self.edges:
            raise ValueError(f"Connection already exists: {connection_uuid}")
        
        # Validate that referenced nodes exist
        if output_node_id not in self.nodes:
            raise ValueError(f"Output node '{output_node_id}' not found in graph")
        if input_node_id not in self.nodes:
            raise ValueError(f"Input node '{input_node_id}' not found in graph")
        
        # Evaluate edge type from the node and outlet that is referenced
        edge_type = self._determine_edge_type(output_node_id, outlet_pin_id)
        
        # TODO: Validate that connection is valid (pin types match or adapter exists)
        
        # Create Edge instance
        edge = Edge(
            edge_type=edge_type,
            output_node_id=output_node_id,
            outlet_pin_id=outlet_pin_id,
            input_node_id=input_node_id,
            inlet_pin_id=inlet_pin_id
        )
        
        self.edges[connection_uuid] = edge
        return connection_uuid
    
    def remove_edge(self, output_node_id: str, outlet_pin_id: str, 
                   input_node_id: str, inlet_pin_id: str) -> bool:
        """Remove an edge from the graph (backward compatibility)
        
        Args:
            output_node_id: ID of the output node
            outlet_pin_id: ID of the outlet pin
            input_node_id: ID of the input node
            inlet_pin_id: ID of the inlet pin
            
        Returns:
            True if edge was found and removed, False otherwise
        """
        # Generate connection UUID from components
        connection_uuid = generate_connection_uuid(
            output_node_id, outlet_pin_id, input_node_id, inlet_pin_id
        )
        
        return self.remove_edge_by_uuid(connection_uuid) is not None
    
    def remove_edge_by_uuid(self, connection_uuid: str) -> Edge | None:
        """Remove edge by connection uuid
        
        Args:
            connection_uuid: Connection UUID to remove
            
        Returns:
            The removed edge, or None if not found
        """
        return self.edges.pop(connection_uuid, None)
    
    def get_edge(self, connection_uuid: str) -> Edge | None:
        """Get edge by connection uuid
        
        Args:
            connection_uuid: Connection UUID to retrieve
            
        Returns:
            The edge if found, None otherwise
        """
        return self.edges.get(connection_uuid)
    
    def list_edges(self) -> list[Edge]:
        """Get all edges as list
        
        Returns:
            List of all edges in the graph
        """
        return list(self.edges.values())
    
    def get_edges_from_node(self, node_id: str) -> list[Edge]:
        """Get all edges originating from a node
        
        Args:
            node_id: ID of the output node
            
        Returns:
            List of edges from the node
        """
        return [edge for edge in self.edges.values() if edge.output_node_id == node_id]
    
    def get_edges_to_node(self, node_id: str) -> list[Edge]:
        """Get all edges going to a node
        
        Args:
            node_id: ID of the input node
            
        Returns:
            List of edges to the node
        """
        return [edge for edge in self.edges.values() if edge.input_node_id == node_id]

    def _determine_edge_type(self, output_node_id: str, outlet_pin_id: str) -> EdgeType:
        """Determine the edge type based on the output node's outlet flow type
        
        Args:
            output_node_id: ID of the output node
            outlet_pin_id: ID of the outlet pin
            
        Returns:
            EdgeType based on the outlet's flow type
        """
        output_node = self.nodes.get(output_node_id)
        if not output_node:
            raise ValueError(f"Determining edge type: node '{output_node_id}' not found in graph")
        
        # Check if the outlet exists on the node
        if hasattr(output_node, 'outlets') and outlet_pin_id in output_node.outlets:
            outlet = output_node.outlets[outlet_pin_id]
            flow_type = outlet.flow_type
            
            # Map FlowType to EdgeType
            if flow_type == 'control':
                return EdgeType.CONTROL
            elif flow_type == 'data':
                return EdgeType.DATA
            elif flow_type == 'callback':
                return EdgeType.CALLBACK
            else:
                # For 'none' or any unknown type, default to DATA
                return EdgeType.DATA
        
        raise ValueError(f"Determining edge type: inside node '{output_node_id}' no outlet id:'{outlet_pin_id}' found in graph")
    


    # ========================================================================
    # Variable Management
    # ========================================================================
    
    def add_variable(self, variable: Variable) -> Variable:
        """Add a variable to the graph
        
        Args:
            variable: Variable instance to add
            
        Returns:
            The added variable
            
        Raises:
            ValueError: If variable name already exists
        """
        if variable.name in self.variables:
            raise ValueError(f"Variable '{variable.name}' already exists in graph")
        
        self.variables[variable.name] = variable
        return variable
    
    def remove_variable(self, name: str) -> Variable | None:
        """Remove a variable from the graph
        
        Args:
            name: Name of the variable to remove
            
        Returns:
            The removed variable, or None if not found
        """
        return self.variables.pop(name, None)
    
    def get_variable(self, name: str) -> Variable | None:
        """Get a variable by name
        
        Args:
            name: Name of the variable
            
        Returns:
            The variable if found, None otherwise
        """
        return self.variables.get(name)
    
    def set_variable_value(self, name: str, value: Any) -> bool:
        """Set the current value of a variable
        
        Args:
            name: Name of the variable
            value: New value to set
            
        Returns:
            True if variable was found and updated, False otherwise
        """
        if name in self.variables:
            self.variables[name].current_value = value
            return True
        return False
    
    def get_variable_value(self, name: str) -> Any:
        """Get the current value of a variable
        
        Args:
            name: Name of the variable
            
        Returns:
            Current value of the variable, or None if not found
        """
        variable = self.variables.get(name)
        return variable.current_value if variable else None
    
    def reset_all_variables(self):
        """Reset all variables to their default values"""
        for variable in self.variables.values():
            variable.reset_to_default()
    
    # ========================================================================
    # Utility Methods
    # ========================================================================
    
    def validate(self) -> list[str]:
        """Validate the graph structure
        
        Returns:
            List of validation errors (empty if valid)
        """
        errors = []
        
        # Check for orphaned edges (edges referencing non-existent nodes)
        for connection_uuid, edge in self.edges.items():
            if edge.output_node_id not in self.nodes:
                errors.append(f"Edge {connection_uuid} references non-existent output node: {edge.output_node_id}")
            if edge.input_node_id not in self.nodes:
                errors.append(f"Edge {connection_uuid} references non-existent input node: {edge.input_node_id}")
        
        return errors
    
    def get_disconnected_components(self) -> list[list[str]]:
        """Find disconnected components in the graph
        
        Returns:
            List of components, where each component is a list of node IDs
        """
        visited = set()
        components = []
        
        def dfs(node_id: str, component: list[str]):
            if node_id in visited:
                return
            visited.add(node_id)
            component.append(node_id)
            
            # Follow all edges from this node
            for edge in self.edges.values():
                if edge.output_node_id == node_id:
                    dfs(edge.input_node_id, component)
                elif edge.input_node_id == node_id:
                    dfs(edge.output_node_id, component)
        
        for node_id in self.nodes.keys():
            if node_id not in visited:
                component = []
                dfs(node_id, component)
                components.append(component)
        
        return components

    # ========================================================================
    # Selection Management
    # ========================================================================
    
    def set_selection(self, selected_nodes: set[str] = None, 
                     selected_connections: set[str] = None):
        """Set selection using consistent ID formats
        
        Args:
            selected_nodes: Set of node IDs to select (None keeps current)
            selected_connections: Set of connection UUIDs to select (None keeps current)
        """
        if selected_nodes is not None:
            self.selected_nodes = selected_nodes.copy()
        if selected_connections is not None:
            self.selected_connections = selected_connections.copy()
    
    def set_selection_state(self, selected_nodes: set[str], selected_connections: set[str]):
        """Set the complete selection state (backward compatibility)."""
        self.selected_nodes = selected_nodes.copy()
        self.selected_connections = selected_connections.copy()
    
    def get_selection_state(self) -> tuple[set[str], set[str]]:
        """Get the current selection state."""
        return self.selected_nodes.copy(), self.selected_connections.copy()
    
    def select_node(self, node_id: str, multi_select: bool = False):
        """Select a node."""
        if not multi_select:
            self.selected_nodes.clear()
            self.selected_connections.clear()
        
        if node_id in self.nodes:
            self.selected_nodes.add(node_id)
    
    def deselect_node(self, node_id: str):
        """Deselect a node."""
        self.selected_nodes.discard(node_id)
    
    def select_connection(self, connection_uuid: str, multi_select: bool = False):
        """Select a connection."""
        if not multi_select:
            self.selected_nodes.clear()
            self.selected_connections.clear()
        
        self.selected_connections.add(connection_uuid)
    
    def deselect_connection(self, connection_uuid: str):
        """Deselect a connection."""
        self.selected_connections.discard(connection_uuid)
    
    def clear_selection(self):
        """Clear all selections."""
        self.selected_nodes.clear()
        self.selected_connections.clear()
    
    def is_node_selected(self, node_id: str) -> bool:
        """Check if a node is selected."""
        return node_id in self.selected_nodes
    
    def is_connection_selected(self, connection_uuid: str) -> bool:
        """Check if a connection is selected."""
        return connection_uuid in self.selected_connections

    # ========================================================================
    # Cleanup
    # ========================================================================

    def clear(self):
        """Clear all nodes, edges, and variables from the graph"""
        self.nodes.clear()
        self.edges.clear()
        self.variables.clear()
        self.selected_nodes.clear()
        self.selected_connections.clear()
    
    # ========================================================================
    # Serialization
    # ========================================================================
    
    def to_dict(self) -> dict[str, Any]:
        """Serialize graph to dictionary
        
        Returns:
            Dictionary representation of the graph
        """
        return {
            "graph_id": self.graph_id,
            "name": self.name,
            "description": self.description,
            "version": self.version,
            "author": self.author,
            "created_at": self.created_at,
            "modified_at": self.modified_at,
            "nodes": {node_id: node.to_dict() for node_id, node in self.nodes.items()},
            "edges": {connection_uuid: edge.to_dict() for connection_uuid, edge in self.edges.items()},
            "variables": {name: var.to_dict() for name, var in self.variables.items()}
        }
    
    def __str__(self) -> str:
        """String representation of the graph"""
        return (f"HaywireGraph(id='{self.graph_id}', name='{self.name}', "
                f"nodes={len(self.nodes)}, edges={len(self.edges)}, "
                f"variables={len(self.variables)})")
    
    def __repr__(self) -> str:
        """Detailed string representation"""
        return self.__str__()
