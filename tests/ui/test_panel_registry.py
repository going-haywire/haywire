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


@panel(actions=_NodeActions, focus=_NodeFocus, label="Test Node Panel A", icon="info", order=10)
class _TestNodePanelA(BasePanel):
    actions: _NodeActions

    def draw(self, ctx, layout):
        pass


@panel(
    actions=_NodeActions,
    focus=_NodeFocus,
    label="Test Node Panel B",
    order=20,
    registry_id="test_node_panel_b",
)
class _TestNodePanelB(BasePanel):
    actions: _NodeActions

    def draw(self, ctx, layout):
        pass


@panel(
    actions=_NodeActions,
    focus=_GraphFocus,
    label="Test Graph Panel",
    order=10,
    registry_id="test_graph_panel",
)
class _TestGraphPanel(BasePanel):
    actions: _NodeActions

    def draw(self, ctx, layout):
        pass


# Display panel fixtures (no actions: annotation) used to test get_panels_for_focus
# and get_display_focuses.
@panel(focus=_NodeFocus, label="Test Node Display Panel", order=5, registry_id="test_node_display_panel")
class _TestNodeDisplayPanel(BasePanel):
    def draw(self, ctx, layout):
        pass


@panel(focus=_GraphFocus, label="Test Graph Display Panel", order=5, registry_id="test_graph_display_panel")
class _TestGraphDisplayPanel(BasePanel):
    def draw(self, ctx, layout):
        pass


class _NotDecoratedPanel(BasePanel):
    """Panel subclass without @panel — should NOT pass _class_filter."""

    def draw(self, ctx, layout):
        pass


# ---------------------------------------------------------------------------
# @panel decorator tests
# ---------------------------------------------------------------------------


class TestPanelDecorator:
    def test_registry_key(self):
        assert _TestNodePanelA.class_identity.registry_key.endswith(":panel:_TestNodePanelA")

    def test_action_protocol(self):
        assert _TestNodePanelA.class_identity.action_protocol is _NodeActions

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

            @panel(focus=_NodeFocus, label="Bad")
            class NotAPanel:
                pass

    def test_sets_class_library(self):
        assert hasattr(_TestNodePanelA, "class_library")

    def test_display_panel_has_no_action_protocol(self):
        assert _TestNodeDisplayPanel.class_identity.action_protocol is None


# ---------------------------------------------------------------------------
# PanelRegistry tests — action panels (get_panels_for_action)
# ---------------------------------------------------------------------------


class TestPanelRegistry:
    def setup_method(self):
        self.registry = PanelRegistry()

    def test_empty_on_init(self):
        assert self.registry.list_names() == []

    def test_register_and_get(self):
        self.registry._register_class(_TestNodePanelA, library_identity=None)
        key = _TestNodePanelA.class_identity.registry_key
        assert self.registry.get(key) is _TestNodePanelA

    def test_get_panels_for_action_returns_matching(self):
        self.registry._register_class(_TestNodePanelA, library_identity=None)
        self.registry._register_class(_TestGraphPanel, library_identity=None)
        node_panels = self.registry.get_panels_for_action(_NodeActions, _NodeFocus)
        assert _TestNodePanelA in node_panels
        assert _TestGraphPanel not in node_panels

    def test_get_panels_for_action_filters_by_focus(self):
        self.registry._register_class(_TestNodePanelA, library_identity=None)
        self.registry._register_class(_TestGraphPanel, library_identity=None)
        graph_panels = self.registry.get_panels_for_action(_NodeActions, _GraphFocus)
        assert _TestGraphPanel in graph_panels
        assert _TestNodePanelA not in graph_panels

    def test_get_panels_for_action_filters_by_protocol_mismatch(self):
        self.registry._register_class(_TestNodePanelA, library_identity=None)
        # _OtherActions is a different protocol — should not match _NodeActions panels.
        panels = self.registry.get_panels_for_action(_OtherActions, _NodeFocus)
        assert _TestNodePanelA not in panels

    def test_get_panels_for_action_sorted_by_order(self):
        self.registry._register_class(_TestNodePanelB, library_identity=None)
        self.registry._register_class(_TestNodePanelA, library_identity=None)
        panels = self.registry.get_panels_for_action(_NodeActions, _NodeFocus)
        assert panels[0] is _TestNodePanelA  # order=10
        assert panels[1] is _TestNodePanelB  # order=20

    def test_get_display_focuses_returns_unique_focuses(self):
        # Register display panels (no action_protocol) to exercise get_display_focuses.
        self.registry._register_class(_TestNodeDisplayPanel, library_identity=None)
        self.registry._register_class(_TestGraphDisplayPanel, library_identity=None)
        focuses = self.registry.get_display_focuses()
        assert _NodeFocus in focuses
        assert _GraphFocus in focuses
        # Each focus should appear exactly once.
        assert focuses.count(_NodeFocus) == 1

    def test_get_display_focuses_excludes_action_panels(self):
        # Action panels should NOT appear in get_display_focuses.
        self.registry._register_class(_TestNodePanelA, library_identity=None)
        focuses = self.registry.get_display_focuses()
        # _TestNodePanelA has action_protocol set, so its focus must not appear.
        assert _NodeFocus not in focuses

    def test_unregister_removes_class(self):
        self.registry._register_class(_TestNodePanelA, library_identity=None)
        key = _TestNodePanelA.class_identity.registry_key
        self.registry._unregister_class(key)
        assert not self.registry.has(key)
        panels = self.registry.get_panels_for_action(_NodeActions, _NodeFocus)
        assert _TestNodePanelA not in panels

    def test_class_filter_accepts_decorated_subclass(self):
        assert self.registry._class_filter(_TestNodePanelA) is True

    def test_class_filter_rejects_panel_base(self):
        assert self.registry._class_filter(BasePanel) is False

    def test_class_filter_rejects_undecorated_subclass(self):
        assert self.registry._class_filter(_NotDecoratedPanel) is False

    def test_class_filter_rejects_non_class(self):
        assert self.registry._class_filter("not_a_class") is False
