# tests/ui/test_theme_registry.py
"""Tests for ThemeRegistry typed accessors and registration."""

import pytest
from haywire.ui.themes.registry import ThemeRegistry
from haywire.ui.themes.workbench import BaseTheme
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
        assert r._class_filter(BaseTheme) is False

    def test_class_filter_rejects_undecorated(self):
        class _Bare(BaseTheme):
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
        assert isinstance(t, BaseTheme)
        assert t.class_identity.theme_type == "workbench"

    def test_get_workbench_light(self):
        r = _make_registry()
        t = r.get_workbench(TestLightTheme.class_identity.registry_key)
        assert isinstance(t, BaseTheme)
        assert t.class_identity.theme_type == "workbench"

    def test_get_workbench_unknown_raises(self):
        r = _make_registry()
        with pytest.raises(KeyError):
            r.get_workbench("nonexistent")

    def test_get_workbench_rejects_a_node_theme_key(self):
        """get_workbench must not hand back a node-flavoured theme."""
        r = _make_registry()
        with pytest.raises(KeyError):
            r.get_workbench(TestNodeTheme.class_identity.registry_key)

    def test_get_node_theme_default(self):
        r = _make_registry()
        t = r.get_node_theme(TestNodeTheme.class_identity.registry_key)
        assert isinstance(t, BaseTheme)
        assert t.class_identity.theme_type == "node"

    def test_get_node_theme_unknown_raises(self):
        r = _make_registry()
        with pytest.raises(KeyError):
            r.get_node_theme("nonexistent")

    def test_get_node_theme_rejects_a_workbench_theme_key(self):
        """get_node_theme must not hand back a workbench-flavoured theme."""
        r = _make_registry()
        with pytest.raises(KeyError):
            r.get_node_theme(TestDarkTheme.class_identity.registry_key)

    def test_get_workbench_returns_fresh_instance(self):
        """Each call to get_workbench() returns a new instance."""
        r = _make_registry()
        t1 = r.get_workbench(TestDarkTheme.class_identity.registry_key)
        t2 = r.get_workbench(TestDarkTheme.class_identity.registry_key)
        assert t1 is not t2


# ---------------------------------------------------------------------------
# Custom theme registration
# ---------------------------------------------------------------------------


@theme(theme_type="workbench", registry_id="custom-test", label="Custom Test")
class _CustomTheme(BaseTheme):
    bg_page = "#abcdef"
    accent = "#123456"


@theme(theme_type="node", registry_id="custom-node-test", label="Custom Node Test")
class _CustomNodeTheme(BaseTheme):
    node_header_bg = "#aabbcc"


def test_deprecation_warning_stored_on_identity():
    @theme(
        theme_type="workbench",
        label="Old Theme",
        deprecation_warning="Use NewTheme instead.",
    )
    class OldTheme(BaseTheme):
        pass

    assert OldTheme.class_identity.deprecation_warning == "Use NewTheme instead."


def test_deprecation_warning_defaults_to_empty_string():
    @theme(theme_type="workbench", label="Fine Theme")
    class FineTheme(BaseTheme):
        pass

    assert FineTheme.class_identity.deprecation_warning == ""


def test_theme_type_is_required():
    with pytest.raises(TypeError):

        @theme(label="No type")  # type: ignore[call-arg]
        class _NoType(BaseTheme):
            pass


def test_theme_type_must_be_valid():
    with pytest.raises(ValueError, match="theme_type"):

        @theme(theme_type="bogus", label="Bad type")
        class _BadType(BaseTheme):
            pass


class TestCustomThemeRegistration:
    def test_custom_workbench_accessible(self):
        r = ThemeRegistry()
        r.register_workbench(_CustomTheme)
        t = r.get_workbench(_CustomTheme.class_identity.registry_key)
        assert isinstance(t, BaseTheme)

    def test_custom_node_theme_accessible(self):
        r = ThemeRegistry()
        r.register_node_theme(_CustomNodeTheme)
        t = r.get_node_theme(_CustomNodeTheme.class_identity.registry_key)
        assert isinstance(t, BaseTheme)

    def test_list_includes_custom(self):
        r = ThemeRegistry()
        r.register_workbench(_CustomTheme)
        assert _CustomTheme.class_identity.registry_key in r.list_workbench_keys()
