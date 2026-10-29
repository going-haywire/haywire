"""
Execution groups - the unit of execution threading.

Flows that share a control node form one execution group, and each group
runs its frames one at a time on a single runner thread. Data nodes never
join groups; a data node executed by several groups is a *shared data node*
and runs under its wrapper's ``exec_lock``. See ADR 0064.
"""

from __future__ import annotations
from typing import TYPE_CHECKING, Dict, List, Optional, Protocol, Sequence, Set
import logging
import queue
import threading
import time

if TYPE_CHECKING:
    from haywire.core.execution.flow import Flow
    from haywire.core.execution.flow_queue import FlowQueue
    from haywire.core.execution.vm import HaywireVM
    from haywire.core.node import BaseNode

logger = logging.getLogger(__name__)


class _HasNodeId(Protocol):
    @property
    def node_id(self) -> str: ...


class _GroupableFlow(Protocol):
    def get_entry_node_id(self) -> str: ...

    def get_control_node_ids(self) -> List[str]: ...

    def get_all_nodes(self) -> Sequence[_HasNodeId]: ...


def group_flows[F: _GroupableFlow](flows: Sequence[F]) -> list[list[F]]:
    """Partition ``flows`` into execution groups: flows that share a control node share a group.

    Sharing is transitive and counts each flow's entry event node as a control
    node. Groups are ordered by the first appearance of any of their flows in
    ``flows``; flows inside a group keep their input order.
    """
    parent = list(range(len(flows)))

    def find(i: int) -> int:
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i

    owner: Dict[str, int] = {}
    for index, flow in enumerate(flows):
        for node_id in (flow.get_entry_node_id(), *flow.get_control_node_ids()):
            first = owner.setdefault(node_id, index)
            root_a, root_b = find(first), find(index)
            if root_a != root_b:
                parent[max(root_a, root_b)] = min(root_a, root_b)

    groups: Dict[int, list[F]] = {}
    for index, flow in enumerate(flows):
        groups.setdefault(find(index), []).append(flow)
    return list(groups.values())


def shared_data_node_ids(groups: Sequence[Sequence[_GroupableFlow]]) -> frozenset[str]:
    """Return the ids of data nodes that more than one group executes."""
    control_ids: Set[str] = set()
    for group in groups:
        for flow in group:
            control_ids.add(flow.get_entry_node_id())
            control_ids.update(flow.get_control_node_ids())

    seen_in: Dict[str, int] = {}
    shared: Set[str] = set()
    for index, group in enumerate(groups):
        for flow in group:
            for node in flow.get_all_nodes():
                node_id = node.node_id
                if node_id in control_ids:
                    continue
                first = seen_in.setdefault(node_id, index)
                if first != index:
                    shared.add(node_id)
    return frozenset(shared)


class ExecutionGroup:
    """One runner thread that runs the frames of a set of flows, one frame at a time.

    Each flow keeps its own trigger queue (``FlowQueue``); every trigger a
    queue accepts posts one ready token here, and the runner takes tokens
    in arrival order, so frames run strictly first-in first-out across the
    group's flows. Before its first frame the runner retains every node the
    group executes (the first retain of a node calls its ``on_startup``); after
    its last frame it releases them (the last release calls ``on_shutdown``).

    Example::

        group = ExecutionGroup("group_flow_a", [flow_a, flow_b], vm)
        for flow in group.flows:
            flow.queue.group = group
        group.start()                      # FlowExec-group_flow_a, runs on_startup
        flow_a.queue.enqueue_trigger(trigger)
        flow_a.queue.wait_for_completion(1.0)
        group.stop(timeout_s=2.0)          # True once the runner has exited
    """

    def __init__(self, group_id: str, flows: List["Flow"], vm: "HaywireVM"):
        self.group_id = group_id
        self.flows = flows
        self.vm = vm

        nodes: List["BaseNode"] = []
        seen: Set[str] = set()
        for flow in flows:
            for node in flow.get_all_nodes():
                if node.node_id not in seen:
                    seen.add(node.node_id)
                    nodes.append(node)
        self.nodes = nodes
        """Every node the group executes, deduplicated, in first-seen order."""

        self.cancel = threading.Event()
        """Set when a ``stop()`` escalates to ``kill()``: the running frame ends at its next control node."""

        self._ready: "queue.Queue[Optional[FlowQueue]]" = queue.Queue()
        """Ready tokens in arrival order; ``None`` tells the runner to exit."""
        self._stop = threading.Event()
        self._exited = threading.Event()
        self._thread: Optional[threading.Thread] = None
        self._gave_up = False

        # Frame barrier: the runner enters a frame only while not held.
        self._barrier = threading.Condition()
        self._held = False
        self._in_frame = False

    def start(self) -> None:
        """Start the runner thread ``FlowExec-<group_id>``."""
        self._thread = threading.Thread(target=self._run, name=f"FlowExec-{self.group_id}", daemon=True)
        self._thread.start()
        logger.debug(f"Started runner for {self.group_id} ({len(self.flows)} flows)")

    def post(self, flow_queue: "FlowQueue") -> None:
        """Announce one trigger newly queued on ``flow_queue``."""
        self._ready.put(flow_queue)

    def is_runner_thread(self) -> bool:
        """Return ``True`` when called on this group's runner thread."""
        return self._thread is not None and threading.current_thread() is self._thread

    def is_stopping(self) -> bool:
        """Return ``True`` once ``stop()`` has been called."""
        return self._stop.is_set()

    @property
    def is_abandoned(self) -> bool:
        """``True`` while the runner thread is still alive after ``stop()`` gave up on it."""
        return self._gave_up and self._thread is not None and self._thread.is_alive()

    def stop(self, timeout_s: float = 2.0, kill_timeout_s: float = 2.0) -> bool:
        """Stop the runner after its running frame, and wait for it to exit.

        Triggers still queued are discarded. A runner still busy after
        ``timeout_s`` is killed (see ``kill()``), so this returns within
        ``timeout_s + kill_timeout_s``.

        Returns:
            ``True`` when the runner exited (or never started); ``False``
            leaves the group abandoned.
        """
        self._stop.set()
        self._ready.put(None)
        self._wake()
        if self._thread is None or self._exited.is_set():
            return True
        if self.is_runner_thread() or self._gave_up:
            return False
        if self._exited.wait(timeout=timeout_s):
            return True
        logger.warning(f"Runner for {self.group_id} did not stop within {timeout_s}s; killing it")
        return self.kill(kill_timeout_s)

    def kill(self, timeout_s: float = 2.0) -> bool:
        """End the run now: discard queued triggers and end the running frame at its next control node.

        The escalation of a ``stop()`` that timed out. Nodes still get
        ``on_shutdown`` when the runner exits.

        Returns:
            ``True`` when the runner exited within ``timeout_s`` (or never
            started); ``False`` leaves the group abandoned (``is_abandoned``).
        """
        self._stop.set()
        self.cancel.set()
        for flow in self.flows:
            if flow.queue is not None:
                flow.queue._discard_pending()
        self._ready.put(None)
        self._wake()
        if self._thread is None:
            return True
        if self.is_runner_thread():
            return False
        if self._exited.wait(timeout=timeout_s):
            return True
        self._gave_up = True
        logger.error(f"Runner for {self.group_id} did not exit within {timeout_s}s of a kill; abandoned")
        return False

    def hold(self, timeout_s: float = 2.0) -> bool:
        """Park the runner at the frame barrier, waiting up to ``timeout_s`` for the running frame to end.

        The hold stays set either way, so the runner parks once its frame ends.

        Returns:
            ``True`` when no frame of this group runs; ``False`` when the
            running frame outlasted ``timeout_s``.
        """
        deadline = time.monotonic() + timeout_s
        with self._barrier:
            self._held = True
            while self._in_frame and not self._exited.is_set():
                remaining = deadline - time.monotonic()
                if remaining <= 0.0:
                    return False
                self._barrier.wait(timeout=min(remaining, 0.1))
            return True

    def release(self) -> None:
        """End a ``hold()``: the runner resumes with its next pending trigger."""
        with self._barrier:
            self._held = False
            self._barrier.notify_all()

    def _wake(self) -> None:
        with self._barrier:
            self._barrier.notify_all()

    def _enter_frame(self) -> bool:
        """Wait at the frame barrier while held; return ``False`` when stopped meanwhile."""
        with self._barrier:
            while self._held and not self._stop.is_set():
                self._barrier.wait()
            if self._stop.is_set():
                return False
            self._in_frame = True
            return True

    def _leave_frame(self) -> None:
        with self._barrier:
            self._in_frame = False
            self._barrier.notify_all()

    def _run(self) -> None:
        context_flow: Flow = self.flows[0]
        self.vm.call_startup(self.nodes, context_flow, self.cancel)
        try:
            while True:
                token: Optional[FlowQueue] = self._ready.get()
                if token is None or self._stop.is_set():
                    break
                if not self._enter_frame():
                    break
                try:
                    token._run_one()
                finally:
                    self._leave_frame()
        except Exception as e:
            logger.error(f"Fatal error in runner for {self.group_id}: {e}", exc_info=True)
        finally:
            for flow in self.flows:
                if flow.queue is not None:
                    flow.queue._discard_pending()
            self.vm.call_shutdown(self.nodes, context_flow, self.cancel)
            self._exited.set()
