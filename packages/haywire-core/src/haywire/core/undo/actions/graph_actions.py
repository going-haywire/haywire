"""
Graph-specific actions for the Haywire undo system.

This module contains actions that operate on the graph structure,
including node and edge manipulation, positioning, and selection.
"""

import copy
from typing import Any, Optional, Dict, List, Tuple
from dataclasses import dataclass

from ...node import NodeWrapper
from ...graph.base import BaseGraph
from ...edge.edge_wrapper import EdgeWrapper
from ....ui.utils import generate_edge_uuid
from ..base_action import ActionBase, CompositeAction
from ..interfaces import IAction

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

        # 1. Compute paste offset from the stored bounding box.
        bbox = payload.get("bounding_box") or {}
        off_x = paste_x - bbox.get("min_x", 0.0)
        off_y = paste_y - bbox.get("min_y", 0.0)

        actions: List[IAction] = []

        # New element ids, exposed so the paste handler can auto-select the
        # freshly pasted subgraph on the canvas.
        self.new_node_ids: List[str] = []
        self.new_edge_ids: List[str] = []

        # 2. Mint new ids + build child AddNodeActions (no registry_key
        #    validation — unknown types become placeholders, like file load).
        id_map: Dict[str, str] = {}
        for old_id, node in nodes.items():
            new_id = graph.generate_unique_node_id()
            id_map[old_id] = new_id
            self.new_node_ids.append(new_id)
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

            actions.append(
                AddNodeAction(
                    graph=graph,
                    registry_key=node["registry_key"],
                    position=(new_x, new_y),
                    node_data=node_data,
                    node_id=new_id,
                )
            )

        # 3. Remap edges through id_map (both endpoints guaranteed present by
        #    the both-endpoints copy rule; skip defensively if not).
        for edge in edges.values():
            src = id_map.get(edge["source_node_id"])
            sink = id_map.get(edge["sink_node_id"])
            if src is None or sink is None:
                continue
            outlet = edge["outlet_port_id"]
            inlet = edge["inlet_port_id"]
            self.new_edge_ids.append(generate_edge_uuid(src, outlet, sink, inlet))
            actions.append(
                AddEdgeAction(
                    graph=graph,
                    source_node_id=src,
                    outlet_pin_id=outlet,
                    sink_node_id=sink,
                    inlet_pin_id=inlet,
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
        new_node_id = graph.generate_unique_node_id(prefix="reroute")
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
                if self.name in type(bag)._property_settings():
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
