"""F21: a framework schema reaches every registry, whenever either was built."""

import pytest

from haywire.barn.builtin.types import INT
from haywire.core.settings import FrameworkSettings, setting
from haywire.core.settings.registry import SettingsRegistry

pytestmark = pytest.mark.unit


def test_a_schema_defined_later_reaches_an_earlier_registry():
    first = SettingsRegistry()
    second = SettingsRegistry()

    class _LateSchema(FrameworkSettings, namespace="test.f21.late"):
        value = setting[INT](1, label="Value")

    key = _LateSchema.class_identity.registry_key
    assert first.has(key)
    assert second.has(key)


def test_a_registry_built_later_takes_a_schema_already_registered():
    SettingsRegistry()

    class _EarlySchema(FrameworkSettings, namespace="test.f21.early"):
        value = setting[INT](1, label="Value")

    later = SettingsRegistry()
    assert later.has(_EarlySchema.class_identity.registry_key)
