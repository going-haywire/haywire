"""Characterization + single-cell tests for the Settings value store.

Task 1 (P4): these pin the *observable* behaviour of a ``Settings`` bag through
its PUBLIC API (getattr/setattr/to_dict/from_dict/reset/is_locally_set/subscribe)
so the migration of the per-field value out of ``_local_store`` and into a
per-field ``DataField`` cell is provably behaviour-preserving. They must pass
against the current (_local_store-backed) code AND against the cell-backed code.

No test in the "characterization" classes below touches ``_local_store`` or
``_cells`` — those are the implementation detail under test. The later
``_cell_for`` tests DO reach into the internals; they are the unit tests for the
new mechanism, added task-by-task.
"""

import pytest

from haywire.core.settings import Settings, setting
from haywire.core.di.test_config import create_test_bag
from haywire.barn.builtin.types import BOOL, CHOICES, COLOR, FLOAT, VEC2I


# ---------------------------------------------------------------------------
# Fixtures — mirror test_settings.py
# ---------------------------------------------------------------------------


class SimpleBag(Settings):
    strength = setting[FLOAT](0.5, min=0.0, max=1.0, label="Strength")
    mode = setting[CHOICES]("fast", widget_config={"options": ["fast", "precise"]}, label="Mode")
    verbose = setting[BOOL](False, label="Verbose")


class ComplexBag(Settings):
    offset = setting[VEC2I]([0, 0], label="Offset")
    tint = setting[COLOR]("#ffffff", label="Tint")


def _make_mirror_bag(predefined_local=None):
    """A registry-backed bag with one shadow field 'color' mirroring 'test.color'.

    Mirrors ``test_settings.py::_make_mirror_bag`` — extended mode with a live
    ``_setting_key`` + ``_mirror_key`` so resolution walks the registry chain.
    Returns (registry, bag, GLOBAL_KEY).
    """
    from haywire.core.settings import SettingsRegistry

    GLOBAL_KEY = "test.color"
    LOCAL_KEY = "test.node.color"

    class MirrorBag(Settings):
        color = setting[COLOR]("#ffffff", label="Color")

    MirrorBag.color._setting_key = LOCAL_KEY
    MirrorBag.color._mirror_key = GLOBAL_KEY

    registry = SettingsRegistry()
    registry.define(GLOBAL_KEY, "#ffffff", type_=COLOR)

    bag = MirrorBag(registry=registry)
    bag._subscribe_settings()

    if predefined_local:
        for name, value in predefined_local.items():
            setattr(bag, name, value)

    return registry, bag, GLOBAL_KEY


# ---------------------------------------------------------------------------
# Simple mode
# ---------------------------------------------------------------------------


class TestSimpleModeCharacterization:
    def test_default_read(self):
        bag = SimpleBag()
        assert bag.strength == 0.5
        assert bag.mode == "fast"
        assert bag.verbose is False

    def test_setattr_then_read(self):
        bag = SimpleBag()
        bag.strength = 0.8
        assert bag.strength == 0.8

    def test_to_dict_returns_only_changed_from_default(self):
        bag = SimpleBag()
        assert bag.to_dict() == {"values": {}, "promoted": {}}
        bag.strength = 0.9
        assert bag.to_dict() == {"values": {"strength": 0.9}, "promoted": {}}

    def test_from_dict_notifies_attached_subscribers(self):
        # Subscription rides the cell event (ADR 0016): the restore writes the
        # cell, so an already-attached subscriber sees it. Load-time restores
        # happen before anything subscribes, so they stay unobserved.
        bag = SimpleBag()
        calls = []
        bag.subscribe(lambda *a: calls.append(a))
        bag.from_dict({"values": {"strength": 0.9}, "promoted": {}})
        assert bag.strength == 0.9
        assert calls == [("strength", 0.9, 0.5)]

    def test_reset_returns_to_default_and_fires(self):
        bag = SimpleBag()
        bag.strength = 0.9
        calls = []
        bag.subscribe(lambda name, val, old: calls.append((name, val, old)))
        bag.reset("strength")
        assert bag.strength == 0.5
        assert calls == [("strength", 0.5, 0.9)]

    def test_reset_all(self):
        bag = SimpleBag()
        bag.strength = 0.9
        bag.mode = "precise"
        bag.reset_all()
        assert bag.strength == 0.5
        assert bag.mode == "fast"

    def test_is_locally_set_true_after_set_false_after_reset(self):
        bag = SimpleBag()
        assert not bag.is_locally_set("strength")
        bag.strength = 0.9
        assert bag.is_locally_set("strength")
        bag.reset("strength")
        assert not bag.is_locally_set("strength")

    def test_set_to_default_value_still_marks_locally_set(self):
        """Setting a field to a value EQUAL to its default is a no-op (echo guard):
        the value never changes, so no override is recorded. This is the pre-P4
        contract and must survive — the cell always holds *a* value, so set-ness
        can't be inferred from value!=default."""
        bag = SimpleBag()
        bag.strength = 0.5  # equal to default → echo-guarded no-op
        assert not bag.is_locally_set("strength")
        assert bag.to_dict() == {"values": {}, "promoted": {}}

    def test_subscribe_callback_shape(self):
        bag = SimpleBag()
        calls = []
        bag.subscribe(lambda name, value, old: calls.append((name, value, old)))
        bag.strength = 0.8
        assert calls == [("strength", 0.8, 0.5)]


# ---------------------------------------------------------------------------
# Extended mode (registry-backed)
# ---------------------------------------------------------------------------


class TestExtendedModeCharacterization:
    def test_read_resolves_through_chain_when_unset(self):
        registry, bag = create_test_bag()
        # bg_color has no local override → resolves to descriptor default
        assert bag.bg_color == "#ffffff"

    def test_local_setattr_overrides(self):
        registry, bag = create_test_bag()
        bag.bg_color = "#ff0000"
        assert bag.bg_color == "#ff0000"
        assert bag.is_locally_set("bg_color")

    def test_reset_drops_override_and_reresolves(self):
        registry, bag = create_test_bag(predefined_local={"bg_color": "#ff0000"})
        assert bag.is_locally_set("bg_color")
        bag.reset("bg_color")
        assert not bag.is_locally_set("bg_color")
        assert bag.bg_color == "#ffffff"

    def test_to_dict_writes_only_locally_set(self):
        registry, bag = create_test_bag()
        bag.font_size = 18
        d = bag.to_dict()
        assert d == {"values": {"font_size": 18}, "promoted": {}}
        assert "bg_color" not in d["values"]

    def test_shadow_unset_tracks_global_change(self):
        registry, bag, key = _make_mirror_bag()
        calls = []
        bag.subscribe(lambda name, val, old: calls.append((name, val)))
        registry.set_global(key, "#aabbcc")
        assert calls == [("color", "#aabbcc")]
        assert bag.color == "#aabbcc"

    def test_shadow_set_ignores_global_change(self):
        registry, bag, key = _make_mirror_bag(predefined_local={"color": "#ff0000"})
        calls = []
        bag.subscribe(lambda name, val, old: calls.append((name, val)))
        registry.set_global(key, "#aabbcc")
        assert calls == []
        assert bag.color == "#ff0000"

    def test_redundant_write_of_resolved_value_creates_no_override(self):
        registry, bag, key = _make_mirror_bag()
        assert not bag.is_locally_set("color")
        resolved = bag.color
        bag.color = resolved  # echo
        assert not bag.is_locally_set("color")


# ---------------------------------------------------------------------------
# Complex IType round-trip — the payoff of the cell
# ---------------------------------------------------------------------------


class TestComplexITypeRoundTrip:
    def test_vec2i_round_trips_through_to_dict_from_dict(self):
        bag = ComplexBag()
        bag.offset = [3, 7]
        data = bag.to_dict()
        assert data == {"values": {"offset": [3, 7]}, "promoted": {}}

        bag2 = ComplexBag()
        bag2.from_dict(data)
        assert list(bag2.offset) == [3, 7]

    def test_color_round_trips(self):
        bag = ComplexBag()
        bag.tint = "#123456"
        data = bag.to_dict()
        bag2 = ComplexBag()
        bag2.from_dict(data)
        assert bag2.tint == "#123456"


# ---------------------------------------------------------------------------
# _cell_for — the per-field DataField cell (Task 2 internals)
# ---------------------------------------------------------------------------


class TestCellFor:
    def test_typed_field_gets_cell_seeded_with_default(self):
        bag = SimpleBag()
        descriptor = type(bag)._property_settings()["strength"]
        cell = bag._cell_for(descriptor)
        from haywire.core.types.fields import DataField

        assert isinstance(cell, DataField)
        assert cell.get_value() == 0.5  # the descriptor default

    def test_cell_is_cached_same_object_second_call(self):
        bag = SimpleBag()
        descriptor = type(bag)._property_settings()["strength"]
        first = bag._cell_for(descriptor)
        second = bag._cell_for(descriptor)
        assert first is second

    def test_object_typed_field_raises(self):
        """Settings are IType-only: an un-IType (``object``-typed) field has no
        cell and no fallback store. ``__set_name__`` rejects it at class-definition
        time; a descriptor that bypassed enforcement fails loudly in ``_cell_for``."""
        bag = SimpleBag()
        # Build a bare descriptor with _type=object WITHOUT running __set_name__
        # (which would reject a non-IType).
        descriptor = setting.__new__(setting)
        descriptor._type = object
        descriptor._default = "x"
        descriptor._setting_key = ""
        descriptor._attr_name = "untyped"
        with pytest.raises(TypeError, match="IType-only"):
            bag._cell_for(descriptor)


# ---------------------------------------------------------------------------
# Cell-backed serialization / introspection wire shape (Task 4)
# ---------------------------------------------------------------------------


class TestCellBackedSerialization:
    def test_to_dict_omits_inherited_unset_extended_field(self):
        registry, bag = create_test_bag()
        bag.font_size = 18
        d = bag.to_dict()
        assert d == {"values": {"font_size": 18}, "promoted": {}}  # bg_color inherited/unset → omitted

    def test_to_dict_wire_shape_is_bare_value(self):
        """The graph settings block stores the BARE value, not the IType
        {"value": ...} dict — this matches NodeBase._to_dict → bag.to_dict()."""
        bag = SimpleBag()
        bag.strength = 0.9
        assert bag.to_dict() == {"values": {"strength": 0.9}, "promoted": {}}

    def test_complex_type_wire_shape_is_bare_value(self):
        bag = ComplexBag()
        bag.offset = [3, 7]
        d = bag.to_dict()
        # Bare list, not {"value": [3, 7]}
        assert d == {"values": {"offset": [3, 7]}, "promoted": {}}

    def test_from_dict_populates_cell_and_marks_set_keys(self):
        bag = SimpleBag()
        descriptor = type(bag)._property_settings()["strength"]
        bag.from_dict({"values": {"strength": 0.9}, "promoted": {}})
        assert bag._is_locally_set(descriptor)
        assert bag._cells["strength"].get_value() == 0.9

    def test_reset_clears_set_keys_and_returns_cell_to_default(self):
        bag = SimpleBag()
        bag.strength = 0.9
        descriptor = type(bag)._property_settings()["strength"]
        bag.reset("strength")
        assert not bag._is_locally_set(descriptor)
        # Cell returned to default (never structurally removed — DECISIONS §C3)
        assert bag._cells["strength"].get_value() == 0.5

    def test_vec2i_bag_round_trips_through_dict(self):
        bag = ComplexBag()
        bag.offset = [5, 9]
        data = bag.to_dict()
        bag2 = ComplexBag()
        bag2.from_dict(data)
        assert list(bag2.offset) == [5, 9]

    def test_dict_value_stores_are_gone(self):
        """P4 removed the general _local_store; the _plain object-typed fallback
        followed once settings became IType-only — the per-field cell is the ONLY
        local value store."""
        bag = SimpleBag()
        assert not hasattr(bag, "_local_store")
        assert not hasattr(bag, "_plain")
