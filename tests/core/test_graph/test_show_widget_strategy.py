"""
Tests for ShowWidgetStrategy — per-port widget visibility vs. link state.

Covers (see ADR 0003):
- Per-direction defaults injected by as_inlet/as_outlet/as_config.
- should_show_widget() resolution for all four strategies against link state.
- The dynamic behavior: an inlet's widget hides once an edge is linked.
- Serialization round-trip (to_dict → from_spec) preserves the enum.
"""

import pytest

from haywire.core.graph.base import BaseGraph
from haywire.core.types.enums import ShowWidgetStrategy

from tests.conftest import make_edge, make_node


def _create_two_nodes(graph: BaseGraph):
    from haybale_testing.nodes.testbed.edge_link_test import EdgeLinkTestNode

    key = EdgeLinkTestNode.class_identity.registry_key
    node_a = make_node(graph, key, position=(100, 100))
    node_b = make_node(graph, key, position=(300, 100))
    return node_a, node_b


@pytest.mark.integration
class TestShowWidgetStrategyDefaults:
    """Per-direction defaults applied by the as_* factory methods."""

    def test_inlet_defaults_to_not_linked(self, graph_with_library_system: BaseGraph, library_system):
        node_a, _ = _create_two_nodes(graph_with_library_system)
        port = node_a.node.ports["bool_inlet"]
        assert port.show_widget == ShowWidgetStrategy.NOT_LINKED

    def test_outlet_defaults_to_never(self, graph_with_library_system: BaseGraph, library_system):
        node_a, _ = _create_two_nodes(graph_with_library_system)
        port = node_a.node.ports["bool_outlet"]
        assert port.show_widget == ShowWidgetStrategy.NEVER


@pytest.mark.integration
class TestShouldShowWidgetResolution:
    """should_show_widget() resolves the strategy against live link state."""

    def test_not_linked_shows_only_when_unlinked(self, graph_with_library_system: BaseGraph, library_system):
        graph = graph_with_library_system
        node_a, node_b = _create_two_nodes(graph)
        inlet = node_b.node.ports["bool_inlet"]
        inlet.show_widget = ShowWidgetStrategy.NOT_LINKED

        # Unlinked → widget shows.
        assert not inlet.is_linked()
        assert inlet.should_show_widget() is True

        # Link an edge → widget hides.
        make_edge(graph, node_a.node_id, "bool_outlet", node_b.node_id, "bool_inlet")
        assert inlet.is_linked()
        assert inlet.should_show_widget() is False

    def test_when_linked_shows_only_when_linked(self, graph_with_library_system: BaseGraph, library_system):
        graph = graph_with_library_system
        node_a, node_b = _create_two_nodes(graph)
        inlet = node_b.node.ports["bool_inlet"]
        inlet.show_widget = ShowWidgetStrategy.WHEN_LINKED

        assert inlet.should_show_widget() is False
        make_edge(graph, node_a.node_id, "bool_outlet", node_b.node_id, "bool_inlet")
        assert inlet.should_show_widget() is True

    def test_always_and_never_ignore_link_state(self, graph_with_library_system: BaseGraph, library_system):
        graph = graph_with_library_system
        node_a, node_b = _create_two_nodes(graph)
        inlet = node_b.node.ports["bool_inlet"]

        inlet.show_widget = ShowWidgetStrategy.ALWAYS
        assert inlet.should_show_widget() is True
        inlet.show_widget = ShowWidgetStrategy.NEVER
        assert inlet.should_show_widget() is False

        # Linking does not change either verdict.
        make_edge(graph, node_a.node_id, "bool_outlet", node_b.node_id, "bool_inlet")
        inlet.show_widget = ShowWidgetStrategy.ALWAYS
        assert inlet.should_show_widget() is True
        inlet.show_widget = ShowWidgetStrategy.NEVER
        assert inlet.should_show_widget() is False


@pytest.mark.integration
class TestShowWidgetStrategySerialization:
    """The enum survives a to_dict → from_spec round-trip."""

    def test_override_round_trips(self, graph_with_library_system: BaseGraph, library_system):
        from haywire.core.types.port import DataPort

        node_a, _ = _create_two_nodes(graph_with_library_system)
        inlet = node_a.node.ports["bool_inlet"]
        inlet.show_widget = ShowWidgetStrategy.WHEN_LINKED

        spec = inlet.to_dict()
        # Serialized as the enum's string value.
        assert spec["kwargs"]["show_widget"] == "when_linked"

        rebuilt = DataPort.from_spec(
            spec,
            type_registry=node_a.node._type_registry,
            wrapper=node_a,
            node=node_a.node,
        )
        assert rebuilt.show_widget == ShowWidgetStrategy.WHEN_LINKED


@pytest.mark.integration
class TestLinkChangeRequestsEndpointRedraw:
    """
    Linking/unlinking marks both endpoint nodes for redraw, so widget visibility
    re-resolves in the UI. The redraw is emitted by EdgeWrapper through the
    validator's dirty-mark pipeline. See ADR 0003.
    """

    def test_connecting_marks_both_endpoints_redraw(
        self, graph_with_library_system: BaseGraph, library_system
    ):
        from haywire.core.graph.types import ChangeReason

        graph = graph_with_library_system
        node_a, node_b = _create_two_nodes(graph)

        # Capture every node reason the validator emits from this point on.
        seen: dict[str, ChangeReason] = {}

        def capture(result):
            seen.update(result.nodes)

        graph._validation.subscribe(capture)
        try:
            make_edge(graph, node_a.node_id, "bool_outlet", node_b.node_id, "bool_inlet")
        finally:
            graph._validation.unsubscribe(capture)

        # Both endpoints were marked for redraw as a result of the link.
        assert seen.get(node_a.node_id) == ChangeReason.NODE_REDRAW_REQUESTED
        assert seen.get(node_b.node_id) == ChangeReason.NODE_REDRAW_REQUESTED

    def test_disconnecting_marks_both_endpoints_redraw(
        self, graph_with_library_system: BaseGraph, library_system
    ):
        from haywire.core.graph.types import ChangeReason

        graph = graph_with_library_system
        node_a, node_b = _create_two_nodes(graph)
        edge = make_edge(graph, node_a.node_id, "bool_outlet", node_b.node_id, "bool_inlet")

        seen: dict[str, ChangeReason] = {}

        def capture(result):
            seen.update(result.nodes)

        graph._validation.subscribe(capture)
        try:
            graph.remove_edge_wrapper(edge.edge_id)
        finally:
            graph._validation.unsubscribe(capture)

        # detach() runs during removal and requests the endpoint redraw; the node
        # ids survive detach, so both endpoints are still reachable.
        assert seen.get(node_a.node_id) == ChangeReason.NODE_REDRAW_REQUESTED
        assert seen.get(node_b.node_id) == ChangeReason.NODE_REDRAW_REQUESTED

    def test_redraw_does_not_downgrade_stronger_reason(
        self, graph_with_library_system: BaseGraph, library_system
    ):
        """
        The endpoint redraw goes through mark_node_dirty → _set_reason, which is
        priority-respecting: a stronger reason already pending for a node (e.g.
        NODE_ADDED on paste, NODE_REMOVED on clear) is NOT downgraded to
        NODE_REDRAW_REQUESTED. This guarantees the redraw is safe to emit during a
        batch that also adds or removes the same node.
        """
        from haywire.core.graph.types import ChangeReason

        validation = graph_with_library_system._validation
        store: dict = {}

        # Stronger reasons must win regardless of mark order.
        validation._set_reason("n1", ChangeReason.NODE_ADDED, store)
        validation._set_reason("n1", ChangeReason.NODE_REDRAW_REQUESTED, store)
        assert store["n1"] == ChangeReason.NODE_ADDED

        validation._set_reason("n2", ChangeReason.NODE_REDRAW_REQUESTED, store)
        validation._set_reason("n2", ChangeReason.NODE_REMOVED, store)
        assert store["n2"] == ChangeReason.NODE_REMOVED

        # NODE_REDRAW_REQUESTED is the lowest-priority of the three.
        assert not ChangeReason.NODE_REDRAW_REQUESTED.has_higher_priority_than(ChangeReason.NODE_ADDED)
        assert not ChangeReason.NODE_REDRAW_REQUESTED.has_higher_priority_than(ChangeReason.NODE_REMOVED)
