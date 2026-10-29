"""
Haywire Interpreter - Main execution coordinator.

The Interpreter is responsible for:
- Managing flow assembly
- Dispatching external events to flows
- Managing execution groups and their runner threads
- Coordinating VM and callback manager
- Providing execution interface to external systems
"""

from __future__ import annotations
from typing import Dict, List, Optional, Any, TYPE_CHECKING
import time
import logging

if TYPE_CHECKING:
    from haywire.core.graph.base import BaseGraph
    from haywire.core.execution.flow import Flow
    from haywire.core.state import LibraryStateContainer

from haywire.core.assembly.flow_assembly_manager import FlowAssemblyManager
from haywire.core.execution.vm import HaywireVM
from haywire.core.execution.callback_manager import CallbackManager
from haywire.core.execution.flow_queue import FlowQueue
from haywire.core.execution.execution_group import ExecutionGroup, group_flows, shared_data_node_ids
from haywire.core.execution.event_source import (
    SystemEvent,
    SystemEventType,
    ExternalEvent,
    CallbackEvent,
    Trigger,
)

logger = logging.getLogger(__name__)


class Interpreter:
    """
    Main Haywire execution coordinator.

    The Interpreter provides the interface between external systems
    and Haywire's internal execution model. It:

    1. Assembles graphs into flows
    2. Registers flows with appropriate event subscriptions
    3. Dispatches events to flows
    4. Runs flows on one runner thread per execution group
    5. Coordinates callbacks between flows

    Usage:
        # Create interpreter
        interpreter = Interpreter()

        # Load and assemble graph
        interpreter.load_graph(graph)

        # Start execution (dispatches BEGIN_PLAY)
        interpreter.start_execution()

        # ... execution runs until stopped ...

        # Stop execution (dispatches SHUTDOWN, waits, cleans up)
        interpreter.stop_execution()
    """

    def __init__(
        self,
        global_context: Optional[Dict[str, Any]] = None,
        max_stack_depth: int = 1000,
        library_state_container: Optional["LibraryStateContainer"] = None,
    ):
        """
        Initialize interpreter.

        Args:
            global_context: Global execution context passed to all flows
            max_stack_depth: Maximum VM stack depth
            library_state_container: Optional pool of LibraryState instances.
                Forwarded to the VM so worker functions get exec_ctx.app_data.
        """
        # Core components
        self.assembly_manager = FlowAssemblyManager()
        self.vm = HaywireVM(
            global_context=global_context,
            max_stack_depth=max_stack_depth,
            library_state_container=library_state_container,
        )
        self.callback_manager = CallbackManager()

        # Wire callback manager to VM
        self.vm.callback_manager = self.callback_manager

        # Event subscriptions: subscription_key → List[Flow]
        self.event_subscriptions: Dict[str, List[Flow]] = {}

        self.groups: List[ExecutionGroup] = []
        """The execution groups of the loaded graph, each with its own runner thread."""
        self._abandoned: List[ExecutionGroup] = []
        self._held_for_reassembly = False

        # Current graph
        self.current_graph: Optional["BaseGraph"] = None

        # Execution state
        self._executing: bool = False

        logger.info("Haywire Interpreter initialized")

    def load_graph(self, graph: "BaseGraph") -> None:
        """
        Load and assemble a graph for execution.

        This:
        1. Assembles all flows in the graph
        2. Registers flows with event subscriptions, flow queues and callback listeners
        3. Partitions the flows into execution groups and starts each group's runner

        Args:
            graph: Graph to load
        """
        logger.info(f"Loading graph: {graph.graph_id}")

        # Clear previous state
        self._cleanup_current_graph()

        # Store graph reference
        self.current_graph = graph

        # Assemble flows
        flows = self.assembly_manager.assemble_graph(graph)

        logger.info(f"Assembled {len(flows)} flows")

        # Register flows
        for flow in flows:
            self._register_flow(flow)

        partition = group_flows(flows)
        shared_ids = shared_data_node_ids(partition)
        for group_flows_ in partition:
            group = ExecutionGroup(f"group_{group_flows_[0].flow_id}", group_flows_, self.vm)
            for flow in group_flows_:
                flow.shared_node_ids = shared_ids
                assert flow.queue is not None
                flow.queue.group = group
            self.groups.append(group)
        for group in self.groups:
            group.start()
        graph.root_graph._validation.set_execution_hold(self)
        logger.info(f"Partitioned {len(flows)} flows into {len(self.groups)} execution groups")

        logger.info(f"Graph {graph.graph_id} loaded and ready")

    @property
    def is_executing(self) -> bool:
        """True if execution has been started and not yet stopped."""
        return self._executing

    def start_execution(self) -> None:
        """
        Start graph execution by dispatching BEGIN_PLAY.

        Call after load_graph(). Dispatches the BEGIN_PLAY system event
        which triggers BeginPlayNode flows.
        """
        if self._executing:
            return

        self._executing = True
        self.dispatch_system_event(SystemEventType.BEGIN_PLAY)
        logger.info("Execution started")

    def stop_execution(self, timeout: float = 2.0) -> None:
        """
        Stop graph execution.

        Dispatches SHUTDOWN, then grants a *scoped* grace period for any
        author-wired graceful teardown to run before forcibly stopping every
        execution group.

        The grace period waits only on the flow(s) rooted at a Shutdown event
        node — the single subscriber to ``system:shutdown``. That flow is where
        the designer wires graceful stops (e.g. ``Shutdown → TickEmit.stop``),
        which halt producer threads so downstream queues stop being fed. We do
        NOT wait on the other flows: producer-fed queues (e.g. a Tick flow
        receiving callbacks) never drain on their own, so joining them would
        hang (see the TickEmit shutdown deadlock).

        If no Shutdown flow exists there is no graceful path to wait for, so we
        skip the grace period and force teardown immediately. Force teardown
        (``_cleanup_current_graph``) stops every execution group, and each
        runner's exit runs node ``on_shutdown`` — the last-resort backstop
        that kills any producer threads the designer didn't stop explicitly.

        After a structural validation batch that requires reassembly the
        groups are parked at their frame barrier; stopping then skips the
        Shutdown flow, which would run on the outdated assembly.

        Args:
            timeout: Grace-period budget for the Shutdown flow to complete.
        """
        if not self._executing:
            return

        # Groups parked for reassembly would run the Shutdown flow on a stale
        # assembly, so it is skipped (ADR 0064).
        if not self._held_for_reassembly:
            # Dispatch SHUTDOWN so a Shutdown-rooted flow can run its graceful path.
            self.dispatch_system_event(SystemEventType.SHUTDOWN)

            # Scoped grace: wait (bounded) only for the Shutdown flow(s) to finish.
            shutdown_key = SystemEvent(type=SystemEventType.SHUTDOWN).get_subscription_key()
            shutdown_flows = self.event_subscriptions.get(shutdown_key, [])
            for flow in shutdown_flows:
                if flow.queue:
                    flow.queue.wait_for_completion(timeout)

        # Force teardown: stop every group; on_shutdown backstops any
        # producer threads not stopped by a graceful path.
        self._cleanup_current_graph(print_stats=True)

        self._executing = False
        logger.info("Execution stopped")

    def hold_for_batch(self, timeout_s: float = 2.0) -> bool:
        """Park every execution group at its frame barrier for a structural validation batch.

        Waits at most ``timeout_s`` in all for running frames to end; a frame
        still running then (a stuck worker) overlaps the batch, with a warning.
        Returns ``False`` without holding anything when called on one of this
        Interpreter's runner threads. See ``ExecutionHold``.
        """
        groups = list(self.groups)
        if any(group.is_runner_thread() for group in groups):
            return False
        deadline = time.monotonic() + timeout_s
        for group in groups:
            if not group.hold(max(0.0, deadline - time.monotonic())):
                logger.warning(f"{group.group_id} is still in a frame; validating without waiting for it")
        return True

    def release_after_batch(self, requires_reassembly: bool) -> None:
        """Resume the groups, unless the batch requires reassembly: then they stay parked until stop."""
        if requires_reassembly:
            self._held_for_reassembly = True
        if self._held_for_reassembly:
            return
        for group in list(self.groups):
            group.release()

    def has_abandoned_runners(self) -> bool:
        """Return ``True`` while a runner a stop gave up on is still alive."""
        self._abandoned = [group for group in self._abandoned if group.is_abandoned]
        return bool(self._abandoned) or any(group.is_abandoned for group in self.groups)

    def _register_flow(self, flow: "Flow") -> None:
        """
        Register a flow with event subscriptions, its flow queue and callback listener.

        Args:
            flow: Flow to register
        """
        # Get subscription key
        subscription_key = flow.get_subscription_key()

        # Register with event subscriptions
        if subscription_key not in self.event_subscriptions:
            self.event_subscriptions[subscription_key] = []
        self.event_subscriptions[subscription_key].append(flow)

        logger.debug(f"Flow {flow.flow_id} registered for event '{subscription_key}'")

        # Create the flow queue. Queue mode + depth ride on the event subscription
        # (set by the event-node author); every EventSource carries them,
        # defaulting to BLOCK / 100.
        sub = flow.event_subscription
        flow.queue = FlowQueue(
            flow=flow, vm=self.vm, queue_mode=sub.queue_mode, max_queue_size=sub.max_queue_size
        )

        # Register callback listeners
        if isinstance(flow.event_subscription, CallbackEvent):
            self.callback_manager.register_callback_listener(flow.event_subscription.event_name, flow)

    def _cleanup_current_graph(self, print_stats: bool = False) -> None:
        """
        Cleanup current graph state.

        Args:
            print_stats: Whether to log each flow's execution statistics during cleanup
        """
        if not self.current_graph:
            return

        logger.debug("Cleaning up current graph")

        root_validation = self.current_graph.root_graph._validation
        if root_validation._execution_hold is self:
            root_validation.set_execution_hold(None)

        self._stop_groups()
        if print_stats:
            for flow in self._all_flows():
                if flow.queue:
                    flow.queue.log_stats()
        self.groups.clear()
        self._held_for_reassembly = False

        # Clear subscriptions
        self.event_subscriptions.clear()

        # Clear callbacks
        self.callback_manager.clear_callbacks()

        # Clear assembly cache
        self.assembly_manager.assembled_flows.clear()
        self.assembly_manager.assembly_cache.clear()

        self.current_graph = None

    def _all_flows(self) -> List["Flow"]:
        return [flow for flows in self.event_subscriptions.values() for flow in flows]

    def _stop_groups(self, timeout_s: float = 2.0) -> None:
        for group in self.groups:
            if not group.stop(timeout_s) and group not in self._abandoned:
                self._abandoned.append(group)

    def dispatch_system_event(
        self, event_type: SystemEventType, payload: Optional[Dict[str, Any]] = None
    ) -> int:
        """
        Dispatch a system event.

        Args:
            event_type: Type of system event
            payload: Optional event data

        Returns:
            Number of flows triggered
        """
        event = SystemEvent(type=event_type)
        return self._dispatch_event(event.get_subscription_key(), payload)

    def dispatch_external_event(
        self, category: str, name: str, payload: Optional[Dict[str, Any]] = None
    ) -> int:
        """
        Dispatch an external event.

        Args:
            category: Event category (e.g., 'input', 'network')
            name: Event name (e.g., 'key_pressed')
            payload: Optional event data

        Returns:
            Number of flows triggered
        """
        event = ExternalEvent(category=category, name=name)
        return self._dispatch_event(event.get_subscription_key(), payload)

    def _dispatch_event(self, subscription_key: str, payload: Optional[Dict[str, Any]] = None) -> int:
        """
        Internal method to dispatch event to flows.

        Args:
            subscription_key: Event subscription key
            payload: Optional event data

        Returns:
            Number of flows triggered
        """
        # Get flows listening for this event
        flows = self.event_subscriptions.get(subscription_key, [])

        if not flows:
            logger.debug("No flows listening for event '%s'", subscription_key)
            return 0

        logger.debug("Dispatching event '%s' to %d flows", subscription_key, len(flows))

        # Create trigger
        trigger = Trigger(source_key=subscription_key, payload=payload, timestamp=time.time())

        # Enqueue in each flow's queue
        triggered = 0
        for flow in flows:
            if flow.queue:
                if flow.queue.enqueue_trigger(trigger):
                    triggered += 1
            else:
                logger.warning(f"Flow {flow.flow_id} has no queue, cannot trigger")

        return triggered

    def wait_all(self, timeout: Optional[float] = None, stop_after: bool = True) -> None:
        """
        Wait for all flows to complete their queued triggers.

        After waiting, optionally stops every execution group's runner
        thread.

        Args:
            timeout: Maximum time to wait per flow (None = wait forever)
            stop_after: Whether to stop the groups after waiting. Defaults to
                True, which causes runners to exit after processing queued work.
        """
        logger.debug("Waiting for all flows to complete")

        # Wait for all queues to empty
        for flows in self.event_subscriptions.values():
            for flow in flows:
                if flow.queue:
                    flow.queue.wait_for_completion(timeout)

        # Stop all groups if requested
        if stop_after:
            logger.debug("Stopping all execution groups after completion")
            self._stop_groups()

        logger.debug("All flows completed")

    def shutdown(self) -> None:
        """Shutdown interpreter and cleanup resources"""
        logger.info("Shutting down interpreter")

        # Cleanup current graph - print stats on explicit shutdown
        self._cleanup_current_graph(print_stats=True)

        logger.info("Interpreter shutdown complete")

    def get_statistics(self) -> Dict[str, Any]:
        """
        Get execution statistics.

        Returns:
            Dictionary with statistics from all components
        """
        assembly_stats = self.assembly_manager.get_statistics()

        return {
            "current_graph": self.current_graph.graph_id if self.current_graph else None,
            "total_subscriptions": len(self.event_subscriptions),
            "groups": [
                {"group_id": group.group_id, "flows": [flow.flow_id for flow in group.flows]}
                for group in self.groups
            ],
            "assembly": assembly_stats,
            "callbacks": self.callback_manager.get_statistics(),
            "flows": [
                {
                    "flow_id": flow.flow_id,
                    "subscription": flow.get_subscription_key(),
                    "executing": flow.queue.is_busy() if flow.queue else False,
                    "queued": flow.queue.get_queue_size() if flow.queue else 0,
                }
                for flows in self.event_subscriptions.values()
                for flow in flows
            ],
        }

    def __str__(self) -> str:
        graph_id = self.current_graph.graph_id if self.current_graph else "None"
        return f"Interpreter(graph={graph_id}, subscriptions={len(self.event_subscriptions)})"
