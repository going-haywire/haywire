# haywire/core/graph/base.py
"""
BaseGraph - Main graph container and coordinator.

Manages collections of nodes, edges, and variables, and coordinates
with internal managers for validation, etc.
"""
from __future__ import annotations
from typing import Any, Dict, List, Optional, Set, Tuple, TYPE_CHECKING
from dataclasses import dataclass
import uuid
import logging

from ..data.enums import FlowType
from ..types.ports import DataPort
from .validation import ValidationManager, ValidationCallback
from .types import ChangeReason, ValidationResult

if TYPE_CHECKING:
    from ..node.factory import NodeFactory
    from ..adapter.factory import AdapterFactory
    from ..edge.edge_wrapper import EdgeWrapper
    from ..node.node_wrapper import NodeWrapper

# Re-export for backward compatibility
from ..edge.edge import Edge

logger = logging.getLogger(__name__)


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
    
    def to_dict(self) -> Dict[str, Any]:
        """Serialize variable to dictionary"""
        return {
            "name": self.name,
            "data_type": self.data_type,
            "default_value": self.default_value,
            "current_value": self.current_value,
            "description": self.description
        }


class BaseGraph:
    """
    Main Graph class for the Haywire system.
    
    A Graph is a container that describes the flow of data and control between nodes.
    It contains:
    - Variables: for statefulness during execution runs
    - Nodes: instantiations of HaywireNode subclasses (managed via NodeWrappers)
    - Edges: connections between nodes (managed via EdgeWrappers)
    
    The graph coordinates with internal managers for validation and other concerns.
    External code should use the graph's public API, not interact with managers directly.
    """
    
    def __init__(
        self, 
        graph_id: str, 
        name: str,
        node_factory: 'NodeFactory', 
        adapter_factory: 'AdapterFactory',
        validation_delay_ms: float = 50.0
    ):
        """
        Initialize a new Haywire graph.
        
        Args:
            graph_id: Unique identifier for this graph
            name: Human-readable name for the graph
            node_factory: Factory for creating node wrappers
            adapter_factory: Factory for creating adapter chains
            validation_delay_ms: Debounce delay for validation (default 50ms)
        """
        self.graph_id: str = graph_id
        self.name: str = name or f"Graph_{graph_id}"
        self.node_factory = node_factory        
        self.adapter_factory = adapter_factory
        
        # Core containers
        self.node_wrappers: Dict[str, 'NodeWrapper'] = {}
        self.edge_wrappers: Dict[str, 'EdgeWrapper'] = {}
        self.variables: Dict[str, Variable] = {}
        
        # Selection state - shared across all sessions
        self.selected_nodes: Set[str] = set()
        self.selected_connections: Set[str] = set()
        
        # Metadata
        self.description: str = ""
        self.version: str = "1.0.0"
        self.author: str = ""
        self.created_at: str | None = None
        self.modified_at: str | None = None
        
        # Internal managers (private - implementation details)
        self._validation = ValidationManager(
            graph=self,
            debounce_ms=validation_delay_ms
        )
    
    # =========================================================================
    # VALIDATION API (delegates to internal manager)
    # =========================================================================
    
    def subscribe_to_validation(self, callback: ValidationCallback) -> None:
        """
        Subscribe to validation completion events.
        
        The callback will be invoked after each validation batch completes,
        receiving a ValidationResult with categorized changes.
        
        Args:
            callback: Callable that accepts ValidationResult
            
        Example:
            def on_validated(result: ValidationResult):
                print(f"Nodes added: {result.nodes_added}")
                print(f"Edges changed: {result.edges_changed}")
            
            graph.subscribe_to_validation(on_validated)
        """
        self._validation.subscribe(callback)
    
    def unsubscribe_from_validation(self, callback: ValidationCallback) -> None:
        """
        Unsubscribe from validation events.
        
        Args:
            callback: The callback to remove
        """
        self._validation.unsubscribe(callback)
    
    def get_validation_stats(self) -> Dict[str, Any]:
        """
        Get validation pipeline statistics.
        
        Returns:
            Dictionary with validation metrics
        """
        return self._validation.get_statistics()
    
    # =========================================================================
    # NODE MANAGEMENT
    # =========================================================================
    
    def generate_unique_node_id(self, prefix: str = "node") -> str:
        """
        Generate a unique node ID that doesn't conflict with existing nodes.
        
        Args:
            prefix: Prefix for the node ID
        Returns:
            A unique node ID string
        """
        while True:
            node_id = f"{prefix}_{uuid.uuid4().hex[:8]}"
            if node_id not in self.node_wrappers:
                return node_id
    
    def create_node_wrapper(
        self,
        registry_key: str,
        position: Tuple[float, float] = (100, 100)
    ) -> Optional['NodeWrapper']:
        """
        Create and add NodeWrapper (graph-managed factory pattern).
        
        This creates a new node, initializes it, and adds it to the graph.
        Automatically triggers validation pipeline.
        
        Args:
            registry_key: Node type to create
            position: (x, y) position for the node
            
        Returns:
            NodeWrapper if successful, None if failed
        """
        from ..node.node_wrapper import NodeWrapper
        
        # Create new wrapper
        wrapper = NodeWrapper(
            registry_key=registry_key,
            node_factory=self.node_factory,
            position=position
        )
        
        # Initialize wrapper (returns self if successful)
        if wrapper.instantiate(self):
            wrapper.build()
            # Add to graph's collection (triggers validation)
            return self.add_node_wrapper(wrapper)
        else:
            return None

    def add_node_wrapper(self, wrapper: 'NodeWrapper') -> 'NodeWrapper':
        """
        Add an initialized wrapper to the graph's collection.
        
        Used by create_node_wrapper() for new wrappers and by undo/redo
        operations to re-add existing wrappers.
        
        Automatically triggers validation pipeline with NODE_ADDED reason.
        
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
        
        # Add to collection
        self.node_wrappers[wrapper.node_id] = wrapper
        
        # Trigger validation (delegates to manager)
        self._validation.mark_node_dirty(
            wrapper.node_id, 
            ChangeReason.NODE_ADDED
        )
        
        logger.debug(f"Added node wrapper: {wrapper.node_id}")
        
        return wrapper
    
    def remove_node_wrapper(self, wrapper: 'NodeWrapper') -> 'NodeWrapper' | None:
        """
        Remove a node wrapper from the graph.
        
        Also removes all edges connected to this node and triggers validation.
        
        Args:
            wrapper: The node wrapper to remove
            
        Returns:
            The removed wrapper, or None if not found
        """
        node_id = wrapper.node_id
        
        if node_id not in self.node_wrappers:
            return None
        
        # Get all connected edges (they'll need to be removed too)
        connected_edges = self._get_all_edges(node_id)
        
        # Remove wrapper from collection
        wrapper = self.node_wrappers.pop(node_id)
        
        # Trigger validation for removal
        self._validation.mark_node_dirty(
            node_id, 
            ChangeReason.NODE_REMOVED
        )
        
        # Remove all connected edges
        for edge_wrapper in connected_edges:
            self.remove_edge_wrapper(edge_wrapper.connection_uuid)
        
        logger.debug(
            f"Removed node wrapper: {node_id} "
            f"(removed {len(connected_edges)} connected edges)"
        )
        
        return wrapper
    
    def get_node_wrapper(self, node_id: str) -> 'NodeWrapper' | None:
        """
        Get a node wrapper by its ID.
        
        Args:
            node_id: ID of the node wrapper to retrieve
            
        Returns:
            The wrapper if found, None otherwise
        """
        return self.node_wrappers.get(node_id)
    
    def move_node(self, node_id: str, new_x: float, new_y: float) -> bool:
        """
        Move a node to a new position.
        
        Note: Position changes typically don't require validation unless
        position affects node behavior. Currently does NOT trigger validation.
        
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
        
        wrapper.move(new_x, new_y)
        
        # Trigger validation with MOVED reason
        self._validation.mark_node_dirty(
            node_id, 
            ChangeReason.NODE_MOVED
        )

        return True
    
    def get_node_wrappers_by_type(self, registry_key: str) -> List['NodeWrapper']:
        """
        Get all node wrappers of a specific type.
        
        Args:
            registry_key: The node type to filter by
            
        Returns:
            List of wrappers matching the type
        """
        return [
            wrapper for wrapper in self.node_wrappers.values() 
            if wrapper.registry_key == registry_key
        ]
    
    def list_all_wrappers(self) -> List['NodeWrapper']:
        """
        Get all node wrappers in the graph.
        
        Returns:
            List of all node wrappers
        """
        return list(self.node_wrappers.values())

    def _get_port(self, node_id: str, port_id: str) -> DataPort:  
        """Convenience method to get a port from a node."""
        return self.node_wrappers[node_id].node.ports[port_id]

    def _get_ports(self, node_id: str) -> List[DataPort]:  
        """Get all current inlet and outlet ports from a node."""
        ports = []
        for port in self.node_wrappers[node_id].node.ports.values():
            if port.is_inlet() or port.is_outlet(): 
                ports.append(port)  
        
        return ports

    # =========================================================================
    # EDGE MANAGEMENT
    # =========================================================================
    
    def create_edge_wrapper(
        self,
        output_node_id: str,
        outlet_port_id: str,
        input_node_id: str,
        inlet_port_id: str
    ) -> Optional['EdgeWrapper']:
        """
        Create and add EdgeWrapper (graph-managed factory pattern).
        
        This creates a new edge, builds its adapter chain, and adds it to the graph.
        Automatically triggers validation pipeline.
        
        Args:
            output_node_id: Source node ID
            outlet_port_id: Source outlet ID
            input_node_id: Target node ID
            inlet_port_id: Target inlet ID
            
        Returns:
            EdgeWrapper if successful, None if failed
        """
        from ..edge.edge_wrapper import EdgeWrapper
        
        flow_type = self.node_wrappers[output_node_id].node.ports[outlet_port_id].flow_type

        # Create new wrapper
        edge_wrapper = EdgeWrapper(
            output_node_id=output_node_id,
            outlet_port_id=outlet_port_id,
            input_node_id=input_node_id,
            inlet_port_id=inlet_port_id,
            edge_type=flow_type,
        )
        
        # Initialize wrapper (returns self if successful)
        if edge_wrapper.instantiate(self):
            # Build adapter chain
            edge_wrapper.build()
            # Add to graph's collection (triggers validation automatically)
            return self.add_edge_wrapper(edge_wrapper)
        else:
            return None
    
    def add_edge_wrapper(self, edge_wrapper: 'EdgeWrapper') -> 'EdgeWrapper':
        """
        Add an initialized wrapper to the graph's collection.
        
        Used by create_edge_wrapper() for new wrappers and by undo/redo
        operations to re-add existing wrappers.
        
        Automatically triggers validation pipeline with EDGE_ADDED reason
        and updates port links.
        
        Args:
            wrapper: EdgeWrapper instance to add (must be initialized)
            
        Returns:
            The added wrapper
            
        Raises:
            ValueError: If connection_uuid already exists
        """
        if edge_wrapper.connection_uuid in self.edge_wrappers:
            raise ValueError(
                f"Edge wrapper with UUID '{edge_wrapper.connection_uuid}' "
                f"already exists in graph"
            )

        # Add to collection
        self.edge_wrappers[edge_wrapper.connection_uuid] = edge_wrapper
        edge_wrapper.set_as_registered(True)

        # Update port links (needs to be done after registration)
        self.update_port_link(edge_wrapper)
        
        # Trigger validation (delegates to manager)
        self._validation.mark_edge_dirty(
            edge_wrapper.connection_uuid, 
            ChangeReason.EDGE_ADDED
        )
        
        logger.debug(f"Added edge wrapper: {edge_wrapper.connection_uuid}")
       
        return edge_wrapper

    def remove_edge_wrapper(self, connection_uuid: str) -> Optional['EdgeWrapper']:
        """
        Remove EdgeWrapper from graph.
        
        Also updates port links and triggers validation.
        
        Args:
            connection_uuid: Connection UUID to remove
            
        Returns:
            Removed wrapper or None
        """
        if connection_uuid not in self.edge_wrappers:
            return None
                
        edge_wrapper = self.edge_wrappers[connection_uuid]
        
        # Remove from collection
        del self.edge_wrappers[connection_uuid]
        edge_wrapper.set_as_registered(False)
        
        # Update port links (needs to be done after deregistration)
        self.update_port_link(edge_wrapper)
        
        # Trigger validation for removal
        self._validation.mark_edge_dirty(
            connection_uuid, 
            ChangeReason.EDGE_REMOVED
        )
        
        logger.debug(f"Removed edge wrapper: {connection_uuid}")
 
        return edge_wrapper

    def update_port_link(self, edge_wrapper: 'EdgeWrapper') -> None:
        """
        Updates the link of an EdgeWrapper to the data ports.
        
        An edge being linked to a port means that the port knows about 
        the edge and the edge is functional. This causes an update of 
        all the other connected edges on the ports this edge connects to 
        and might cause other edges to change their linked state if the 
        port connection rules demand it.
        
        Args:
            edge_wrapper: EdgeWrapper to validate
        """
        if edge_wrapper.is_functional():
            self._link_edge_to_port(
                edge_wrapper,
                edge_wrapper.input_node_id,
                edge_wrapper.inlet_port_id
            )
            self._link_edge_to_port(
                edge_wrapper,
                edge_wrapper.output_node_id,
                edge_wrapper.outlet_port_id
            ) 
        else:
            self._unlink_edge_from_port(
                edge_wrapper,
                edge_wrapper.input_node_id,
                edge_wrapper.inlet_port_id
            )
            self._unlink_edge_from_port(
                edge_wrapper,
                edge_wrapper.output_node_id,
                edge_wrapper.outlet_port_id
            ) 

    def _link_edge_to_port(
        self,
        edge_wrapper: 'EdgeWrapper',
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
            port._add_link(edge_wrapper)
            edge_wrapper.validate_link(port)
            edges_wrps = self._get_edge_wrappers_for_port(node_id, port_id)
            if edge_wrapper in edges_wrps:
                edges_wrps.remove(edge_wrapper)
            for ew in edges_wrps:
                if ew.validate_link(port) or ew.state.has_warning():
                    self._validation.mark_edge_dirty(
                        ew.connection_uuid,
                        ChangeReason.EDGE_REDRAW_REQUESTED
                    )
        return port

    def _unlink_edge_from_port(
        self,
        edge_wrapper: 'EdgeWrapper',
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
            edge_wrapper.validate_link(port)
            edges_wrps = self._get_edge_wrappers_for_port(node_id, port_id)
            if edge_wrapper in edges_wrps:
                edges_wrps.remove(edge_wrapper)
            for ew in edges_wrps:
                if ew.is_functional():
                    port._add_link(ew)
            for ew in edges_wrps:   
                if ew.validate_link(port):
                    self._validation.mark_edge_dirty(
                        ew.connection_uuid,
                        ChangeReason.EDGE_REDRAW_REQUESTED
                    )

        return port

    def get_edge_wrapper(self, connection_uuid: str) -> Optional['EdgeWrapper']:
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
            if (wrapper.input_node_id == node_id and 
                wrapper.inlet_port_id == port_id):
                connected_wrappers.append(wrapper)
            if (wrapper.output_node_id == node_id and 
                wrapper.outlet_port_id == port_id):
                connected_wrappers.append(wrapper)
        
        return connected_wrappers

    def _get_edge_wrappers_for_node(self, node_id: str) -> List['EdgeWrapper']:
        """
        Get all EdgeWrappers connected to a specific node.
        
        Args:
            node_id: ID of the node containing the port

        Returns:
            List of EdgeWrappers connected to the specified node
        """
        connected_wrappers = []
        
        for wrapper in self.edge_wrappers.values():
            if (wrapper.input_node_id == node_id or 
                wrapper.output_node_id == node_id):
                connected_wrappers.append(wrapper)
        
        return connected_wrappers

    def _get_all_edges(self, node_id: str) -> List['EdgeWrapper']:  
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

    def _get_linked_edges(self, node_id: str) -> List['EdgeWrapper']:  
        """
        Get all **linked** edges from and to a node.
        These are not necessarily all the edges connected to the node,
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
 
    # =========================================================================
    # VARIABLE MANAGEMENT
    # =========================================================================
    
    def add_variable(self, variable: Variable) -> Variable:
        """
        Add a variable to the graph.
        
        Args:
            variable: Variable instance to add
            
        Returns:
            The added variable
            
        Raises:
            ValueError: If variable name already exists
        """
        if variable.name in self.variables:
            raise ValueError(
                f"Variable '{variable.name}' already exists in graph"
            )
        
        self.variables[variable.name] = variable
        return variable
    
    def remove_variable(self, name: str) -> Variable | None:
        """
        Remove a variable from the graph.
        
        Args:
            name: Name of the variable to remove
            
        Returns:
            The removed variable, or None if not found
        """
        return self.variables.pop(name, None)
    
    def get_variable(self, name: str) -> Variable | None:
        """
        Get a variable by name.
        
        Args:
            name: Name of the variable
            
        Returns:
            The variable if found, None otherwise
        """
        return self.variables.get(name)
    
    def set_variable_value(self, name: str, value: Any) -> bool:
        """
        Set the current value of a variable.
        
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
        """
        Get the current value of a variable.
        
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
    
    # =========================================================================
    # UTILITY METHODS
    # =========================================================================
    
    def validate(self) -> List[str]:
        """
        Validate the graph structure.
        
        Returns:
            List of validation errors (empty if valid)
        """
        errors = []
        
        # Check for orphaned edges (edges referencing non-existent nodes)
        for connection_uuid, edge in self.edge_wrappers.items():
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
    
    def get_disconnected_components(self) -> List[List[str]]:
        """
        Find disconnected components in the graph.
        
        Returns:
            List of components, where each component is a list of node IDs
        """
        visited = set()
        components = []
        
        def dfs(node_id: str, component: List[str]):
            if node_id in visited:
                return
            visited.add(node_id)
            component.append(node_id)
            
            # Follow all edges from this node
            for edge in self.edge_wrappers.values():
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

    # =========================================================================
    # SELECTION MANAGEMENT
    # =========================================================================
        
    def set_selection_state(
        self, 
        selected_nodes: Set[str], 
        selected_connections: Set[str]
    ):
        """Set the complete selection state (backward compatibility)."""
        self.selected_nodes = selected_nodes.copy()
        self.selected_connections = selected_connections.copy()
    
    def get_selection_state(self) -> Tuple[Set[str], Set[str]]:
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

    # =========================================================================
    # CLEANUP
    # =========================================================================

    def clear(self):
        """Clear all nodes, edges, and variables from the graph"""
        # Clear validation manager state
        self._validation.clear()
        
        # Cleanup all wrappers before clearing
        for wrapper in self.node_wrappers.values():
            wrapper.cleanup()
        
        for wrapper in self.edge_wrappers.values():
            wrapper.cleanup()
        
        self.node_wrappers.clear()
        self.edge_wrappers.clear()
        self.variables.clear()
        self.selected_nodes.clear()
        self.selected_connections.clear()
    
    # =========================================================================
    # SERIALIZATION
    # =========================================================================
    
    def to_dict(self) -> Dict[str, Any]:
        """
        Serialize graph to dictionary.
        
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
                connection_uuid: wrapper.edge.to_dict() 
                for connection_uuid, wrapper in self.edge_wrappers.items()
            },
            "variables": {
                name: var.to_dict() 
                for name, var in self.variables.items()
            }
        }
    
    def load_from_dict(self, data: Dict[str, Any]) -> bool:
        """
        Deserialize graph from dictionary.
        
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
                from ..node.node_wrapper import NodeWrapper
                
                for node_id, node_data in data["nodes"].items():
                    # Create wrapper
                    wrapper = NodeWrapper(
                        registry_key=node_data["registry_key"],
                        node_factory=self.node_factory,
                        position=node_data.get("position", (100, 100))
                    )
                    
                    # Initialize and deserialize
                    if wrapper.initialize(self):
                        if wrapper.deserialize(node_data):
                            self.add_node_wrapper(wrapper)
                        else:
                            logger.warning(f"Failed to deserialize node {node_id}")
            
            # Load edges
            if "edges" in data:
                from ..edge.edge_wrapper import EdgeWrapper
                
                for connection_uuid, edge_data in data["edges"].items():
                    edge_wrapper = EdgeWrapper(
                        output_node_id=edge_data["output_node_id"],
                        outlet_port_id=edge_data["outlet_port_id"],
                        input_node_id=edge_data["input_node_id"],
                        inlet_port_id=edge_data["inlet_port_id"],
                        edge_type=FlowType(edge_data["edge_type"]),
                    )
                    
                    if edge_wrapper.initialize(self):
                        edge_wrapper.build()
                        self.add_edge_wrapper(edge_wrapper)
            
            return True
            
        except Exception as e:
            logger.error(
                f"Error loading graph from dictionary: {e}", 
                exc_info=True
            )
            return False
    
    def __str__(self) -> str:
        """String representation of the graph"""
        return (
            f"HaywireGraph(id='{self.graph_id}', name='{self.name}', "
            f"nodes={len(self.node_wrappers)}, edges={len(self.edge_wrappers)}, "
            f"variables={len(self.variables)})"
        )
    
    def __repr__(self) -> str:
        """Detailed string representation"""
        return self.__str__()