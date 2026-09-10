# tests/core/test_settings/test_optional_setting.py
"""
``setting[OPTIONAL[T]]`` — a field that can hold absence.

Absence is a VALUE the user chooses ("do not pass this parameter to the wrapped
library at all"), not an opinion about whether a tier has a view. The two axes
stay orthogonal, and the settings VALUE MODEL is untouched: ``_set_keys``,
``_to_dict``/``_from_dict``, ``_reset`` and the ``__set__`` equality guard all
behave exactly as they do for any other field. These tests pin that down —
especially the property that motivated the whole design, that two routes to the
same visible state must agree.
"""

import pytest

from haywire.barn.builtin.types import BOOL, FLOAT, INT, OPTIONAL
from haywire.core.di.test_config import create_test_settings_registry
from haywire.core.settings import NodeSettings, Promotable, setting
from haywire.core.types.enums import PortType


class Nms(NodeSettings):
    """Mirrors the real shape: two knobs resting absent, one resting at a value."""

    eta = setting[OPTIONAL[FLOAT]](None, min=0.0, max=1.0, label="Eta", validator=lambda v: 0.0 <= v <= 1.0)
    top_k = setting[OPTIONAL[INT]](None, min=1, max=1000, label="Top K")
    min_steps = setting[OPTIONAL[INT]](-1, label="Min Steps Alive")
    flag = setting[OPTIONAL[BOOL]](None, label="Show Bounding Box")


def _bag() -> Nms:
    return Nms(registry=create_test_settings_registry())


class TestValueDomain:
    def test_a_field_may_rest_absent(self):
        bag = _bag()
        assert bag.eta is None
        assert bag.top_k is None
        assert bag.flag is None

    def test_a_field_may_rest_at_a_value(self):
        # The default is free: "rests at the library's own value, can be cleared"
        # is as expressible as "rests absent".
        assert _bag().min_steps == -1

    def test_absence_is_reachable_and_leaveable(self):
        bag = _bag()
        bag.eta = 0.7
        assert bag.eta == 0.7
        bag.eta = None
        assert bag.eta is None

    def test_the_declared_range_stays_the_real_range(self):
        # The point of moving absence out of the value domain: eta's range is
        # 0..1, not widened to admit a -1 sentinel that is neither a valid eta
        # nor distinguishable from one.
        props = Nms.eta.widget_config["properties"]
        assert props["min"] == 0.0
        assert props["max"] == 1.0


class TestNoPathDependence:
    def test_two_routes_to_absence_agree(self):
        # The defect that motivated the design: keyed on is_locally_set, the
        # answer depended on the route taken, because a write equal to the
        # resolved value records no opinion. As a value, absence cannot do that.
        direct = _bag()
        direct.min_steps = None
        via_value = _bag()
        via_value.min_steps = 7
        via_value.min_steps = None

        assert direct.min_steps == via_value.min_steps is None
        assert direct._to_dict()["values"] == via_value._to_dict()["values"]
        assert direct._is_locally_set("min_steps") == via_value._is_locally_set("min_steps")


class TestSerialization:
    def test_a_cleared_non_absent_default_survives_a_round_trip(self):
        # The case "no local override" could never carry: on reload the field
        # must come back absent, not at its default.
        bag = _bag()
        bag.min_steps = None
        data = bag._to_dict()
        assert data["values"] == {"min_steps": None}

        restored = _bag()
        restored._from_dict(data)
        assert restored.min_steps is None

    def test_resting_absent_serializes_nothing(self):
        # Same rule as every other field: a value equal to the default is not
        # written. Nothing about absence is special-cased.
        assert _bag()._to_dict()["values"] == {}

    def test_a_present_value_serializes_normally(self):
        bag = _bag()
        bag.top_k = 5
        assert bag._to_dict()["values"] == {"top_k": 5}


class TestReset:
    def test_reset_returns_to_the_declared_default_not_to_absence(self):
        # Reset and "set to none" are different verbs once a default may be a
        # value — which is why the row menu offers both there.
        bag = _bag()
        bag.min_steps = None
        bag._reset("min_steps")
        assert bag.min_steps == -1

    def test_reset_of_an_absent_default_lands_on_absence(self):
        bag = _bag()
        bag.eta = 0.5
        bag._reset("eta")
        assert bag.eta is None


class TestValidator:
    def test_a_validator_constrains_only_the_present_domain(self):
        # Written for the wrapped type (0.0 <= v <= 1.0), it would raise
        # TypeError on None from inside a plain attribute assignment.
        bag = _bag()
        bag.eta = 0.5
        bag.eta = None
        assert bag.eta is None

    def test_a_validator_still_rejects_an_invalid_present_value(self):
        bag = _bag()
        bag.eta = 5.0
        assert bag.eta is None

    def test_the_lift_reaches_validate_itself_not_just_the_setter(self):
        # validate() has three callers, including SettingsRegistry.set_global on
        # a mirrored field — so the lift must live on the descriptor, not in a
        # guard inside __set__.
        assert Nms.eta.validate(None) is True
        assert Nms.eta.validate(0.5) is True
        assert Nms.eta.validate(5.0) is False


class TestPromotionFence:
    """The fence is drawn where its justification reaches: PINS, not ports.

    No adapter maps ``OPTIONAL[T]`` to ``T``, so an inlet or outlet pin would
    refuse every edge. A CONFIG port is pinless by construction — never linked,
    never edge-driven — so the missing adapter cannot bite it.
    """

    def test_config_is_the_seed(self):
        # A seed, not a structural override: eligible_promotion_directions keeps
        # its invariant that the declared flag IS the eligibility.
        from haywire.core.node.promotion import eligible_promotion_directions

        assert Nms.eta._promotable is Promotable.CONFIG
        assert eligible_promotion_directions(Nms.eta) == (PortType.CONFIG,)

    def test_a_plain_field_is_unaffected(self):
        class Plain(NodeSettings):
            n = setting[INT](0)

        assert Plain.n._promotable is Promotable.ALL

    @pytest.mark.parametrize("direction", [Promotable.INLET, Promotable.OUTLET, Promotable.ALL])
    def test_asking_for_a_pin_raises_rather_than_being_discarded(self, direction):
        # The author asked for a pin; silently ignoring that would leave them
        # with no pin and no explanation.
        with pytest.raises(ValueError, match="cannot be promoted to a PIN"):

            class Bad(NodeSettings):
                f = setting[OPTIONAL[INT]](None, promotable=direction)

    def test_an_explicit_config_is_accepted(self):
        class Fine(NodeSettings):
            f = setting[OPTIONAL[INT]](None, promotable=Promotable.CONFIG)

        assert Fine.f._promotable is Promotable.CONFIG

    def test_an_explicit_none_is_honoured(self):
        # NONE is narrower than the seed, not wider — nothing to refuse.
        class Fine(NodeSettings):
            f = setting[OPTIONAL[INT]](None, promotable=Promotable.NONE)

        assert Fine.f._promotable is Promotable.NONE

    def test_a_config_promote_default_is_allowed(self):
        class Fine(NodeSettings):
            f = setting[OPTIONAL[INT]](None, promote_default=PortType.CONFIG)

        assert Fine.f._promote_default is PortType.CONFIG

    def test_an_inlet_promote_default_is_refused(self):
        # The fence is applied before the promote_default check reads it, so
        # this fails at class-definition time rather than at node construction.
        with pytest.raises(ValueError, match="promote_default"):

            class Bad(NodeSettings):
                f = setting[OPTIONAL[INT]](None, promote_default=PortType.INLET)


class TestRestoreStamp:
    def test_a_non_absent_default_is_offered_as_the_restore_value(self):
        assert Nms.min_steps.widget_config["properties"]["restore"] == -1

    def test_an_absent_default_stamps_nothing(self):
        # Nothing to restore TO; the widget falls back to the element default.
        assert "restore" not in Nms.eta.widget_config["properties"]

    def test_an_explicit_restore_wins(self):
        class Bag(NodeSettings):
            f = setting[OPTIONAL[INT]](-1, widget_config={"restore": 10})

        assert Bag.f.widget_config["properties"]["restore"] == 10

    def test_a_plain_field_never_stamps_one(self):
        class Plain(NodeSettings):
            n = setting[INT](5)

        assert "restore" not in Plain.n.widget_config["properties"]


class TestWidgetContract:
    def test_the_row_renders_through_the_optional_widget(self):
        from haywire.barn.builtin import widget_keys

        assert Nms.eta.widget_key == widget_keys.OPTIONAL_WIDGET
