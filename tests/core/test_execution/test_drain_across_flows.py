"""A drain inlet collecting what another flow writes: every value arrives once, in order.

Flow P runs a producer that writes 0, 1, 2, ... to an outlet; flow C runs a consumer
whose drain inlet that outlet feeds. Each flow is started by its own event node
through ``HaywireVM.emit_callback``, so the two run on separate threads and
interleave freely.
"""

import pytest

from haywire.core.execution.interpreter import Interpreter
from haywire.core.graph.base import BaseGraph

from tests.conftest import make_edge, make_node

WRITES = 300


def _setup(graph: BaseGraph):
    from haybale_testing.nodes.testbed.drain_probe import DrainConsumerProbeNode, DrainProducerProbeNode
    from haybale_testing.nodes.testbed.record_callback_nodes import TestRecordEventNode

    event = TestRecordEventNode.class_identity.registry_key
    p_event = make_node(graph, event, position=(0, 0))
    c_event = make_node(graph, event, position=(0, 300))
    producer = make_node(graph, DrainProducerProbeNode.class_identity.registry_key, position=(300, 0))
    consumer = make_node(graph, DrainConsumerProbeNode.class_identity.registry_key, position=(300, 300))
    assert isinstance(producer.node, DrainProducerProbeNode)
    assert isinstance(consumer.node, DrainConsumerProbeNode)

    for edge in (
        make_edge(graph, p_event.node_id, "triggered", producer.node_id, "exec_in"),
        make_edge(graph, c_event.node_id, "triggered", consumer.node_id, "exec_in"),
        make_edge(graph, producer.node_id, "value", consumer.node_id, "queue"),
    ):
        assert edge.state.is_valid(), f"invalid edge {edge.edge_id}"
    return p_event, c_event, producer.node, consumer.node


@pytest.mark.integration
class TestADrainInletAcrossFlows:
    def test_every_value_arrives_once_in_order(self, graph_with_library_system: BaseGraph, library_system):
        p_event, c_event, producer, consumer = _setup(graph_with_library_system)

        interpreter = Interpreter()
        interpreter.load_graph(graph_with_library_system)
        try:
            for i in range(WRITES):
                interpreter.vm.emit_callback(p_event.node_id)
                if i % 7 == 0:
                    interpreter.vm.emit_callback(c_event.node_id)
            interpreter.wait_all(timeout=10.0, stop_after=False)
            # One more take after the producer is done collects what is still queued.
            interpreter.vm.emit_callback(c_event.node_id)
            interpreter.wait_all(timeout=10.0)
        finally:
            interpreter.shutdown()

        assert producer.written == WRITES
        assert consumer.taken == [float(i) for i in range(WRITES)]
        assert consumer.dropped == 0
        # More than one non-empty take: values were taken while the producer was still writing.
        assert sum(1 for n in consumer.batches if n) > 1

    def test_the_flows_run_on_separate_threads(self, graph_with_library_system: BaseGraph, library_system):
        p_event, c_event, producer, consumer = _setup(graph_with_library_system)

        interpreter = Interpreter()
        interpreter.load_graph(graph_with_library_system)
        try:
            interpreter.vm.emit_callback(p_event.node_id)
            interpreter.vm.emit_callback(c_event.node_id)
            interpreter.wait_all(timeout=10.0)
        finally:
            interpreter.shutdown()

        assert producer.threads
        assert consumer.threads
        assert producer.threads.isdisjoint(consumer.threads)
