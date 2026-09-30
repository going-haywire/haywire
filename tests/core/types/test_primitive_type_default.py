"""A primitive type must declare a default value it can hold."""

import pytest

from haywire.core.types.base import PrimitiveType
from haywire.core.types.decorator import type as type_dec

pytestmark = pytest.mark.unit


def test_a_primitive_type_without_a_default_value_is_rejected():
    with pytest.raises(TypeError, match="needs a 'value' that is not None"):

        @type_dec(label="NoValue", default={})
        class NoValue(PrimitiveType[str]):
            pass


def test_a_primitive_type_with_a_none_default_is_rejected():
    with pytest.raises(TypeError, match="OPTIONAL"):

        @type_dec(label="NoneValue", default={"value": None})
        class NoneValue(PrimitiveType[str]):
            pass


def test_a_primitive_type_with_a_value_is_accepted():
    @type_dec(label="HasValue", default={"value": ""})
    class HasValue(PrimitiveType[str]):
        pass

    assert HasValue.class_identity.default == {"value": ""}


def test_a_derived_primitive_type_keeps_its_parents_default():
    from haywire.barn.builtin.types import STRING

    @type_dec(label="Derived")
    class Derived(STRING):
        pass

    assert Derived.class_identity.default == {"value": ""}
