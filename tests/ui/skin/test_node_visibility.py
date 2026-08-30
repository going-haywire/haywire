"""NodeVisibility — the ADR-0032 rank→element mapping, in one place.

The whole point of the object under test is that skins never compare ranks, so
this file is where the mapping is pinned. A change here is a deliberate
re-tiering; a change in a skin is a bug.
"""

from __future__ import annotations

import pathlib
from dataclasses import FrozenInstanceError
from typing import TYPE_CHECKING, Any, List, cast

import pytest

from haywire.core.types import NodeDetail
from haywire.ui.skin.visibility import NodeVisibility, resolve_node_visibility

if TYPE_CHECKING:
    from haywire.core.node.data import NodeData
    from haywire.core.node.node_wrapper import NodeWrapper

pytestmark = pytest.mark.unit


def _show(detail: NodeDetail, collapsed: bool = False) -> NodeVisibility:
    return NodeVisibility(collapsed=collapsed, detail=detail)


class TestRankMapping:
    """The truth table. Read it as the spec."""

    @pytest.mark.parametrize(
        ("detail", "label", "widget", "diagnostics"),
        [
            (NodeDetail.COMPACT, False, False, False),
            (NodeDetail.STANDARD, False, True, False),
            (NodeDetail.FULL, True, True, True),
        ],
    )
    def test_unfolded_ranks(self, detail, label, widget, diagnostics):
        show = _show(detail)
        assert show.label is label
        assert show.widget is widget
        assert show.diagnostics is diagnostics

    @pytest.mark.parametrize("detail", list(NodeDetail))
    def test_folding_beats_every_rank(self, detail):
        """A folded card draws none of it, whatever the detail says."""
        show = _show(detail, collapsed=True)
        assert not show.label
        assert not show.widget
        assert not show.diagnostics

    def test_labels_sit_above_widgets(self):
        """Deliberate ordering (ADR 0032): tooltips already identify a port, and
        a label is one element per port against a widget's whole subtree — so
        STANDARD buys widgets and FULL adds the cheaper half."""
        assert _show(NodeDetail.STANDARD).widget
        assert not _show(NodeDetail.STANDARD).label

    def test_predicates_are_properties_not_methods(self):
        """`if show.label:` on a method is silently always true — this object
        exists to make that class of bug impossible."""
        for name in ("label", "widget", "diagnostics"):
            assert isinstance(getattr(NodeVisibility, name), property)

    def test_is_a_frozen_value(self):
        """Built inside a SkinFactory-cached skin shared across every node in
        every open graph, so it must carry no mutable per-node state."""
        show = _show(NodeDetail.FULL)
        with pytest.raises(FrozenInstanceError):
            show.collapsed = True  # type: ignore[misc]


class _FakePort:
    def __init__(self, pid, *, order=0, linked=False, section=None, is_group=False, visible=True):
        self.id = pid
        self.order = order
        self.section = section
        self.is_group = is_group
        self._linked = linked
        self._visible = visible

    def is_linked(self):
        return self._linked


class _FakeNode:
    """Stands in for NodeData's two port accessors."""

    def __init__(self, ports):
        self._ports = ports

    def get_all_ports(self):
        return sorted(self._ports, key=lambda p: p.order)

    def get_visible_ports(self, include_sections: bool = False):
        return [p for p in self.get_all_ports() if p._visible]


def _fake_node(ports: List[Any]) -> "NodeData":
    """Cast once here rather than ignoring at every call site: the fake stands
    in for exactly the two port accessors NodeVisibility.ports() uses."""
    return cast("NodeData", _FakeNode(ports))


def _fake_wrapper(props: Any) -> "NodeWrapper":
    return cast("NodeWrapper", _FakeWrapper(props))


class TestPortFilter:
    def test_unfolded_defers_to_get_visible_ports(self):
        """Detail changes what is drawn PER port, not which ports exist."""
        hidden = _FakePort("in_group", order=1, linked=True, visible=False)
        shown = _FakePort("plain", order=2, visible=True)
        node = _fake_node([hidden, shown])

        for detail in NodeDetail:
            assert _show(detail).ports(node) == [shown]

    def test_folded_keeps_every_linked_port(self):
        linked = _FakePort("linked", order=1, linked=True)
        loose = _FakePort("loose", order=2, linked=False)
        node = _fake_node([linked, loose])

        assert _show(NodeDetail.FULL, collapsed=True).ports(node) == [linked]

    def test_folded_ignores_group_collapse(self):
        """An edge must always find its endpoint: a linked port hidden by a
        collapsed GROUP still gets a pin on a folded card, because a folded
        card is all header and there is nowhere else for it to go."""
        buried = _FakePort("buried", order=1, linked=True, visible=False)
        node = _fake_node([buried])

        assert _show(NodeDetail.FULL).ports(node) == []  # unfolded: group hides it
        assert _show(NodeDetail.FULL, collapsed=True).ports(node) == [buried]

    def test_folded_drops_sections_and_group_controls(self):
        """Matches iter_hidden_connected_ports' filter. A group control port is
        never linked anyway, so it falls out twice over."""
        section = _FakePort("sect", order=1, linked=True, section="advanced")
        group = _FakePort("grp", order=2, linked=True, is_group=True)
        real = _FakePort("real", order=3, linked=True)
        node = _fake_node([section, group, real])

        assert _show(NodeDetail.COMPACT, collapsed=True).ports(node) == [real]

    def test_folded_preserves_display_order(self):
        late = _FakePort("late", order=9, linked=True)
        early = _FakePort("early", order=1, linked=True)
        node = _fake_node([late, early])

        assert _show(NodeDetail.FULL, collapsed=True).ports(node) == [early, late]


class _FakeProps:
    def __init__(self, collapsed, detail):
        self.collapsed = collapsed
        self.detail = detail


class _FakeWrapper:
    def __init__(self, props):
        self.node = type("N", (), {"props": props})()


class TestResolver:
    def test_reads_both_axes(self):
        show = resolve_node_visibility(_fake_wrapper(_FakeProps(True, "compact")))
        assert show.collapsed is True
        assert show.detail is NodeDetail.COMPACT

    @pytest.mark.parametrize("junk", ["sideways", None, 7])
    def test_corrupt_detail_degrades_to_full(self, junk):
        """Render path: degrade toward MORE drawing. Too much is slow; too
        little looks broken."""
        show = resolve_node_visibility(_fake_wrapper(_FakeProps(False, junk)))
        assert show.detail is NodeDetail.FULL

    def test_unreadable_props_never_raise(self):
        """A stale or exploding props bag must not take a node card down."""

        class Exploding:
            @property
            def collapsed(self):
                raise RuntimeError("boom")

            @property
            def detail(self):
                raise RuntimeError("boom")

        show = resolve_node_visibility(_fake_wrapper(Exploding()))
        assert show.collapsed is False
        assert show.detail is NodeDetail.FULL

    def test_missing_node_degrades_rather_than_raising(self):
        class NoNode:
            @property
            def node(self):
                raise AttributeError("detached")

        show = resolve_node_visibility(NoNode())  # type: ignore[arg-type]
        assert show == NodeVisibility(collapsed=False, detail=NodeDetail.FULL)


class TestSkinsHonourTheAxes:
    """ADR 0032 decision 7: skins honour the axes, the framework does not
    enforce them. Nothing can cover a third-party skin, so this covers ours —
    the same source-inspection approach ``test_node_skin_settings.py`` uses,
    and for the same reason: "does this skin consult the axes" is not
    observable from a rendered card.

    A skin that ignores them renders everything — slower, never broken.
    """

    _ROOT = pathlib.Path(__file__).resolve().parents[3]

    # Every in-repo directory that holds node skins. A new one added without
    # being listed here is invisible to this check, which is what
    # `test_every_known_skin_dir_exists` is for.
    _SKIN_DIRS = (
        _ROOT / "barn/haybale-studio/haybale_studio/skins",
        _ROOT / "packages/haywire-core/src/haywire/barn/builtin/skins",
    )

    # Skins that ignore the axes ON PURPOSE. Each entry is a decision, not a
    # backlog item — adding one means arguing why that card should stay
    # full-size when the user folds every node in the graph.
    #
    # The error skin is NOT here. It shows everything, but it says so through
    # the axes rather than around them: it overrides ``show_of`` to return a
    # wide-open NodeVisibility, so the sweep below sees it consulting the
    # contract and every ``show.`` call on its render path stays honest.
    _EXEMPT = {
        # Already a bare dot on a wire — a folded card would be BIGGER, and it
        # has no labels or widgets for a rank to remove.
        "reroute_skin.py",
    }

    def test_every_known_skin_dir_exists(self):
        """Guard the premise — a stale path makes the sweep below vacuous."""
        for directory in self._SKIN_DIRS:
            assert directory.is_dir(), f"skin directory not found: {directory}"
        assert (self._SKIN_DIRS[0] / "stacked_skin.py").is_file()

    def test_every_non_exempt_skin_consults_node_visibility(self):
        unaware = []
        for directory in self._SKIN_DIRS:
            for path in sorted(directory.glob("*_skin.py")):
                if path.name in self._EXEMPT:
                    continue
                source = path.read_text()
                if "show_of" not in source and "NodeVisibility" not in source:
                    unaware.append(str(path.relative_to(self._ROOT)))

        assert not unaware, (
            f"{unaware} render node cards without consulting show_of(). They will "
            f"draw everything at every rank, so graph-level collapse silently "
            f"does nothing for nodes using them. Wire them, or add them to "
            f"_EXEMPT with a reason."
        )

    def test_exempt_skins_still_exist(self):
        """A rename would otherwise turn an exemption into a silent hole."""
        present = {p.name for d in self._SKIN_DIRS for p in d.glob("*_skin.py")}
        missing = self._EXEMPT - present
        assert not missing, f"{sorted(missing)} no longer exist — update _EXEMPT"


@pytest.mark.integration
class TestSkinAccessor:
    def test_node_skin_exposes_show_of(self):
        """Standalone skins call the resolver directly; NodeSkin subclasses get
        this thin wrapper, mirroring layout_of."""
        from haybale_studio.skins.node_skin import NodeSkin

        assert hasattr(NodeSkin, "show_of")


@pytest.fixture
def live_graph(library_system):
    """A graph with the library system loaded, for the integration class below.

    Declared here rather than reused from ``tests/core/conftest.py``: that one
    is scoped to ``tests/core/``, and this module belongs beside the UI code it
    covers. ``SyncScheduler`` runs validation inline, so assertions can follow
    a mutation without flushing a timer.
    """
    from haywire.core.graph.base import BaseGraph
    from haywire.core.graph.scheduler import SyncScheduler

    return BaseGraph(filestem="Visibility Test Graph", validation_scheduler=SyncScheduler())


@pytest.mark.integration
class TestAgainstRealNodes:
    """The fakes above pin the mapping; these pin that it fits reality.

    A prop that stops returning what the resolver expects, or a NodeData port
    accessor that changes shape, fails here rather than silently in a card.
    """

    def _add_node(self, graph_obj):
        from haybale_testing.nodes.testbed.print_node import TestPrintNode

        return graph_obj.create_node_wrapper(TestPrintNode.class_identity.registry_key, position=(100, 100))

    def test_resolves_a_real_wrapper_at_the_default(self, live_graph):
        wrapper = self._add_node(live_graph)
        show = resolve_node_visibility(wrapper)

        assert show.collapsed is False
        assert show.detail is NodeDetail.FULL
        assert show.label
        assert show.widget
        assert show.diagnostics

    def test_tier_writes_reach_the_resolver(self, live_graph):
        graph_obj = live_graph
        wrapper = self._add_node(graph_obj)

        graph_obj.props.detail = NodeDetail.COMPACT.value
        assert resolve_node_visibility(wrapper).detail is NodeDetail.COMPACT

        wrapper.node.props.detail = NodeDetail.STANDARD.value
        assert resolve_node_visibility(wrapper).detail is NodeDetail.STANDARD

        graph_obj.props.collapsed = True
        assert resolve_node_visibility(wrapper).collapsed is True

    def test_port_filter_runs_against_real_node_data(self, live_graph):
        """get_all_ports / get_visible_ports exist with the shapes assumed."""
        wrapper = self._add_node(live_graph)
        node = wrapper.node

        unfolded = NodeVisibility(collapsed=False, detail=NodeDetail.FULL).ports(node)
        assert unfolded == node.get_visible_ports()

        folded = NodeVisibility(collapsed=True, detail=NodeDetail.FULL).ports(node)
        assert all(p.is_linked() for p in folded)
        assert len(folded) <= len(node.get_all_ports())

    def test_unlinked_node_folds_to_no_ports(self, live_graph):
        """The element-count win: a freshly added node has no edges, so folding
        it drops every pin."""
        wrapper = self._add_node(live_graph)
        assert NodeVisibility(collapsed=True, detail=NodeDetail.FULL).ports(wrapper.node) == []
