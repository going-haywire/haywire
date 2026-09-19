# haywire/core/node/behavior.py
"""
Node behavior flags - immutable class-level characteristics.
"""

from dataclasses import dataclass
from enum import IntFlag


class NodeType(IntFlag):
    """Bitwise flags for node behavior.

    The types are mutually exclusive. What the structural validator enforces:

    - DATA: no pins on non-DATA ports, and at least one data outlet.
    - CONTROL: at least one control inlet and at least one control outlet. A
      control node may carry several control outlets — ``ControlSwitch`` has two.
    - EVENT: no inlets with pins, an ``event_subscription``, and at least one
      control outlet.
    - OUTPUT: a control node that ends a flow.
    - LOOPBACK: a control node carrying at least one outlet with
      ``needs_loopback=True`` (the loop body) and at least one with
      ``needs_loopback=False`` (the exit). Outlet *count* does not distinguish
      LOOPBACK from CONTROL; the flags do.
    - REROUTE: a pass-through node that splits an edge and bends a wire. It
      carries neither the DATA nor the CONTROL bit and may stay port-less until
      the edge-split action configures it; the structural validator checks it
      before the DATA/CONTROL rules and applies the looser reroute ones (a
      port-less state is valid, as is any single-FlowType passthrough pair).
      Supports DATA, CONTROL and CALLBACK edges.
    - BOUNDARY: a Subgraph Input or Subgraph Output node, defining the interface
      of a Subgraph. It carries neither the DATA nor the CONTROL bit — its role
      comes from the assembly context, so one pair of classes serves both data
      and control crossings. Like REROUTE it may stay port-less until the
      collapse action stamps its ports, and every port faces one direction.

    Examples:
        @node(node_type=NodeType.EVENT)
        @node(node_type=NodeType.CONTROL)
        @node(node_type=NodeType.LOOPBACK)
        @node(node_type=NodeType.DATA)
        @node(node_type=NodeType.REROUTE)
        @node(node_type=NodeType.BOUNDARY)
    """

    DATA = 1
    CONTROL = 2
    EVENT = 4 | CONTROL  # 6
    OUTPUT = 8 | CONTROL  # 10
    LOOPBACK = 16 | CONTROL  # 18
    REROUTE = 32  # standalone — no DATA or CONTROL bit
    BOUNDARY = 64  # standalone — no DATA or CONTROL bit


@dataclass(frozen=True)
class NodeBehaviorFlags:
    """An immutable set of behavioral characteristics.

    The ``@node`` decorator builds one per class, and every node is stamped
    with its class's at construction. The object itself never changes — a node
    whose shape decides its role replaces the whole set through
    ``BaseNode.set_node_type()``, which is the only field that may vary per
    instance. See ``NodeData.behavior``.

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
    """Primary node type classification; decides the node's control-flow behavior."""

    is_stateful: bool = False
    """If True, this node keeps state between executions, so identical inputs may
    produce different outputs (a counter, an accumulator)."""

    has_execute_async: bool = False
    """If True, this node supports asynchronous execution and can yield control
    while waiting on I/O or a long-running operation."""

    is_thread_safe: bool = False
    """If True, this node can safely run inside a multithreaded flow execution."""

    is_mutable: bool = False
    """If True, this node's configuration can change at runtime, adding or removing
    ports dynamically."""

    # =========================================================================
    # COMPUTED PROPERTIES
    # =========================================================================

    @property
    def is_control_node(self) -> bool:
        """True if node participates in control flow (CONTROL, EVENT, OUTPUT, LOOPBACK)."""
        return bool(NodeType.CONTROL in self.node_type)

    @property
    def is_data_node(self) -> bool:
        """True if node is a pure data node (DATA). A reroute node is not one."""
        return bool(NodeType.DATA in self.node_type)

    @property
    def is_reroute_node(self) -> bool:
        """True if node is a reroute (a DATA node permitting a port-less state)."""
        return bool(NodeType.REROUTE in self.node_type)

    @property
    def is_boundary_node(self) -> bool:
        """True if node defines a Subgraph's interface (BOUNDARY)."""
        return bool(NodeType.BOUNDARY in self.node_type)

    @property
    def is_event_node(self) -> bool:
        """True if node is a flow entry point (EVENT)."""
        return bool(NodeType.EVENT in self.node_type)

    @property
    def is_output_node(self) -> bool:
        """True if node is a flow termination (OUTPUT)."""
        return bool(NodeType.OUTPUT in self.node_type)

    @property
    def is_loopback(self) -> bool:
        """True if control flow can return to this node (LOOPBACK)."""
        return bool(NodeType.LOOPBACK in self.node_type)


# Fields that belong to NodeBehaviorFlags (used by @node decorator)
BEHAVIOR_FIELDS = frozenset(
    {"node_type", "is_stateful", "has_execute_async", "is_mutable", "is_thread_safe"}
)
