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
    - Outlet mapping (outlet_pin_id → next_node_id)
    - Loopback flag
    - Localized data flow for this node
    """
    node_wrapper: 'NodeWrapper'
    outlet_map: Dict[str, str] = field(default_factory=dict)
    """Maps outlet port IDs to next node IDs"""
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


@dataclass
class LoopbackFrame:
    """
    Stack frame for loopback node tracking.
    
    When a loopback node is encountered, we push a frame onto the
    loopback stack. If a branch ends without an output node, we
    pop frames until we find a loopback node to return to.
    """
    node_id: str
    """ID of the loopback node"""
    done_index: int
    """Index in done_stack where this node was executed"""


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
    
    def __str__(self) -> str:
        return (
            f"Flow(id={self.flow_id}, "
            f"event={self.event_subscription}, "
            f"assembled={self.is_assembled()})"
        )
    
    def __repr__(self) -> str:
        return self.__str__()
