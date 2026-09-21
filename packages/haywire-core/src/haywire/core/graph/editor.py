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
    CollapseToGraphNodeAction,
    ExpandGraphNodeAction,
    PromoteGroupToMacroAction,
    SetPortMetadataAction,
    SetPropertyAction,
)

logger = logging.getLogger(__name__)


class Editor:
    """Undo-recorded graph operations: create, move, connect, remove, paste, undo and redo.

    Every mutating method records one action on the history manager and
    reports a failure by returning ``False`` or ``None``; it does not raise.
    """

    def __init__(
        self,
        graph: BaseGraph,
        node_factory: NodeFactory,
        undo_config: Optional[UndoConfig] = None,
        history_manager: Optional[IHistoryManager] = None,
    ):
        """Initialize the editor with the graph it edits.

        Args:
            undo_config: Undo history configuration for the history this editor
                creates. Defaults to ``UndoConfig()``; ignored when
                ``history_manager`` is given.
            history_manager: The history to record on. Defaults to one of this
                editor's own. Pass another editor's to put both editors' actions
                on a single stack: every action names the graph it mutates, so
                one history can span a graph and the Subgraphs inside it.

        Example::

            editor = Editor(graph, node_factory)
            # A Subgraph belongs to the same file, so it shares the history:
            # an edit inside it undoes in order with the edits around it.
            inner = Editor(definition, node_factory, history_manager=editor.history_manager)
        """
        self.graph: BaseGraph = graph
        self.history_manager: IHistoryManager = history_manager or HistoryManager(
            undo_config or UndoConfig()
        )
        self._node_factory = node_factory

    # =============================================================================
    # NODE OPERATIONS
    # =============================================================================

    def create_wrapper(
        self, registry_key: str, position: Tuple[float, float] = (3750, 3750)
    ) -> Optional[NodeWrapper]:
        """Create a node of type ``registry_key`` as one undoable action.

        Args:
            position: ``(x, y)`` in canvas coordinates.

        Returns:
            The created wrapper, or ``None`` if creation failed.
        """
        try:
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
        """Paste a clipboard payload at ``(paste_x, paste_y)`` as one undoable action.

        A node type the registry doesn't know pastes as a placeholder error node.

        Returns:
            ``(new_node_ids, new_edge_ids)`` for the pasted elements, or
            ``None`` on an unexpected error.
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
        """Move every node in ``nodes`` by ``(deltaX, deltaY)`` as one undoable action.

        Returns:
            ``False`` if ``nodes`` is empty or the move failed, otherwise ``True``.
        """
        if not nodes:
            return False

        try:
            action = MoveNodesAction(self.graph, nodes, deltaX, deltaY)
            self.history_manager.add_action(action)

            logger.info(f"Moved {len(nodes)} nodes by delta ({deltaX}, {deltaY})")
            return True

        except Exception as e:
            logger.error(f"Error moving nodes by delta: {e}")
            return False

    def move_nodes_to(self, positions: Dict[str, Dict[str, float]]) -> bool:
        """Move nodes to absolute positions as one undoable action.

        Args:
            positions: Node ID to ``{"x": ..., "y": ...}`` in canvas coordinates.

        Returns:
            ``False`` if ``positions`` is empty or the move failed, otherwise ``True``.
        """
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

    def set_property(self, node_id: str, name: str, value: Any, prefer_setting: bool = False) -> bool:
        """Set a port value or settings-bag field on a node, undo-recorded.

        ``name`` resolves to a port id first, then a settings-bag field name;
        ``prefer_setting=True`` flips that order, for a ``name`` that must mean
        the settings field even though a port shares it. Returns ``False``
        without mutating anything if the node or the name is unknown.
        """
        try:
            action = SetPropertyAction(self.graph, node_id, name, value, prefer_setting=prefer_setting)
            # Pre-validate: the history manager swallows execute() failures, so
            # resolve the target up front to distinguish a real set from a miss.
            action._resolve()
            self.history_manager.add_action(action)
            logger.info(f"Set property {name!r} on node {node_id}")
            return True
        except Exception as e:
            logger.error(f"Error setting property {name!r} on {node_id}: {e}")
            return False

    def set_port_metadata(self, node_id: str, port_id: str, **changes: Any) -> Tuple[bool, Optional[str]]:
        """Edit a port's label, description and/or default, undo-recorded.

        One call is one undo step, however many fields it carries, so a dialog
        applying all three reverts in one gesture. Only a ``RESOLVED`` port may
        be edited — see :class:`SetPortMetadataAction`.

        Args:
            **changes: Any of ``label``, ``description``, ``default``.

        Returns:
            ``(True, None)`` on success, otherwise ``(False, reason)`` with a
            message written to be shown to the user.
        """
        try:
            action = SetPortMetadataAction(self.graph, node_id, port_id, **changes)
            # Pre-flight for the same reason set_property does it: the history
            # manager swallows an execute() failure, so a refusal would look
            # like a silent no-op rather than a reported one.
            action._port()
            self.history_manager.add_action(action)
        except Exception as e:
            logger.error(f"Error editing port {port_id!r} on {node_id}: {e}")
            return False, str(e)
        if not action._executed:
            return False, f"Port {port_id!r} could not be edited"
        logger.info(f"Edited port {port_id!r} on node {node_id}")
        return True, None

    def remove_elements(self, nodes: List[str], edges: List[str]) -> bool:
        """Remove the given nodes and edges as one undoable action.

        A Subgraph's two boundary nodes are dropped from ``nodes`` rather than
        removed: they are the Subgraph's interface, not its content, so deleting
        everything inside a Group empties it and leaves the interface standing.
        A selection of nothing but boundary nodes therefore removes nothing.

        Returns:
            ``False`` without removing anything if both lists are empty, if
            everything named was filtered out, or if either list names an
            element the graph doesn't have.
        """
        if not nodes and not edges:
            return False

        nodes = [node_id for node_id in nodes if not self._is_boundary_node(node_id)]
        if not nodes and not edges:
            logger.info("Nothing to remove: a Subgraph's boundary nodes cannot be deleted")
            return False

        missing_nodes = [node_id for node_id in nodes if node_id not in self.graph.node_wrappers]
        if missing_nodes:
            logger.warning(f"Nodes not found for removal: {missing_nodes}")
            return False

        missing_edges = [conn_id for conn_id in edges if not self.graph.get_edge_wrapper(conn_id)]
        if missing_edges:
            logger.warning(f"Connections not found for removal: {missing_edges}")
            return False

        try:
            action = RemoveElementsAction(self.graph, nodes, edges)
            self.history_manager.add_action(action)

            total_count = len(nodes) + len(edges)
            logger.info(f"Removed {total_count} elements ({len(nodes)} nodes, {len(edges)} connections)")
            return True

        except Exception as e:
            logger.error(f"Error removing elements: {e}")
            return False

    def _is_boundary_node(self, node_id: str) -> bool:
        """Whether ``node_id`` names a Subgraph Input or Output in this graph."""
        wrapper = self.graph.get_node_wrapper(node_id)
        return wrapper is not None and wrapper.node.behavior.is_boundary_node

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
        """Connect ``outlet_pin`` on the source node to ``inlet_pin`` on the sink node.

        Returns:
            ``True`` if the edge was created, ``False`` otherwise.
        """
        try:
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
        """Split a data edge and insert a reroute node of type ``registry_key`` at ``position``.

        Removes the original edge, creates the port-less reroute node, adds its
        typed inlet and outlet, and wires it in between — all as one undoable
        operation (see ``SplitEdgeWithRerouteAction``).

        Args:
            registry_key: The reroute node type to instantiate, chosen by the
                caller so the core needs no specific library.

        Returns:
            The new reroute node's id, or ``None`` on failure.
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
        """Dissolve a reroute node, reconnecting its upstream source to every downstream sink.

        One undoable operation — see ``DissolveRerouteAction``. Returns
        ``True`` on success, ``False`` on failure.
        """
        try:
            action = DissolveRerouteAction(graph=self.graph, node_id=node_id)
            self.history_manager.add_action(action)
            logger.info(f"Dissolved reroute node {node_id}")
            return True
        except Exception as e:
            logger.error(f"Error dissolving reroute {node_id}: {e}")
            return False

    def collapse_to_group(
        self,
        node_ids: List[str],
        card_registry_key: str,
        input_registry_key: str,
        output_registry_key: str,
        label: str = "Group",
    ) -> Tuple[Optional[str], Optional[str]]:
        """Collapse ``node_ids`` into a Group as one undoable operation.

        The three registry keys name the Graph-node and boundary-node classes,
        which the caller discovers through the registry's ``_is_subgraph_input``
        / ``_is_subgraph_output`` flags and the Graph-node's own key — so the
        core names no library's node.

        Returns:
            ``(card_node_id, None)`` on success, or ``(None, reason)`` when the
            collapse was refused — a non-convex selection names the intervening
            nodes in ``reason``, which is written to be shown to the user.
        """
        try:
            action = CollapseToGraphNodeAction(
                graph=self.graph,
                node_ids=node_ids,
                card_registry_key=card_registry_key,
                input_registry_key=input_registry_key,
                output_registry_key=output_registry_key,
                label=label,
            )
        except ValueError as e:
            logger.info(f"Collapse refused: {e}")
            return (None, str(e))

        try:
            self.history_manager.add_action(action)
            logger.info(f"Collapsed {len(node_ids)} nodes into subgraph {action.subgraph_key}")
            return (action.card_node_id, None)
        except Exception as e:
            logger.error(f"Error collapsing selection: {e}")
            return (None, str(e))

    def promote_to_macro(
        self,
        node_id: str,
        macro_registry_key: str,
    ) -> Tuple[Optional[str], Optional[str]]:
        """Swap the Group on ``node_id`` for a placement of ``macro_registry_key``.

        One undoable operation. The macro file must already be written and
        registered — this only exchanges the cards, so undo restores the Group
        and leaves the file alone.

        Fenced on both sides: auto-grouping would otherwise fold the swap into
        whatever the user did just before, and a promotion that undid the
        preceding collapse along with itself would take back work the user
        never asked to reverse.

        Returns:
            ``(placement_node_id, None)`` on success, or ``(None, reason)``
            when the swap was refused, phrased to be shown to the user.
        """
        try:
            action = PromoteGroupToMacroAction(
                graph=self.graph,
                node_id=node_id,
                macro_registry_key=macro_registry_key,
            )
        except ValueError as e:
            logger.info(f"Promotion refused: {e}")
            return (None, str(e))

        try:
            self.history_manager.add_fence()
            self.history_manager.add_action(action)
            self.history_manager.add_fence()
            logger.info(f"Promoted Group {node_id} to macro '{macro_registry_key}'")
            return (action.placement_node_id, None)
        except Exception as e:
            logger.error(f"Error promoting Group {node_id}: {e}")
            return (None, str(e))

    def expand_group(self, node_id: str) -> bool:
        """Expand the Group on ``node_id`` back into this graph as one undoable operation.

        Returns ``True`` on success, ``False`` if the node is not a Graph-node
        with a Subgraph bound, or if the expansion failed.
        """
        try:
            action = ExpandGraphNodeAction(graph=self.graph, node_id=node_id)
            self.history_manager.add_action(action)
            logger.info(f"Expanded Group {node_id}")
            return True
        except Exception as e:
            logger.error(f"Error expanding Group {node_id}: {e}")
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
