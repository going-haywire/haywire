"""Graceful stop, its escalation to a kill, and abandoned runners of execution groups (ADR 0064).

Chains of stub control nodes run through the real ``HaywireVM`` control loop,
so the kill flag is checked exactly where production checks it.
"""

import threading
import time
from types import SimpleNamespace
from typing import Any, Callable, Dict, List, Optional, Sequence

import pytest

from haywire.core.execution.execution_group import ExecutionGroup
from haywire.core.execution.event_source import Trigger
from haywire.core.execution.flow import ControlFlowGraph, ControlNodeInfo, Flow, LocalizedDataFlow
from haywire.core.execution.interpreter import Interpreter
from haywire.core.execution.flow_queue import FlowQueue
from haywire.core.execution.vm import HaywireVM
from haywire.core.node.base import BaseNode
from haywire.core.node.node_wrapper import NodeWrapper


def _wrapper() -> NodeWrapper:
    wrapper = NodeWrapper.__new__(NodeWrapper)
    wrapper.exec_lock = threading.Lock()
    wrapper._run_refs = 0
    return wrapper


class _Node:
    """Stub control node: runs ``work`` then follows outlet ``next``."""

    on_startup = BaseNode.on_startup
    on_shutdown = BaseNode.on_shutdown
    on_frame_start = BaseNode.on_frame_start
    on_frame_end = BaseNode.on_frame_end

    def __init__(self, node_id: str, ran: List[str], work: Optional[Callable[[Any], None]] = None):
        self.node_id = node_id
        self.wrapper = _wrapper()
        self.ran = ran
        self.work = work

    def _execute(self, context) -> Optional[str]:
        self.ran.append(self.node_id)
        if self.work is not None:
            self.work(context)
        return "next"


class _FrameEndNode(_Node):
    def __init__(self, node_id: str, ran: List[str], work=None):
        super().__init__(node_id, ran, work)
        self.frame_ends = 0

    def on_frame_end(self, context):  # type: ignore[override]
        self.frame_ends += 1


class _ShutdownNode(_Node):
    def __init__(self, node_id: str, ran: List[str], work=None):
        super().__init__(node_id, ran, work)
        self.shutdowns = 0

    def on_shutdown(self, context):  # type: ignore[override]
        self.shutdowns += 1


class _SharedDataNode(_Node):
    """A shared data node whose worker parks on ``block`` for triggers in ``park_on``."""

    def __init__(self, node_id: str, park_on: str):
        super().__init__(node_id, [])
        self.park_on = park_on
        self.inside = threading.Event()
        self.block = threading.Event()
        self.shutdowns = 0

    def _execute(self, context) -> None:
        if context.trigger.source_key == self.park_on:
            self.inside.set()
            self.block.wait(10.0)
        return None

    def on_shutdown(self, context):  # type: ignore[override]
        self.shutdowns += 1


def _flow(
    flow_id: str, nodes: Sequence[_Node], cycle: bool = False, data: Optional[List[Any]] = None
) -> Flow:
    infos: Dict[str, ControlNodeInfo] = {}
    for index, node in enumerate(nodes):
        if index + 1 < len(nodes):
            outlets = {"next": (nodes[index + 1].node_id, "in")}
        else:
            outlets = {"next": (nodes[0].node_id, "in")} if cycle else {}
        infos[node.node_id] = ControlNodeInfo(node=node, outlet_map=outlets)  # type: ignore[arg-type]
    if data:
        first = nodes[0].node_id
        infos[first].localized_data_flow = LocalizedDataFlow(first, data)
    flow = Flow(flow_id, nodes[0], SimpleNamespace(), SimpleNamespace(variables={}))  # type: ignore[arg-type]
    flow.control_graph = ControlFlowGraph(entry_node=nodes[0], control_nodes=infos)  # type: ignore[arg-type]
    return flow


def _group(flow: Flow, vm: HaywireVM, gid: str) -> ExecutionGroup:
    flow.queue = FlowQueue(flow, vm)
    group = ExecutionGroup(gid, [flow], vm)
    flow.queue.group = group
    return group


def _enqueue(flow: Flow, key: str) -> bool:
    assert flow.queue is not None
    return flow.queue.enqueue_trigger(Trigger(source_key=key, payload=None, timestamp=time.time()))


@pytest.mark.unit
def test_kill_ends_frame_at_next_control_node():
    ran: List[str] = []
    third = threading.Event()

    def park(context):
        third.set()
        time.sleep(0.2)

    nodes: List[_Node] = [_FrameEndNode("n1", ran)]
    nodes += [_Node(f"n{i}", ran, park if i == 3 else None) for i in range(2, 11)]
    flow = _flow("chain", nodes)
    group = _group(flow, HaywireVM(), "g")
    group.start()
    assert _enqueue(flow, "t")
    assert third.wait(2.0)
    assert group.kill(2.0) is True
    assert ran == ["n1", "n2", "n3"]
    first = nodes[0]
    assert isinstance(first, _FrameEndNode)
    assert first.frame_ends == 1


@pytest.mark.unit
def test_stop_timeout_escalates_to_kill():
    """A frame that never ends on its own is killed; queued triggers are dropped, on_shutdown runs once."""
    ran: List[str] = []
    first = _ShutdownNode("n0", ran, lambda context: time.sleep(0.01))
    nodes: List[_Node] = [first] + [_Node(f"n{i}", ran, lambda context: time.sleep(0.01)) for i in (1, 2)]
    flow = _flow("loop", nodes, cycle=True)
    group = _group(flow, HaywireVM(), "g")
    group.start()
    assert _enqueue(flow, "t")
    assert _enqueue(flow, "queued")
    while not ran:
        time.sleep(0.01)
    start = time.monotonic()
    assert group.stop(0.2) is True
    assert time.monotonic() - start < 0.2 + 2.0
    assert group.is_abandoned is False
    assert first.shutdowns == 1
    assert flow.queue is not None
    assert flow.queue.wait_for_completion(0.1)  # the queued trigger was discarded, not left pending


@pytest.mark.unit
def test_stuck_worker_is_abandoned():
    stuck = threading.Event()
    entered = threading.Event()

    def block(context):
        entered.set()
        stuck.wait(10.0)

    flow = _flow("stuck", [_Node("n1", [], block)])
    group = _group(flow, HaywireVM(), "g")
    interpreter = Interpreter()
    interpreter.groups = [group]
    group.start()
    try:
        assert _enqueue(flow, "t")
        assert entered.wait(2.0)
        assert group.kill(0.2) is False
        assert group.is_abandoned is True
        assert interpreter.has_abandoned_runners() is True
    finally:
        stuck.set()
        assert group._exited.wait(2.0)
    assert group.is_abandoned is False
    assert interpreter.has_abandoned_runners() is False


@pytest.mark.unit
def test_stop_frees_group_waiting_on_shared_data_node():
    vm = HaywireVM()
    s = _SharedDataNode("s", park_on="a")
    flow_a = _flow("A", [_Node("ca", [])], data=[s])
    flow_b = _flow("B", [_Node("cb", [])], data=[s])
    flow_a.shared_node_ids = flow_b.shared_node_ids = frozenset({"s"})
    ga, gb = _group(flow_a, vm, "ga"), _group(flow_b, vm, "gb")
    interpreter = Interpreter()
    interpreter.groups = [ga, gb]
    ga.start()
    gb.start()
    try:
        _enqueue(flow_a, "warm_a")
        _enqueue(flow_b, "warm_b")
        assert flow_a.queue is not None
        assert flow_b.queue is not None
        assert flow_a.queue.wait_for_completion(2.0)
        assert flow_b.queue.wait_for_completion(2.0)

        _enqueue(flow_a, "a")
        assert s.inside.wait(2.0)
        _enqueue(flow_b, "b")
        time.sleep(0.2)  # B's frame now waits for s
        assert flow_b.queue.is_busy()

        assert ga.stop(0.2, kill_timeout_s=0.2) is False
        assert gb.stop(0.2, kill_timeout_s=1.0) is True
        assert ga.is_abandoned is True
        assert interpreter.has_abandoned_runners() is True
        assert s.shutdowns == 0
    finally:
        s.block.set()
        assert ga._exited.wait(2.0)
