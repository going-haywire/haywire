"""
Control Flow Builder - Builds control flow navigation graphs.

The ControlFlowBuilder creates a navigation structure (not an execution
sequence) that the VM uses to determine which node to execute next based
on runtime decisions.
"""

from __future__ import annotations
from typing import Dict, List, Set, TYPE_CHECKING
import logging

from haywire.core.types.enums import FlowType, PortType

if TYPE_CHECKING:
    from haywire.core.graph.base import BaseGraph
    from haywire.core.node.base import BaseNode
    from haywire.core.execution.flow import ControlFlowGraph

from haywire.core.node.behavior import NodeType

logger = logging.getLogger(__name__)


class ControlFlowBuilder:
    """
    Builds control flow navigation graphs.

    Starting from an event node, this builder:
    1. Traverses all control connections
    2. Maps outlet pins to next node IDs
    3. Identifies loopback nodes
    4. Creates navigation structure for runtime
    """

    @staticmethod
    def build(event_node: "BaseNode", graph: "BaseGraph") -> "ControlFlowGraph":
        """
        Build control flow graph starting from event node.

        Args:
            event_node: Event node that starts the flow
            graph: Parent graph containing nodes and edges

        Returns:
            ControlFlowGraph navigation structure
        """
        from haywire.core.execution.flow import ControlFlowGraph, ControlNodeInfo

        logger.debug(f"Building control flow from event node {event_node.node_id}")

        # Initialize control flow graph
        control_graph = ControlFlowGraph(entry_node=event_node)

        # Track visited nodes (for cycle detection)
        visited: Set[str] = set()

        # BFS queue
        queue: List["BaseNode"] = [event_node]

        # Build navigation graph
        while queue:
            current = queue.pop(0)

            if current.wrapper.node_id in visited:
                continue  # Already processed (cycle)

            visited.add(current.wrapper.node_id)

            # Create info for this node
            info = ControlNodeInfo(node=current)

            # Mark loopback nodes
            if NodeType.LOOPBACK in current.behavior.node_type:
                info.is_loopback = True
                logger.debug(f"Node {current.wrapper.node_id} is loopback")

            # Get all control outlet ports
            control_outlets = current.get_ports(is_port_type=PortType.OUTLET, is_flow_type=FlowType.CONTROL)

            # Map each outlet to its connected node
            for outlet in control_outlets:
                # Get edges connected to this outlet
                edge_wrappers = outlet.get_valid_edges()

                # Control outlets should have at most one connection
                if edge_wrappers:
                    edge = edge_wrappers[0]  # Take first (should be only one)
                    next_node_id = edge.sink_node_id
                    inlet_port_id = edge.edge.inlet_port_id

                    # Record in outlet map: (next_node_id, inlet_port_id)
                    info.outlet_map[outlet.id] = (next_node_id, inlet_port_id)

                    logger.debug(
                        f"Outlet {current.wrapper.node_id}.{outlet.id} → {next_node_id}.{inlet_port_id}"
                    )

                    # Add next node to queue
                    next_wrapper = graph.get_node_wrapper(next_node_id)
                    if next_wrapper:
                        queue.append(next_wrapper.node)

            # Add to control graph
            control_graph.control_nodes[current.wrapper.node_id] = info

        logger.debug(f"Control flow built: {len(control_graph.control_nodes)} nodes")

        # Build topology order (for data flow assembly)
        control_graph.topology_order = ControlFlowBuilder._build_topology(control_graph)

        return control_graph

    @staticmethod
    def _build_topology(control_graph: "ControlFlowGraph") -> List[str]:
        """
        Build topological order of control nodes.

        This is used by data flow builder to determine which control
        nodes are "upstream" vs "downstream" to prevent illegal data
        cycles through control nodes.

        Args:
            control_graph: Control flow graph

        Returns:
            List of node IDs in topological order
        """
        # Build adjacency list
        adj: Dict[str, List[str]] = {}
        in_degree: Dict[str, int] = {}

        for node_id, info in control_graph.control_nodes.items():
            if node_id not in adj:
                adj[node_id] = []
            if node_id not in in_degree:
                in_degree[node_id] = 0

            # Add edges from this node
            for target_id, _inlet_id in info.outlet_map.values():
                if target_id not in adj:
                    adj[target_id] = []
                if target_id not in in_degree:
                    in_degree[target_id] = 0

                adj[node_id].append(target_id)
                in_degree[target_id] += 1

        # Kahn's algorithm for topological sort
        queue = [node_id for node_id, degree in in_degree.items() if degree == 0]
        topology = []

        while queue:
            current = queue.pop(0)
            topology.append(current)

            for neighbor in adj.get(current, []):
                in_degree[neighbor] -= 1
                if in_degree[neighbor] == 0:
                    queue.append(neighbor)

        # Note: If there are cycles, not all nodes will be in topology
        # This is okay for control flow (cycles are allowed)

        return topology
