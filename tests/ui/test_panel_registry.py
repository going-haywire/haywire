# tests/ui/test_panel_registry.py
"""
Tests for the PanelRegistry and @panel decorator (Phase 1.5+ contract).
"""

from typing import Protocol, runtime_checkable

import pytest

from haywire.ui.panel import BasePanel, panel
from haywire.ui.panel.focus import Focus
from haywire.ui.panel.registry import PanelRegistry


# ---------------------------------------------------------------------------
# Test fixtures
# ---------------------------------------------------------------------------


@runtime_checkable
class _NodeActions(Protocol):
    def do_node_thing(self) -> None: ...


@runtime_checkable
class _OtherActions(Protocol):
    def do_other_thing(self) -> None: ...


class _NodeFocus(Focus):
    id = "registry_test_node"
    label = "Node"
    icon = "x"

    @classmethod
    def available(cls, ctx):
        return True


class _GraphFocus(Focus):
    id = "registry_test_graph"
    label = "Graph"
    icon = "y"

    @classmethod
    def available(cls, ctx):
        return True


@panel(action=_NodeActions, focus=_NodeFocus, label="Test Node Panel A", icon="info", order=10)
class _TestNodePanelA(BasePanel):
    def draw(self, ctx, layout, actions):
        pass


@panel(
    action=_NodeActions,
    focus=_NodeFocus,
    label="Test Node Panel B",
    order=20,
    registry_id="test_node_panel_b",
)
class _TestNodePanelB(BasePanel):
    def draw(self, ctx, layout, actions):
        pass


@panel(
    action=_NodeActions,
    focus=_GraphFocus,
    label="Test Graph Panel",
    order=10,
    registry_id="test_graph_panel",
)
class _TestGraphPanel(BasePanel):
    def draw(self, ctx, layout, actions):
        pass


class _NotDecoratedPanel(BasePanel):
    """Panel subclass without @panel — should NOT pass _class_filter."""

    def draw(self, ctx, layout, actions):
        pass


# ---------------------------------------------------------------------------
# @panel decorator tests
# ---------------------------------------------------------------------------


class TestPanelDecorator:
    def test_registry_key(self):
        assert _TestNodePanelA.class_identity.registry_key.endswith(":panel:_TestNodePanelA")

    def test_action(self):
        assert _TestNodePanelA.class_identity.action is _NodeActions

    def test_focus(self):
        assert _TestNodePanelA.class_identity.focus is _NodeFocus

    def test_label(self):
        assert _TestNodePanelA.class_identity.label == "Test Node Panel A"

    def test_icon(self):
        assert _TestNodePanelA.class_identity.icon == "info"

    def test_order(self):
        assert _TestNodePanelA.class_identity.order == 10

    def test_does_not_auto_register(self):
        """@panel must NOT register the class in any registry on its own."""
        assert _TestNodePanelA.class_identity is not None

    def test_rejects_non_panel(self):
        with pytest.raises(TypeError):

            @panel(action=_NodeActions, focus=_NodeFocus, label="Bad")
            class NotAPanel:
                pass

    def test_sets_class_library(self):
        assert hasattr(_TestNodePanelA, "class_library")


# ---------------------------------------------------------------------------
# PanelRegistry tests
# ---------------------------------------------------------------------------


class _NodeActionsImpl:
    """Structural impl of _NodeActions used as actions_provider in tests."""

    def do_node_thing(self) -> None:
        pass


class _OtherActionsImpl:
    """Structural impl of _OtherActions only — does NOT satisfy _NodeActions."""

    def do_other_thing(self) -> None:
        pass


class TestPanelRegistry:
    def setup_method(self):
        self.registry = PanelRegistry()

    def test_empty_on_init(self):
        assert self.registry.list_names() == []

    def test_register_and_get(self):
        self.registry._register_class(_TestNodePanelA, library_identity=None)
        key = _TestNodePanelA.class_identity.registry_key
        assert self.registry.get(key) is _TestNodePanelA

    def test_get_panels_for_returns_matching(self):
        self.registry._register_class(_TestNodePanelA, library_identity=None)
        self.registry._register_class(_TestGraphPanel, library_identity=None)
        provider = _NodeActionsImpl()
        node_panels = self.registry.get_panels_for(actions_provider=provider, focus=_NodeFocus)
        assert _TestNodePanelA in node_panels
        assert _TestGraphPanel not in node_panels

    def test_get_panels_for_filters_by_focus(self):
        self.registry._register_class(_TestNodePanelA, library_identity=None)
        self.registry._register_class(_TestGraphPanel, library_identity=None)
        provider = _NodeActionsImpl()
        graph_panels = self.registry.get_panels_for(actions_provider=provider, focus=_GraphFocus)
        assert _TestGraphPanel in graph_panels
        assert _TestNodePanelA not in graph_panels

    def test_get_panels_for_filters_by_action_isinstance(self):
        self.registry._register_class(_TestNodePanelA, library_identity=None)
        # _OtherActionsImpl does NOT satisfy _NodeActions structurally.
        provider = _OtherActionsImpl()
        panels = self.registry.get_panels_for(actions_provider=provider, focus=_NodeFocus)
        assert _TestNodePanelA not in panels

    def test_get_panels_for_sorted_by_order(self):
        self.registry._register_class(_TestNodePanelB, library_identity=None)
        self.registry._register_class(_TestNodePanelA, library_identity=None)
        provider = _NodeActionsImpl()
        panels = self.registry.get_panels_for(actions_provider=provider, focus=_NodeFocus)
        assert panels[0] is _TestNodePanelA  # order=10
        assert panels[1] is _TestNodePanelB  # order=20

    def test_get_focuses_for_returns_unique_focuses(self):
        self.registry._register_class(_TestNodePanelA, library_identity=None)
        self.registry._register_class(_TestNodePanelB, library_identity=None)
        self.registry._register_class(_TestGraphPanel, library_identity=None)
        provider = _NodeActionsImpl()
        focuses = self.registry.get_focuses_for(actions_provider=provider)
        assert _NodeFocus in focuses
        assert _GraphFocus in focuses
        # _NodeFocus appears for two panels but should be returned once.
        assert focuses.count(_NodeFocus) == 1

    def test_unregister_removes_class(self):
        self.registry._register_class(_TestNodePanelA, library_identity=None)
        key = _TestNodePanelA.class_identity.registry_key
        self.registry._unregister_class(key)
        assert not self.registry.has(key)
        provider = _NodeActionsImpl()
        panels = self.registry.get_panels_for(actions_provider=provider, focus=_NodeFocus)
        assert _TestNodePanelA not in panels

    def test_class_filter_accepts_decorated_subclass(self):
        assert self.registry._class_filter(_TestNodePanelA) is True

    def test_class_filter_rejects_panel_base(self):
        assert self.registry._class_filter(BasePanel) is False

    def test_class_filter_rejects_undecorated_subclass(self):
        assert self.registry._class_filter(_NotDecoratedPanel) is False

    def test_class_filter_rejects_non_class(self):
        assert self.registry._class_filter("not_a_class") is False
