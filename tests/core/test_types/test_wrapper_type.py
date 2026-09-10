# tests/core/test_types/test_wrapper_type.py
"""
WrapperType — the fourth IType family: exactly one value of another IType, or absence.

The load-bearing claim is what it is NOT. ``issubclass(x, CompoundType)`` means
"a container of N elements", and ``AdapterFactory`` and ``pin_render`` dispatch
on it. A wrapper holding zero-or-one that inherited CompoundType would silently
get element-wise adapter chains and collection pin iconography — wrong, and only
once the value reached a port. So the family boundary is tested, not assumed.
"""

import pytest

from haywire.barn.builtin.types import BOOL, FLOAT, INT, OPTIONAL, VEC3F
from haywire.core.types.base import CompoundType
from haywire.core.types.utils import serialize_element_type


class TestFamilyBoundary:
    def test_a_wrapper_is_not_a_compound(self):
        # The whole reason WrapperType exists rather than reusing CompoundType.
        assert not issubclass(OPTIONAL, CompoundType)
        assert not issubclass(OPTIONAL[INT], CompoundType)

    def test_adapter_factory_treats_it_as_scalar(self):
        # AdapterFactory branches on issubclass(..., CompoundType) to decide
        # between a scalar chain and an element-wise chain. A wrapper must take
        # the scalar branch: it holds zero or one value, not N.
        from haywire.core.adapter.factory import CompoundType as FactoryCompoundType

        assert not issubclass(OPTIONAL[FLOAT], FactoryCompoundType)

    def test_pin_render_treats_it_as_scalar(self):
        # Same predicate, different consumer: collection iconography would make
        # an optional pin look like an array pin.
        from haywire.ui.skin.pin_render import CompoundType as PinCompoundType

        assert not issubclass(OPTIONAL[INT], PinCompoundType)


class TestParameterization:
    def test_subscripting_is_cached_so_type_identity_holds(self):
        assert OPTIONAL[INT] is OPTIONAL[INT]

    def test_distinct_elements_are_distinct_types(self):
        assert OPTIONAL[INT] is not OPTIONAL[FLOAT]

    def test_element_is_recorded(self):
        assert OPTIONAL[INT].element_type_cls is INT

    def test_a_wrapper_may_not_wrap_a_wrapper(self):
        # Absence has no degrees: a second wrapper can only mean the first.
        with pytest.raises(TypeError, match="cannot wrap another wrapper"):
            OPTIONAL[OPTIONAL[INT]]


class TestStorage:
    def test_the_cell_holds_absence(self):
        cell = OPTIONAL[INT].create_field(default_override={"value": None})
        assert cell.get_value() is None

    def test_present_values_keep_the_elements_own_coercion(self):
        # INT declares INTField, which int()-coerces every write. An optional int
        # must behave exactly like a plain int while a value is present —
        # otherwise the same write means different things depending on how the
        # field was declared.
        cell = OPTIONAL[INT].create_field(default_override={"value": None})
        cell.set_value(3.7)
        assert cell.get_value() == 3
        assert isinstance(cell.get_value(), int)

    def test_absence_bypasses_that_coercion(self):
        # int(None) raises; the None branch must skip the element's override.
        cell = OPTIONAL[INT].create_field(default_override={"value": 5})
        cell.set_value(None)
        assert cell.get_value() is None

    def test_the_derived_field_class_is_shared_per_element(self):
        assert OPTIONAL[INT].field_class is OPTIONAL[INT].field_class
        assert OPTIONAL[INT].field_class is not OPTIONAL[FLOAT].field_class

    def test_a_change_event_still_fires_for_absence(self):
        # Widgets and promoted ports listen on this; skipping the element's
        # coercion must not skip its notification.
        cell = OPTIONAL[INT].create_field(default_override={"value": 5})
        seen: list = []
        cell.on_changed += lambda change: seen.append((change.value, change.old))
        cell.set_value(None)
        assert seen == [(None, 5)]


class TestIdentity:
    def test_the_element_recipe_round_trips(self):
        assert serialize_element_type(OPTIONAL[INT]) == {
            "registry_key": OPTIONAL.class_identity.registry_key,
            "element_type": {"registry_key": INT.class_identity.registry_key},
        }

    def test_the_registry_key_stays_the_wrappers(self):
        # A saved graph must resolve back to the wrapper, then re-parameterize
        # from the recipe.
        assert OPTIONAL[INT].class_identity.registry_key == OPTIONAL.class_identity.registry_key

    def test_the_widget_key_stays_the_wrappers(self):
        # OptionalWidget renders the row; it is what looks up the element's
        # widget in turn.
        assert OPTIONAL[INT].class_identity.widget_key == OPTIONAL.class_identity.widget_key

    def test_the_colour_comes_from_the_element(self):
        # Inert while the promotion fence holds, correct the moment it lifts.
        assert OPTIONAL[INT].class_identity.color == INT.class_identity.color
        assert OPTIONAL[BOOL].class_identity.color == BOOL.class_identity.color

    def test_element_widget_properties_are_inherited(self):
        # VEC3F declares vec_meta on its identity, not per-declaration. Without
        # this merge, VecWidget cannot render an optional vector at all.
        props = OPTIONAL[VEC3F].class_identity.widget_config["properties"]
        assert props["vec_meta"] == {"length": 3, "labels": ["X", "Y", "Z"]}


class TestSerialization:
    def test_absence_serializes_as_an_explicit_null(self):
        assert OPTIONAL[INT](value=None).to_dict() == {"value": None}

    def test_absence_reads_back_as_absence_not_the_element_default(self):
        assert OPTIONAL[INT].from_dict({"value": None}) is None

    def test_a_present_value_uses_the_elements_own_encoding(self):
        assert OPTIONAL[VEC3F].from_dict({"value": [1.0, 2.0, 3.0]}) == [1.0, 2.0, 3.0]

    def test_create_default_tolerates_absence(self):
        # PrimitiveType.__init__ raises on a None value; the wrapper family must
        # not, since its decorator default IS {'value': None}.
        assert OPTIONAL[INT].create_default().value is None


class TestGuards:
    def test_an_element_with_no_field_class_is_refused(self):
        class NoStorage:
            pass

        with pytest.raises(TypeError, match="no field_class"):
            OPTIONAL[NoStorage]

    def test_an_element_stored_by_basefield_is_refused(self):
        # "Absence" means a bare value or None in an unwrapped slot. A BaseField
        # element has nowhere to put absence and would need its own design, so
        # the refusal is explicit rather than a later AttributeError.
        from haywire.core.types.base import BaseType

        class Structured(BaseType):
            @property
            def value(self):
                return self

            def to_dict(self):
                return {}

            @classmethod
            def from_dict(cls, data):
                return cls()

        with pytest.raises(TypeError, match="only defined for PrimitiveField storage"):
            OPTIONAL[Structured]
