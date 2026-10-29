"""
Flow Queue - the trigger queue of a single flow.

Each flow has its own queue that:
- Queues incoming triggers under the flow's queue mode (block/drop)
- Hands each queued trigger to its execution group's runner thread
- Runs one frame per trigger when the runner asks it to
"""

from __future__ import annotations
from typing import TYPE_CHECKING, Any, Dict, Optional
from queue import Queue, Empty, Full
from threading import Event, Lock
from enum import Enum
import logging
import time

if TYPE_CHECKING:
    from haywire.core.execution.flow import Flow
    from haywire.core.execution.event_source import Trigger
    from haywire.core.execution.vm import HaywireVM
    from haywire.core.execution.execution_group import ExecutionGroup

logger = logging.getLogger(__name__)


def format_us(value_us: float) -> str:
    """Format a microsecond value with an auto-scaled unit (μs/ms/s)."""
    if value_us >= 1_000_000:
        return f"{value_us / 1_000_000:.2f} s"
    if value_us >= 1_000:
        return f"{value_us / 1_000:.2f} ms"
    return f"{value_us:.2f} μs"


class QueueMode(Enum):
    """How to handle triggers when the flow's queue is full"""

    BLOCK = "block"  # Wait for room in the queue
    DROP = "drop"  # Replace the oldest pending trigger with the new one


class FlowQueue:
    """
    The trigger queue and queue mode of one flow.

    Its frames run on its execution group's runner thread, one at a time, in
    trigger arrival order across all flows of the group. See ``ExecutionGroup``.
    """

    def __init__(
        self,
        flow: Flow,
        vm: HaywireVM,
        queue_mode: QueueMode = QueueMode.BLOCK,
        max_queue_size: int = 100,
        group: Optional[ExecutionGroup] = None,
    ) -> None:
        """
        Initialize the queue.

        Args:
            flow: Flow to manage
            vm: Virtual machine for execution
            queue_mode: How to handle triggers when the queue is full
            max_queue_size: Maximum queued triggers
            group: The execution group whose runner runs this flow's frames;
                ``None`` until the Interpreter has grouped the flows.
        """
        self.flow = flow
        self.vm = vm
        self.queue_mode = queue_mode
        self.max_queue_size = max_queue_size
        self.group = group

        # Trigger queue
        self.trigger_queue: Queue[Trigger] = Queue(maxsize=max_queue_size)
        # Makes DROP's replace-or-put atomic against the runner taking a trigger.
        self._queue_lock = Lock()

        self._is_executing = Event()

        # Execution time statistics (in nanoseconds)
        self._frame_count = 0
        self._exec_time_sum_ns = 0
        self._exec_time_min_ns: Optional[int] = None
        self._exec_time_max_ns: Optional[int] = None
        self._exec_min_iteration: Optional[int] = None
        self._exec_max_iteration: Optional[int] = None

        # Node execution statistics
        self._node_exec_total = 0
        self._node_exec_min: Optional[int] = None
        self._node_exec_max: Optional[int] = None

        logger.debug(f"Created queue for flow {flow.flow_id}")

    def enqueue_trigger(self, trigger: Trigger) -> bool:
        """
        Enqueue a trigger for execution.

        ``DROP`` never waits: when the queue is full, the oldest pending trigger
        is discarded and ``trigger`` takes its place. ``BLOCK`` waits up to 5 s
        for room, except when called from the group's own runner thread (a
        callback emitted from inside a frame), which never waits: a full queue
        then drops ``trigger`` with a warning.

        Args:
            trigger: Trigger to enqueue

        Returns:
            True if enqueued, False if rejected (group stopping) or dropped
        """
        group = self.group
        if group is not None and group.is_stopping():
            logger.debug("Rejecting trigger for %s (stopping)", self.flow.flow_id)
            return False

        if self.queue_mode == QueueMode.DROP:
            with self._queue_lock:
                try:
                    self.trigger_queue.put_nowait(trigger)
                except Full:
                    # The discarded trigger's ready token now stands for the new one.
                    try:
                        self.trigger_queue.get_nowait()
                        self.trigger_queue.task_done()
                    except Empty:
                        pass
                    self.trigger_queue.put_nowait(trigger)
                    logger.debug("Replaced pending trigger for %s (drop mode)", self.flow.flow_id)
                    return True
        elif group is not None and group.is_runner_thread():
            try:
                self.trigger_queue.put_nowait(trigger)
            except Full:
                logger.warning(f"Dropping trigger for {self.flow.flow_id}: queue full (emitted in-group)")
                return False
        else:
            try:
                self.trigger_queue.put(trigger, block=True, timeout=5.0)
            except Full:
                logger.warning(f"Failed to enqueue trigger for {self.flow.flow_id}: queue full")
                return False

        if group is not None:
            group.post(self)
        return True

    def _run_one(self) -> None:
        """Take one pending trigger and run its frame; called by the group's runner."""
        with self._queue_lock:
            try:
                trigger = self.trigger_queue.get_nowait()
            except Empty:
                return
        try:
            self._execute_flow(trigger)
        finally:
            self.trigger_queue.task_done()

    def _discard_pending(self) -> int:
        """Drop every pending trigger, marking each done; return how many were dropped."""
        dropped = 0
        with self._queue_lock:
            while True:
                try:
                    self.trigger_queue.get_nowait()
                except Empty:
                    return dropped
                self.trigger_queue.task_done()
                dropped += 1

    def _execute_flow(self, trigger: Trigger) -> None:
        """Run one frame for ``trigger`` and record its timing; an exception is logged, not raised."""
        self._is_executing.set()

        try:
            self._frame_count += 1

            start_ns = time.perf_counter_ns()

            # >>>>>>>>>>>
            # Execute via VM with timing. The node count is returned (not read
            # off the VM) because the VM instance is shared across all
            # execution groups' runner threads.
            cancel = self.group.cancel if self.group is not None else None
            node_count = self.vm.execute_control_flow(self.flow, trigger, self._frame_count, cancel)
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

            # Update node execution statistics
            self._node_exec_total += node_count
            if self._node_exec_min is None or node_count < self._node_exec_min:
                self._node_exec_min = node_count
            if self._node_exec_max is None or node_count > self._node_exec_max:
                self._node_exec_max = node_count

        except Exception as e:
            logger.error(f"Error executing flow {self.flow.flow_id}: {e}", exc_info=True)

        finally:
            self._is_executing.clear()

    def wait_for_completion(self, timeout: Optional[float] = None) -> bool:
        """
        Wait for all queued triggers to complete.

        ``Queue.join()`` has no timeout, so when a producer keeps feeding the
        queue (e.g. a TickEmit thread emitting callbacks) a bare join never
        returns. We instead wait on the queue's ``all_tasks_done`` condition
        with a deadline so the caller's ``timeout`` is honoured and a still-busy
        queue can never wedge shutdown.

        Args:
            timeout: Maximum time to wait (None = wait forever)

        Returns:
            True if the queue drained, False if the timeout elapsed first
        """
        if timeout is None:
            self.trigger_queue.join()
            return True

        deadline = time.monotonic() + timeout
        with self.trigger_queue.all_tasks_done:
            while self.trigger_queue.unfinished_tasks:
                remaining = deadline - time.monotonic()
                if remaining <= 0.0:
                    return False
                self.trigger_queue.all_tasks_done.wait(timeout=remaining)
        return True

    def log_stats(self) -> None:
        """Log this flow's execution statistics."""
        stats = self.get_execution_stats()
        if stats["min_us"] is not None:
            logger.warning(
                f"\n--------------------------------------------------------\n"
                f"Total Runs            : {stats['count']} iterations for {self.flow.flow_id}\n"
                f"Total Executed Nodes  : {stats['nodes_total']}\n"
                f"Executed Nodes per run: {stats['nodes_avg']:.0f} avg\n"
                f"Executed Nodes range  : {stats['nodes_min']}-{stats['nodes_max']}\n"
                f"Min time per run      : {format_us(stats['min_us'])} "
                f"(iteration {stats['min_iteration']})\n"
                f"Max time per run      : {format_us(stats['max_us'])} "
                f"(iteration {stats['max_iteration']})\n"
                f"Avg time per run      : {format_us(stats['avg_us'])}\n"
                f"Avg time per node     : {format_us(stats['avg_us'] / stats['nodes_avg'])}"
                f"\n--------------------------------------------------------\n"
            )
        else:
            logger.warning(f"\nExecutions: 0 for {self.flow.flow_id}")

    def get_queue_size(self) -> int:
        """Get current number of queued triggers."""
        return self.trigger_queue.qsize()

    def is_busy(self) -> bool:
        """Check if flow is currently executing."""
        return self._is_executing.is_set()

    def get_execution_stats(self) -> Dict[str, Any]:
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

                stats = flow.queue.get_execution_stats()
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
                "nodes_total": 0,
                "nodes_min": None,
                "nodes_max": None,
                "nodes_avg": None,
            }

        return {
            "count": self._frame_count,
            "min_us": self._exec_time_min_ns / 1_000 if self._exec_time_min_ns else None,
            "max_us": self._exec_time_max_ns / 1_000 if self._exec_time_max_ns else None,
            "avg_us": (self._exec_time_sum_ns / self._frame_count) / 1_000,
            "total_us": self._exec_time_sum_ns / 1_000,
            "min_iteration": self._exec_min_iteration,
            "max_iteration": self._exec_max_iteration,
            "nodes_total": self._node_exec_total,
            "nodes_min": self._node_exec_min,
            "nodes_max": self._node_exec_max,
            "nodes_avg": self._node_exec_total / self._frame_count,
        }

    def __str__(self) -> str:
        return (
            f"FlowQueue(flow={self.flow.flow_id}, "
            f"executing={self.is_busy()}, "
            f"queued={self.get_queue_size()})"
        )
