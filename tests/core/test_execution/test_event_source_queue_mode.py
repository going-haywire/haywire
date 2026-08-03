"""Integration tests for per-event-node queue mode (ADR 0010).

Exercises the realtime-drop wiring end to end through a real haybale-testing
event node (``TestCustomCallback``): the node's ``queue_mode`` config feeds the
``CallbackEvent`` it builds, assembly turns it into a Flow, and ``_register_flow``
builds the ``FlowScheduler`` from the subscription's fields — replacing the old
hardcoded ``QueueMode.BLOCK``.

Driven entirely through library nodes + the Interpreter; no hand-built
``CallbackEvent``/``FlowScheduler``.
"""

import pytest

from haywire.core.execution.interpreter import Interpreter
from haywire.core.execution.scheduler import QueueMode
from haywire.core.graph.base import BaseGraph
from haywire.core.di.config import LibrarySystemService

from tests.conftest import make_edge, make_node


def _scheduler_for(interpreter: Interpreter, callback_name: str):
    """Return the scheduler of the flow subscribed to ``callback:<name>``."""
    flows = interpreter.event_subscriptions.get(f"callback:{callback_name}", [])
    assert len(flows) == 1, f"expected one flow for {callback_name!r}, got {len(flows)}"
    return flows[0].scheduler


@pytest.mark.integration
@pytest.mark.slow
class TestEventNodeQueueMode:
    """The queue mode chosen on the event node reaches its flow's scheduler."""

    def _build(self, graph: BaseGraph, callback_name: str, queue_mode: str) -> BaseGraph:
        from haybale_testing.nodes.testbed.custom_callback_node import (
            TestCustomCallbackNode as CustomCallbackNode,
        )
        from haybale_testing.nodes.testbed.print_node import TestPrintNode as PrintNode

        custom_callback = make_node(
            graph, CustomCallbackNode.class_identity.registry_key, position=(100, 100)
        )
        # Set the name + queue mode first, then flip mode_switch last — its
        # on_change="redraw" rebuilds the subscription and captures both.
        custom_callback.node.ports["custom_callback_name"].set_value(callback_name)
        custom_callback.node.ports["queue_mode"].set_value(queue_mode)
        custom_callback.node.ports["mode_switch"].set_value(True)

        print_msg = make_node(graph, PrintNode.class_identity.registry_key, position=(300, 100))
        make_edge(graph, custom_callback.node_id, "triggered", print_msg.node_id, "exec")
        return graph

    def test_drop_event_node_yields_drop_scheduler(
        self, graph_with_library_system: BaseGraph, library_system: LibrarySystemService
    ):
        """A 'drop' event node assembles into a DROP scheduler with a depth-1 queue."""
        graph = self._build(graph_with_library_system, "rt_cb", "drop")

        interpreter = Interpreter()
        interpreter.load_graph(graph)
        try:
            scheduler = _scheduler_for(interpreter, "rt_cb")
            assert scheduler.queue_mode is QueueMode.DROP
            assert scheduler.max_queue_size == 1
            assert scheduler.trigger_queue.maxsize == 1
        finally:
            interpreter.shutdown()

    def test_default_event_node_yields_block_scheduler(
        self, graph_with_library_system: BaseGraph, library_system: LibrarySystemService
    ):
        """The default 'block' event node keeps the legacy BLOCK / 100 scheduler —
        existing graphs are unchanged."""
        graph = self._build(graph_with_library_system, "batch_cb", "block")

        interpreter = Interpreter()
        interpreter.load_graph(graph)
        try:
            scheduler = _scheduler_for(interpreter, "batch_cb")
            assert scheduler.queue_mode is QueueMode.BLOCK
            assert scheduler.max_queue_size == 100
        finally:
            interpreter.shutdown()
