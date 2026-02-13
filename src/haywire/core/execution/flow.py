"""
Flow - Executable representation of a graph's control and data flows.

A Flow is the assembled, executable form of a graph. It contains:
- Entry event node
- Control flow graph (navigation structure)
- Localized data flows for each control node
- Flow scheduler for execution management
"""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Set, Any, TYPE_CHECKING
from datetime import datetime
import logging


if TYPE_CHECKING:
    from haywire.core.graph.base import BaseGraph
    from haywire.core.node import BaseNode
    from haywire.core.execution.event_source import EventSource
    from haywire.core.execution.scheduler import FlowScheduler

logger = logging.getLogger(__name__)


@dataclass
class ControlNodeInfo:
    """
    Navigation information for a control node in the flow.
    
    Contains:
    - Node reference (BaseNode)
    - Outlet mapping (outlet_pin_id → (next_node_id, inlet_port_id))
    - Loopback flag
    - Localized data flow for this node
    """
    node: 'BaseNode'
    outlet_map: Dict[str, tuple[str, str]] = field(default_factory=dict)
    """Maps outlet port IDs to (next_node_id, inlet_port_id) tuples"""
    is_loopback: bool = False
    """If True, this node expects branches to return to it"""
    localized_data_flow: Optional['LocalizedDataFlow'] = None
    """Data flow specific to this control node"""


@dataclass
class LocalizedDataFlow:
    """
    Data flow execution sequence for a specific control node.
    
    Contains the ordered list of data nodes that must be evaluated
    before the control node can execute.
    """
    control_node_id: str
    """ID of the control node this data flow belongs to"""
    execution_sequence: List['BaseNode'] = field(default_factory=list)
    """Ordered list of data nodes to evaluate"""
    eval_masks: Dict[str, int] = field(default_factory=dict)
    """Lazy evaluation masks: node_id → bitfield"""
    requires_lazy: bool = False
    """If True, lazy evaluation is possible for this flow"""
    
    def __str__(self) -> str:
        return (
            f"LocalizedDataFlow(control={self.control_node_id}, "
            f"nodes={len(self.execution_sequence)}, lazy={self.requires_lazy})"
        )


@dataclass
class ControlFlowGraph:
    """
    Control flow navigation graph.
    
    This is NOT an execution sequence - it's a navigation structure
    that the VM uses to determine which node to execute next based
    on runtime decisions (branch outcomes, loop conditions, etc).
    """
    entry_node: 'BaseNode'
    """The event node that starts this flow"""
    control_nodes: Dict[str, ControlNodeInfo] = field(default_factory=dict)
    """All control nodes in this flow: node_id → ControlNodeInfo"""
    topology_order: List[str] = field(default_factory=list)
    """Topological order for dependency analysis"""
    
    def get_node_info(self, node_id: str) -> Optional[ControlNodeInfo]:
        """Get control node info by ID"""
        return self.control_nodes.get(node_id)
    
    def __str__(self) -> str:
        return (
            f"ControlFlowGraph(entry={self.entry_node.node_id}, "
            f"nodes={len(self.control_nodes)})"
        )


class Flow:
    """
    Assembled, executable flow.
    
    A Flow represents one complete execution path through a graph,
    starting from an event node and containing all control and data
    flow information needed for execution.
    """
    
    def __init__(
        self,
        flow_id: str,
        entry_event_node: 'BaseNode',
        event_subscription: 'EventSource',
        graph_ref: 'BaseGraph'
    ):
        """
        Initialize a flow.
        
        Args:
            flow_id: Unique identifier for this flow
            entry_event_node: Event node that starts this flow
            event_subscription: What event triggers this flow
            graph_ref: Reference to parent graph
        """
        self.flow_id = flow_id
        self.entry_event_node = entry_event_node
        self.event_subscription = event_subscription
        self.graph_ref = graph_ref
        
        # Control flow structure (set during assembly)
        self.control_graph: Optional[ControlFlowGraph] = None
        
        # Execution management
        self.scheduler: Optional['FlowScheduler'] = None
        self.is_locked = False
        
        # Cache for nodes (populated on first access after assembly)
        self._all_nodes_cache: Optional[List['BaseNode']] = None
        self._nodes_with_on_startup_cache: Optional[List['BaseNode']] = None
        self._nodes_with_on_shutdown_cache: Optional[List['BaseNode']] = None
        self._nodes_with_on_frame_start_cache: Optional[List['BaseNode']] = None
        self._nodes_with_on_frame_end_cache: Optional[List['BaseNode']] = None
        
        # Metadata
        self.assembly_timestamp = datetime.now()
        
        logger.debug(
            f"Created Flow {flow_id} for event {event_subscription}"
        )
    
    def is_assembled(self) -> bool:
        """Check if flow has been fully assembled"""
        return self.control_graph is not None
    
    def get_entry_node_id(self) -> str:
        """Get ID of entry event node"""
        return self.entry_event_node.node_id
    
    def get_control_node_ids(self) -> List[str]:
        """Get list of all control node IDs in this flow"""
        if not self.control_graph:
            return []
        return list(self.control_graph.control_nodes.keys())
    
    def get_subscription_key(self) -> str:
        """Get subscription key for event registration"""
        return self.event_subscription.get_subscription_key()
    
    def get_all_nodes(self) -> List['BaseNode']:
        """
        Get all nodes (control + data) in this flow.
        
        Returns:
            List of all BaseNode instances, including:
            - Entry event node
            - All control nodes
            - All data nodes from localized data flows
            
        Note:
            Returns empty list if flow is not assembled.
            Result is cached after first call for performance.
            Ensures no duplicates in the returned list.
        """
        # Return empty list if not assembled
        if not self.is_assembled() or not self.control_graph:
            return []
        
        # Return cached result if available
        if self._all_nodes_cache is not None:
            return self._all_nodes_cache
        
        # Build the list
        nodes = []
        seen_nodes: Set[str] = set()
        
        # Add entry event node
        nodes.append(self.entry_event_node)
        seen_nodes.add(self.entry_event_node.node_id)
        
        # Add all control nodes and their data flows
        for node_info in self.control_graph.control_nodes.values():
            # Add control node
            if node_info.node.node_id not in seen_nodes:
                nodes.append(node_info.node)
                seen_nodes.add(node_info.node.node_id)
            
            # Add data nodes from localized data flow
            if node_info.localized_data_flow:
                for data_node in (
                    node_info.localized_data_flow.execution_sequence
                ):
                    if data_node.node_id not in seen_nodes:
                        nodes.append(data_node)
                        seen_nodes.add(data_node.node_id)
        
        # Cache and return
        self._all_nodes_cache = nodes
        return nodes
    
    def _is_method_overridden(
        self, 
        node: 'BaseNode', 
        method_name: str
    ) -> bool:
        """
        Check if node has overridden a lifecycle method from BaseNode.
        
        Args:
            node: Node to check
            method_name: Name of the method to check
        
        Returns:
            True if the method is overridden from BaseNode
        
        Examples:
            is_overridden = self._is_method_overridden(
                node, 'on_startup'
            )
        """
        node_class = type(node)
        from haywire.core.node.base import BaseNode
        return (
            getattr(node_class, method_name) 
            is not getattr(BaseNode, method_name)
        )
    
    def get_nodes_with_on_startup(self) -> List['BaseNode']:
        """
        Get nodes that have overridden on_startup from BaseNode.
        
        Filters nodes to only those that implement custom startup logic,
        avoiding unnecessary method calls on nodes using default no-op.
        
        Returns:
            List of BaseNode instances with overridden on_startup
        
        Examples:
            for node in flow.get_nodes_with_on_startup():
                node.on_startup(context)
        """
        if self._nodes_with_on_startup_cache is not None:
            return self._nodes_with_on_startup_cache
        
        filtered = [
            n for n in self.get_all_nodes()
            if self._is_method_overridden(n, 'on_startup')
        ]
        self._nodes_with_on_startup_cache = filtered
        return filtered
    
    def get_nodes_with_on_shutdown(self) -> List['BaseNode']:
        """
        Get nodes that have overridden on_shutdown from BaseNode.
        
        Filters nodes to only those that implement custom shutdown logic,
        avoiding unnecessary method calls on nodes using default no-op.
        
        Returns:
            List of BaseNode instances with overridden on_shutdown
        
        Examples:
            for node in flow.get_nodes_with_on_shutdown():
                node.on_shutdown(context)
        """
        if self._nodes_with_on_shutdown_cache is not None:
            return self._nodes_with_on_shutdown_cache
        
        filtered = [
            n for n in self.get_all_nodes()
            if self._is_method_overridden(n, 'on_shutdown')
        ]
        self._nodes_with_on_shutdown_cache = filtered
        return filtered
    
    def get_nodes_with_on_frame_start(self) -> List['BaseNode']:
        """
        Get nodes that have overridden on_frame_start from BaseNode.
        
        Filters nodes to only those that implement custom per-frame start
        logic, avoiding unnecessary method calls on nodes using default
        no-op.
        
        Returns:
            List of BaseNode instances with overridden on_frame_start
        
        Examples:
            for node in flow.get_nodes_with_on_frame_start():
                node.on_frame_start(context)
        """
        if self._nodes_with_on_frame_start_cache is not None:
            return self._nodes_with_on_frame_start_cache
        
        filtered = [
            n for n in self.get_all_nodes()
            if self._is_method_overridden(n, 'on_frame_start')
        ]
        self._nodes_with_on_frame_start_cache = filtered
        return filtered
    
    def get_nodes_with_on_frame_end(self) -> List['BaseNode']:
        """
        Get nodes that have overridden on_frame_end from BaseNode.
        
        Filters nodes to only those that implement custom per-frame end
        logic, avoiding unnecessary method calls on nodes using default
        no-op.
        
        Returns:
            List of BaseNode instances with overridden on_frame_end
        
        Examples:
            for node in flow.get_nodes_with_on_frame_end():
                node.on_frame_end(context)
        """
        if self._nodes_with_on_frame_end_cache is not None:
            return self._nodes_with_on_frame_end_cache
        
        filtered = [
            n for n in self.get_all_nodes()
            if self._is_method_overridden(n, 'on_frame_end')
        ]
        self._nodes_with_on_frame_end_cache = filtered
        return filtered
    
    def __str__(self) -> str:
        return (
            f"Flow(id={self.flow_id}, "
            f"event={self.event_subscription}, "
            f"assembled={self.is_assembled()})"
        )
    
    def __repr__(self) -> str:
        return self.__str__()
