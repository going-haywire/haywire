"""``behavior`` is per-instance state, stamped from the class at construction.

Most nodes keep their class's flags for life. A node whose execution role
follows its ports — a Graph-node is the one in the codebase — restamps
``node_type`` through ``set_node_type()``, which is the only field that may
vary per instance.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, cast

import pytest

from haywire.core.graph.base import BaseGraph
from haywire.core.node.behavior import NodeType
from haywire.core.node.node_wrapper import NodeWrapper

from tests.conftest import make_node

if TYPE_CHECKING:
    from haywire.barn.builtin.nodes.graph_node import GraphNode

pytestmark = [pytest.mark.integration]

_ADD = "haybale-testing:node:TestAddFloatNode"
_PRINT = "haybale-testing:node:TestPrintNode"
_CARD = "haywire-core:node:GraphNode"


def _card(wrapper: NodeWrapper) -> "GraphNode":
    """The wrapper's node, typed as the GraphNode it is."""
    return cast("GraphNode", wrapper.node)


class TestStampedFromTheClass:
    def test_a_fresh_node_carries_its_class_flags(self, graph_with_library_system: BaseGraph):
        graph = graph_with_library_system
        wrapper = make_node(graph, _ADD)

        assert wrapper.node.behavior == type(wrapper.node).class_behavior

    def test_the_instance_answer_is_not_the_class_attribute_itself(
        self, graph_with_library_system: BaseGraph
    ):
        """Equal at first, but a restamp must not reach back to the class."""
        graph = graph_with_library_system
        wrapper = make_node(graph, _PRINT)
        before = type(wrapper.node).class_behavior

        wrapper.node.set_node_type(NodeType.DATA)

        assert type(wrapper.node).class_behavior is before
        assert type(wrapper.node).class_behavior.node_type == before.node_type


class TestRestamping:
    def test_it_changes_the_node_type(self, graph_with_library_system: BaseGraph):
        graph = graph_with_library_system
        wrapper = make_node(graph, _PRINT)

        wrapper.node.set_node_type(NodeType.DATA)

        assert wrapper.node.behavior.node_type == NodeType.DATA

    def test_it_leaves_every_other_flag_alone(self, graph_with_library_system: BaseGraph):
        graph = graph_with_library_system
        wrapper = make_node(graph, _PRINT)
        before = wrapper.node.behavior

        wrapper.node.set_node_type(NodeType.DATA)
        after = wrapper.node.behavior

        assert after.is_stateful == before.is_stateful
        assert after.has_execute_async == before.has_execute_async
        assert after.is_thread_safe == before.is_thread_safe
        assert after.is_mutable == before.is_mutable

    def test_the_flags_object_is_replaced_not_mutated(self, graph_with_library_system: BaseGraph):
        """``NodeBehaviorFlags`` is frozen — a restamp swaps the whole set."""
        graph = graph_with_library_system
        wrapper = make_node(graph, _PRINT)
        before = wrapper.node.behavior

        wrapper.node.set_node_type(NodeType.DATA)

        assert wrapper.node.behavior is not before

    def test_two_nodes_of_one_class_restamp_independently(self, graph_with_library_system: BaseGraph):
        """The field is per instance, so one card's role cannot move another's."""
        graph = graph_with_library_system
        first, second = make_node(graph, _PRINT), make_node(graph, _PRINT)
        untouched = second.node.behavior.node_type

        first.node.set_node_type(NodeType.DATA)

        assert first.node.behavior.node_type == NodeType.DATA
        assert second.node.behavior.node_type == untouched


class TestTheGraphNodeCard:
    """The one node in the codebase whose role follows its ports."""

    def test_a_card_with_no_subgraph_is_a_data_node(self, graph_with_library_system: BaseGraph):
        """No interface, so no control crossing, so DATA.

        An unbound card never reaches ``reconcile_interface`` — it returns
        early with no definition — so the role has to be stamped in ``init()``.
        Leaving it to reconcile alone makes an unbound card report its class
        default, CONTROL.
        """
        graph = graph_with_library_system
        card = make_node(graph, _CARD)

        assert card.node.behavior.node_type == NodeType.DATA

    def test_the_role_is_readable_before_the_first_reconcile(self, graph_with_library_system: BaseGraph):
        """Structural validation reads it as the node is added."""
        graph = graph_with_library_system
        card = make_node(graph, _CARD)

        assert card.node.behavior is not None
        assert card.node.behavior.is_mutable is True

    def test_a_control_crossed_card_is_a_control_node(self, graph_with_library_system: BaseGraph):
        from haybale_core.types import EXEC
        from haywire.core.graph.scheduler import SyncScheduler
        from haywire.core.graph.subgraph import SubgraphDefinition
        from haywire.barn.builtin.nodes.graph_node import SUBGRAPH_KEY
        from haywire.core.types.enums import PortType

        graph = graph_with_library_system
        definition = graph.add_subgraph(
            SubgraphDefinition(key="sg_b", label="G", validation_scheduler=SyncScheduler())
        )
        input_node = make_node(definition, "haywire-core:node:SubgraphInputNode")
        with input_node.node.rejig():
            input_node.node.add(EXEC.as_outlet("exec"))

        card = make_node(graph, _CARD, node_data={"store": {SUBGRAPH_KEY: "sg_b"}})
        _card(card).reconcile_interface()

        assert card.node.get_ports(is_port_type=PortType.INLET, has_pin=True)
        assert card.node.behavior.node_type == NodeType.CONTROL

    def test_the_role_follows_the_interface_when_it_changes(self, graph_with_library_system: BaseGraph):
        """Drop the control crossing and the card becomes a DATA node again."""
        from haybale_core.types import EXEC
        from haywire.core.graph.scheduler import SyncScheduler
        from haywire.core.graph.subgraph import SubgraphDefinition
        from haywire.barn.builtin.nodes.graph_node import SUBGRAPH_KEY

        graph = graph_with_library_system
        definition = graph.add_subgraph(
            SubgraphDefinition(key="sg_c", label="G", validation_scheduler=SyncScheduler())
        )
        input_node = make_node(definition, "haywire-core:node:SubgraphInputNode")
        with input_node.node.rejig():
            input_node.node.add(EXEC.as_outlet("exec"))

        card = make_node(graph, _CARD, node_data={"store": {SUBGRAPH_KEY: "sg_c"}})
        _card(card).reconcile_interface()
        assert card.node.behavior.node_type == NodeType.CONTROL

        # The interface loses its control port; the card follows.
        with input_node.node.rejig():
            pass
        _card(card).reconcile_interface()

        assert card.node.behavior.node_type == NodeType.DATA
