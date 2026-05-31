# haywire/core/graph/base.py
"""
BaseGraph - Main graph container and coordinator.

Manages collections of nodes, edges, and variables, and coordinates
with internal managers for validation, etc.
"""

from __future__ import annotations
from typing import Any, Dict, List, Optional, Tuple, TYPE_CHECKING
from dataclasses import dataclass
import math
import uuid
import logging

from haywire.core.validation.interface import IStructuralValidator
from haywire.core.validation.structural_validator import StructuralValidator
from haywire.core.library.utils import get_registry_id_from_key

from ..types import FlowType
from .validation import ValidationManager, ValidationCallback
from .types import ChangeReason

if TYPE_CHECKING:
    from ..types import DataPort
    from ..edge.edge_wrapper import EdgeWrapper
    from ..node.node_wrapper import NodeWrapper
    from .scheduler import ValidationScheduler

logger = logging.getLogger(__name__)

# Canvas auto-expansion constants
_CANVAS_EDGE_MARGIN = 1000
_CANVAS_EXPANSION_STEP = 2000
_CANVAS_MIN_SIZE = 4000


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
            "description": self.description,
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
        validation_delay_ms: float = 50.0,
        validation_scheduler: "Optional[ValidationScheduler]" = None,
    ):
        """
        Initialize a new Haywire graph.

        Args:
            graph_id: Unique identifier for this graph
            name: Human-readable name for the graph
            validation_delay_ms: Debounce delay for validation (default 50ms)
            validation_scheduler: Strategy that runs the debounced validation
                pass. Defaults to a background ``threading.Timer`` (legacy
                behavior). See ``haywire.core.graph.scheduler`` and ADR 0002.
        """
        self.graph_id: str = graph_id
        self.name: str = name or f"Graph_{graph_id}"

        # Core containers
        self.node_wrappers: Dict[str, "NodeWrapper"] = {}
        self.edge_wrappers: Dict[str, "EdgeWrapper"] = {}
        self.variables: Dict[str, Variable] = {}

        # Metadata
        self.description: str = ""
        self.version: str = "1.0.0"
        self.author: str = ""
        self.created_at: str | None = None
        self.modified_at: str | None = None

        # Canvas dimensions — auto-expanded when nodes approach the boundary.
        # Persisted as runtime state; call estimate_canvas_size() after loading.
        self.canvas_width: int = _CANVAS_MIN_SIZE
        self.canvas_height: int = _CANVAS_MIN_SIZE
        self._canvas_size_changed: bool = False

        # Internal managers (private - implementation details)
        self._validation = ValidationManager(
            graph=self, debounce_ms=validation_delay_ms, scheduler=validation_scheduler
        )

        self._structural: IStructuralValidator = StructuralValidator(graph=self)

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

    def force_validation(self):
        """
        Forces the graph to do an immediate validation
        on all queued validation requests.

        Its good practice to call this method before adding
        the graph to the interpretor for assembly
        """
        self._validation.force_immediate_validation()

    # =========================================================================
    # REFRESH REQUESTS (bypass undo history - non-mutating operations)
    # =========================================================================

    def request_node_redraw(self, node_id: str) -> None:
        """Request visual refresh for a node. Does not modify state."""
        if node_id in self.node_wrappers:
            self._validation.mark_node_dirty(node_id, ChangeReason.NODE_REDRAW_REQUESTED)

    def request_node_revalidation(self, node_id: str) -> None:
        """Request structural revalidation for a node and its connected edges."""
        if node_id in self.node_wrappers:
            self._validation.mark_node_dirty(node_id, ChangeReason.NODE_VALIDATION_REQUESTED)

    def request_node_reset(self, node_id: str) -> None:
        """Request full rebuild for a node (re-runs build + validation)."""
        if node_id in self.node_wrappers:
            self._validation.mark_node_dirty(node_id, ChangeReason.NODE_RESET_REQUESTED)

    def request_edge_redraw(self, edge_id: str) -> None:
        """Request visual refresh for an edge. Does not modify state."""
        if edge_id in self.edge_wrappers:
            self._validation.mark_edge_dirty(edge_id, ChangeReason.EDGE_REDRAW_REQUESTED)

    def request_edge_revalidation(self, edge_id: str) -> None:
        """Request structural revalidation for an edge."""
        if edge_id in self.edge_wrappers:
            self._validation.mark_edge_dirty(edge_id, ChangeReason.EDGE_VALIDATION_REQUESTED)

    def request_edge_reset(self, edge_id: str) -> None:
        """Request full rebuild for an edge (re-runs build + port link update)."""
        if edge_id in self.edge_wrappers:
            self._validation.mark_edge_dirty(edge_id, ChangeReason.EDGE_RESET_REQUESTED)

    def request_full_redraw(self) -> None:
        """Request visual refresh for all nodes and edges."""
        for node_id in self.node_wrappers:
            self._validation.mark_node_dirty(node_id, ChangeReason.NODE_REDRAW_REQUESTED)
        for edge_id in self.edge_wrappers:
            self._validation.mark_edge_dirty(edge_id, ChangeReason.EDGE_REDRAW_REQUESTED)

    def request_full_revalidation(self) -> None:
        """Request structural revalidation for all nodes and edges."""
        for node_id in self.node_wrappers:
            self._validation.mark_node_dirty(node_id, ChangeReason.NODE_VALIDATION_REQUESTED)
        for edge_id in self.edge_wrappers:
            self._validation.mark_edge_dirty(edge_id, ChangeReason.EDGE_VALIDATION_REQUESTED)

    def request_full_reset(self) -> None:
        """Request full rebuild for all nodes and edges."""
        for node_id in self.node_wrappers:
            self._validation.mark_node_dirty(node_id, ChangeReason.NODE_RESET_REQUESTED)
        for edge_id in self.edge_wrappers:
            self._validation.mark_edge_dirty(edge_id, ChangeReason.EDGE_RESET_REQUESTED)

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
        self, registry_key: str, position: Tuple[float, float] = (3750, 3750)
    ) -> Optional["NodeWrapper"]:
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

        node_id = self.generate_unique_node_id(get_registry_id_from_key(registry_key))
        # Create new wrapper
        wrapper = NodeWrapper(registry_key=registry_key, node_id=node_id, graph=self, position=position)

        wrapper.build()

        # Add to graph's collection (triggers validation)
        return self.add_node_wrapper(wrapper)

    def add_node_wrapper(self, wrapper: "NodeWrapper") -> "NodeWrapper":
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
            raise ValueError(f"Node wrapper with ID '{wrapper.node_id}' already exists in graph")

        # Add to collection
        self.node_wrappers[wrapper.node_id] = wrapper

        wrapper.set_as_registered(True)

        # Check whether the canvas needs to grow to accommodate the new node.
        self._check_canvas_size()

        # Trigger validation (delegates to manager)
        self._validation.mark_node_dirty(wrapper.node_id, ChangeReason.NODE_ADDED)

        logger.debug(f"Added node wrapper: {wrapper.node_id}")

        return wrapper

    def remove_node_wrapper(self, wrapper: "NodeWrapper") -> "NodeWrapper" | None:
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

        wrapper.set_as_registered(False)

        # Check whether the canvas can shrink now that the node is gone.
        self._check_canvas_size()

        # Trigger validation for removal
        self._validation.mark_node_dirty(node_id, ChangeReason.NODE_REMOVED)

        # Remove all connected edges
        for edge_wrapper in connected_edges:
            self.remove_edge_wrapper(edge_wrapper.edge_id)

        logger.debug(f"Removed node wrapper: {node_id} (removed {len(connected_edges)} connected edges)")

        return wrapper

    def get_node_wrapper(self, node_id: str) -> "NodeWrapper" | None:
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

        # Check whether the canvas needs to grow or shrink after the move.
        self._check_canvas_size()

        # Trigger validation with MOVED reason
        self._validation.mark_node_dirty(node_id, ChangeReason.NODE_MOVED)

        return True

    def get_node_wrappers_by_type(self, registry_key: str) -> List["NodeWrapper"]:
        """
        Get all node wrappers of a specific type.

        Args:
            registry_key: The node type to filter by

        Returns:
            List of wrappers matching the type
        """
        return [wrapper for wrapper in self.node_wrappers.values() if wrapper.registry_key == registry_key]

    def list_node_wrappers(self) -> List["NodeWrapper"]:
        """
        Get all node wrappers in the graph.

        Returns:
            List of all node wrappers
        """
        return list(self.node_wrappers.values())

    # =========================================================================
    # CANVAS SIZE MANAGEMENT
    # =========================================================================

    def _check_canvas_size(self) -> bool:
        """
        Recompute canvas_width/canvas_height from current node positions.

        Expands or shrinks to the nearest _CANVAS_EXPANSION_STEP boundary,
        never going below _CANVAS_MIN_SIZE.  Sets _canvas_size_changed = True
        when the size actually changes so the next ValidationResult carries it.

        Returns:
            True if the canvas dimensions changed.
        """
        if not self.node_wrappers:
            new_w = _CANVAS_MIN_SIZE
            new_h = _CANVAS_MIN_SIZE
        else:
            max_x = max(w.node.props.posX for w in self.node_wrappers.values())
            max_y = max(w.node.props.posY for w in self.node_wrappers.values())
            needed_w = max_x + _CANVAS_EDGE_MARGIN
            needed_h = max_y + _CANVAS_EDGE_MARGIN
            steps_w = math.ceil(needed_w / _CANVAS_EXPANSION_STEP)
            steps_h = math.ceil(needed_h / _CANVAS_EXPANSION_STEP)
            new_w = max(_CANVAS_MIN_SIZE, steps_w * _CANVAS_EXPANSION_STEP)
            new_h = max(_CANVAS_MIN_SIZE, steps_h * _CANVAS_EXPANSION_STEP)

        if new_w != self.canvas_width or new_h != self.canvas_height:
            self.canvas_width = new_w
            self.canvas_height = new_h
            self._canvas_size_changed = True
            logger.debug(f"Canvas resized to {new_w}×{new_h}")
            return True
        return False

    def estimate_canvas_size(self) -> None:
        """
        Initialise canvas_width/canvas_height from current node positions.

        Call this after loading a graph from disk, before attaching any UI.
        Unlike _check_canvas_size(), this does NOT set _canvas_size_changed —
        the initial size is applied directly when the manager wires up.
        """
        self._check_canvas_size()
        self._canvas_size_changed = False

    def _get_port(self, node_id: str, port_id: str) -> "DataPort":
        """Convenience method to get a port from a node."""
        return self.node_wrappers[node_id].node.ports[port_id]

    def _get_ports(self, node_id: str) -> List["DataPort"]:
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
        source_node_id: str,
        outlet_port_id: str,
        sink_node_id: str,
        inlet_port_id: str,
        lazy: bool = False,
    ) -> Optional["EdgeWrapper"]:
        """
        Create and add EdgeWrapper (graph-managed factory pattern).

        This creates a new edge, builds its adapter chain, and adds it to the graph.
        Automatically triggers validation pipeline.

        Args:
            source_node_id: Source node ID
            outlet_port_id: Source outlet ID
            sink_node_id: Target node ID
            inlet_port_id: Target inlet ID
            lazy: If True, edge uses lazy (pull-on-demand) propagation

        Returns:
            EdgeWrapper if successful, None if failed
        """
        from ..edge.edge_wrapper import EdgeWrapper

        flow_type = self.node_wrappers[source_node_id].node.ports[outlet_port_id].flow_type

        # Create new wrapper
        edge_wrapper = EdgeWrapper(
            graph=self,
            source_node_id=source_node_id,
            outlet_port_id=outlet_port_id,
            sink_node_id=sink_node_id,
            inlet_port_id=inlet_port_id,
            edge_type=flow_type,
            lazy=lazy,
        )

        # Build adapter chain
        edge_wrapper.build()

        # Add to graph's collection (triggers validation automatically)
        return self.add_edge_wrapper(edge_wrapper)

    def add_edge_wrapper(self, edge_wrapper: "EdgeWrapper") -> "EdgeWrapper":
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
            ValueError: If edge_id already exists
        """
        if edge_wrapper.edge_id in self.edge_wrappers:
            raise ValueError(f"Edge wrapper with UUID '{edge_wrapper.edge_id}' already exists in graph")

        # Add to collection
        self.edge_wrappers[edge_wrapper.edge_id] = edge_wrapper
        edge_wrapper.set_as_registered(True)

        # Edge drives its own linking to ports
        edge_wrapper.link()

        # Trigger validation (delegates to manager)
        self._validation.mark_edge_dirty(edge_wrapper.edge_id, ChangeReason.EDGE_ADDED)

        logger.debug(f"Added edge wrapper: {edge_wrapper.edge_id}")

        return edge_wrapper

    def remove_edge_wrapper(self, edge_id: str) -> Optional["EdgeWrapper"]:
        """
        Remove EdgeWrapper from graph.

        Also detaches from ports and triggers validation.

        Args:
            edge_id: Edge UUID to remove

        Returns:
            Removed wrapper or None
        """
        if edge_id not in self.edge_wrappers:
            return None

        edge_wrapper = self.edge_wrappers[edge_id]

        # Remove from collection
        del self.edge_wrappers[edge_id]
        edge_wrapper.set_as_registered(False)

        # Edge drives its own detachment from ports
        edge_wrapper.detach()

        # Trigger validation for removal
        self._validation.mark_edge_dirty(edge_id, ChangeReason.EDGE_REMOVED)

        logger.debug(f"Removed edge wrapper: {edge_id}")

        return edge_wrapper

    def get_edge_wrapper(self, edge_id: str) -> Optional["EdgeWrapper"]:
        """
        Get EdgeWrapper by Edge ID.

        Args:
            edge_id: Edge ID

        Returns:
            EdgeWrapper if found, None otherwise
        """
        return self.edge_wrappers.get(edge_id)

    def list_edge_wrappers(self) -> List["EdgeWrapper"]:
        """
        Get all EdgeWrappers.

        Returns:
            List of all edge wrappers
        """
        return list(self.edge_wrappers.values())

    def _get_edge_wrappers_for_port(self, node_id: str, port_id: str) -> List["EdgeWrapper"]:
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
            if wrapper.sink_node_id == node_id and wrapper.inlet_port_id == port_id:
                connected_wrappers.append(wrapper)
            if wrapper.source_node_id == node_id and wrapper.outlet_port_id == port_id:
                connected_wrappers.append(wrapper)

        return connected_wrappers

    def _get_edge_wrappers_for_node(self, node_id: str) -> List["EdgeWrapper"]:
        """
        Get all EdgeWrappers connected to a specific node.

        Args:
            node_id: ID of the node containing the port

        Returns:
            List of EdgeWrappers connected to the specified node
        """
        connected_wrappers = []

        for wrapper in self.edge_wrappers.values():
            if wrapper.sink_node_id == node_id or wrapper.source_node_id == node_id:
                connected_wrappers.append(wrapper)

        return connected_wrappers

    def _get_all_edges(self, node_id: str) -> List["EdgeWrapper"]:
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
            if edges.sink_node_id == node_id or edges.source_node_id == node_id:
                connected_edges.append(edges)
        return connected_edges

    def _get_linked_edges(self, node_id: str) -> List["EdgeWrapper"]:
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
            raise ValueError(f"Variable '{variable.name}' already exists in graph")

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
        Validate the graph structure (both formal and structural).

        Returns:
            List of validation errors (empty if valid)
        """
        errors = []

        # Existing formal validation (orphaned edges, etc.)
        for edge_id, edge in self.edge_wrappers.items():
            if edge.source_node_id not in self.node_wrappers:
                errors.append(f"Edge {edge_id} references non-existent output node: {edge.source_node_id}")
            if edge.sink_node_id not in self.node_wrappers:
                errors.append(f"Edge {edge_id} references non-existent input node: {edge.sink_node_id}")

        # Wrapper-level validation
        for wrapper in self.node_wrappers.values():
            wrapper_errors = wrapper.validate()
            for error in wrapper_errors:
                errors.append(f"Node {wrapper.node_id}: {error}")

        # NEW: Graph-wide structural validation
        structural_errors = self._structural.validate_graph()
        errors.extend(structural_errors)

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
                if edge.source_node_id == node_id:
                    dfs(edge.sink_node_id, component)
                elif edge.sink_node_id == node_id:
                    dfs(edge.source_node_id, component)

        for node_id in self.node_wrappers.keys():
            if node_id not in visited:
                component: list[str] = []
                dfs(node_id, component)
                components.append(component)

        return components

    # =========================================================================
    # CLEANUP
    # =========================================================================

    def clear(self):
        """
        Clear all nodes, edges, and variables from the graph.

        Notifies validation listeners about all removed elements before clearing.
        """
        # Mark all edges as removed (must do edges before nodes to maintain refs)
        for edge_id in list(self.edge_wrappers.keys()):
            self._validation.mark_edge_dirty(edge_id, ChangeReason.EDGE_REMOVED)

        # Mark all nodes as removed
        for node_id in list(self.node_wrappers.keys()):
            self._validation.mark_node_dirty(node_id, ChangeReason.NODE_REMOVED)

        # Force immediate validation to notify listeners before cleanup
        self._validation.force_immediate_validation()

        # Now cleanup all wrappers
        for node_wrapper in self.node_wrappers.values():
            node_wrapper.cleanup()

        for edge_wrapper in self.edge_wrappers.values():
            edge_wrapper.cleanup()

        # Clear all data structures
        self.node_wrappers.clear()
        self.edge_wrappers.clear()
        self.variables.clear()

        # Clear validation manager state after notifications
        self._validation.clear()

    # =========================================================================
    # SERIALIZATION
    # =========================================================================

    def to_dict(self, include_data: bool = True) -> Dict[str, Any]:
        """
        Serialize graph to dictionary.

        Args:
            include_data: If True, includes field values. If False, structure only.

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
                node_id: wrapper.serialize(include_data=include_data)
                for node_id, wrapper in self.node_wrappers.items()
            },
            "edges": {edge_id: wrapper.edge.to_dict() for edge_id, wrapper in self.edge_wrappers.items()},
            "variables": {name: var.to_dict() for name, var in self.variables.items()},
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
                        description=var_data.get("description"),
                    )
                    self.variables[name] = var

            # Load node wrappers
            if "nodes" in data:
                from ..node.node_wrapper import NodeWrapper

                try:
                    for node_id, wrapper_data in data["nodes"].items():
                        # Create wrapper
                        wrapper = NodeWrapper(
                            registry_key=wrapper_data["registry_key"],
                            node_id=node_id,
                            graph=self,
                            position=tuple(wrapper_data.get("position", [100, 100])),
                        )

                        # Instantiate with original node_id and build
                        wrapper.build(wrapper_data.get("node_data", {}))

                        # Add to graph
                        self.add_node_wrapper(wrapper)

                except Exception as e:
                    logger.error(f"Error loading node {node_id} from dictionary: {e}", exc_info=True)

            # Load edges
            if "edges" in data:
                from ..edge.edge_wrapper import EdgeWrapper

                try:
                    for edge_id, edge_data in data["edges"].items():
                        edge_wrapper = EdgeWrapper(
                            graph=self,
                            source_node_id=edge_data["source_node_id"],
                            outlet_port_id=edge_data["outlet_port_id"],
                            sink_node_id=edge_data["sink_node_id"],
                            inlet_port_id=edge_data["inlet_port_id"],
                            edge_type=FlowType(edge_data["edge_type"]),
                            lazy=edge_data.get("is_lazy", False),
                        )

                        edge_wrapper.build()

                        # Validate adapter chain for changes
                        chain = edge_data["chain_adapter_keys"]
                        edge_wrapper._check_chain_for_changes(chain)

                        self.add_edge_wrapper(edge_wrapper)

                except Exception as e:
                    logger.error(f"Error loading edge {edge_id} from dictionary: {e}", exc_info=True)

            for wrapper in self.node_wrappers.values():
                wrapper._housekeeping()

            return True

        except Exception as e:
            logger.error(f"Error loading graph from dictionary: {e}", exc_info=True)
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

    # =========================================================================
    # FILE I/O
    # =========================================================================

    def save_to_file(self, filepath: str, include_data: bool = True) -> bool:
        """
        Save graph to JSON file.

        Args:
            filepath: Path to save the graph file
            include_data: If True (default), saves field values.
                         If False, saves structure only.

        Returns:
            True if save succeeded, False otherwise

        Examples:
            graph.save_to_file('my_graph.json')  # Full save
            graph.save_to_file('template.json', include_data=False)  # Structure only
        """
        import json
        import os
        from datetime import datetime
        from pathlib import Path

        try:
            # Update modification timestamp
            self.modified_at = datetime.now().isoformat()

            # Serialize graph
            data = self.to_dict(include_data=include_data)

            # Serialize to string first — if this fails, the file is untouched
            json_str = json.dumps(data, indent=2, ensure_ascii=False)

            # Atomic write: write to a temp file, then rename over the target
            target = Path(filepath)
            tmp_path = target.with_suffix(".haywire.tmp")
            try:
                tmp_path.write_text(json_str, encoding="utf-8")
                os.replace(str(tmp_path), str(target))
            except Exception:
                # Clean up the temp file if rename failed
                tmp_path.unlink(missing_ok=True)
                raise

            logger.info(f"Successfully saved graph to {filepath}")
            return True

        except Exception as e:
            logger.error(f"Failed to save graph to {filepath}: {e}", exc_info=True)
            return False

    def load_from_file(self, filepath: str) -> bool:
        """
        Load graph from JSON file.

        Args:
            filepath: Path to load the graph file from

        Returns:
            True if load succeeded, False otherwise
        """
        import json

        try:
            # Read from file
            with open(filepath, "r", encoding="utf-8") as f:
                data = json.load(f)

            # Deserialize graph
            success = self.load_from_dict(data)

            if success:
                logger.info(
                    f"Successfully loaded graph from {filepath}: "
                    f"{len(self.node_wrappers)} nodes, "
                    f"{len(self.edge_wrappers)} edges"
                )
            else:
                logger.error(f"Failed to load graph from {filepath}")

            return success

        except Exception as e:
            logger.error(f"Failed to load graph from {filepath}: {e}", exc_info=True)
            return False
