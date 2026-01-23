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
from threading import Thread, Lock
from enum import Enum
import logging

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
    - Ensure single-threaded execution (lock flow during execution)
    - Handle queue overflow based on mode
    - Manage execution thread lifecycle
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
        
        # Thread management
        self.execution_thread: Optional[Thread] = None
        self.lock = Lock()
        self.is_executing = False
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
        if self.queue_mode == QueueMode.DROP and self.is_executing:
            logger.debug(
                f"Dropping trigger for {self.flow.flow_id} "
                f"(already executing)"
            )
            return False
        
        try:
            # Try to enqueue (may block or raise if full)
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
        """Start execution thread if not already running"""
        with self.lock:
            if self.execution_thread is None or not self.execution_thread.is_alive():
                self.should_stop = False
                self.execution_thread = Thread(
                    target=self._execution_loop,
                    name=f"FlowExec-{self.flow.flow_id}",
                    daemon=True
                )
                self.execution_thread.start()
                logger.debug(f"Started execution thread for {self.flow.flow_id}")
    
    def _execution_loop(self):
        """
        Main execution loop (runs in separate thread).
        
        Continuously processes triggers from queue until stopped.
        """
        logger.debug(f"Execution loop started for {self.flow.flow_id}")
        
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
        
        logger.debug(f"Execution loop ended for {self.flow.flow_id}")
    
    def _execute_flow(self, trigger: 'Trigger'):
        """
        Execute flow with given trigger.
        
        Args:
            trigger: Trigger that activated this execution
        """
        with self.lock:
            if self.is_executing:
                logger.warning(
                    f"Flow {self.flow.flow_id} already executing "
                    f"(should not happen with proper locking)"
                )
                return
            
            self.is_executing = True
        
        try:
            logger.debug(
                f"Executing flow {self.flow.flow_id} "
                f"with trigger {trigger.source_key}"
            )
            
            # Execute via VM
            self.vm.execute_control_flow(self.flow, trigger)
            
            logger.debug(f"Flow {self.flow.flow_id} execution completed")
            
        except Exception as e:
            logger.error(
                f"Error executing flow {self.flow.flow_id}: {e}",
                exc_info=True
            )
        
        finally:
            with self.lock:
                self.is_executing = False
    
    def wait_for_completion(self, timeout: Optional[float] = None):
        """
        Wait for all queued triggers to complete.
        
        Args:
            timeout: Maximum time to wait (None = wait forever)
        """
        if timeout:
            self.trigger_queue.join()  # Wait with timeout not directly supported
        else:
            self.trigger_queue.join()
    
    def stop(self):
        """Stop the scheduler and wait for thread to exit"""
        logger.debug(f"Stopping scheduler for {self.flow.flow_id}")
        self.should_stop = True
        
        if self.execution_thread and self.execution_thread.is_alive():
            self.execution_thread.join(timeout=2.0)
        
        logger.debug(f"Scheduler stopped for {self.flow.flow_id}")
    
    def get_queue_size(self) -> int:
        """Get current number of queued triggers"""
        return self.trigger_queue.qsize()
    
    def is_busy(self) -> bool:
        """Check if flow is currently executing"""
        return self.is_executing
    
    def __str__(self) -> str:
        return (
            f"FlowScheduler(flow={self.flow.flow_id}, "
            f"executing={self.is_executing}, "
            f"queued={self.get_queue_size()})"
        )
