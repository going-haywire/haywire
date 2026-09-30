"""Fields of immediate types hold absence (``None``), whatever their storage."""

import pytest

pytestmark = pytest.mark.integration


@pytest.fixture
def callback_field(library_system):
    from haybale_core.types import CALLBACK

    return CALLBACK.create_field()


@pytest.fixture
def record_field(library_system):
    from haybale_testing.types import TEST_RECORD_CALLBACK

    return TEST_RECORD_CALLBACK.create_field()


class TestPrimitiveCallbackField:
    def test_it_accepts_absence(self, callback_field):
        assert callback_field.accepts_absence()

    def test_it_stores_none(self, callback_field):
        callback_field.set_value("tick")

        callback_field.set_value(None)

        assert callback_field.get_value() is None
        assert not callback_field.has_data()

    def test_absence_saves_and_loads(self, callback_field):
        from haybale_core.types import CALLBACK

        callback_field.set_value(None)
        restored = CALLBACK.create_field()
        restored.set_value("tick")

        restored.from_dict(callback_field.to_dict())

        assert restored.get_value() is None

    def test_it_still_travels_as_callback(self, callback_field):
        from haybale_core.types import CALLBACK

        assert callback_field.get_stored_type() is CALLBACK


class TestDataclassCallbackField:
    def test_it_accepts_absence(self, record_field):
        assert record_field.accepts_absence()

    def test_it_stores_none(self, record_field):
        record_field.set_value(None)

        assert record_field.get_value() is None
        assert not record_field.has_data()

    def test_a_present_value_is_still_type_checked(self, record_field):
        with pytest.raises(TypeError):
            record_field.set_value("not a record")

    def test_absence_saves_and_loads(self, record_field):
        from haybale_testing.types import TEST_RECORD_CALLBACK

        record_field.set_value(None)
        restored = TEST_RECORD_CALLBACK.create_field()

        restored.from_dict(record_field.to_dict())

        assert restored.get_value() is None

    def test_a_present_value_still_saves_and_loads(self, record_field):
        from haybale_testing.types import TEST_RECORD_CALLBACK

        record_field.set_value(TEST_RECORD_CALLBACK(name="tick", weight=3))
        restored = TEST_RECORD_CALLBACK.create_field()

        restored.from_dict(record_field.to_dict())

        assert restored.get_value() == TEST_RECORD_CALLBACK(name="tick", weight=3)


class TestOtherTypesAreUnchanged:
    def test_a_float_field_does_not_accept_absence(self, library_system):
        from haywire.barn.builtin.types import FLOAT

        assert not FLOAT.create_field().accepts_absence()

    def test_an_optional_field_still_travels_as_its_element(self, library_system):
        from haywire.barn.builtin.types import INT, OPTIONAL

        assert OPTIONAL[INT].create_field().get_stored_type() is INT

    def test_an_optional_field_still_saves_absence_as_a_null_value(self, library_system):
        from haywire.barn.builtin.types import INT, OPTIONAL

        field = OPTIONAL[INT].create_field()
        field.set_value(None)

        assert field.to_dict() == {"value": None}


class TestPooledFields:
    def test_a_pooled_callback_field_accepts_absence(self, library_system):
        from haybale_core.types import CALLBACK, PooledType

        assert PooledType[CALLBACK].create_field().accepts_absence()

    def test_absence_from_a_source_removes_its_entry(self, library_system):
        from haybale_core.types import CALLBACK, PooledType

        pool = PooledType[CALLBACK].create_field()
        pool.set_value("a", source_id="e1")
        pool.set_value("b", source_id="e2")

        pool.set_value(None, source_id="e1")

        assert pool.get_value() == {"e2": "b"}

    def test_absence_without_a_source_changes_nothing(self, library_system):
        from haybale_core.types import CALLBACK, PooledType

        pool = PooledType[CALLBACK].create_field()
        pool.set_value("a", source_id="e1")

        pool.set_value(None)

        assert pool.get_value() == {"e1": "a"}

    def test_a_pooled_data_field_is_unchanged(self, library_system):
        from haybale_core.types import PooledType
        from haywire.barn.builtin.types import FLOAT

        pool = PooledType[FLOAT].create_field()
        pool.set_value(1.0, source_id="e1")

        pool.set_value(None, source_id="e1")

        assert not pool.accepts_absence()
        assert pool.get_value() == {"e1": None}  # the entry stays; only immediate pools drop it
