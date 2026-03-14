# tests/ui/test_workbench_theme.py
"""Tests for WorkbenchTheme field collection and to_css_vars()."""

import pytest
from haywire.ui.themes.workbench import WorkbenchTheme, _FieldProxy
from haywire.ui.themes.decorator import theme
from haybale_testing.themes.workbench import TestDarkTheme, TestLightTheme


# ---------------------------------------------------------------------------
# Field collection
# ---------------------------------------------------------------------------

class TestWorkbenchThemeFieldCollection:

    def test_plain_string_attrs_collected(self):
        class _T(WorkbenchTheme):
            bg_page    = '#111111'
            bg_surface = '#222222'

        assert 'bg_page'    in _T._fields
        assert 'bg_surface' in _T._fields

    def test_private_attrs_excluded(self):
        class _T(WorkbenchTheme):
            _internal = 'ignored'
            bg_page   = '#111111'

        assert '_internal' not in _T._fields
        assert 'bg_page' in _T._fields

    def test_fields_are_field_proxies(self):
        class _T(WorkbenchTheme):
            bg_page = '#abcdef'

        proxy = _T._fields['bg_page']
        assert isinstance(proxy, _FieldProxy)
        assert proxy._default == '#abcdef'

    def test_fields_fresh_per_class(self):
        class _A(WorkbenchTheme):
            a_color = '#aaaaaa'

        class _B(WorkbenchTheme):
            b_color = '#bbbbbb'

        assert 'b_color' not in _A._fields
        assert 'a_color' not in _B._fields

    def test_base_class_has_empty_fields(self):
        assert WorkbenchTheme._fields == {}


# ---------------------------------------------------------------------------
# to_css_vars()
# ---------------------------------------------------------------------------

class TestToCssVars:

    def test_returns_dict_with_hw_prefix(self):
        t = TestDarkTheme()
        css = t.to_css_vars()
        for key in css:
            assert key.startswith('--hw-'), f"CSS var {key!r} should start with '--hw-'"

    def test_dark_bg_page(self):
        t = TestDarkTheme()
        css = t.to_css_vars()
        assert css['--hw-bg-page'] == '#111111'

    def test_light_bg_page(self):
        t = TestLightTheme()
        css = t.to_css_vars()
        assert css['--hw-bg-page'] == '#ffffff'

    def test_custom_theme_values(self):
        @theme(registry_id='_test_css_vars')
        class _T(WorkbenchTheme):
            bg_page = '#aabbcc'
            accent  = '#112233'

        t = _T()
        css = t.to_css_vars()
        assert css.get('--hw-bg-page') == '#aabbcc'
        assert css.get('--hw-accent')  == '#112233'

    def test_dark_theme_has_all_major_tokens(self):
        t = TestDarkTheme()
        css = t.to_css_vars()
        for token in ('--hw-bg-page', '--hw-accent', '--hw-text-body',
                      '--hw-node-bg', '--hw-canvas-bg', '--hw-topbar-bg',
                      '--hw-statusbar-bg', '--hw-console-bg'):
            assert token in css, f"Missing token: {token}"

    def test_missing_field_not_in_result(self):
        """A field listed in _CSS_TOKEN_MAP but missing from _fields is silently skipped."""
        class _Sparse(WorkbenchTheme):
            bg_page = '#ffffff'
            # nothing else

        t = _Sparse()
        css = t.to_css_vars()
        assert '--hw-bg-page' in css
        assert '--hw-accent' not in css   # not defined in _Sparse


# ---------------------------------------------------------------------------
# @theme decorator
# ---------------------------------------------------------------------------

class TestThemeDecorator:

    def test_class_identity_set(self):
        assert hasattr(TestDarkTheme, 'class_identity')
        assert TestDarkTheme.class_identity.registry_id == 'test-dark'
        assert TestDarkTheme.class_identity.theme_type  == 'workbench'

    def test_registry_key_format(self):
        assert TestDarkTheme.class_identity.registry_key == 'testing:theme:workbench:test-dark'
