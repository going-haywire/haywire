"""``TypeRegistry.get_type_for_python_type`` resolves value types only."""

from dataclasses import replace

import pytest

from haywire.barn.builtin.wires import ControlWire, DataWire
from haywire.core.types import PrimitiveType
from haywire.core.types import type as haywire_type
from haywire.core.types.registry import TypeRegistry


@haywire_type(wire_type=DataWire, label="Dict Value", default={"value": {}})
class _DictValue(PrimitiveType[dict]):
    """A value type wrapping `dict`."""


@haywire_type(wire_type=ControlWire, label="Dict Signal", default={"value": {}})
class _DictSignal(PrimitiveType[dict]):
    """A signal type wrapping `dict`, as `EXEC` does."""


# The lookup prefers a haywire-core key, so the signal type gets one: it must lose anyway.
_DictSignal.class_identity = replace(_DictSignal.class_identity, registry_key="haywire-core:type:DictSignal")
_DictValue.class_identity = replace(_DictValue.class_identity, registry_key="some-library:type:DictValue")


@pytest.mark.unit
def test_a_signal_type_never_answers_for_a_python_type():
    registry = TypeRegistry()
    registry._register(_DictSignal.class_identity.registry_key, _DictSignal)
    registry._register(_DictValue.class_identity.registry_key, _DictValue)

    assert registry.get_type_for_python_type(dict) is _DictValue


@pytest.mark.unit
def test_a_python_type_only_signal_types_wrap_resolves_to_nothing():
    registry = TypeRegistry()
    registry._register(_DictSignal.class_identity.registry_key, _DictSignal)

    assert registry.get_type_for_python_type(dict) is None


@pytest.mark.integration
@pytest.mark.parametrize(
    ("py_type", "expected_key"),
    [
        (dict, "haybale-core:type:DICT"),
        (str, "haywire-core:type:STRING"),
        (int, "haywire-core:type:INT"),
        (float, "haywire-core:type:FLOAT"),
        (bool, "haywire-core:type:BOOL"),
    ],
)
def test_the_loaded_libraries_resolve_each_python_type_to_its_value_type(
    library_system, py_type, expected_key
):
    from haywire.core.di.config import get_type_registry

    resolved = get_type_registry().get_type_for_python_type(py_type)

    assert resolved is not None
    assert resolved.class_identity.registry_key == expected_key
