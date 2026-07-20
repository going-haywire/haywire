import logging
from typing import Any, Dict, List, Optional, Tuple
from haywire.core.graph.base import BaseGraph
from haywire.core.edge.edge_wrapper import EdgeWrapper
from haywire.core.node.node_wrapper import NodeWrapper
from haywire.core.node.factory import NodeFactory
from haywire.core.undo.interfaces import IHistoryManager
from haywire.core.undo.history_manager import HistoryManager
from haywire.core.undo.config import UndoConfig
from haywire.core.undo.actions.graph_actions import (
    AddNodeAction,
    MoveNodesAction,
    MoveNodesToAction,
    RemoveElementsAction,
    AddEdgeAction,
    PasteClipboardAction,
    SplitEdgeWithRerouteAction,
    DissolveRerouteAction,
    SetPropertyAction,
)

logger = logging.getLogger(__name__)


class Editor:
    """
    High-level editor interface with simple callback-based change notifications.

    This class provides semantic methods for graph operations and abstracts away
    the complexity of managing the graph, history, and node factory together.
    Uses simple callbacks for change notifications rather than complex events.
    """

    def __init__(
        self,
        graph: BaseGraph,
        node_factory: NodeFactory,
        undo_config: Optional[UndoConfig] = None,
    ):
        """
        Initialize the editor with core components.

        Args:
            graph:        The graph instance to manipulate.
            node_factory: Factory for looking up and subscribing to node classes.
            undo_config:  Optional undo configuration. Defaults to UndoConfig().
        """
        self.graph: BaseGraph = graph
        self.history_manager: IHistoryManager = HistoryManager(undo_config or UndoConfig())
        self._node_factory = node_factory

    # =============================================================================
    # NODE OPERATIONS
    # =============================================================================

    def create_wrapper(
        self, registry_key: str, position: Tuple[float, float] = (3750, 3750)
    ) -> Optional[NodeWrapper]:
        """
        Create a new node wrapper of the specified type at the given position.

        Args:
            registry_key: Registry key for the node type to create
            position: (x, y) position for the node

        Returns:
            The created node wrapper or None if creation failed
        """
        try:
            # Create and execute undo action
            action = AddNodeAction(graph=self.graph, registry_key=registry_key, position=position)
            self.history_manager.add_action(action)

            logger.info(f"Created node of type {registry_key} at {position}")

            return action.wrapper

        except Exception as e:
            logger.error(f"Error creating node of type {registry_key}: {e}")
            return None

    def paste_clipboard(
        self, payload: Dict[str, Any], paste_x: float, paste_y: float
    ) -> Optional[Tuple[List[str], List[str]]]:
        """Paste a clipboard payload at (paste_x, paste_y) as one undoable action.

        Unknown node types in the payload are NOT rejected — they paste as
        placeholder error nodes (like loading a .haywire file whose library is
        missing).

        Returns ``(new_node_ids, new_edge_ids)`` for the freshly pasted
        elements (so callers can auto-select them), or ``None`` on an
        unexpected error.
        """
        try:
            action = PasteClipboardAction(
                graph=self.graph, payload=payload, paste_x=paste_x, paste_y=paste_y
            )
            self.history_manager.add_action(action)
            logger.info(f"Pasted {len(payload.get('nodes', {}))} nodes at ({paste_x}, {paste_y})")
            return (action.new_node_ids, action.new_edge_ids)
        except Exception as e:
            logger.error(f"Error pasting clipboard: {e}")
            return None

    def move_nodes(self, nodes: List[str], deltaX: float, deltaY: float) -> bool:
        """
        Move multiple nodes by delta amounts.

        Args:
            nodes: List of node IDs to move
            deltaX: Delta X amount to move all nodes
            deltaY: Delta Y amount to move all nodes

        Returns:
            True if nodes were moved, False otherwise
        """
        if not nodes:
            return False

        try:
            # Create and execute delta move action
            action = MoveNodesAction(self.graph, nodes, deltaX, deltaY)
            self.history_manager.add_action(action)

            logger.info(f"Moved {len(nodes)} nodes by delta ({deltaX}, {deltaY})")
            return True

        except Exception as e:
            logger.error(f"Error moving nodes by delta: {e}")
            return False

    def move_nodes_to(self, positions: Dict[str, Dict[str, float]]) -> bool:
        """Move nodes to absolute positions (e.g. from a snapped drag)."""
        if not positions:
            return False
        try:
            action = MoveNodesToAction(self.graph, positions)
            self.history_manager.add_action(action)
            logger.info(f"Moved {len(positions)} nodes to absolute positions")
            return True
        except Exception as e:
            logger.error(f"Error moving nodes to absolute positions: {e}")
            return False

    def set_property(self, node_id: str, name: str, value: Any) -> bool:
        """Set a port value or settings-bag field on a node, undo-recorded.

        ``name`` resolves to a port id first, then a settings-bag field name.
        Returns False (without mutating) if the node or name is unknown.
        """
        try:
            action = SetPropertyAction(self.graph, node_id, name, value)
            # Pre-validate: the history manager swallows execute() failures, so
            # resolve the target up front to distinguish a real set from a miss.
            action._resolve()
            self.history_manager.add_action(action)
            logger.info(f"Set property {name!r} on node {node_id}")
            return True
        except Exception as e:
            logger.error(f"Error setting property {name!r} on {node_id}: {e}")
            return False

    def remove_elements(self, nodes: List[str], edges: List[str]) -> bool:
        """
        Remove multiple nodes and connections in a single operation.

        Args:
            nodes: List of node IDs to remove
            connections: List of connection UUIDs to remove

        Returns:
            True if elements were removed, False otherwise
        """
        if not nodes and not edges:
            return False

        # Validate nodes exist
        missing_nodes = [node_id for node_id in nodes if node_id not in self.graph.node_wrappers]
        if missing_nodes:
            logger.warning(f"Nodes not found for removal: {missing_nodes}")
            return False

        # Validate connections exist
        missing_edges = [conn_id for conn_id in edges if not self.graph.get_edge_wrapper(conn_id)]
        if missing_edges:
            logger.warning(f"Connections not found for removal: {missing_edges}")
            return False

        try:
            # Create and execute remove elements action
            action = RemoveElementsAction(self.graph, nodes, edges)
            self.history_manager.add_action(action)

            total_count = len(nodes) + len(edges)
            logger.info(f"Removed {total_count} elements ({len(nodes)} nodes, {len(edges)} connections)")
            return True

        except Exception as e:
            logger.error(f"Error removing elements: {e}")
            return False

    def get_node_wrapper(self, node_id: str) -> Optional[NodeWrapper]:
        """Get a node wrapper by ID."""
        return self.graph.get_node_wrapper(node_id)

    def list_node_wrappers(self) -> List[NodeWrapper]:
        """Get a list of all node wrappers in the graph."""
        return list(self.graph.node_wrappers.values())

    def get_available_node_regkeys(self) -> List[str]:
        """Get a list of all available node types from the factory."""
        return self._node_factory.node_registry.list_names()

    # =============================================================================
    # CONNECTION OPERATIONS
    # =============================================================================

    def create_edge(self, source_node_id: str, outlet_pin: str, sink_node_id: str, inlet_pin: str) -> bool:
        """
        Create a connection between two nodes.

        Args:
            source_node_id: ID of the source node
            outlet_pin: Name of the output pin
            sink_node_id: ID of the sink node
            inlet_pin: Name of the input pin

        Returns:
            True if connection was created, False otherwise
        """
        try:
            # Create and execute action using graph-managed pattern
            action = AddEdgeAction(
                graph=self.graph,
                source_node_id=source_node_id,
                outlet_pin_id=outlet_pin,
                sink_node_id=sink_node_id,
                inlet_pin_id=inlet_pin,
            )
            self.history_manager.add_action(action)

            logger.info(f"Created connection {source_node_id}:{outlet_pin} -> {sink_node_id}:{inlet_pin}")
            return True

        except Exception as e:
            logger.error(f"Error creating connection: {e}")
            return False

    def split_edge_with_reroute(
        self,
        edge_id: str,
        position: Tuple[float, float],
        registry_key: str,
    ) -> Optional[str]:
        """Split a data edge and insert a reroute node at ``position``.

        Removes the original edge, creates the port-less reroute node
        (``registry_key``), adds its typed inlet/outlet (ids owned by the split
        action), and wires it in between — all as one undoable operation (see
        ``SplitEdgeWithRerouteAction``).

        The reroute node type is supplied by the caller (the graph editor
        discovers it via the registry's ``_is_reroute`` flag) so the core stays
        independent of any specific library. Returns the new reroute node id, or
        ``None`` on failure.
        """
        try:
            action = SplitEdgeWithRerouteAction(
                graph=self.graph,
                edge_id=edge_id,
                position=position,
                registry_key=registry_key,
            )
            self.history_manager.add_action(action)
            logger.info(f"Split edge {edge_id} with reroute {action.reroute_node_id}")
            return action.reroute_node_id
        except Exception as e:
            logger.error(f"Error splitting edge {edge_id} with reroute: {e}")
            return None

    def dissolve_reroute(self, node_id: str) -> bool:
        """Dissolve a reroute node, bridging upstream to all downstream sinks.

        Removes the reroute node and reconnects upstream directly to each
        downstream sink — all as one undoable operation (see
        ``DissolveRerouteAction``).

        Returns ``True`` on success, ``False`` on failure.
        """
        try:
            action = DissolveRerouteAction(graph=self.graph, node_id=node_id)
            self.history_manager.add_action(action)
            logger.info(f"Dissolved reroute node {node_id}")
            return True
        except Exception as e:
            logger.error(f"Error dissolving reroute {node_id}: {e}")
            return False

    def list_edges(self) -> List[EdgeWrapper]:
        """Get a list of all connections in the graph."""
        return list(self.graph.edge_wrappers.values())

    # =============================================================================
    # HISTORY OPERATIONS
    # =============================================================================

    def undo(self) -> bool:
        """Perform an undo operation. Returns True if undo was performed."""
        if self.history_manager.can_undo():
            try:
                result = self.history_manager.undo()
                if result:
                    logger.info("Undo performed")
                return result
            except Exception as e:
                logger.error(f"Error during undo: {e}")
                return False
        logger.warning("Nothing to undo")
        return False

    def redo(self) -> bool:
        """Perform a redo operation. Returns True if redo was performed."""
        if self.history_manager.can_redo():
            try:
                result = self.history_manager.redo()
                if result:
                    logger.info("Redo performed")
                return result
            except Exception as e:
                logger.error(f"Error during redo: {e}")
                return False
        logger.warning("Nothing to redo")
        return False

    def can_undo(self) -> bool:
        """Check if undo is available."""
        return self.history_manager.can_undo()

    def can_redo(self) -> bool:
        """Check if redo is available."""
        return self.history_manager.can_redo()

    def add_fence(self) -> None:
        """Add a fence to group operations."""
        self.history_manager.add_fence()

    def is_valid(self) -> bool:
        """Check if the editor is in a valid state."""
        return self.graph is not None
