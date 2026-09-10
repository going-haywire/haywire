"""The detail axes actually change what StackedNodeSkin builds.

The rest of the ADR-0032 suite is pure logic: the enum, the resolver, the
truth table. None of it renders, and every existing skin-render test is
``perf``-marked and so excluded from the pre-commit gate — meaning a green gate
would say nothing about whether these axes reach a card at all.

This file closes that hole by rendering real nodes through ``SkinFactory`` and
inspecting the elements that come out. Since the 2026-09 CSS-filter redesign
(ADR 0032's "Superseded" section) NodeDetail no longer changes which elements
are BUILT — every rank builds the same element count. What changes is which
``.hw-detail-*`` class each element carries, matched by canvas.vue's
``[data-node-props-detail]`` rules. So this file asserts "the element exists
AND carries the class its rank implies" rather than "the element exists only
above some rank" — a skin restyle does not break it while a skin that stops
tagging elements does.
"""

from __future__ import annotations

import pytest
from nicegui import ui

from haywire.core.graph.base import BaseGraph
from haywire.core.graph.scheduler import SyncScheduler
from haywire.core.types import NodeDetail
from haywire.ui import elements as hui
from haywire.ui.skin.factory import SkinFactory

pytestmark = [pytest.mark.integration]


def _graph():
    return BaseGraph(filestem="detail render", validation_scheduler=SyncScheduler())


_PORT_COUNT = 3


def _node(graph):
    """A node whose ports actually carry visible widgets AND labels.

    The choice matters: a node whose only port is an outlet cannot distinguish
    WIDGETS from PINS, because outlets default to ``ShowWidgetStrategy.NEVER``
    and so draw no widget at either rank. ``PerformanceTester`` generates
    unlinked FLOAT inlets with NumberWidgets, which is the case the ranks are
    actually about.
    """
    from haybale_testing.nodes.testbed.test_performance import PerformanceTester

    wrapper = graph.create_node_wrapper(PerformanceTester.class_identity.registry_key, position=(0, 0))
    assert wrapper is not None
    # Fires the dynamic-port rejig that adds the widget-bearing inlets.
    wrapper.node.ports["port_count"].set_value(_PORT_COUNT)
    graph.force_validation()
    shown = [p for p in wrapper.node.get_visible_ports() if p.should_show_widget()]
    assert shown, "fixture node draws no widgets — it cannot tell WIDGETS from PINS"
    return wrapper


def _render(skin_factory: SkinFactory, wrapper, skin_key: str) -> int:
    """Render one card into a throwaway container; return its element count."""
    container = ui.element("div")
    with container:
        skin_factory.render(skin_registry_key=skin_key, wrapper=wrapper)
    return len(list(container.descendants()))


def _render_container(skin_factory: SkinFactory, wrapper, skin_key: str) -> ui.element:
    """Render one card into a throwaway container; return the container itself
    so a caller can inspect classes, not just count elements."""
    container = ui.element("div")
    with container:
        skin_factory.render(skin_registry_key=skin_key, wrapper=wrapper)
    return container


def _elements_with_class(container: ui.element, css_class: str) -> list:
    return [el for el in container.descendants() if css_class in el._classes]


@pytest.fixture
def render_ctx(library_system, nicegui_slot_context):
    # From the injector, not constructed: a SkinFactory caches one skin
    # instance per registry key, and building a rival would bypass that.
    skin_factory = library_system.injector.get(SkinFactory)
    graph = _graph()
    wrapper = _node(graph)
    skin_key = skin_factory._skin_registry.get_default_skin_registry_key()
    assert skin_key, "no default skin registered"
    return skin_factory, graph, wrapper, skin_key


def _count_at(render_ctx, detail: NodeDetail, collapsed: bool = False) -> int:
    skin_factory, _graph_obj, wrapper, skin_key = render_ctx
    wrapper.node.props.detail = detail.value
    wrapper.node.props.collapsed = collapsed
    return _render(skin_factory, wrapper, skin_key)


def _render_at(render_ctx, detail: NodeDetail, collapsed: bool = False) -> ui.element:
    skin_factory, _graph_obj, wrapper, skin_key = render_ctx
    wrapper.node.props.detail = detail.value
    wrapper.node.props.collapsed = collapsed
    return _render_container(skin_factory, wrapper, skin_key)


class TestElementCountIsStableAcrossRanks:
    """2026-09: NodeDetail stopped being a construction gate. Every rank now
    builds the SAME elements — an unfolded card's element count must not move
    with the rank at all, because nothing is omitted from construction any
    more (ADR 0032's "Superseded" section)."""

    def test_every_unfolded_rank_builds_the_same_element_count(self, render_ctx):
        full = _count_at(render_ctx, NodeDetail.FULL)
        labels = _count_at(render_ctx, NodeDetail.LABELS)
        widgets = _count_at(render_ctx, NodeDetail.WIDGETS)
        pins_all = _count_at(render_ctx, NodeDetail.PINS_ALL)
        pins = _count_at(render_ctx, NodeDetail.PINS)

        assert pins == pins_all == widgets == labels == full, (
            f"element counts diverged across ranks (pins={pins}, "
            f"pins_all={pins_all}, widgets={widgets}, labels={labels}, "
            f"full={full}) — a rank is still gating construction instead of "
            f"tagging a CSS class"
        )

    def test_folding_is_still_the_cheapest(self, render_ctx):
        """Collapse is UNCHANGED — still a real construction gate, so a folded
        card still builds fewer elements than any unfolded rank."""
        full = _count_at(render_ctx, NodeDetail.FULL)
        folded = _count_at(render_ctx, NodeDetail.FULL, collapsed=True)

        assert folded < full, (
            f"folded ({folded}) must be cheaper than an unfolded card ({full}) — "
            f"an unlinked node folds to title and badges with no pins at all"
        )

    def test_folding_ignores_the_detail_rank(self, render_ctx):
        """`collapsed` short-circuits every predicate, so the rank underneath
        it cannot leak back into the card."""
        assert _count_at(render_ctx, NodeDetail.FULL, collapsed=True) == _count_at(
            render_ctx, NodeDetail.PINS, collapsed=True
        )


class TestDetailClassesGateVisibility:
    """The replacement for the old construction-gate assertions: the widget
    and label elements are BUILT at every rank, and only their `.hw-detail-*`
    class differs — canvas.vue's [data-node-props-detail] rules do the hiding.
    """

    def test_widget_carries_its_class_at_every_rank(self, render_ctx):
        for detail in NodeDetail:
            container = _render_at(render_ctx, detail)
            widgets = _elements_with_class(container, "hw-detail-widget")
            assert widgets, f"widget element missing at {detail} — it must always be BUILT"

    def test_label_carries_its_class_at_every_rank(self, render_ctx):
        for detail in NodeDetail:
            container = _render_at(render_ctx, detail)
            labels = _elements_with_class(container, "hw-detail-label")
            assert labels, f"label element missing at {detail} — it must always be BUILT"

    def test_folded_card_builds_no_detail_classed_elements(self, render_ctx):
        """Folding is still a construction gate — nothing to tag because
        nothing is built."""
        container = _render_at(render_ctx, NodeDetail.FULL, collapsed=True)
        assert not _elements_with_class(container, "hw-detail-widget")
        assert not _elements_with_class(container, "hw-detail-label")


class TestSplitSkinHonoursTheAxes:
    """The split skin is the reference an author copies, so it has to model
    the contract — not merely compile against it.

    It is also the only user-selectable in-repo skin with a materially
    different layout (two bands, its own section headings), which makes it the
    one most likely to thread ``show`` somewhere the stacked skin never
    exercises.
    """

    @pytest.fixture
    def example_ctx(self, render_ctx):
        from haybale_studio.skins.split_skin import SplitNodeSkin

        skin_factory, graph, wrapper, _default_key = render_ctx
        return skin_factory, graph, wrapper, SplitNodeSkin.class_identity.registry_key

    def test_ranks_build_the_same_element_count(self, example_ctx):
        full = _count_at(example_ctx, NodeDetail.FULL)
        widgets = _count_at(example_ctx, NodeDetail.WIDGETS)
        pins = _count_at(example_ctx, NodeDetail.PINS)

        assert pins == widgets == full

    def test_folds(self, example_ctx):
        folded = _count_at(example_ctx, NodeDetail.FULL, collapsed=True)
        assert folded < _count_at(example_ctx, NodeDetail.PINS)

    @pytest.mark.parametrize("detail", list(NodeDetail))
    @pytest.mark.parametrize("collapsed", [False, True])
    def test_every_combination_renders(self, example_ctx, detail, collapsed):
        assert _count_at(example_ctx, detail, collapsed) > 0


class TestCardStaysWellFormed:
    """Cheaper must not mean broken."""

    @pytest.mark.parametrize("detail", list(NodeDetail))
    @pytest.mark.parametrize("collapsed", [False, True])
    def test_every_combination_renders(self, render_ctx, detail, collapsed):
        assert _count_at(render_ctx, detail, collapsed) > 0

    @pytest.mark.parametrize("collapsed", [False, True])
    def test_card_always_carries_the_behavioural_classes(self, render_ctx, collapsed):
        """`node-card` and `zoom-pan-lod0` are contracts canvas.vue keys off —
        omitting either fails silently at drag or hover time. The folded branch
        writes its own class list, so it needs its own check.
        See docs/components/skins/skin-canon.md."""
        skin_factory, _g, wrapper, skin_key = render_ctx
        wrapper.node.props.detail = NodeDetail.FULL.value
        wrapper.node.props.collapsed = collapsed

        container = ui.element("div")
        with container:
            skin_factory.render(skin_registry_key=skin_key, wrapper=wrapper)

        classes = " ".join(" ".join(el._classes) for el in container.descendants())
        assert "node-card" in classes
        assert "zoom-pan-lod0" in classes


@pytest.mark.integration
class TestCommentBadge:
    """A comment surfaces as a badge, with emptiness as the only visibility rule.

    ADR 0032 retired the companion ``show_comment`` bool: it bought exactly
    "no badge", which an empty comment already gives, and no skin ever read it.
    """

    def _render_with_comment(self, render_ctx, comment: str, collapsed: bool = False) -> int:
        skin_factory, _g, wrapper, skin_key = render_ctx
        wrapper.node.props.comment = comment
        wrapper.node.props.collapsed = collapsed
        container = ui.element("div")
        with container:
            skin_factory.render(skin_registry_key=skin_key, wrapper=wrapper)
        return sum(1 for el in container.descendants() if isinstance(el, ui.tooltip) and el.text == comment)

    def test_a_comment_draws_a_badge(self, render_ctx):
        assert self._render_with_comment(render_ctx, "why this node exists") == 1

    def test_no_comment_draws_nothing(self, render_ctx):
        skin_factory, _g, wrapper, skin_key = render_ctx
        wrapper.node.props.comment = ""
        container = ui.element("div")
        with container:
            skin_factory.render(skin_registry_key=skin_key, wrapper=wrapper)
        icons = [
            el
            for el in container.descendants()
            if isinstance(el, ui.button) and el._props.get("icon") == hui.icon.message
        ]
        assert icons == []

    def test_whitespace_only_is_not_a_comment(self, render_ctx):
        assert self._render_with_comment(render_ctx, "   \n  ") == 0

    def test_the_badge_survives_folding(self, render_ctx):
        """The point of drawing it at the COLLAPSED tier: a folded node is a box
        with a title, and the comment is often the only thing saying why."""
        assert self._render_with_comment(render_ctx, "load bearing", collapsed=True) == 1

    @pytest.mark.parametrize("detail", list(NodeDetail))
    def test_the_badge_is_not_gated_by_rank(self, render_ctx, detail):
        skin_factory, _g, wrapper, skin_key = render_ctx
        wrapper.node.props.detail = detail.value
        assert self._render_with_comment(render_ctx, "still here") == 1


@pytest.mark.unit
class TestRetiredFlags:
    """The five ADR-0032 deletions stay deleted. Each was declared-but-unread,
    which is how they survived so long — nothing failed when they did nothing."""

    @pytest.mark.parametrize("gone", ["condensed", "show_comment"])
    def test_node_props_no_longer_declares(self, gone):
        from haywire.core.node.properties import NodeProperties

        assert gone not in NodeProperties._settings_descriptors()
        assert gone not in NodeProperties.REDRAW_FIELDS

    def test_comment_itself_survives(self):
        """The text stays — only its visibility flag went."""
        from haywire.core.node.properties import NodeProperties

        assert "comment" in NodeProperties._settings_descriptors()
        assert "comment" in NodeProperties.REDRAW_FIELDS
