"""Containers of control and callback elements run end to end (decision Q39)."""

import pytest

from haywire.core.execution.event_source import SystemEventType
from haywire.core.execution.interpreter import Interpreter
from haywire.core.types import WireRole

from tests.conftest import make_edge, make_node

pytestmark = pytest.mark.integration


def _run(graph) -> None:
    interpreter = Interpreter()
    interpreter.load_graph(graph)
    try:
        interpreter.dispatch_system_event(SystemEventType.BEGIN_PLAY)
        interpreter.wait_all(timeout=5.0)
    finally:
        interpreter.shutdown()


def test_an_array_of_exec_fires_its_transition_with_the_list(graph_with_library_system):
    from haybale_testing.nodes.testbed.begin_play_node import TestBeginPlayNode
    from haybale_testing.nodes.testbed.container_signal_probes import ArrayExecProbeNode

    graph = graph_with_library_system
    begin = make_node(graph, TestBeginPlayNode.class_identity.registry_key, position=(0, 0))
    source = make_node(graph, ArrayExecProbeNode.class_identity.registry_key, position=(200, 0))
    sink = make_node(graph, ArrayExecProbeNode.class_identity.registry_key, position=(400, 0))
    make_edge(graph, begin.node_id, "exec", source.node_id, "exec_in")
    edge = make_edge(graph, source.node_id, "exec_list_out", sink.node_id, "exec_list_in")
    source.node.emit = [{"n": 1}, {"n": 2}]  # type: ignore[attr-defined]
    graph.force_validation()

    assert edge.state.is_valid()
    assert edge.wire_type is not None and edge.wire_type.role is WireRole.SEQUENCE  # noqa: PT018

    _run(graph)

    assert sink.node.received == [{"n": 1}, {"n": 2}]  # type: ignore[attr-defined]


def test_an_array_of_callbacks_reaches_its_inlet_on_write(graph_with_library_system):
    from haybale_testing.nodes.testbed.container_signal_probes import ArrayCallbackProbeNode

    graph = graph_with_library_system
    key = ArrayCallbackProbeNode.class_identity.registry_key
    source = make_node(graph, key, position=(0, 0))
    sink = make_node(graph, key, position=(300, 0))
    edge = make_edge(graph, source.node_id, "names_out", sink.node_id, "names_in")
    graph.force_validation()

    assert edge.state.is_valid()

    source.node.ports["names_out"].set_value(["a", "b"])

    assert sink.node.heard[-1] == ["a", "b"]  # type: ignore[attr-defined]


def test_a_pool_of_exec_stays_refused(graph_with_library_system):
    """A pool of EXEC stays refused when a node builds the port, as its `init()` would (Q39)."""
    from haybale_core.types import PooledType
    from haybale_testing.nodes.testbed.container_signal_probes import ArrayExecProbeNode

    from haywire.barn.builtin.types import EXEC

    node = make_node(
        graph_with_library_system, ArrayExecProbeNode.class_identity.registry_key, position=(0, 0)
    ).node

    with pytest.raises(ValueError, match="never fired"):
        node.add(PooledType[EXEC].as_inlet("pooled_exec_in"))
