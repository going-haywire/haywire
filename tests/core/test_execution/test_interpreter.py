"""
Integration tests for Interpreter with full library system.

These tests require libraries to be loaded and are slower.
"""

import pytest
from haywire.core.execution.event_source import SystemEventType
from haywire.core.execution.interpreter import Interpreter
from haywire.core.graph.base import BaseGraph
from haywire.core.di.config import LibrarySystemService

from tests.conftest import make_node


@pytest.mark.integration
@pytest.mark.slow
class TestInterpreter:
    """Test Interpreter with real nodes from libraries."""

    def _create_simple_graph(self, graph: BaseGraph) -> BaseGraph:
        """
        Create a simple graph: BeginPlay → PrintMessage

        Args:
            graph: The graph to populate

        Returns:
            The populated graph
        """
        from haybale_testing.nodes.testbed.begin_play_node import TestBeginPlayNode as BeginPlayNode
        from haybale_testing.nodes.testbed.print_node import TestPrintNode as PrintTerminalMessageNode

        begin_play = make_node(graph, BeginPlayNode.class_identity.registry_key, position=(100, 100))

        print_msg = make_node(
            graph, PrintTerminalMessageNode.class_identity.registry_key, position=(300, 100)
        )

        graph.create_edge_wrapper(begin_play.node_id, "exec", print_msg.node_id, "exec")

        return graph

    def _create_graph_with_math(self, graph: BaseGraph) -> BaseGraph:
        """
        Create graph: BeginPlay → PrintMessage with MathOP data flow

        Args:
            graph: The graph to populate

        Returns:
            The populated graph
        """
        from haybale_testing.nodes.testbed.begin_play_node import TestBeginPlayNode as BeginPlayNode
        from haybale_testing.nodes.testbed.print_node import TestPrintNode as PrintTerminalMessageNode
        from haybale_testing.nodes.testbed.math_op_node import TestAddFloatNode as MathOP

        begin_play = make_node(graph, BeginPlayNode.class_identity.registry_key, position=(100, 100))

        print_msg = make_node(
            graph, PrintTerminalMessageNode.class_identity.registry_key, position=(300, 100)
        )

        math_op = make_node(graph, MathOP.class_identity.registry_key, position=(200, 100))

        graph.create_edge_wrapper(begin_play.node_id, "exec", print_msg.node_id, "exec")
        graph.create_edge_wrapper(begin_play.node_id, "timestamp", math_op.node_id, "value_a")
        graph.create_edge_wrapper(math_op.node_id, "result", print_msg.node_id, "message")

        return graph

    def test_simple_flow_execution(
        self, graph_with_library_system: BaseGraph, library_system: LibrarySystemService
    ):
        """Test simple flow: BeginPlay → PrintMessage"""
        graph = self._create_simple_graph(graph_with_library_system)

        # Test: Verify graph structure
        assert len(graph.node_wrappers) == 2
        assert len(graph.list_edge_wrappers()) == 1

        # Test: Create and load interpreter
        interpreter = Interpreter()
        assert interpreter is not None

        # Test: Load and assemble graph
        interpreter.load_graph(graph)
        assert interpreter.current_graph == graph

        # Test: Verify assembly statistics
        stats = interpreter.get_statistics()
        assert stats["current_graph"] == graph.graph_id
        assert stats["assembly"]["total_flows"] == 1
        assert len(stats["assembly"]["flows"]) == 1

        flow_info = stats["assembly"]["flows"][0]
        assert "begin_play" in flow_info["event_type"]
        assert flow_info["node_count"] == 2

        # Test: Dispatch event
        triggered = interpreter.dispatch_system_event(SystemEventType.BEGIN_PLAY)
        assert triggered == 1

        # Test: Wait for completion
        interpreter.wait_all(timeout=5.0)

        # Test: Verify schedulers
        assert len(stats["schedulers"]) == 1
        scheduler_info = stats["schedulers"][0]
        assert scheduler_info["subscription"] is not None

        # Cleanup
        interpreter.shutdown()
        assert interpreter.current_graph is None

        # Test: Library system integration
        assert library_system is not None
        node_registry = library_system.get_node_registry()
        assert node_registry is not None

        available_nodes = node_registry.list_names()
        assert isinstance(available_nodes, list)
        assert len(available_nodes) > 0

    def test_callback_flow_execution(
        self, graph_with_library_system: BaseGraph, library_system: LibrarySystemService
    ):
        """Test callback flow: BeginPlay → EmitCallback, CustomCallback → Print"""
        from haybale_testing.nodes.testbed.begin_play_node import TestBeginPlayNode as BeginPlayNode
        from haybale_testing.nodes.testbed.emit_callback_node import TestEmitCallbackNode as EmitCallbackNode
        from haybale_testing.nodes.testbed.custom_callback_node import (
            TestCustomCallbackNode as CustomCallbackNode,
        )
        from haybale_testing.nodes.testbed.print_node import TestPrintNode as PrintTerminalMessageNode

        graph = graph_with_library_system

        # Flow 1: BeginPlay → EmitCallback
        begin_play = make_node(graph, BeginPlayNode.class_identity.registry_key, position=(100, 100))

        emit_callback = make_node(graph, EmitCallbackNode.class_identity.registry_key, position=(300, 100))

        # Set mode to use custom callback name and set the callback name
        emit_callback.node.ports["mode_switch"].set_value(True)
        emit_callback.node.ports["custom_callback_name"].set_value("test_callback")

        graph.create_edge_wrapper(begin_play.node_id, "exec", emit_callback.node_id, "execute")

        # Flow 2: CustomCallback → PrintMessage
        custom_callback = make_node(
            graph, CustomCallbackNode.class_identity.registry_key, position=(100, 300)
        )

        # Set mode to use custom callback name and set the listener name
        custom_callback.node.ports["mode_switch"].set_value(True)
        custom_callback.node.ports["custom_callback_name"].set_value("test_callback")

        print_msg = make_node(
            graph, PrintTerminalMessageNode.class_identity.registry_key, position=(300, 300)
        )

        print_msg.node.ports["message"].set_value("Callback received!")

        graph.create_edge_wrapper(custom_callback.node_id, "triggered", print_msg.node_id, "exec")

        # Test: Verify graph structure
        assert len(graph.node_wrappers) == 4
        assert len(graph.edge_wrappers) == 2

        # Test: Load graph
        interpreter = Interpreter()
        interpreter.load_graph(graph)

        # Test: Verify assembly
        stats = interpreter.get_statistics()
        assert stats["assembly"]["total_flows"] == 2

        # Test: Verify callback registration
        callback_stats = stats["callbacks"]
        assert callback_stats["total_callbacks"] >= 1

        # Test: Dispatch BEGIN_PLAY
        triggered = interpreter.dispatch_system_event(SystemEventType.BEGIN_PLAY)
        assert triggered == 1

        # Wait for execution (including callback trigger)
        interpreter.wait_all(timeout=5.0)

        # Cleanup
        interpreter.shutdown()

    def test_multiple_event_dispatches(
        self, graph_with_library_system: BaseGraph, library_system: LibrarySystemService
    ):
        """Test multiple event dispatches to the same flow"""
        graph = self._create_simple_graph(graph_with_library_system)

        interpreter = Interpreter()
        interpreter.load_graph(graph)

        # Test: Dispatch event multiple times
        triggered1 = interpreter.dispatch_system_event(SystemEventType.BEGIN_PLAY)
        assert triggered1 == 1

        triggered2 = interpreter.dispatch_system_event(SystemEventType.BEGIN_PLAY)
        assert triggered2 == 1

        triggered3 = interpreter.dispatch_system_event(SystemEventType.BEGIN_PLAY)
        assert triggered3 == 1

        # Test: Wait for all executions
        interpreter.wait_all(timeout=5.0)

        # Test: Verify scheduler state
        stats = interpreter.get_statistics()
        assert len(stats["schedulers"]) == 1

        interpreter.shutdown()

    def test_interpreter_reload_graph(
        self, graph_with_library_system: BaseGraph, library_system: LibrarySystemService
    ):
        """Test reloading a different graph into the interpreter"""

        # Create first graph
        graph1 = self._create_simple_graph(graph_with_library_system)

        # Create second graph
        graph2 = BaseGraph(graph_id="test_graph_2", name="Test Graph 2")
        graph2 = self._create_simple_graph(graph2)

        # Test: Load first graph
        interpreter = Interpreter()
        interpreter.load_graph(graph1)

        stats1 = interpreter.get_statistics()
        assert stats1["current_graph"] == graph1.graph_id
        assert stats1["assembly"]["total_flows"] == 1

        # Test: Reload with second graph
        interpreter.load_graph(graph2)

        stats2 = interpreter.get_statistics()
        assert stats2["current_graph"] == graph2.graph_id
        assert stats2["assembly"]["total_flows"] == 1

        # Test: Execute second graph
        triggered = interpreter.dispatch_system_event(SystemEventType.BEGIN_PLAY)
        assert triggered == 1

        interpreter.wait_all(timeout=5.0)
        interpreter.shutdown()

    def test_empty_graph_handling(
        self, graph_with_library_system: BaseGraph, library_system: LibrarySystemService
    ):
        """Test interpreter with an empty graph"""
        graph = graph_with_library_system

        # Test: Load empty graph
        interpreter = Interpreter()
        interpreter.load_graph(graph)

        # Test: Verify no flows assembled
        stats = interpreter.get_statistics()
        assert stats["current_graph"] == graph.graph_id
        assert stats["assembly"]["total_flows"] == 0

        # Test: Dispatch event to empty graph
        triggered = interpreter.dispatch_system_event(SystemEventType.BEGIN_PLAY)
        assert triggered == 0

        interpreter.shutdown()

    def test_interpreter_statistics(
        self, graph_with_library_system: BaseGraph, library_system: LibrarySystemService
    ):
        """Test interpreter statistics reporting"""

        graph = self._create_graph_with_math(graph_with_library_system)

        interpreter = Interpreter()
        interpreter.load_graph(graph)

        # Test: Statistics structure
        stats = interpreter.get_statistics()

        assert "current_graph" in stats
        assert "total_subscriptions" in stats
        assert "assembly" in stats
        assert "callbacks" in stats
        assert "schedulers" in stats

        # Test: Assembly stats
        assembly_stats = stats["assembly"]
        assert "total_flows" in assembly_stats
        assert "flows" in assembly_stats
        assert assembly_stats["total_flows"] > 0

        # Test: Scheduler stats
        assert isinstance(stats["schedulers"], list)
        assert len(stats["schedulers"]) > 0

        scheduler = stats["schedulers"][0]
        assert "flow_id" in scheduler
        assert "subscription" in scheduler
        assert "executing" in scheduler
        assert "queued" in scheduler

        interpreter.shutdown()

    # ------------------------------------------------------------------
    # Shutdown protocol end-to-end smoke tests: stopping a graph with
    # running TickEmit producer threads must return (not hang) in both the
    # no-Shutdown-node and graceful-Shutdown-wired cases.
    #
    # NOTE: the deterministic regression for the underlying deadlock lives
    # in test_scheduler_wait.py (wait_for_completion timeout contract).
    # These integration tests exercise the full stop_execution protocol but
    # cannot reliably reproduce the hang on their own, because an idle Tick
    # flow drains faster than the emitter produces.
    # ------------------------------------------------------------------

    def _build_two_tick_emitters(self, graph: BaseGraph, with_shutdown: bool) -> BaseGraph:
        """Two BeginPlay→TickEmit→Tick chains; optionally wire Shutdown→stop.

        Mirrors the user's reproduction graph: two independent TickEmit
        producers, each emitting callbacks into its own Tick event flow. When
        ``with_shutdown`` is True a single Shutdown node drives both emitters'
        ``stop`` inlets (the graceful path).
        """
        # These two shutdown-hang tests deliberately use the REAL haybale_core
        # nodes (not haybale_testing equivalents): they are regression guards
        # for a deadlock in TickEmitNode's threaded emitter / ShutdownNode's
        # graceful-stop protocol. The guard must watch the production node, so
        # this is the rule's "tests specifically of another library's
        # components" exemption — do not migrate to testbed copies.
        from haybale_core.nodes.emits.tick_emit import TickEmitNode
        from haybale_core.nodes.events.tick_event import TickEventNode
        from haybale_core.nodes.events.begin_play import BeginPlayNode
        from haybale_core.nodes.events.shutdown import ShutdownNode

        begin = make_node(graph, BeginPlayNode.class_identity.registry_key, position=(0, 0))
        shutdown = (
            make_node(graph, ShutdownNode.class_identity.registry_key, position=(0, 200))
            if with_shutdown
            else None
        )

        for i in range(2):
            emit = make_node(graph, TickEmitNode.class_identity.registry_key, position=(200, i * 300))
            tick = make_node(graph, TickEventNode.class_identity.registry_key, position=(400, i * 300))
            # Tick listener feeds the emitter's pooled callback inlet.
            graph.create_edge_wrapper(tick.node_id, "listen_callback", emit.node_id, "callback_names")
            # BeginPlay starts each emitter.
            graph.create_edge_wrapper(begin.node_id, "exec", emit.node_id, "start")
            # Shutdown stops each emitter (graceful path).
            if shutdown is not None:
                graph.create_edge_wrapper(shutdown.node_id, "exec", emit.node_id, "stop")

        return graph

    def _stop_must_not_hang(self, interpreter: Interpreter, ceiling: float = 8.0) -> float:
        """Run stop_execution on a watchdog; fail if it exceeds ``ceiling``."""
        import threading
        import time as _time

        done = threading.Event()
        start = _time.monotonic()

        def _stop():
            interpreter.stop_execution()
            done.set()

        worker = threading.Thread(target=_stop, daemon=True)
        worker.start()
        if not done.wait(timeout=ceiling):
            raise AssertionError(
                f"stop_execution did not return within {ceiling}s — shutdown hang regression"
            )
        return _time.monotonic() - start

    def test_stop_with_tick_emitters_no_shutdown_node(
        self, graph_with_library_system: BaseGraph, library_system: LibrarySystemService
    ):
        """Two running TickEmit producers, no Shutdown node: stop must not hang.

        This is the original reported bug. Without a Shutdown flow there is no
        graceful path, so stop skips the grace period and force-tears-down
        immediately; on_shutdown is the last-resort thread kill.
        """
        import time

        graph = self._build_two_tick_emitters(graph_with_library_system, with_shutdown=False)

        interpreter = Interpreter()
        interpreter.load_graph(graph)
        interpreter.start_execution()

        # Let the tick threads spin up and start feeding the Tick queues.
        time.sleep(0.2)

        elapsed = self._stop_must_not_hang(interpreter)
        # No graceful path => no grace period => fast stop.
        assert elapsed < 4.0
        assert not interpreter.is_executing

    def test_stop_with_tick_emitters_graceful_shutdown(
        self, graph_with_library_system: BaseGraph, library_system: LibrarySystemService
    ):
        """Two running TickEmit producers with Shutdown→stop wired: stop is graceful."""
        import time

        graph = self._build_two_tick_emitters(graph_with_library_system, with_shutdown=True)

        interpreter = Interpreter()
        interpreter.load_graph(graph)
        interpreter.start_execution()

        time.sleep(0.2)

        # Graceful path runs during the grace period; must still not hang.
        self._stop_must_not_hang(interpreter)
        assert not interpreter.is_executing
