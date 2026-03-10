# tests/core/test_settings/test_schema.py
"""Tests for _SettingsSchema, NodeSettings, LibrarySettings, GlobalSettings."""

import pytest
from haywire.core.settings.descriptors import setting
from haywire.core.settings.schema import (
    _SettingsSchema,
    NodeSettings,
    LibrarySettings,
    GlobalSettings,
    _EmptyNodeSettings,
)
from haywire.core.settings.decorators import library_settings


# ---------------------------------------------------------------------------
# GlobalSettings — namespace kwarg wires _field_key immediately
# ---------------------------------------------------------------------------

class _GS(GlobalSettings, namespace='gs.test'):
    alpha: float = setting(0.1, label='Alpha')
    beta: str    = setting('x',  label='Beta')


class TestGlobalSettings:

    def test_fields_collected(self):
        assert 'alpha' in _GS._fields
        assert 'beta' in _GS._fields

    def test_field_keys(self):
        assert _GS._fields['alpha']._field_key == 'gs.test.alpha'
        assert _GS._fields['beta']._field_key  == 'gs.test.beta'

    def test_namespace(self):
        assert _GS._namespace == 'gs.test'

    def test_fields_fresh_per_class(self):
        """Subclass _fields must not include parent's fields."""
        class _GS2(GlobalSettings, namespace='gs.test2'):
            gamma: int = setting(99)

        assert 'gamma' in _GS2._fields
        assert 'alpha' not in _GS2._fields
        assert 'beta' not in _GS2._fields


# ---------------------------------------------------------------------------
# NodeSettings — namespace empty until wired by BaseNode
# ---------------------------------------------------------------------------

class _NS(NodeSettings):
    width:  int   = setting(512, min=1, max=8192, label='Width')
    height: int   = setting(512, min=1, max=8192, label='Height')


class _NSExplicit(NodeSettings, namespace='explicit.ns'):
    value: float = setting(0.0)


class TestNodeSettings:

    def test_fields_collected(self):
        assert 'width'  in _NS._fields
        assert 'height' in _NS._fields

    def test_namespace_empty_by_default(self):
        assert _NS._namespace == ''

    def test_field_key_empty_until_wired(self):
        assert _NS._fields['width']._field_key == ''

    def test_explicit_namespace_kwarg(self):
        assert _NSExplicit._namespace == 'explicit.ns'
        assert _NSExplicit._fields['value']._field_key == 'explicit.ns.value'

    def test_fields_isolated_from_sibling(self):
        """Two sibling NodeSettings subclasses must not share fields."""
        class _A(NodeSettings):
            x: int = setting(1)

        class _B(NodeSettings):
            y: int = setting(2)

        assert 'x' not in _B._fields
        assert 'y' not in _A._fields


# ---------------------------------------------------------------------------
# LibrarySettings + @library_settings decorator
# ---------------------------------------------------------------------------

@library_settings(namespace='mylib', label='My Library')
class _LS(LibrarySettings):
    rate: int  = setting(4, min=1, max=20, label='Rate')
    mode: str  = setting('fast', choices=['fast', 'slow'], label='Mode')


class TestLibrarySettings:

    def test_namespace_set_by_decorator(self):
        assert _LS._namespace == 'mylib'

    def test_field_key_set_by_decorator(self):
        assert _LS._fields['rate']._field_key  == 'mylib.rate'
        assert _LS._fields['mode']._field_key  == 'mylib.mode'

    def test_class_identity_set(self):
        assert hasattr(_LS, 'class_identity')
        assert _LS.class_identity.namespace    == 'mylib'
        assert _LS.class_identity.registry_key == '__system__:settings:mylib'
        assert _LS.class_identity.label        == 'My Library'

    def test_auto_register_flag(self):
        assert _LS._auto_register is True


# ---------------------------------------------------------------------------
# _EmptyNodeSettings
# ---------------------------------------------------------------------------

class TestEmptyNodeSettings:

    def test_no_fields(self):
        assert _EmptyNodeSettings._fields == {}

    def test_namespace_empty(self):
        assert _EmptyNodeSettings._namespace == ''


# ---------------------------------------------------------------------------
# Inheritance isolation
# ---------------------------------------------------------------------------

class TestFieldIsolation:

    def test_parent_fields_not_inherited_into_child_fields(self):
        """
        Python class inheritance lets child *access* parent class attrs, but
        _fields must only contain descriptors declared in *that class's* body.
        """
        class _Parent(GlobalSettings, namespace='iso.parent'):
            a: int = setting(1)

        class _Child(GlobalSettings, namespace='iso.child'):
            b: int = setting(2)

        assert 'a' not in _Child._fields
        assert 'b' not in _Parent._fields
