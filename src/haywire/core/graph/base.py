from __future__ import annotations
from typing import Any, TYPE_CHECKING
from dataclasses import dataclass
from enum import Enum
import uuid

from ..node.base import BaseNode
from ..node.node_wrapper import NodeWrapper
from ...ui.utils import generate_connection_uuid, parse_connection_uuid

if TYPE_CHECKING:
    from ..node.factory import NodeFactory


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

class BaseGraph:
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
    
    def __init__(self, graph_id: str, node_factory: 'NodeFactory', name: str = ""):
        """Initialize a new Haywire graph
        
        Args:
            graph_id: Unique identifier for this graph
            node_factory: Factory for creating node wrappers
            name: Human-readable name for the graph
        """
        self.graph_id: str = graph_id
        self.name: str = name or f"Graph_{graph_id}"
        self.node_factory = node_factory
        
        # Core containers - NOW USING WRAPPERS
        self.node_wrappers: dict[str, NodeWrapper] = {}
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
    # Node Management (NodeWrapper-based)
    # ========================================================================
    
    def generate_unique_node_id(self) -> str:
        """Generate a unique node ID that doesn't conflict with existing nodes.
        
        Returns:
            A unique node ID string
        """
        while True:
            node_id = f"node_{uuid.uuid4().hex[:8]}"
            if node_id not in self.node_wrappers:
                return node_id
    

    def add_node_wrapper(self, wrapper: NodeWrapper) -> NodeWrapper:
        """Add an already created node wrapper to the graph
        
        Args:
            wrapper: NodeWrapper instance to add
            
        Returns:
            The added wrapper
            
        Raises:
            ValueError: If node_id already exists in graph
        """
        if wrapper.node_id in self.node_wrappers:
            raise ValueError(f"Node wrapper with ID '{wrapper.node_id}' already exists in graph")
        
        self.node_wrappers[wrapper.node_id] = wrapper
        
        # Set graph reference on the actual node instance
        if wrapper._node_instance:
            wrapper.node.wrapper = self
        
        return wrapper
    
    def remove_node_wrapper(self, wrapper: NodeWrapper) -> NodeWrapper | None:
        """Remove a node wrapper from the graph
        
        Also removes all edges connected to this node and cleans up the wrapper.
        
        Args:
            node_id: ID of the node to remove
            
        Returns:
            The removed wrapper, or None if not found
        """
        node_id = wrapper.node_id
        
        if node_id not in self.node_wrappers:
            return None
        
        # Remove all edges connected to this node
        edges_to_remove = [
            connection_uuid for connection_uuid, edge in self.edges.items()
            if edge.input_node_id == node_id or edge.output_node_id == node_id
        ]
        for connection_uuid in edges_to_remove:
            self.edges.pop(connection_uuid)
        
        # Remove and cleanup wrapper
        wrapper = self.node_wrappers.pop(node_id)
        wrapper.cleanup()
        return wrapper
    
    def get_node(self, node_id: str) -> BaseNode | None:
        """Get a node instance by its ID (for backward compatibility)
        
        Args:
            node_id: ID of the node to retrieve
            
        Returns:
            The node instance if found, None otherwise
        """
        wrapper = self.node_wrappers.get(node_id)
        return wrapper.node if wrapper else None
    
    def get_node_wrapper(self, node_id: str) -> NodeWrapper | None:
        """Get a node wrapper by its ID
        
        Args:
            node_id: ID of the node wrapper to retrieve
            
        Returns:
            The wrapper if found, None otherwise
        """
        return self.node_wrappers.get(node_id)
    
    def move_node(self, node_id: str, new_x: float, new_y: float) -> bool:
        """Move a node to a new position
        
        Args:
            node_id: ID of the node to move
            new_x: New X position
            new_y: New Y position
            
        Returns:
            True if node was moved, False if not found
        """
        wrapper = self.node_wrappers.get(node_id)
        if wrapper is None:
            return False
        
        wrapper.node.ui_state.posX = new_x
        wrapper.node.ui_state.posY = new_y
        return True
    
    def get_nodes_by_type(self, registry_key: str) -> list[BaseNode]:
        """Get all node instances of a specific type (for backward compatibility)
        
        Args:
            registry_key: The node type to filter by
            
        Returns:
            List of node instances matching the type
        """
        return [
            wrapper.node for wrapper in self.node_wrappers.values() 
            if wrapper.registry_key == registry_key
        ]
    
    def get_wrappers_by_type(self, registry_key: str) -> list[NodeWrapper]:
        """Get all node wrappers of a specific type
        
        Args:
            registry_key: The node type to filter by
            
        Returns:
            List of wrappers matching the type
        """
        return [
            wrapper for wrapper in self.node_wrappers.values() 
            if wrapper.registry_key == registry_key
        ]
    
    def list_all_wrappers(self) -> list[NodeWrapper]:
        """Get all node wrappers in the graph
        
        Returns:
            List of all node wrappers
        """
        return list(self.node_wrappers.values())


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
        
        # Validate that referenced node wrappers exist
        if output_node_id not in self.node_wrappers:
            raise ValueError(f"Output node '{output_node_id}' not found in graph")
        if input_node_id not in self.node_wrappers:
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
        wrapper = self.node_wrappers.get(output_node_id)
        if not wrapper:
            raise ValueError(f"Determining edge type: node '{output_node_id}' not found in graph")
        
        output_node = wrapper.node
        
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
            if edge.output_node_id not in self.node_wrappers:
                errors.append(f"Edge {connection_uuid} references non-existent output node: {edge.output_node_id}")
            if edge.input_node_id not in self.node_wrappers:
                errors.append(f"Edge {connection_uuid} references non-existent input node: {edge.input_node_id}")
        
        # Check wrapper validation
        for wrapper in self.node_wrappers.values():
            wrapper_errors = wrapper.validate()
            for error in wrapper_errors:
                errors.append(f"Node {wrapper.node_id}: {error}")
        
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
        
        for node_id in self.node_wrappers.keys():
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
        
        if node_id in self.node_wrappers:
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
        # Cleanup all wrappers before clearing
        for wrapper in self.node_wrappers.values():
            wrapper.cleanup()
        
        self.node_wrappers.clear()
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
            "nodes": {node_id: wrapper.serialize() for node_id, wrapper in self.node_wrappers.items()},
            "edges": {connection_uuid: edge.to_dict() for connection_uuid, edge in self.edges.items()},
            "variables": {name: var.to_dict() for name, var in self.variables.items()}
        }
    
    def load_from_dict(self, data: dict[str, Any]) -> bool:
        """Deserialize graph from dictionary
        
        Args:
            data: Dictionary representation of the graph
            
        Returns:
            True if successful, False if there were errors
        """
        try:
            # Load metadata
            self.graph_id = data.get("graph_id", self.graph_id)
            self.name = data.get("name", self.name)
            self.description = data.get("description", "")
            self.version = data.get("version", "1.0.0")
            self.author = data.get("author", "")
            self.created_at = data.get("created_at")
            self.modified_at = data.get("modified_at")
            
            # Clear existing data
            self.clear()
            
            # Load variables first
            if "variables" in data:
                for name, var_data in data["variables"].items():
                    var = Variable(
                        name=var_data["name"],
                        data_type=var_data["data_type"],
                        default_value=var_data.get("default_value"),
                        current_value=var_data.get("current_value"),
                        description=var_data.get("description")
                    )
                    self.variables[name] = var
            
            # Load node wrappers
            if "nodes" in data:
                for node_id, node_data in data["nodes"].items():
                    # Create wrapper
                    wrapper = NodeWrapper(
                        node_id=node_id,
                        registry_key=node_data["registry_key"],
                        node_factory=self.node_factory,
                        position=node_data.get("position")
                    )
                    
                    # Deserialize wrapper data
                    if wrapper.deserialize(node_data):
                        self.node_wrappers[node_id] = wrapper
                        # Set graph reference
                        if wrapper._node_instance:
                            wrapper.node.wrapper = self
                    else:
                        print(f"⚠️ Warning: Failed to deserialize node {node_id}")
            
            # Load edges
            if "edges" in data:
                for connection_uuid, edge_data in data["edges"].items():
                    edge = Edge(
                        edge_type=EdgeType(edge_data["edge_type"]),
                        output_node_id=edge_data["output_node_id"],
                        outlet_pin_id=edge_data["outlet_pin_id"],
                        input_node_id=edge_data["input_node_id"],
                        inlet_pin_id=edge_data["inlet_pin_id"],
                        outlet_pin_data_type=edge_data.get("outlet_pin_data_type"),
                        inlet_pin_data_type=edge_data.get("inlet_pin_data_type"),
                        is_valid=edge_data.get("is_valid", True)
                    )
                    self.edges[connection_uuid] = edge
            
            return True
            
        except Exception as e:
            print(f"❌ Error loading graph from dictionary: {e}")
            return False
    
    def __str__(self) -> str:
        """String representation of the graph"""
        return (f"HaywireGraph(id='{self.graph_id}', name='{self.name}', "
                f"nodes={len(self.node_wrappers)}, edges={len(self.edges)}, "
                f"variables={len(self.variables)})")
    
    def __repr__(self) -> str:
        """Detailed string representation"""
        return self.__str__()
