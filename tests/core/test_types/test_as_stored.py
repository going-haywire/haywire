"""``DataField.as_stored``: a value as the field would store it, with nothing stored."""

from __future__ import annotations

import pytest

pytestmark = pytest.mark.integration


@pytest.fixture
def int_field(library_system):
    from haywire.barn.builtin.types import INT

    field = INT.create_field()
    field.set_value(5)
    return field


def test_a_value_comes_back_as_the_field_stores_it(int_field):
    assert int_field.as_stored(3.7) == 3


def test_nothing_is_stored(int_field):
    int_field.as_stored(9)

    assert int_field.get_own_value() == 5
    assert int_field.get_value() == 5


def test_a_value_the_field_rejects_raises(int_field):
    with pytest.raises((TypeError, ValueError)):
        int_field.as_stored("not a number")
