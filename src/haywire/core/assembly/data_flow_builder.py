"""
Data Flow Builder - Builds localized data flows for control nodes.

For each control node, this builder:
1. Backpropagates from data inlets
2. Identifies all required data nodes
3. Topologically sorts for execution order
4. Detects illegal data cycles
5. Handles lazy evaluation setup
"""
from __future__ import annotations
from typing import Dict, List, Set, TYPE_CHECKING
import logging

if TYPE_CHECKING:
    from haywire.core.graph.base import BaseGraph
    from haywire.core.node.base import BaseNode
    from haywire.core.execution.flow import LocalizedDataFlow, ControlFlowGraph

from haywire.core.types.enums import FlowType

logger = logging.getLogger(__name__)


class DataFlowBuilder:
    """
    Builds localized data flows for control nodes.
    
    Each control node gets its own data flow that determines which
    data nodes must be evaluated before the control node executes.
    """
    
    @staticmethod
    def build_localized(
        control_node: 'BaseNode',
        control_graph: 'ControlFlowGraph',
        graph: 'BaseGraph'
    ) -> 'LocalizedDataFlow':
        """
        Build localized data flow for a control node.
        
        Args:
            control_node: Control node to build data flow for
            control_graph: Control flow graph (for topology)
            graph: Parent graph
            
        Returns:
            LocalizedDataFlow with execution sequence
        """
        from haywire.core.execution.flow import LocalizedDataFlow
        
        logger.debug(
            f"Building localized data flow for {control_node.node_id}"
        )
        
        # Initialize data flow
        data_flow = LocalizedDataFlow(
            control_node_id=control_node.node_id
        )
        
        # Get all data inlets on control node
        data_inlets = [
            port for port in control_node.ports.values()
            if port.flow_type == FlowType.DATA and port.is_inlet()
        ]
        
        if not data_inlets:
            logger.debug(
                f"No data inlets on {control_node.node_id}"
            )
            return data_flow  # No data dependencies
        
        # Backpropagate from each inlet
        required_nodes: Set[str] = set()
        eval_masks: Dict[str, int] = {}
        
        for i, inlet in enumerate(data_inlets):
            # Create bit mask for this inlet (bit i set)
            inlet_mask = 1 << i
            
            # Backpropagate to find dependencies
            dependencies = DataFlowBuilder._backpropagate(
                control_node.node_id,
                inlet.id,
                graph,
                control_graph
            )
            
            # Update required nodes
            required_nodes.update(dependencies)
            
            # Update eval masks (OR together at merge points)
            for dep_node_id in dependencies:
                if dep_node_id not in eval_masks:
                    eval_masks[dep_node_id] = 0
                eval_masks[dep_node_id] |= inlet_mask
        
        # Check for cycles (not allowed in data flow, except through control)
        DataFlowBuilder._check_cycles(
            required_nodes,
            graph,
            control_graph
        )
        
        # Topological sort for execution order
        execution_sequence = DataFlowBuilder._topological_sort(
            required_nodes,
            graph
        )
        
        # Build data flow - convert node IDs to BaseNode instances
        data_flow.execution_sequence = [
            graph.get_node_wrapper(node_id).node
            for node_id in execution_sequence
            if graph.get_node_wrapper(node_id) is not None
        ]
        data_flow.eval_masks = eval_masks
        data_flow.requires_lazy = any(
            inlet.is_lazy for inlet in data_inlets
        )
        
        logger.debug(
            f"Localized data flow built: {len(execution_sequence)} nodes, "
            f"lazy={data_flow.requires_lazy}"
        )
        
        return data_flow
    
    @staticmethod
    def _backpropagate(
        start_node_id: str,
        inlet_id: str,
        graph: 'BaseGraph',
        control_graph: 'ControlFlowGraph'
    ) -> Set[str]:
        """
        Backpropagate from inlet to find all data dependencies.
        
        Args:
            start_node_id: Node containing the inlet
            inlet_id: Inlet port ID
            graph: Parent graph
            control_graph: Control flow graph (to stop at control nodes)
            
        Returns:
            Set of node IDs that are dependencies
        """
        dependencies: Set[str] = set()
        visited: Set[tuple] = set()  # (node_id, port_id) pairs
        
        # BFS queue: (node_id, inlet_id)
        queue: List[tuple] = [(start_node_id, inlet_id)]
        
        while queue:
            node_id, port_id = queue.pop(0)
            
            # Skip if visited
            if (node_id, port_id) in visited:
                continue
            visited.add((node_id, port_id))
            
            # Get edges connected to this inlet
            edge_wrappers = graph._get_edge_wrappers_for_port(node_id, port_id)
            
            for edge in edge_wrappers:
                # Follow data edge backwards to source
                source_node_id = edge.source_node_id
                source_port_id = edge.outlet_port_id
                
                # Check if source is a control node
                source_wrapper = graph.get_node_wrapper(source_node_id)
                if source_wrapper:
                    source_node = source_wrapper.node
                    is_control = any(
                        port.flow_type == FlowType.CONTROL
                        for port in source_node.ports.values()
                    )
                    
                    if is_control:
                        # Stop at control nodes (data doesn't backprop through them)
                        continue
                    
                    # Add to dependencies
                    dependencies.add(source_node_id)
                    
                    # Continue backpropagating from this node's inlets
                    source_inlets = [
                        port for port in source_node.ports.values()
                        if port.flow_type == FlowType.DATA and port.is_inlet()
                    ]
                    
                    for inlet in source_inlets:
                        queue.append((source_node_id, inlet.id))
        
        return dependencies
    
    @staticmethod
    def _check_cycles(
        node_ids: Set[str],
        graph: 'BaseGraph',
        control_graph: 'ControlFlowGraph'
    ):
        """
        Check for illegal cycles in data flow.
        
        Data cycles are not allowed unless they pass through a control node.
        
        Args:
            node_ids: Set of node IDs in data flow
            graph: Parent graph
            control_graph: Control flow graph
            
        Raises:
            RuntimeError: If illegal cycle detected
        """
        # Build adjacency list for these nodes
        adj: Dict[str, List[str]] = {node_id: [] for node_id in node_ids}
        
        for node_id in node_ids:
            node_wrapper = graph.get_node_wrapper(node_id)
            if not node_wrapper:
                continue
            
            node = node_wrapper.node
            
            # Get all data outlets
            outlets = [
                port for port in node.ports.values()
                if port.flow_type == FlowType.DATA and port.is_outlet()
            ]
            
            for outlet in outlets:
                # Get connected edges
                edges = graph._get_edge_wrappers_for_port(node_id, outlet.id)
                
                for edge in edges:
                    target_id = edge.sink_node_id
                    
                    # Only consider edges within our data flow
                    if target_id in node_ids:
                        adj[node_id].append(target_id)
        
        # DFS to detect cycles
        visited: Set[str] = set()
        rec_stack: Set[str] = set()
        
        def has_cycle(node_id: str) -> bool:
            visited.add(node_id)
            rec_stack.add(node_id)
            
            for neighbor in adj.get(node_id, []):
                if neighbor not in visited:
                    if has_cycle(neighbor):
                        return True
                elif neighbor in rec_stack:
                    return True  # Cycle detected
            
            rec_stack.remove(node_id)
            return False
        
        for node_id in node_ids:
            if node_id not in visited:
                if has_cycle(node_id):
                    raise RuntimeError(
                        "Illegal cycle detected in data flow for control node. "
                        "Data cycles are not allowed unless passing through "
                        "a control node."
                    )
    
    @staticmethod
    def _topological_sort(
        node_ids: Set[str],
        graph: 'BaseGraph'
    ) -> List[str]:
        """
        Topologically sort data nodes for execution order.
        
        Args:
            node_ids: Set of node IDs to sort
            graph: Parent graph
            
        Returns:
            List of node IDs in execution order
        """
        # Build adjacency list and in-degree
        adj: Dict[str, List[str]] = {node_id: [] for node_id in node_ids}
        in_degree: Dict[str, int] = {node_id: 0 for node_id in node_ids}
        
        for node_id in node_ids:
            node_wrapper = graph.get_node_wrapper(node_id)
            if not node_wrapper:
                continue
            
            node = node_wrapper.node
            
            # Get all data outlets
            outlets = [
                port for port in node.ports.values()
                if port.flow_type == FlowType.DATA and port.is_outlet()
            ]
            
            for outlet in outlets:
                edges = graph._get_edge_wrappers_for_port(node_id, outlet.id)
                
                for edge in edges:
                    target_id = edge.sink_node_id
                    
                    if target_id in node_ids:
                        adj[node_id].append(target_id)
                        in_degree[target_id] += 1
        
        # Kahn's algorithm
        queue = [node_id for node_id, degree in in_degree.items() if degree == 0]
        sorted_nodes = []
        
        while queue:
            current = queue.pop(0)
            sorted_nodes.append(current)
            
            for neighbor in adj[current]:
                in_degree[neighbor] -= 1
                if in_degree[neighbor] == 0:
                    queue.append(neighbor)
        
        if len(sorted_nodes) != len(node_ids):
            logger.warning(
                f"Topological sort incomplete: "
                f"{len(sorted_nodes)} of {len(node_ids)} nodes sorted. "
                f"This indicates a cycle (which should have been caught earlier)."
            )
        
        return sorted_nodes
