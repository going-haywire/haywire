# tests/ui/test_panel_registry.py
"""
Tests for the PanelRegistry and @panel decorator (surface model).
"""

from typing import Protocol, runtime_checkable

import pytest

from haywire.ui.panel import BasePanel, panel
from haywire.ui.panel.registry import PanelRegistry
from haywire.ui.surface import Surface


# ---------------------------------------------------------------------------
# Test fixtures
# ---------------------------------------------------------------------------


@runtime_checkable
class _NodeActions(Protocol):
    def do_node_thing(self) -> None: ...


class _NodeSurface(Surface):
    id = "registry_test_node"
    provides = _NodeActions


class _GraphSurface(Surface):
    id = "registry_test_graph"


class _NestedSurface(Surface):
    id = "registry_test_nested"


@panel(surface=_NodeSurface, label="Test Node Panel A", icon="info", order=10)
class _TestNodePanelA(BasePanel):
    actions: _NodeActions

    def draw(self, ctx, layout):
        pass


@panel(
    surface=_NodeSurface,
    label="Test Node Panel B",
    order=20,
    registry_id="test_node_panel_b",
)
class _TestNodePanelB(BasePanel):
    actions: _NodeActions

    def draw(self, ctx, layout):
        pass


@panel(
    surface=_GraphSurface,
    label="Test Graph Panel",
    order=10,
    registry_id="test_graph_panel",
)
class _TestGraphPanel(BasePanel):
    def draw(self, ctx, layout):
        pass


@panel(
    surface=_GraphSurface,
    hosts=(_NestedSurface,),
    label="Test Hosting Panel",
    order=1,
    registry_id="test_hosting_panel",
)
class _TestHostingPanel(BasePanel):
    def draw(self, ctx, layout):
        pass


@panel(surface=_NestedSurface, label="Test Nested Panel", order=5, registry_id="test_nested_panel")
class _TestNestedPanel(BasePanel):
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

    def test_surface(self):
        assert _TestNodePanelA.class_identity.surface is _NodeSurface

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

            @panel(surface=_NodeSurface, label="Bad")
            class NotAPanel:
                pass

    def test_sets_class_library(self):
        assert _TestNodePanelA.class_library is not None

    def test_leaf_panel_declares_no_hosts(self):
        assert _TestNodePanelA.class_identity.hosts == ()

    def test_hosting_panel_carries_its_declaration(self):
        assert _TestHostingPanel.class_identity.hosts == (_NestedSurface,)


# ---------------------------------------------------------------------------
# PanelRegistry tests
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

    def test_get_panels_returns_matching(self):
        self.registry._register_class(_TestNodePanelA, library_identity=None)
        self.registry._register_class(_TestGraphPanel, library_identity=None)
        node_panels = self.registry.get_panels(_NodeSurface)
        assert _TestNodePanelA in node_panels
        assert _TestGraphPanel not in node_panels

    def test_get_panels_filters_by_surface(self):
        self.registry._register_class(_TestNodePanelA, library_identity=None)
        self.registry._register_class(_TestGraphPanel, library_identity=None)
        graph_panels = self.registry.get_panels(_GraphSurface)
        assert _TestGraphPanel in graph_panels
        assert _TestNodePanelA not in graph_panels

    def test_get_panels_matches_by_id_not_class_object(self):
        """A surface reloaded into a new class object with the same id still matches.

        This is the hot-reload rule from ADR-0009: routing is by the stable id,
        never by identity of the class captured at decoration time.
        """
        self.registry._register_class(_TestNodePanelA, library_identity=None)

        class _Impostor:
            id = "registry_test_node"

        assert _TestNodePanelA in self.registry.get_panels(_Impostor)

    def test_get_panels_sorted_by_order(self):
        self.registry._register_class(_TestNodePanelB, library_identity=None)
        self.registry._register_class(_TestNodePanelA, library_identity=None)
        panels = self.registry.get_panels(_NodeSurface)
        assert panels[0] is _TestNodePanelA  # order=10
        assert panels[1] is _TestNodePanelB  # order=20

    def test_get_root_surfaces_returns_unique_surfaces(self):
        self.registry._register_class(_TestNodePanelA, library_identity=None)
        self.registry._register_class(_TestGraphPanel, library_identity=None)
        surfaces = self.registry.get_root_surfaces()
        assert _NodeSurface in surfaces
        assert _GraphSurface in surfaces
        assert surfaces.count(_NodeSurface) == 1

    def test_get_root_surfaces_excludes_hosted_surfaces(self):
        """A surface some panel hosts is drawn by that panel, not by a root host."""
        self.registry._register_class(_TestHostingPanel, library_identity=None)
        self.registry._register_class(_TestNestedPanel, library_identity=None)
        surfaces = self.registry.get_root_surfaces()
        assert _GraphSurface in surfaces
        assert _NestedSurface not in surfaces

    def test_get_root_surfaces_reads_the_panel_catalog(self):
        """Unregistering the last panel on a surface drops it — no ghost tab.

        ``_SURFACE_BY_ID`` never evicts, so a surface whose library was
        uninstalled would linger there; deriving from panels does not.
        """
        self.registry._register_class(_TestGraphPanel, library_identity=None)
        assert _GraphSurface in self.registry.get_root_surfaces()
        self.registry._unregister_class(_TestGraphPanel.class_identity.registry_key)
        assert _GraphSurface not in self.registry.get_root_surfaces()

    def test_unregister_removes_class(self):
        self.registry._register_class(_TestNodePanelA, library_identity=None)
        key = _TestNodePanelA.class_identity.registry_key
        self.registry._unregister_class(key)
        assert not self.registry.has(key)
        assert _TestNodePanelA not in self.registry.get_panels(_NodeSurface)

    def test_class_filter_accepts_decorated_subclass(self):
        assert self.registry._class_filter(_TestNodePanelA) is True

    def test_class_filter_rejects_panel_base(self):
        assert self.registry._class_filter(BasePanel) is False

    def test_class_filter_rejects_undecorated_subclass(self):
        assert self.registry._class_filter(_NotDecoratedPanel) is False

    def test_class_filter_rejects_non_class(self):
        assert self.registry._class_filter("not_a_class") is False
