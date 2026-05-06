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
import logging

from haywire.core.execution.callback_manager import CallbackManager
from haywire.core.execution.execution_context import ExecutionContext
from haywire.core.execution.flow import ControlNodeInfo, LocalizedDataFlow
from haywire.core.errors.haywire_exception import HaywireException
from haywire.core.node.behavior import NodeType

if TYPE_CHECKING:
    from haywire.core.execution.flow import Flow
    from haywire.core.execution.event_source import Trigger
    from haywire.core.node import BaseNode

logger = logging.getLogger(__name__)


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

    def __init__(self, global_context: Optional[Dict[str, Any]] = None, max_stack_depth: int = 1000):
        """
        Initialize VM.

        Args:
            global_context: Global execution context
            max_stack_depth: Maximum loopback stack depth before error
        """
        self.global_context = global_context or {}
        self.max_stack_depth = max_stack_depth
        self.execution_count: int = 0

        # Callback manager reference (set by interpreter)
        self.callback_manager: Optional[CallbackManager] = None

        logger.debug("HaywireVM initialized")

    def _create_execution_context(
        self, flow: "Flow", trigger: Optional["Trigger"] = None, frame_number: int = 0
    ) -> ExecutionContext:
        """
        Create execution context for flow execution.

        Creates local context from graph variables and builds complete
        ExecutionContext with global context, trigger, and frame number.

        Args:
            flow: Flow being executed
            trigger: Optional trigger that activated flow
            frame_number: Current frame number for this execution

        Returns:
            Complete ExecutionContext ready for node execution
        """
        # Create local context from graph variables
        local_ctx = {}
        for var_name, variable in flow.graph_ref.variables.items():
            local_ctx[var_name] = variable.current_value

        # Build and return complete execution context
        return ExecutionContext(
            global_ctx=self.global_context,
            local_ctx=local_ctx,
            trigger=trigger,
            vm=self,
            frame_number=frame_number,
        )

    def call_flow_startup(self, flow: "Flow"):
        """
        Call on_startup() on all nodes in flow.

        Invoked once when flow execution thread starts, before processing
        any triggers. Nodes can use this to initialize resources.

        Args:
            flow: Flow containing nodes to initialize
        """
        exec_ctx = self._create_execution_context(flow)

        for node in flow.get_nodes_with_on_startup():
            try:
                # call the nodes wrapper on_startup for housekeeping purposes.
                node.on_startup(exec_ctx)
            except Exception as e:
                self.catch_exception(e, node, "Node on_startup() Execution")

    def call_flow_shutdown(self, flow: "Flow"):
        """
        Call on_shutdown() on all nodes in flow.

        Invoked once when flow execution thread ends, after all triggers
        processed. Nodes can use this to cleanup resources.

        Args:
            flow: Flow containing nodes to cleanup
        """
        exec_ctx = self._create_execution_context(flow)

        for node in flow.get_nodes_with_on_shutdown():
            try:
                # call the nodes wrapper on_shutdown for housekeeping purposes.
                node.on_shutdown(exec_ctx)
            except Exception as e:
                self.catch_exception(e, node, "Node on_shutdown() Execution")

    def execute_control_flow(self, flow: "Flow", trigger: "Trigger", frame_number: int = 0):
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
            frame_number: int = 0
        """
        if not flow.is_assembled():
            raise RuntimeError(f"Cannot execute flow {flow.flow_id}: not assembled")
        assert flow.control_graph is not None, "is_assembled() guarantees control_graph is set"

        # logger.debug(
        #     f"Starting control flow execution: {flow.flow_id} "
        #     f"(trigger: {trigger.source_key})"
        # )

        # Reset execution tracking for this flow
        self.execution_count = 0
        loopback_stack: List[str] = []

        # Create execution context
        exec_ctx = self._create_execution_context(flow, trigger, frame_number)

        for node in flow.get_nodes_with_on_frame_start():
            try:
                node.on_frame_start(exec_ctx)
            except Exception as e:
                self.catch_exception(e, node, "Node on_frame_start() Execution")

        # Start from event node
        current_node_id: Optional[str] = flow.get_entry_node_id()
        current_inlet_id: Optional[str] = None  # Entry has no inlet

        # Main execution loop
        while current_node_id is not None:
            # Get node info
            node_info = flow.control_graph.get_node_info(current_node_id)
            if node_info is None:
                logger.error(f"Node {current_node_id} not found in control graph")
                break

            # Set which control inlet we entered through
            exec_ctx.control_pin = current_inlet_id

            # >>>>>>>>>>>
            # Execute this control node (including localized data flow)
            next_outlet_id = self._execute_control_node(node_info, flow, exec_ctx)
            # >>>>>>>>>>>

            # Only push to loopback stack if taking a loopback outlet
            if node_info.is_loopback and next_outlet_id:
                outlet_port = node_info.node.ports[next_outlet_id]
                if outlet_port and outlet_port.needs_loopback:
                    loopback_stack.append(current_node_id)
                    if len(loopback_stack) > self.max_stack_depth:
                        raise RuntimeError(
                            f"Exceeded max iterations in flow {flow.flow_id}: "
                            f"{self.max_stack_depth} iterations. "
                            f"Possible infinite loop."
                        )

            # Navigate to next node
            current_node_id, current_inlet_id = self._navigate_next(
                next_outlet_id, node_info, loopback_stack
            )

        for node in flow.get_nodes_with_on_frame_end():
            try:
                node.on_frame_end(exec_ctx)
            except Exception as e:
                self.catch_exception(e, node, "Node on_frame_end() Execution")

    def _execute_control_node(
        self, node_info: "ControlNodeInfo", flow: "Flow", exec_ctx: ExecutionContext
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
        node = node_info.node

        # Update context with current node
        exec_ctx.node = node

        if node_info.localized_data_flow:
            # logger.debug(
            #     f"> Executing Data Flow for node: {node_wrapper.node_id} on frame {exec_ctx.frame_number}"
            # )
            # >>>>>>>>>>>
            # 1. Evaluate localized data flow
            self._evaluate_data_flow(
                node_info.localized_data_flow,
                exec_ctx,
            )
            # >>>>>>>>>>>

        self.execution_count += 1
        exec_ctx.exec_count = self.execution_count

        # >>>>>>>>>>>
        # 2. Execute control node
        try:
            next_outlet_id = node._execute(exec_ctx)
        except Exception as e:
            self.catch_exception(e, node, "Node Execution")
            return None
        # >>>>>>>>>>>

        # logger.debug(
        #     f"Control node {node.node_id} completed, "
        #     f"next outlet: {next_outlet_id}"
        # )

        return next_outlet_id

    def catch_exception(self, exception: Exception, node: "BaseNode", operation: str) -> None:
        """
        Handle exception during node execution.

        Stores the error in the node's runtime errors.
        """

        error = HaywireException.from_exception(
            exception=exception, operation=operation, message=f"Error executing node '{node.identity.label}'"
        ).enrich(
            _node_id=node.node_id,
            registry_key=node.identity.registry_key,
            module_name=node.__class__.__module__,
            library_identity=node.library,
        )
        error.log()
        node.wrapper._add_runtime_error(error)

    def _navigate_next(
        self, next_outlet_id: Optional[str], node_info: "ControlNodeInfo", loopback_stack: List[str]
    ) -> tuple[Optional[str], Optional[str]]:
        """
        Determine next node to execute based on worker result.

        Args:
            next_outlet_id: Outlet ID from worker, or None
            node_info: Current node info
            loopback_stack: Stack of loopback node IDs

        Returns:
            Tuple of (next_node_id, inlet_port_id), or (None, None) to end
        """
        node = node_info.node

        # Case 1: No outlet specified
        if next_outlet_id is None:
            # Check if this is an output node
            if NodeType.OUTPUT in node.behavior.node_type:
                return (None, None)  # End flow
            else:
                # Branch ended without output - try loopback
                if loopback_stack:
                    # Loopback re-enters the node (no specific inlet)
                    return (loopback_stack.pop(), None)
                return (None, None)

        # Case 2: Outlet specified - look it up
        outlet_target = node_info.outlet_map.get(next_outlet_id)

        if outlet_target is None:
            # Outlet exists but not connected - try loopback
            if loopback_stack:
                return (loopback_stack.pop(), None)
            return (None, None)

        next_node_id, inlet_port_id = outlet_target

        # Case 3: Node is already on the loopback stack.
        if next_node_id in loopback_stack:
            # Unwind the stack back to that point to avoid duplicate frames.
            # Return None for inlet_id to indicate this is a loopback return
            # and not a fresh entry through an inlet.
            loopback_index = loopback_stack.index(next_node_id)
            # Truncate stack to remove this node and everything after
            del loopback_stack[loopback_index:]
            return (next_node_id, None)  # Loopback return, no specific inlet

        return (next_node_id, inlet_port_id)

    def _evaluate_data_flow(
        self,
        data_flow: "LocalizedDataFlow",
        exec_ctx: ExecutionContext,
    ):
        """
        Evaluate a localized data flow.

        Executes data nodes in sequence to update inlet values
        for the control node.

        Args:
            data_flow: LocalizedDataFlow to evaluate
            exec_ctx: Execution context
        """
        for data_node in data_flow.execution_sequence:
            self.execution_count += 1
            exec_ctx.exec_count = self.execution_count

            # Execute data node
            try:
                data_node._execute(exec_ctx)
            except Exception as e:
                self.catch_exception(e, data_node, "Node Execution")

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
            logger.warning(f"Cannot emit callback '{event_name}': No callback manager registered")
