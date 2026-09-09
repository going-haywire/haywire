# tests/core/test_settings/test_promoted_keys.py
"""
_promoted_keys state + accessors on Settings (Task 1 of settings-owned-promotion):

- set_promoted / clear_promoted / is_promoted / get_promoted_direction
- keyed by storage_key, storing a PortType direction
- unknown-field handling (warn+ignore on set, silent on clear/read)

Serialization (to_dict/from_dict new shape) is tested separately in Task 2's
additions to this file. Panel/port wiring is tested at higher layers.
"""

import logging

import pytest

from haywire.core.settings import Settings, setting
from haywire.core.settings.settings import PromotedFormatError
from haywire.core.types.enums import PortType, ShowWidgetStrategy
from haywire.barn.builtin.types import BOOL, FLOAT


class PromoSettings(Settings):
    alpha = setting[FLOAT](1.0, label="Alpha")
    beta = setting[FLOAT](2.0, label="Beta")
    flag = setting[BOOL](True, label="Flag")


class TestPromotedAccessors:
    def test_field_starts_unpromoted(self):
        bag = PromoSettings()
        assert bag._is_promoted("alpha") is False
        assert bag._get_promoted_direction("alpha") is None

    def test_set_promoted_inlet(self):
        bag = PromoSettings()
        bag._set_promoted("alpha", PortType.INLET)
        assert bag._is_promoted("alpha") is True
        assert bag._get_promoted_direction("alpha") is PortType.INLET

    def test_set_promoted_outlet(self):
        bag = PromoSettings()
        bag._set_promoted("beta", PortType.OUTLET)
        assert bag._get_promoted_direction("beta") is PortType.OUTLET

    def test_clear_promoted(self):
        bag = PromoSettings()
        bag._set_promoted("alpha", PortType.INLET)
        bag._clear_promoted("alpha")
        assert bag._is_promoted("alpha") is False
        assert bag._get_promoted_direction("alpha") is None

    def test_reset_direction_by_re_setting(self):
        bag = PromoSettings()
        bag._set_promoted("alpha", PortType.INLET)
        bag._set_promoted("alpha", PortType.OUTLET)  # a field has at most one port
        assert bag._get_promoted_direction("alpha") is PortType.OUTLET

    def test_is_promoted_unknown_field_false(self):
        bag = PromoSettings()
        assert bag._is_promoted("nonexistent") is False
        assert bag._get_promoted_direction("nonexistent") is None

    def test_set_promoted_unknown_field_warns_and_ignores(self, caplog):
        bag = PromoSettings()
        with caplog.at_level(logging.WARNING):
            bag._set_promoted("nonexistent", PortType.INLET)
        assert any("nonexistent" in rec.message for rec in caplog.records)
        assert bag._is_promoted("nonexistent") is False

    def test_clear_promoted_unknown_or_unpromoted_is_silent(self):
        bag = PromoSettings()
        bag._clear_promoted("nonexistent")  # must not raise
        bag._clear_promoted("alpha")  # not promoted — must not raise
        assert bag._is_promoted("alpha") is False

    def test_promotion_does_not_affect_value(self):
        bag = PromoSettings()
        bag._set_promoted("alpha", PortType.INLET)
        assert bag.alpha == 1.0
        bag.alpha = 9.0
        assert bag.alpha == 9.0
        assert bag._is_promoted("alpha") is True


class TestSerializationShape:
    def test_to_dict_new_shape_empty(self):
        bag = PromoSettings()
        d = bag._to_dict()
        assert d == {"values": {}, "promoted": {}}

    def test_to_dict_includes_values_and_promotions(self):
        bag = PromoSettings()
        bag.alpha = 5.0  # locally set, differs from default
        bag._set_promoted("beta", PortType.OUTLET)
        d = bag._to_dict()
        assert d["values"] == {"alpha": 5.0}
        # promoted is keyed by storage_key; for a plain field storage_key == attr name.
        # No show_widget: an untouched promotion uses its direction default (v3).
        assert d["promoted"] == {"beta": {"direction": "outlet"}}

    def test_from_dict_restores_values_and_promotions(self):
        bag = PromoSettings()
        bag._from_dict({"values": {"alpha": 7.0}, "promoted": {"beta": {"direction": "inlet"}}})
        assert bag.alpha == 7.0
        assert bag._is_promoted("beta") is True
        assert bag._get_promoted_direction("beta") is PortType.INLET
        assert bag._get_promoted_show_widget("beta") is None

    def test_round_trip(self):
        bag = PromoSettings()
        bag.beta = 42.0
        bag._set_promoted("alpha", PortType.INLET)
        restored = PromoSettings()
        restored._from_dict(bag._to_dict())
        assert restored.beta == 42.0
        assert restored._get_promoted_direction("alpha") is PortType.INLET

    def test_from_dict_old_flat_shape_raises(self):
        bag = PromoSettings()
        with pytest.raises(PromotedFormatError):
            bag._from_dict({"alpha": 5.0})  # pre-refactor flat shape

    def test_from_dict_empty_is_not_an_error(self):
        bag = PromoSettings()
        bag._from_dict({})  # a bag that serialized nothing — must not raise
        assert bag.alpha == 1.0

    def test_from_dict_missing_promoted_section_defaults_empty(self):
        bag = PromoSettings()
        bag._from_dict({"values": {"alpha": 3.0}})  # no "promoted" key
        assert bag.alpha == 3.0
        assert bag._promoted_keys == {}

    def test_from_dict_rejects_a_pre_v3_bare_direction_string(self):
        """The v2 shape must never be silently accepted here — the prehydrator
        migrates it, and tolerating both would leave two live spellings."""
        bag = PromoSettings()
        with pytest.raises(PromotedFormatError):
            bag._from_dict({"values": {}, "promoted": {"beta": "outlet"}})


class TestPromotedShowWidget:
    """The user's per-port widget-visibility choice, recorded beside the direction."""

    def test_defaults_to_none(self):
        bag = PromoSettings()
        bag._set_promoted("alpha", PortType.OUTLET)
        assert bag._get_promoted_show_widget("alpha") is None

    def test_set_keeps_the_direction(self):
        bag = PromoSettings()
        bag._set_promoted("alpha", PortType.OUTLET)
        bag._set_promoted_show_widget("alpha", ShowWidgetStrategy.ALWAYS)
        assert bag._get_promoted_direction("alpha") is PortType.OUTLET
        assert bag._get_promoted_show_widget("alpha") is ShowWidgetStrategy.ALWAYS

    def test_set_on_an_unpromoted_field_is_a_noop(self):
        bag = PromoSettings()
        bag._set_promoted_show_widget("alpha", ShowWidgetStrategy.ALWAYS)
        assert bag._get_promoted_show_widget("alpha") is None
        assert bag._is_promoted("alpha") is False

    def test_non_default_strategy_serializes(self):
        bag = PromoSettings()
        bag._set_promoted("alpha", PortType.OUTLET)
        bag._set_promoted_show_widget("alpha", ShowWidgetStrategy.ALWAYS)
        assert bag._to_dict()["promoted"] == {"alpha": {"direction": "outlet", "show_widget": "always"}}

    def test_strategy_equal_to_the_direction_default_is_omitted(self):
        """NEVER *is* the outlet default, so it is not a choice worth writing."""
        bag = PromoSettings()
        bag._set_promoted("alpha", PortType.OUTLET)
        bag._set_promoted_show_widget("alpha", ShowWidgetStrategy.NEVER)
        assert bag._to_dict()["promoted"] == {"alpha": {"direction": "outlet"}}

    def test_same_strategy_is_a_choice_on_one_direction_and_a_default_on_another(self):
        """ALWAYS is the config default but an explicit choice on an outlet."""
        bag = PromoSettings()
        bag._set_promoted("alpha", PortType.CONFIG)
        bag._set_promoted_show_widget("alpha", ShowWidgetStrategy.ALWAYS)
        assert bag._to_dict()["promoted"] == {"alpha": {"direction": "config"}}

    def test_round_trip_preserves_a_non_default_strategy(self):
        bag = PromoSettings()
        bag._set_promoted("alpha", PortType.INLET)
        bag._set_promoted_show_widget("alpha", ShowWidgetStrategy.ALWAYS)
        restored = PromoSettings()
        restored._from_dict(bag._to_dict())
        assert restored._get_promoted_show_widget("alpha") is ShowWidgetStrategy.ALWAYS
