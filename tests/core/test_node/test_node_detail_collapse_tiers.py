"""The two ADR-0032 card axes on real nodes: NodeDetail and Node collapse.

Modelled on test_node_layout_direction_graph_tier.py — `detail` rides the exact
same shadow()/graph() machinery, so its tier behaviour must match field for
field. `collapsed` deliberately does NOT: it is a two-tier field (graph < node)
with no framework counterpart, and the asymmetry is the thing most likely to be
"fixed" by someone who notices it, so it is asserted here explicitly.
"""

import pytest

from haywire.core.di.context import get_settings_registry
from haywire.core.graph.base import BaseGraph
from haywire.core.types import NodeDetail

DETAIL_KEY = "ui.node.default.skin.studio_node_detail"

COMPACT = NodeDetail.COMPACT.value
STANDARD = NodeDetail.STANDARD.value
FULL = NodeDetail.FULL.value


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
    registry.reset_global(DETAIL_KEY)
    yield
    registry.reset_global(DETAIL_KEY)


@pytest.mark.unit
class TestNodeDetailEnum:
    def test_ranks_are_cumulative_and_ordered(self):
        assert NodeDetail.COMPACT.rank < NodeDetail.STANDARD.rank < NodeDetail.FULL.rank

    def test_includes_is_reflexive_and_directional(self):
        assert NodeDetail.STANDARD.includes(NodeDetail.STANDARD)
        assert NodeDetail.FULL.includes(NodeDetail.COMPACT)
        assert not NodeDetail.COMPACT.includes(NodeDetail.STANDARD)

    def test_wire_value_is_the_string(self):
        """StrEnum, not IntEnum: saved graphs hold names, so adding a rank
        later renumbers nothing. See ADR 0032."""
        assert NodeDetail.FULL == "full"
        assert isinstance(NodeDetail.FULL, str)

    @pytest.mark.parametrize("bad", ["sideways", "", None, 7, object()])
    def test_coerce_degrades_upward_to_full(self, bad):
        """Degrading UP is deliberate: a card drawing too much costs
        performance, one drawing too little looks broken."""
        assert NodeDetail.coerce(bad) is NodeDetail.FULL

    def test_coerce_passes_through_members_and_valid_strings(self):
        assert NodeDetail.coerce(NodeDetail.COMPACT) is NodeDetail.COMPACT
        assert NodeDetail.coerce("standard") is NodeDetail.STANDARD

    def test_every_member_has_a_label(self):
        """The label feeds the CHOICES widget — a missing one is a KeyError in
        a settings panel, not at import."""
        assert all(d.label for d in NodeDetail)


@pytest.mark.integration
class TestNodeDetailGraphTier:
    def test_defaults_to_full(self, graph_with_library_system):
        """The most legible card is the default at every tier (ADR 0032)."""
        wrapper = _add_node(graph_with_library_system)
        assert wrapper.node.props.detail == FULL

    def test_unset_node_tracks_graph_default(self, graph_with_library_system):
        graph_obj = graph_with_library_system
        wrapper = _add_node(graph_obj)
        graph_obj.props.detail = COMPACT
        assert wrapper.node.props.detail == COMPACT

    def test_node_override_wins_and_resets_fall_one_tier(self, graph_with_library_system):
        graph_obj = graph_with_library_system
        registry = get_settings_registry()
        wrapper = _add_node(graph_obj)

        registry.set_global(DETAIL_KEY, COMPACT)
        graph_obj.props.detail = STANDARD
        wrapper.node.props.detail = FULL
        assert wrapper.node.props.detail == FULL

        wrapper.node.props.reset("detail")
        assert wrapper.node.props.detail == STANDARD  # node → graph
        graph_obj.props.reset("detail")
        assert wrapper.node.props.detail == COMPACT  # graph → framework

    def test_round_trip_preserves_all_three_tiers(self, graph_with_library_system, library_system):
        graph_obj = graph_with_library_system
        w1 = _add_node(graph_obj)
        _add_node(graph_obj)  # w2: left tracking, only inspected after round-trip below
        graph_obj.props.detail = STANDARD
        w1.node.props.detail = COMPACT  # w1 overridden, w2 tracking
        data = graph_obj.to_dict()

        g2 = BaseGraph(filestem="G2")
        assert g2.load_from_dict(data) is True
        loaded = list(g2.node_wrappers.values())
        overridden = [w for w in loaded if w.node.props.is_locally_set("detail")]
        tracking = [w for w in loaded if not w.node.props.is_locally_set("detail")]
        assert len(overridden) == 1
        assert overridden[0].node.props.detail == COMPACT
        assert len(tracking) == 1
        assert tracking[0].node.props.detail == STANDARD

    def test_pre_feature_graph_without_detail_loads(self, graph_with_library_system):
        """A graph saved before ADR 0032 has no key and must default cleanly."""
        graph_obj = graph_with_library_system
        _add_node(graph_obj)
        data = graph_obj.to_dict()
        data["props"].pop("detail", None)
        for node_data in data.get("nodes", {}).values():
            if isinstance(node_data, dict):
                node_data.get("props", {}).pop("detail", None)

        g2 = BaseGraph(filestem="G2")
        assert g2.load_from_dict(data) is True
        assert not g2.props.is_locally_set("detail")
        wrapper = next(iter(g2.node_wrappers.values()))
        assert wrapper.node.props.detail == FULL

    def test_graph_tier_change_reaches_a_tracking_node(self, graph_with_library_system):
        """The mirror must actually fire, not just resolve on next read."""
        graph_obj = graph_with_library_system
        wrapper = _add_node(graph_obj)

        seen = []
        wrapper.node.props.subscribe_field("detail", lambda v, o: seen.append(v))
        graph_obj.props.detail = COMPACT

        assert seen, "graph-tier write did not fire the node's field subscription"
        assert seen[-1] == COMPACT


@pytest.mark.integration
class TestNodeCollapseGraphTier:
    def test_defaults_to_expanded(self, graph_with_library_system):
        wrapper = _add_node(graph_with_library_system)
        assert wrapper.node.props.collapsed is False

    def test_unset_node_tracks_graph_default(self, graph_with_library_system):
        """This is the whole point of the graph tier: one write folds a large
        graph without touching any node."""
        graph_obj = graph_with_library_system
        wrapper = _add_node(graph_obj)
        graph_obj.props.collapsed = True
        assert wrapper.node.props.collapsed is True

    def test_hand_folded_node_ignores_the_graph_tier(self, graph_with_library_system):
        """ "unset tracks, set ignores" — a node the user has touched keeps its
        own answer, and `reset` is what hands authority back to the graph.

        The fold-then-unfold round trip is how a user actually produces a local
        "no": see :meth:`test_writing_the_resolved_value_does_not_pin`.
        """
        graph_obj = graph_with_library_system
        wrapper = _add_node(graph_obj)

        wrapper.node.props.collapsed = True
        wrapper.node.props.collapsed = False
        assert wrapper.node.props.is_locally_set("collapsed")

        graph_obj.props.collapsed = True
        assert wrapper.node.props.collapsed is False

        wrapper.node.props.reset("collapsed")
        assert wrapper.node.props.collapsed is True

    def test_writing_the_resolved_value_does_not_pin(self, graph_with_library_system):
        """`__set__` short-circuits on equality, so writing the value a field
        already resolves to leaves it TRACKING.

        Consequence for the toolbar: a toggle that re-asserts the current state
        (on redraw, say) does not silently pin every node it touches and
        neuter the graph tier. Clicking "unfold" on an already-unfolded node is
        likewise a no-op, not an opinion.
        """
        graph_obj = graph_with_library_system
        wrapper = _add_node(graph_obj)

        wrapper.node.props.collapsed = False  # already False from the graph
        assert not wrapper.node.props.is_locally_set("collapsed")

        graph_obj.props.collapsed = True
        assert wrapper.node.props.collapsed is True

    def test_has_no_framework_tier(self):
        """Two tiers by design (ADR 0032): a studio-wide fold would open every
        graph showing nothing. Delete this test only by amending that ADR."""
        from haywire.core.skin.settings import NodeDefaultSkinSettings

        assert not any("collaps" in name for name in NodeDefaultSkinSettings._property_settings()), (
            "collapse gained a framework tier; ADR 0032 says graph < node only"
        )

    def test_round_trip_preserves_both_tiers(self, graph_with_library_system, library_system):
        graph_obj = graph_with_library_system
        w1 = _add_node(graph_obj)
        _add_node(graph_obj)  # w2: left tracking
        graph_obj.props.collapsed = True
        w1.node.props.collapsed = False  # w1 overridden, w2 tracking
        data = graph_obj.to_dict()

        g2 = BaseGraph(filestem="G2")
        assert g2.load_from_dict(data) is True
        assert g2.props.collapsed is True
        loaded = list(g2.node_wrappers.values())
        overridden = [w for w in loaded if w.node.props.is_locally_set("collapsed")]
        tracking = [w for w in loaded if not w.node.props.is_locally_set("collapsed")]
        assert len(overridden) == 1
        assert overridden[0].node.props.collapsed is False
        assert len(tracking) == 1
        assert tracking[0].node.props.collapsed is True


@pytest.mark.unit
class TestBothAxesRedraw:
    @pytest.mark.parametrize("field", ["collapsed", "detail"])
    def test_axis_is_a_redraw_field(self, field):
        """Both are CONSTRUCTION gates, so a change must rebuild the card.
        Without the entry no tier change ever reaches the canvas."""
        from haywire.core.node.properties import NodeProperties

        assert field in NodeProperties.REDRAW_FIELDS
