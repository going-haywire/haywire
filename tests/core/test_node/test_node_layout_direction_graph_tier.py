"""framework < graph < node layout_direction chain on real nodes.

Modelled on test_node_skin_graph_tier.py — layout_direction rides the exact
same shadow()/graph() machinery, so the tier behaviour must match field for
field.
"""

import pytest

from haywire.core.di.context import get_settings_registry
from haywire.core.graph.base import BaseGraph
from haywire.core.types import LayoutDirection

LAYOUT_KEY = "ui.node.default.skin.studio_layout_direction"

L2R = LayoutDirection.LEFT_TO_RIGHT.value
R2L = LayoutDirection.RIGHT_TO_LEFT.value
T2B = LayoutDirection.TOP_TO_BOTTOM.value
B2T = LayoutDirection.BOTTOM_TO_TOP.value


def _add_node(graph_obj: BaseGraph):
    from haybale_testing.nodes.testbed.print_node import TestPrintNode

    return graph_obj.create_node_wrapper(TestPrintNode.class_identity.registry_key, position=(100, 100))


@pytest.fixture(autouse=True)
def _clean_framework_tier(library_system):
    """Clear the framework-tier value around every test in this module.

    The settings registry is process-shared, so a `set_global` in one test
    otherwise leaks into the next and any test asserting the framework DEFAULT
    silently becomes order-dependent.
    """
    registry = get_settings_registry()
    registry.reset_global(LAYOUT_KEY)
    yield
    registry.reset_global(LAYOUT_KEY)


@pytest.mark.integration
class TestNodeLayoutDirectionGraphTier:
    def test_defaults_to_left_to_right(self, graph_with_library_system):
        """The pre-feature layout stays the default at every tier."""
        graph_obj = graph_with_library_system
        wrapper = _add_node(graph_obj)
        assert wrapper.node.props.layout_direction == L2R

    def test_unset_node_tracks_graph_default(self, graph_with_library_system):
        graph_obj = graph_with_library_system
        wrapper = _add_node(graph_obj)
        graph_obj.props.layout_direction = T2B
        assert wrapper.node.props.layout_direction == T2B

    def test_node_override_wins_and_resets_fall_one_tier(self, graph_with_library_system):
        graph_obj = graph_with_library_system
        registry = get_settings_registry()
        wrapper = _add_node(graph_obj)

        registry.set_global(LAYOUT_KEY, R2L)
        graph_obj.props.layout_direction = T2B
        wrapper.node.props.layout_direction = B2T
        assert wrapper.node.props.layout_direction == B2T

        wrapper.node.props.reset("layout_direction")
        assert wrapper.node.props.layout_direction == T2B  # node → graph
        graph_obj.props.reset("layout_direction")
        assert wrapper.node.props.layout_direction == R2L  # graph → framework

    def test_round_trip_preserves_all_three_tiers(self, graph_with_library_system, library_system):
        graph_obj = graph_with_library_system
        w1 = _add_node(graph_obj)
        _add_node(graph_obj)  # w2: left tracking, only inspected after round-trip below
        graph_obj.props.layout_direction = T2B
        w1.node.props.layout_direction = B2T  # w1 overridden, w2 tracking
        data = graph_obj.to_dict()

        g2 = BaseGraph(filestem="G2")
        assert g2.load_from_dict(data) is True
        loaded = list(g2.node_wrappers.values())
        overridden = [w for w in loaded if w.node.props.is_locally_set("layout_direction")]
        tracking = [w for w in loaded if not w.node.props.is_locally_set("layout_direction")]
        assert len(overridden) == 1
        assert overridden[0].node.props.layout_direction == B2T
        assert len(tracking) == 1
        assert tracking[0].node.props.layout_direction == T2B

    def test_pre_feature_graph_without_layout_direction_loads(self, graph_with_library_system):
        """A graph saved before this feature has no key and must default cleanly."""
        graph_obj = graph_with_library_system
        _add_node(graph_obj)
        data = graph_obj.to_dict()
        data["props"].pop("layout_direction", None)
        for node_data in data.get("nodes", {}).values():
            if isinstance(node_data, dict):
                node_data.get("props", {}).pop("layout_direction", None)

        g2 = BaseGraph(filestem="G2")
        assert g2.load_from_dict(data) is True
        assert not g2.props.is_locally_set("layout_direction")
        assert len(g2.node_wrappers) == 1
        wrapper = next(iter(g2.node_wrappers.values()))
        assert wrapper.node.props.layout_direction == L2R

    def test_layout_direction_is_a_redraw_field(self):
        """Without this entry no tier change ever reaches the canvas."""
        from haywire.core.node.properties import NodeProperties

        assert "layout_direction" in NodeProperties.REDRAW_FIELDS

    def test_graph_tier_change_reaches_a_tracking_node(self, graph_with_library_system):
        """The mirror must actually fire, not just resolve on next read."""
        graph_obj = graph_with_library_system
        wrapper = _add_node(graph_obj)

        seen = []
        wrapper.node.props.subscribe_field("layout_direction", lambda v, o: seen.append(v))
        graph_obj.props.layout_direction = T2B

        assert seen, "graph-tier write did not fire the node's field subscription"
        assert seen[-1] == T2B


@pytest.mark.integration
class TestLayoutDirectionResolution:
    def test_resolver_returns_enum_for_each_tier_value(self, graph_with_library_system):
        from haywire.ui.skin.pin_render import resolve_layout_direction

        graph_obj = graph_with_library_system
        wrapper = _add_node(graph_obj)
        wrapper.node.props.layout_direction = T2B
        assert resolve_layout_direction(wrapper) is LayoutDirection.TOP_TO_BOTTOM

    def test_graph_resolver_ignores_node_override(self, graph_with_library_system):
        """Reroute skins follow the wire, not the node sitting on it."""
        from haywire.ui.skin.pin_render import (
            resolve_graph_layout_direction,
            resolve_layout_direction,
        )

        graph_obj = graph_with_library_system
        wrapper = _add_node(graph_obj)
        graph_obj.props.layout_direction = T2B
        wrapper.node.props.layout_direction = R2L

        assert resolve_layout_direction(wrapper) is LayoutDirection.RIGHT_TO_LEFT
        assert resolve_graph_layout_direction(wrapper) is LayoutDirection.TOP_TO_BOTTOM

    def test_corrupt_stored_value_degrades_to_l2r(self, graph_with_library_system):
        from haywire.ui.skin.pin_render import resolve_layout_direction

        graph_obj = graph_with_library_system
        wrapper = _add_node(graph_obj)
        wrapper.node.props.layout_direction = "sideways"
        assert resolve_layout_direction(wrapper) is LayoutDirection.LEFT_TO_RIGHT
