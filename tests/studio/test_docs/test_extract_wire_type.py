"""The generated type docs name a type's wire type, and a container's has none."""

import pytest

from haywire_studio.packaging.docs.extract import _extra_for_kind

pytestmark = pytest.mark.unit


def test_a_value_type_names_its_wire_type():
    from haywire.barn.builtin.types import EXEC

    assert _extra_for_kind("type", EXEC, EXEC.class_identity)["wire_type"] == "haywire-core:wire:ControlWire"


def test_a_container_names_none():
    from haybale_core.types import ArrayType

    assert _extra_for_kind("type", ArrayType, ArrayType.class_identity)["wire_type"] is None
