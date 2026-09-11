# haywire/core/graph/base.py
"""BaseGraph — the container for a graph's nodes, edges and variables.

It owns the validation pipeline those elements feed, and the graph-tier
settings bags ``props`` and ``meta``.
"""

from __future__ import annotations
from typing import Any, Dict, List, Optional, Tuple, TYPE_CHECKING
from dataclasses import dataclass
from datetime import datetime
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
    from ..settings.settings_graph import GraphSettings
    from .properties import GraphProperties

logger = logging.getLogger(__name__)

# Canvas auto-expansion constants
_CANVAS_EDGE_MARGIN = 1000
_CANVAS_EXPANSION_STEP = 2000
_CANVAS_MIN_SIZE = 4000


@dataclass
class Variable:
    """A named value owned by a graph that keeps state between execution runs.

    Every variable's ``current_value`` is copied into the local context of each
    execution, where a node's worker can read it.
    """

    name: str
    data_type: str
    default_value: Any = None
    current_value: Any = None
    description: str | None = None

    def __post_init__(self):
        """Default ``current_value`` to ``default_value`` when it is ``None``."""
        if self.current_value is None:
            self.current_value = self.default_value

    def reset_to_default(self):
        """Reset ``current_value`` to ``default_value``."""
        self.current_value = self.default_value

    def to_dict(self) -> Dict[str, Any]:
        """Return the variable's fields as a JSON-serializable dict."""
        return {
            "name": self.name,
            "data_type": self.data_type,
            "default_value": self.default_value,
            "current_value": self.current_value,
            "description": self.description,
        }


class BaseGraph:
    """A graph: the nodes, edges and variables describing a flow of data and control.

    Nodes are held as ``NodeWrapper``s, edges as ``EdgeWrapper``s, and every
    structural change marks the element dirty so the validation pipeline
    batches it and notifies subscribers. Use the methods here rather than the
    private managers behind them.
    """

    def __init__(
        self,
        filestem: str = "",
        validation_delay_ms: float = 50.0,
        validation_scheduler: "Optional[ValidationScheduler]" = None,
    ):
        """Initialize an empty graph, requiring a settings registry on the DI context.

        ``graph_id`` is minted here as a uuid4 and is never supplied,
        serialized or reassigned, so two tabs on one file hold two different
        ids.

        Args:
            filestem: The graph's filename without extension. Only a seed —
                ``save_to_file`` and ``load_from_file`` both restamp it from
                the real path. Pass the ``"Untitled N"`` placeholder for a
                graph that has no file yet.
            validation_delay_ms: Debounce window before a batch of dirty marks
                is validated.
            validation_scheduler: Strategy that runs the debounced validation
                pass. Defaults to a background ``threading.Timer``. See
                ``haywire.core.graph.scheduler``.

        Raises:
            RuntimeError: If no settings registry is configured on the DI context.
        """
        # Transient identity of this loaded instance, never serialized.
        self.graph_id: str = str(uuid.uuid4())

        self.node_wrappers: Dict[str, "NodeWrapper"] = {}
        self.edge_wrappers: Dict[str, "EdgeWrapper"] = {}
        self.variables: Dict[str, Variable] = {}

        # Framework-written metadata; the editable fields live in the `meta` bag
        # below. filestem is derived from the real path by save_to_file and
        # load_from_file, never read back from the file it was saved in.
        self.filestem: str = filestem or "Untitled"
        self.created_at: str = datetime.now().isoformat()
        self.modified_at: str | None = None

        # Auto-expanded when nodes approach the boundary. Derived from node
        # positions and not serialized; call estimate_canvas_size() after loading.
        self.canvas_width: int = _CANVAS_MIN_SIZE
        self.canvas_height: int = _CANVAS_MIN_SIZE
        self._canvas_size_changed: bool = False

        # Library-wide compatibility findings from the most recent load_from_dict call.
        # Node-specific findings are written directly onto node state as NodeWarnings.
        self.library_compatibility_findings: list[str] = []

        # The graph tier. The registry comes from the DI context, like node
        # bags, and must already be configured.
        from haywire.core.di.context import get_settings_registry
        from haywire.core.graph.metadata import GraphMetadata
        from haywire.core.graph.properties import GraphProperties

        settings_registry = get_settings_registry()
        self.props: GraphProperties = GraphProperties(registry=settings_registry, graph=self)
        self.props._subscribe_settings()

        # Graphs have no _settings_bags auto-discovery, so settings_bag_for()
        # and cleanup() name both bags by hand.
        self.meta: GraphMetadata = GraphMetadata(registry=settings_registry, graph=self)
        self.meta._subscribe_settings()

        self._validation = ValidationManager(
            graph=self, debounce_ms=validation_delay_ms, scheduler=validation_scheduler
        )

        self._structural: IStructuralValidator = StructuralValidator(graph=self)

    # =========================================================================
    # VALIDATION API (delegates to internal manager)
    # =========================================================================

    def subscribe_to_validation(self, callback: ValidationCallback) -> None:
        """Register ``callback`` to run after each validation batch that found changes.

        Registering the same callback twice still calls it once per batch::

            def on_validated(result: ValidationResult) -> None:
                print(result.get_nodes_requiring_redraw())
                print(result.get_removed_edges())

            graph.subscribe_to_validation(on_validated)
        """
        self._validation.subscribe(callback)

    def unsubscribe_from_validation(self, callback: ValidationCallback) -> None:
        """Remove ``callback`` from the subscribers; a callback that isn't subscribed is ignored."""
        self._validation.unsubscribe(callback)

    def get_validation_stats(self) -> Dict[str, Any]:
        """Return the validation pipeline's counters.

        Returns:
            The dict described in ``ValidationManager.get_statistics``.
        """
        return self._validation.get_statistics()

    def force_validation(self):
        """Validate every queued request now, without waiting for the debounce.

        Call before handing the graph to the interpreter for assembly.
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

    def generate_unique_node_id(self, registry_key: str = "node") -> str:
        """Return a node ID, prefixed from ``registry_key``, that no node in this graph uses."""
        prefix = get_registry_id_from_key(registry_key)

        while True:
            node_id = f"{prefix}_{uuid.uuid4().hex[:6]}"
            if node_id not in self.node_wrappers:
                return node_id

    def create_node_wrapper(
        self,
        registry_key: str,
        position: Tuple[float, float] = (3750, 3750),
        node_data: Optional[Dict[str, Any]] = None,
        node_id: Optional[str] = None,
    ) -> Optional["NodeWrapper"]:
        """Create a node of type ``registry_key``, build it, and add it to the graph.

        Args:
            position: ``(x, y)`` in canvas coordinates.
            node_data: Serialized node data to build the node from, as for a
                paste or a load. When ``None`` the node is built blank.
            node_id: A pre-minted node id to adopt, so edges already remapped
                to it connect to the node this call creates. When ``None`` a
                fresh unique id is generated.

        Returns:
            The added wrapper.

        Raises:
            ValueError: If ``node_id`` is already in the graph.
        """
        from ..node.node_wrapper import NodeWrapper

        if node_id is None:
            node_id = self.generate_unique_node_id(registry_key)
        wrapper = NodeWrapper(registry_key=registry_key, node_id=node_id, graph=self, position=position)

        wrapper.build(node_data or {})

        return self.add_node_wrapper(wrapper)

    def add_node_wrapper(self, wrapper: "NodeWrapper") -> "NodeWrapper":
        """Add an already built wrapper to the graph and mark it dirty as ``NODE_ADDED``.

        Registers the wrapper and resizes the canvas to fit it.

        Returns:
            The added wrapper.

        Raises:
            ValueError: If a wrapper with the same ``node_id`` is already in the graph.
        """
        if wrapper.node_id in self.node_wrappers:
            raise ValueError(f"Node wrapper with ID '{wrapper.node_id}' already exists in graph")

        self.node_wrappers[wrapper.node_id] = wrapper

        wrapper.set_as_registered(True)

        self._check_canvas_size()

        self._validation.mark_node_dirty(wrapper.node_id, ChangeReason.NODE_ADDED)

        logger.debug(f"Added node wrapper: {wrapper.node_id}")

        return wrapper

    def remove_node_wrapper(self, wrapper: "NodeWrapper") -> "NodeWrapper" | None:
        """Remove ``wrapper`` and every edge attached to it, marking them all dirty as removed.

        Returns:
            The removed wrapper, or ``None`` if it isn't in this graph.
        """
        node_id = wrapper.node_id

        if node_id not in self.node_wrappers:
            return None

        # Collected before the node goes, so the edges are still reachable.
        connected_edges = self._get_all_edges(node_id)

        wrapper = self.node_wrappers.pop(node_id)

        wrapper.set_as_registered(False)

        self._check_canvas_size()

        self._validation.mark_node_dirty(node_id, ChangeReason.NODE_REMOVED)

        for edge_wrapper in connected_edges:
            self.remove_edge_wrapper(edge_wrapper.edge_id)

        logger.debug(f"Removed node wrapper: {node_id} (removed {len(connected_edges)} connected edges)")

        return wrapper

    def get_node_wrapper(self, node_id: str) -> "NodeWrapper" | None:
        """Return the wrapper for ``node_id``, or ``None`` if this graph has no such node."""
        return self.node_wrappers.get(node_id)

    def move_node(self, node_id: str, new_x: float, new_y: float) -> bool:
        """Move a node to ``(new_x, new_y)`` and mark it dirty as ``NODE_MOVED``.

        Resizes the canvas if the new position needs it.

        Returns:
            ``True`` if the node was moved, ``False`` if this graph has no
            node with ``node_id``.
        """
        wrapper = self.node_wrappers.get(node_id)
        if wrapper is None:
            return False

        wrapper.move(new_x, new_y)

        self._check_canvas_size()

        self._validation.mark_node_dirty(node_id, ChangeReason.NODE_MOVED)

        return True

    def get_node_wrappers_by_type(self, registry_key: str) -> List["NodeWrapper"]:
        """Return every node wrapper in the graph whose type is ``registry_key``."""
        return [wrapper for wrapper in self.node_wrappers.values() if wrapper.registry_key == registry_key]

    def list_node_wrappers(self) -> List["NodeWrapper"]:
        """Return every node wrapper in the graph."""
        return list(self.node_wrappers.values())

    # =========================================================================
    # CANVAS SIZE MANAGEMENT
    # =========================================================================

    def _check_canvas_size(self) -> bool:
        """Recompute ``canvas_width``/``canvas_height`` from the current node positions.

        Expands or shrinks to the nearest ``_CANVAS_EXPANSION_STEP`` boundary,
        never below ``_CANVAS_MIN_SIZE``. Sets ``_canvas_size_changed`` when the
        size actually changes, so the next ``ValidationResult`` carries it.

        Returns:
            ``True`` if the dimensions changed.
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
        """Set ``canvas_width``/``canvas_height`` from the current node positions.

        Call after loading a graph from disk, before attaching any UI. Leaves
        ``_canvas_size_changed`` clear, so no ``ValidationResult`` reports the
        initial size as a resize.
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
        """Create an edge between two ports, build its adapter chain, and add it to the graph.

        The edge takes its flow type from the source outlet.

        Args:
            lazy: When ``True`` the edge uses lazy (pull-on-demand) propagation.

        Returns:
            The added wrapper.

        Raises:
            ValueError: If an edge with the same id is already in the graph.
        """
        from ..edge.edge_wrapper import EdgeWrapper

        flow_type = self.node_wrappers[source_node_id].node.ports[outlet_port_id].flow_type

        edge_wrapper = EdgeWrapper(
            graph=self,
            source_node_id=source_node_id,
            outlet_port_id=outlet_port_id,
            sink_node_id=sink_node_id,
            inlet_port_id=inlet_port_id,
            edge_type=flow_type,
            lazy=lazy,
        )

        edge_wrapper.build()

        return self.add_edge_wrapper(edge_wrapper)

    def add_edge_wrapper(self, edge_wrapper: "EdgeWrapper") -> "EdgeWrapper":
        """Add an already built wrapper to the graph, link it to its ports, and mark it ``EDGE_ADDED``.

        Returns:
            The added wrapper.

        Raises:
            ValueError: If a wrapper with the same ``edge_id`` is already in the graph.
        """
        if edge_wrapper.edge_id in self.edge_wrappers:
            raise ValueError(f"Edge wrapper with UUID '{edge_wrapper.edge_id}' already exists in graph")

        self.edge_wrappers[edge_wrapper.edge_id] = edge_wrapper
        edge_wrapper.set_as_registered(True)

        edge_wrapper.link()

        self._validation.mark_edge_dirty(edge_wrapper.edge_id, ChangeReason.EDGE_ADDED)

        logger.debug(f"Added edge wrapper: {edge_wrapper.edge_id}")

        return edge_wrapper

    def remove_edge_wrapper(self, edge_id: str) -> Optional["EdgeWrapper"]:
        """Remove the edge with ``edge_id``, detach it from its ports, and mark it ``EDGE_REMOVED``.

        Returns:
            The removed wrapper, or ``None`` if this graph has no such edge.
        """
        if edge_id not in self.edge_wrappers:
            return None

        edge_wrapper = self.edge_wrappers[edge_id]

        del self.edge_wrappers[edge_id]
        edge_wrapper.set_as_registered(False)

        edge_wrapper.detach()

        self._validation.mark_edge_dirty(edge_id, ChangeReason.EDGE_REMOVED)

        logger.debug(f"Removed edge wrapper: {edge_id}")

        return edge_wrapper

    def get_edge_wrapper(self, edge_id: str) -> Optional["EdgeWrapper"]:
        """Return the wrapper for ``edge_id``, or ``None`` if this graph has no such edge."""
        return self.edge_wrappers.get(edge_id)

    def list_edge_wrappers(self) -> List["EdgeWrapper"]:
        """Return every edge wrapper in the graph."""
        return list(self.edge_wrappers.values())

    def _get_edge_wrappers_for_port(self, node_id: str, port_id: str) -> List["EdgeWrapper"]:
        """Return every edge wrapper attached to ``port_id`` on ``node_id``, as inlet or outlet."""
        connected_wrappers = []

        for wrapper in self.edge_wrappers.values():
            if wrapper.sink_node_id == node_id and wrapper.inlet_port_id == port_id:
                connected_wrappers.append(wrapper)
            if wrapper.source_node_id == node_id and wrapper.outlet_port_id == port_id:
                connected_wrappers.append(wrapper)

        return connected_wrappers

    def _get_edge_wrappers_for_node(self, node_id: str) -> List["EdgeWrapper"]:
        """Return every edge wrapper whose source or sink is ``node_id``."""
        connected_wrappers = []

        for wrapper in self.edge_wrappers.values():
            if wrapper.sink_node_id == node_id or wrapper.source_node_id == node_id:
                connected_wrappers.append(wrapper)

        return connected_wrappers

    def _get_all_edges(self, node_id: str) -> List["EdgeWrapper"]:
        """Return every edge wrapper attached to ``node_id``, linked or not."""
        connected_edges = []
        for edges in self.edge_wrappers.values():
            if edges.sink_node_id == node_id or edges.source_node_id == node_id:
                connected_edges.append(edges)
        return connected_edges

    def _get_linked_edges(self, node_id: str) -> List["EdgeWrapper"]:
        """Return the edge wrappers currently linked to ``node_id``'s ports.

        An edge attached to the node but not linked to its ports is left out;
        see ``_get_all_edges``.
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
        """Add a variable to the graph and return it.

        Raises:
            ValueError: If the graph already has a variable with that name.
        """
        if variable.name in self.variables:
            raise ValueError(f"Variable '{variable.name}' already exists in graph")

        self.variables[variable.name] = variable
        return variable

    def remove_variable(self, name: str) -> Variable | None:
        """Remove the variable called ``name`` and return it, or ``None`` if there is none."""
        return self.variables.pop(name, None)

    def get_variable(self, name: str) -> Variable | None:
        """Return the variable called ``name``, or ``None`` if there is none."""
        return self.variables.get(name)

    def set_variable_value(self, name: str, value: Any) -> bool:
        """Set the current value of the variable called ``name``.

        Returns:
            ``False`` if the graph has no such variable, otherwise ``True``.
        """
        if name in self.variables:
            self.variables[name].current_value = value
            return True
        return False

    def get_variable_value(self, name: str) -> Any:
        """Return the current value of the variable called ``name``, or ``None`` if there is none."""
        variable = self.variables.get(name)
        return variable.current_value if variable else None

    def reset_all_variables(self):
        """Reset every variable to its default value."""
        for variable in self.variables.values():
            variable.reset_to_default()

    # =========================================================================
    # UTILITY METHODS
    # =========================================================================

    def get_disconnected_components(self) -> List[List[str]]:
        """Return the graph's connected components, each as a list of node IDs.

        Edge direction is ignored, so two nodes joined by any edge land in the
        same component.
        """
        visited = set()
        components = []

        def dfs(node_id: str, component: List[str]):
            if node_id in visited:
                return
            visited.add(node_id)
            component.append(node_id)

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
        """Remove every node, edge and variable from the graph.

        Subscribers are notified of all the removals, through an immediate
        validation pass, before the wrappers are cleaned up. The graph stays
        usable afterwards; ``cleanup()`` is what releases it for good.
        """
        # Edges before nodes: the edge marks need their wrappers still in place.
        for edge_id in list(self.edge_wrappers.keys()):
            self._validation.mark_edge_dirty(edge_id, ChangeReason.EDGE_REMOVED)

        for node_id in list(self.node_wrappers.keys()):
            self._validation.mark_node_dirty(node_id, ChangeReason.NODE_REMOVED)

        # Notify listeners while the wrappers are still alive.
        self._validation.force_immediate_validation()

        for node_wrapper in self.node_wrappers.values():
            node_wrapper.cleanup()

        for edge_wrapper in self.edge_wrappers.values():
            edge_wrapper.cleanup()

        self.node_wrappers.clear()
        self.edge_wrappers.clear()
        self.variables.clear()

        self._validation.clear()

    def settings_bag_for(self, owner_cls: type) -> "GraphSettings | None":
        """Return this graph's settings bag that is an instance of ``owner_cls``, or ``None``.

        Matches ``props`` and ``meta`` by class (see ADR 0022).
        """
        for bag in (self.props, self.meta):
            if isinstance(bag, owner_cls):
                return bag
        return None

    def cleanup(self) -> None:
        """Release graph-owned resources: both settings bags' registry subscriptions.

        Call when the graph object is discarded for good. ``clear()`` does not
        call it, so a cleared graph stays usable.
        """
        self.props._cleanup()
        self.meta._cleanup()

    # =========================================================================
    # SERIALIZATION
    # =========================================================================

    def to_dict(self, include_data: bool = True) -> Dict[str, Any]:
        """Return the graph as a JSON-serializable dict, stamped with the current format version.

        Args:
            include_data: When ``False``, node field values are left out and
                only the structure is serialized.
        """
        from haywire.core.graph.prehydration import CURRENT_FORMAT_VERSION

        return {
            "format_version": CURRENT_FORMAT_VERSION,
            "filestem": self.filestem,
            "created_at": self.created_at,
            "modified_at": self.modified_at,
            "meta": self.meta._to_dict(),
            "nodes": {
                node_id: wrapper.serialize(include_data=include_data)
                for node_id, wrapper in self.node_wrappers.items()
            },
            "edges": {edge_id: wrapper.edge.to_dict() for edge_id, wrapper in self.edge_wrappers.items()},
            "variables": {name: var.to_dict() for name, var in self.variables.items()},
            "props": self.props._to_dict(),
        }

    def load_from_dict(self, data: Dict[str, Any]) -> bool:
        """Replace this graph's contents with ``data``, upgraded to the current file format first.

        Clears the graph, restores the ``props`` and ``meta`` bags, then the
        variables, nodes and edges; a node or edge that fails to load is logged
        and skipped. ``created_at`` and ``modified_at`` come from ``data``,
        ``filestem`` does not. Compatibility warnings for the loaded nodes are
        applied at the end.

        Returns:
            ``True`` on success, ``False`` if the load raised.

        Raises:
            HaywireException: If ``data`` came from a newer Haywire, or is not a graph.
        """
        from haywire.core.graph.prehydration import prehydrate

        data = prehydrate(data)

        try:
            # graph_id and filestem are not read back: the first is this
            # instance's identity, the second comes from the real path.
            self.created_at = data.get("created_at") or self.created_at
            self.modified_at = data.get("modified_at")

            self.clear()

            # Restored before the nodes: a node bag's graph mirrors seed from
            # these cells at construction. _reset_all first, because this graph
            # may be reused and still carry the previous file's opinions.
            self.props._reset_all()
            self.props._from_dict(data.get("props", {}))

            # No node-side mirrors, so its order relative to the nodes is free.
            self.meta._reset_all()
            self.meta._from_dict(data.get("meta", {}))

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

            if "nodes" in data:
                from ..node.node_wrapper import NodeWrapper

                for node_id, wrapper_data in data["nodes"].items():
                    try:
                        wrapper = NodeWrapper(
                            registry_key=wrapper_data["registry_key"],
                            node_id=node_id,
                            graph=self,
                            position=tuple(wrapper_data.get("position", [100, 100])),
                        )

                        wrapper.build(wrapper_data.get("node_data", {}))

                        self.add_node_wrapper(wrapper)
                    except Exception as e:
                        logger.error(f"Error loading node {node_id} from dictionary: {e}", exc_info=True)

            if "edges" in data:
                from ..edge.edge_wrapper import EdgeWrapper

                for edge_id, edge_data in data["edges"].items():
                    try:
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

                        chain = edge_data["chain_adapter_keys"]
                        edge_wrapper._check_chain_for_changes(chain)

                        self.add_edge_wrapper(edge_wrapper)
                    except Exception as e:
                        logger.error(f"Error loading edge {edge_id} from dictionary: {e}", exc_info=True)

            for wrapper in self.node_wrappers.values():
                wrapper._housekeeping()

            self._apply_compatibility_warnings(data)

            return True

        except Exception as e:
            logger.error(f"Error loading graph from dictionary: {e}", exc_info=True)
            return False

    def _apply_compatibility_warnings(self, data: Dict[str, Any]) -> None:
        """Record compatibility warnings for the nodes just loaded from ``data``.

        Checks each node's library version as saved in ``data``, not the live
        class, against that library's warning history. Per-node findings become
        ``NodeWarning`` records on node state, library-wide ones replace
        ``library_compatibility_findings``, and node data is never touched.
        With no library system configured it returns having cleared the findings.
        """
        from haywire.core.library.compatibility import (
            CompatibilityChecker,
            SavedNode,
        )
        from haywire.core.node.node_warning import NodeWarning

        self.library_compatibility_findings = []

        try:
            from haywire.core.di.config import get_library_system

            lib_registry = get_library_system().get_library_registry()
        except Exception as exc:  # a bare graph has no library system to check against
            logger.debug(f"Compatibility check skipped (no library system): {exc}")
            return

        def history_lookup(lib_id: str):
            lib = lib_registry._libraries.get(lib_id)
            if lib is None:
                return []
            try:
                return lib.compatibility_warnings()
            except Exception as exc:
                logger.warning(f"compatibility_warnings() failed for '{lib_id}': {exc}")
                return []

        saved_nodes: list[SavedNode] = []
        for node_id, wrapper_data in data.get("nodes", {}).items():
            node_data = wrapper_data.get("node_data", {})
            library_block = node_data.get("library", {})
            registry_key = wrapper_data.get("registry_key", "")
            saved_nodes.append(
                SavedNode(
                    node_id=node_id,
                    registry_key=registry_key,
                    library_id=library_block.get("name", ""),
                    saved_version=library_block.get("version"),
                )
            )

        checker = CompatibilityChecker(history_lookup)
        findings = checker.check(saved_nodes)

        for finding in findings:
            if finding.node_id is None:
                self.library_compatibility_findings.append(finding.message)
                continue
            wrapper = self.node_wrappers.get(finding.node_id)
            if wrapper is not None:
                wrapper.state.add_warning(
                    NodeWarning(
                        message=finding.message,
                        source_version=finding.source_version,
                        kind="compatibility",
                    )
                )

    def __str__(self) -> str:
        """Return a one-line summary naming the file stem, id, and element counts."""
        return (
            f"HaywireGraph(filestem='{self.filestem}', id={self.graph_id[:8]}, "
            f"nodes={len(self.node_wrappers)}, edges={len(self.edge_wrappers)}, "
            f"variables={len(self.variables)})"
        )

    def __repr__(self) -> str:
        """Return the same summary as ``__str__``."""
        return self.__str__()

    # =========================================================================
    # FILE I/O
    # =========================================================================

    def save_to_file(self, filepath: str, include_data: bool = True) -> bool:
        """Write the graph to ``filepath`` as JSON, restamping ``modified_at`` and ``filestem``.

        The JSON is written to a temporary file and renamed over the target, so
        a failure leaves any existing file untouched.

        Args:
            include_data: When ``False``, saves the structure without field values.

        Returns:
            ``True`` if the save succeeded, ``False`` if it raised.

        Example::

            graph.save_to_file("my_graph.json")
            graph.save_to_file("template.json", include_data=False)
        """
        import json
        import os
        from datetime import datetime
        from pathlib import Path

        try:
            # Stamped before serializing, or the write persists the previous
            # save's values.
            self.modified_at = datetime.now().isoformat()
            self.filestem = Path(filepath).stem

            data = self.to_dict(include_data=include_data)

            # Serialized to a string first: if this fails, the file is untouched.
            json_str = json.dumps(data, indent=2, ensure_ascii=False)

            # Atomic write: fill a temp file, then rename it over the target.
            target = Path(filepath)
            tmp_path = target.with_suffix(".haywire.tmp")
            try:
                tmp_path.write_text(json_str, encoding="utf-8")
                os.replace(str(tmp_path), str(target))
            except Exception:
                tmp_path.unlink(missing_ok=True)
                raise

            logger.info(f"Successfully saved graph to {filepath}")
            return True

        except Exception as e:
            logger.error(f"Failed to save graph to {filepath}: {e}", exc_info=True)
            return False

    def load_from_file(self, filepath: str) -> bool:
        """Load the graph from the JSON file at ``filepath``.

        On success ``filestem`` is stamped from the path, not read from the
        file's own copy.

        Returns:
            ``True`` if the load succeeded, ``False`` on a read, parse or load error.
        """
        import json
        from pathlib import Path

        try:
            with open(filepath, "r", encoding="utf-8") as f:
                data = json.load(f)

            success = self.load_from_dict(data)

            if success:
                self.filestem = Path(filepath).stem
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
