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
    from haywire.core.node.node_wrapper import NodeWrapper
    from haywire.core.execution.event_source import EventSource
    from haywire.core.execution.scheduler import FlowScheduler

logger = logging.getLogger(__name__)


@dataclass
class ControlNodeInfo:
    """
    Navigation information for a control node in the flow.
    
    Contains:
    - Node wrapper reference
    - Outlet mapping (outlet_pin_id → (next_node_id, inlet_port_id))
    - Loopback flag
    - Localized data flow for this node
    """
    node_wrapper: 'NodeWrapper'
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
    execution_sequence: List['NodeWrapper'] = field(default_factory=list)
    """Ordered list of data node wrappers to evaluate"""
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
    entry_node: 'NodeWrapper'
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
        entry_event_node: 'NodeWrapper',
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
        
        # Cache for node wrappers (populated on first access after assembly)
        self._all_node_wrappers_cache: Optional[List['NodeWrapper']] = None
        self._nodes_with_on_startup_cache: Optional[List['NodeWrapper']] = None
        self._nodes_with_on_shutdown_cache: Optional[List['NodeWrapper']] = None
        self._nodes_with_on_frame_start_cache: Optional[List['NodeWrapper']] = None
        self._nodes_with_on_frame_end_cache: Optional[List['NodeWrapper']] = None
        
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
    
    def get_all_node_wrappers(self) -> List['NodeWrapper']:
        """
        Get all node wrappers (control + data) in this flow.
        
        Returns:
            List of all NodeWrapper instances, including:
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
        if self._all_node_wrappers_cache is not None:
            return self._all_node_wrappers_cache
        
        # Build the list
        wrappers = []
        seen_wrappers: Set[str] = set()
        
        # Add entry event node
        wrappers.append(self.entry_event_node)
        seen_wrappers.add(self.entry_event_node.node_id)
        
        # Add all control nodes and their data flows
        for node_info in self.control_graph.control_nodes.values():
            # Add control node
            if node_info.node_wrapper.node_id not in seen_wrappers:
                wrappers.append(node_info.node_wrapper)
                seen_wrappers.add(node_info.node_wrapper.node_id)
            
            # Add data nodes from localized data flow
            if node_info.localized_data_flow:
                for data_wrapper in (
                    node_info.localized_data_flow.execution_sequence
                ):
                    if data_wrapper.node_id not in seen_wrappers:
                        wrappers.append(data_wrapper)
                        seen_wrappers.add(data_wrapper.node_id)
        
        # Cache and return
        self._all_node_wrappers_cache = wrappers
        return wrappers
    
    def _is_method_overridden(
        self, 
        wrapper: 'NodeWrapper', 
        method_name: str
    ) -> bool:
        """
        Check if node has overridden a lifecycle method from BaseNode.
        
        Args:
            wrapper: Node wrapper to check
            method_name: Name of the method to check
        
        Returns:
            True if the method is overridden from BaseNode
        
        Examples:
            is_overridden = self._is_method_overridden(
                wrapper, 'on_startup'
            )
        """
        node_class = type(wrapper.node)
        from haywire.core.node.base import BaseNode
        return (
            getattr(node_class, method_name) 
            is not getattr(BaseNode, method_name)
        )
    
    def get_nodes_with_on_startup(self) -> List['NodeWrapper']:
        """
        Get node wrappers that have overridden on_startup from BaseNode.
        
        Filters nodes to only those that implement custom startup logic,
        avoiding unnecessary method calls on nodes using default no-op.
        
        Returns:
            List of NodeWrapper instances with overridden on_startup
        
        Examples:
            for wrapper in flow.get_nodes_with_on_startup():
                wrapper.node.on_startup(context)
        """
        if self._nodes_with_on_startup_cache is not None:
            return self._nodes_with_on_startup_cache
        
        filtered = [
            w for w in self.get_all_node_wrappers()
            if self._is_method_overridden(w, 'on_startup')
        ]
        self._nodes_with_on_startup_cache = filtered
        return filtered
    
    def get_nodes_with_on_shutdown(self) -> List['NodeWrapper']:
        """
        Get node wrappers that have overridden on_shutdown from BaseNode.
        
        Filters nodes to only those that implement custom shutdown logic,
        avoiding unnecessary method calls on nodes using default no-op.
        
        Returns:
            List of NodeWrapper instances with overridden on_shutdown
        
        Examples:
            for wrapper in flow.get_nodes_with_on_shutdown():
                wrapper.node.on_shutdown(context)
        """
        if self._nodes_with_on_shutdown_cache is not None:
            return self._nodes_with_on_shutdown_cache
        
        filtered = [
            w for w in self.get_all_node_wrappers()
            if self._is_method_overridden(w, 'on_shutdown')
        ]
        self._nodes_with_on_shutdown_cache = filtered
        return filtered
    
    def get_nodes_with_on_frame_start(self) -> List['NodeWrapper']:
        """
        Get node wrappers that have overridden on_frame_start from BaseNode.
        
        Filters nodes to only those that implement custom per-frame start
        logic, avoiding unnecessary method calls on nodes using default
        no-op.
        
        Returns:
            List of NodeWrapper instances with overridden on_frame_start
        
        Examples:
            for wrapper in flow.get_nodes_with_on_frame_start():
                wrapper.node.on_frame_start(context)
        """
        if self._nodes_with_on_frame_start_cache is not None:
            return self._nodes_with_on_frame_start_cache
        
        filtered = [
            w for w in self.get_all_node_wrappers()
            if self._is_method_overridden(w, 'on_frame_start')
        ]
        self._nodes_with_on_frame_start_cache = filtered
        return filtered
    
    def get_nodes_with_on_frame_end(self) -> List['NodeWrapper']:
        """
        Get node wrappers that have overridden on_frame_end from BaseNode.
        
        Filters nodes to only those that implement custom per-frame end
        logic, avoiding unnecessary method calls on nodes using default
        no-op.
        
        Returns:
            List of NodeWrapper instances with overridden on_frame_end
        
        Examples:
            for wrapper in flow.get_nodes_with_on_frame_end():
                wrapper.node.on_frame_end(context)
        """
        if self._nodes_with_on_frame_end_cache is not None:
            return self._nodes_with_on_frame_end_cache
        
        filtered = [
            w for w in self.get_all_node_wrappers()
            if self._is_method_overridden(w, 'on_frame_end')
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
