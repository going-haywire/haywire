"""A node or edge failing inside a validation batch reaches the error ledger; the batch goes on."""

import pytest

from haywire.core.errors.ledger import ErrorLedger, get_error_ledger, set_error_ledger
from haywire.core.graph.types import ChangeReason

from tests.conftest import make_edge, make_node

pytestmark = pytest.mark.integration

_ADD = "haybale-testing:node:TestAddFloatNode"


@pytest.fixture
def ledger():
    previous = get_error_ledger()
    fresh = ErrorLedger(max_entries=5)
    set_error_ledger(fresh)
    yield fresh
    set_error_ledger(previous)


def test_a_node_failing_validation_is_recorded_and_the_loop_continues(ledger, graph_with_library_system):
    from haybale_testing.nodes.testbed.math_op_node import TestAddFloatNode

    graph = graph_with_library_system
    key = TestAddFloatNode.class_identity.registry_key
    bad, good = make_node(graph, key), make_node(graph, key)
    assert isinstance(bad.node, TestAddFloatNode)
    graph.force_validation()
    ledger.clear()

    def broken(*args, **kwargs):
        raise RuntimeError("build broke")

    bad.build = broken  # type: ignore[method-assign]
    validated: set[str] = set()
    graph._validation.subscribe(lambda result: validated.update(result.nodes))
    graph._validation.mark_node_dirty(bad.node_id, ChangeReason.NODE_RESET_REQUESTED)
    graph._validation.mark_node_dirty(good.node_id, ChangeReason.NODE_RESET_REQUESTED)
    graph._validation.force_immediate_validation()

    assert good.node_id in validated
    assert bad.node_id not in validated
    (entry,) = ledger.query().entries
    assert entry.operation == "Validate node"
    assert entry.node_id == bad.node_id
    assert entry.graph_id == graph.graph_id
    assert entry.registry_key == key
    assert entry.error_context["reason"] == "NODE_RESET_REQUESTED"


def test_an_edge_failing_validation_is_recorded(ledger, graph_with_library_system):
    graph = graph_with_library_system
    a = make_node(graph, _ADD, position=(0, 0))
    b = make_node(graph, _ADD, position=(300, 0))
    edge = make_edge(graph, a.node_id, "result", b.node_id, "value_a")
    graph.force_validation()
    ledger.clear()

    def broken(*args, **kwargs):
        raise RuntimeError("edge broke")

    edge.build = broken  # type: ignore[method-assign]
    graph._validation.mark_edge_dirty(edge.edge_id, ChangeReason.EDGE_VALIDATION_REQUESTED)
    graph._validation.force_immediate_validation()

    (entry,) = ledger.query().entries
    assert entry.operation == "Validate edge"
    assert entry.edge_id == edge.edge_id
    assert entry.graph_id == graph.graph_id
    assert entry.error_context["reason"] == "EDGE_VALIDATION_REQUESTED"
