"""Pooled callback delivery: listeners of one emit share its callbacks, the emitter's backlog holds the rest.

The unit tests drive real ``FlowQueue``s through a stub execution group whose
frames the test runs by hand, so every hand-over is deterministic. The
integration tests run Record Event Probes through a real ``Interpreter``. See ADR 0097.
"""

from __future__ import annotations

import threading
import time
from collections import Counter
from types import SimpleNamespace
from typing import Any

import pytest

from haywire.core.execution.callback_manager import DEFAULT_BACKLOG_SIZE, CallbackManager
from haywire.core.execution.delivery import BacklogFull, Delivery
from haywire.core.execution.event_source import CallbackEvent, Trigger
from haywire.core.execution.flow_queue import FlowQueue
from tests.conftest import make_node
from tests.wait import wait_until


class _VM:
    """Records each frame as ``(flow_id, n)``; a payload with ``boom`` raises inside the frame."""

    def __init__(self) -> None:
        self.ran: list[tuple[str, int]] = []

    def execute_control_flow(self, flow: Any, trigger: Trigger, frame: int, cancel: Any) -> int:
        payload = trigger.payload or {}
        self.ran.append((flow.flow_id, payload["n"]))
        if payload.get("boom"):
            raise RuntimeError("boom")
        return 1


class _Group:
    """An execution group whose frames run only when the test calls ``run``."""

    def __init__(self) -> None:
        self.tokens: list[FlowQueue] = []
        self.stopping = False
        self.runner = False
        self.cancel = None

    def post(self, flow_queue: FlowQueue) -> None:
        self.tokens.append(flow_queue)

    def is_stopping(self) -> bool:
        return self.stopping

    def is_runner_thread(self) -> bool:
        return self.runner

    def run(self, count: int | None = None) -> None:
        """Run ``count`` frames in token order, or every frame until no token is left."""
        while self.tokens and (count is None or count > 0):
            self.tokens.pop(0)._run_one()
            if count is not None:
                count -= 1


class _Flow:
    """A flow with identity hashing, as ``Flow`` has."""

    def __init__(self, flow_id: str, delivery: Delivery) -> None:
        self.flow_id = flow_id
        self.event_subscription = CallbackEvent(event_name=flow_id, delivery=delivery)
        self.queue: FlowQueue | None = None


class _Rig:
    def __init__(self, wait_timeout_s: float = 5.0) -> None:
        self.manager = CallbackManager(wait_timeout_s=wait_timeout_s)
        self.vm = _VM()
        self.group = _Group()

    def flow(self, name: str, delivery: Delivery = Delivery.POOLED) -> _Flow:
        flow = _Flow(name, delivery)
        flow.queue = FlowQueue(flow, self.vm, group=self.group)  # type: ignore[arg-type]  # stub flow, VM and group
        if delivery is Delivery.POOLED:
            flow.queue.on_done = self.manager.trigger_done
        self.manager.register_callback_listener(name, flow)  # type: ignore[arg-type]  # stub flow
        return flow

    def emit(self, names: str | list[str], n: int, backlog: Any = None, **extra: Any) -> None:
        self.manager.emit_callback(names, {"n": n, **extra}, backlog)

    def pools(self) -> list[dict[str, Any]]:
        return self.manager.get_statistics()["pools"]


def _backlog(size: int, rule: BacklogFull = BacklogFull.DROP_OLDEST, owner: str | None = "emitter") -> Any:
    """A stand-in for an emitter's ``BacklogSettings``."""
    return SimpleNamespace(size=size, rule=rule, owner_id=owner)


@pytest.mark.unit
class TestEvery:
    def test_one_emit_to_many_names_matches_one_emit_per_name(self):
        rig = _Rig()
        a = rig.flow("a", Delivery.EVERY)
        rig.flow("b", Delivery.EVERY)
        rig.emit(["a", "b"], 0)
        rig.emit("a", 1)

        assert [q.flow.flow_id for q in rig.group.tokens] == ["a", "b", "a"]
        rig.group.run()
        assert rig.vm.ran == [("a", 0), ("b", 0), ("a", 1)]
        assert rig.manager.callback_stats == {"a": 2, "b": 1}
        assert a.queue is not None
        assert a.queue.on_done is None
        assert rig.pools() == []

    def test_every_listener_gets_every_callback_beside_a_pool(self):
        rig = _Rig()
        rig.flow("e", Delivery.EVERY)
        rig.flow("p1")
        rig.flow("p2")
        for n in range(3):
            rig.emit(["e", "p1", "p2"], n)
        rig.group.run()

        ran = Counter(flow for flow, _ in rig.vm.ran)
        assert ran["e"] == 3
        assert sorted(n for flow, n in rig.vm.ran if flow != "e") == [0, 1, 2], (
            "each pooled callback runs once"
        )


@pytest.mark.unit
class TestPool:
    def test_free_members_take_callbacks_the_rest_wait(self):
        rig = _Rig()
        rig.flow("p1")
        rig.flow("p2")
        for n in range(4):
            rig.emit(["p1", "p2"], n)

        assert [q.flow.flow_id for q in rig.group.tokens] == ["p1", "p2"]
        assert rig.pools() == [{"members": ["p1", "p2"], "busy": 2, "waiting": 2, "dropped": 0}]

        rig.group.run(1)
        assert rig.vm.ran == [("p1", 0)]
        assert [q.flow.flow_id for q in rig.group.tokens] == ["p2", "p1"], "the freed member takes the next"

        rig.group.run()
        assert rig.vm.ran == [("p1", 0), ("p2", 1), ("p1", 2), ("p2", 3)]
        assert rig.pools()[0]["busy"] == 0

    def test_free_members_take_turns(self):
        rig = _Rig()
        rig.flow("p1")
        rig.flow("p2")
        for n in range(4):
            rig.emit(["p1", "p2"], n)
            rig.group.run()
        assert [flow for flow, _ in rig.vm.ran] == ["p1", "p2", "p1", "p2"]

    def test_a_flow_in_two_pools_is_busy_once_and_takes_the_oldest(self):
        rig = _Rig()
        rig.flow("p1")
        rig.emit("p1", 0, _backlog(4, owner="A"))
        rig.emit("p1", 1, _backlog(4, owner="B"))
        rig.emit("p1", 2, _backlog(4, owner="A"))

        assert len(rig.group.tokens) == 1, "a busy flow gets nothing more from a second pool"
        rig.group.run()
        assert rig.vm.ran == [("p1", 0), ("p1", 1), ("p1", 2)]

    def test_a_raising_frame_still_frees_its_flow(self):
        rig = _Rig()
        rig.flow("p1")
        rig.emit("p1", 0, boom=True)
        rig.emit("p1", 1)
        rig.group.run()
        assert rig.vm.ran == [("p1", 0), ("p1", 1)]
        assert rig.pools()[0]["busy"] == 0

    def test_without_backlog_settings_the_default_holds_and_drops_the_oldest(self):
        rig = _Rig()
        rig.flow("p1")
        for n in range(DEFAULT_BACKLOG_SIZE + 4):
            rig.emit("p1", n)
        assert rig.pools()[0]["waiting"] == DEFAULT_BACKLOG_SIZE
        assert rig.pools()[0]["dropped"] == 3
        rig.group.run()
        assert [n for _, n in rig.vm.ran] == [0, *range(4, DEFAULT_BACKLOG_SIZE + 4)]


@pytest.mark.unit
class TestFullBacklog:
    def test_drop_oldest_keeps_the_newest(self):
        rig = _Rig()
        rig.flow("p1")
        for n in range(3):
            rig.emit("p1", n, _backlog(1))
        assert rig.pools()[0]["dropped"] == 1
        rig.group.run()
        assert rig.vm.ran == [("p1", 0), ("p1", 2)]

    def test_wait_gives_up_after_its_timeout_and_drops_the_new_callback(self):
        rig = _Rig(wait_timeout_s=0.2)
        rig.flow("p1")
        backlog = _backlog(1, BacklogFull.WAIT)
        rig.emit("p1", 0, backlog)
        rig.emit("p1", 1, backlog)

        started = time.monotonic()
        rig.emit("p1", 2, backlog)
        assert time.monotonic() - started >= 0.2
        assert rig.pools()[0]["dropped"] == 1
        rig.group.run()
        assert rig.vm.ran == [("p1", 0), ("p1", 1)]

    def test_wait_resumes_once_a_frame_makes_room(self):
        rig = _Rig()
        rig.flow("p1")
        backlog = _backlog(1, BacklogFull.WAIT)
        rig.emit("p1", 0, backlog)
        rig.emit("p1", 1, backlog)

        emitter = threading.Thread(target=rig.emit, args=("p1", 2, backlog))
        emitter.start()
        assert wait_until(lambda: emitter.is_alive())
        rig.group.run(1)
        emitter.join(timeout=2.0)
        assert not emitter.is_alive()
        rig.group.run()
        assert rig.vm.ran == [("p1", 0), ("p1", 1), ("p1", 2)]
        assert rig.pools()[0]["dropped"] == 0

    def test_a_runner_thread_never_waits(self):
        rig = _Rig(wait_timeout_s=5.0)
        rig.flow("p1")
        backlog = _backlog(1, BacklogFull.WAIT)
        rig.emit("p1", 0, backlog)
        rig.emit("p1", 1, backlog)
        rig.group.runner = True

        started = time.monotonic()
        rig.emit("p1", 2, backlog)
        assert time.monotonic() - started < 1.0
        assert rig.pools()[0]["dropped"] == 1

    def test_clearing_the_callbacks_wakes_a_waiting_emitter(self):
        rig = _Rig(wait_timeout_s=5.0)
        rig.flow("p1")
        backlog = _backlog(1, BacklogFull.WAIT)
        rig.emit("p1", 0, backlog)
        rig.emit("p1", 1, backlog)

        emitter = threading.Thread(target=rig.emit, args=("p1", 2, backlog))
        emitter.start()
        time.sleep(0.05)  # lets the emitter reach its wait; a sleep never ends early
        rig.manager.clear_callbacks()
        emitter.join(timeout=1.0)
        assert not emitter.is_alive()
        assert rig.pools() == []


@pytest.mark.unit
class TestStop:
    def test_discarding_at_a_stop_frees_the_flow(self):
        rig = _Rig()
        p1 = rig.flow("p1")
        rig.emit("p1", 0)
        rig.emit("p1", 1)
        rig.group.stopping = True
        assert p1.queue is not None
        assert p1.queue._discard_pending() == 1

        assert rig.pools()[0] == {"members": ["p1"], "busy": 0, "waiting": 0, "dropped": 0}
        assert rig.vm.ran == []


@pytest.mark.integration
class TestThroughTheInterpreter:
    def _events(self, graph: Any, count: int) -> list[Any]:
        from haybale_testing.nodes.testbed.record_callback_probes import RecordEventProbeNode

        key = RecordEventProbeNode.class_identity.registry_key
        return [make_node(graph, key, position=(0, 200 * i)).node for i in range(count)]

    def _record(self, node: Any, runs: list[tuple[str, int]], lock: threading.Lock, delay_s: float) -> None:
        def worker(context: Any) -> str:
            time.sleep(delay_s)
            with lock:
                runs.append((node.node_id, context.trigger.payload["n"]))
            return "triggered"

        node.worker = worker

    def _run(self, graph: Any, emits: Any) -> None:
        from haywire.core.execution.interpreter import Interpreter

        interpreter = Interpreter()
        interpreter.load_graph(graph)
        interpreter.start_execution()
        try:
            emits(interpreter.vm)
            interpreter.wait_all(timeout=10.0)
        finally:
            interpreter.shutdown()

    def test_tick_event_listens_every_until_set_to_pooled(self, graph_with_library_system):
        from haybale_core.nodes.events.tick_event import TickEventNode

        node: Any = make_node(
            graph_with_library_system, TickEventNode.class_identity.registry_key, position=(0, 0)
        ).node
        assert node.event_subscription.delivery is Delivery.EVERY, "Every keeps today's broadcast"
        node.delivery.mode = "Pooled"
        assert node.event_subscription.delivery is Delivery.POOLED
        assert node.event_subscription.event_name == node.node_id

    def test_each_pooled_callback_runs_once_and_every_listener_runs_all(self, graph_with_library_system):
        a, b, every = self._events(graph_with_library_system, 3)
        a.delivery.mode = "Pooled"
        b.delivery.mode = "Pooled"
        assert a.event_subscription.delivery is Delivery.POOLED
        runs: list[tuple[str, int]] = []
        lock = threading.Lock()
        for node in (a, b):
            self._record(node, runs, lock, 0.01)
        self._record(every, runs, lock, 0.0)
        names = [a.node_id, b.node_id, every.node_id]

        def emits(vm: Any) -> None:
            for n in range(30):
                vm.emit_callback(names, {"n": n}, _backlog(64))

        self._run(graph_with_library_system, emits)

        pooled = [(flow, n) for flow, n in runs if flow != every.node_id]
        assert sorted(n for _, n in pooled) == list(range(30)), "each callback runs once in the pool"
        assert {flow for flow, _ in pooled} == {a.node_id, b.node_id}, "both members run"
        assert sorted(n for flow, n in runs if flow == every.node_id) == list(range(30))

    def test_two_emitting_threads_lose_nothing_under_wait(self, graph_with_library_system):
        a, b = self._events(graph_with_library_system, 2)
        a.delivery.mode = "Pooled"
        b.delivery.mode = "Pooled"
        runs: list[tuple[str, int]] = []
        lock = threading.Lock()
        for node in (a, b):
            self._record(node, runs, lock, 0.002)
        names = [a.node_id, b.node_id]
        backlog = _backlog(2, BacklogFull.WAIT)

        def emits(vm: Any) -> None:
            def emit_range(start: int) -> None:
                for n in range(start, start + 50):
                    vm.emit_callback(names, {"n": n}, backlog)

            threads = [threading.Thread(target=emit_range, args=(start,)) for start in (0, 50)]
            for thread in threads:
                thread.start()
            for thread in threads:
                thread.join(timeout=20.0)

        self._run(graph_with_library_system, emits)

        assert sorted(n for _, n in runs) == list(range(100))
