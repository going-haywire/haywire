# haywire/core/graph/structural_validator.py
"""
Structural validation for Haywire graphs.

Validates domain-specific structural rules that go beyond formal validity:
- Event node constraints
- Control flow topology
- Data flow cycles
- Callback edge rules
"""
from __future__ import annotations
from typing import TYPE_CHECKING, List
import logging

from haywire.core.types import FlowType
from haywire.core.node.behavior import NodeType
from haywire.core.types.enums import PortType
from haywire.core.validation.interface import IStructuralValidator

if TYPE_CHECKING:
    from haywire.core.graph.base import BaseGraph
    from haywire.core.node.node_wrapper import NodeWrapper
    from haywire.core.edge.edge_wrapper import EdgeWrapper

logger = logging.getLogger(__name__)

class StructuralValidator(IStructuralValidator):
    """
    Validates structural constraints for Haywire graphs.
    
    This validator enforces domain-specific rules that define
    valid graph structures for execution. It can be subclassed
    to implement different structural requirements for different
    execution models.
    
    Responsibilities:
    - Event node constraint validation
    - Control flow topology validation
    - Data flow cycle detection
    - Callback edge constraint validation
    - Graph-wide consistency checks
    """
    
    def __init__(self, graph: 'BaseGraph'):
        """
        Initialize structural validator.
        
        Args:
            graph: The graph to validate
        """
        self.graph = graph
    
    # ========================================================================
    # NODE VALIDATION
    # ========================================================================
    
    def validate_node(
        self, wrapper: 'NodeWrapper'
    ) -> tuple[bool, str | None, list[str]]:
        """
        Validate structural constraints for a single node.
        
        This is called after node initialization but before adding to graph.
        
        Args:
            wrapper: NodeWrapper to validate
            
        Returns:
            Tuple of (is_valid, error_message, suggestions).
            Error message is None if valid.
            Suggestions is a list of actionable fixes.
        """
        node = wrapper.node

        # Check if this is an event node
        if NodeType.EVENT in node.behavior.node_type:
            return self._validate_event_node(wrapper)
        
        if NodeType.DATA in node.behavior.node_type:
            return self._validate_data_node(wrapper)
        
        # Check if this is a loopback node
        if NodeType.LOOPBACK in node.behavior.node_type:
            return self._validate_loopback_node(wrapper)
        
        # Regular nodes pass by default
        # (future: add other node-level structural checks here)
        return (True, None, [])
    
    def _validate_event_node(
        self, wrapper: 'NodeWrapper'
    ) -> tuple[bool, str | None, list[str]]:
        """
        Validate event node structural constraints.
        
        Rules:
        - No control inlets allowed (events are entry points)
        - Must have event_subscription set
        - Must have at least one control outlet
        
        Args:
            wrapper: Event node wrapper to validate
            
        Returns:
            Tuple of (is_valid, error_message, suggestions).
            Error message is None if valid.
            Suggestions is a list of actionable fixes.
        """
        node = wrapper.node
        
        # Check for inlets with pins (not allowed)
        inlets = node.get_ports(is_port_type=PortType.INLET, has_pin=True)
        if len(inlets) > 0:
            return (
                False,
                f"Event nodes cannot have inlets with pins. "
                f"Found: {[p.id for p in inlets]}",
                [
                    "Remove all inlets with pins from event node",
                    "Event nodes are entry points and cannot be triggered or modified by other nodes"
                ]
            )
        
        # Check event subscription
        if node.event_subscription is None:
            return (
                False,
                "Event node must have event_subscription set",
                [
                    "Set EVENT_SOURCE at class level",
                    "Or set self.event_subscription in initialize()"
                ]
            )
        
        # Check for at least one control outlet  
        if len(node.get_ports(is_port_type=PortType.OUTLET, is_flow_type=FlowType.CONTROL)) == 0:
            return (
                False,
                "Event node must have at least one control outlet",
                ["Add at least one EXEC.as_outlet(...) to the node"]
            )
        
        # All checks passed
        return (True, None, [])

    def _validate_data_node(
        self, wrapper: 'NodeWrapper'
    ) -> tuple[bool, str | None, list[str]]:
        """
        Validate data node structural constraints.
        
        Rules:
        - No control inlets and outlets allowed 
        - Must have at least one data outlet
        
        Args:
            wrapper: Event node wrapper to validate
            
        Returns:
            Tuple of (is_valid, error_message, suggestions).
            Error message is None if valid.
            Suggestions is a list of actionable fixes.
        """
        node = wrapper.node
        
        # Check for non-DATA ports with pins (not allowed)
        ports = node.get_ports(is_not_flow_type=FlowType.DATA, has_pin=True)
        if len(ports) > 0:
            return (
                False,
                f"Data nodes cannot have pins on non-DATA ports. "
                f"Found: {[p.id for p in ports]}",
                [
                    "Remove all inlets and outlets with pins that are not DATA ports",
                    "Data nodes are cannot be triggered by events or control flow"
                ]
            )
        
        # Check for at least one data outlet  
        if len(node.get_ports(is_port_type=PortType.OUTLET, is_flow_type=FlowType.DATA)) == 0:
            return (
                False,
                "Data nodes must have at least one data outlet",
                ["Add at least one outlet with FlowType.DATA to the node"]
            )
        
        # All checks passed
        return (True, None, [])

    def _validate_loopback_node(
        self, wrapper: 'NodeWrapper'
    ) -> tuple[bool, str | None, list[str]]:
        """
        Validate loopback node structural constraints.
        
        Loopback nodes (ForLoop, WhileLoop, Sequence, etc.) must have:
        - At least one control outlet with is_loopback_outlet=True (loop body)
        - At least one control outlet with is_loopback_outlet=False (exit path)
        
        This ensures the loop can both iterate and terminate.
        
        Args:
            wrapper: Loopback node wrapper to validate
            
        Returns:
            Tuple of (is_valid, error_message, suggestions).
            Error message is None if valid.
            Suggestions is a list of actionable fixes.
        """
        node = wrapper.node
        control_outlets = node.get_ports(is_port_type=PortType.OUTLET, is_flow_type=FlowType.CONTROL)
        
        # Must have at least 2 control outlets (one for loop, one for exit)
        if len(control_outlets) < 2:
            return (
                False,
                f"Loopback node must have at least 2 control outlets "
                f"(loop body and exit). Found: {len(control_outlets)}",
                [
                    "Add a control outlet for the loop body with needs_loopback=True",
                    "Add a control outlet for exit/completion with needs_loopback=False"
                ]
            )
        
        # Check for loopback outlet (needs_loopback=True)
        loopback_outlets = [p for p in control_outlets if p.needs_loopback]
        if len(loopback_outlets) == 0:
            return (
                False,
                "Loopback node must have at least one control outlet with "
                "needs_loopback=True (the loop body outlet)",
                [
                    "Set needs_loopback=True on the loop body outlet",
                    "Example: EXEC.as_outlet('loop_body', needs_loopback=True)"
                ]
            )
        
        # Check for exit outlet (needs_loopback=False)
        exit_outlets = [p for p in control_outlets if not p.needs_loopback]
        if len(exit_outlets) == 0:
            return (
                False,
                "Loopback node must have at least one control outlet with "
                "needs_loopback=False (the exit/completed outlet)",
                [
                    "Add a control outlet for loop exit without needs_loopback flag",
                    "Example: EXEC.as_outlet('completed')  # needs_loopback defaults to False"
                ]
            )
        
        # All checks passed
        return (True, None, [])
    
    def _validate_event_nodes_graph_wide(self) -> List[str]:
        """
        Validate event node constraints across the entire graph.
        
        Rules:
        - No duplicate event subscriptions (only one node per event)
        - All event nodes individually valid
        
        Returns:
            List of error messages (empty if valid)
        """
        errors = []
        event_subscriptions = {}  # subscription_key -> list of node_ids
        
        for node_wrapper in self.graph.node_wrappers.values():
            node = node_wrapper.node
            
            # Check if this is an event node
            if NodeType.EVENT in node.behavior.node_type:
                # Check individual validity
                if not node_wrapper._state.is_structural:
                    errors.append(
                        f"Event node {node_wrapper.node_id} failed structural validation: "
                        f"{node_wrapper._state.error_structural}"
                    )
                
                # Track subscription for duplicate detection
                if node.event_subscription:
                    sub_key = node.event_subscription.get_subscription_key()
                    if sub_key not in event_subscriptions:
                        event_subscriptions[sub_key] = []
                    event_subscriptions[sub_key].append(node_wrapper.node_id)
        
        # Check for duplicate subscriptions
        for sub_key, node_ids in event_subscriptions.items():
            if len(node_ids) > 1:
                errors.append(
                    f"Multiple event nodes subscribe to '{sub_key}': "
                    f"{', '.join(node_ids)}. Only one event node per "
                    f"event type is allowed."
                )
        
        return errors
    
    # ========================================================================
    # EDGE VALIDATION
    # ========================================================================
    
    def validate_edge(
        self, wrapper: 'EdgeWrapper'
    ) -> tuple[bool, str | None, list[str]]:
        """
        Validate structural constraints for a single edge.
        
        This is called after edge build but before adding to graph.
        
        Args:
            wrapper: EdgeWrapper to validate
            
        Returns:
            Tuple of (is_valid, error_message, suggestions).
            Error message is None if valid.
            Suggestions is a list of actionable fixes.
        """
        # Check edge type-specific rules
        if wrapper._edge_type == FlowType.CALLBACK:
            return self._validate_callback_edge(wrapper)
        elif wrapper._edge_type == FlowType.DATA:
            # Note: Data cycle validation happens graph-wide
            # Individual edges are valid by default
            pass
        
        # Edge passes validation
        return (True, None, [])
    
    def _validate_callback_edge(
        self, wrapper: 'EdgeWrapper'
    ) -> tuple[bool, str | None, list[str]]:
        """
        Validate callback edge structural constraints.
        
        Rules:
        - Target node must be an event node
        
        Args:
            wrapper: Callback edge wrapper to validate
            
        Returns:
            Tuple of (is_valid, error_message, suggestions).
            Error message is None if valid.
            Suggestions is a list of actionable fixes.
        """
        
        # Source must be an event node
        if NodeType.EVENT not in wrapper._source_wrapper.node.behavior.node_type:
            return (
                False,
                f"Callback edge source must be an event node. "
                f"Node '{wrapper.source_node_id}' is not an event node.",
                [
                    "Connect callback to an event node (EventNode subclass)",
                    "Or change edge type to DATA if passing data"
                ]
            )

        
        # All checks passed
        return (True, None, [])
    
    # ========================================================================
    # GRAPH-WIDE VALIDATION
    # ========================================================================
    
    def validate_graph(self) -> List[str]:
        """
        Validate all structural constraints across the graph.
        
        Returns:
            List of error messages (empty if valid)
        """
        errors = []
        
        # Validate event nodes
        event_errors = self._validate_event_nodes_graph_wide()
        errors.extend(event_errors)
        
        # Validate data flow cycles
        # (future: implement cycle detection)
        
        # Validate control flow topology
        # (future: implement unreachable node detection, etc.)
        
        return errors