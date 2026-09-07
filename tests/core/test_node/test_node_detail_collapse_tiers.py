"""The two ADR-0032 card axes on real nodes: NodeDetail and Node collapse.

Modelled on test_node_layout_direction_graph_tier.py — `detail` rides the exact
same shadow()/graph() machinery, so its tier behaviour must match field for
field. `collapsed` deliberately does NOT: it is a single-tier, node-only field
with no graph or framework counterpart, and the asymmetry is the thing most
likely to be "fixed" by someone who notices it, so it is asserted here
explicitly.
"""

import pytest

from haywire.core.di.context import get_settings_registry
from haywire.core.graph.base import BaseGraph
from haywire.core.types import NodeDetail

DETAIL_KEY = "ui.node.default.skin.studio_node_detail"

PINS = NodeDetail.PINS.value
PINS_ALL = NodeDetail.PINS_ALL.value
WIDGETS = NodeDetail.WIDGETS.value
LABELS = NodeDetail.LABELS.value
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
        assert (
            NodeDetail.PINS.rank
            < NodeDetail.PINS_ALL.rank
            < NodeDetail.WIDGETS.rank
            < NodeDetail.LABELS.rank
            < NodeDetail.FULL.rank
        )

    def test_includes_is_reflexive_and_directional(self):
        assert NodeDetail.WIDGETS.includes(NodeDetail.WIDGETS)
        assert NodeDetail.FULL.includes(NodeDetail.PINS)
        assert not NodeDetail.PINS.includes(NodeDetail.WIDGETS)

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

    @pytest.mark.parametrize("old_value", ["compact", "standard"])
    def test_pre_5rank_saved_values_degrade_to_full(self, old_value):
        """Breaking change, no migration shim (design session, 2026-09-02):
        an old 3-rank graph's detail value is simply unrecognised now."""
        assert NodeDetail.coerce(old_value) is NodeDetail.FULL

    def test_coerce_passes_through_members_and_valid_strings(self):
        assert NodeDetail.coerce(NodeDetail.PINS) is NodeDetail.PINS
        assert NodeDetail.coerce("widgets") is NodeDetail.WIDGETS

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
        graph_obj.props.detail = PINS
        assert wrapper.node.props.detail == PINS

    def test_node_override_wins_and_resets_fall_one_tier(self, graph_with_library_system):
        graph_obj = graph_with_library_system
        registry = get_settings_registry()
        wrapper = _add_node(graph_obj)

        registry.set_global(DETAIL_KEY, PINS)
        graph_obj.props.detail = WIDGETS
        wrapper.node.props.detail = FULL
        assert wrapper.node.props.detail == FULL

        wrapper.node.props.reset("detail")
        assert wrapper.node.props.detail == WIDGETS  # node → graph
        graph_obj.props.reset("detail")
        assert wrapper.node.props.detail == PINS  # graph → framework

    def test_round_trip_preserves_all_three_tiers(self, graph_with_library_system, library_system):
        graph_obj = graph_with_library_system
        w1 = _add_node(graph_obj)
        _add_node(graph_obj)  # w2: left tracking, only inspected after round-trip below
        graph_obj.props.detail = WIDGETS
        w1.node.props.detail = PINS  # w1 overridden, w2 tracking
        data = graph_obj.to_dict()

        g2 = BaseGraph(filestem="G2")
        assert g2.load_from_dict(data) is True
        loaded = list(g2.node_wrappers.values())
        overridden = [w for w in loaded if w.node.props.is_locally_set("detail")]
        tracking = [w for w in loaded if not w.node.props.is_locally_set("detail")]
        assert len(overridden) == 1
        assert overridden[0].node.props.detail == PINS
        assert len(tracking) == 1
        assert tracking[0].node.props.detail == WIDGETS

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
        graph_obj.props.detail = PINS

        assert seen, "graph-tier write did not fire the node's field subscription"
        assert seen[-1] == PINS


@pytest.mark.integration
class TestNodeCollapse:
    """Collapse is a single-tier, node-only field — no graph or framework
    mirror. It was a two-tier (graph < node) shadow field; the graph tier was
    removed (see ``GraphProperties``). What is worth pinning is not that it
    behaves like an ordinary attribute (it does, trivially) but that it does
    NOT regain either tier it used to have.
    """

    def test_defaults_to_expanded_and_stays_per_node(self, graph_with_library_system):
        graph_obj = graph_with_library_system
        w1 = _add_node(graph_obj)
        w2 = _add_node(graph_obj)
        assert w1.node.props.collapsed is False

        w1.node.props.collapsed = True
        assert w2.node.props.collapsed is False  # untouched, no graph mirror to inherit

    def test_has_no_graph_tier(self, graph_with_library_system):
        """The tier this class used to test — deleted, not a bug. Guards
        against `collapsed` silently regaining a graph-level shadow."""
        graph_obj = graph_with_library_system
        assert not any("collaps" in name for name in type(graph_obj.props)._property_settings()), (
            "collapse regained a graph tier; it is now node-only"
        )

    def test_has_no_framework_tier(self):
        """Single tier by design: a studio-wide fold would open every graph
        showing nothing."""
        from haywire.core.skin.settings import NodeDefaultSkinSettings

        assert not any("collaps" in name for name in NodeDefaultSkinSettings._property_settings()), (
            "collapse gained a framework tier; it is node-only"
        )


@pytest.mark.unit
class TestBothAxesRedraw:
    def test_collapse_is_a_redraw_field(self):
        """Collapse is still a CONSTRUCTION gate, so a change must rebuild the
        card. Without the entry no tier change ever reaches the canvas."""
        from haywire.core.node.properties import NodeProperties

        assert "collapsed" in NodeProperties.REDRAW_FIELDS

    def test_detail_is_not_a_redraw_field(self):
        """NodeDetail stopped being a construction gate (2026-09 CSS-filter
        redesign) — a rank change is a class-attribute flip handled by
        UINode._apply_detail_attr, not a card rebuild. If this ever needs to
        change back, it is a deliberate reversal, not a bug fix."""
        from haywire.core.node.properties import NodeProperties

        assert "detail" not in NodeProperties.REDRAW_FIELDS
