"""GraphNode: binding a Subgraph, mirroring its interface, and the derived node type."""

from __future__ import annotations

from typing import TYPE_CHECKING, cast

import pytest

from haywire.core.graph.base import BaseGraph
from haywire.core.graph.scheduler import SyncScheduler
from haywire.core.graph.subgraph import SubgraphDefinition
from haywire.core.node.node_wrapper import NodeWrapper
from haywire.core.types.enums import PortType

if TYPE_CHECKING:
    from haywire.barn.builtin.nodes.graph_node import GraphNode

pytestmark = pytest.mark.integration


def _definition(graph: BaseGraph, key: str = "sg_1", label: str = "Group") -> SubgraphDefinition:
    definition = SubgraphDefinition(key=key, label=label, validation_scheduler=SyncScheduler())
    return graph.add_subgraph(definition)


def _boundary(graph: BaseGraph, *, is_input: bool) -> NodeWrapper:
    from haywire.barn.builtin.nodes.subgraph_io import SubgraphInputNode, SubgraphOutputNode

    cls = SubgraphInputNode if is_input else SubgraphOutputNode
    wrapper = graph.create_node_wrapper(cls.class_identity.registry_key)
    assert wrapper is not None
    return wrapper


def _card(wrapper: NodeWrapper) -> "GraphNode":
    """The wrapper's node, typed as the GraphNode it is."""
    return cast("GraphNode", wrapper.node)


def _graph_node(graph: BaseGraph, subgraph_key: str | None = None) -> NodeWrapper:
    """Create a Graph-node, optionally already bound through its store."""
    from haywire.barn.builtin.nodes.graph_node import SUBGRAPH_KEY, GraphNode

    node_data = {"store": {SUBGRAPH_KEY: subgraph_key}} if subgraph_key else None
    wrapper = graph.create_node_wrapper(
        GraphNode.class_identity.registry_key,
        node_data=node_data,
    )
    assert wrapper is not None
    return wrapper


def _rendered(node) -> list[str]:
    """The card's pin ids in the order the skin draws them."""
    return [p.id for p in node.get_visible_ports() if p.has_pin() and p.is_inlet()]


def _stamp_data_interface(definition: SubgraphDefinition) -> tuple[NodeWrapper, NodeWrapper]:
    """Give the definition a data-only interface: one inlet in, one outlet out."""
    from haybale_testing.types.test_types import TEST_FLOAT

    input_node = _boundary(definition, is_input=True)
    output_node = _boundary(definition, is_input=False)

    with input_node.node.rejig():
        input_node.node.add(TEST_FLOAT.as_outlet("value", label="Value"))
    with output_node.node.rejig():
        output_node.node.add(TEST_FLOAT.as_inlet("result", label="Result"))

    return input_node, output_node


def _stamp_control_interface(definition: SubgraphDefinition) -> None:
    """Give the definition a control crossing on top of a data outlet."""
    from haybale_core.types import EXEC
    from haybale_testing.types.test_types import TEST_FLOAT

    input_node = _boundary(definition, is_input=True)
    output_node = _boundary(definition, is_input=False)

    with input_node.node.rejig():
        input_node.node.add(EXEC.as_outlet("exec"))
    with output_node.node.rejig():
        output_node.node.add(EXEC.as_inlet("exec"))
        output_node.node.add(TEST_FLOAT.as_inlet("result"))


class TestBinding:
    def test_an_unbound_graph_node_resolves_no_definition(self, graph_with_library_system: BaseGraph):
        node = _card(_graph_node(graph_with_library_system))

        assert node.subgraph_key is None
        assert node.resolve_definition() is None

    def test_binding_records_the_key_and_resolves(self, graph_with_library_system: BaseGraph):
        graph = graph_with_library_system
        definition = _definition(graph)
        node = _card(_graph_node(graph))

        node.bind_subgraph(definition.key)

        assert node.subgraph_key == definition.key
        assert node.resolve_definition() is definition

    def test_a_key_with_no_definition_resolves_to_none(self, graph_with_library_system: BaseGraph):
        node = _card(_graph_node(graph_with_library_system))
        node.bind_subgraph("nobody")

        assert node.subgraph_key == "nobody"
        assert node.resolve_definition() is None

    def test_the_key_survives_a_round_trip(self, graph_with_library_system: BaseGraph):
        graph = graph_with_library_system
        definition = _definition(graph)
        _stamp_data_interface(definition)
        node = _graph_node(graph, subgraph_key=definition.key)

        data = graph.to_dict()
        restored = BaseGraph(filestem="restored", validation_scheduler=SyncScheduler())
        assert restored.load_from_dict(data) is True

        restored_node = restored.get_node_wrapper(node.node_id)
        assert restored_node is not None
        assert _card(restored_node).subgraph_key == definition.key
        assert _card(restored_node).resolve_definition() is restored.get_subgraph(definition.key)


class TestInterfaceMirroring:
    def test_the_card_mirrors_the_boundary_ports(self, graph_with_library_system: BaseGraph):
        graph = graph_with_library_system
        definition = _definition(graph)
        _stamp_data_interface(definition)

        node = _card(_graph_node(graph, subgraph_key=definition.key))

        inlets = node.get_ports(is_port_type=PortType.INLET, has_pin=True)
        outlets = node.get_ports(is_port_type=PortType.OUTLET, has_pin=True)

        assert [p.id for p in inlets] == ["in_value"]
        assert [p.id for p in outlets] == ["out_result"]

    def test_a_mirrored_pin_keeps_the_boundary_ports_label(self, graph_with_library_system: BaseGraph):
        graph = graph_with_library_system
        definition = _definition(graph)
        _stamp_data_interface(definition)

        node = _card(_graph_node(graph, subgraph_key=definition.key))

        assert node.get_ports(is_port_type=PortType.INLET, has_pin=True)[0].label == "Value"
        assert node.get_ports(is_port_type=PortType.OUTLET, has_pin=True)[0].label == "Result"

    def test_an_unbound_card_carries_no_pins(self, graph_with_library_system: BaseGraph):
        node = _card(_graph_node(graph_with_library_system))

        assert node.get_ports(has_pin=True) == []

    def test_adding_a_boundary_port_reconciles_the_card(self, graph_with_library_system: BaseGraph):
        from haybale_testing.types.test_types import TEST_FLOAT

        graph = graph_with_library_system
        definition = _definition(graph)
        input_node, _ = _stamp_data_interface(definition)
        node = _card(_graph_node(graph, subgraph_key=definition.key))

        with input_node.node.rejig():
            input_node.node.add(TEST_FLOAT.as_outlet("value", label="Value"))
            input_node.node.add(TEST_FLOAT.as_outlet("gain", label="Gain"))

        node.reconcile_interface()

        assert {p.id for p in node.get_ports(is_port_type=PortType.INLET, has_pin=True)} == {
            "in_value",
            "in_gain",
        }

    def test_removing_a_boundary_port_drops_exactly_that_pin(self, graph_with_library_system: BaseGraph):
        from haybale_testing.types.test_types import TEST_FLOAT

        graph = graph_with_library_system
        definition = _definition(graph)
        input_node, _ = _stamp_data_interface(definition)
        with input_node.node.rejig():
            input_node.node.add(TEST_FLOAT.as_outlet("value"))
            input_node.node.add(TEST_FLOAT.as_outlet("gain"))

        node = _card(_graph_node(graph, subgraph_key=definition.key))
        assert len(node.get_ports(is_port_type=PortType.INLET, has_pin=True)) == 2

        with input_node.node.rejig():
            input_node.node.add(TEST_FLOAT.as_outlet("value"))
        node.reconcile_interface()

        assert [p.id for p in node.get_ports(is_port_type=PortType.INLET, has_pin=True)] == ["in_value"]

    def test_removing_a_boundary_port_drops_the_edges_that_lost_it(
        self, graph_with_library_system: BaseGraph
    ):
        from haybale_testing.nodes.testbed.edge_link_test import EdgeLinkTestNode
        from haybale_testing.types.test_types import TEST_FLOAT

        graph = graph_with_library_system
        definition = _definition(graph)
        input_node, _ = _stamp_data_interface(definition)
        with input_node.node.rejig():
            input_node.node.add(TEST_FLOAT.as_outlet("value"))
            input_node.node.add(TEST_FLOAT.as_outlet("gain"))

        card = _graph_node(graph, subgraph_key=definition.key)
        feeder = graph.create_node_wrapper(EdgeLinkTestNode.class_identity.registry_key)
        assert feeder is not None

        kept = graph.create_edge_wrapper(feeder.node_id, "float_outlet", card.node_id, "in_value")
        dropped = graph.create_edge_wrapper(feeder.node_id, "float_outlet", card.node_id, "in_gain")
        assert kept is not None
        assert dropped is not None

        with input_node.node.rejig():
            input_node.node.add(TEST_FLOAT.as_outlet("value"))
        _card(card).reconcile_interface()
        graph.force_validation()

        assert graph.get_edge_wrapper(kept.edge_id) is not None
        assert graph.get_edge_wrapper(dropped.edge_id) is None


class TestPinIdMapping:
    def test_the_two_sides_never_collide(self):
        """A control Subgraph has ``exec`` on both boundary nodes."""
        from haywire.core.graph.subgraph_crossing import card_port_id

        assert card_port_id("exec", is_inlet=True) != card_port_id("exec", is_inlet=False)

    def test_the_mapping_is_invertible(self):
        from haywire.core.graph.subgraph_crossing import boundary_port_id, card_port_id

        for port_id in ("exec", "value", "in_x", "out_x", "in_in_x"):
            for is_inlet in (True, False):
                assert boundary_port_id(card_port_id(port_id, is_inlet=is_inlet)) == port_id

    def test_a_prefixed_boundary_id_does_not_alias_a_bare_one(self):
        """Prefixing every pin is what keeps the mapping total."""
        from haywire.core.graph.subgraph_crossing import card_port_id

        assert card_port_id("in_x", is_inlet=True) != card_port_id("x", is_inlet=True)

    def test_a_pin_that_mirrors_nothing_maps_to_none(self):
        from haywire.core.graph.subgraph_crossing import boundary_port_id

        assert boundary_port_id("unprefixed") is None

    def test_a_control_subgraph_gets_both_exec_pins(self, graph_with_library_system: BaseGraph):
        graph = graph_with_library_system
        definition = _definition(graph)
        _stamp_control_interface(definition)

        node = _card(_graph_node(graph, subgraph_key=definition.key))

        assert {p.id for p in node.get_ports(is_port_type=PortType.INLET, has_pin=True)} == {"in_exec"}
        assert {p.id for p in node.get_ports(is_port_type=PortType.OUTLET, has_pin=True)} == {
            "out_exec",
            "out_result",
        }


class TestDerivedNodeType:
    def test_a_data_only_interface_makes_it_a_data_node(self, graph_with_library_system: BaseGraph):
        from haywire.core.node import NodeType

        graph = graph_with_library_system
        definition = _definition(graph)
        _stamp_data_interface(definition)
        node = _card(_graph_node(graph, subgraph_key=definition.key))

        assert node.behavior.node_type == NodeType.DATA
        assert node.behavior.is_data_node is True
        assert node.behavior.is_control_node is False

    def test_a_control_crossing_makes_it_a_control_node(self, graph_with_library_system: BaseGraph):
        from haywire.core.node import NodeType

        graph = graph_with_library_system
        definition = _definition(graph)
        _stamp_control_interface(definition)
        node = _card(_graph_node(graph, subgraph_key=definition.key))

        assert NodeType.CONTROL in node.behavior.node_type
        assert node.behavior.is_control_node is True

    def test_the_class_stays_control_typed(self):
        """The derived type is per instance; the class cannot carry an interface."""
        from haywire.barn.builtin.nodes.graph_node import GraphNode
        from haywire.core.node import NodeType

        assert GraphNode.class_behavior.node_type == NodeType.CONTROL

    def test_a_data_typed_card_passes_structural_validation(self, graph_with_library_system: BaseGraph):
        graph = graph_with_library_system
        definition = _definition(graph)
        _stamp_data_interface(definition)
        card = _graph_node(graph, subgraph_key=definition.key)

        assert card.state.is_structural, card.state.error_structural

    def test_a_control_typed_card_passes_structural_validation(self, graph_with_library_system: BaseGraph):
        graph = graph_with_library_system
        definition = _definition(graph)
        _stamp_control_interface(definition)
        card = _graph_node(graph, subgraph_key=definition.key)

        assert card.state.is_structural, card.state.error_structural


class TestRegistration:
    def test_the_class_is_hidden_from_the_add_node_menu(self):
        from haywire.barn.builtin.nodes.graph_node import GraphNode

        assert GraphNode.class_identity.hidden is True

    def test_the_class_is_mutable(self):
        from haywire.barn.builtin.nodes.graph_node import GraphNode

        assert GraphNode.class_behavior.is_mutable is True


class TestInterfaceEditing:
    """Editing a boundary port, then reconciling.

    ``reconcile_interface()`` is the explicit call the editing path has to make;
    nothing observes a boundary port edit on its own — see the note in step 5 of
    the plan.
    """

    def test_reordering_boundary_ports_reorders_the_cards_pins(self, graph_with_library_system: BaseGraph):
        """The Ports panel's drag-to-reorder writes ``DataPort.order``."""
        from haybale_testing.types.test_types import TEST_FLOAT

        graph = graph_with_library_system
        definition = _definition(graph)
        input_node, _ = _stamp_data_interface(definition)
        with input_node.node.rejig():
            input_node.node.add(TEST_FLOAT.as_outlet("alpha"))
            input_node.node.add(TEST_FLOAT.as_outlet("beta"))

        card = _card(_graph_node(graph, subgraph_key=definition.key))
        # get_ports is dict order; get_visible_ports is what the skin renders,
        # sorted by DataPort.order — that is the order a reorder has to reach.
        assert _rendered(card) == ["in_alpha", "in_beta"]

        input_node.node.reorder_ports(["beta", "alpha"])
        card.reconcile_interface()

        assert _rendered(card) == ["in_beta", "in_alpha"]

    def test_reconciling_after_an_unrelated_inner_edit_leaves_the_pins_alone(
        self, graph_with_library_system: BaseGraph
    ):
        from haybale_testing.nodes.testbed.edge_link_test import EdgeLinkTestNode

        graph = graph_with_library_system
        definition = _definition(graph)
        _stamp_data_interface(definition)
        card = _card(_graph_node(graph, subgraph_key=definition.key))
        before = [p.id for p in card.get_ports(has_pin=True)]

        definition.create_node_wrapper(EdgeLinkTestNode.class_identity.registry_key)
        card.reconcile_interface()

        assert [p.id for p in card.get_ports(has_pin=True)] == before

    def test_reconciling_twice_is_idempotent(self, graph_with_library_system: BaseGraph):
        graph = graph_with_library_system
        definition = _definition(graph)
        _stamp_data_interface(definition)
        card = _card(_graph_node(graph, subgraph_key=definition.key))

        before = [p.id for p in card.get_ports(has_pin=True)]
        card.reconcile_interface()
        card.reconcile_interface()

        assert [p.id for p in card.get_ports(has_pin=True)] == before


class TestNaming:
    """The card is what the user names, so its name is the Subgraph's name."""

    def test_renaming_the_card_renames_the_subgraph(self, graph_with_library_system: BaseGraph):
        graph = graph_with_library_system
        definition = _definition(graph, label="Group")
        node = _card(_graph_node(graph, definition.key))

        node.props.label = "Smoothing"

        assert definition.label == "Smoothing"

    def test_clearing_the_label_goes_back_to_the_class_label(self, graph_with_library_system: BaseGraph):
        graph = graph_with_library_system
        definition = _definition(graph, label="Group")
        node = _card(_graph_node(graph, definition.key))
        node.props.label = "Smoothing"

        node.props.label = ""

        assert definition.label == node.display_label == "Group"

    def test_an_unbound_card_renames_nothing(self, graph_with_library_system: BaseGraph):
        """No definition to reach, and nothing raised on the way."""
        node = _card(_graph_node(graph_with_library_system))

        node.props.label = "Smoothing"

        assert node.display_label == "Smoothing"

    def test_the_name_survives_a_save_and_load(self, graph_with_library_system: BaseGraph):
        """Both halves are serialized, so they come back agreeing."""
        graph = graph_with_library_system
        definition = _definition(graph, label="Group")
        node = _card(_graph_node(graph, definition.key))
        node.props.label = "Smoothing"

        reloaded = BaseGraph(filestem="reloaded", validation_scheduler=SyncScheduler())
        reloaded.load_from_dict(graph.to_dict(include_data=True))

        restored = reloaded.get_subgraph(definition.key)
        assert restored is not None
        assert restored.label == "Smoothing"
