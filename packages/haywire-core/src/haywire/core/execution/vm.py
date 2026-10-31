"""Haywire Virtual Machine - executes control and data flows."""

from __future__ import annotations
from typing import Callable, Dict, List, Optional, Any, Sequence, TYPE_CHECKING
import logging
import threading

from haywire.core.execution.callback_manager import CallbackManager
from haywire.core.execution.execution_context import ExecutionContext
from haywire.core.execution.flow import ControlNodeInfo, LocalizedDataFlow, overrides
from haywire.core.errors.haywire_exception import HaywireException
from haywire.core.node.behavior import NodeType
from haywire.core.state.data_namespace import AppDataNamespace

if TYPE_CHECKING:
    from haywire.core.execution.flow import Flow
    from haywire.core.execution.event_source import Trigger
    from haywire.core.node import BaseNode
    from haywire.core.state import LibraryStateContainer

logger = logging.getLogger(__name__)


class HaywireVM:
    """
    Virtual Machine for executing Haywire flows.

    The VM manages control flow execution by:
    1. Starting from event node
    2. Navigating control graph based on worker function results
    3. Managing the loopback stack for loop handling
    4. Evaluating data flows before each control node
    5. Handling callbacks between flows

    One VM is shared by every execution group's runner thread, so it keeps
    no per-frame state of its own.
    """

    def __init__(
        self,
        global_context: Optional[Dict[str, Any]] = None,
        max_stack_depth: int = 1000,
        library_state_container: Optional[LibraryStateContainer] = None,
        exception_bail: Optional[Callable[[], str]] = None,
        on_bail_run: Optional[Callable[[], None]] = None,
    ) -> None:
        """
        Initialize VM.

        Args:
            global_context: Global execution context
            max_stack_depth: Maximum loopback stack depth before error
            library_state_container: Container exposing app-global LibraryState
                instances to worker functions via exec_ctx.app_data[Cls].
                Optional — when None, exec_ctx.app_data is None.
            exception_bail: Returns how far a frame bails when a worker raises:
                ``"run"``, ``"frame"`` or ``"branch"``. Read at each exception, so a
                changed policy applies at once. ``None``, or any other value, means
                ``"branch"``.
            on_bail_run: Called when a frame bails with ``"run"``; asks the run's owner
                to stop it. Called on the runner thread, so it must not stop the run itself.
        """
        self.global_context = global_context or {}
        self.max_stack_depth = max_stack_depth
        self._exception_bail = exception_bail
        self._on_bail_run = on_bail_run

        # Callback manager reference (set by interpreter)
        self.callback_manager: Optional[CallbackManager] = None
        self._library_state_container = library_state_container
        # Built once: the container never changes, and the namespace holds no per-frame state.
        self._app_data: Optional[AppDataNamespace] = (
            AppDataNamespace(library_state_container) if library_state_container is not None else None
        )

        logger.debug("HaywireVM initialized")

    def _create_execution_context(
        self, flow: Flow, trigger: Optional[Trigger] = None, frame_number: int = 0
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
        local_ctx: Dict[str, Any] = {
            var_name: variable.current_value for var_name, variable in flow.graph_ref.variables.items()
        }
        return ExecutionContext(
            global_ctx=self.global_context,
            local_ctx=local_ctx,
            trigger=trigger,
            vm=self,
            frame_number=frame_number,
            app_data=self._app_data,
        )

    def call_startup(
        self, nodes: Sequence[BaseNode], context_flow: Flow, cancel: Optional[threading.Event] = None
    ) -> None:
        """Retain every node in ``nodes`` for a run, calling ``on_startup()`` on first retain.

        Called by an execution group before its first frame. A node shared
        with another group that already retained it is not started again.

        Args:
            nodes: The nodes the group executes.
            context_flow: The flow whose graph provides the hook's execution context.
            cancel: The group's ``cancel`` flag; once set, a node whose ``exec_lock``
                another group holds is skipped.
        """
        exec_ctx = self._create_execution_context(context_flow)

        for node in nodes:
            if not self._acquire_exec_lock(node, cancel):
                continue
            try:
                if node.wrapper.retain() and overrides(node, "on_startup"):
                    node.on_startup(exec_ctx)
            except Exception as e:
                self.catch_exception(e, node, "Node on_startup() Execution")
            finally:
                node.wrapper.exec_lock.release()

    def call_shutdown(
        self, nodes: Sequence[BaseNode], context_flow: Flow, cancel: Optional[threading.Event] = None
    ) -> None:
        """Release every node in ``nodes``, calling ``on_shutdown()`` on the last release.

        Called by an execution group after its last frame; mirrors ``call_startup()``.
        Once ``cancel`` is set, a node whose ``exec_lock`` another group holds
        (a stuck worker) is skipped and stays retained.
        """
        exec_ctx = self._create_execution_context(context_flow)

        for node in nodes:
            if not self._acquire_exec_lock(node, cancel):
                logger.warning(f"Skipping on_shutdown bookkeeping of {node.node_id}: held by a stuck run")
                continue
            try:
                if node.wrapper.release() and overrides(node, "on_shutdown"):
                    node.on_shutdown(exec_ctx)
            except Exception as e:
                self.catch_exception(e, node, "Node on_shutdown() Execution")
            finally:
                node.wrapper.exec_lock.release()

    @staticmethod
    def _acquire_exec_lock(node: BaseNode, cancel: Optional[threading.Event]) -> bool:
        """Take ``node``'s ``exec_lock``; give up (``False``) once ``cancel`` is set."""
        lock = node.wrapper.exec_lock
        if cancel is None:
            return lock.acquire()
        while not lock.acquire(timeout=0.1):
            if cancel.is_set():
                return False
        return True

    def execute_control_flow(
        self,
        flow: Flow,
        trigger: Trigger,
        frame_number: int = 0,
        cancel: Optional[threading.Event] = None,
    ) -> int:
        """
        Execute a flow's control flow.

        This is the main entry point for flow execution. It:
        1. Creates the execution context and runs ``on_frame_start``
        2. Navigates the control graph from the entry node
        3. Handles loopback nodes
        4. Runs ``on_frame_end``

        Args:
            flow: Flow to execute
            trigger: Trigger that activated this flow
            frame_number: Number of this frame within its flow, counted from 1
            cancel: ``cancel`` flag of the flow's execution group. Once set, the
                frame ends before its next control node; ``on_frame_end``
                still runs.

        Returns:
            The number of nodes executed in this frame.
        """
        if not flow.is_assembled():
            raise RuntimeError(f"Cannot execute flow {flow.flow_id}: not assembled")
        assert flow.control_graph is not None, "is_assembled() guarantees control_graph is set"
        control_nodes = flow.control_graph.control_nodes

        loopback_stack: List[str] = []

        exec_ctx = self._create_execution_context(flow, trigger, frame_number)
        exec_ctx.cancel = cancel

        # A worker error shows on its card until the next frame of the flow that raised it.
        if flow.nodes_with_worker_error:
            for failed in flow.nodes_with_worker_error:
                failed.wrapper.clear_runtime_errors()
            flow.nodes_with_worker_error = []

        shared = flow.shared_node_ids
        for node in flow.get_nodes_with_on_frame_start():
            self._run_frame_hook(
                node, node.on_frame_start, shared, exec_ctx, "Node on_frame_start() Execution"
            )

        # Start from event node
        current_node_id: Optional[str] = flow.get_entry_node_id()
        current_inlet_id: Optional[str] = None  # Entry has no inlet

        # Main execution loop
        while current_node_id is not None:
            if cancel is not None and cancel.is_set():
                break

            node_info = control_nodes.get(current_node_id)
            if node_info is None:
                logger.error(f"Node {current_node_id} not found in control graph")
                break

            # Set which control inlet we entered through
            exec_ctx.control_pin = current_inlet_id

            # >>>>>>>>>>>
            # Execute this control node (including localized data flow)
            next_outlet_id = self._execute_control_node(node_info, flow, exec_ctx)
            # >>>>>>>>>>>

            if exec_ctx.bail is not None:
                if exec_ctx.bail != "branch":
                    break
                # The branch ends here: back to the enclosing loop, or the frame ends.
                exec_ctx.bail = None
                next_outlet_id = None

            # Only push to loopback stack if taking a loopback outlet
            if node_info.is_loopback and next_outlet_id:
                # .get(), not [...]: a worker may return any string, and an id
                # naming no port must end the branch through _navigate_next
                # rather than abort the whole frame from here.
                outlet_port = node_info.node.ports.get(next_outlet_id)
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

        if exec_ctx.failures:
            flow.nodes_with_worker_error = list(dict.fromkeys(node for node, _ in exec_ctx.failures))
        if exec_ctx.bail == "run" and self._on_bail_run is not None:
            self._on_bail_run()

        for node in flow.get_nodes_with_on_frame_end():
            self._run_frame_hook(node, node.on_frame_end, shared, exec_ctx, "Node on_frame_end() Execution")

        return exec_ctx.exec_count

    def _run_frame_hook(
        self,
        node: BaseNode,
        hook: Callable[[ExecutionContext], None],
        shared_node_ids: frozenset[str],
        exec_ctx: ExecutionContext,
        operation: str,
    ) -> None:
        """Run a frame hook of ``node``, under its ``exec_lock`` when it is a shared data node.

        A shared node whose lock the frame gave up waiting for (``cancel`` set) is skipped.
        """
        shared = node.node_id in shared_node_ids
        if shared and not self._acquire_exec_lock(node, exec_ctx.cancel):
            return
        try:
            hook(exec_ctx)
        except Exception as e:
            self.catch_exception(e, node, operation)
        finally:
            if shared:
                node.wrapper.exec_lock.release()

    def _execute_control_node(
        self, node_info: ControlNodeInfo, flow: Flow, exec_ctx: ExecutionContext
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
            # >>>>>>>>>>>
            # 1. Evaluate localized data flow
            self._evaluate_data_flow(
                node_info.localized_data_flow,
                exec_ctx,
                flow.shared_node_ids,
            )
            # >>>>>>>>>>>
            if exec_ctx.cancel is not None and exec_ctx.cancel.is_set():
                return None
            # A data node raised: the control node does not run on what it left behind.
            if exec_ctx.bail is not None:
                return None

        exec_ctx.exec_count += 1

        # >>>>>>>>>>>
        # 2. Execute control node
        try:
            next_outlet_id = node._execute(exec_ctx)
        except Exception as e:
            self._fail(e, node, exec_ctx)
            return None
        # >>>>>>>>>>>

        return next_outlet_id

    def catch_exception(self, exception: Exception, node: BaseNode, operation: str) -> None:
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
        self, next_outlet_id: Optional[str], node_info: ControlNodeInfo, loopback_stack: List[str]
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

        # Case 3: an edge back into a node on the loopback stack (a Break wired from the body).
        if next_node_id in loopback_stack:
            # Unwind the stack back to that node so its frames are not duplicated.
            loopback_index = loopback_stack.index(next_node_id)
            del loopback_stack[loopback_index:]

        # The edge's inlet goes with it; only a branch end (above) re-enters with no inlet.
        return (next_node_id, inlet_port_id)

    def _evaluate_data_flow(
        self,
        data_flow: LocalizedDataFlow,
        exec_ctx: ExecutionContext,
        shared_node_ids: frozenset[str] = frozenset(),
    ) -> None:
        """
        Evaluate a localized data flow.

        Executes data nodes in sequence to update inlet values
        for the control node. A shared data node runs under its wrapper's
        ``exec_lock``: a group arriving while another computes it waits, then
        finds it clean and reads the fresh outlet.

        Args:
            data_flow: LocalizedDataFlow to evaluate
            exec_ctx: Execution context
            shared_node_ids: Ids of the flow's shared data nodes.
        """
        for data_node in data_flow.execution_sequence:
            exec_ctx.exec_count += 1

            # Hot path: an unshared data node takes no lock and no context manager.
            if shared_node_ids and data_node.node_id in shared_node_ids:
                if not self._acquire_exec_lock(data_node, exec_ctx.cancel):
                    return
                try:
                    ok = self._execute_data_node(data_node, exec_ctx)
                finally:
                    data_node.wrapper.exec_lock.release()
            else:
                ok = self._execute_data_node(data_node, exec_ctx)
            if not ok:
                return  # the frame bails; the rest of this data flow would only feed the skipped node

    def _execute_data_node(self, data_node: BaseNode, exec_ctx: ExecutionContext) -> bool:
        """Run ``data_node``; return whether it returned normally (a raise is recorded, not raised)."""
        try:
            data_node._execute(exec_ctx)
        except Exception as e:
            self._fail(e, data_node, exec_ctx)
            return False
        return True

    def _fail(self, exception: Exception, node: BaseNode, exec_ctx: ExecutionContext) -> None:
        """Record a worker exception and set how far the frame bails (ADR 0066).

        The node's data inlets are marked dirty again, so the next evaluation retries it.
        """
        for port in node.ports.values():
            if port.is_dependent and port.is_inlet():
                node.mark_port_as_dirty(port)
        exec_ctx.failures.append((node, exception))
        self.catch_exception(exception, node, "Node Execution")
        policy = self._exception_bail() if self._exception_bail is not None else "branch"
        exec_ctx.bail = policy if policy in ("run", "frame", "branch") else "branch"

    def emit_callback(self, event_name: str, payload: Optional[Dict[str, Any]] = None) -> None:
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
