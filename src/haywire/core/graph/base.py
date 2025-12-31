from __future__ import annotations
from typing import Any, TYPE_CHECKING, Optional, List, Tuple
from dataclasses import dataclass
from enum import Enum
import uuid

from haywire.core.types.ports import DataPort

from ..node.node_wrapper import NodeWrapper
from ..data.enums import FlowType


if TYPE_CHECKING:
    from ..node.factory import NodeFactory
    from ..adapter.factory import AdapterFactory
    from .edge_wrapper import EdgeWrapper

# Re-export Edge and FlowType from new location for backward compatibility
from .edge import Edge


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
    
    def __init__(
        self, 
        graph_id: str, 
        name: str,
        node_factory: 'NodeFactory', 
        adapter_factory: 'AdapterFactory'
    ):
        """Initialize a new Haywire graph
        
        Args:
            graph_id: Unique identifier for this graph
            node_factory: Factory for creating node wrappers
            name: Human-readable name for the graph
            adapter_factory: Optional factory for creating adapter chains
        """
        self.graph_id: str = graph_id
        self.name: str = name or f"Graph_{graph_id}"
        self.node_factory = node_factory        
        self.adapter_factory = adapter_factory
        
        # Core containers - NOW USING WRAPPERS
        self.node_wrappers: dict[str, NodeWrapper] = {}
        self.edge_wrappers: dict[str, 'EdgeWrapper'] = {}  # NEW
        self.variables: dict[str, Variable] = {}
        
        # Selection state - shared across all sessions
        self.selected_nodes: set[str] = set()
        self.selected_connections: set[str] = set()
        
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
    
    def create_node_wrapper(
        self,
        registry_key: str,
        position: Tuple[float, float] = (100, 100)
    ) -> Optional[NodeWrapper]:
        """
        Create and adds NodeWrapper (graph-managed factory pattern).
        
        Args:
            registry_key: Node type to create
            position: (x, y) position for the node
            
        Returns:
            NodeWrapper if successful, None if failed
        """
        # Create new wrapper
        wrapper = NodeWrapper(
            registry_key=registry_key,
            node_factory=self.node_factory,
            position=position
        )
        
        # Initialize wrapper (returns self if successful)
        if wrapper.initialize(self):
            # Add to graph's collection
            return self.add_node_wrapper(wrapper)
        else:
            return None

    def add_node_wrapper(self, wrapper: NodeWrapper) -> NodeWrapper:
        """
        Add an initialized wrapper to the graph's collection.
        
        Used by create_node_wrapper() for new wrappers and by undo/redo
        operations to re-add existing wrappers.
        
        Args:
            wrapper: NodeWrapper instance to add (must be initialized)
            
        Returns:
            The added wrapper
            
        Raises:
            ValueError: If node_id already exists in graph
        """
        if wrapper.node_id in self.node_wrappers:
            raise ValueError(
                f"Node wrapper with ID '{wrapper.node_id}' already exists "
                f"in graph"
            )
        
        self.node_wrappers[wrapper.node_id] = wrapper
        return wrapper
    
    def remove_node_wrapper(self, wrapper: NodeWrapper) -> NodeWrapper | None:
        """Remove a node wrapper from the graph        
        Also removes all edges connected to this node.
        
        Args:
            wrapper: The node wrapper to remove
            
        Returns:
            The removed wrapper, or None if not found
        """
        node_id = wrapper.node_id
        
        if node_id not in self.node_wrappers:
            return None
                
        # Remove wrapper (but don't cleanup - undo system handles that)
        wrapper = self.node_wrappers.pop(node_id)
        return wrapper
    
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
    
    def get_node_wrappers_by_type(self, registry_key: str) -> list[NodeWrapper]:
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

    def _get_port(
            self,
            node_id: str,
            port_id: str
        ) -> DataPort:  
        """Convenience method to get a port from a node."""
        return self.node_wrappers[node_id].node.ports[port_id]

    def _get_ports(
            self,
            node_id: str
        ) -> List[DataPort]:  
        """Get all current inlet and outlet ports from a node."""
        ports = []
        for port in self.node_wrappers[node_id].node.ports.values():
            if port.is_inlet() or port.is_outlet(): 
                ports.append(port)  
        
        return ports

    # ========================================================================
    # EdgeWrapper Management
    # ========================================================================
    
    def create_edge_wrapper(
        self,
        output_node_id: str,
        outlet_port_id: str,
        input_node_id: str,
        inlet_port_id: str
    ) -> Optional['EdgeWrapper']:
        """
        Create and adds EdgeWrapper (graph-managed factory pattern).
        
        Args:
            output_node_id: Source node ID
            outlet_pin_id: Source outlet ID
            input_node_id: Target node ID
            inlet_pin_id: Target inlet ID
            
        Returns:
            EdgeWrapper if successful, None if failed
        """
        from .edge_wrapper import EdgeWrapper
        
        flow_type = self.node_wrappers[output_node_id].node.ports[outlet_port_id].flow_type

        # Create new wrapper
        wrapper = EdgeWrapper(
            output_node_id=output_node_id,
            outlet_port_id=outlet_port_id,
            input_node_id=input_node_id,
            inlet_port_id=inlet_port_id,
            edge_type=flow_type,
        )
        
        # Initialize wrapper (returns self if successful)
        if wrapper.initialize(self):
            # Add to graph's collection
            wrapper.rebuild()
            return self.add_edge_wrapper(wrapper)
        else:
            return None
    
    def add_edge_wrapper(self, wrapper: 'EdgeWrapper') -> 'EdgeWrapper':
        """
        Add an initialized wrapper to the graph's collection.
        
        Used by create_edge_wrapper() for new wrappers and by undo/redo
        operations to re-add existing wrappers.
        
        Args:
            wrapper: EdgeWrapper instance to add (must be initialized)
            
        Returns:
            The added wrapper
            
        Raises:
            ValueError: If connection_uuid already exists
        """
        if wrapper.connection_uuid in self.edge_wrappers:
            raise ValueError(
                f"Edge wrapper with UUID '{wrapper.connection_uuid}' "
                f"already exists in graph"
            )

        # Add to collection after updating connections!
        self.edge_wrappers[wrapper.connection_uuid] = wrapper
        wrapper.set_as_registered(True)

        # this needs to be done after registration
        self.update_port_link(wrapper)

        # Need to update states after updating links
        wrapper.refresh_state()
       
        return wrapper

    def remove_edge_wrapper(
        self,
        connection_uuid: str
    ) -> Optional['EdgeWrapper']:
        """
        Remove EdgeWrapper from graph.
       
        Args:
            connection_uuid: Connection UUID to remove
            
        Returns:
            Removed wrapper or None
        """
        if connection_uuid not in self.edge_wrappers:
            return None
                
        wrapper = self.edge_wrappers[connection_uuid]
        del self.edge_wrappers[connection_uuid]
        wrapper.set_as_registered(False)
        
        # needs to be done after deregistration
        self.update_port_link(wrapper)

        # Need to update states after updating links
        wrapper.refresh_state()
 
        return wrapper

    # this method is also called by the edge wrapper when its state changes
    def update_port_link(
            self,
            wrapper: 'EdgeWrapper'
        ):
        """
        Updates the link of an EdgeWrapper to the data ports.
        An edge beeing linked to a port means that the 
        port knows about the edge and the edge is functional.
        This causes an update of all the other connected edges on the ports 
        this edge connects to and might cause other edges to change their 
        linked state if the port connection rules demands it.
        
        Args:
            wrapper: EdgeWrapper to validate

        """
        if (wrapper.is_functional()):
            self._link_edge_to_port(
                wrapper,
                wrapper.input_node_id,
                wrapper.inlet_port_id
            )
            self._link_edge_to_port(
                wrapper,
                wrapper.output_node_id,
                wrapper.outlet_port_id
            ) 
        else:
            self._unlink_edge_from_port(
                wrapper,
                wrapper.input_node_id,
                wrapper.inlet_port_id
            )
            self._unlink_edge_from_port(
                wrapper,
                wrapper.output_node_id,
                wrapper.outlet_port_id
            ) 

        
    def _link_edge_to_port(
            self,
            wrapper: 'EdgeWrapper',
            node_id: str,
            port_id: str
        ) -> DataPort:
        """
        Links an edge to a port. 
        Update port link state.
        Update link of other connected edges and refresh them.
        """
        port = self._get_port(node_id, port_id)
        if port:
            port._add_link(wrapper)
            wrapper.validate_link(port)
            edges_wrps = self._get_edge_wrappers_for_port(
                node_id,
                port_id
            )
            if wrapper in edges_wrps:
                edges_wrps.remove(wrapper)
            for ew in edges_wrps:
                ew.validate_link(port)
                ew.refresh()
        return port

    def _unlink_edge_from_port(
            self,
            wrapper: 'EdgeWrapper',
            node_id: str,
            port_id: str
        ) -> DataPort:
        """
        Unlinks the edge from a port. 
        Updates port link state.
        Update link of other connected edges and refresh them.
        """
        port = self._get_port(node_id, port_id)
        if port:
            port._clear_all_links()
            wrapper.validate_link(port)
            edges_wrps = self._get_edge_wrappers_for_port(
                node_id,
                port_id
            )
            if wrapper in edges_wrps:
                edges_wrps.remove(wrapper)
            for ew in edges_wrps:
                if ew.is_functional():
                    port._add_link(ew)
            for ew in edges_wrps:   
                ew.validate_link(port)
                ew.refresh()
 
        return port

    def get_edge_wrapper(
        self,
        connection_uuid: str
    ) -> Optional['EdgeWrapper']:
        """
        Get EdgeWrapper by connection UUID.
        
        Args:
            connection_uuid: Connection UUID
            
        Returns:
            EdgeWrapper if found, None otherwise
        """
        return self.edge_wrappers.get(connection_uuid)
    
    def list_edge_wrappers(self) -> List['EdgeWrapper']:
        """
        Get all EdgeWrappers.
        
        Returns:
            List of all edge wrappers
        """
        return list(self.edge_wrappers.values())
    
    def _get_edge_wrappers_for_port(
        self,
        node_id: str,
        port_id: str
    ) -> List['EdgeWrapper']:
        """
        Get all EdgeWrappers connected to a specific port.
        
        Args:
            node_id: ID of the node containing the port
            port_id: ID of the inlet or outlet
            
        Returns:
            List of EdgeWrappers connected to the specified port
        """
        connected_wrappers = []
        
        for wrapper in self.edge_wrappers.values():
                if (
                    wrapper.input_node_id == node_id 
                    and wrapper.inlet_port_id == port_id
                ):
                    connected_wrappers.append(wrapper)
                if (
                    wrapper.output_node_id == node_id 
                    and wrapper.outlet_port_id == port_id
                ):
                    connected_wrappers.append(wrapper)
        
        return connected_wrappers

    def _get_edge_wrappers_for_node(
        self,
        node_id: str
    ) -> List['EdgeWrapper']:
        """
        Get all EdgeWrappers connected to a specific node.
        
        Args:
            node_id: ID of the node containing the port

        Returns:
            List of EdgeWrappers connected to the specified node
        """
        connected_wrappers = []
        
        for wrapper in self.edge_wrappers.values():
                # Check if this edge connects to the specified inlet
                if (
                    wrapper.input_node_id == node_id 
                    or wrapper.outlet_port_id == node_id
                ):
                    connected_wrappers.append(wrapper)
        
        return connected_wrappers

    def _get_all_edges(
            self,
            node_id: str
        ) -> List[EdgeWrapper]:  
        """
        Get **all** edges from and to a node.
        These are the linked and unlinked edges connected to the node.
        Args:
            node_id: ID of the node
        Returns:    
            List of valid EdgeWrappers connected to the node
        """
        connected_edges = []
        for edges in self.edge_wrappers.values():
            if edges.input_node_id == node_id or edges.output_node_id == node_id:
                connected_edges.append(edges)
        return connected_edges

    def _get_linked_edges(
            self,
            node_id: str
        ) -> List[EdgeWrapper]:  
        """
        Get all **linked** edges from and to a node.
        These are not necessaray all the edges connected to the node,
        but only the linked ones.
        Args:
            node_id: ID of the node
        Returns:    
            List of linked EdgeWrappers connected to the node
        """
        connected_edges = []
        for port in self._get_ports(node_id):
            for edge_uuid in port._get_linked_edges_uuid():
                connected_edges.append(self.edge_wrappers[edge_uuid])
        return connected_edges
 
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
        for connection_uuid, edge in self.node_wrappers.items():
            if edge.output_node_id not in self.node_wrappers:
                errors.append(
                    f"Edge {connection_uuid} references non-existent "
                    f"output node: {edge.output_node_id}"
                )
            if edge.input_node_id not in self.node_wrappers:
                errors.append(
                    f"Edge {connection_uuid} references non-existent "
                    f"input node: {edge.input_node_id}"
                )
        
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
            for edge in self.node_wrappers.values():
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
            "nodes": {
                node_id: wrapper.serialize() 
                for node_id, wrapper in self.node_wrappers.items()
            },
            "edges": {
                connection_uuid: self.node_wrappers.to_dict() 
                for connection_uuid, edge in self.node_wrappers.items()
            },
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
                    edge = EdgeWrapper(
                        output_node_id=edge_data["output_node_id"],
                        outlet_port_id=edge_data["outlet_port_id"],
                        input_node_id=edge_data["input_node_id"],
                        inlet_port_id=edge_data["inlet_port_id"],
                        edge_type=FlowType(edge_data["edge_type"]),
                    )
                    self.add_edge_wrapper(edge)
            
            return True
            
        except Exception as e:
            print(f"❌ Error loading graph from dictionary: {e}")
            return False
    
    def __str__(self) -> str:
        """String representation of the graph"""
        return (f"HaywireGraph(id='{self.graph_id}', name='{self.name}', "
                f"nodes={len(self.node_wrappers)}, edges={len(self.edge_wrappers)}, "
                f"variables={len(self.variables)})")
    
    def __repr__(self) -> str:
        """Detailed string representation"""
        return self.__str__()
