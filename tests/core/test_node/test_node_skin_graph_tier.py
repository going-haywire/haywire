"""framework < graph < node skin chain on real nodes."""

import pytest

from haywire.core.di.context import get_settings_registry
from haywire.core.graph.base import BaseGraph

SKIN_KEY = "ui.node.default.skin.studio_skin"


def _add_node(graph_obj: BaseGraph):
    from haybale_testing.nodes.testbed.print_node import TestPrintNode

    return graph_obj.create_node_wrapper(TestPrintNode.class_identity.registry_key, position=(100, 100))


@pytest.mark.integration
class TestNodeSkinGraphTier:
    def test_unset_node_tracks_graph_default(self, graph_with_library_system):
        graph_obj = graph_with_library_system
        wrapper = _add_node(graph_obj)
        graph_obj.props.default_skin = "skin-graph"
        assert wrapper.node.props.skin == "skin-graph"

    def test_node_override_wins_and_resets_fall_one_tier(self, graph_with_library_system):
        graph_obj = graph_with_library_system
        registry = get_settings_registry()
        wrapper = _add_node(graph_obj)

        registry.set_global(SKIN_KEY, "skin-fw")
        graph_obj.props.default_skin = "skin-graph"
        wrapper.node.props.skin = "skin-node"
        assert wrapper.node.props.skin == "skin-node"

        wrapper.node.props.reset("skin")
        assert wrapper.node.props.skin == "skin-graph"  # node → graph
        graph_obj.props.reset("default_skin")
        assert wrapper.node.props.skin == "skin-fw"  # graph → framework

    def test_round_trip_preserves_all_three_tiers(self, graph_with_library_system, library_system):
        graph_obj = graph_with_library_system
        w1 = _add_node(graph_obj)
        _add_node(graph_obj)  # w2: left tracking, only inspected after round-trip below
        graph_obj.props.default_skin = "skin-graph"
        w1.node.props.skin = "skin-node"  # w1 overridden, w2 tracking
        data = graph_obj.to_dict()

        g2 = BaseGraph(graph_id="g2", name="G2")
        assert g2.load_from_dict(data) is True
        loaded = list(g2.node_wrappers.values())
        overridden = [w for w in loaded if w.node.props.is_locally_set("skin")]
        tracking = [w for w in loaded if not w.node.props.is_locally_set("skin")]
        assert len(overridden) == 1
        assert overridden[0].node.props.skin == "skin-node"
        assert len(tracking) == 1
        assert tracking[0].node.props.skin == "skin-graph"

    def test_pre_feature_graph_without_props_block_loads(self, graph_with_library_system):
        graph_obj = graph_with_library_system
        _add_node(graph_obj)
        data = graph_obj.to_dict()
        del data["props"]  # simulate old file
        g2 = BaseGraph(graph_id="g2", name="G2")
        assert g2.load_from_dict(data) is True
        assert not g2.props.is_locally_set("default_skin")
        assert len(g2.node_wrappers) == 1

    def test_skin_promotion_still_works(self, graph_with_library_system):
        from haywire.core.types.enums import PortType

        graph_obj = graph_with_library_system
        wrapper = _add_node(graph_obj)
        wrapper.node.props.promote("skin", PortType.INLET)
        assert wrapper.node.props.is_promoted("skin")
        wrapper.node.props.demote("skin")
        assert not wrapper.node.props.is_promoted("skin")
