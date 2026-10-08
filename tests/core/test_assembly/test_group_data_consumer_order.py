"""A data node downstream of a data-only Group runs after the Group's interior.

Regression: the data-flow sort used to order from outlet-side lookups, while the
flat view splices ``Output -> consumer`` only on inlet-side lookups, so the
consumer read the card's value from the previous frame.
"""

from __future__ import annotations

import pytest

from tests.conftest import make_edge, make_node, run_frame

pytestmark = pytest.mark.integration

_INPUT = "haywire-core:node:SubgraphInputNode"
_OUTPUT = "haywire-core:node:SubgraphOutputNode"
_CARD = "haywire-core:node:GraphNode"


def _keys():
    from haybale_testing.nodes.testbed.begin_play_node import TestBeginPlayNode
    from haybale_testing.nodes.testbed.math_op_node import TestAddFloatNode
    from haybale_testing.nodes.testbed.print_node import TestPrintNode

    return (
        TestBeginPlayNode.class_identity.registry_key,
        TestPrintNode.class_identity.registry_key,
        TestAddFloatNode.class_identity.registry_key,
    )


def _add(graph, b: float):
    _, _, add_key = _keys()
    node = make_node(graph, add_key)
    node.node.ports["value_b"].set_value(b)
    return node


def _collapse(graph, node_ids):
    from haywire.core.undo.actions.graph_actions import CollapseToGraphNodeAction

    CollapseToGraphNodeAction(
        graph=graph,
        node_ids=list(node_ids),
        card_registry_key=_CARD,
        input_registry_key=_INPUT,
        output_registry_key=_OUTPUT,
        label="Group",
    ).execute()
    graph.force_validation()


def _chain(graph, tails):
    """BeginPlay -> Print, and A(1+2) -> X(+0) -> tails... -> Print.message."""
    begin_key, print_key, _ = _keys()
    begin = make_node(graph, begin_key)
    printer = make_node(graph, print_key)
    make_edge(graph, begin.node_id, "exec", printer.node_id, "exec")
    a = _add(graph, 2.0)
    a.node.ports["value_a"].set_value(1.0)
    x = _add(graph, 0.0)
    make_edge(graph, a.node_id, "result", x.node_id, "value_a")
    previous = x
    for node in tails:
        make_edge(graph, previous.node_id, "result", node.node_id, "value_a")
        previous = node
    make_edge(graph, previous.node_id, "result", printer.node_id, "message")
    graph.force_validation()
    return a, x


def test_a_data_node_after_a_group_sees_this_frames_interior(graph_with_library_system):
    graph = graph_with_library_system
    y = _add(graph, 100.0)
    a, x = _chain(graph, [y])
    _collapse(graph, [x.node_id])

    run_frame(graph)
    assert y.node.ports["result"].get_value() == pytest.approx(103.0)

    a.node.ports["value_a"].set_value(11.0)
    run_frame(graph)
    assert y.node.ports["result"].get_value() == pytest.approx(113.0)


def test_a_data_node_after_two_adjacent_groups_sees_both_interiors(graph_with_library_system):
    graph = graph_with_library_system
    z = _add(graph, 1000.0)
    y = _add(graph, 100.0)
    _a, x = _chain(graph, [z, y])
    _collapse(graph, [x.node_id])
    _collapse(graph, [z.node_id])

    run_frame(graph)

    assert y.node.ports["result"].get_value() == pytest.approx(1103.0)
