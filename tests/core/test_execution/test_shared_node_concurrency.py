"""Regression suite: no node ever executes on two threads at once.

Each test wires two event nodes whose flows reach one shared node. The shared
node's ``on_validate`` (called from inside ``BaseNode._execute``, before the
worker) waits on a ``threading.Barrier`` for two parties, so it only opens
when two threads are inside the node together. With execution groups the
second frame never enters while the first is inside: the barrier times out on
purpose (``BARRIER_TIMEOUT_S``) and the probe records one active thread.

Triggers go through production paths only: ``Interpreter.start_execution()``
(BEGIN_PLAY) and ``HaywireVM.emit_callback``. See ADR 0064.
"""

import threading
from typing import Any, Dict, List, Optional, Tuple

import pytest

from haywire.core.execution.interpreter import Interpreter
from haywire.core.graph.base import BaseGraph

from tests.conftest import make_edge, make_node

BARRIER_TIMEOUT_S = 0.5


class _OverlapProbe:
    """An ``on_validate`` stand-in that records how many threads are inside one node together."""

    def __init__(self, node: Any, parties: int = 2):
        self.node = node
        self.barrier = threading.Barrier(parties, timeout=BARRIER_TIMEOUT_S)
        self.lock = threading.Lock()
        self.active = 0
        self.max_active = 0
        self.entries: List[Tuple[str, str, int]] = []  # (trigger source_key, thread name, thread id)
        self.entry_payload: Dict[str, Any] = {}  # exec_in as each frame found it on entry
        self.broken = False
        self.first_inside = threading.Event()

    def on_validate(self, context: Any) -> None:
        key = context.trigger.source_key if context.trigger else "?"
        with self.lock:
            self.active += 1
            self.max_active = max(self.max_active, self.active)
            self.entries.append((key, threading.current_thread().name, threading.get_ident()))
            if "exec_in" in self.node.ports:
                self.entry_payload[key] = self.node.value("exec_in")
        self.first_inside.set()
        try:
            self.barrier.wait()
        except threading.BrokenBarrierError:
            self.broken = True
        finally:
            with self.lock:
                self.active -= 1


def _record_node_cls():
    from haybale_testing.nodes.testbed.record_callback_nodes import TestRecordEventNode

    return TestRecordEventNode


def _payload_node_cls():
    from haybale_testing.nodes.testbed.control_payload_node import ControlPayloadTestNode

    return ControlPayloadTestNode


def _flows_containing(interpreter: Interpreter, node_id: str) -> List[Any]:
    return [
        flow
        for flows in interpreter.event_subscriptions.values()
        for flow in flows
        if flow.control_graph is not None and node_id in flow.control_graph.control_nodes
    ]


@pytest.mark.integration
class TestSharedNodeConcurrentExecution:
    def test_shared_control_node_never_runs_on_two_threads(
        self, graph_with_library_system: BaseGraph, library_system
    ):
        """BeginPlay -> RecordEmit emits to event A and event B; both flows reach shared X."""
        from haybale_testing.nodes.testbed.begin_play_node import TestBeginPlayNode
        from haybale_testing.nodes.testbed.record_callback_nodes import TestRecordEmitNode

        RecordEvent = _record_node_cls()
        Payload = _payload_node_cls()
        graph = graph_with_library_system

        begin = make_node(graph, TestBeginPlayNode.class_identity.registry_key, position=(0, 0))
        emit = make_node(graph, TestRecordEmitNode.class_identity.registry_key, position=(200, 0))
        a = make_node(graph, RecordEvent.class_identity.registry_key, position=(0, 200))
        b = make_node(graph, RecordEvent.class_identity.registry_key, position=(0, 400))
        x = make_node(graph, Payload.class_identity.registry_key, position=(400, 300))
        for w, cls in (
            (begin, TestBeginPlayNode),
            (emit, TestRecordEmitNode),
            (a, RecordEvent),
            (b, RecordEvent),
            (x, Payload),
        ):
            assert isinstance(w.node, cls), f"{w.node_id} is {type(w.node).__name__}, not {cls.__name__}"

        edges = [
            make_edge(graph, begin.node_id, "exec", emit.node_id, "execute"),
            make_edge(graph, a.node_id, "subscription", emit.node_id, "subscriptions"),
            make_edge(graph, b.node_id, "subscription", emit.node_id, "subscriptions"),
            make_edge(graph, a.node_id, "triggered", x.node_id, "exec_in"),
            make_edge(graph, b.node_id, "triggered", x.node_id, "exec_in"),
        ]
        for edge in edges:
            assert edge.state.is_valid(), f"invalid edge {edge.edge_id}"

        probe = _OverlapProbe(x.node)
        x.node.on_validate = probe.on_validate  # type: ignore[method-assign]  # instance hook; _execute calls self.on_validate

        interpreter = Interpreter()
        interpreter.load_graph(graph)
        try:
            assert len(_flows_containing(interpreter, x.node_id)) == 2
            interpreter.start_execution()
            interpreter.wait_all(timeout=6 * BARRIER_TIMEOUT_S)
        finally:
            interpreter.shutdown()

        assert probe.broken is True, "barrier opened: two threads were inside X together"
        assert probe.max_active == 1
        assert {e[0] for e in probe.entries} == {f"callback:{a.node_id}", f"callback:{b.node_id}"}

    def test_shared_node_worker_sees_its_own_flows_payload(
        self, graph_with_library_system: BaseGraph, library_system
    ):
        """A -> CA(out {"flow": "A"}) -> X ; B -> CB(out {"flow": "B"}) -> X.

        A is triggered first and parks inside X; then B is triggered. B's frame
        must not push its payload into X while A's frame is still inside it.
        """
        RecordEvent = _record_node_cls()
        Payload = _payload_node_cls()
        graph = graph_with_library_system

        a = make_node(graph, RecordEvent.class_identity.registry_key, position=(0, 0))
        b = make_node(graph, RecordEvent.class_identity.registry_key, position=(0, 200))
        ca = make_node(graph, Payload.class_identity.registry_key, position=(200, 0))
        cb = make_node(graph, Payload.class_identity.registry_key, position=(200, 200))
        x = make_node(graph, Payload.class_identity.registry_key, position=(400, 100))
        for w in (ca, cb, x):
            assert isinstance(w.node, Payload)
        for w in (a, b):
            assert isinstance(w.node, RecordEvent)
        ca.node.emit_payload = {"flow": "A"}  # type: ignore[attr-defined]
        cb.node.emit_payload = {"flow": "B"}  # type: ignore[attr-defined]

        for edge in (
            make_edge(graph, a.node_id, "triggered", ca.node_id, "exec_in"),
            make_edge(graph, ca.node_id, "exec_out", x.node_id, "exec_in"),
            make_edge(graph, b.node_id, "triggered", cb.node_id, "exec_in"),
            make_edge(graph, cb.node_id, "exec_out", x.node_id, "exec_in"),
        ):
            assert edge.state.is_valid()

        probe = _OverlapProbe(x.node)
        x.node.on_validate = probe.on_validate  # type: ignore[method-assign]

        real_worker = x.node.worker  # ControlPayloadTestNode.worker: self.received = self.value("exec_in")
        worker_saw: Dict[str, Optional[Any]] = {}

        def recording_worker(context):
            result = real_worker(context)
            worker_saw[context.trigger.source_key] = x.node.received  # type: ignore[attr-defined]
            return result

        x.node.worker = recording_worker  # type: ignore[method-assign]
        x.node._executor = None

        key_a, key_b = f"callback:{a.node_id}", f"callback:{b.node_id}"
        interpreter = Interpreter()
        interpreter.load_graph(graph)
        try:
            interpreter.vm.emit_callback(a.node_id)
            assert probe.first_inside.wait(5.0), "flow A never reached X"
            interpreter.vm.emit_callback(b.node_id)
            interpreter.wait_all(timeout=6 * BARRIER_TIMEOUT_S)
        finally:
            interpreter.shutdown()

        assert worker_saw[key_a] == {"flow": "A"}
        assert worker_saw[key_b] == {"flow": "B"}

    def test_dirty_port_drain_has_one_drainer(self, graph_with_library_system: BaseGraph, library_system):
        """Two frames draining X._has_dirty_ports never interleave between the check and the pop.

        ``_has_dirty_ports`` is swapped for a dict whose truth test parks each
        runner thread once at a barrier, standing in for a thread switch between
        ``while self._has_dirty_ports`` and ``popitem()`` (base.py).
        """
        RecordEvent = _record_node_cls()
        Payload = _payload_node_cls()
        graph = graph_with_library_system

        a = make_node(graph, RecordEvent.class_identity.registry_key, position=(0, 0))
        b = make_node(graph, RecordEvent.class_identity.registry_key, position=(0, 200))
        x = make_node(graph, Payload.class_identity.registry_key, position=(400, 100))
        assert isinstance(x.node, Payload)
        make_edge(graph, a.node_id, "triggered", x.node_id, "exec_in")
        make_edge(graph, b.node_id, "triggered", x.node_id, "exec_in")

        gate_barrier = threading.Barrier(2, timeout=BARRIER_TIMEOUT_S)

        class _GateDict(dict):
            def __init__(self):
                super().__init__()
                self.parked: set = set()

            def __bool__(self):
                truth = len(self) > 0
                me = threading.get_ident()
                if threading.current_thread().name.startswith("FlowExec-") and me not in self.parked:
                    self.parked.add(me)
                    try:
                        gate_barrier.wait()  # opens only if a second thread is at the check too
                    except threading.BrokenBarrierError:
                        pass
                return truth

        runs: List[str] = []
        real_worker = x.node.worker

        def counting_worker(context):
            runs.append(context.trigger.source_key)
            return real_worker(context)

        x.node.worker = counting_worker
        x.node._executor = None

        interpreter = Interpreter()
        interpreter.load_graph(graph)
        try:
            gate = _GateDict()
            x.node._has_dirty_ports = gate
            x.node.mark_port_as_dirty(x.node.ports["exec_in"])  # exactly one dirty entry
            assert len(gate) == 1
            interpreter.vm.emit_callback(a.node_id)
            interpreter.vm.emit_callback(b.node_id)
            interpreter.wait_all(timeout=6 * BARRIER_TIMEOUT_S)
        finally:
            interpreter.shutdown()

        assert x.state.error_runtime is None
        assert sorted(runs) == sorted([f"callback:{a.node_id}", f"callback:{b.node_id}"])

    def test_stop_during_begin_play_frame_serializes_with_shutdown(
        self, graph_with_library_system: BaseGraph, library_system
    ):
        """BeginPlay -> X and Shutdown -> X: stop while the BeginPlay frame is inside X.

        The Shutdown frame runs after the BeginPlay frame, and the shared node's
        lifecycle hooks run once each.
        """
        from haybale_core.nodes.events.shutdown import ShutdownNode
        from haybale_testing.nodes.testbed.begin_play_node import TestBeginPlayNode

        Payload = _payload_node_cls()
        graph = graph_with_library_system

        begin = make_node(graph, TestBeginPlayNode.class_identity.registry_key, position=(0, 0))
        shut = make_node(graph, ShutdownNode.class_identity.registry_key, position=(0, 200))
        x = make_node(graph, Payload.class_identity.registry_key, position=(300, 100))
        assert isinstance(begin.node, TestBeginPlayNode)
        assert isinstance(shut.node, ShutdownNode)
        assert isinstance(x.node, Payload)
        make_edge(graph, begin.node_id, "exec", x.node_id, "exec_in")
        make_edge(graph, shut.node_id, "exec", x.node_id, "exec_in")

        probe = _OverlapProbe(x.node)
        x.node.on_validate = probe.on_validate

        hook_threads: Dict[str, List[str]] = {"on_startup": [], "on_shutdown": []}
        hook_lock = threading.Lock()

        def _hook(name):
            def hook(context):
                with hook_lock:
                    hook_threads[name].append(threading.current_thread().name)

            return hook

        # Override detection looks the hook up on the class, so patch the class.
        mp = pytest.MonkeyPatch()
        mp.setattr(
            Payload, "on_startup", lambda self, ctx: _hook("on_startup")(ctx) if self is x.node else None
        )
        mp.setattr(
            Payload, "on_shutdown", lambda self, ctx: _hook("on_shutdown")(ctx) if self is x.node else None
        )

        interpreter = Interpreter()
        try:
            interpreter.load_graph(graph)
            interpreter.start_execution()
            assert probe.first_inside.wait(5.0), "BeginPlay flow never reached X"
            interpreter.stop_execution(timeout=6 * BARRIER_TIMEOUT_S)
        finally:
            interpreter.shutdown()
            mp.undo()

        assert probe.max_active == 1
        assert {e[0] for e in probe.entries} == {"system:begin_play", "system:shutdown"}
        assert len(hook_threads["on_startup"]) == 1
        assert len(hook_threads["on_shutdown"]) == 1

    def test_shared_data_node_never_runs_on_two_threads(
        self, graph_with_library_system: BaseGraph, library_system
    ):
        """A DATA node D feeding a control node in each flow: no shared CONTROL node at all.

        A -> EA ; B -> EB ; D.result -> EA.payload and EB.payload. The flows stay
        in separate groups; D is a shared data node, so they take turns on it.
        """
        from haybale_testing.nodes.testbed.emit_callback_node import TestEmitCallbackNode
        from haybale_testing.nodes.testbed.math_op_node import TestAddFloatNode

        RecordEvent = _record_node_cls()
        graph = graph_with_library_system

        a = make_node(graph, RecordEvent.class_identity.registry_key, position=(0, 0))
        b = make_node(graph, RecordEvent.class_identity.registry_key, position=(0, 200))
        ea = make_node(graph, TestEmitCallbackNode.class_identity.registry_key, position=(300, 0))
        eb = make_node(graph, TestEmitCallbackNode.class_identity.registry_key, position=(300, 200))
        d = make_node(graph, TestAddFloatNode.class_identity.registry_key, position=(150, 100))
        assert isinstance(d.node, TestAddFloatNode)
        assert isinstance(ea.node, TestEmitCallbackNode)
        assert isinstance(eb.node, TestEmitCallbackNode)
        for edge in (
            make_edge(graph, a.node_id, "triggered", ea.node_id, "execute"),
            make_edge(graph, b.node_id, "triggered", eb.node_id, "execute"),
            make_edge(graph, d.node_id, "result", ea.node_id, "payload"),
            make_edge(graph, d.node_id, "result", eb.node_id, "payload"),
        ):
            assert edge.state.is_valid()
        for w in (ea, eb):
            w.node.worker = lambda context: None  # type: ignore[method-assign,misc]  # the emitters' own work is irrelevant here
            w.node._executor = None

        probe = _OverlapProbe(d.node)
        d.node.on_validate = probe.on_validate  # type: ignore[method-assign]

        interpreter = Interpreter()
        interpreter.load_graph(graph)
        try:
            assert len(interpreter.groups) == 2
            d.node.ports["value_a"].set_value(1.0)  # widget-style own write: marks D dirty
            interpreter.vm.emit_callback(a.node_id)
            assert probe.first_inside.wait(5.0), "flow A never evaluated D"
            d.node.ports["value_a"].set_value(2.0)
            interpreter.vm.emit_callback(b.node_id)
            interpreter.wait_all(timeout=6 * BARRIER_TIMEOUT_S)
        finally:
            interpreter.shutdown()

        assert probe.max_active == 1
