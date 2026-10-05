"""Callback values: present values save and travel as their type (absence: `test_callback_absence.py`)."""

import pytest

pytestmark = pytest.mark.integration


class TestCallbackFields:
    def test_a_callback_value_saves_and_loads(self, library_system):
        from haywire.barn.builtin.types import CALLBACK

        field = CALLBACK.create_field()
        field.set_value("tick")
        restored = CALLBACK.create_field()

        restored.from_dict(field.to_dict())

        assert restored.get_value() == "tick"

    def test_it_still_travels_as_callback(self, library_system):
        from haywire.barn.builtin.types import CALLBACK

        assert CALLBACK.create_field().get_stored_type() is CALLBACK


class TestDataclassCallbackField:
    def test_a_present_value_is_still_type_checked(self, library_system):
        from haybale_testing.types import TEST_RECORD_CALLBACK

        with pytest.raises(TypeError):
            TEST_RECORD_CALLBACK.create_field().set_value("not a record")


class TestOptionalKeepsAbsence:
    def test_an_optional_field_accepts_absence(self, library_system):
        from haywire.barn.builtin.types import INT, OPTIONAL

        assert OPTIONAL[INT].create_field().accepts_absence()

    def test_an_optional_field_still_travels_as_its_element(self, library_system):
        from haywire.barn.builtin.types import INT, OPTIONAL

        assert OPTIONAL[INT].create_field().get_stored_type() is INT

    def test_an_optional_field_saves_absence_as_null(self, library_system):
        from haywire.barn.builtin.types import INT, OPTIONAL

        field = OPTIONAL[INT].create_field()
        field.set_value(None)

        assert field.to_dict() is None


class TestPooledDataFields:
    def test_a_pooled_data_field_keeps_every_value(self, library_system):
        from haybale_core.types import PooledType
        from haywire.barn.builtin.types import FLOAT

        pool = PooledType[FLOAT].create_field()

        pool.set_value(0.0, source_id="e1")
        pool.set_value(1.0, source_id="e2")
        pool.set_value(None, source_id="e2")

        assert not pool.accepts_absence()
        assert pool.get_value() == {"e1": 0.0, "e2": None}
