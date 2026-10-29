"""Several event nodes may share one event subscription (ADR 0064).

Each event node roots its own flow; one dispatch triggers every flow on the
key. Flows whose chains share a control node land in one execution group.
"""

import threading
import time
from types import SimpleNamespace
from typing import Any, Dict, List

import pytest

from haywire.core.execution.event_source import SystemEvent, SystemEventType
from haywire.core.execution.interpreter import Interpreter
from haywire.core.graph.base import BaseGraph

from tests.conftest import make_edge, make_node


def _begin_play_cls():
    from haybale_testing.nodes.testbed.begin_play_node import TestBeginPlayNode

    return TestBeginPlayNode


def _payload_cls():
    from haybale_testing.nodes.testbed.control_payload_node import ControlPayloadTestNode

    return ControlPayloadTestNode


def _recording(wrapper: Any, seen: List[str], lock: threading.Lock) -> None:
    """Make ``wrapper``'s worker record ``<node_id>@<thread name>`` before it runs."""
    real_worker = wrapper.node.worker

    def worker(context):
        with lock:
            seen.append(f"{wrapper.node_id}@{threading.current_thread().name}")
        return real_worker(context)

    wrapper.node.worker = worker
    wrapper.node._executor = None


def _event_and_target(graph: BaseGraph, event_cls: Any, y: int) -> tuple:
    event = make_node(graph, event_cls.class_identity.registry_key, position=(0, y))
    target = make_node(graph, _payload_cls().class_identity.registry_key, position=(300, y))
    assert isinstance(event.node, event_cls)
    assert isinstance(target.node, _payload_cls())
    assert make_edge(graph, event.node_id, "exec", target.node_id, "exec_in").state.is_valid()
    return event, target


@pytest.mark.integration
class TestMultipleEventNodes:
    def test_two_begin_play_nodes_with_disjoint_chains_both_run(
        self, graph_with_library_system: BaseGraph, library_system
    ):
        graph = graph_with_library_system
        _, x1 = _event_and_target(graph, _begin_play_cls(), 0)
        _, x2 = _event_and_target(graph, _begin_play_cls(), 200)

        seen: List[str] = []
        lock = threading.Lock()
        _recording(x1, seen, lock)
        _recording(x2, seen, lock)

        interpreter = Interpreter()
        interpreter.load_graph(graph)
        try:
            key = SystemEvent(type=SystemEventType.BEGIN_PLAY).get_subscription_key()
            assert len(interpreter.event_subscriptions[key]) == 2
            assert len(interpreter.groups) == 2
            interpreter.start_execution()
            interpreter.wait_all(timeout=2.0)
        finally:
            interpreter.shutdown()

        assert sorted(entry.split("@")[0] for entry in seen) == sorted([x1.node_id, x2.node_id])
        assert len({entry.split("@")[1] for entry in seen}) == 2  # one runner per group

    def test_two_begin_play_nodes_sharing_a_control_node_share_a_group(
        self, graph_with_library_system: BaseGraph, library_system
    ):
        graph = graph_with_library_system
        b1 = make_node(graph, _begin_play_cls().class_identity.registry_key, position=(0, 0))
        b2 = make_node(graph, _begin_play_cls().class_identity.registry_key, position=(0, 200))
        x = make_node(graph, _payload_cls().class_identity.registry_key, position=(300, 100))
        make_edge(graph, b1.node_id, "exec", x.node_id, "exec_in")
        make_edge(graph, b2.node_id, "exec", x.node_id, "exec_in")

        seen: List[str] = []
        lock = threading.Lock()
        _recording(x, seen, lock)

        interpreter = Interpreter()
        interpreter.load_graph(graph)
        try:
            assert len(interpreter.groups) == 1
            interpreter.start_execution()
            interpreter.wait_all(timeout=2.0)
        finally:
            interpreter.shutdown()

        assert len(seen) == 2  # x ran once per Begin Play
        assert len({entry.split("@")[1] for entry in seen}) == 1  # on one runner

    def test_two_shutdown_nodes_both_run_on_stop(self, graph_with_library_system: BaseGraph, library_system):
        from haybale_core.nodes.events.shutdown import ShutdownNode

        graph = graph_with_library_system
        _, x1 = _event_and_target(graph, ShutdownNode, 0)
        _, x2 = _event_and_target(graph, ShutdownNode, 200)
        seen: List[str] = []
        lock = threading.Lock()
        _recording(x1, seen, lock)
        _recording(x2, seen, lock)

        interpreter = Interpreter()
        interpreter.load_graph(graph)
        try:
            interpreter.start_execution()
            interpreter.stop_execution(timeout=2.0)
        finally:
            interpreter.shutdown()

        assert sorted(entry.split("@")[0] for entry in seen) == sorted([x1.node_id, x2.node_id])

    def test_two_custom_callbacks_with_one_name_both_trigger(
        self, graph_with_library_system: BaseGraph, library_system
    ):
        from haybale_testing.nodes.testbed.custom_callback_node import TestCustomCallbackNode

        graph = graph_with_library_system
        targets = []
        for y in (0, 200):
            listener = make_node(graph, TestCustomCallbackNode.class_identity.registry_key, position=(0, y))
            assert isinstance(listener.node, TestCustomCallbackNode)
            listener.node.ports["custom_callback_name"].set_value("shared_name")
            listener.node.ports["custom_name"].set_value(True)  # rebuilds the subscription
            target = make_node(graph, _payload_cls().class_identity.registry_key, position=(300, y))
            edge = make_edge(graph, listener.node_id, "triggered", target.node_id, "exec_in")
            assert edge.state.is_valid(), edge.state
            targets.append(target)

        seen: List[str] = []
        lock = threading.Lock()
        for target in targets:
            _recording(target, seen, lock)

        interpreter = Interpreter()
        interpreter.load_graph(graph)
        try:
            assert len(interpreter.event_subscriptions["callback:shared_name"]) == 2
            # The testbed listener writes the whole payload to a FLOAT outlet.
            interpreter.vm.emit_callback("shared_name", 1.0)  # type: ignore[arg-type]
            interpreter.wait_all(timeout=2.0)
        finally:
            interpreter.shutdown()

        assert sorted(entry.split("@")[0] for entry in seen) == sorted(t.node_id for t in targets)


@pytest.mark.unit
def test_shutdown_grace_is_one_deadline_for_all_shutdown_flows():
    """N Shutdown flows that never finish cost one grace period, not N."""
    waits: List[float] = []

    class _StuckQueue:
        def wait_for_completion(self, timeout: float) -> bool:
            waits.append(timeout)
            time.sleep(timeout)
            return False

    interpreter = Interpreter()
    interpreter._executing = True
    key = SystemEvent(type=SystemEventType.SHUTDOWN).get_subscription_key()
    flows: Dict[str, List[Any]] = {key: [SimpleNamespace(queue=_StuckQueue()) for _ in range(3)]}
    interpreter.event_subscriptions = flows  # type: ignore[assignment]
    interpreter.dispatch_system_event = lambda *args, **kwargs: 0  # type: ignore[method-assign]

    start = time.monotonic()
    interpreter.stop_execution(timeout=0.3)
    assert time.monotonic() - start < 0.6
    assert sum(waits) <= 0.3 + 0.05
