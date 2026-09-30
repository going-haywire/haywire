"""Callback values: an empty name means no subscription and a pool drops it; only OPTIONAL holds absence."""

import pytest

pytestmark = pytest.mark.integration


class TestCallbackFields:
    def test_a_callback_field_defaults_to_an_empty_name(self, library_system):
        from haybale_core.types import CALLBACK

        assert CALLBACK.create_field().get_value() == ""

    def test_a_callback_field_holds_no_absence(self, library_system):
        from haybale_core.types import CALLBACK

        assert not CALLBACK.create_field().accepts_absence()

    def test_a_callback_value_saves_and_loads(self, library_system):
        from haybale_core.types import CALLBACK

        field = CALLBACK.create_field()
        field.set_value("tick")
        restored = CALLBACK.create_field()

        restored.from_dict(field.to_dict())

        assert restored.get_value() == "tick"

    def test_it_still_travels_as_callback(self, library_system):
        from haybale_core.types import CALLBACK

        assert CALLBACK.create_field().get_stored_type() is CALLBACK


class TestDataclassCallbackField:
    def test_it_keeps_plain_storage(self, library_system):
        from haybale_testing.types import TEST_RECORD_CALLBACK

        assert not TEST_RECORD_CALLBACK.create_field().accepts_absence()

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

    def test_an_optional_field_saves_absence_as_a_null_value(self, library_system):
        from haywire.barn.builtin.types import INT, OPTIONAL

        field = OPTIONAL[INT].create_field()
        field.set_value(None)

        assert field.to_dict() == {"value": None}


class TestPooledFields:
    def test_an_empty_name_from_a_source_removes_its_entry(self, library_system):
        from haybale_core.types import CALLBACK, PooledType

        pool = PooledType[CALLBACK].create_field()
        pool.set_value("a", source_id="e1")
        pool.set_value("b", source_id="e2")

        pool.set_value("", source_id="e1")

        assert pool.get_value() == {"e2": "b"}

    def test_a_dataclass_default_from_a_source_removes_its_entry(self, library_system):
        from haybale_core.types import PooledType
        from haybale_testing.types import TEST_RECORD_CALLBACK

        pool = PooledType[TEST_RECORD_CALLBACK].create_field()
        pool.set_value(TEST_RECORD_CALLBACK(name="a", weight=1), source_id="e1")

        pool.set_value(TEST_RECORD_CALLBACK(), source_id="e1")

        assert pool.get_value() == {}

    def test_a_value_other_than_the_default_keeps_its_entry(self, library_system):
        from haybale_core.types import PooledType
        from haybale_testing.types import TEST_RECORD_CALLBACK

        pool = PooledType[TEST_RECORD_CALLBACK].create_field()

        pool.set_value(TEST_RECORD_CALLBACK(name="", weight=2), source_id="e1")

        assert pool.get_value() == {"e1": TEST_RECORD_CALLBACK(name="", weight=2)}

    def test_the_default_without_a_source_changes_nothing(self, library_system):
        from haybale_core.types import CALLBACK, PooledType

        pool = PooledType[CALLBACK].create_field()
        pool.set_value("a", source_id="e1")

        pool.set_value("")

        assert pool.get_value() == {"e1": "a"}

    def test_a_pooled_data_field_keeps_every_value(self, library_system):
        from haybale_core.types import PooledType
        from haywire.barn.builtin.types import FLOAT

        pool = PooledType[FLOAT].create_field()

        pool.set_value(0.0, source_id="e1")
        pool.set_value(1.0, source_id="e2")
        pool.set_value(None, source_id="e2")

        assert not pool.accepts_absence()
        assert pool.get_value() == {"e1": 0.0, "e2": None}
