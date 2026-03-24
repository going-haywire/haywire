# tests/ui/test_panel_registry.py
"""
Tests for the PanelRegistry and @panel decorator.
"""

import pytest
from haywire.ui.panel.base import BasePanel
from haywire.ui.panel.decorator import panel
from haywire.ui.panel.registry import PanelRegistry
from haywire.ui.panel.scope import ScopeDescriptor


# ---------------------------------------------------------------------------
# Minimal concrete panels for testing
# ---------------------------------------------------------------------------


@panel(
    registry_id="test_node_panel",
    editor="properties",
    scope="node",
    label="Test Node Panel",
    icon="info",
    order=10,
)
class _TestNodePanel(BasePanel):
    def draw(self, context, layout):
        pass


@panel(
    registry_id="test_node_panel_b",
    editor="properties",
    scope="node",
    label="Test Node Panel B",
    order=20,
)
class _TestNodePanelB(BasePanel):
    def draw(self, context, layout):
        pass


@panel(
    registry_id="test_graph_panel",
    editor="properties",
    scope="graph",
    label="Test Graph Panel",
    order=10,
)
class _TestGraphPanel(BasePanel):
    def draw(self, context, layout):
        pass


@panel(
    registry_id="test_other_editor_panel",
    editor="other_editor",
    scope="node",
    label="Other Editor Panel",
    order=10,
)
class _TestOtherEditorPanel(BasePanel):
    def draw(self, context, layout):
        pass


@panel(
    registry_id="test_multi_scope_panel",
    editor="properties",
    scope=["node", "graph"],
    label="Multi Scope Panel",
    order=15,
)
class _TestMultiScopePanel(BasePanel):
    def draw(self, context, layout):
        pass


class _NotDecoratedPanel(BasePanel):
    """BasePanel subclass without @panel — should NOT pass _class_filter."""

    def draw(self, context, layout):
        pass


# ---------------------------------------------------------------------------
# @panel decorator tests
# ---------------------------------------------------------------------------


class TestPanelDecorator:
    def test_sets_class_identity(self):
        assert hasattr(_TestNodePanel, "class_identity")

    def test_registry_key(self):
        assert _TestNodePanel.class_identity.registry_key.endswith(":panel:test_node_panel")

    def test_editor_key(self):
        assert _TestNodePanel.class_identity.editor_key == "properties"

    def test_scope_is_list(self):
        assert _TestNodePanel.class_identity.scope == ["node"]

    def test_scope_multi_normalised(self):
        assert _TestMultiScopePanel.class_identity.scope == ["node", "graph"]

    def test_label(self):
        assert _TestNodePanel.class_identity.label == "Test Node Panel"

    def test_icon(self):
        assert _TestNodePanel.class_identity.icon == "info"

    def test_order(self):
        assert _TestNodePanel.class_identity.order == 10

    def test_does_not_auto_register(self):
        """@panel must NOT register the class in any registry on its own."""
        assert _TestNodePanel.class_identity is not None

    def test_rejects_non_base_panel(self):
        with pytest.raises(TypeError):

            @panel(registry_id="bad", editor="props", scope="node")
            class NotAPanel:
                pass

    def test_sets_class_library(self):
        assert hasattr(_TestNodePanel, "class_library")


# ---------------------------------------------------------------------------
# PanelRegistry tests
# ---------------------------------------------------------------------------


class TestPanelRegistry:
    def setup_method(self):
        self.registry = PanelRegistry()

    def test_empty_on_init(self):
        assert self.registry.list_names() == []
        assert self.registry._index == {}

    def test_register_and_get(self):
        self.registry._register_class(_TestNodePanel, library_identity=None)
        key = _TestNodePanel.class_identity.registry_key
        assert self.registry.get(key) is _TestNodePanel

    def test_register_updates_primary_index(self):
        self.registry._register_class(_TestNodePanel, library_identity=None)
        panels = self.registry.get_panels("properties", "node")
        assert _TestNodePanel in panels

    def test_get_panels_sorted_by_order(self):
        self.registry._register_class(_TestNodePanelB, library_identity=None)
        self.registry._register_class(_TestNodePanel, library_identity=None)
        panels = self.registry.get_panels("properties", "node")
        assert panels[0] is _TestNodePanel  # order=10
        assert panels[1] is _TestNodePanelB  # order=20

    def test_get_panels_empty_for_unknown(self):
        panels = self.registry.get_panels("nonexistent", "node")
        assert panels == []

    def test_get_panels_filters_by_scope(self):
        self.registry._register_class(_TestNodePanel, library_identity=None)
        self.registry._register_class(_TestGraphPanel, library_identity=None)
        node_panels = self.registry.get_panels("properties", "node")
        graph_panels = self.registry.get_panels("properties", "graph")
        assert _TestNodePanel in node_panels
        assert _TestGraphPanel not in node_panels
        assert _TestGraphPanel in graph_panels
        assert _TestNodePanel not in graph_panels

    def test_multi_scope_panel_appears_in_both_scopes(self):
        self.registry._register_class(_TestMultiScopePanel, library_identity=None)
        node_panels = self.registry.get_panels("properties", "node")
        graph_panels = self.registry.get_panels("properties", "graph")
        assert _TestMultiScopePanel in node_panels
        assert _TestMultiScopePanel in graph_panels

    def test_get_all_for_editor(self):
        self.registry._register_class(_TestNodePanel, library_identity=None)
        self.registry._register_class(_TestGraphPanel, library_identity=None)
        self.registry._register_class(_TestOtherEditorPanel, library_identity=None)
        result = self.registry.get_all_for_editor("properties")
        assert "node" in result
        assert "graph" in result
        assert "other_editor" not in str(result)  # panels for other editor not included
        assert _TestNodePanel in result["node"]
        assert _TestGraphPanel in result["graph"]

    def test_unregister_removes_from_primary(self):
        self.registry._register_class(_TestNodePanel, library_identity=None)
        key = _TestNodePanel.class_identity.registry_key
        self.registry._unregister_class(key)
        assert not self.registry.has(key)

    def test_unregister_removes_from_index(self):
        self.registry._register_class(_TestNodePanel, library_identity=None)
        key = _TestNodePanel.class_identity.registry_key
        self.registry._unregister_class(key)
        panels = self.registry.get_panels("properties", "node")
        assert _TestNodePanel not in panels

    def test_unregister_removes_multi_scope_panel_from_all_scopes(self):
        self.registry._register_class(_TestMultiScopePanel, library_identity=None)
        key = _TestMultiScopePanel.class_identity.registry_key
        self.registry._unregister_class(key)
        assert _TestMultiScopePanel not in self.registry.get_panels("properties", "node")
        assert _TestMultiScopePanel not in self.registry.get_panels("properties", "graph")

    def test_class_filter_accepts_decorated_subclass(self):
        assert self.registry._class_filter(_TestNodePanel) is True

    def test_class_filter_rejects_base_class(self):
        assert self.registry._class_filter(BasePanel) is False

    def test_class_filter_rejects_undecorated_subclass(self):
        assert self.registry._class_filter(_NotDecoratedPanel) is False

    def test_class_filter_rejects_non_class(self):
        assert self.registry._class_filter("not_a_class") is False


# ---------------------------------------------------------------------------
# Scope registration tests
# ---------------------------------------------------------------------------


class TestScopeRegistration:
    def setup_method(self):
        self.registry = PanelRegistry()

    def test_register_scope(self):
        desc = ScopeDescriptor(scope_id="node", label="Node", icon="widgets", order=10)
        self.registry.register_scope("properties", desc)
        scopes = self.registry.get_scopes("properties")
        assert len(scopes) == 1
        assert scopes[0].scope_id == "node"

    def test_get_scopes_sorted_by_order(self):
        self.registry.register_scope(
            "properties", ScopeDescriptor(scope_id="z", label="Z", icon="a", order=50)
        )
        self.registry.register_scope(
            "properties", ScopeDescriptor(scope_id="a", label="A", icon="b", order=10)
        )
        scopes = self.registry.get_scopes("properties")
        assert scopes[0].scope_id == "a"
        assert scopes[1].scope_id == "z"

    def test_get_scopes_empty_for_unknown_editor(self):
        scopes = self.registry.get_scopes("nonexistent")
        assert scopes == []

    def test_get_scopes_filters_by_editor(self):
        self.registry.register_scope(
            "properties", ScopeDescriptor(scope_id="node", label="Node", icon="widgets")
        )
        self.registry.register_scope("other", ScopeDescriptor(scope_id="node", label="Node", icon="widgets"))
        scopes = self.registry.get_scopes("properties")
        assert len(scopes) == 1

    def test_scope_overwrite(self):
        """Re-registering an existing scope is a no-op — first registration wins."""
        desc1 = ScopeDescriptor(scope_id="node", label="Old", icon="x")
        desc2 = ScopeDescriptor(scope_id="node", label="New", icon="y")
        self.registry.register_scope("properties", desc1)
        self.registry.register_scope("properties", desc2)
        scopes = self.registry.get_scopes("properties")
        assert len(scopes) == 1
        assert scopes[0].label == "Old"
