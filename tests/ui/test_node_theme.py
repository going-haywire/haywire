# tests/ui/test_node_theme.py
"""Tests for BaseTheme field collection and to_css_vars(), from the node-authoring side.

BaseTheme is one class for both flavours (see test_workbench_theme.py for the
workbench-authoring side of the same mechanics) — these tests exercise
@theme(theme_type='node') specifically: what a node-scoped theme is allowed
to declare and how its declarations resolve through to_css_vars().
"""

from haywire.ui.themes.workbench import BaseTheme, _FieldProxy
from haywire.ui.themes.decorator import theme
from haybale_testing.themes.node import TestNodeTheme


# ---------------------------------------------------------------------------
# Field collection
# ---------------------------------------------------------------------------


class TestNodeThemeFieldCollection:
    def test_string_attrs_collected(self):
        class _T(BaseTheme):
            node_header_bg = "#252540"
            node_bg = "#4a90d9"

        assert "node_header_bg" in _T._fields
        assert "node_bg" in _T._fields

    def test_private_excluded(self):
        class _T(BaseTheme):
            _internal = "ignored"
            node_header_bg = "#111111"

        assert "_internal" not in _T._fields

    def test_proxy_wraps_default(self):
        class _T(BaseTheme):
            node_header_bg = "#abcdef"

        proxy = _T._fields["node_header_bg"]
        assert isinstance(proxy, _FieldProxy)
        assert proxy._default == "#abcdef"

    def test_fields_fresh_per_class(self):
        class _A(BaseTheme):
            node_bg = "#aaaaaa"

        class _B(BaseTheme):
            node_header_bg = "#bbbbbb"

        assert "node_header_bg" not in _A._fields
        assert "node_bg" not in _B._fields

    def test_base_class_has_empty_fields(self):
        assert BaseTheme._fields == {}


# ---------------------------------------------------------------------------
# to_css_vars() — the only way to read a theme
# ---------------------------------------------------------------------------


class TestToCssVars:
    def test_emits_mapped_tokens(self):
        v = TestNodeTheme().to_css_vars()
        assert v["--hw-node-bg"] == "#123456"
        assert v["--hw-node-border-color"] == "#234567"

    def test_unmapped_field_is_dropped(self):
        """A field absent from the shared token map produces no var, silently.

        Documented rather than desired: to_css_vars walks the map, not _fields,
        so a mistyped token in a theme subclass fails without a signal.
        """

        class _T(BaseTheme):
            not_a_real_token = "#ff0000"

        assert "#ff0000" not in str(_T().to_css_vars().values())

    def test_length_tokens_carry_their_unit(self):
        """var() is textual substitution — a bare int would emit invalid CSS."""
        v = TestNodeTheme().to_css_vars()
        assert v["--hw-node-border-width"].endswith("px")
        assert v["--hw-node-border-radius"].endswith("px")

    def test_a_token_may_hold_a_gradient(self):
        """Why every consumer must use `background`, not `background-color`."""

        class _T(BaseTheme):
            node_bg = "linear-gradient(135deg, #667eea 0%, #764ba2 100%)"

        assert _T().to_css_vars()["--hw-node-bg"].startswith("linear-gradient(")

    def test_a_node_theme_may_declare_any_workbench_token(self):
        """No curated node-scoped subset — a node-authored theme may set
        text_body, bg_input, accent, ... anything in _CSS_TOKEN_MAP."""

        class _T(BaseTheme):
            text_body = "rgba(255,255,255,0.9)"
            bg_input = "#0a0a12"
            accent = "#ff00aa"

        v = _T().to_css_vars()
        assert v["--hw-text-body"] == "rgba(255,255,255,0.9)"
        assert v["--hw-bg-input"] == "#0a0a12"
        assert v["--hw-accent"] == "#ff00aa"

    def test_tier_2_tokens_are_declarable_but_structurally_inert_at_node_tier(self):
        """node_selected/active/shadow are real, mapped tokens a node-authored
        theme may set — nothing stops it. They're consumed on an ANCESTOR of
        the node tier's element ([data-node-id] vs .ui-node-slot), so a
        node-scoped theme's value for them is written but never visibly
        applied. The graph and global tiers sit above that ancestor and DO
        apply them — this is a DOM-position fact for the write path (see
        ui_node.py / graph_canvas_manager.py) to know, not a restriction on
        the theme class itself."""
        for token in ("node_selected", "node_active", "node_shadow"):
            assert token in BaseTheme._CSS_TOKEN_MAP


# ---------------------------------------------------------------------------
# @theme(theme_type='node') decorator
# ---------------------------------------------------------------------------


class TestNodeThemeDecorator:
    def test_class_identity_set(self):
        assert TestNodeTheme.class_identity.registry_id == "TestNodeTheme"
        assert TestNodeTheme.class_identity.theme_type == "node"

    def test_registry_key_format(self):
        """Standard 3-segment reg_key — theme_type lives on class_identity,
        not encoded into the key."""
        expected = "haybale-testing:theme:TestNodeTheme"
        assert TestNodeTheme.class_identity.registry_key == expected

    def test_label(self):
        assert TestNodeTheme.class_identity.label == "Test Node"

    def test_custom_decorator(self):
        @theme(theme_type="node", registry_id="_test_custom_node", label="Custom")
        class _T(BaseTheme):
            node_header_bg = "#ffffff"

        assert _T.class_identity.registry_id == "_test_custom_node"
        assert _T.class_identity.theme_type == "node"
        assert _T.class_identity.label == "Custom"

    def test_rejects_non_theme_subclass(self):
        import pytest

        with pytest.raises(TypeError):

            @theme(theme_type="node", label="Not a theme")
            class _NotATheme:
                pass
