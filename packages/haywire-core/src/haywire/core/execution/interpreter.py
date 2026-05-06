"""
Haywire Interpreter - Main execution coordinator.

The Interpreter is responsible for:
- Managing flow assembly
- Dispatching external events to flows
- Managing flow schedulers
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
from haywire.core.execution.scheduler import FlowScheduler, QueueMode
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
    4. Manages execution threads via schedulers
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
                Forwarded to the VM so worker functions get exec_ctx.data.
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

        # Current graph
        self.current_graph: Optional["BaseGraph"] = None

        # Execution state
        self._executing: bool = False

        logger.info("Haywire Interpreter initialized")

    def load_graph(self, graph: "BaseGraph"):
        """
        Load and assemble a graph for execution.

        This:
        1. Assembles all flows in the graph
        2. Registers flows with event subscriptions
        3. Sets up schedulers
        4. Registers callback listeners

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
        Stop graph execution gracefully.

        Dispatches SHUTDOWN event, waits for shutdown flows to complete,
        then stops all schedulers and cleans up.

        Args:
            timeout: Maximum time to wait for flows to complete.
        """
        if not self._executing:
            return

        # Dispatch SHUTDOWN so ShutdownNode flows can run
        self.dispatch_system_event(SystemEventType.SHUTDOWN)

        # Wait for SHUTDOWN flows to finish processing
        self.wait_all(timeout=timeout, stop_after=False)

        # Now stop all schedulers and clean up
        self._cleanup_current_graph(print_stats=True)

        self._executing = False
        logger.info("Execution stopped")

    def _register_flow(self, flow: "Flow"):
        """
        Register a flow with event subscriptions and setup scheduler.

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

        # Create scheduler
        flow.scheduler = FlowScheduler(flow=flow, vm=self.vm, queue_mode=QueueMode.BLOCK)

        # Start execution thread - it will sleep until triggers arrive
        flow.scheduler.start()

        # Register callback listeners
        if isinstance(flow.event_subscription, CallbackEvent):
            self.callback_manager.register_callback_listener(flow.event_subscription.event_name, flow)

    def _cleanup_current_graph(self, print_stats: bool = False):
        """
        Cleanup current graph state.

        Args:
            print_stats: Whether to print scheduler statistics during cleanup
        """
        if not self.current_graph:
            return

        logger.debug("Cleaning up current graph")

        # Stop all schedulers
        for flows in self.event_subscriptions.values():
            for flow in flows:
                if flow.scheduler:
                    flow.scheduler.stop(print_stats=print_stats)

        # Clear subscriptions
        self.event_subscriptions.clear()

        # Clear callbacks
        self.callback_manager.clear_callbacks()

        # Clear assembly cache
        self.assembly_manager.assembled_flows.clear()
        self.assembly_manager.assembly_cache.clear()

        self.current_graph = None

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
            logger.debug(f"No flows listening for event '{subscription_key}'")
            return 0

        logger.debug(f"Dispatching event '{subscription_key}' to {len(flows)} flows")

        # Create trigger
        trigger = Trigger(source_key=subscription_key, payload=payload, timestamp=time.time())

        # Enqueue in each flow's scheduler
        triggered = 0
        for flow in flows:
            if flow.scheduler:
                if flow.scheduler.enqueue_trigger(trigger):
                    triggered += 1
            else:
                logger.warning(f"Flow {flow.flow_id} has no scheduler, cannot trigger")

        return triggered

    def wait_all(self, timeout: Optional[float] = None, stop_after: bool = True):
        """
        Wait for all flows to complete their queued triggers.

        After waiting, optionally stops all scheduler threads so they
        exit their execution loops. This is the primary way to signal
        schedulers to stop waiting for new triggers.

        Args:
            timeout: Maximum time to wait per scheduler (None = wait forever)
            stop_after: Whether to stop schedulers after waiting. Defaults to
                True, which causes threads to exit after processing queued work.
        """
        logger.debug("Waiting for all flows to complete")

        # Wait for all queues to empty
        for flows in self.event_subscriptions.values():
            for flow in flows:
                if flow.scheduler:
                    flow.scheduler.wait_for_completion(timeout)

        # Stop all schedulers if requested
        if stop_after:
            logger.debug("Stopping all schedulers after completion")
            for flows in self.event_subscriptions.values():
                for flow in flows:
                    if flow.scheduler:
                        flow.scheduler.stop(print_stats=False)

        logger.debug("All flows completed")

    def shutdown(self):
        """Shutdown interpreter and cleanup resources"""
        logger.info("Shutting down interpreter")

        # Cleanup current graph - print stats on explicit shutdown
        self._cleanup_current_graph(print_stats=True)

        logger.info("Interpreter shutdown complete")

    def get_statistics(self) -> Dict:
        """
        Get execution statistics.

        Returns:
            Dictionary with statistics from all components including callback topology
        """
        assembly_stats = self.assembly_manager.get_statistics()

        return {
            "current_graph": self.current_graph.graph_id if self.current_graph else None,
            "total_subscriptions": len(self.event_subscriptions),
            "assembly": assembly_stats,
            "callbacks": self.callback_manager.get_statistics(),
            "callback_topology": assembly_stats.get("callback_topology", {}),
            "schedulers": [
                {
                    "flow_id": flow.flow_id,
                    "subscription": flow.get_subscription_key(),
                    "executing": flow.scheduler.is_busy() if flow.scheduler else False,
                    "queued": flow.scheduler.get_queue_size() if flow.scheduler else 0,
                }
                for flows in self.event_subscriptions.values()
                for flow in flows
            ],
        }

    def __str__(self) -> str:
        graph_id = self.current_graph.graph_id if self.current_graph else "None"
        return f"Interpreter(graph={graph_id}, subscriptions={len(self.event_subscriptions)})"
