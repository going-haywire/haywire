# tests/ui/test_theme_registry.py
"""Tests for ThemeRegistry typed accessors and registration."""

import pytest
from haywire.ui.themes.registry import ThemeRegistry
from haywire.ui.themes.workbench import WorkbenchTheme
from haywire.ui.themes.node_theme import NodeTheme
from haywire.ui.themes.decorator import theme
from haybale_testing.themes.workbench import TestDarkTheme, TestLightTheme
from haybale_testing.themes.node import TestNodeTheme


# ---------------------------------------------------------------------------
# Helpers — fresh registry per test
# ---------------------------------------------------------------------------


def _make_registry() -> ThemeRegistry:
    r = ThemeRegistry()
    r.register_workbench(TestDarkTheme)
    r.register_workbench(TestLightTheme)
    r.register_node_theme(TestNodeTheme)
    return r


# ---------------------------------------------------------------------------
# Registration
# ---------------------------------------------------------------------------


class TestThemeRegistration:
    def test_register_workbench(self):
        r = _make_registry()
        keys = r.list_workbench_keys()
        assert TestDarkTheme.class_identity.registry_key in keys
        assert TestLightTheme.class_identity.registry_key in keys

    def test_register_node_theme(self):
        r = _make_registry()
        keys = r.list_node_theme_keys()
        assert TestNodeTheme.class_identity.registry_key in keys

    def test_class_filter_accepts_decorated(self):
        r = ThemeRegistry()
        assert r._class_filter(TestDarkTheme) is True

    def test_class_filter_rejects_base(self):
        r = ThemeRegistry()
        assert r._class_filter(WorkbenchTheme) is False
        assert r._class_filter(NodeTheme) is False

    def test_class_filter_rejects_undecorated(self):
        class _Bare(WorkbenchTheme):
            bg_page = "#000"

        r = ThemeRegistry()
        assert r._class_filter(_Bare) is False


# ---------------------------------------------------------------------------
# Typed accessors
# ---------------------------------------------------------------------------


class TestThemeAccessors:
    def test_get_workbench_dark(self):
        r = _make_registry()
        t = r.get_workbench(TestDarkTheme.class_identity.registry_key)
        assert isinstance(t, WorkbenchTheme)

    def test_get_workbench_light(self):
        r = _make_registry()
        t = r.get_workbench(TestLightTheme.class_identity.registry_key)
        assert isinstance(t, WorkbenchTheme)

    def test_get_workbench_unknown_raises(self):
        r = _make_registry()
        with pytest.raises(KeyError):
            r.get_workbench("nonexistent")

    def test_get_node_theme_default(self):
        r = _make_registry()
        t = r.get_node_theme(TestNodeTheme.class_identity.registry_key)
        assert isinstance(t, NodeTheme)

    def test_get_node_theme_unknown_raises(self):
        r = _make_registry()
        with pytest.raises(KeyError):
            r.get_node_theme("nonexistent")

    def test_get_workbench_returns_fresh_instance(self):
        """Each call to get_workbench() returns a new instance."""
        r = _make_registry()
        t1 = r.get_workbench(TestDarkTheme.class_identity.registry_key)
        t2 = r.get_workbench(TestDarkTheme.class_identity.registry_key)
        assert t1 is not t2


# ---------------------------------------------------------------------------
# Custom theme registration
# ---------------------------------------------------------------------------


@theme(registry_id="custom-test", label="Custom Test")
class _CustomTheme(WorkbenchTheme):
    bg_page = "#abcdef"
    accent = "#123456"


@theme(registry_id="custom-node-test", label="Custom Node Test")
class _CustomNodeTheme(NodeTheme):
    header_bg = "#aabbcc"


class TestCustomThemeRegistration:
    def test_custom_workbench_accessible(self):
        r = ThemeRegistry()
        r.register_workbench(_CustomTheme)
        t = r.get_workbench(_CustomTheme.class_identity.registry_key)
        assert isinstance(t, WorkbenchTheme)

    def test_custom_node_theme_accessible(self):
        r = ThemeRegistry()
        r.register_node_theme(_CustomNodeTheme)
        t = r.get_node_theme(_CustomNodeTheme.class_identity.registry_key)
        assert isinstance(t, NodeTheme)

    def test_list_includes_custom(self):
        r = ThemeRegistry()
        r.register_workbench(_CustomTheme)
        assert _CustomTheme.class_identity.registry_key in r.list_workbench_keys()
