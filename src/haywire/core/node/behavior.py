# haywire/core/node/behavior.py
"""
Node behavior flags - immutable class-level characteristics.
"""

from dataclasses import dataclass
from enum import IntFlag, auto


class NodeType(IntFlag):
    """
    Bitwise flags for node behavior.
    
    Node types are mutually exclusive and determined by control port configuration:
    - DATA: 0 ctrl inlet / 0 ctrl outlet
    - CONTROL: 1 ctrl inlet / 1 ctrl outlet
    - EVENT: 0 ctrl inlet / 1 ctrl outlet
    - OUTPUT: 1 ctrl inlet / 0 ctrl outlet
    - LOOPBACK: 1 ctrl inlet / 2+ ctrl outlets (with loopback)
    
    Examples:
        @node(node_type=NodeType.EVENT)
        @node(node_type=NodeType.CONTROL)
        @node(node_type=NodeType.LOOPBACK)
        @node(node_type=NodeType.DATA)
    """
    DATA = auto()         # 0b00001 - Pure data processing
    CONTROL = auto()      # 0b00010 - Standard control flow
    EVENT = auto()        # 0b00100 - Flow entry point
    OUTPUT = auto()       # 0b01000 - Flow termination
    LOOPBACK = auto()     # 0b10000 - Loop constructs


@dataclass(frozen=True)
class NodeBehaviorFlags:
    """
    Immutable behavioral characteristics of a node class.
    
    These flags are set at class definition time via the @node decorator
    and cannot be changed at runtime. They define the fundamental nature
    of the node and how the execution engine treats it.
    
    Set via decorator:
        @node(
            label="My Loop Node",
            node_type=NodeType.LOOPBACK
        )
        class ForLoopNode(BaseNode):
            ...
    
    Access at runtime:
        if self.behavior.node_type & NodeType.CONTROL:
            ...
        
        if self.behavior.is_control_node:  # Computed property
            ...
    """

    node_type: NodeType = NodeType(0)
    """
    Primary node type classification.
    Determines control flow behavior and execution semantics.
    """
    
    is_stateful: bool = False
    """
    If True, this node maintains state between executions.
    Stateful nodes may produce different outputs even with
    identical inputs (e.g., counters, accumulators).
    """
    
    has_execute_async: bool = False
    """
    If True, this node supports asynchronous execution.
    Async nodes can yield control while waiting for I/O
    or long-running operations.
    """

    is_thread_safe: bool = False
    """
    If True, this node can safely run within a multithreaded
    flow execution.
    """

    is_mutable: bool = False
    """
    If True, this node's configuration can change at runtime.
    Mutable nodes may add/remove ports dynamically.
    """
    
    # =========================================================================
    # COMPUTED PROPERTIES - For backward compatibility and convenience
    # =========================================================================
    
    @property
    def is_control_node(self) -> bool:
        """True if node participates in control flow (CONTROL, EVENT, OUTPUT, LOOPBACK)."""
        return bool(self.node_type & (NodeType.CONTROL | NodeType.EVENT | NodeType.OUTPUT | NodeType.LOOPBACK))
    
    @property
    def is_data_node(self) -> bool:
        """True if node is a pure data node (DATA)."""
        return bool(self.node_type & NodeType.DATA)
    
    @property
    def is_event_node(self) -> bool:
        """True if node is a flow entry point (EVENT)."""
        return bool(self.node_type & NodeType.EVENT)
    
    @property
    def is_output_node(self) -> bool:
        """True if node is a flow termination (OUTPUT)."""
        return bool(self.node_type & NodeType.OUTPUT)
    
    @property
    def is_loopback(self) -> bool:
        """True if control flow can return to this node (LOOPBACK)."""
        return bool(self.node_type & NodeType.LOOPBACK)


# Fields that belong to NodeBehaviorFlags (used by @node decorator)
BEHAVIOR_FIELDS = frozenset({
    'node_type',
    'is_stateful',
    'has_execute_async',
    'is_mutable',
    'is_thread_safe'
})