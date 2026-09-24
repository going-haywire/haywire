"""
Graph-specific actions for the Haywire undo system.

This module contains actions that operate on the graph structure,
including node and edge manipulation, positioning, and selection.
"""

import copy
import logging
from typing import Any, Optional, Dict, List, Tuple
from dataclasses import dataclass

from ...node import NodeWrapper
from ...graph.base import BaseGraph
from ...edge.edge_wrapper import EdgeWrapper
from ...graph.utils.node_remap import remap_node_ids
from ..base_action import ActionBase, CompositeAction
from ..interfaces import IAction

logger = logging.getLogger(__name__)

#: Store key a Graph-node holds its Subgraph key under. Named by string so the
#: core never imports the card's class.
SUBGRAPH_KEY = "subgraph_key"

# Default port ids the split action stamps onto a reroute node. The reroute is
# port-less until split; these ids are an implementation detail of the split
# (the node discovers whatever it is given via introspection), so they live here
# and are NOT part of the public split API.
_REROUTE_INLET_ID = "in"
_REROUTE_OUTLET_ID = "out"


class AddNodeAction(ActionBase):
    """Action for adding a node to the graph."""

    def __init__(
        self,
        graph: BaseGraph,
        registry_key: str,
        position: Tuple[float, float] = (3750, 3750),
        description: Optional[str] = None,
        node_data: Optional[Dict[str, Any]] = None,
        node_id: Optional[str] = None,
    ):
        """
        Initialize the add node action.

        Args:
            graph: The graph to add the node to
            registry_key: Node type to create
            position: Initial position for the node
            description: Optional description override
            node_data: Optional serialized node state to recreate the node
                from (used by paste). Only applied on first execution.
            node_id: Optional pre-minted node id to adopt on first execution
                (used by paste so remapped edges connect to the created node).
                Only applied on first execution.
        """
        super().__init__(description or f"Add node '{registry_key}'")
        self.graph = graph
        self.registry_key = registry_key
        self.position = position
        self.node_data = node_data
        self.node_id = node_id
        self.wrapper: "NodeWrapper | None" = None

        self.undo_wrapper: "NodeWrapper | None" = None

    def _execute_impl(self) -> None:
        """Add the node to the graph."""
        if self.wrapper is None:
            # First execution: Create new wrapper via graph
            self.wrapper = self.graph.create_node_wrapper(
                registry_key=self.registry_key,
                position=self.position,
                node_data=self.node_data,
                node_id=self.node_id,
            )
        else:
            # Redo: Re-add existing wrapper
            self.wrapper = self.graph.add_node_wrapper(self.wrapper)

        self.undo_wrapper = None

        if not self.wrapper:
            raise RuntimeError(f"Failed to create node wrapper '{self.registry_key}'")

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
        description: Optional[str] = None,
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
        super().__init__(description or f"Connect {source_node_id} to {sink_node_id}")
        self.graph = graph
        self.source_node_id = source_node_id
        self.outlet_port_id = outlet_pin_id
        self.outlet_pin_id = outlet_pin_id
        self.sink_node_id = sink_node_id
        self.inlet_port_id = inlet_pin_id
        self.inlet_pin_id = inlet_pin_id

        # Wrapper created during execute
        self.wrapper: Optional[EdgeWrapper] = None

        self.undo_wrapper: Optional[EdgeWrapper] = None

    def _execute_impl(self) -> None:
        """Add the edge to the graph."""
        if self.wrapper is None:
            # First execution: Create new wrapper via graph
            self.wrapper = self.graph.create_edge_wrapper(
                self.source_node_id, self.outlet_port_id, self.sink_node_id, self.inlet_port_id
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
            self.undo_wrapper = self.graph.remove_edge_wrapper(self.wrapper.edge_id)

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

    def __init__(
        self,
        graph: BaseGraph,
        nodes: List[str],
        deltaX: float,
        deltaY: float,
        description: Optional[str] = None,
    ):
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
            wrapper = self.graph.get_node_wrapper(node_id)
            if wrapper and wrapper.node:
                node = wrapper.node
                self.graph.move_node(
                    node_id,
                    node.props.posX + self.deltaX,
                    node.props.posY + self.deltaY,
                )

    def _undo_impl(self) -> None:
        """Move all nodes back by subtracting the delta amounts."""
        for node_id in self.nodes:
            wrapper = self.graph.get_node_wrapper(node_id)
            if wrapper and wrapper.node:
                node = wrapper.node
                self.graph.move_node(
                    node_id,
                    node.props.posX - self.deltaX,
                    node.props.posY - self.deltaY,
                )

    def can_merge(self, other) -> bool:
        """Check if this move can be merged with another delta move of the same nodes."""
        return (
            isinstance(other, MoveNodesAction)
            and set(other.nodes) == set(self.nodes)
            and super().can_merge(other)
        )

    def merge(self, other) -> Optional["MoveNodesAction"]:
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

        merged = MoveNodesAction(self.graph, self.nodes, combined_deltaX, combined_deltaY, description)
        # Both operands have already moved the nodes, and the combined delta
        # covers both. The merged action therefore enters history as already
        # executed: undoing it subtracts the full delta, and it must never be
        # re-executed on top of the movement that is already on the canvas.
        merged.mark_executed()

        return merged


class MoveNodesToAction(ActionBase):
    """Action for moving nodes to absolute positions (used by snapped drag)."""

    def __init__(
        self,
        graph: BaseGraph,
        positions: Dict[str, Dict[str, float]],
        description: Optional[str] = None,
    ):
        node_count = len(positions)
        if node_count == 1:
            node_id = next(iter(positions))
            super().__init__(description or f"Move node '{node_id}'")
        else:
            super().__init__(description or f"Move {node_count} nodes")

        self.graph = graph
        self.target_positions = positions  # {nodeId: {x, y}}
        # Capture originals at construction time so undo is exact.
        self.original_positions: Dict[str, Dict[str, float]] = {}
        for node_id in positions:
            wrapper = graph.get_node_wrapper(node_id)
            if wrapper and wrapper.node:
                node = wrapper.node
                self.original_positions[node_id] = {"x": node.props.posX, "y": node.props.posY}

    def _execute_impl(self) -> None:
        for node_id, pos in self.target_positions.items():
            self.graph.move_node(node_id, pos["x"], pos["y"])

    def _undo_impl(self) -> None:
        for node_id, pos in self.original_positions.items():
            self.graph.move_node(node_id, pos["x"], pos["y"])


class RemoveElementsAction(ActionBase):
    """
    Action for removing multiple nodes and connections in a single
    operation.
    """

    def __init__(
        self,
        graph: BaseGraph,
        nodes: Optional[List[str]] = None,
        edges: Optional[List[str]] = None,
        description: Optional[str] = None,
    ):
        """
        Initialize the remove elements action.

        Args:
            graph: The graph to remove elements from
            nodes: List of node IDs to remove
            edges: List of edge UUIDs to remove
            description: Optional description override
        """
        nodes = nodes or []
        edges = edges or []

        total_count = len(nodes) + len(edges)
        if total_count == 0:
            raise ValueError("Must specify at least one node or edge to remove")
        elif total_count == 1:
            if nodes:
                super().__init__(description or f"Remove node '{nodes[0]}'")
            else:
                super().__init__(description or "Remove edge")
        else:
            super().__init__(description or f"Remove {total_count} elements")

        self.graph = graph
        self.nodes = nodes
        self.edges = edges

        # Store removed elements for restoration
        self.removed_node_wrappers: Dict[str, NodeWrapper] = {}
        self.removed_edge_wrappers: Dict[str, EdgeWrapper] = {}
        # node_id -> edge wrappers that were connected to it
        self.node_connected_edge_wrappers: Dict[str, EdgeWrapper] = {}

    def _execute_impl(self) -> None:
        """Remove all specified elements and store them for undo."""
        # First, store and remove connections
        for edge_id in self.edges:
            edge_wrapper = self.graph.get_edge_wrapper(edge_id)
            if edge_wrapper:
                self.removed_edge_wrappers[edge_id] = edge_wrapper
                self.graph.remove_edge_wrapper(edge_id)

        # Then, store and remove nodes
        for node_id in self.nodes:
            node_wrapper = self.graph.get_node_wrapper(node_id)
            if node_wrapper:
                self.removed_node_wrappers[node_id] = node_wrapper

                all_edges = self.graph._get_all_edges(node_id)

                for edge in all_edges:
                    self.node_connected_edge_wrappers[edge.edge_id] = edge
                    # Remove the connected edge wrapper
                    self.graph.remove_edge_wrapper(edge.edge_id)

                # Remove the node wrapper
                self.graph.remove_node_wrapper(node_wrapper)

    def _undo_impl(self) -> None:
        """Restore all removed elements."""
        # First, restore node wrappers
        for _node_id, node_wrapper in self.removed_node_wrappers.items():
            self.graph.add_node_wrapper(node_wrapper)

        # then, restore all edges connected to restored nodes
        for _edge_id, edge_wrapper in self.node_connected_edge_wrappers.items():
            # Re-add existing wrapper
            self.graph.add_edge_wrapper(edge_wrapper)

        # Then, restore standalone connections
        # (that weren't connected to removed nodes)
        for _edge_id, edge_wrapper in self.removed_edge_wrappers.items():
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
    """
    Snapshot of a selection (node IDs + edge UUIDs).

    Not used in the undo stack — selection is per-session and non-undoable.
    Kept as a plain data-transfer object for copy/paste, context panels, and
    future collaborative multi-cursor features.
    """

    selected_nodes: set[str]
    selected_edges: set[str]  # Edge UUIDs


class DuplicateNodeAction(CompositeAction):
    """Composite action for duplicating a node."""

    def __init__(
        self,
        graph: BaseGraph,
        source_node_id: str,
        new_node_id: str,
        offset_x: float = 50.0,
        offset_y: float = 50.0,
    ):
        """
        Initialize the duplicate node action.

        Args:
            graph: The graph
            source_node_id: ID of the node to duplicate
            new_node_id: ID for the new node
            offset_x: X offset for the new node position
            offset_y: Y offset for the new node position
        """
        # NOT YET IMPLEMENTED — scaffolding for a future duplicate feature.
        # The previous body called _clone_node (NotImplementedError) and passed
        # a BaseNode instance to AddNodeAction (which expects a registry_key str),
        # so it would have crashed at runtime regardless. See git history for
        # the broken sketch.
        raise NotImplementedError(
            "DuplicateNodeAction is not yet implemented. "
            "Requires node cloning and rewiring to AddNodeAction's registry-key API."
        )


@dataclass
class ClipboardData:
    """Session clipboard mirror: the serialized payload + a copy timestamp.

    Holds the same dict written to the OS clipboard (see
    haywire.core.graph.clipboard.build_clipboard_payload), enabling a
    synchronous, permission-independent copy->paste within one session.
    """

    payload: Dict[str, Any]
    timestamp: float


class PasteClipboardAction(CompositeAction):
    """Undoable composite that pastes a clipboard payload into a graph.

    Mints fresh node IDs, remaps edge endpoints through the old->new map,
    offsets node positions so the selection's top-left lands at
    (paste_x, paste_y), and composes AddNodeAction (carrying node_data) +
    AddEdgeAction children. Undo/redo of all children is inherited from
    CompositeAction.

    Does NOT validate registry_keys: unknown node types degrade to placeholder
    error nodes (carrying their node_data) via create_node_wrapper/build —
    exactly as Graph.load_from_dict handles a file whose library is missing.
    """

    def __init__(
        self,
        graph: BaseGraph,
        payload: Dict[str, Any],
        paste_x: float,
        paste_y: float,
        description: Optional[str] = None,
    ):
        """
        Initialize the paste clipboard action.

        Args:
            graph: The graph to paste into
            payload: The clipboard payload (see build_clipboard_payload)
            paste_x: X position where to paste (upper-left corner)
            paste_y: Y position where to paste (upper-left corner)
            description: Optional description override
        """
        self.graph = graph

        nodes = payload.get("nodes", {})
        edges = payload.get("edges", {})
        subgraphs = payload.get("subgraphs", {})

        # 1. Compute paste offset from the stored bounding box.
        bbox = payload.get("bounding_box") or {}
        off_x = paste_x - bbox.get("min_x", 0.0)
        off_y = paste_y - bbox.get("min_y", 0.0)

        actions: List[IAction] = []

        # 1b. A copied Group gets a Subgraph of its own: one card per definition
        #     is what makes SubgraphDefinition.graph_node_wrapper() unambiguous,
        #     so the key is reminted and the cards below are rebound to it.
        subgraph_key_map: Dict[str, str] = {}
        for source_key, definition_payload in subgraphs.items():
            new_key = graph.generate_unique_subgraph_key()
            subgraph_key_map[source_key] = new_key
            actions.append(_RestoreSubgraphAction(graph=graph, key=new_key, payload=definition_payload))

        # 2. Mint new ids and remap the edges onto them.
        remap = remap_node_ids(nodes=nodes, edges=edges, mint_id=graph.generate_unique_node_id)

        # New element ids, exposed so the paste handler can auto-select the
        # freshly pasted subgraph on the canvas.
        self.new_node_ids: List[str] = remap.new_node_ids
        self.new_edge_ids: List[str] = [edge.edge_id for edge in remap.edges]

        # 3. Build child AddNodeActions (no registry_key validation — unknown
        #    types become placeholders, like file load).
        for old_id, node in nodes.items():
            new_id = remap.id_map[old_id]
            pos = node.get("position") or [0.0, 0.0]
            new_x = float(pos[0]) + off_x
            new_y = float(pos[1]) + off_y

            # Copy node_data and force the restored position to the paste
            # point. NodeWrapper.build() applies position via set_position
            # early, but _initialize_from_dict() then restores the ORIGINAL
            # posX/posY from the serialized props, landing the pasted node on
            # top of its source. Overwriting the props here makes the restored
            # position the paste point. deepcopy keeps the shared payload dict
            # (mirror / OS-clipboard) intact for re-paste.
            node_data = copy.deepcopy(node.get("node_data") or {})
            # Props serialize in a nested shape — from_dict restores
            # positions from the "values" block only.
            props_values = node_data.setdefault("props", {}).setdefault("values", {})
            props_values["posX"] = new_x
            props_values["posY"] = new_y

            # A pasted card points at the copy of its Subgraph, not the original.
            store = node_data.get("store")
            if isinstance(store, dict):
                source_key = store.get(SUBGRAPH_KEY)
                if isinstance(source_key, str) and source_key in subgraph_key_map:
                    store[SUBGRAPH_KEY] = subgraph_key_map[source_key]

            actions.append(
                AddNodeAction(
                    graph=graph,
                    registry_key=node["registry_key"],
                    position=(new_x, new_y),
                    node_data=node_data,
                    node_id=new_id,
                )
            )

        # 4. Build child AddEdgeActions from the remapped edges.
        for edge in remap.edges:
            actions.append(
                AddEdgeAction(
                    graph=graph,
                    source_node_id=edge.source_node_id,
                    outlet_pin_id=edge.outlet_port_id,
                    sink_node_id=edge.sink_node_id,
                    inlet_pin_id=edge.inlet_port_id,
                )
            )

        super().__init__(actions, description or "Paste clipboard")


class _AddReroutePortsAction(ActionBase):
    """Add a reroute node's typed inlet/outlet for ``itype``.

    A child of ``SplitEdgeWithRerouteAction``. The reroute node ships
    port-less; this action adds an inlet/outlet under the ids ``inlet_id`` /
    ``outlet_id`` typed to ``itype``, inside a ``rejig`` block (the dynamic-port
    primitive the node already exposes — using the same ids on a re-run keeps
    the port set to exactly those two). The core never imports the node class or
    names its type; the ids and target ``IType`` are passed in by the caller
    (the graph-editor), so no core→library dependency is introduced.

    Undo is a no-op — the sibling ``AddNodeAction`` removes the whole node (and
    its ports) on undo, and redo re-runs this on the re-added (port-less)
    wrapper.
    """

    def __init__(
        self,
        graph: BaseGraph,
        node_id: str,
        itype: Any,
        inlet_id: str,
        outlet_id: str,
        description: Optional[str] = None,
    ):
        super().__init__(description or f"Add reroute ports '{node_id}'")
        self.graph = graph
        self.node_id = node_id
        self.itype = itype
        self.inlet_id = inlet_id
        self.outlet_id = outlet_id

    def _execute_impl(self) -> None:
        wrapper = self.graph.get_node_wrapper(self.node_id)
        if wrapper is None:
            raise RuntimeError(f"Reroute node '{self.node_id}' not found for port configuration")
        node = wrapper.node
        # Add the typed ports. rejig (include=ids) makes the operation
        # idempotent: on a fresh port-less node it simply adds them; on a redo
        # it keeps the port set to exactly {inlet_id, outlet_id}.
        with node.rejig(include=[self.inlet_id, self.outlet_id]):
            node.add(self.itype.as_inlet(id=self.inlet_id, label=""))
            node.add(self.itype.as_outlet(id=self.outlet_id, label=""))

    def _undo_impl(self) -> None:
        # No-op: the node (and its ports) is removed by the sibling
        # AddNodeAction's undo. Nothing to reverse here.
        pass


class SplitEdgeWithRerouteAction(CompositeAction):
    """Split a data edge and insert a reroute node in between.

    Given an edge ``A.out -> B.in``, this composite (one undoable unit):

    1. removes the original edge,
    2. creates a port-less reroute node (``registry_key``) at ``position``,
    3. adds its inlet/outlet typed to the outlet's concrete ``IType``,
    4. wires ``A.out -> R.in`` (adapter-free, same type) and
       ``R.out -> B.in`` (rebuilds whatever adapter the original had).

    Typing the reroute to the **outlet** type keeps the split behaviorally
    transparent: the first new edge needs no adapter, and the second edge
    re-derives the original ``source_type -> sink_type`` adapter chain
    automatically (see ``EdgeWrapper._build_adapter_chain``). One undo
    restores the original edge with its chain intact.

    The reroute node *type* is supplied by the caller as ``registry_key`` (the
    graph editor discovers it via the registry's ``_is_reroute`` flag), so the
    core carries no dependency on a specific haybale library. The port ids are an
    implementation detail of the split (``_REROUTE_INLET_ID`` / ``_REROUTE_OUTLET_ID``).
    """

    def __init__(
        self,
        graph: BaseGraph,
        edge_id: str,
        position: Tuple[float, float],
        registry_key: str,
        description: Optional[str] = None,
    ):
        self.graph = graph
        self.reroute_node_id: Optional[str] = None

        edge = graph.get_edge_wrapper(edge_id)
        if edge is None:
            raise ValueError(f"Edge '{edge_id}' not found; cannot split")

        source_node_id = edge.source_node_id
        outlet_port_id = edge.outlet_port_id
        sink_node_id = edge.sink_node_id
        inlet_port_id = edge.inlet_port_id

        # Resolve the outlet's concrete IType (the type the reroute will carry).
        source_wrapper = graph.get_node_wrapper(source_node_id)
        if source_wrapper is None:
            raise ValueError(f"Source node '{source_node_id}' not found; cannot split edge")
        outlet_port = source_wrapper.node.ports.get(outlet_port_id)
        if outlet_port is None:
            raise ValueError(f"Outlet port '{outlet_port_id}' not found; cannot split edge")
        itype = outlet_port.stored_type

        # Pre-mint the reroute node id so the edge children can reference it.
        new_node_id = graph.generate_unique_node_id(registry_key=registry_key)
        self.reroute_node_id = new_node_id

        actions: List[IAction] = [
            RemoveElementsAction(graph=graph, edges=[edge_id]),
            AddNodeAction(
                graph=graph,
                registry_key=registry_key,
                position=position,
                node_id=new_node_id,
            ),
            _AddReroutePortsAction(
                graph=graph,
                node_id=new_node_id,
                itype=itype,
                inlet_id=_REROUTE_INLET_ID,
                outlet_id=_REROUTE_OUTLET_ID,
            ),
            AddEdgeAction(
                graph=graph,
                source_node_id=source_node_id,
                outlet_pin_id=outlet_port_id,
                sink_node_id=new_node_id,
                inlet_pin_id=_REROUTE_INLET_ID,
            ),
            AddEdgeAction(
                graph=graph,
                source_node_id=new_node_id,
                outlet_pin_id=_REROUTE_OUTLET_ID,
                sink_node_id=sink_node_id,
                inlet_pin_id=inlet_port_id,
            ),
        ]

        super().__init__(actions, description or "Insert reroute")


class DissolveRerouteAction(CompositeAction):
    """Dissolve a reroute node, bridging upstream to all downstream sinks.

    Given a reroute R with upstream edges ``A.out → R.in``,
    ``B.out → R.in`` and downstream edges ``R.out → C.in``,
    ``R.out → D.in``, this composite (one undoable unit):

    1. Removes R and all its connected edges (``RemoveElementsAction`` with
       just the node id; cascade removes the edges).
    2. For each (upstream, downstream) pair, adds a direct edge
       ``upstream.out → downstream.in`` (``AddEdgeAction``).

    DATA reroutes have one upstream edge; CONTROL reroutes allow multiple
    upstream edges on the inlet (``allow_multiple_links=True``), so all
    upstreams are bridged to all downstreams.

    If no upstream edges exist (partial state), no bridge edges are created
    — only the node is removed. This covers all partial states without
    blocking the user.

    Raises ``ValueError`` if ``node_id`` is not present in the graph.
    """

    def __init__(
        self,
        graph: BaseGraph,
        node_id: str,
        description: Optional[str] = None,
    ):
        wrapper = graph.get_node_wrapper(node_id)
        if wrapper is None:
            raise ValueError(f"Reroute node '{node_id}' not found; cannot dissolve")

        all_edges = graph._get_all_edges(node_id)

        # Partition into upstream (node is sink) and downstream (node is source).
        upstream = [e for e in all_edges if e.sink_node_id == node_id]
        downstream = [e for e in all_edges if e.source_node_id == node_id]

        actions: List[IAction] = [
            RemoveElementsAction(graph=graph, nodes=[node_id]),
        ]

        # Bridge every upstream source to every downstream sink.
        # CONTROL inlets allow multiple upstream edges; DATA inlets allow one.
        for src in upstream:
            for sink_edge in downstream:
                actions.append(
                    AddEdgeAction(
                        graph=graph,
                        source_node_id=src.source_node_id,
                        outlet_pin_id=src.outlet_port_id,
                        sink_node_id=sink_edge.sink_node_id,
                        inlet_pin_id=sink_edge.inlet_port_id,
                    )
                )

        super().__init__(actions, description or "Dissolve reroute")


class SetPropertyAction(ActionBase):
    """Undoable set of a node property addressed by (node_id, name).

    ``name`` resolves against the node's ports first (port id -> port value),
    then against its settings bags (field name -> settings-bag write). This is
    the one deliberate new core mutation surface mandated by the Farmhand spec:
    the raw settings/port write paths are non-undoable and not id-addressable.

    ``prefer_setting=True`` flips the resolution order (settings bags first),
    for callers that mean a settings field even when a port shares the name —
    e.g. the resize commit writing ``props.width`` on a node that also has a
    ``width`` outlet.
    """

    def __init__(self, graph: BaseGraph, node_id: str, name: str, value: Any, prefer_setting: bool = False):
        super().__init__(description=f"Set '{name}' on {node_id}")
        self.graph = graph
        self.node_id = node_id
        self.name = name
        self.new_value = value
        self.prefer_setting = prefer_setting
        self._old_value: Any = None

    def _resolve(self) -> Tuple[Any, str, Optional[str]]:
        """Return (node, kind, accessor) where kind is 'port' or 'setting'."""
        wrapper = self.graph.get_node_wrapper(self.node_id)
        if wrapper is None:
            raise ValueError(f"Node '{self.node_id}' not found")
        node = wrapper.node

        def _find_bag() -> Optional[str]:
            for accessor in type(node)._settings_bags:
                bag = getattr(node, accessor)
                if self.name in type(bag)._settings_descriptors():
                    return accessor
            return None

        if self.prefer_setting:
            accessor = _find_bag()
            if accessor is not None:
                return node, "setting", accessor
            if self.name in node.ports:
                return node, "port", None
        else:
            if self.name in node.ports:
                return node, "port", None
            accessor = _find_bag()
            if accessor is not None:
                return node, "setting", accessor
        raise ValueError(f"Node '{self.node_id}' has no port or setting named '{self.name}'")

    def _execute_impl(self) -> None:
        node, kind, accessor = self._resolve()
        if kind == "port":
            self._old_value = node.ports[self.name].get_value()
            node.ports[self.name].set_value(self.new_value)
        else:
            assert accessor is not None  # kind == "setting" always carries an accessor
            bag = getattr(node, accessor)
            self._old_value = getattr(bag, self.name)
            setattr(bag, self.name, self.new_value)

    def _undo_impl(self) -> None:
        node, kind, accessor = self._resolve()
        if kind == "port":
            node.ports[self.name].set_value(self._old_value)
        else:
            assert accessor is not None  # kind == "setting" always carries an accessor
            setattr(getattr(node, accessor), self.name, self._old_value)


class SetPortMetadataAction(ActionBase):
    """Undoable edit of a port's own presentation — its label, docs and default.

    Distinct from :class:`SetPropertyAction`, which writes a port's *value*.
    This writes the spec beside it: what the port is called, what it documents
    and where it starts. One action carries every field the user changed in one
    gesture, so a dialog's Apply is one undo step.

    Only a ``RESOLVED`` port may be edited. A ``DECLARED`` port is the node
    author's contract — it appears in that component's generated docs — and a
    ``PROMOTED`` one takes its presentation from the setting descriptor and is
    regenerated on load, so an edit could not persist.

    Raises:
        ValueError: If the node or port is not found, or the port's origin is
            not ``RESOLVED``.

    Example::

        action = SetPortMetadataAction(
            graph, node_id, "gain", label="Confidence", description="0 to 1"
        )
        editor.history_manager.add_action(action)
    """

    #: The port attributes this action may write.
    _FIELDS = ("label", "description", "default")

    def __init__(
        self,
        graph: BaseGraph,
        node_id: str,
        port_id: str,
        description_: Optional[str] = None,
        **changes: Any,
    ):
        """
        Args:
            port_id: The port to edit, on ``node_id``.
            description_: Optional override for the undo entry's own text, kept
                out of the way of the ``description`` field being edited.
            **changes: Any of ``label``, ``description``, ``default``. A field
                left out is untouched.
        """
        unknown = set(changes) - set(self._FIELDS)
        if unknown:
            raise ValueError(
                f"SetPortMetadataAction cannot write {', '.join(sorted(unknown))}; "
                f"it writes {', '.join(self._FIELDS)}"
            )
        super().__init__(description=description_ or f"Edit '{port_id}' on {node_id}")
        self.graph = graph
        self.node_id = node_id
        self.port_id = port_id
        self.changes = changes
        self._old: Dict[str, Any] = {}

    def _port(self) -> Any:
        wrapper = self.graph.get_node_wrapper(self.node_id)
        if wrapper is None:
            raise ValueError(f"Node '{self.node_id}' not found")
        port = wrapper.node.ports.get(self.port_id)
        if port is None:
            raise ValueError(f"Node '{self.node_id}' has no port '{self.port_id}'")
        return port

    def _execute_impl(self) -> None:
        from ...types.enums import PortOrigin

        port = self._port()
        if port.origin is not PortOrigin.RESOLVED:
            raise ValueError(
                f"Port '{self.port_id}' is {port.origin.value}, not resolved: only a port the "
                f"user brought into being carries its own label, docs and default"
            )
        self._old = {name: getattr(port, name) for name in self.changes}
        self._apply(port, self.changes)

    def _undo_impl(self) -> None:
        self._apply(self._port(), self._old)

    def _apply(self, port: Any, values: Dict[str, Any]) -> None:
        """Write ``values`` onto ``port``, then publish the change.

        Marked ``NODE_VALIDATION_REQUESTED``, which is in both the redraw set
        (so the card repaints with the new name and bounds) and the reassembly
        set (so a Graph-node watching this Subgraph reconciles and its mirrored
        pin follows). A rename changes no structure, so nothing else tells them.

        Straight to ``mark_node_dirty`` rather than through the wrapper's
        ``mark_as_structuraly_dirty``: that one no-ops while the node's
        ``_is_dirty_structural`` is still set from an earlier rejig, and the
        flag is cleared by a housekeeping pass this very call is trying to
        cause.
        """
        from ...graph.types import ChangeReason

        for name, value in values.items():
            setattr(port, name, value)
        self.graph._validation.mark_node_dirty(self.node_id, ChangeReason.NODE_VALIDATION_REQUESTED)


def _move_subgraphs(source: BaseGraph, target: BaseGraph, keys: List[str]) -> None:
    """Move the Subgraph definitions named by ``keys`` from one table to the other.

    A key that ``source`` does not hold, or that ``target`` already holds, is
    skipped with a warning rather than raising: these run inside undo actions,
    where an exception mid-list would leave half a move applied.
    """
    for key in keys:
        if target.get_subgraph(key) is not None:
            logger.warning(f"Subgraph '{key}' is already in the target graph; not moving it")
            continue
        definition = source.detach_subgraph(key)
        if definition is None:
            logger.warning(f"Subgraph '{key}' is not in the source graph; nothing to move")
            continue
        target.add_subgraph(definition)


class _BuildSubgraphAction(ActionBase):
    """Create one Subgraph definition, its interface, and its contents.

    A child of ``CollapseToGraphNodeAction``. Registers a ``SubgraphDefinition``
    under ``key`` in the host's table, creates the two boundary nodes and stamps
    the ports ``plan`` derived, then rebuilds the selected nodes and the edges
    internal to them inside it, under the **same ids** they had in the host —
    they are already unique across the whole tree, so nothing is remapped and a
    later expand puts them back where they were.

    A selected Graph-node brings its own Subgraph along: ``nested_keys`` names
    the definitions that move from the host's table into this one, ahead of the
    nodes, because a Graph-node mirrors its boundary ports while it is built.

    Undo removes the definition outright, which releases its nodes' settings
    subscriptions; the nested definitions go back to the host first, so they
    survive it. Redo rebuilds it from the payload captured at construction.
    """

    def __init__(
        self,
        graph: BaseGraph,
        key: str,
        label: str,
        plan: Any,
        nodes: Dict[str, Any],
        edges: Dict[str, Any],
        input_node_id: str,
        output_node_id: str,
        input_registry_key: str,
        output_registry_key: str,
        input_position: Tuple[float, float],
        output_position: Tuple[float, float],
        nested_keys: Optional[List[str]] = None,
        description: Optional[str] = None,
    ):
        super().__init__(description or f"Build subgraph '{key}'")
        self.graph = graph
        self.key = key
        self.label = label
        self.plan = plan
        self.nodes = nodes
        self.edges = edges
        self.input_node_id = input_node_id
        self.output_node_id = output_node_id
        self.input_registry_key = input_registry_key
        self.output_registry_key = output_registry_key
        self.input_position = input_position
        self.output_position = output_position
        self.nested_keys = list(nested_keys or [])

    def _execute_impl(self) -> None:
        from ...graph.subgraph import SubgraphDefinition

        definition = SubgraphDefinition(key=self.key, label=self.label)
        self.graph.add_subgraph(definition)

        self._build_boundary(definition, is_input=True)
        self._build_boundary(definition, is_input=False)

        # Before the nodes: a Graph-node among them resolves its Subgraph from
        # this table while it is built, to mirror the boundary ports.
        _move_subgraphs(self.graph, definition, self.nested_keys)

        for node_id, node_data in self.nodes.items():
            position = node_data.get("position") or [0.0, 0.0]
            definition.create_node_wrapper(
                registry_key=node_data["registry_key"],
                position=(float(position[0]), float(position[1])),
                node_data=node_data.get("node_data", {}),
                node_id=node_id,
            )

        for edge in self.edges.values():
            definition.create_edge_wrapper(
                edge["source_node_id"],
                edge["outlet_port_id"],
                edge["sink_node_id"],
                edge["inlet_port_id"],
            )

        # The interface's inner side: the Subgraph Input fans out to the ports
        # the crossing edges used to land on, and the Subgraph Output collects
        # from the ports they used to leave.
        for port in self.plan.inlets:
            for node_id, port_id in port.inner:
                definition.create_edge_wrapper(self.input_node_id, port.port_id, node_id, port_id)
        for port in self.plan.outlets:
            node_id, port_id = port.inner[0]
            definition.create_edge_wrapper(node_id, port_id, self.output_node_id, port.port_id)

    def _build_boundary(self, definition: Any, *, is_input: bool) -> None:
        """Create one boundary node at its side of the contents, with the plan's ports."""
        node_id = self.input_node_id if is_input else self.output_node_id
        registry_key = self.input_registry_key if is_input else self.output_registry_key
        ports = self.plan.inlets if is_input else self.plan.outlets
        position = self.input_position if is_input else self.output_position

        wrapper = definition.create_node_wrapper(
            registry_key=registry_key, node_id=node_id, position=position
        )
        if wrapper is None:
            raise RuntimeError(f"Could not create boundary node '{node_id}' for subgraph '{self.key}'")

        node = wrapper.node
        # The interface is the user's, so it is RESOLVED and each port carries a
        # removal row. Excluding DECLARED spares the growing slot init() added,
        # which a bare rejig would take with the rest.
        from ...types.enums import PortOrigin

        with node.rejig(exclude=[PortOrigin.DECLARED]):
            for port in ports:
                # Seeded from the interior port that named this one, so an
                # interface derived from documented nodes arrives documented and
                # keeps their editing affordances. All of it is the user's from
                # here on — an interface port is RESOLVED.
                kwargs: Dict[str, Any] = {
                    "label": port.label,
                    "description": port.description,
                    "flow_type": port.flow_type,
                    "default": port.default,
                    "origin": PortOrigin.RESOLVED,
                }
                if port.widget_key is not None:
                    kwargs["widget_key"] = port.widget_key
                    kwargs["widget_config"] = dict(port.widget_config)
                factory = port.itype.as_outlet if is_input else port.itype.as_inlet
                node.add(factory(port.port_id, **kwargs))

    def _undo_impl(self) -> None:
        definition = self.graph.get_subgraph(self.key)
        if definition is not None:
            # Out before the definition goes: remove_subgraph destroys the whole
            # subtree, and these belong to the cards returning to the host.
            _move_subgraphs(definition, self.graph, self.nested_keys)
        self.graph.remove_subgraph(self.key)


class _LiftNestedSubgraphsAction(ActionBase):
    """Move the Subgraphs of a dissolving Group's own Graph-nodes out to the host.

    A child of ``ExpandGraphNodeAction``, and the first of them: the cards those
    definitions belong to are rebuilt in the host by the actions that follow,
    and a Graph-node resolves its Subgraph from its graph's table while it is
    built. Undo moves them back in, after the definition itself is restored.
    """

    def __init__(
        self,
        graph: BaseGraph,
        subgraph_key: str,
        keys: List[str],
        description: Optional[str] = None,
    ):
        super().__init__(description or f"Lift nested subgraphs out of '{subgraph_key}'")
        self.graph = graph
        self.subgraph_key = subgraph_key
        self.keys = list(keys)

    def _execute_impl(self) -> None:
        definition = self.graph.get_subgraph(self.subgraph_key)
        if definition is not None:
            _move_subgraphs(definition, self.graph, self.keys)

    def _undo_impl(self) -> None:
        definition = self.graph.get_subgraph(self.subgraph_key)
        if definition is not None:
            _move_subgraphs(self.graph, definition, self.keys)


class _DiscardTemplateInteriorAction(ActionBase):
    """Drop a placement's instantiated interior when its card goes.

    A child of ``PromoteGroupToMacroAction``, and the mirror of what creates
    the interior: a placement builds it in ``post_init``, not through an
    action, so nothing else would take it away again on undo.

    Execute re-instantiates rather than doing nothing, because a redo re-adds
    the *existing* wrapper instead of building a new one, so ``post_init`` —
    which is what creates the interior — does not run a second time. The
    interior is runtime state rebuilt from the template (ADR 0038), so
    building it again is the whole restoration.
    """

    def __init__(self, graph: BaseGraph, node_id: str, description: Optional[str] = None):
        super().__init__(description or f"Discard the interior of '{node_id}'")
        self.graph = graph
        self.node_id = node_id

    def _execute_impl(self) -> None:
        """Rebuild the interior, for the redo that re-adds an existing card.

        A no-op on first execution: the card was just built, and its
        ``post_init`` has already instantiated the interior.
        """
        wrapper = self.graph.get_node_wrapper(self.node_id)
        if wrapper is None:
            return
        rebuild = getattr(wrapper.node, "instantiate_from_template", None)
        if rebuild is not None:
            rebuild()

    def _undo_impl(self) -> None:
        # Asked of the card rather than rebuilt from its id: how a placement
        # derives its key is the node's business, and core does not import the
        # library the class lives in.
        wrapper = self.graph.get_node_wrapper(self.node_id)
        if wrapper is None:
            return
        key = getattr(wrapper.node, "subgraph_key", None)
        if key and self.graph.get_subgraph(key) is not None:
            self.graph.remove_subgraph(key)


class _DropSubgraphAction(ActionBase):
    """Remove one Subgraph definition, restoring it whole on undo.

    A child of ``ExpandGraphNodeAction``. The definition is serialized just
    before it goes, so undo rebuilds it — boundary nodes, contents, edges and
    graph-tier settings alike — through the same ``load_from_dict`` a file load
    uses.
    """

    def __init__(self, graph: BaseGraph, key: str, description: Optional[str] = None):
        super().__init__(description or f"Drop subgraph '{key}'")
        self.graph = graph
        self.key = key
        self._payload: Optional[Dict[str, Any]] = None

    def _execute_impl(self) -> None:
        definition = self.graph.get_subgraph(self.key)
        if definition is None:
            return
        self._payload = definition.to_dict(include_data=True)
        self.graph.remove_subgraph(self.key)

    def _undo_impl(self) -> None:
        if self._payload is None:
            return
        from ...graph.subgraph import SubgraphDefinition

        definition = SubgraphDefinition(key=self.key)
        self.graph.add_subgraph(definition)
        definition.load_from_dict(self._payload)


class _RestoreSubgraphAction(ActionBase):
    """Build one Subgraph definition from a serialized payload, under ``key``.

    A child of ``PasteClipboardAction``. The payload travels in the clipboard,
    so the contents are rebuilt under ids minted for this graph — a pasted Group
    shares nothing with the one it was copied from. Undo removes the definition
    again.
    """

    def __init__(
        self,
        graph: BaseGraph,
        key: str,
        payload: Dict[str, Any],
        description: Optional[str] = None,
    ):
        super().__init__(description or f"Restore subgraph '{key}'")
        self.graph = graph
        self.key = key
        self.payload = payload

    def _execute_impl(self) -> None:
        from ...graph.subgraph import SubgraphDefinition

        definition = SubgraphDefinition(key=self.key, label=self.payload.get("label") or self.key)
        self.graph.add_subgraph(definition)
        # instantiate(), not load_from_dict(): the source graph's node ids are
        # still in use here, so the contents need ids of their own.
        definition.instantiate(
            nodes=self.payload.get("nodes", {}),
            edges=self.payload.get("edges", {}),
            subgraphs=self.payload.get("subgraphs", {}),
        )

    def _undo_impl(self) -> None:
        self.graph.remove_subgraph(self.key)


class CollapseToGraphNodeAction(CompositeAction):
    """Collapse a selection into a Group — one card standing for a Subgraph.

    Given a convex selection, this composite (one undoable unit):

    1. removes the selected nodes from the host, taking their edges with them,
    2. builds the ``SubgraphDefinition``, its two boundary nodes, and the
       selection's own nodes and internal edges inside it,
    3. creates the Graph-node bound to the definition's key, at the selection's
       centroid, whose pins mirror the boundary nodes,
    4. rewires each crossing edge to the matching pin on the card.

    The interface is derived by ``derive_interface``: inlets dedup by their
    outer source, outlets by their inner source, so one outer outlet feeding
    three selected nodes becomes one inlet that fans out again inside.

    The boundary node classes are supplied by the caller, discovered through the
    registry's ``_is_subgraph_input`` / ``_is_subgraph_output`` flags, so the
    core names no library's node.

    Raises:
        ValueError: If fewer than one node is selected, if a selected node is
            not in the graph, if the selection is not convex (the message names
            the intervening nodes), or if it holds a boundary node (the message
            names those).
    """

    def __init__(
        self,
        graph: BaseGraph,
        node_ids: List[str],
        card_registry_key: str,
        input_registry_key: str,
        output_registry_key: str,
        label: str = "Group",
        description: Optional[str] = None,
    ):
        from ...graph.subgraph_collapse import check_convex, derive_interface
        from ...graph.subgraph_crossing import card_port_id

        self.graph = graph

        selected = [node_id for node_id in node_ids if graph.get_node_wrapper(node_id) is not None]
        if not selected:
            raise ValueError("Nothing to collapse: none of the selected nodes are in the graph")

        boundary = [
            node_id
            for node_id in selected
            if (wrapper := graph.get_node_wrapper(node_id)) is not None
            and wrapper.node.behavior.is_boundary_node
        ]
        if boundary:
            raise ValueError(
                "This selection cannot be collapsed: "
                f"{', '.join(boundary)} carries the interface of the Group it is already in, "
                "and a Group cannot hand its interface to another one. "
                "Leave them out of the selection to collapse the rest."
            )

        is_convex, intervening = check_convex(graph, selected)
        if not is_convex:
            raise ValueError(
                "This selection cannot be collapsed: control would leave the Group and re-enter "
                f"it through {', '.join(intervening)}. Add them to the selection to collapse it."
            )

        straddling = _callback_edge_partners(graph, selected)
        if straddling:
            raise ValueError(
                "This selection cannot be collapsed: a callback edge would cross the Group's "
                f"boundary, to {', '.join(straddling)}. A callback edge must run straight from "
                "its event node to its listener — the subscription travels as a port value, and "
                "a boundary node cannot carry it across. Add the node at the other end to the "
                "selection, or leave both ends outside it."
            )

        plan = derive_interface(graph, selected)

        # Captured while the graph is still intact — the children below run later.
        wrappers = [graph.get_node_wrapper(node_id) for node_id in selected]
        nodes = {w.node_id: w.serialize(include_data=True) for w in wrappers if w is not None}
        # A Graph-node in the selection is collapsed together with its Subgraph.
        nested_keys = [
            key
            for w in wrappers
            if w is not None
            and (key := getattr(w.node, "subgraph_key", None))
            and graph.get_subgraph(key) is not None
        ]
        edges = {
            edge_id: edge.edge.to_dict()
            for edge_id in plan.internal_edge_ids
            if (edge := graph.get_edge_wrapper(edge_id)) is not None
        }
        crossings = [
            (edge.source_node_id, edge.outlet_port_id, edge.sink_node_id, edge.inlet_port_id)
            for edge_id in plan.crossing_edge_ids
            if (edge := graph.get_edge_wrapper(edge_id)) is not None
        ]

        # The boundary nodes flank the contents rather than sharing the default
        # position: they are the Subgraph's edges, so they belong outside its
        # bounding box, on the axis the contents flow along.
        input_position, output_position = _boundary_positions(nodes)

        self.subgraph_key = graph.generate_unique_subgraph_key()
        self.card_node_id = graph.generate_unique_node_id(card_registry_key)
        input_node_id = graph.generate_unique_node_id(input_registry_key)
        output_node_id = graph.generate_unique_node_id(output_registry_key)

        actions: List[IAction] = [
            RemoveElementsAction(graph=graph, nodes=list(selected)),
            _BuildSubgraphAction(
                graph=graph,
                key=self.subgraph_key,
                label=label,
                plan=plan,
                nodes=nodes,
                edges=edges,
                input_node_id=input_node_id,
                output_node_id=output_node_id,
                input_registry_key=input_registry_key,
                output_registry_key=output_registry_key,
                input_position=input_position,
                output_position=output_position,
                nested_keys=nested_keys,
            ),
            AddNodeAction(
                graph=graph,
                registry_key=card_registry_key,
                position=_centroid(nodes),
                node_data={"store": {"subgraph_key": self.subgraph_key}},
                node_id=self.card_node_id,
            ),
        ]

        # Rewire the crossing edges onto the card. An inlet's pin takes the one
        # outer source it deduped on; an outlet's pin feeds every outer sink.
        pin_for_source = {port.outer[0]: card_port_id(port.port_id, is_inlet=True) for port in plan.inlets}
        pin_for_sink = {
            sink: card_port_id(port.port_id, is_inlet=False) for port in plan.outlets for sink in port.outer
        }

        # The pins are deduped but the crossings are not, so several crossings
        # can land on one pin and name the same card edge. One AddEdgeAction
        # each; a second on the same endpoints raises and aborts the composite.
        emitted: set[Tuple[str, str, str, str]] = set()

        for source_node_id, outlet_port_id, sink_node_id, inlet_port_id in crossings:
            if sink_node_id in nodes:
                pin = pin_for_source.get((source_node_id, outlet_port_id))
                if pin is None:
                    continue
                if not _claim(emitted, (source_node_id, outlet_port_id, self.card_node_id, pin)):
                    continue
                actions.append(
                    AddEdgeAction(
                        graph=graph,
                        source_node_id=source_node_id,
                        outlet_pin_id=outlet_port_id,
                        sink_node_id=self.card_node_id,
                        inlet_pin_id=pin,
                    )
                )
            else:
                pin = pin_for_sink.get((sink_node_id, inlet_port_id))
                if pin is None:
                    continue
                if not _claim(emitted, (self.card_node_id, pin, sink_node_id, inlet_port_id)):
                    continue
                actions.append(
                    AddEdgeAction(
                        graph=graph,
                        source_node_id=self.card_node_id,
                        outlet_pin_id=pin,
                        sink_node_id=sink_node_id,
                        inlet_pin_id=inlet_port_id,
                    )
                )

        super().__init__(actions, description or f"Collapse to {label}")


class ExpandGraphNodeAction(CompositeAction):
    """Expand a Group back into the host graph — the inverse of a collapse.

    Given a Graph-node, this composite (one undoable unit):

    1. rebuilds the Subgraph's own nodes and edges in the host, under the ids
       they already carry (unique across the tree, so nothing is remapped),
    2. rewires each of the card's edges to the inner port the matching boundary
       port pointed at,
    3. removes the card, which takes its edges with it, and drops the
       definition and its boundary nodes.

    ``collapse → expand`` returns an equivalent graph, and each is undoable on
    its own.

    Raises:
        ValueError: If ``node_id`` is not a Graph-node with a Subgraph bound.
    """

    def __init__(
        self,
        graph: BaseGraph,
        node_id: str,
        description: Optional[str] = None,
    ):
        from ...graph.subgraph import SubgraphDefinition
        from ...graph.subgraph_crossing import boundary_port_id

        self.graph = graph

        card = graph.get_node_wrapper(node_id)
        if card is None:
            raise ValueError(f"Node '{node_id}' not found; cannot expand")

        resolve = getattr(card.node, "resolve_definition", None)
        definition = resolve() if resolve is not None else None
        if not isinstance(definition, SubgraphDefinition):
            raise ValueError(f"Node '{node_id}' is not a Graph-node with a Subgraph; cannot expand")

        input_node = definition.input_node
        output_node = definition.output_node
        boundary_ids = {w.node_id for w in (input_node, output_node) if w is not None}

        # The contents to lift out, and the edges among them.
        contents = definition.content_node_wrappers()
        nodes = {w.node_id: w.serialize(include_data=True) for w in contents}
        inner_edges = [
            edge
            for edge in definition.edge_wrappers.values()
            if edge.source_node_id in nodes and edge.sink_node_id in nodes
        ]

        # Where each boundary port pointed, so the card's edges can be rewired
        # to the same inner ports.
        inner_sinks: Dict[str, List[Tuple[str, str]]] = {}
        inner_sources: Dict[str, Tuple[str, str]] = {}
        for edge in definition.edge_wrappers.values():
            if input_node is not None and edge.source_node_id == input_node.node_id:
                inner_sinks.setdefault(edge.outlet_port_id, []).append(
                    (edge.sink_node_id, edge.inlet_port_id)
                )
            if output_node is not None and edge.sink_node_id == output_node.node_id:
                inner_sources[edge.inlet_port_id] = (edge.source_node_id, edge.outlet_port_id)

        # First, so the Graph-nodes among the contents find their own Subgraphs
        # in the host's table as they are rebuilt into it below.
        nested_keys = [
            key
            for w in contents
            if (key := getattr(w.node, "subgraph_key", None)) and definition.get_subgraph(key) is not None
        ]
        actions: List[IAction] = [
            _LiftNestedSubgraphsAction(graph=graph, subgraph_key=definition.key, keys=nested_keys)
        ]

        for inner_id, node_data in nodes.items():
            position = node_data.get("position") or [0.0, 0.0]
            actions.append(
                AddNodeAction(
                    graph=graph,
                    registry_key=node_data["registry_key"],
                    position=(float(position[0]), float(position[1])),
                    node_data=node_data.get("node_data", {}),
                    node_id=inner_id,
                )
            )

        for edge in inner_edges:
            actions.append(
                AddEdgeAction(
                    graph=graph,
                    source_node_id=edge.source_node_id,
                    outlet_pin_id=edge.outlet_port_id,
                    sink_node_id=edge.sink_node_id,
                    inlet_pin_id=edge.inlet_port_id,
                )
            )

        # Bridge the card's own edges to the inner ports behind its pins.
        for edge in graph._get_all_edges(node_id):
            if edge.sink_node_id == node_id:
                boundary_id = boundary_port_id(edge.inlet_port_id)
                for inner_node_id, inner_port_id in inner_sinks.get(boundary_id or "", []):
                    actions.append(
                        AddEdgeAction(
                            graph=graph,
                            source_node_id=edge.source_node_id,
                            outlet_pin_id=edge.outlet_port_id,
                            sink_node_id=inner_node_id,
                            inlet_pin_id=inner_port_id,
                        )
                    )
            else:
                boundary_id = boundary_port_id(edge.outlet_port_id)
                inner = inner_sources.get(boundary_id or "")
                if inner is not None:
                    actions.append(
                        AddEdgeAction(
                            graph=graph,
                            source_node_id=inner[0],
                            outlet_pin_id=inner[1],
                            sink_node_id=edge.sink_node_id,
                            inlet_pin_id=edge.inlet_port_id,
                        )
                    )

        # Last: the card goes, taking its edges, and the definition with it.
        actions.append(RemoveElementsAction(graph=graph, nodes=[node_id]))
        actions.append(_DropSubgraphAction(graph=graph, key=definition.key))

        self.inner_node_ids = [node_id for node_id in nodes if node_id not in boundary_ids]
        super().__init__(actions, description or "Expand Group")


class _AdoptTemplateInteriorAction(ActionBase):
    """Turn a placement's interior into a Subgraph the host file owns.

    A child of :class:`DetachPlacementFromMacroAction`. Moves the definition out
    of the table and back under a key of its own, clearing ``template_key`` so
    ``BaseGraph.to_dict`` stops skipping it — that mark is the only thing that
    distinguishes a placement's interior from a Group's Subgraph, so clearing it
    and re-keying is the whole conversion. The live nodes and edges travel
    intact, which is what ``detach_subgraph`` exists for.

    Runs before the cards are swapped, so the new key is in the table by the
    time the Group's card is built and binds to it.
    """

    def __init__(
        self,
        graph: BaseGraph,
        source_key: str,
        target_key: str,
        template_key: str,
        description: Optional[str] = None,
    ):
        super().__init__(description or f"Adopt interior '{source_key}' as '{target_key}'")
        self.graph = graph
        self.source_key = source_key
        self.target_key = target_key
        self.template_key = template_key

    def _execute_impl(self) -> None:
        definition = self.graph.detach_subgraph(self.source_key)
        if definition is None:
            return
        definition.key = self.target_key
        definition.template_key = None
        self.graph.add_subgraph(definition)

    def _undo_impl(self) -> None:
        definition = self.graph.detach_subgraph(self.target_key)
        if definition is None:
            return
        definition.key = self.source_key
        definition.template_key = self.template_key
        self.graph.add_subgraph(definition)


class DetachPlacementFromMacroAction(CompositeAction):
    """Swap a macro placement for a Group holding the interior it was showing.

    The card stops tracking the template: a later save of the ``.hwm`` no longer
    reaches it, and the interior becomes part of the host file. This composite
    (one undoable unit):

    1. re-keys the placement's interior and clears its ``template_key``, so the
       host serializes it,
    2. removes the placement, which takes its edges with it,
    3. creates a Graph-node bound to the re-keyed definition, at the same
       position and carrying the same label,
    4. re-attaches each of the placement's edges to the matching pin.

    Pin ids survive untouched: both cards derive them from the same boundary
    ports, so an edge re-attaches by the id it already had.

    **Acts on this one card.** The macro file stays on disk and every other
    placement of it keeps tracking the template — this is not the inverse of
    promotion, which consumed the only card standing for the Subgraph.

    Raises:
        ValueError: If ``node_id`` is not a macro placement with an interior.
    """

    def __init__(
        self,
        graph: BaseGraph,
        node_id: str,
        card_registry_key: str,
        description: Optional[str] = None,
    ):
        self.graph = graph

        card = graph.get_node_wrapper(node_id)
        if card is None:
            raise ValueError(f"Node '{node_id}' not found; cannot detach")

        source_key = str(getattr(card.node, "subgraph_key", "") or "")
        definition = graph.get_subgraph(source_key) if source_key else None
        if definition is None:
            raise ValueError(
                f"Node '{node_id}' has no macro interior to detach; "
                f"only a placement whose template resolved can be detached."
            )

        template_key = getattr(definition, "template_key", None)
        if template_key is None:
            raise ValueError(f"Node '{node_id}' is already a Group, not a macro placement")

        serialized = card.serialize(include_data=True)
        raw_position = serialized.get("position") or [0.0, 0.0]
        position = (float(raw_position[0]), float(raw_position[1]))

        # The macro's own name, so the Group opens under the name the user knows
        # it by rather than the generic Graph-node label.
        label = definition.label or ""
        try:
            label = str(card.node.props.label or "") or label
        except Exception:
            pass

        edges = [
            (edge.source_node_id, edge.outlet_port_id, edge.sink_node_id, edge.inlet_port_id)
            for edge in graph._get_all_edges(node_id)
        ]

        self.subgraph_key = graph.generate_unique_subgraph_key()
        self.card_node_id = graph.generate_unique_node_id(card_registry_key)

        node_data: Dict[str, Any] = {"store": {SUBGRAPH_KEY: self.subgraph_key}}
        if label:
            node_data["props"] = {"values": {"label": label}}

        actions: List[IAction] = [
            _AdoptTemplateInteriorAction(
                graph=graph,
                source_key=source_key,
                target_key=self.subgraph_key,
                template_key=template_key,
            ),
            RemoveElementsAction(graph=graph, nodes=[node_id]),
            AddNodeAction(
                graph=graph,
                registry_key=card_registry_key,
                position=position,
                node_data=node_data,
                node_id=self.card_node_id,
            ),
        ]

        for source_node_id, outlet_port_id, sink_node_id, inlet_port_id in edges:
            if sink_node_id == node_id:
                actions.append(
                    AddEdgeAction(
                        graph=graph,
                        source_node_id=source_node_id,
                        outlet_pin_id=outlet_port_id,
                        sink_node_id=self.card_node_id,
                        inlet_pin_id=inlet_port_id,
                    )
                )
            else:
                actions.append(
                    AddEdgeAction(
                        graph=graph,
                        source_node_id=self.card_node_id,
                        outlet_pin_id=outlet_port_id,
                        sink_node_id=sink_node_id,
                        inlet_pin_id=inlet_port_id,
                    )
                )

        super().__init__(actions, description or "Detach from Macro")


class PromoteGroupToMacroAction(CompositeAction):
    """Swap a Group's card for a placement of the macro it was written to.

    The file is already on disk and registered when this runs — writing it is
    the promote pipeline's job, not the undo stack's. This composite (one
    undoable unit):

    1. removes the Group's card, which takes its edges with it, and drops the
       Subgraph definition that served it,
    2. creates the placement at the same position, under the macro's registry
       key,
    3. re-attaches each of the card's edges to the placement's matching pin.

    Pin ids survive the swap untouched: both cards derive them from the same
    boundary ports through ``card_port_id``, and the placement's interior is
    instantiated from the document the Group's Subgraph just became. So an
    edge re-attaches by the id it already had.

    Undo restores the Group, its definition and its edges. **The file stays** —
    it is not this action's to remove, and a macro that other graphs may
    already place must not vanish because one promotion was undone.

    Raises:
        ValueError: If ``node_id`` is not a Graph-node with a Subgraph bound.
    """

    def __init__(
        self,
        graph: BaseGraph,
        node_id: str,
        macro_registry_key: str,
        description: Optional[str] = None,
    ):
        from ...graph.subgraph import SubgraphDefinition

        self.graph = graph

        card = graph.get_node_wrapper(node_id)
        if card is None:
            raise ValueError(f"Node '{node_id}' not found; cannot promote")

        resolve = getattr(card.node, "resolve_definition", None)
        definition = resolve() if resolve is not None else None
        if not isinstance(definition, SubgraphDefinition):
            raise ValueError(f"Node '{node_id}' is not a Graph-node with a Subgraph; cannot promote")

        serialized = card.serialize(include_data=True)
        raw_position = serialized.get("position") or [0.0, 0.0]
        position = (float(raw_position[0]), float(raw_position[1]))

        try:
            label = str(card.node.props.label or "")
        except Exception:
            label = ""

        # Captured while the card is still in the graph: the removal below
        # takes its edges with it.
        edges = [
            (edge.source_node_id, edge.outlet_port_id, edge.sink_node_id, edge.inlet_port_id)
            for edge in graph._get_all_edges(node_id)
        ]

        self.placement_node_id = graph.generate_unique_node_id(macro_registry_key)

        # The label the user gave this card is carried over as a prop, so a
        # renamed Group does not lose its name to the macro's own. Props
        # deserialize from the `values` bag, not from a flat dict.
        node_data: Dict[str, Any] = {}
        if label:
            node_data["props"] = {"values": {"label": label}}

        actions: List[IAction] = [
            RemoveElementsAction(graph=graph, nodes=[node_id]),
            _DropSubgraphAction(graph=graph, key=definition.key),
            AddNodeAction(
                graph=graph,
                registry_key=macro_registry_key,
                position=position,
                node_data=node_data,
                node_id=self.placement_node_id,
            ),
            # After the card, so its undo runs before the card is removed —
            # while the card, and the interior it built, are still standing.
            _DiscardTemplateInteriorAction(graph=graph, node_id=self.placement_node_id),
        ]

        for source_node_id, outlet_port_id, sink_node_id, inlet_port_id in edges:
            if sink_node_id == node_id:
                actions.append(
                    AddEdgeAction(
                        graph=graph,
                        source_node_id=source_node_id,
                        outlet_pin_id=outlet_port_id,
                        sink_node_id=self.placement_node_id,
                        inlet_pin_id=inlet_port_id,
                    )
                )
            else:
                actions.append(
                    AddEdgeAction(
                        graph=graph,
                        source_node_id=self.placement_node_id,
                        outlet_pin_id=outlet_port_id,
                        sink_node_id=sink_node_id,
                        inlet_pin_id=inlet_port_id,
                    )
                )

        super().__init__(actions, description or "Promote to Macro")


def _callback_edge_partners(graph: BaseGraph, selected: List[str]) -> List[str]:
    """The nodes outside ``selected`` that a callback edge joins to one inside it.

    A callback edge carries its subscription as a port value, read from the
    sink's pool. A boundary node cannot relay it: the copy would re-key the
    pool entry by its own edge, and unlinking the outer edge clears only the
    outer port's pool, leaving the interior holding a subscription to a
    listener that is no longer connected. Both directions are reported — a
    Group can no more import a callback than export one.
    """
    from ...types.enums import FlowType

    inside = set(selected)
    partners: List[str] = []
    for node_id in selected:
        for edge in graph._get_all_edges(node_id):
            if edge.edge_type is not FlowType.CALLBACK:
                continue
            other = edge.sink_node_id if edge.source_node_id == node_id else edge.source_node_id
            if other not in inside:
                partners.append(other)
    return sorted(set(partners))


#: How far outside the contents' bounding box a boundary node sits.
_BOUNDARY_MARGIN = 360.0


def _boundary_positions(
    nodes: Dict[str, Any],
) -> Tuple[Tuple[float, float], Tuple[float, float]]:
    """Where the Subgraph Input and Output go, flanking the serialized ``nodes``.

    The Input sits before the contents and the Output after them, both centred
    on the contents' vertical extent, so a collapsed selection opens with its
    interface either side of it rather than two cards stacked at the canvas
    default.

    Returns:
        ``(input_position, output_position)`` as ``(x, y)`` pairs.
    """
    positions = [node.get("position") or [0.0, 0.0] for node in nodes.values()]
    if not positions:
        return ((3750.0 - _BOUNDARY_MARGIN, 3750.0), (3750.0 + _BOUNDARY_MARGIN, 3750.0))

    xs = [float(p[0]) for p in positions]
    ys = [float(p[1]) for p in positions]
    middle_y = (min(ys) + max(ys)) / 2
    return (
        (min(xs) - _BOUNDARY_MARGIN, middle_y),
        (max(xs) + _BOUNDARY_MARGIN, middle_y),
    )


def _centroid(nodes: Dict[str, Any]) -> Tuple[float, float]:
    """The average position of the serialized ``nodes``, or the canvas middle if empty."""
    positions = [node.get("position") or [0.0, 0.0] for node in nodes.values()]
    if not positions:
        return (3750.0, 3750.0)
    return (
        sum(float(p[0]) for p in positions) / len(positions),
        sum(float(p[1]) for p in positions) / len(positions),
    )


def _claim(seen: set, key: Tuple[str, str, str, str]) -> bool:
    """Record ``key`` and report whether it is the first time it was seen."""
    if key in seen:
        return False
    seen.add(key)
    return True
