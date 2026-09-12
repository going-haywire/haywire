"""Tests for ANY — the placeholder type resolved from a connected pin.

Covers the adapter short-circuit (every pairing involving ANY is a
pass-through), the config-port rejection, and the end-to-end resolve: an ANY
inlet adopts the connected outlet's type and grows a fresh slot.
"""

import pytest

from haywire.barn.builtin.types import ANY, BOOL, FLOAT, INT, STRING
from haywire.core.adapter.factory import AdapterFactory
from haywire.core.adapter.registry import AdapterRegistry
from haywire.core.adapter.base import ReturnAdapter
from haywire.core.edge.edge_wrapper import EdgeWrapper
from haywire.core.graph.base import BaseGraph
from haywire.core.node.node_wrapper import NodeWrapper
from haywire.core.types import DataPort
from haywire.core.types.enums import PortOrigin, PortType, ShowWidgetStrategy, StoreStrategy


@pytest.fixture
def factory() -> AdapterFactory:
    """An AdapterFactory over an empty registry.

    Empty on purpose: every pairing here must resolve without a registered
    adapter, so a hit could only come from the ANY short-circuit.
    """
    return AdapterFactory(AdapterRegistry())


class TestAnyTypeDeclaration:
    def test_any_is_flagged_and_other_types_are_not(self):
        assert ANY._is_any is True
        assert INT._is_any is False
        assert STRING._is_any is False

    def test_any_declares_no_widget(self):
        """An undecided pin has no value to edit, so it renders no widget."""
        assert not ANY.class_identity.widget_key

    def test_an_undecided_instance_constructs_and_serializes(self):
        """``PrimitiveType`` rejects None, which a placeholder has to hold."""
        assert ANY().to_dict() == {"value": None}
        assert ANY(value=None).to_dict() == {"value": None}
        assert ANY.create_field().to_dict() == {"value": None}

    def test_an_any_port_never_stores_its_value(self):
        """Nothing to save, so the port is not asked to serialize one."""
        assert ANY.class_identity.store_strategy is StoreStrategy.NEVER

    def test_config_port_is_rejected(self):
        """A config port has no pin, so an ANY config could never resolve."""
        with pytest.raises(ValueError, match="config port"):
            ANY.as_config("nope")

    @pytest.mark.parametrize("factory_name", ["as_inlet", "as_outlet"])
    def test_pin_carrying_port_types_are_allowed(self, factory_name):
        spec = getattr(ANY, factory_name)("slot")
        assert spec["kwargs"]["id"] == "slot"


def _bare_port(spec) -> DataPort:
    """Build a DataPort straight from *spec*, with no graph behind it.

    ``from_spec`` needs a type registry and a wrapper/node; these tests only
    read provenance off the finished port, so the kwargs are applied directly.
    """
    kwargs = dict(spec["kwargs"])
    kwargs.pop("flow_type", None)
    port_type = PortType(kwargs.pop("port_type"))
    if kwargs.pop("promoted", False):
        kwargs.setdefault("origin", PortOrigin.PROMOTED)
    if "show_widget" in kwargs:
        kwargs["show_widget"] = ShowWidgetStrategy(kwargs["show_widget"])
    if "store_strategy" in kwargs:
        kwargs["store_strategy"] = StoreStrategy(kwargs["store_strategy"])
    kwargs.setdefault("type_cls", INT)
    return DataPort(port_type=port_type, **kwargs)


class TestPortOrigin:
    """``promoted`` stays readable and writable on top of ``origin``."""

    def test_a_declared_port_is_not_promoted_and_not_removable(self):
        port = _bare_port(INT.as_inlet("declared"))
        assert port.origin is PortOrigin.DECLARED
        assert port.promoted is False
        assert not port.is_user_removable()

    def test_promoted_kwarg_still_sets_the_origin(self):
        port = _bare_port(INT.as_inlet("bag.field", promoted=True))
        assert port.origin is PortOrigin.PROMOTED
        assert port.promoted is True
        assert port.is_user_removable()

    def test_a_resolved_port_is_removable_but_not_promoted(self):
        port = _bare_port(INT.as_inlet("slot", origin=PortOrigin.RESOLVED))
        assert port.origin is PortOrigin.RESOLVED
        assert port.promoted is False
        assert port.is_user_removable()

    def test_setting_promoted_writes_through_to_origin(self):
        port = _bare_port(INT.as_inlet("declared"))
        port.promoted = True
        assert port.origin is PortOrigin.PROMOTED
        port.promoted = False
        assert port.origin is PortOrigin.DECLARED

    def test_origin_round_trips_through_to_dict(self):
        port = _bare_port(INT.as_inlet("slot", origin=PortOrigin.RESOLVED))
        assert port.to_dict()["kwargs"]["origin"] == "resolved"


class TestAnyAdapterShortCircuit:
    @pytest.mark.parametrize(
        ("source", "sink"),
        [
            (INT, ANY),
            (ANY, INT),
            (STRING, ANY),
            (ANY, STRING),
            (FLOAT, ANY),
            (BOOL, ANY),
        ],
    )
    def test_any_paired_with_a_concrete_type_passes_through(self, factory, source, sink):
        adapter, error = factory.create_chain(source, sink, "edge-1")
        assert error is None
        assert isinstance(adapter, ReturnAdapter)

    def test_any_to_any_passes_through(self):
        """Two undecided ends still make a valid edge; neither resolves."""
        factory = AdapterFactory(AdapterRegistry())
        adapter, error = factory.create_chain(ANY, ANY, "edge-1")
        assert error is None
        assert isinstance(adapter, ReturnAdapter)

    def test_compound_to_any_passes_through(self, factory):
        """The short-circuit runs before scalar/compound dispatch."""
        from haybale_core.types import ArrayType

        adapter, error = factory.create_chain(ArrayType[INT], ANY, "edge-1")
        assert error is None
        assert isinstance(adapter, ReturnAdapter)

    def test_unrelated_concrete_types_still_fail(self, factory):
        """The short-circuit must not make every edge valid."""
        adapter, error = factory.create_chain(STRING, INT, "edge-1")
        assert adapter is None
        assert error is not None


def _make_any_node(graph: BaseGraph, position: tuple[float, float]) -> NodeWrapper:
    from haybale_testing.nodes.testbed.any_port_test import AnyPortTestNode

    wrapper = graph.create_node_wrapper(AnyPortTestNode.class_identity.registry_key, position=position)
    assert wrapper is not None, f"node creation failed at {position}"
    return wrapper


def _make_link_node(graph: BaseGraph, position: tuple[float, float]) -> NodeWrapper:
    from haybale_testing.nodes.testbed.edge_link_test import EdgeLinkTestNode

    wrapper = graph.create_node_wrapper(EdgeLinkTestNode.class_identity.registry_key, position=position)
    assert wrapper is not None, f"node creation failed at {position}"
    return wrapper


@pytest.mark.integration
class TestAnyResolution:
    """End-to-end: an ANY pin adopts the type of what connects to it."""

    def test_any_inlet_adopts_connected_type_and_grows_a_new_slot(
        self, graph_with_library_system: BaseGraph, library_system
    ):
        graph = graph_with_library_system
        source = _make_link_node(graph, (100, 100))
        target = _make_any_node(graph, (300, 100))

        assert target.node.ports["any_in_0"].type_cls is ANY

        edge = graph.create_edge_wrapper(source.node_id, "int_outlet", target.node_id, "any_in_0")
        assert edge is not None

        resolved = target.node.ports["any_in_0"]
        assert resolved.type_cls is not None
        assert resolved.type_cls is not ANY
        assert resolved.type_cls.class_identity.registry_key.endswith("TEST_INT")
        # A fresh undecided slot is appended below the one just resolved.
        assert target.node.ports["any_in_1"].type_cls is ANY

    def test_any_outlet_adopts_connected_type_and_grows_a_new_slot(
        self, graph_with_library_system: BaseGraph, library_system
    ):
        """An outlet resolves from the inlet it feeds, mirroring the inlet side."""
        graph = graph_with_library_system
        source = _make_any_node(graph, (100, 100))
        sink = _make_link_node(graph, (300, 100))

        assert source.node.ports["any_out_0"].type_cls is ANY

        edge = graph.create_edge_wrapper(source.node_id, "any_out_0", sink.node_id, "float_inlet")
        assert edge is not None

        resolved = source.node.ports["any_out_0"]
        assert resolved.type_cls is not None
        assert resolved.type_cls is not ANY
        assert resolved.type_cls.class_identity.registry_key.endswith("TEST_FLOAT")
        assert source.node.ports["any_out_1"].type_cls is ANY

    def test_resolved_edge_is_valid(self, graph_with_library_system: BaseGraph, library_system):
        """The edge survives the port swap and rebuilds against the new type."""
        graph = graph_with_library_system
        source = _make_link_node(graph, (100, 100))
        target = _make_any_node(graph, (300, 100))

        edge = graph.create_edge_wrapper(source.node_id, "int_outlet", target.node_id, "any_in_0")
        assert edge is not None
        graph._validation.force_immediate_validation()

        assert edge.is_functional()

    def test_any_to_any_leaves_both_ends_undecided(
        self, graph_with_library_system: BaseGraph, library_system
    ):
        """Neither end has a type to adopt, so no port is retyped or added."""
        graph = graph_with_library_system
        source = _make_any_node(graph, (100, 100))
        target = _make_any_node(graph, (300, 100))

        edge: EdgeWrapper | None = graph.create_edge_wrapper(
            source.node_id, "any_out_0", target.node_id, "any_in_0"
        )
        assert edge is not None

        assert target.node.ports["any_in_0"].type_cls is ANY
        assert source.node.ports["any_out_0"].type_cls is ANY
        assert "any_in_1" not in target.node.ports
        assert "any_out_1" not in source.node.ports


@pytest.mark.integration
class TestAnyPersistence:
    """A resolved slot outlives the edge that made it, and can be reconnected."""

    def test_the_resolved_slot_survives_edge_removal(
        self, graph_with_library_system: BaseGraph, library_system
    ):
        graph = graph_with_library_system
        source = _make_link_node(graph, (100, 100))
        target = _make_any_node(graph, (300, 100))

        edge = graph.create_edge_wrapper(source.node_id, "int_outlet", target.node_id, "any_in_0")
        assert edge is not None

        graph.remove_edge_wrapper(edge.edge_id)

        # The typed slot stays, now empty, and the trailing ANY stays with it.
        resolved = target.node.ports["any_in_0"]
        assert resolved.type_cls is not None
        assert resolved.type_cls.class_identity.registry_key.endswith("TEST_INT")
        assert target.node.ports["any_in_1"].type_cls is ANY

    def test_a_released_slot_can_be_reconnected(self, graph_with_library_system: BaseGraph, library_system):
        """Reconnecting to an emptied slot links, without needing a second attempt."""
        graph = graph_with_library_system
        source = _make_link_node(graph, (100, 100))
        target = _make_any_node(graph, (300, 100))

        first = graph.create_edge_wrapper(source.node_id, "int_outlet", target.node_id, "any_in_0")
        assert first is not None
        graph.remove_edge_wrapper(first.edge_id)

        again = graph.create_edge_wrapper(source.node_id, "int_outlet", target.node_id, "any_in_0")
        assert again is not None
        graph._validation.force_immediate_validation()

        assert again.is_functional()
        assert again.state.is_linked

    def test_indices_are_never_reused_so_edges_keep_their_ports(
        self, graph_with_library_system: BaseGraph, library_system
    ):
        """A surviving edge still points at its own port after another is freed.

        An edge id is derived from the port id, so a renumbering scheme would
        silently unlink the edges it moved.
        """
        graph = graph_with_library_system
        source = _make_link_node(graph, (100, 100))
        target = _make_any_node(graph, (300, 100))

        first = graph.create_edge_wrapper(source.node_id, "int_outlet", target.node_id, "any_in_0")
        second = graph.create_edge_wrapper(source.node_id, "string_outlet", target.node_id, "any_in_1")
        assert first is not None
        assert second is not None

        graph.remove_edge_wrapper(first.edge_id)
        graph._validation.force_immediate_validation()

        # The STRING slot keeps its id, so its edge is still linked.
        assert second.state.is_linked
        assert target.node.ports["any_in_1"].type_cls is not ANY
        assert target.node.ports["any_in_2"].type_cls is ANY

    def test_a_resolved_port_is_user_removable(self, graph_with_library_system: BaseGraph, library_system):
        """The pin the user created is the one the user may delete."""
        graph = graph_with_library_system
        source = _make_link_node(graph, (100, 100))
        target = _make_any_node(graph, (300, 100))

        graph.create_edge_wrapper(source.node_id, "int_outlet", target.node_id, "any_in_0")

        assert target.node.ports["any_in_0"].is_user_removable()
        # The undecided slot is author-declared, so it stays.
        assert not target.node.ports["any_in_1"].is_user_removable()

    def test_remove_port_drops_a_resolved_pin_and_its_edge(
        self, graph_with_library_system: BaseGraph, library_system
    ):
        """The pin-menu verb, on the pin the user created."""
        from haywire.core.node.promotion import remove_port

        graph = graph_with_library_system
        source = _make_link_node(graph, (100, 100))
        target = _make_any_node(graph, (300, 100))

        edge = graph.create_edge_wrapper(source.node_id, "int_outlet", target.node_id, "any_in_0")
        assert edge is not None

        assert remove_port(target.node, "any_in_0") is True

        assert "any_in_0" not in target.node.ports
        assert not edge.state.is_linked

    def test_removing_an_edge_through_an_action_succeeds(
        self, graph_with_library_system: BaseGraph, library_system
    ):
        """Every callback an ANY slot names must exist on the node.

        A port naming a method the node does not define raises from inside
        ``_trigger_callback``, which surfaces as a failed undo action rather
        than anything pointing at the port.
        """
        from haywire.core.undo.actions.graph_actions import RemoveElementsAction

        graph = graph_with_library_system
        source = _make_link_node(graph, (100, 100))
        target = _make_any_node(graph, (300, 100))

        edge = graph.create_edge_wrapper(source.node_id, "int_outlet", target.node_id, "any_in_0")
        assert edge is not None

        action = RemoveElementsAction(graph=graph, edges=[edge.edge_id])
        action.execute()

        assert graph.get_edge_wrapper(edge.edge_id) is None

    def test_a_node_with_any_pins_can_be_serialized(
        self, graph_with_library_system: BaseGraph, library_system
    ):
        """The copy path, which serializes with ``include_data=True``.

        An unresolved pin has no value, and building one to write it out is
        what used to raise from inside ``PrimitiveField.to_dict``.
        """
        graph = graph_with_library_system
        source = _make_link_node(graph, (100, 100))
        target = _make_any_node(graph, (300, 100))

        # Both an untouched node and one carrying a resolved slot.
        assert target.serialize(include_data=True)["node_data"]["ports"]

        graph.create_edge_wrapper(source.node_id, "int_outlet", target.node_id, "any_in_0")
        ports = target.serialize(include_data=True)["node_data"]["ports"]

        assert "any_in_0" in ports
        assert "any_in_1" in ports

    def test_remove_port_refuses_a_declared_pin(self, graph_with_library_system: BaseGraph, library_system):
        """An author-declared port is part of what the node is."""
        from haywire.core.node.promotion import remove_port

        graph = graph_with_library_system
        target = _make_any_node(graph, (300, 100))

        assert remove_port(target.node, "any_in_0") is False
        assert "any_in_0" in target.node.ports

    def test_remove_port_is_a_no_op_for_an_unknown_pin(
        self, graph_with_library_system: BaseGraph, library_system
    ):
        from haywire.core.node.promotion import remove_port

        graph = graph_with_library_system
        target = _make_any_node(graph, (300, 100))

        assert remove_port(target.node, "nope") is False

    def test_the_trailing_any_slot_is_always_present(
        self, graph_with_library_system: BaseGraph, library_system
    ):
        """A node with nothing connected still offers one undecided pin per side."""
        graph = graph_with_library_system
        target = _make_any_node(graph, (300, 100))

        assert target.node.ports["any_in_0"].type_cls is ANY
        assert target.node.ports["any_out_0"].type_cls is ANY
