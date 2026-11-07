"""Carrier values and the CARRIER and BUNDLE types."""

import pytest

from haywire.barn.builtin.carrier import BundleValue, CarrierValue, Stamp
from haywire.barn.builtin.types import BUNDLE, CARRIER, FLOAT, INT
from haywire.core.types.enums import StoreStrategy

pytestmark = pytest.mark.unit


def test_stamping_returns_a_new_carrier_and_leaves_the_original_alone():
    base = BundleValue()
    one = base.stamped("t", 1.5, FLOAT)
    other = base.stamped("x", 2, INT)
    assert dict(base.fields) == {}
    assert one.fields["t"] == Stamp(1.5, FLOAT.class_identity.registry_key)
    assert "x" not in one.fields
    assert "t" not in other.fields


def test_a_second_stamp_keeps_the_first():
    two = BundleValue().stamped("t", 1.5, FLOAT).stamped("x", 2, INT)
    assert set(two.fields) == {"t", "x"}


def test_fields_cannot_be_written_through_the_mapping():
    with pytest.raises(TypeError):
        BundleValue().fields["t"] = Stamp(1, "k")  # type: ignore[index]


def test_a_carrier_describes_nothing_by_default():
    assert CarrierValue().describe() == {}


def test_bundle_is_a_carrier_and_starts_empty():
    assert issubclass(BUNDLE, CARRIER)
    assert isinstance(BUNDLE.create_field().get_value(), BundleValue)
    assert BUNDLE.element_type_cls is BundleValue


def test_carrier_values_are_never_saved():
    assert BUNDLE.class_identity.store_strategy is StoreStrategy.NEVER
    assert CARRIER.class_identity.store_strategy is StoreStrategy.NEVER


def test_carrier_is_hidden_and_bundle_is_visible():
    assert CARRIER.class_identity.hidden is True
    assert BUNDLE.class_identity.hidden is False


def test_a_field_holds_what_it_is_given_and_a_dict_becomes_empty():
    field = BUNDLE.create_field()
    value = BundleValue().stamped("t", 1.5, FLOAT)
    field.set_value(value)
    assert field.get_value() is value
    assert BUNDLE.from_dict({"value": {}}).fields == {}


def test_a_hidden_type_does_not_hide_its_pins():
    """Hidden on a type keeps it out of pickers; hidden on a port hides the row on the card."""
    spec = CARRIER.as_inlet("carrier")
    assert spec["kwargs"].get("hidden", False) is False
