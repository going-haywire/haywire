"""A field keeps its own value and, while an edge feeds it, the linked value in front of it."""

import pytest

pytestmark = pytest.mark.integration


@pytest.fixture
def float_field(library_system):
    from haywire.barn.builtin.types import FLOAT

    return FLOAT.create_field()


class TestTwoValues:
    def test_a_write_without_a_source_is_the_own_value(self, float_field):
        float_field.set_value(7.0)

        assert float_field.get_value() == 7.0
        assert float_field.get_own_value() == 7.0
        assert not float_field.has_linked_value()

    def test_a_write_with_a_source_stands_in_front_of_the_own_value(self, float_field):
        float_field.set_value(7.0)

        float_field.set_value(42.0, source_id="e1")

        assert float_field.has_linked_value()
        assert float_field.get_value() == 42.0
        assert float_field.get_own_value() == 7.0

    def test_an_own_write_while_linked_changes_only_the_own_value(self, float_field):
        float_field.set_value(42.0, source_id="e1")

        float_field.set_value(5.0)

        assert float_field.get_value() == 42.0
        assert float_field.get_own_value() == 5.0

    def test_clearing_the_linked_value_reveals_the_own_value(self, float_field):
        float_field.set_value(7.0)
        float_field.set_value(42.0, source_id="e1")

        float_field.clear_linked()

        assert not float_field.has_linked_value()
        assert float_field.get_value() == 7.0

    def test_clearing_without_a_linked_value_changes_nothing(self, float_field):
        float_field.set_value(7.0)

        float_field.clear_linked()

        assert float_field.get_value() == 7.0

    def test_only_the_own_value_is_saved(self, float_field):
        float_field.set_value(7.0)
        float_field.set_value(42.0, source_id="e1")

        assert float_field.to_dict() == {"value": 7.0}


class TestEvents:
    def test_every_change_fires_with_the_value_get_value_returns(self, float_field):
        seen: list = []
        float_field.add_observer(lambda change: seen.append((change.old, change.value)))

        float_field.set_value(7.0)
        float_field.set_value(42.0, source_id="e1")
        float_field.set_value(5.0)
        float_field.clear_linked()

        assert seen == [(0.0, 7.0), (7.0, 42.0), (42.0, 42.0), (42.0, 5.0)]


class TestTheFieldChecksBothValues:
    def test_a_linked_value_is_coerced_like_an_own_one(self, library_system):
        from haywire.barn.builtin.types import INT

        field = INT.create_field()

        field.set_value(3.7, source_id="e1")

        assert field.get_value() == 3

    def test_a_rejected_linked_value_leaves_no_linked_value_behind(self, library_system):
        from haybale_core.types import ArrayType
        from haywire.barn.builtin.types import FLOAT

        field = ArrayType[FLOAT].create_field()

        with pytest.raises(TypeError):
            field.set_value("not a list", source_id="e1")
        assert not field.has_linked_value()


class TestPooledFieldsKeepTheirShape:
    def test_a_pooled_field_never_holds_a_linked_value(self, library_system):
        from haybale_core.types import PooledType
        from haywire.barn.builtin.types import FLOAT

        pool = PooledType[FLOAT].create_field()

        pool.set_value(1.0, source_id="e1")

        assert not pool.has_linked_value()
        assert pool.get_value() == {"e1": 1.0}
