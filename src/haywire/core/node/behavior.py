# haywire/core/node/behavior.py
"""
Node behavior flags - immutable class-level characteristics.
"""

from dataclasses import dataclass


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
            is_control_node=True,
            is_loopback=True,
            is_pure=False
        )
        class ForLoopNode(BaseNode):
            ...
    
    Access at runtime:
        if self.behavior.is_control_node:
            ...
    """
    
    is_control_node: bool = False
    """
    If True, this node participates in control flow.
    Control nodes have execution (EXEC) ports and determine
    the order of execution in the graph.
    """
    
    is_data_node: bool = False
    """
    If True, this node processes data.
    Data nodes have data ports and transform inputs to outputs.
    A node can be both a control node and a data node.
    """
    
    is_event_node: bool = False
    """
    If True, this node is an event entry point.
    Event nodes start execution flows (e.g., OnStart, OnClick).
    Only one event node can trigger a flow at a time.
    """
    
    is_output_node: bool = False
    """
    If True, this node is a terminal output.
    Output nodes represent final results (e.g., Display, Export).
    Used by the execution engine to determine execution targets.
    """
    
    is_stateful: bool = False
    """
    TODO: Do we need this?
    If True, this node maintains state between executions.
    Stateful nodes may produce different outputs even with
    identical inputs (e.g., counters, accumulators).
    """
    
    is_loopback: bool = False
    """
    If True, control flow can return to this node.
    Used for loop constructs (For, While, Sequence).
    Affects cycle detection in the execution engine.
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
    TODO: Do we need this?
    If True, this node's configuration can change at runtime.
    Mutable nodes may add/remove ports dynamically.
    """


# Fields that belong to NodeBehaviorFlags (used by @node decorator)
BEHAVIOR_FIELDS = frozenset({
    'is_control_node',
    'is_data_node', 
    'is_event_node',
    'is_output_node',
    'is_stateful',
    'is_loopback',
    'has_execute_async',
    'is_mutable',
    'is_thread_safe'
})