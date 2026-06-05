"""
Tests for ShowWidgetStrategy — per-port widget visibility vs. link state.

Covers (see ADR 0003):
- Per-direction defaults injected by as_inlet/as_outlet/as_config.
- should_show_widget() resolution for all four strategies against link state.
- The dynamic behavior: an inlet's widget hides once an edge is linked.
- Serialization round-trip (to_dict → from_spec) preserves the enum.
"""

# editor import first to avoid circular import (see CLAUDE.md / test conventions)
import haywire.core.graph.editor  # noqa: F401

import pytest

from haywire.core.graph.base import BaseGraph
from haywire.core.types.enums import ShowWidgetStrategy


def _create_two_nodes(graph: BaseGraph):
    from haybale_testing.nodes.testbed.edge_link_test import EdgeLinkTestNode

    key = EdgeLinkTestNode.class_identity.registry_key
    node_a = graph.create_node_wrapper(key, position=(100, 100))
    node_b = graph.create_node_wrapper(key, position=(300, 100))
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
        graph.create_edge_wrapper(node_a.node_id, "bool_outlet", node_b.node_id, "bool_inlet")
        assert inlet.is_linked()
        assert inlet.should_show_widget() is False

    def test_when_linked_shows_only_when_linked(self, graph_with_library_system: BaseGraph, library_system):
        graph = graph_with_library_system
        node_a, node_b = _create_two_nodes(graph)
        inlet = node_b.node.ports["bool_inlet"]
        inlet.show_widget = ShowWidgetStrategy.WHEN_LINKED

        assert inlet.should_show_widget() is False
        graph.create_edge_wrapper(node_a.node_id, "bool_outlet", node_b.node_id, "bool_inlet")
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
        graph.create_edge_wrapper(node_a.node_id, "bool_outlet", node_b.node_id, "bool_inlet")
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
