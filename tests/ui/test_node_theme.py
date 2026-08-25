# tests/ui/test_node_theme.py
"""Tests for NodeTheme field collection and to_css_vars()."""

from haywire.ui.themes.node_theme import NodeTheme
from haywire.ui.themes.workbench import NODE_TIER_TOKENS, WorkbenchTheme, _FieldProxy
from haywire.ui.themes.decorator import theme
from haybale_testing.themes.node import TestNodeTheme


# ---------------------------------------------------------------------------
# Field collection
# ---------------------------------------------------------------------------


class TestNodeThemeFieldCollection:
    def test_string_attrs_collected(self):
        class _T(NodeTheme):
            node_header_bg = "#252540"
            node_bg = "#4a90d9"

        assert "node_header_bg" in _T._fields
        assert "node_bg" in _T._fields

    def test_private_excluded(self):
        class _T(NodeTheme):
            _internal = "ignored"
            node_header_bg = "#111111"

        assert "_internal" not in _T._fields

    def test_proxy_wraps_default(self):
        class _T(NodeTheme):
            node_header_bg = "#abcdef"

        proxy = _T._fields["node_header_bg"]
        assert isinstance(proxy, _FieldProxy)
        assert proxy._default == "#abcdef"

    def test_fields_fresh_per_class(self):
        class _A(NodeTheme):
            node_bg = "#aaaaaa"

        class _B(NodeTheme):
            node_header_bg = "#bbbbbb"

        assert "node_header_bg" not in _A._fields
        assert "node_bg" not in _B._fields

    def test_base_class_has_empty_fields(self):
        assert NodeTheme._fields == {}


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

        class _T(NodeTheme):
            not_a_real_token = "#ff0000"

        assert "#ff0000" not in str(_T().to_css_vars().values())

    def test_length_tokens_carry_their_unit(self):
        """var() is textual substitution — a bare int would emit invalid CSS."""
        v = TestNodeTheme().to_css_vars()
        assert v["--hw-node-border-width"].endswith("px")
        assert v["--hw-node-border-radius"].endswith("px")

    def test_a_token_may_hold_a_gradient(self):
        """Why every consumer must use `background`, not `background-color`."""

        class _T(NodeTheme):
            node_bg = "linear-gradient(135deg, #667eea 0%, #764ba2 100%)"

        assert _T().to_css_vars()["--hw-node-bg"].startswith("linear-gradient(")

    def test_node_and_workbench_share_one_token_map(self):
        """A NodeTheme cannot name a token the workbench does not have.

        The shared map is what makes "NodeTheme is a subset of WorkbenchTheme"
        structural rather than conventional — two maps could drift on a var
        name and a node theme would silently override nothing.
        """
        assert NodeTheme._CSS_TOKEN_MAP is WorkbenchTheme._CSS_TOKEN_MAP

    def test_every_node_tier_token_is_mapped(self):
        for token in NODE_TIER_TOKENS:
            assert token in NodeTheme._CSS_TOKEN_MAP

    def test_tier_2_tokens_are_not_node_tier(self):
        """node_selected/active/shadow are consumed on an ANCESTOR of the slot,
        so a node-tier theme cannot reach them — they must stay out of the list
        a node tier writes."""
        for token in ("node_selected", "node_active", "node_shadow"):
            assert token in NodeTheme._CSS_TOKEN_MAP
            assert token not in NODE_TIER_TOKENS


# ---------------------------------------------------------------------------
# @theme decorator
# ---------------------------------------------------------------------------


class TestThemeDecorator:
    def test_class_identity_set(self):
        assert TestNodeTheme.class_identity.registry_id == "TestNodeTheme"
        assert TestNodeTheme.class_identity.theme_type == "node"

    def test_registry_key_format(self):
        expected = "haybale-testing:theme:node:TestNodeTheme"
        assert TestNodeTheme.class_identity.registry_key == expected

    def test_label(self):
        assert TestNodeTheme.class_identity.label == "Test Node"

    def test_custom_decorator(self):
        @theme(registry_id="_test_custom_node", label="Custom")
        class _T(NodeTheme):
            node_header_bg = "#ffffff"

        assert _T.class_identity.registry_id == "_test_custom_node"
        assert _T.class_identity.theme_type == "node"
        assert _T.class_identity.label == "Custom"
