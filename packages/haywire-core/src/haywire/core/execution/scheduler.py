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


# Sentinel object for signaling shutdown via queue
_SHUTDOWN_SENTINEL = object()


class QueueMode(Enum):
    """How to handle triggers when flow is already executing"""

    BLOCK = "block"  # Queue triggers and wait
    DROP = "drop"  # Drop incoming triggers


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
        flow: "Flow",
        vm: "HaywireVM",
        queue_mode: QueueMode = QueueMode.BLOCK,
        max_queue_size: int = 100,
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
        self.trigger_queue: Queue = Queue(maxsize=max_queue_size)

        # Thread management with Events for coordination
        self.execution_thread: Optional[Thread] = None
        self._is_executing = Event()
        self._stop_requested = Event()
        self._thread_exited = Event()

        # Execution time statistics (in nanoseconds)
        self._frame_count = 0
        self._exec_time_sum_ns = 0
        self._exec_time_min_ns: Optional[int] = None
        self._exec_time_max_ns: Optional[int] = None
        self._exec_min_iteration: Optional[int] = None
        self._exec_max_iteration: Optional[int] = None

        logger.debug(f"Created scheduler for flow {flow.flow_id}")

    def enqueue_trigger(self, trigger: "Trigger") -> bool:
        """
        Enqueue a trigger for execution.

        Args:
            trigger: Trigger to enqueue

        Returns:
            True if enqueued successfully, False if dropped
        """
        # Don't accept triggers if stopping
        if self._stop_requested.is_set():
            logger.debug(f"Rejecting trigger for {self.flow.flow_id} (stopping)")
            return False

        # Check if we should drop
        if self.queue_mode == QueueMode.DROP and self._is_executing.is_set():
            logger.debug(f"Dropping trigger for {self.flow.flow_id} (already executing)")
            return False

        try:
            # Try to enqueue
            if self.queue_mode == QueueMode.BLOCK:
                self.trigger_queue.put(trigger, block=True, timeout=5.0)
            else:
                self.trigger_queue.put(trigger, block=False)

            logger.debug(
                f"Enqueued trigger for {self.flow.flow_id} (queue size: {self.trigger_queue.qsize()})"
            )

            return True

        except Exception as e:
            logger.warning(f"Failed to enqueue trigger for {self.flow.flow_id}: {e}")
            return False

    def start(self):
        """
        Start execution thread.

        Thread will stay alive until explicitly stopped, sleeping while
        waiting for triggers to arrive in the queue.
        """
        # Check if thread exists and is alive
        if self.execution_thread is not None and self.execution_thread.is_alive():
            logger.debug(f"Execution thread for {self.flow.flow_id} already running")
            return

        # Wait for previous thread to fully exit if needed
        if self.execution_thread is not None:
            self._thread_exited.wait(timeout=1.0)

        # Reset events for new thread
        self._stop_requested.clear()
        self._thread_exited.clear()

        # Create and start new execution thread
        self.execution_thread = Thread(
            target=self._execution_loop, name=f"FlowExec-{self.flow.flow_id}", daemon=True
        )

        self.execution_thread.start()
        logger.debug(f"Started execution thread for {self.flow.flow_id}")

    def _execution_loop(self):
        """
        Main execution loop (runs in separate thread).

        Stays alive and blocks waiting for triggers until explicitly stopped.
        Thread only exits when stop is requested or shutdown sentinel is received.
        """
        self.vm.call_flow_startup(self.flow)

        self._frame_count = 0

        try:
            while not self._stop_requested.is_set():
                try:
                    # Block indefinitely waiting for trigger or shutdown sentinel
                    trigger = self.trigger_queue.get()

                    # Check for shutdown sentinel
                    if trigger is _SHUTDOWN_SENTINEL:
                        self.trigger_queue.task_done()
                        break

                    # Execute flow with this trigger
                    self._execute_flow(trigger)

                    # Mark task done
                    self.trigger_queue.task_done()

                except Empty:
                    # Should not happen with blocking get(), but handle gracefully
                    continue

        except Exception as e:
            logger.error(f"Fatal error in execution loop for {self.flow.flow_id}: {e}", exc_info=True)

        finally:
            self.vm.call_flow_shutdown(self.flow)

            # Signal that thread has exited
            self._thread_exited.set()

    def _execute_flow(self, trigger: "Trigger"):
        """
        Execute flow with given trigger.

        Args:
            trigger: Trigger that activated this execution
        """
        self._is_executing.set()

        try:
            queue_depth = self.trigger_queue.qsize()
            if queue_depth > 0:
                logger.info(f"Queue depth at execution: {queue_depth}")

            self._frame_count += 1

            start_ns = time.perf_counter_ns()

            # >>>>>>>>>>>
            # Execute via VM with timing
            self.vm.execute_control_flow(self.flow, trigger, self._frame_count)
            # >>>>>>>>>>>

            elapsed_ns = time.perf_counter_ns() - start_ns

            # Update execution statistics
            self._exec_time_sum_ns += elapsed_ns
            if self._exec_time_min_ns is None or elapsed_ns < self._exec_time_min_ns:
                self._exec_time_min_ns = elapsed_ns
                self._exec_min_iteration = self._frame_count
            if self._exec_time_max_ns is None or elapsed_ns > self._exec_time_max_ns:
                self._exec_time_max_ns = elapsed_ns
                self._exec_max_iteration = self._frame_count

        except Exception as e:
            logger.error(f"Error executing flow {self.flow.flow_id}: {e}", exc_info=True)

        finally:
            self._is_executing.clear()

            # Signal completion for backpressure
            if trigger.payload:
                on_complete = trigger.payload.get("_on_complete")
                if on_complete and callable(on_complete):
                    try:
                        on_complete()
                    except Exception as e:
                        logger.warning(f"Error in completion callback: {e}")

    def wait_for_completion(self, timeout: Optional[float] = None) -> bool:
        """
        Wait for all queued triggers to complete.

        Args:
            timeout: Maximum time to wait (None = wait forever)

        Returns:
            True if completed, False if timed out
        """
        # Use join with timeout for queue completion
        self.trigger_queue.join()
        return True

    def stop(self, timeout: float = 2.0, print_stats: bool = False) -> bool:
        """
        Stop the scheduler and wait for thread to exit.

        Args:
            timeout: Maximum time to wait for clean shutdown
            print_stats: Whether to print execution statistics on stop

        Returns:
            True if stopped cleanly, False if forced
        """
        logger.debug(f"Stopping scheduler for {self.flow.flow_id}")

        # Signal stop request
        self._stop_requested.set()

        # Send shutdown sentinel to wake up blocked get()
        try:
            self.trigger_queue.put_nowait(_SHUTDOWN_SENTINEL)
        except Exception:
            pass  # Queue full, thread will see stop_requested on timeout

        # Wait for thread to exit
        clean_exit = True
        if self.execution_thread and self.execution_thread.is_alive():
            # Use event wait for more responsive shutdown
            if not self._thread_exited.wait(timeout=timeout):
                logger.warning(
                    f"Execution thread for {self.flow.flow_id} did not exit cleanly within {timeout}s"
                )
                clean_exit = False

        # Only print stats if explicitly requested (not during cleanup)
        if print_stats:
            stats = self.get_execution_stats()
            if stats["min_us"] is not None:
                logger.warning(
                    f"\nExecutions: {stats['count']} for {self.flow.flow_id}\n"
                    f"Min: {stats['min_us']:.2f} μs "
                    f"(iteration {stats['min_iteration']})\n"
                    f"Max: {stats['max_us']:.2f} μs "
                    f"(iteration {stats['max_iteration']})\n"
                    f"Avg: {stats['avg_us']:.2f} μs"
                )
            else:
                logger.warning(f"\nExecutions: 0 for {self.flow.flow_id}")

        logger.debug(f"Scheduler stopped for {self.flow.flow_id}")

        return clean_exit

    def get_queue_size(self) -> int:
        """Get current number of queued triggers."""
        return self.trigger_queue.qsize()

    def is_busy(self) -> bool:
        """Check if flow is currently executing."""
        return self._is_executing.is_set()

    def is_running(self) -> bool:
        """Check if execution thread is running."""
        return self.execution_thread is not None and self.execution_thread.is_alive()

    def get_execution_stats(self) -> dict:
        """
        Get execution time statistics.

        Returns:
            Dictionary containing execution statistics:
            - count: Number of executions
            - min_us: Minimum execution time in microseconds
            - max_us: Maximum execution time in microseconds
            - avg_us: Average execution time in microseconds
            - total_us: Total execution time in microseconds
            - min_iteration: Execution number with minimum time
            - max_iteration: Execution number with maximum time

        Examples:
            Basic usage:

            .. code-block:: python

                stats = scheduler.get_execution_stats()
                print(f"Avg: {stats['avg_us']:.2f} μs")
                print(f"Min at iteration {stats['min_iteration']}")
        """
        if self._frame_count == 0:
            return {
                "count": 0,
                "min_us": None,
                "max_us": None,
                "avg_us": None,
                "total_us": None,
                "min_iteration": None,
                "max_iteration": None,
            }

        return {
            "count": self._frame_count,
            "min_us": self._exec_time_min_ns / 1_000 if self._exec_time_min_ns else None,
            "max_us": self._exec_time_max_ns / 1_000 if self._exec_time_max_ns else None,
            "avg_us": (self._exec_time_sum_ns / self._frame_count) / 1_000,
            "total_us": self._exec_time_sum_ns / 1_000,
            "min_iteration": self._exec_min_iteration,
            "max_iteration": self._exec_max_iteration,
        }

    def __str__(self) -> str:
        return (
            f"FlowScheduler(flow={self.flow.flow_id}, "
            f"running={self.is_running()}, "
            f"executing={self.is_busy()}, "
            f"queued={self.get_queue_size()})"
        )
