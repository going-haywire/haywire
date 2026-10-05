"""Field serialization: absence saves as null, a present value through the field's hook (Q14, Q25)."""

import json
from dataclasses import dataclass

import pytest

pytestmark = pytest.mark.integration


def _round_trip(type_cls, value):
    """Save a field of *type_cls* holding *value* through JSON and load it into a fresh field."""
    field = type_cls.create_field()
    field.set_value(value)
    saved = json.loads(json.dumps(field.to_dict()))
    restored = type_cls.create_field()
    restored.from_dict(saved)
    return saved, restored.get_value()


class TestAbsence:
    def test_an_absent_callback_saves_null_and_loads_absent(self, library_system):
        from haywire.barn.builtin.types import CALLBACK

        saved, loaded = _round_trip(CALLBACK, None)

        assert saved is None
        assert loaded is None

    def test_an_absent_dataclass_saves_null_and_loads_absent(self, library_system):
        from haywire.barn.builtin.wires import CallbackWire
        from haywire.core.types import BaseType
        from haywire.core.types import type as type_dec

        @type_dec(wire_type=CallbackWire, label="Probe Record", default=None)
        @dataclass
        class PROBE_RECORD(BaseType):
            name: str = ""

        assert _round_trip(PROBE_RECORD, None) == (None, None)
        assert _round_trip(PROBE_RECORD, PROBE_RECORD(name="n"))[1] == PROBE_RECORD(name="n")

    def test_a_present_callback_round_trips(self, library_system):
        from haywire.barn.builtin.types import CALLBACK

        assert _round_trip(CALLBACK, "tick")[1] == "tick"

    def test_null_into_a_field_that_cannot_hold_absence_raises(self, library_system):
        from haywire.barn.builtin.types import FLOAT

        with pytest.raises(TypeError, match="absence"):
            FLOAT.create_field().from_dict(None)


class TestOptional:
    def test_an_absent_optional_saves_null(self, library_system):
        from haywire.barn.builtin.types import INT, OPTIONAL

        assert _round_trip(OPTIONAL[INT], None) == (None, None)

    def test_a_saved_null_value_key_still_loads_absent(self, library_system):
        from haywire.barn.builtin.types import INT, OPTIONAL

        field = OPTIONAL[INT].create_field(default_override={"value": 3})

        field.from_dict({"value": None})

        assert field.get_value() is None


class TestContainers:
    def test_an_array_value_survives_save_and_load(self, library_system):
        from haybale_core.types import ArrayType

        from haywire.barn.builtin.types import FLOAT

        assert _round_trip(ArrayType[FLOAT], [5.0, 6.0])[1] == [5.0, 6.0]

    def test_an_array_of_callbacks_keeps_an_absent_item(self, library_system):
        from haybale_core.types import ArrayType

        from haywire.barn.builtin.types import CALLBACK

        assert _round_trip(ArrayType[CALLBACK], ["a", None])[1] == ["a", None]

    def test_a_map_value_survives_save_and_load(self, library_system):
        from haybale_example.types.maps_string_type import MapsStringType

        from haywire.barn.builtin.types import FLOAT

        assert _round_trip(MapsStringType[FLOAT], {"a": 1.0, "b": 2.0})[1] == {"a": 1.0, "b": 2.0}

    def test_an_array_port_value_survives_the_port_block(self, library_system):
        from haybale_core.types import ArrayType

        from haywire.barn.builtin.types import FLOAT
        from haywire.core.types import DataPort, PortType
        from haywire.core.types.enums import StoreStrategy

        array = ArrayType[FLOAT]
        port = DataPort(
            registry_id="a",
            registry_key=array.class_identity.registry_key,
            label="A",
            id="a",
            type_cls=array,
            port_type=PortType.OUTLET,
        )
        port.store_strategy = StoreStrategy.ALWAYS
        port.set_value([5.0, 6.0])
        spec = json.loads(json.dumps(port.to_dict(include_data=True)))
        port.set_value([])

        port._data.from_dict(spec["field_data"])

        assert port.get_value() == [5.0, 6.0]


def test_an_add_slot_still_saves_its_placeholder(library_system):
    from haywire.barn.builtin.types import ADD

    assert ADD.create_field().to_dict() == {"value": None}
