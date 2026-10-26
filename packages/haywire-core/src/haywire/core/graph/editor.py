import logging
from typing import Any, Dict, List, Optional, Sequence, Tuple, cast
from haywire.core.errors import report_failure
from haywire.core.graph.base import BaseGraph
from haywire.core.edge.edge_wrapper import EdgeWrapper
from haywire.core.graph.setting_owner import SettingOwner
from haywire.core.graph.stacking import Restack, restacked
from haywire.core.node.layout import PATCH, LayoutChannel
from haywire.core.node.node_wrapper import NodeWrapper
from haywire.core.node.factory import NodeFactory
from haywire.core.types import Propagation
from haywire.core.undo.interfaces import IAction, IHistoryManager
from haywire.core.undo.history_manager import HistoryManager
from haywire.core.undo.config import UndoConfig
from haywire.core.undo.actions.graph_actions import (
    ResetSettingsAction,
    SetSettingsAction,
    stage_placement,
    AddNodeAction,
    MoveNodesAction,
    MoveNodesToAction,
    RemoveElementsAction,
    RemovePortAction,
    PromoteSettingAction,
    AddEdgeAction,
    PasteClipboardAction,
    SplitEdgeWithRerouteAction,
    DissolveRerouteAction,
    ClearMacroOriginAction,
    CollapseToGraphNodeAction,
    DetachPlacementFromMacroAction,
    ExpandGraphNodeAction,
    PromoteGroupToMacroAction,
    ReorderPortsAction,
    ResetSettingAction,
    SetEdgePropagationAction,
    SetPortMetadataAction,
    SetPropertyAction,
    SetSettingAction,
    SetStageMembershipAction,
    RestackNodesAction,
)

logger = logging.getLogger(__name__)


class Editor:
    """Undo-recorded graph operations: create, move, connect, remove, paste, undo and redo.

    Every mutating method records one action on the history manager and
    reports a failure by returning ``False`` or ``None``; it does not raise.
    A value write given ``record=False`` applies its action without recording
    it, and fences the history after it.
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
        #: Edges removed by the most recent ``promote_to_macro`` call only (0 unless it dropped any).
        self.last_promotion_dropped_edges = 0
        self.history_manager: IHistoryManager = history_manager or HistoryManager(
            undo_config or UndoConfig()
        )
        graph.set_history(self.history_manager)
        self._node_factory = node_factory

    # =============================================================================
    # NODE OPERATIONS
    # =============================================================================

    def create_wrapper(
        self,
        registry_key: str,
        position: Tuple[float, float] = (3750, 3750),
        channel: LayoutChannel = PATCH,
        patch_fallback: Optional[Tuple[float, float]] = None,
    ) -> Optional[NodeWrapper]:
        """Create a node of type ``registry_key`` as one undoable action.

        Args:
            position: ``(x, y)`` in canvas coordinates.
            channel: The layout channel of the canvas the node is made in. On the stage channel
                the node is created on stage at ``position``, and in the patch near the nodes
                already on stage.
            patch_fallback: Stage channel only. The patch position when no node is on stage yet
                (the patch canvas's viewport centre); see ``patch_position_for_stage``.

        Returns:
            The created wrapper, or ``None`` if creation failed.
        """
        try:
            if channel.stage:
                action = AddNodeAction(
                    graph=self.graph,
                    registry_key=registry_key,
                    props=stage_placement(self.graph, channel, position, patch_fallback),
                )
            else:
                action = AddNodeAction(graph=self.graph, registry_key=registry_key, position=position)
            if not self.history_manager.add_action(action):
                return None

            logger.info(f"Created node of type {registry_key} at {position}")

            return action.wrapper

        except Exception as e:
            logger.error(f"Error creating node of type {registry_key}: {e}")
            return None

    def paste_clipboard(
        self,
        payload: Dict[str, Any],
        paste_x: float,
        paste_y: float,
        channel: LayoutChannel = PATCH,
        patch_anchor: Optional[Tuple[float, float]] = None,
        patch_fallback: Optional[Tuple[float, float]] = None,
        stage_anchor: Optional[Tuple[float, float]] = None,
    ) -> Optional[Tuple[List[str], List[str]]]:
        """Paste a clipboard payload at canvas position ``(paste_x, paste_y)`` as one undoable action.

        On the stage ``channel`` the pasted nodes land on stage, keeping their relative layout
        in both views. Their patch anchor is ``patch_anchor`` (a duplicate passes its own), else
        derived from the paste point with ``patch_fallback``.
        In a patch canvas the pasted nodes that are on stage keep their stage layout too,
        anchored at ``stage_anchor`` (a duplicate passes its own), else near the nodes already
        on stage.

        A node type the registry doesn't know pastes as a placeholder error node.

        Returns:
            ``(new_node_ids, new_edge_ids)`` for the pasted elements, or
            ``None`` if the paste failed.
        """
        try:
            action = PasteClipboardAction(
                graph=self.graph,
                payload=payload,
                paste_x=paste_x,
                paste_y=paste_y,
                channel=channel,
                patch_anchor=patch_anchor,
                patch_fallback=patch_fallback,
                stage_anchor=stage_anchor,
            )
            if not self.history_manager.add_action(action):
                return None
            logger.info(f"Pasted {len(payload.get('nodes', {}))} nodes at ({paste_x}, {paste_y})")
            return (action.new_node_ids, action.new_edge_ids)
        except Exception as e:
            logger.error(f"Error pasting clipboard: {e}")
            return None

    def move_nodes(
        self, nodes: List[str], deltaX: float, deltaY: float, channel: LayoutChannel = PATCH
    ) -> bool:
        """Move every node in ``nodes`` by ``(deltaX, deltaY)`` in ``channel`` as one undoable action.

        Returns:
            ``False`` if ``nodes`` is empty or the move failed, otherwise ``True``.
        """
        if not nodes:
            return False

        try:
            action = MoveNodesAction(self.graph, nodes, deltaX, deltaY, channel)
            if not self.history_manager.add_action(action):
                return False

            logger.info(f"Moved {len(nodes)} nodes by delta ({deltaX}, {deltaY})")
            return True

        except Exception as e:
            logger.error(f"Error moving nodes by delta: {e}")
            return False

    def move_nodes_to(self, positions: Dict[str, Dict[str, float]], channel: LayoutChannel = PATCH) -> bool:
        """Move nodes to absolute positions in ``channel`` as one undoable action.

        Args:
            positions: Node ID to ``{"x": ..., "y": ...}`` in canvas coordinates.

        Returns:
            ``False`` if ``positions`` is empty or the move failed, otherwise ``True``.
        """
        if not positions:
            return False
        try:
            action = MoveNodesToAction(self.graph, positions, channel)
            if not self.history_manager.add_action(action):
                return False
            logger.info(f"Moved {len(positions)} nodes to absolute positions")
            return True
        except Exception as e:
            logger.error(f"Error moving nodes to absolute positions: {e}")
            return False

    def add_to_stage(self, node_ids: List[str]) -> bool:
        """Put nodes on the graph's stage as one undoable action.

        Each node is placed below the nodes already on stage, in patch order. Nodes that are
        unknown or already on stage are skipped.

        Returns:
            ``False`` if no node changes or the action failed, otherwise ``True``.
        """
        return self._set_stage_membership(node_ids, True)

    def remove_from_stage(self, node_ids: List[str]) -> bool:
        """Take nodes off the graph's stage as one undoable action, keeping their stage rectangle.

        Nodes that are unknown or already off stage are skipped.

        Returns:
            ``False`` if no node changes or the action failed, otherwise ``True``.
        """
        return self._set_stage_membership(node_ids, False)

    def restack_nodes(self, node_ids: List[str], how: Restack, channel: LayoutChannel = PATCH) -> bool:
        """Change the stacking order of nodes in ``channel``'s view as one undoable action.

        Ids that are unknown or not in the view are ignored. See ``Restack`` for the verbs.

        Returns:
            ``False`` if the order does not change or the action failed, otherwise ``True``.

        Example::

            editor.restack_nodes(["n1", "n2"], Restack.FRONT)            # patch view
            editor.restack_nodes(["n1"], Restack.BACKWARD, STAGE)        # stage view
        """
        changes = restacked(self.graph, node_ids, how, channel)
        if not changes:
            return False
        try:
            action = RestackNodesAction(self.graph, changes, channel)
            if not self.history_manager.add_action(action):
                return False
            logger.info(f"Restacked {len(node_ids)} nodes ({how.value}, {channel.name})")
            return True
        except Exception as e:
            logger.error(f"Error changing stacking order: {e}")
            return False

    def _set_stage_membership(self, node_ids: List[str], on_stage: bool) -> bool:
        changing = []
        for node_id in dict.fromkeys(node_ids):
            wrapper = self.graph.get_node_wrapper(node_id)
            if wrapper and wrapper.node and wrapper.node.props.on_stage != on_stage:
                changing.append(node_id)
        if not changing:
            return False
        try:
            action = SetStageMembershipAction(self.graph, changing, on_stage)
            if not self.history_manager.add_action(action):
                return False
            logger.info(f"{'Added' if on_stage else 'Removed'} {len(changing)} nodes on the stage")
            return True
        except Exception as e:
            logger.error(f"Error changing stage membership: {e}")
            return False

    def set_property(
        self,
        node_id: str,
        name: str,
        value: Any,
        prefer_setting: bool = False,
        *,
        record: bool = True,
        merge_owner: object | None = None,
    ) -> bool:
        """Set a port value or settings-bag field on a node; see ``SetPropertyAction``.

        ``name`` resolves to a port id first, then a settings-bag field name;
        ``prefer_setting=True`` flips that order, for a ``name`` that must mean
        the settings field even though a port shares it. Returns ``False``
        without mutating anything if the node or the name is unknown, or the port
        holds no own value (a pooled inlet or an ``ADD`` slot).

        Args:
            record: Record the write as an undo step. ``False`` applies it and
                adds a fence, so it joins no undo step.
            merge_owner: The session token a run of writes belongs to; writes with the
                same token amend one step while the run lasts. ``None`` never merges.
                A write that changes nothing adds no step and no fence.
        """
        try:
            action = SetPropertyAction(self.graph, node_id, name, value, prefer_setting=prefer_setting)
            # Resolve up front so a miss is refused before the action runs.
            action._resolve()
        except Exception as e:
            logger.error(f"Error setting property {name!r} on {node_id}: {e}")
            return False
        if not self._apply_value(action, record, merge_owner):
            return False
        # An unrecorded write arrives per widget tick, so it logs at debug.
        (logger.info if record else logger.debug)(f"Set property {name!r} on node {node_id}")
        return True

    def set_setting(
        self,
        owner: SettingOwner,
        name: str,
        value: Any,
        *,
        record: bool = True,
        merge_owner: object | None = None,
    ) -> bool:
        """Set one settings field on a node, the graph or an edge; see ``SetSettingAction``.

        Args:
            record: Record the write as an undo step. ``False`` applies it and
                adds a fence, so it joins no undo step.
            merge_owner: As for ``set_property``.

        Returns:
            ``False`` without writing if ``owner`` does not resolve in this graph or
            its bag has no field ``name``.
        """
        return self._apply_value(SetSettingAction(self.graph, owner, name, value), record, merge_owner)

    def reset_setting(
        self, owner: SettingOwner, name: str, *, record: bool = True, merge_owner: object | None = None
    ) -> bool:
        """Reset one settings field to the value it takes when not set locally; see ``ResetSettingAction``.

        Args:
            record: As for ``set_setting``.
            merge_owner: As for ``set_property``.

        Returns:
            ``False`` without writing if ``owner`` does not resolve in this graph or
            its bag has no field ``name``.
        """
        return self._apply_value(ResetSettingAction(self.graph, owner, name), record, merge_owner)

    def set_settings(
        self,
        owners: Sequence[SettingOwner],
        name: str,
        value: Any,
        *,
        record: bool = True,
        merge_owner: object | None = None,
    ) -> bool:
        """Set one settings field on every owner as one step; see ``SetSettingsAction``.

        Args:
            record: As for ``set_setting``.
            merge_owner: As for ``set_property``; a run amends every child of the step.

        Returns:
            ``False`` without writing if an owner does not resolve or lacks the field.
        """
        return self._apply_value(SetSettingsAction(self.graph, owners, name, value), record, merge_owner)

    def reset_settings(
        self,
        owners: Sequence[SettingOwner],
        name: str,
        *,
        record: bool = True,
        merge_owner: object | None = None,
    ) -> bool:
        """Reset one settings field on every owner as one step; see ``ResetSettingsAction``.

        Args:
            record: As for ``set_setting``.
            merge_owner: As for ``set_property``.

        Returns:
            ``False`` without writing if an owner does not resolve or lacks the field.
        """
        return self._apply_value(ResetSettingsAction(self.graph, owners, name), record, merge_owner)

    def reorder_ports(self, node_id: str, ordered_ids: List[str]) -> bool:
        """Reorder one sibling group of a node's ports as one undoable action.

        Args:
            ordered_ids: Port ids of the group, in display order; see ``NodeData.reorder_ports``.

        Returns:
            ``False`` if the node is unknown or the reorder failed.
        """
        return self._apply(ReorderPortsAction(self.graph, node_id, ordered_ids), record=True)

    def set_edge_propagation(self, edge_id: str, propagation: Propagation) -> bool:
        """Change an edge's propagation mode as one undoable action.

        Returns:
            ``False`` if the edge is unknown, or refuses the mode (its wire type
            does not allow it, or the edge is locked to another).
        """
        return self._apply(SetEdgePropagationAction(self.graph, edge_id, propagation), record=True)

    def _apply_value(self, action: IAction, record: bool, merge_owner: object | None) -> bool:
        """Run a value write: recorded (and merged) on the history, or applied and fenced if it changed.

        A write that changes nothing adds no step and no fence. ``False`` if it raised.
        """
        try:
            if record:
                return self.history_manager.add_value_action(action, merge_owner)
            action.execute()
            if cast(Any, action).changed:
                self.history_manager.add_fence()
            return True
        except Exception as e:
            self._report_apply_failure(e, action)
            return False

    def _report_apply_failure(self, exc: Exception, action: IAction) -> None:
        """Record a failed edit in the error ledger; a ``Refusal`` is not recorded."""
        context: Dict[str, Any] = {"graph_id": self.graph.graph_id, "action": action.description}
        node_id = getattr(action, "node_id", None)
        if node_id:
            context["node_id"] = node_id
        report_failure(exc, operation="Apply edit", **context)

    def _apply(self, action: IAction, record: bool) -> bool:
        """Run ``action``: recorded on the history, or applied and fenced; ``False`` if it raised."""
        try:
            if record:
                return self.history_manager.add_action(action)
            action.execute()
            self.history_manager.add_fence()
            return True
        except Exception as e:
            self._report_apply_failure(e, action)
            return False

    def reset_nodes(self, node_ids: List[str]) -> bool:
        """Rebuild the nodes through ``init()`` as one undo step; Undo puts them back exactly.

        Returns:
            ``False`` without changing anything when *node_ids* is empty or names
            a node the graph does not have.
        """
        from haywire.core.undo.actions.graph_actions import RebuildNodesAction, describe_rebuild

        wrappers = [self.graph.get_node_wrapper(node_id) for node_id in node_ids]
        if not wrappers or any(wrapper is None for wrapper in wrappers):
            return False
        try:
            labels = [w.node.identity.label for w in wrappers if w is not None]
            description = describe_rebuild("Reset", labels)
            action = RebuildNodesAction.capture(self.graph, node_ids, description)
        except Exception as e:
            report_failure(e, operation="Reset nodes", graph_id=self.graph.graph_id, node_ids=node_ids)
            return False
        return self.history_manager.add_action(action)

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
            # Pre-flight so a refusal returns its reason; a failure inside the
            # action itself only reports that it failed.
            action._port()
            added = self.history_manager.add_action(action)
        except Exception as e:
            logger.error(f"Error editing port {port_id!r} on {node_id}: {e}")
            return False, str(e)
        if not added:
            return False, f"Port {port_id!r} could not be edited"
        logger.info(f"Edited port {port_id!r} on node {node_id}")
        return True, None

    def promote_setting(self, node_id: str, accessor: str, field: str, direction: Any) -> bool:
        """Promote a node setting to a pin of *direction*, undo-recorded.

        Returns:
            ``False`` without promoting anything for an unknown node or setting, or a
            direction the setting is not eligible for.
        """
        try:
            action = PromoteSettingAction(self.graph, node_id, accessor, field, direction)
            return self.history_manager.add_action(action)
        except Exception as e:
            logger.error(f"Error promoting {accessor}.{field} on {node_id}: {e}")
            return False

    def remove_port(self, node_id: str, port_id: str) -> bool:
        """Remove a port the user brought into being (promoted or resolved), undo-recorded.

        Returns:
            ``False`` without removing anything for an unknown node or port, or one
            the node's author declared.
        """
        try:
            action = RemovePortAction(self.graph, node_id, port_id)
            return self.history_manager.add_action(action)
        except Exception as e:
            logger.error(f"Error removing port {port_id!r} on {node_id}: {e}")
            return False

    def remove_elements(self, nodes: List[str], edges: List[str], release_pins: bool = True) -> bool:
        """Remove the given nodes and edges as one undoable action.

        A Subgraph's two boundary nodes are dropped from ``nodes`` rather than
        removed: they are the Subgraph's interface, not its content, so deleting
        everything inside a Group empties it and leaves the interface standing.
        A selection of nothing but boundary nodes therefore removes nothing.

        Args:
            release_pins: Let the nodes the removed edges ended on drop the ports the
                edges leave bare. Pass ``False`` when the edge is about to be replaced,
                as in a reconnect drag, which starts from one of those ports.

        Returns:
            ``False`` without removing anything if both lists are empty, if
            everything named was filtered out, if either list names an
            element the graph doesn't have, or if the removal failed.
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
            action = RemoveElementsAction(self.graph, nodes, edges, release_pins=release_pins)
            if not self.history_manager.add_action(action):
                return False

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
            ``True`` if the edge was created, ``False`` if the graph refused it
            (an edge already links the two pins, in either direction) or the
            creation failed.
        """
        try:
            action = AddEdgeAction(
                graph=self.graph,
                source_node_id=source_node_id,
                outlet_pin_id=outlet_pin,
                sink_node_id=sink_node_id,
                inlet_pin_id=inlet_pin,
            )
            if not self.history_manager.add_action(action):
                return False

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
        channel: LayoutChannel = PATCH,
        patch_fallback: Optional[Tuple[float, float]] = None,
    ) -> Optional[str]:
        """Split a data edge and insert a reroute node of type ``registry_key`` at ``position``.

        Removes the original edge, creates the port-less reroute node, adds its
        typed inlet and outlet, and wires it in between — all as one undoable
        operation (see ``SplitEdgeWithRerouteAction``).

        Args:
            registry_key: The reroute node type to instantiate, chosen by the
                caller so the core needs no specific library.
            channel: The layout channel of the canvas; on the stage channel the reroute
                node lands on stage.
            patch_fallback: Stage channel only; see ``create_wrapper``.

        Returns:
            The new reroute node's id, or ``None`` on failure.
        """
        try:
            action = SplitEdgeWithRerouteAction(
                graph=self.graph,
                edge_id=edge_id,
                position=position,
                registry_key=registry_key,
                channel=channel,
                patch_fallback=patch_fallback,
            )
            if not self.history_manager.add_action(action):
                return None
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
            if not self.history_manager.add_action(action):
                return False
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
            if not self.history_manager.add_action(action):
                return (None, "The selection could not be collapsed")
            logger.info(f"Collapsed {len(node_ids)} nodes into subgraph {action.subgraph_key}")
            return (action.card_node_id, None)
        except Exception as e:
            logger.error(f"Error collapsing selection: {e}")
            return (None, str(e))

    def promote_to_macro(
        self,
        node_id: str,
        macro_registry_key: str,
        description: str | None = None,
        drop_unmatched_edges: bool = False,
    ) -> Tuple[Optional[str], Optional[str]]:
        """Swap the Group on ``node_id`` for a placement of ``macro_registry_key``.

        One undoable operation. The macro file must already be written and
        registered — this only exchanges the cards, so undo restores the Group
        and leaves the file alone.

        Fenced on both sides: auto-grouping would otherwise fold the swap into
        whatever the user did just before, and a promotion that undid the
        preceding collapse along with itself would take back work the user
        never asked to reverse.

        Args:
            description: The undo-history name of the swap; ``None`` names it
                "Save new Macro".
            drop_unmatched_edges: Leave an edge removed when the placement has
                no pin for it, instead of re-attaching it. Undo restores it.
                ``last_promotion_dropped_edges`` reports how many.

        Returns:
            ``(placement_node_id, None)`` on success, or ``(None, reason)``
            when the swap was refused, phrased to be shown to the user.
        """
        self.last_promotion_dropped_edges = 0
        try:
            action = PromoteGroupToMacroAction(
                graph=self.graph,
                node_id=node_id,
                macro_registry_key=macro_registry_key,
                description=description,
                drop_unmatched_edges=drop_unmatched_edges,
            )
        except ValueError as e:
            logger.info(f"Save as macro refused: {e}")
            return (None, str(e))

        try:
            self.history_manager.add_fence()
            added = self.history_manager.add_action(action)
            self.history_manager.add_fence()
            if not added:
                return (None, "The Group could not be saved as a macro")
            self.last_promotion_dropped_edges = action.dropped_edge_count
            logger.info(f"Saved Group {node_id} as macro '{macro_registry_key}'")
            return (action.placement_node_id, None)
        except Exception as e:
            logger.error(f"Error saving Group {node_id} as a macro: {e}")
            return (None, str(e))

    def detach_placement_from_macro(
        self,
        node_id: str,
        card_registry_key: str,
    ) -> Tuple[Optional[str], Optional[str]]:
        """Swap the macro placement on ``node_id`` for a Group holding its interior.

        One undoable operation. The macro file and every other placement of it
        are untouched: this card alone stops tracking the template, and its
        interior becomes part of this graph's file.

        Fenced on both sides, for the same reason ``promote_to_macro`` is:
        auto-grouping would otherwise fold the swap into whatever preceded it.

        Args:
            card_registry_key: The Graph-node class to build the Group's card
                from, which the caller discovers through the registry's
                ``_is_graph_node`` flag — so the core names no library's node.

        Returns:
            ``(card_node_id, None)`` on success, or ``(None, reason)`` when the
            detach was refused, phrased to be shown to the user.
        """
        try:
            action = DetachPlacementFromMacroAction(
                graph=self.graph,
                node_id=node_id,
                card_registry_key=card_registry_key,
            )
        except ValueError as e:
            logger.info(f"Detach refused: {e}")
            return (None, str(e))

        try:
            self.history_manager.add_fence()
            added = self.history_manager.add_action(action)
            self.history_manager.add_fence()
            if not added:
                return (None, "The placement could not be detached")
            logger.info(f"Detached placement {node_id} into Group {action.subgraph_key}")
            return (action.card_node_id, None)
        except Exception as e:
            logger.error(f"Error detaching placement {node_id}: {e}")
            return (None, str(e))

    def forget_macro_origin(self, node_id: str) -> bool:
        """Turn the modified instance on ``node_id`` into a plain Group, as one undoable operation.

        The card and its interior stay as they are; the Group stops recording the
        macro it was copied from, so Revert to Macro and Update Macro no longer
        apply to it.

        Returns ``True`` on success, ``False`` if the node is not a Group with a
        macro origin, or if the change failed.
        """
        try:
            action = ClearMacroOriginAction(graph=self.graph, node_id=node_id)
        except ValueError as e:
            logger.info(f"Forget origin refused: {e}")
            return False
        try:
            if not self.history_manager.add_action(action):
                return False
            logger.info(f"Forgot the macro origin of Group {node_id}")
            return True
        except Exception as e:
            logger.error(f"Error forgetting the macro origin of {node_id}: {e}")
            return False

    def expand_group(self, node_id: str) -> bool:
        """Expand the Group on ``node_id`` back into this graph as one undoable operation.

        Returns ``True`` on success, ``False`` if the node is not a Graph-node
        with a Subgraph bound, or if the expansion failed.
        """
        try:
            action = ExpandGraphNodeAction(graph=self.graph, node_id=node_id)
            if not self.history_manager.add_action(action):
                return False
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
