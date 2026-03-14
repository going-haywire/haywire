# tests/ui/test_node_theme.py
"""Tests for NodeTheme field collection and get_color()."""

import pytest
from haywire.ui.themes.node_theme import NodeTheme
from haywire.ui.themes.workbench import _FieldProxy
from haywire.ui.themes.decorator import theme
from haybale_testing.themes.node import TestNodeTheme


# ---------------------------------------------------------------------------
# Field collection
# ---------------------------------------------------------------------------

class TestNodeThemeFieldCollection:

    def test_string_attrs_collected(self):
        class _T(NodeTheme):
            header_bg   = '#252540'
            port_inlet  = '#4a90d9'

        assert 'header_bg'  in _T._fields
        assert 'port_inlet' in _T._fields

    def test_private_excluded(self):
        class _T(NodeTheme):
            _internal = 'ignored'
            header_bg = '#111111'

        assert '_internal' not in _T._fields

    def test_proxy_wraps_default(self):
        class _T(NodeTheme):
            header_bg = '#abcdef'

        proxy = _T._fields['header_bg']
        assert isinstance(proxy, _FieldProxy)
        assert proxy._default == '#abcdef'

    def test_fields_fresh_per_class(self):
        class _A(NodeTheme):
            a_token = '#aaaaaa'

        class _B(NodeTheme):
            b_token = '#bbbbbb'

        assert 'b_token' not in _A._fields
        assert 'a_token' not in _B._fields

    def test_base_class_has_empty_fields(self):
        assert NodeTheme._fields == {}


# ---------------------------------------------------------------------------
# get_color()
# ---------------------------------------------------------------------------

class TestGetColor:

    def test_get_color_known_token(self):
        t = TestNodeTheme()
        assert t.get_color('header_bg') == '#abcdef'

    def test_get_color_unknown_returns_empty(self):
        t = TestNodeTheme()
        assert t.get_color('nonexistent_token') == ''

    def test_node_theme_has_port_colors(self):
        t = TestNodeTheme()
        assert t.get_color('port_inlet')  != ''
        assert t.get_color('port_outlet') != ''

    def test_node_theme_has_error_colors(self):
        t = TestNodeTheme()
        assert t.get_color('error_bg')     != ''
        assert t.get_color('error_border') != ''


# ---------------------------------------------------------------------------
# @theme decorator
# ---------------------------------------------------------------------------

class TestThemeDecorator:

    def test_class_identity_set(self):
        assert hasattr(TestNodeTheme, 'class_identity')
        assert TestNodeTheme.class_identity.registry_id == 'test-node'
        assert TestNodeTheme.class_identity.theme_type  == 'node'

    def test_registry_key_format(self):
        expected = 'testing:theme:node:test-node'
        assert TestNodeTheme.class_identity.registry_key == expected

    def test_label(self):
        assert TestNodeTheme.class_identity.label == 'Test Node'

    def test_custom_decorator(self):
        @theme(registry_id='_test_custom_node', label='Custom')
        class _T(NodeTheme):
            header_bg = '#ffffff'

        assert _T.class_identity.registry_id == '_test_custom_node'
        assert _T.class_identity.theme_type  == 'node'
        assert _T.class_identity.label       == 'Custom'
