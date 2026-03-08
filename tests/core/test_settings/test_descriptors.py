# tests/core/test_settings/test_descriptors.py
"""Tests for the setting(), shadow(), and watch() descriptor classes."""

import pytest
from haywire.core.settings.descriptors import setting, shadow, watch, _SettingDescriptor
from haywire.core.settings.schema import NodeSettings, GlobalSettings
from haywire.core.settings.decorators import library_settings
from haywire.core.settings.schema import LibrarySettings


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

class _FakeGlobal(GlobalSettings, namespace='test.global'):
    threshold: float = setting(0.5, min=0.0, max=1.0, label='Threshold', category='quality')
    label_text: str  = setting('hello', label='Label', description='A text field')
    enabled: bool    = setting(True, label='Enabled')
    count: int       = setting(4, min=1, max=20, label='Count')


# ---------------------------------------------------------------------------
# setting() descriptor
# ---------------------------------------------------------------------------

class TestSettingDescriptor:

    def test_attr_name_set_by_set_name(self):
        """__set_name__ sets _attr_name to the field name."""
        assert _FakeGlobal._fields['threshold']._attr_name == 'threshold'

    def test_full_key_set_by_schema(self):
        """Schema __init_subclass__ sets _full_key = namespace.name."""
        assert _FakeGlobal._fields['threshold']._full_key == 'test.global.threshold'

    def test_default_value_preserved(self):
        assert _FakeGlobal._fields['threshold']._default == 0.5
        assert _FakeGlobal._fields['label_text']._default == 'hello'
        assert _FakeGlobal._fields['enabled']._default is True
        assert _FakeGlobal._fields['count']._default == 4

    def test_min_max_preserved(self):
        d = _FakeGlobal._fields['threshold']
        assert d._min == 0.0
        assert d._max == 1.0

    def test_label_and_description(self):
        d = _FakeGlobal._fields['label_text']
        assert d._label == 'Label'
        assert d._description == 'A text field'

    def test_category_and_order_defaults(self):
        d = _FakeGlobal._fields['count']
        assert d._category == ''
        assert d._order == 0

    def test_flags(self):
        d = _FakeGlobal._fields['threshold']
        assert d._panel_visible is True
        assert d._stored is True
        assert d._read_only is False

    def test_class_access_returns_descriptor(self):
        """Accessing the descriptor on the class returns the descriptor object."""
        d = _FakeGlobal.threshold
        assert isinstance(d, _SettingDescriptor)

    def test_instance_access_raises(self):
        """Accessing a setting on an instance raises AttributeError."""
        with pytest.raises(AttributeError):
            _ = _FakeGlobal().threshold


# ---------------------------------------------------------------------------
# shadow() descriptor
# ---------------------------------------------------------------------------

@library_settings(namespace='shadow_lib')
class _ShadowLib(LibrarySettings):
    bg_color: str = setting('#1e1e2e', label='BG Color', category='appearance')
    timeout: int  = setting(30, min=5, max=300, label='Timeout')


class _ShadowedNode(NodeSettings):
    bg_color: str = shadow(_ShadowLib.bg_color)
    timeout: int  = shadow(_ShadowLib.timeout)


class TestShadowDescriptor:

    def test_global_key_stored_as_string(self):
        """shadow() stores the global_key as a string, not a descriptor reference."""
        d = _ShadowedNode._fields['bg_color']
        assert d._global_key == 'shadow_lib.bg_color'

    def test_inherits_default(self):
        assert _ShadowedNode._fields['bg_color']._default == '#1e1e2e'

    def test_inherits_label(self):
        assert _ShadowedNode._fields['bg_color']._label == 'BG Color'

    def test_inherits_category(self):
        assert _ShadowedNode._fields['bg_color']._category == 'appearance'

    def test_inherits_min_max(self):
        d = _ShadowedNode._fields['timeout']
        assert d._min == 5
        assert d._max == 300

    def test_flags(self):
        d = _ShadowedNode._fields['bg_color']
        assert d._panel_visible is True
        assert d._stored is True
        assert d._read_only is False

    def test_on_change_not_inherited(self):
        """shadow() does not inherit on_change from global descriptor."""
        assert _ShadowedNode._fields['bg_color']._on_change == ''


# ---------------------------------------------------------------------------
# watch() descriptor
# ---------------------------------------------------------------------------

class _WatchedNode(NodeSettings):
    bg_color: str = watch(_ShadowLib.bg_color)


class TestWatchDescriptor:

    def test_global_key(self):
        assert _WatchedNode._fields['bg_color']._global_key == 'shadow_lib.bg_color'

    def test_flags(self):
        d = _WatchedNode._fields['bg_color']
        assert d._panel_visible is False
        assert d._stored is False
        assert d._read_only is True

    def test_inherits_default(self):
        assert _WatchedNode._fields['bg_color']._default == '#1e1e2e'


# ---------------------------------------------------------------------------
# choices
# ---------------------------------------------------------------------------

class _ChoicesSchema(GlobalSettings, namespace='test.choices'):
    algorithm: str = setting('lanczos', choices=['nearest', 'bilinear', 'lanczos'], label='Algorithm')


class TestChoicesDescriptor:

    def test_choices_preserved(self):
        d = _ChoicesSchema._fields['algorithm']
        assert d._choices == ['nearest', 'bilinear', 'lanczos']


# ---------------------------------------------------------------------------
# Repr
# ---------------------------------------------------------------------------

class TestDescriptorRepr:

    def test_repr(self):
        d = _FakeGlobal._fields['threshold']
        r = repr(d)
        assert 'test.global.threshold' in r
        assert '0.5' in r
