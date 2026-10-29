"""Structural validation batches wait for the frame barrier (ADR 0064).

A RecordEvent A drives a ``ControlPayloadTestNode`` X; X's ``on_validate``
parks a frame on an ``Event`` so a batch can be scheduled while it runs. The
graph is built on the fixture's ``SyncScheduler`` and then switched to a
``ThreadingTimerScheduler`` so batches run on their own thread.
"""

import threading
import time
from typing import Any, List

import pytest

from haywire.core.execution.interpreter import Interpreter
from haywire.core.graph.base import BaseGraph
from haywire.core.graph.scheduler import ThreadingTimerScheduler
from haywire.core.graph.types import ChangeReason

from tests.conftest import make_edge, make_node

pytestmark = pytest.mark.integration


class _Rig:
    def __init__(self, graph: BaseGraph, timer: bool = True):
        from haybale_testing.nodes.testbed.control_payload_node import ControlPayloadTestNode
        from haybale_testing.nodes.testbed.record_callback_nodes import TestRecordEventNode

        self.graph = graph
        self.a = make_node(graph, TestRecordEventNode.class_identity.registry_key, position=(0, 0))
        self.x = make_node(graph, ControlPayloadTestNode.class_identity.registry_key, position=(300, 0))
        assert isinstance(self.a.node, TestRecordEventNode)
        assert isinstance(self.x.node, ControlPayloadTestNode)
        make_edge(graph, self.a.node_id, "triggered", self.x.node_id, "exec_in")

        self.order: List[str] = []
        self.inside = threading.Event()
        self.gate = threading.Event()
        self.gate.set()
        self.frames = 0

        def on_validate(context: Any) -> None:
            self.frames += 1
            self.inside.set()
            self.gate.wait(5.0)
            self.order.append("frame_end")

        self.x.node.on_validate = on_validate  # type: ignore[method-assign]
        if timer:
            graph._validation.adopt_scheduler(ThreadingTimerScheduler())
        self.interpreter = Interpreter()
        self.interpreter.load_graph(graph)

    def trigger(self) -> None:
        self.interpreter.vm.emit_callback(self.a.node_id)

    def park_frame(self) -> None:
        self.gate.clear()
        self.inside.clear()
        self.trigger()
        assert self.inside.wait(2.0)

    def validation_count(self) -> int:
        return self.graph._validation.get_statistics()["validation_count"]


def _wait_until(predicate, timeout_s: float = 2.0) -> bool:
    deadline = time.monotonic() + timeout_s
    while time.monotonic() < deadline:
        if predicate():
            return True
        time.sleep(0.01)
    return predicate()


def test_structural_batch_waits_for_running_frame(graph_with_library_system: BaseGraph, library_system):
    rig = _Rig(graph_with_library_system)
    rig.x._housekeeping = lambda: rig.order.append("housekeeping")  # type: ignore[method-assign]
    try:
        rig.park_frame()
        rig.graph._validation.mark_node_dirty(rig.x.node_id, ChangeReason.NODE_VALIDATION_REQUESTED)
        time.sleep(0.3)  # well past the debounce
        assert "housekeeping" not in rig.order
        rig.gate.set()
        assert _wait_until(lambda: "housekeeping" in rig.order)
    finally:
        rig.gate.set()
        rig.interpreter.shutdown()
    assert rig.order[0] == "frame_end"
    assert "housekeeping" in rig.order


def test_value_batch_does_not_hold(graph_with_library_system: BaseGraph, library_system):
    rig = _Rig(graph_with_library_system)
    try:
        before = rig.validation_count()
        rig.park_frame()
        rig.graph._validation.mark_node_dirty(rig.x.node_id, ChangeReason.NODE_VALUE_CHANGED)
        assert _wait_until(lambda: rig.validation_count() > before)
        assert "frame_end" not in rig.order  # the frame is still parked
    finally:
        rig.gate.set()
        rig.interpreter.shutdown()


def test_reassembly_batch_leaves_groups_held(graph_with_library_system: BaseGraph, library_system):
    rig = _Rig(graph_with_library_system)
    try:
        before = rig.validation_count()
        rig.graph._validation.mark_edge_dirty("edge_that_was_added", ChangeReason.EDGE_ADDED)
        assert _wait_until(lambda: rig.validation_count() > before)
        frames = rig.frames
        rig.trigger()
        time.sleep(0.2)
        assert rig.frames == frames  # parked at the frame barrier
        assert all(group.stop() for group in rig.interpreter.groups)
    finally:
        rig.interpreter.shutdown()
    assert rig.frames == frames


def test_hold_from_runner_thread_is_noop(graph_with_library_system: BaseGraph, library_system):
    """SyncScheduler graph: a worker's structural mark validates inline inside its own frame."""
    rig = _Rig(graph_with_library_system, timer=False)
    real_worker = rig.x.node.worker
    validated = threading.Event()

    def worker(context):
        rig.graph._validation.mark_node_dirty(rig.x.node_id, ChangeReason.NODE_VALIDATION_REQUESTED)
        validated.set()
        return real_worker(context)

    rig.x.node.worker = worker  # type: ignore[method-assign]
    rig.x.node._executor = None
    try:
        rig.trigger()
        assert validated.wait(2.0), "the frame deadlocked on its own hold"
        flow = rig.interpreter.event_subscriptions[f"callback:{rig.a.node_id}"][0]
        assert flow.queue is not None
        assert flow.queue.wait_for_completion(2.0)
    finally:
        rig.interpreter.shutdown()


def test_stop_while_held_for_reassembly_skips_shutdown_grace(
    graph_with_library_system: BaseGraph, library_system
):
    """A Shutdown flow cannot run on a stale assembly, so stop does not wait for it."""
    from haybale_core.nodes.events.shutdown import ShutdownNode

    rig = _Rig(graph_with_library_system, timer=False)
    make_node(rig.graph, ShutdownNode.class_identity.registry_key, position=(0, 300))
    rig.interpreter.load_graph(rig.graph)
    rig.graph._validation.adopt_scheduler(ThreadingTimerScheduler())
    rig.interpreter.start_execution()
    before = rig.validation_count()
    rig.graph._validation.mark_edge_dirty("edge_that_was_added", ChangeReason.EDGE_ADDED)
    assert _wait_until(lambda: rig.validation_count() > before)
    start = time.monotonic()
    rig.interpreter.stop_execution(timeout=2.0)
    assert time.monotonic() - start < 1.0
    assert rig.interpreter.is_executing is False
