"""
Flow Scheduler - Manages execution of a single flow.

Each flow has its own scheduler that:
- Queues incoming triggers
- Manages execution thread
- Prevents concurrent execution of same flow
- Handles trigger queue modes (block/drop)
"""
from __future__ import annotations
from typing import TYPE_CHECKING, Optional
from queue import Queue, Empty
from threading import Thread, Event
from enum import Enum
import logging
import time

if TYPE_CHECKING:
    from haywire.core.execution.flow import Flow
    from haywire.core.execution.event_source import Trigger
    from haywire.core.execution.vm import HaywireVM

logger = logging.getLogger(__name__)


class QueueMode(Enum):
    """How to handle triggers when flow is already executing"""
    BLOCK = "block"  # Queue triggers and wait
    DROP = "drop"    # Drop incoming triggers


class FlowScheduler:
    """
    Manages execution of a single flow.
    
    Responsibilities:
    - Queue incoming triggers
    - Ensure single-threaded execution
    - Handle queue overflow based on mode
    - Manage execution thread lifecycle
    - Signal completion for backpressure
    """
    
    def __init__(
        self, 
        flow: 'Flow',
        vm: 'HaywireVM',
        queue_mode: QueueMode = QueueMode.BLOCK,
        max_queue_size: int = 100
    ):
        """
        Initialize scheduler.
        
        Args:
            flow: Flow to manage
            vm: Virtual machine for execution
            queue_mode: How to handle triggers when executing
            max_queue_size: Maximum queued triggers
        """
        self.flow = flow
        self.vm = vm
        self.queue_mode = queue_mode
        self.max_queue_size = max_queue_size
        
        # Trigger queue
        self.trigger_queue: Queue['Trigger'] = Queue(maxsize=max_queue_size)
        
        # Thread management - use Event for lock-free status check
        self.execution_thread: Optional[Thread] = None
        self._is_executing = Event()
        self.should_stop = False
        
        logger.debug(f"Created scheduler for flow {flow.flow_id}")
    
    def enqueue_trigger(self, trigger: 'Trigger') -> bool:
        """
        Enqueue a trigger for execution.
        
        Args:
            trigger: Trigger to enqueue
            
        Returns:
            True if enqueued successfully, False if dropped
        """
        # Check if we should drop
        if self.queue_mode == QueueMode.DROP and self._is_executing.is_set():
            logger.debug(
                f"Dropping trigger for {self.flow.flow_id} "
                f"(already executing)"
            )
            return False
        
        try:
            # Try to enqueue
            if self.queue_mode == QueueMode.BLOCK:
                self.trigger_queue.put(trigger, block=True, timeout=5.0)
            else:
                self.trigger_queue.put(trigger, block=False)
            
            logger.debug(
                f"Enqueued trigger for {self.flow.flow_id} "
                f"(queue size: {self.trigger_queue.qsize()})"
            )
            
            # Start execution thread if not running
            self._ensure_execution_thread()
            
            return True
            
        except Exception as e:
            logger.warning(
                f"Failed to enqueue trigger for {self.flow.flow_id}: {e}"
            )
            return False
    
    def _ensure_execution_thread(self):
        """Start execution thread if not already running."""
        if self.execution_thread is None or not self.execution_thread.is_alive():
            self.should_stop = False
            self.execution_thread = Thread(
                target=self._execution_loop,
                name=f"FlowExec-{self.flow.flow_id}",
                daemon=True
            )
            self.execution_thread.start()
            logger.debug(f"Started execution thread for {self.flow.flow_id}")
    
    def _call_startup(self):
        """
        Call startup() on all nodes in the flow.
        
        Creates a minimal execution context for startup calls.
        """
        from haywire.core.execution.execution_context import ExecutionContext
        
        local_context = self.vm._create_local_context(self.flow)
        exec_ctx = ExecutionContext(
            global_ctx=self.vm.global_context,
            local_ctx=local_context,
            trigger=None,
            vm=self.vm
        )
        
        logger.debug(f"Calling startup() on all nodes in flow {self.flow.flow_id}")
        
        for wrapper in self.flow.get_all_node_wrappers():
            wrapper._startup(exec_ctx)
    
    def _call_shutdown(self):
        """
        Call shutdown() on all nodes in the flow.
        
        Creates a minimal execution context for shutdown calls.
        """
        from haywire.core.execution.execution_context import ExecutionContext
        
        local_context = self.vm._create_local_context(self.flow)
        exec_ctx = ExecutionContext(
            global_ctx=self.vm.global_context,
            local_ctx=local_context,
            trigger=None,
            vm=self.vm
        )
        
        logger.debug(
            f"Calling shutdown() on all nodes in flow {self.flow.flow_id}"
        )
        
        for wrapper in self.flow.get_all_node_wrappers():
            wrapper._shutdown(exec_ctx)
            logger.debug(f"Called shutdown on {wrapper.node_id}")
    
    def _execution_loop(self):
        """
        Main execution loop (runs in separate thread).
        
        Continuously processes triggers from queue until stopped.
        """
        logger.debug(f"Execution loop started for {self.flow.flow_id}")
        
        # Call startup() on all nodes before processing any triggers
        try:
            self._call_startup()
        except Exception as e:
            logger.error(
                f"Error during startup phase for {self.flow.flow_id}: {e}",
                exc_info=True
            )
        
        while not self.should_stop:
            try:
                # Wait for next trigger (with timeout for clean shutdown)
                trigger = self.trigger_queue.get(timeout=0.5)
                
                # Execute flow with this trigger
                self._execute_flow(trigger)
                
                # Mark task done
                self.trigger_queue.task_done()
                
            except Empty:
                # No triggers, check if we should stop
                if self.trigger_queue.empty() and not self.should_stop:
                    # No more work, thread can exit
                    break
                continue
            
            except Exception as e:
                logger.error(
                    f"Error in execution loop for {self.flow.flow_id}: {e}",
                    exc_info=True
                )
        
        # Call shutdown() on all nodes after processing is complete
        try:
            self._call_shutdown()
        except Exception as e:
            logger.error(
                f"Error during shutdown phase for {self.flow.flow_id}: {e}",
                exc_info=True
            )
        
        logger.debug(f"Execution loop ended for {self.flow.flow_id}")
    
    def _execute_flow(self, trigger: 'Trigger'):
        """
        Execute flow with given trigger.
        
        Args:
            trigger: Trigger that activated this execution
        """
        self._is_executing.set()
        
        try:
            logger.debug(
                f"Executing flow {self.flow.flow_id} "
                f"with trigger {trigger.source_key}"
            )
            
            # Execute via VM with timing
            start_ns = time.perf_counter_ns()
            self.vm.execute_control_flow(self.flow, trigger)
            elapsed_ns = time.perf_counter_ns() - start_ns
            
            logger.info(
                f"Flow {self.flow.flow_id} completed in "
                f"{elapsed_ns / 1_000:.2f} μs"
            )
            
        except Exception as e:
            logger.error(
                f"Error executing flow {self.flow.flow_id}: {e}",
                exc_info=True
            )
        
        finally:
            self._is_executing.clear()
            
            # Signal completion for backpressure
            if trigger.payload:
                on_complete = trigger.payload.get('_on_complete')
                if on_complete and callable(on_complete):
                    try:
                        on_complete()
                    except Exception as e:
                        logger.warning(f"Error in completion callback: {e}")
    
    def wait_for_completion(self, timeout: Optional[float] = None):
        """
        Wait for all queued triggers to complete.
        
        Args:
            timeout: Maximum time to wait (None = wait forever)
        """
        self.trigger_queue.join()
    
    def stop(self):
        """Stop the scheduler and wait for thread to exit."""
        logger.debug(f"Stopping scheduler for {self.flow.flow_id}")
        self.should_stop = True
        
        if self.execution_thread and self.execution_thread.is_alive():
            self.execution_thread.join(timeout=2.0)
            
            if self.execution_thread.is_alive():
                logger.warning(
                    f"Execution thread for {self.flow.flow_id} did not exit cleanly"
                )
        
        logger.debug(f"Scheduler stopped for {self.flow.flow_id}")
    
    def get_queue_size(self) -> int:
        """Get current number of queued triggers."""
        return self.trigger_queue.qsize()
    
    def is_busy(self) -> bool:
        """Check if flow is currently executing."""
        return self._is_executing.is_set()
    
    def __str__(self) -> str:
        return (
            f"FlowScheduler(flow={self.flow.flow_id}, "
            f"executing={self.is_busy()}, "
            f"queued={self.get_queue_size()})"
        )