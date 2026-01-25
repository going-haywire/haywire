"""
Haywire Virtual Machine - Executes control and data flows.

The VM is responsible for:
- Navigating control flow based on runtime decisions
- Managing execution stacks (done, loopback)
- Evaluating localized data flows
- Managing execution context
- Detecting infinite loops
"""
from __future__ import annotations
from typing import Dict, List, Optional, Any, TYPE_CHECKING
from dataclasses import dataclass
import logging

from haywire.core.execution.flow import ControlNodeInfo, LocalizedDataFlow

if TYPE_CHECKING:
    from haywire.core.execution.flow import Flow
    from haywire.core.execution.event_source import Trigger
    from haywire.core.node.node_wrapper import NodeWrapper

logger = logging.getLogger(__name__)


@dataclass
class ExecutionContext:
    """
    Context passed to worker functions during execution.
    
    Contains all data needed by worker functions:
    - Global context (from external system)
    - Local context (graph variables)
    - Current trigger
    - Callback emission function
    """
    global_ctx: Dict[str, Any]
    """Global context from external system"""
    local_ctx: Dict[str, Any]
    """Local context (graph variables)"""
    trigger: 'Trigger'
    """Current trigger that activated this flow"""
    control_pin: Optional[str] = None
    """ID of control inlet that was triggered (for control nodes)"""
    node_wrapper: Optional['NodeWrapper'] = None
    """Current node being executed"""
    vm: Optional['HaywireVM'] = None
    """Reference to VM for callback emission"""
    
    def emit_callback(self, event_name: str, payload: Optional[Dict] = None):
        """
        Emit a callback to trigger other flows.
        
        Args:
            event_name: Name of callback event
            payload: Optional data to pass
        """
        if self.vm:
            self.vm.emit_callback(event_name, payload)
        else:
            logger.warning("Cannot emit callback: No VM reference in context")
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for worker function compatibility"""
        return {
            'global': self.global_ctx,
            'local': self.local_ctx,
            'trigger': self.trigger,
            'control_pin': self.control_pin,
            'node': self.node_wrapper,
            'emit_callback': self.emit_callback
        }


class HaywireVM:
    """
    Virtual Machine for executing Haywire flows.
    
    The VM manages control flow execution by:
    1. Starting from event node
    2. Navigating control graph based on worker function results
    3. Managing done/loopback stacks for loop handling
    4. Evaluating data flows before each control node
    5. Handling callbacks between flows
    """
    
    def __init__(
        self,
        global_context: Optional[Dict[str, Any]] = None,
        max_stack_depth: int = 10000
    ):
        """
        Initialize VM.
        
        Args:
            global_context: Global execution context
            max_stack_depth: Maximum stack depth before error
        """
        self.global_context = global_context or {}
        self.max_stack_depth = max_stack_depth
        
        # Callback manager reference (set by interpreter)
        self.callback_manager = None
        
        logger.debug("HaywireVM initialized")
    
    def execute_control_flow(self, flow: 'Flow', trigger: 'Trigger'):
        """
        Execute a flow's control flow.
        
        This is the main entry point for flow execution. It:
        1. Initializes execution stacks
        2. Creates execution context
        3. Navigates control graph
        4. Handles loopback nodes
        
        Args:
            flow: Flow to execute
            trigger: Trigger that activated this flow
        """
        if not flow.is_assembled():
            raise RuntimeError(
                f"Cannot execute flow {flow.flow_id}: not assembled"
            )
        
        logger.debug(
            f"Starting control flow execution: {flow.flow_id} "
            f"(trigger: {trigger.source_key})"
        )
        
        # Initialize execution tracking
        execution_count: int = 0
        loopback_stack: List[str] = []
        
        # Create local context from graph variables
        local_context = self._create_local_context(flow)
        
        # Create execution context
        exec_ctx = ExecutionContext(
            global_ctx=self.global_context,
            local_ctx=local_context,
            trigger=trigger,
            vm=self
        )
        
        # Start from event node
        current_node_id = flow.get_entry_node_id()
        
        # Main execution loop
        while current_node_id is not None:
            
            # Infinite loop protection
            execution_count += 1
            if execution_count > self.max_stack_depth:
                raise RuntimeError(
                    f"Exceeded max iterations in flow {flow.flow_id}: "
                    f"{self.max_stack_depth} iterations. "
                    f"Possible infinite loop."
                )
            
            # Get node info
            node_info = flow.control_graph.get_node_info(current_node_id)
            if node_info is None:
                logger.error(
                    f"Node {current_node_id} not found in control graph"
                )
                break
            
            # Execute this control node
            next_outlet_id = self._execute_control_node(
                node_info, 
                flow, 
                exec_ctx
            )
            
            # Only push to loopback stack if taking a loopback outlet
            if node_info.is_loopback and next_outlet_id:
                outlet_port = node_info.node_wrapper.node.ports[next_outlet_id]
                if outlet_port and outlet_port.needs_loopback:
                    loopback_stack.append(current_node_id)
            
            # Navigate to next node
            current_node_id = self._navigate_next(
                next_outlet_id,
                node_info,
                loopback_stack
            )
        
        logger.debug(f"Control flow execution completed: {flow.flow_id}")
    
    def _create_local_context(self, flow: 'Flow') -> Dict[str, Any]:
        """
        Create local context from graph variables.
        
        Args:
            flow: Flow being executed
            
        Returns:
            Dictionary with graph variable values
        """
        local_ctx = {}
        
        # Copy current values from graph variables
        for var_name, variable in flow.graph_ref.variables.items():
            local_ctx[var_name] = variable.current_value
        
        return local_ctx
    
    def _execute_control_node(
        self,
        node_info: 'ControlNodeInfo',
        flow: 'Flow',
        exec_ctx: ExecutionContext
    ) -> Optional[str]:
        """
        Execute a control node.
        
        Steps:
        1. Evaluate localized data flow (if exists)
        2. Call optional validation hooks
        3. Execute worker function
        4. Return next outlet ID
        
        Args:
            node_info: ControlNodeInfo for the node
            flow: Flow being executed
            exec_ctx: Execution context
            
        Returns:
            ID of outlet pin to follow next, or None
        """
        node_wrapper = node_info.node_wrapper
        node = node_wrapper.node
        
        logger.debug(f"Executing control node: {node_wrapper.node_id}")
        
        # Update context with current node
        exec_ctx.node_wrapper = node_wrapper
        
        # 1. Evaluate localized data flow
        if node_info.localized_data_flow:
            self._evaluate_data_flow(
                node_info.localized_data_flow,
                exec_ctx,
                lazy_mask=None  # TODO: Implement lazy evaluation
            )
        
        # 2 Execute control node
        next_outlet_id = node_wrapper._execute_method(exec_ctx)
        
        logger.debug(
            f"Control node {node_wrapper.node_id} completed, "
            f"next outlet: {next_outlet_id}"
        )
        
        return next_outlet_id
    
    
    def _navigate_next(
        self,
        next_outlet_id: Optional[str],
        node_info: 'ControlNodeInfo',
        loopback_stack: List[str]
    ) -> Optional[str]:
        """
        Determine next node to execute based on worker result.
        
        Args:
            next_outlet_id: Outlet ID from worker, or None
            node_info: Current node info
            loopback_stack: Stack of loopback node IDs
            
        Returns:
            ID of next node to execute, or None to end
        """
        node = node_info.node_wrapper.node
        
        # Case 1: No outlet specified
        if next_outlet_id is None:
            # Check if this is an output node
            if node.behavior.is_output_node:
                logger.debug("Reached output node, ending flow")
                return None  # End flow
            else:
                # Branch ended without output - try loopback
                return loopback_stack.pop() if loopback_stack else None
        
        # Case 2: Outlet specified - look it up
        next_node_id = node_info.outlet_map.get(next_outlet_id)
        
        if next_node_id is None:
            # Outlet exists but not connected - try loopback
            logger.debug(
                f"Outlet {next_outlet_id} not connected, trying loopback"
            )
            return loopback_stack.pop() if loopback_stack else None
        
        # Check if next node is already on the loopback stack.
        # If so, unwind the stack back to that point to avoid duplicate frames.
        if next_node_id in loopback_stack:
            loopback_index = loopback_stack.index(next_node_id)
            logger.debug(
                f"Navigating back to loopback node {next_node_id} "
                f"already on stack at index {loopback_index}, unwinding"
            )
            # Truncate stack to remove this node and everything after
            del loopback_stack[loopback_index:]
        
        return next_node_id
    
    def _evaluate_data_flow(
        self,
        data_flow: 'LocalizedDataFlow',
        exec_ctx: ExecutionContext,
        lazy_mask: Optional[int]
    ):
        """
        Evaluate a localized data flow.
        
        Executes data nodes in sequence to update inlet values
        for the control node.
        
        Args:
            data_flow: LocalizedDataFlow to evaluate
            exec_ctx: Execution context
            lazy_mask: Optional lazy evaluation mask
        """
        logger.debug(
            f"Evaluating data flow for {data_flow.control_node_id} "
            f"({len(data_flow.execution_sequence)} nodes)"
        )
        
        for data_node_wrapper in data_flow.execution_sequence:
            
            # TODO: Implement lazy evaluation check
            # if lazy_mask and data_flow.requires_lazy:
            #     eval_mask = data_flow.eval_masks.get(data_node_wrapper.node_id, 0)
            #     if (lazy_mask & eval_mask) == 0:
            #         continue  # Skip this node
                        
            # Execute data node
            logger.debug(f"Executing data node: {data_node_wrapper.node_id}")            
            data_node_wrapper._execute_method(exec_ctx)            
            
    def emit_callback(self, event_name: str, payload: Optional[Dict] = None):
        """
        Emit a callback to trigger other flows.
        
        This is called by control nodes during execution to trigger
        event nodes listening for this callback.
        
        Args:
            event_name: Name of callback event
            payload: Optional data to pass
        """
        if self.callback_manager:
            self.callback_manager.emit_callback(event_name, payload)
        else:
            logger.warning(
                f"Cannot emit callback '{event_name}': "
                f"No callback manager registered"
            )
