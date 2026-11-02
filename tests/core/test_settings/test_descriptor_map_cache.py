"""Settings._settings_descriptors(): built once per class, read-only, never shared with a subclass."""

import pytest

from haywire.barn.builtin.types import INT
from haywire.core.settings import NodeSettings, setting, settings_fields

pytestmark = pytest.mark.unit


class _Base(NodeSettings):
    a = setting[INT](1)


class _Child(_Base):
    b = setting[INT](2)


def test_the_map_is_built_once_per_class():
    assert _Base._settings_descriptors() is _Base._settings_descriptors()


def test_a_subclass_gets_its_own_map_with_inherited_fields_first():
    _Base._settings_descriptors()
    assert list(_Child._settings_descriptors()) == ["a", "b"]
    assert list(_Base._settings_descriptors()) == ["a"]


def test_the_map_is_read_only():
    with pytest.raises(TypeError):
        _Base._settings_descriptors()["x"] = _Base.a  # type: ignore[index]


def test_settings_fields_serves_the_same_map():
    assert settings_fields(_Child) is _Child._settings_descriptors()
    assert settings_fields(_Child()) is _Child._settings_descriptors()
