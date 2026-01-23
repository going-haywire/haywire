"""
Flow Assembly Manager - Coordinates flow assembly from graphs.

The FlowAssemblyManager is responsible for:
1. Identifying flows in a graph (by event nodes)
2. Building control flow graphs
3. Building localized data flows
4. Managing assembly cache
5. Just-in-time reassembly on graph changes
"""
from __future__ import annotations
from typing import Dict, List, Optional, Set, TYPE_CHECKING
from dataclasses import dataclass
from datetime import datetime
import logging

if TYPE_CHECKING:
    from haywire.core.graph.base import BaseGraph
    from haywire.core.execution.flow import Flow
    from haywire.core.node.node_wrapper import NodeWrapper

from haywire.core.assembly.control_flow_builder import ControlFlowBuilder
from haywire.core.assembly.data_flow_builder import DataFlowBuilder
from haywire.core.execution.flow import Flow

logger = logging.getLogger(__name__)


@dataclass
class AssemblyMetadata:
    """Metadata about an assembled flow"""
    flow_id: str
    timestamp: datetime
    node_count: int
    event_node_id: str


class FlowAssemblyManager:
    """
    Manages assembly of graphs into executable flows.
    
    Responsibilities:
    - Identify event nodes and separate flows
    - Coordinate control and data flow builders
    - Cache assembled flows
    - Handle JIT reassembly on graph changes
    """
    
    def __init__(self):
        """Initialize assembly manager"""
        self.assembled_flows: Dict[str, Flow] = {}
        """Cache of assembled flows: flow_id → Flow"""
        
        self.assembly_cache: Dict[str, AssemblyMetadata] = {}
        """Assembly metadata: flow_id → AssemblyMetadata"""
        
        self.dirty_flows: Set[str] = set()
        """Flow IDs that need reassembly"""
        
        logger.debug("FlowAssemblyManager initialized")
    
    def assemble_graph(self, graph: 'BaseGraph') -> List[Flow]:
        """
        Assemble all flows in a graph.
        
        This is the main entry point for assembly. It:
        1. Validates the graph
        2. Identifies event nodes
        3. Builds a flow for each event node
        4. Caches assembled flows
        
        Args:
            graph: Graph to assemble
            
        Returns:
            List of assembled flows
        """
        logger.info(f"Assembling graph: {graph.graph_id}")
        
        # Clear previous assembly
        self.assembled_flows.clear()
        self.assembly_cache.clear()
        self.dirty_flows.clear()
        
        # Validate graph
        validation_errors = self._validate_graph(graph)
        if validation_errors:
            error_msg = "Graph validation failed:\n" + "\n".join(validation_errors)
            logger.error(error_msg)
            raise RuntimeError(error_msg)
        
        # Identify event nodes
        event_nodes = self._identify_event_nodes(graph)
        
        if not event_nodes:
            logger.warning(f"No event nodes found in graph {graph.graph_id}")
            return []
        
        logger.info(f"Found {len(event_nodes)} event nodes")
        
        # Build a flow for each event node
        flows = []
        for event_node in event_nodes:
            try:
                flow = self._assemble_flow(event_node, graph)
                flows.append(flow)
                
                # Cache flow
                self.assembled_flows[flow.flow_id] = flow
                self.assembly_cache[flow.flow_id] = AssemblyMetadata(
                    flow_id=flow.flow_id,
                    timestamp=flow.assembly_timestamp,
                    node_count=len(flow.get_control_node_ids()),
                    event_node_id=event_node.node_id
                )
                
            except Exception as e:
                logger.error(
                    f"Failed to assemble flow from event node {event_node.node_id}: {e}",
                    exc_info=True
                )
                raise
        
        logger.info(f"Assembly complete: {len(flows)} flows")
        
        return flows
    
    def _validate_graph(self, graph: 'BaseGraph') -> List[str]:
        """
        Validate graph structure before assembly.
        
        Args:
            graph: Graph to validate
            
        Returns:
            List of validation errors (empty if valid)
        """
        errors = []
        
        # Check for duplicate event nodes of same type
        event_nodes = self._identify_event_nodes(graph)
        event_types: Dict[str, List[str]] = {}
        
        for wrapper in event_nodes:
            if hasattr(wrapper.node, 'event_subscription'):
                key = wrapper.node.event_subscription.get_subscription_key()
                if key not in event_types:
                    event_types[key] = []
                event_types[key].append(wrapper.node_id)
        
        for event_type, node_ids in event_types.items():
            if len(node_ids) > 1:
                errors.append(
                    f"Multiple event nodes listening for '{event_type}': {node_ids}. "
                    f"Only one event node per event type is allowed."
                )
        
        # Additional validations can be added here
        # - Check for Graph-nodes with missing Source/Sink
        # - Check for invalid node configurations
        # etc.
        
        return errors
    
    def _identify_event_nodes(self, graph: 'BaseGraph') -> List['NodeWrapper']:
        """
        Identify all event nodes in the graph.
        
        Args:
            graph: Graph to search
            
        Returns:
            List of event node wrappers
        """
        event_nodes = []
        
        for wrapper in graph.node_wrappers.values():
            # Check if node is an event node
            if wrapper.node.behavior.is_event_node:
                event_nodes.append(wrapper)
        
        return event_nodes
    
    def _assemble_flow(
        self,
        event_node: 'NodeWrapper',
        graph: 'BaseGraph'
    ) -> Flow:
        """
        Assemble a complete flow from an event node.
        
        Args:
            event_node: Event node starting the flow
            graph: Parent graph
            
        Returns:
            Assembled flow
        """
        logger.debug(f"Assembling flow from event node {event_node.node_id}")
        
        # Get event subscription
        if not hasattr(event_node.node, 'event_subscription'):
            raise RuntimeError(
                f"Event node {event_node.node_id} has no event_subscription"
            )
        
        event_subscription = event_node.node.event_subscription
        
        # Create flow
        flow = Flow(
            flow_id=f"flow_{event_node.node_id}",
            entry_event_node=event_node,
            event_subscription=event_subscription,
            graph_ref=graph
        )
        
        # Build control flow graph
        control_graph = ControlFlowBuilder.build(event_node, graph)
        flow.control_graph = control_graph
        
        # Build localized data flows for each control node
        for node_id, node_info in control_graph.control_nodes.items():
            try:
                localized_flow = DataFlowBuilder.build_localized(
                    node_info.node_wrapper,
                    control_graph,
                    graph
                )
                node_info.localized_data_flow = localized_flow
                
            except Exception as e:
                logger.error(
                    f"Failed to build data flow for {node_id}: {e}",
                    exc_info=True
                )
                raise
        
        logger.debug(f"Flow assembled: {flow}")
        
        return flow
    
    def get_flow(self, flow_id: str) -> Optional[Flow]:
        """
        Get an assembled flow by ID.
        
        Args:
            flow_id: Flow ID
            
        Returns:
            Flow if found, None otherwise
        """
        return self.assembled_flows.get(flow_id)
    
    def get_flows_for_event(self, subscription_key: str) -> List[Flow]:
        """
        Get all flows listening for a specific event.
        
        Args:
            subscription_key: Event subscription key
            
        Returns:
            List of flows listening for this event
        """
        matching_flows = []
        
        for flow in self.assembled_flows.values():
            if flow.get_subscription_key() == subscription_key:
                matching_flows.append(flow)
        
        return matching_flows
    
    def mark_flow_dirty(self, flow_id: str):
        """
        Mark a flow as needing reassembly.
        
        Args:
            flow_id: Flow ID to mark dirty
        """
        self.dirty_flows.add(flow_id)
        logger.debug(f"Flow {flow_id} marked dirty")
    
    def reassemble_dirty_flows(self, graph: 'BaseGraph') -> List[Flow]:
        """
        Reassemble all dirty flows.
        
        This is called by JIT assembly manager when graph changes.
        
        Args:
            graph: Parent graph
            
        Returns:
            List of reassembled flows
        """
        if not self.dirty_flows:
            return []
        
        logger.info(f"Reassembling {len(self.dirty_flows)} dirty flows")
        
        reassembled = []
        
        for flow_id in list(self.dirty_flows):
            try:
                # Get event node for this flow
                metadata = self.assembly_cache.get(flow_id)
                if not metadata:
                    logger.warning(f"No metadata for flow {flow_id}, skipping")
                    continue
                
                event_node = graph.get_node_wrapper(metadata.event_node_id)
                if not event_node:
                    logger.warning(
                        f"Event node {metadata.event_node_id} not found, "
                        f"removing flow {flow_id}"
                    )
                    self.assembled_flows.pop(flow_id, None)
                    self.assembly_cache.pop(flow_id, None)
                    continue
                
                # Reassemble
                flow = self._assemble_flow(event_node, graph)
                
                # Update cache
                self.assembled_flows[flow_id] = flow
                self.assembly_cache[flow_id] = AssemblyMetadata(
                    flow_id=flow.flow_id,
                    timestamp=flow.assembly_timestamp,
                    node_count=len(flow.get_control_node_ids()),
                    event_node_id=event_node.node_id
                )
                
                reassembled.append(flow)
                
            except Exception as e:
                logger.error(
                    f"Failed to reassemble flow {flow_id}: {e}",
                    exc_info=True
                )
        
        # Clear dirty flags
        self.dirty_flows.clear()
        
        logger.info(f"Reassembled {len(reassembled)} flows")
        
        return reassembled
    
    def get_statistics(self) -> Dict:
        """
        Get assembly statistics.
        
        Returns:
            Dictionary with statistics
        """
        return {
            'total_flows': len(self.assembled_flows),
            'dirty_flows': len(self.dirty_flows),
            'flows': [
                {
                    'flow_id': flow_id,
                    'event_type': flow.event_subscription.get_subscription_key(),
                    'node_count': len(flow.get_control_node_ids()),
                    'assembled_at': metadata.timestamp.isoformat()
                }
                for flow_id, flow in self.assembled_flows.items()
                if (metadata := self.assembly_cache.get(flow_id))
            ]
        }
