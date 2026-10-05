"""A wire type that holds absence gives the types declared on it fields that can hold `None` (Q14, Q22)."""

from dataclasses import dataclass

import pytest

pytestmark = pytest.mark.integration


def _record_type(default):
    """A dataclass type on `CallbackWire` with the given declared default."""
    from haywire.barn.builtin.wires import CallbackWire
    from haywire.core.types import BaseType
    from haywire.core.types import type as type_dec

    @type_dec(wire_type=CallbackWire, label="Probe Record", default=default)
    @dataclass
    class PROBE_RECORD(BaseType):
        name: str = ""

    return PROBE_RECORD


class TestTheWire:
    def test_only_the_callback_wire_holds_absence(self, library_system):
        from haywire.barn.builtin.wires import CallbackWire, ControlWire, DataWire

        assert CallbackWire.holds_absence
        assert not DataWire.holds_absence
        assert not ControlWire.holds_absence


class TestAPrimitiveOnTheWire:
    def test_it_holds_absence_and_keeps_its_stored_type(self, library_system):
        from haywire.barn.builtin.types import CALLBACK

        field = CALLBACK.create_field()
        field.set_value(None)

        assert field.accepts_absence()
        assert field.get_value() is None
        assert field.get_stored_type() is CALLBACK

    def test_a_linked_value_can_be_absent(self, library_system):
        from haywire.barn.builtin.types import CALLBACK

        field = CALLBACK.create_field()
        field.set_value(None, source_id="e1")

        assert field.has_linked_value()
        assert field.get_value() is None

    def test_a_none_default_is_stored_empty_and_starts_absent(self, library_system):
        from haywire.barn.builtin.types import STRING
        from haywire.barn.builtin.wires import CallbackWire
        from haywire.core.types import type as type_dec

        @type_dec(wire_type=CallbackWire, label="Probe Name", default=None)
        class PROBE_NAME(STRING):
            """Probe."""

        assert PROBE_NAME.class_identity.default == {}
        assert PROBE_NAME.create_field().get_value() is None

    def test_a_none_default_off_the_wire_is_still_refused(self, library_system):
        from haywire.barn.builtin.types import STRING
        from haywire.core.types import type as type_dec

        with pytest.raises(TypeError, match="OPTIONAL"):

            @type_dec(label="Probe Text", default=None)
            class PROBE_TEXT(STRING):
                """Probe."""


class TestADataclassOnTheWire:
    def test_a_none_default_starts_and_resets_absent(self, library_system):
        field = _record_type(None).create_field()
        assert field.get_value() is None

        field.reset()

        assert field.get_value() is None
        assert field.accepts_absence()

    def test_a_present_default_is_read_back(self, library_system):
        record = _record_type({"name": "n"})

        assert record.create_field().get_value() == record(name="n")

    def test_a_present_value_is_still_type_checked(self, library_system):
        field = _record_type(None).create_field()

        with pytest.raises(TypeError):
            field.set_value("not a record")

    def test_it_takes_absence_after_a_value(self, library_system):
        record = _record_type(None)
        field = record.create_field()
        field.set_value(record(name="n"))

        field.set_value(None)

        assert field.get_value() is None


class TestWhatIsNotWrapped:
    def test_containers_of_a_callback_keep_their_own_fields(self, library_system):
        from haybale_core.types import ArrayType, PooledType
        from haybale_core.types.array_type import ArrayField
        from haybale_core.types.pooled_type import PooledField

        from haywire.barn.builtin.types import CALLBACK

        assert type(ArrayType[CALLBACK].create_field()) is ArrayField
        assert type(PooledType[CALLBACK].create_field()) is PooledField

    def test_an_optional_callback_is_still_a_wrapper_field(self, library_system):
        from haywire.barn.builtin.types import CALLBACK, OPTIONAL

        field = OPTIONAL[CALLBACK].create_field()

        assert field.accepts_absence()
        assert field.get_stored_type() is CALLBACK

    def test_a_data_type_keeps_its_field_class(self, library_system):
        from haywire.barn.builtin.types import FLOAT
        from haywire.barn.builtin.types.specs import FLOATField

        assert type(FLOAT.create_field()) is FLOATField
