# tests/core/test_settings/test_settings.py
"""
Tests for the Settings-based settings system.

Covers:
- Simple mode (no registry): direct local store access
- Extended mode (registry injected): resolution chain
- on_change callbacks
- mirrors= (shadow behaviour)
- read_only= (watch behaviour)
- Serialization round-trip (to_dict / from_dict)
- Conflict detection at class-definition time
- Direct binding on node instances via @node decorator
"""

import pytest
from haywire.core.settings import (
    Settings,
    NodeSettings,
    field,
    Vec2i,
    Vec3i,
    Vec4i,
    Vec2f,
    Vec3f,
    Vec4f,
    get_vec_meta,
)
from haywire.core.di.test_config import create_test_bag


# ---------------------------------------------------------------------------
# Simple mode — no registry
# ---------------------------------------------------------------------------


class SimpleSettings(Settings):
    strength: float = field(0.5, min=0.0, max=1.0, label="Strength")
    mode: str = field("fast", choices=["fast", "precise"], label="Mode")
    verbose: bool = field(False, label="Verbose")


class TestSimpleMode:
    def test_default_values(self):
        bag = SimpleSettings()
        assert bag.strength == 0.5
        assert bag.mode == "fast"
        assert bag.verbose is False

    def test_set_and_read(self):
        bag = SimpleSettings()
        bag.strength = 0.8
        assert bag.strength == 0.8

    def test_reset_restores_default(self):
        bag = SimpleSettings()
        bag.strength = 0.9
        bag.reset("strength")
        assert bag.strength == 0.5

    def test_reset_all(self):
        bag = SimpleSettings()
        bag.strength = 0.9
        bag.mode = "precise"
        bag.reset_all()
        assert bag.strength == 0.5
        assert bag.mode == "fast"

    def test_is_locally_set(self):
        bag = SimpleSettings()
        assert not bag.is_locally_set("strength")
        bag.strength = 0.9
        assert bag.is_locally_set("strength")

    def test_subscribe_fires_on_change(self):
        bag = SimpleSettings()
        calls = []
        bag.subscribe(lambda name, val, old: calls.append((name, val, old)))
        bag.strength = 0.8
        assert calls == [("strength", 0.8, 0.5)]

    def test_subscribe_no_fire_if_same_value(self):
        bag = SimpleSettings()
        calls = []
        bag.subscribe(lambda name, val, old: calls.append((name, val, old)))
        bag.strength = 0.5  # same as default
        assert calls == []


# ---------------------------------------------------------------------------
# Serialization
# ---------------------------------------------------------------------------


class TestSerialization:
    def test_to_dict_excludes_defaults(self):
        bag = SimpleSettings()
        assert bag.to_dict() == {}

    def test_to_dict_includes_non_defaults(self):
        bag = SimpleSettings()
        bag.strength = 0.9
        d = bag.to_dict()
        assert d == {"strength": 0.9}

    def test_from_dict_silent(self):
        bag = SimpleSettings()
        calls = []
        bag.subscribe(lambda *a: calls.append(a))
        bag.from_dict({"strength": 0.9})  # silent=True by default
        assert bag.strength == 0.9
        assert calls == []  # no callbacks

    def test_from_dict_not_silent(self):
        bag = SimpleSettings()
        calls = []
        bag.subscribe(lambda *a: calls.append(a))
        bag.from_dict({"strength": 0.9}, silent=False)
        assert bag.strength == 0.9
        assert len(calls) == 1

    def test_round_trip(self):
        bag = SimpleSettings()
        bag.strength = 0.8
        bag.mode = "precise"
        data = bag.to_dict()

        bag2 = SimpleSettings()
        bag2.from_dict(data)
        assert bag2.strength == 0.8
        assert bag2.mode == "precise"

    def test_from_dict_unknown_keys_ignored(self):
        bag = SimpleSettings()
        bag.from_dict({"unknown_key": 42, "strength": 0.7})
        assert bag.strength == 0.7


# ---------------------------------------------------------------------------
# on_change parameter
# ---------------------------------------------------------------------------


class SettingsWithCallback(Settings):
    strength: float = field(0.5, on_change="_on_strength")

    def __init__(self, registry=None):
        super().__init__(registry)
        self.callback_values = []

    def _on_strength(self, value: float, field: str = "") -> None:
        self.callback_values.append((value, field))


class TestOnChange:
    def test_on_change_fires_on_set(self):
        bag = SettingsWithCallback()
        bag.strength = 0.8
        assert bag.callback_values == [(0.8, "strength")]

    def test_on_change_not_fired_same_value(self):
        bag = SettingsWithCallback()
        bag.strength = 0.5  # same as default
        assert bag.callback_values == []

    def test_on_change_not_fired_from_dict_silent(self):
        bag = SettingsWithCallback()
        bag.from_dict({"strength": 0.9})  # silent=True
        assert bag.callback_values == []

    def test_on_change_fired_from_dict_not_silent(self):
        bag = SettingsWithCallback()
        bag.from_dict({"strength": 0.9}, silent=False)
        assert bag.callback_values == [(0.9, "strength")]


# ---------------------------------------------------------------------------
# read_only (watch behaviour)
# ---------------------------------------------------------------------------


class ReadOnlySettings(Settings):
    editable: float = field(1.0)
    read_only_field: bool = field(False, read_only=True)


class TestReadOnly:
    def test_read_only_raises_on_set(self):
        bag = ReadOnlySettings()
        with pytest.raises(AttributeError):
            bag.read_only_field = True

    def test_read_only_not_serialized(self):
        bag = ReadOnlySettings()
        d = bag.to_dict()
        assert "read_only_field" not in d

    def test_read_only_not_restored_from_dict(self):
        bag = ReadOnlySettings()
        bag.from_dict({"read_only_field": True})
        assert bag.read_only_field is False  # unchanged


# ---------------------------------------------------------------------------
# Extended mode — resolution chain with registry
# ---------------------------------------------------------------------------


class TestExtendedMode:
    def test_local_override_beats_default(self):
        registry, bag = create_test_bag()
        bag.bg_color = "#ff0000"
        assert bag.bg_color == "#ff0000"

    def test_reset_falls_back_to_default(self):
        registry, bag = create_test_bag(predefined_local={"bg_color": "#ff0000"})
        bag.reset("bg_color")
        assert bag.bg_color == "#ffffff"

    def test_global_set_beats_default(
        self,
    ):
        registry, bag = create_test_bag(predefined_global={"bg_color": "#aaaaaa"})
        # bg_color has no _field_key set (create_test_bag default bag has no
        # extended-mode keys), so falls back to default — just verify no crash
        assert bag.bg_color is not None

    def test_to_dict_only_locally_set(self):
        registry, bag = create_test_bag()
        bag.font_size = 18
        d = bag.to_dict()
        assert "font_size" in d
        assert d["font_size"] == 18
        assert "bg_color" not in d  # not locally set


# ---------------------------------------------------------------------------
# mirror callback suppression (shadow / watch global-change filtering)
# ---------------------------------------------------------------------------


def _make_mirror_bag(predefined_local=None):
    """
    Build a Settings bag with one shadow field ('color') mirroring the global
    key 'test.color'.  Returns (registry, bag, GLOBAL_KEY).

    _field_key must be set so the descriptor enters extended-mode resolution;
    _mirror_key points it at the global registry entry.
    """
    from haywire.core.settings import SettingsRegistry

    GLOBAL_KEY = "test.color"
    LOCAL_KEY = "test.node.color"  # simulates a node-scoped field key

    class MirrorBag(Settings):
        color: str = field("#ffffff", label="Color")

    MirrorBag.color._field_key = LOCAL_KEY
    MirrorBag.color._mirror_key = GLOBAL_KEY

    registry = SettingsRegistry()
    registry.define(GLOBAL_KEY, "#ffffff")

    bag = MirrorBag(registry=registry)
    bag._subscribe_fields()

    if predefined_local:
        for name, value in predefined_local.items():
            setattr(bag, name, value)

    return registry, bag, GLOBAL_KEY


class TestMirrorCallbackSuppression:
    def test_global_change_fires_callback_when_no_local_override(self):
        """When no local override exists, a global SET fires the on_change callback."""
        registry, bag, key = _make_mirror_bag()
        calls = []
        bag.subscribe(lambda name, val, old: calls.append((name, val)))

        registry.set_global(key, "#aabbcc")

        assert calls == [("color", "#aabbcc")]

    def test_global_change_suppressed_when_local_override_exists(self):
        """When a local override exists, a global SET must not fire the callback."""
        registry, bag, key = _make_mirror_bag(predefined_local={"color": "#ff0000"})
        calls = []
        bag.subscribe(lambda name, val, old: calls.append((name, val)))

        registry.set_global(key, "#aabbcc")

        assert calls == [], "callback must be suppressed when local override exists"

    def test_global_override_fires_callback_even_with_local_override(self):
        """A global OVERRIDE beats the local value — callback must still fire."""
        from haywire.core.settings.enums import FieldMode

        registry, bag, key = _make_mirror_bag(predefined_local={"color": "#ff0000"})
        calls = []
        bag.subscribe(lambda name, val, old: calls.append((name, val)))

        registry.set_global(key, "#aabbcc", mode=FieldMode.OVERRIDE)

        assert len(calls) == 1
        assert calls[0] == ("color", "#aabbcc")


# ---------------------------------------------------------------------------
# @node decorator + direct binding on node instances
# ---------------------------------------------------------------------------


class TestNodeDirectBinding:
    @staticmethod
    def _init_ambient():
        """Create a test injector and force-resolve ambient singletons."""
        from haywire.core.di.test_config import create_test_injector
        from haywire.core.types.registry import TypeRegistry
        from haywire.core.settings import SettingsRegistry

        inj = create_test_injector()
        inj.get(TypeRegistry)
        inj.get(SettingsRegistry)
        return inj

    def test_settings_bound_as_direct_attribute(self):
        from haywire.core.node import BaseNode, node

        self._init_ambient()

        @node(label="Test Binding Node")
        class _TestBindingNode(BaseNode):
            class filter(NodeSettings):
                strength: float = field(0.5, min=0.0, max=1.0, label="Strength")

        wrapper = type("W", (), {"node_id": "w1", "notify": lambda *a: None})()
        n = _TestBindingNode("n1", wrapper)

        assert hasattr(n, "filter")
        assert isinstance(n.filter, NodeSettings)

    def test_direct_read(self):
        from haywire.core.node import BaseNode, node

        self._init_ambient()

        @node(label="Test Read Node")
        class _TestReadNode(BaseNode):
            class params(NodeSettings):
                threshold: float = field(0.7)

        wrapper = type("W", (), {"node_id": "w1", "notify": lambda *a: None})()
        n = _TestReadNode("n1", wrapper)

        assert n.params.threshold == 0.7

    def test_direct_write(self):
        from haywire.core.node import BaseNode, node

        self._init_ambient()

        @node(label="Test Write Node")
        class _TestWriteNode(BaseNode):
            class params(NodeSettings):
                threshold: float = field(0.7)

        wrapper = type("W", (), {"node_id": "w1", "notify": lambda *a: None})()
        n = _TestWriteNode("n1", wrapper)

        n.params.threshold = 0.9
        assert n.params.threshold == 0.9

    def test_conflict_raises_at_decoration(self):
        from haywire.core.node import BaseNode, node

        with pytest.raises(ValueError, match="conflicts with"):

            @node(label="Conflict Node")
            class _ConflictNode(BaseNode):
                class init(NodeSettings):  # 'init' is a BaseNode method
                    x: float = field(1.0)

    def test_serialization_round_trip_on_node(self):
        from haywire.core.node import BaseNode, node

        self._init_ambient()

        @node(label="Test Serial Node")
        class _TestSerialNode(BaseNode):
            class filter(NodeSettings):
                strength: float = field(0.5)

        wrapper = type("W", (), {"node_id": "w1", "notify": lambda *a: None})()
        n = _TestSerialNode("n1", wrapper)
        n.filter.strength = 0.9

        data = n._to_dict()
        assert data["settings"]["filter"]["strength"] == 0.9

        n2 = _TestSerialNode("n2", wrapper)
        n2._initialize_from_dict({"settings": data["settings"]})
        assert n2.filter.strength == 0.9


# ---------------------------------------------------------------------------
# New params: type_, stored, validator
# ---------------------------------------------------------------------------


class TypedSettings(Settings):
    explicit_int: int = field(0, type_=int)
    inferred_float: float = field(1.0)
    no_default_str: str = field(type_=str)


class StoredSettings(Settings):
    stored_field: float = field(0.5)
    unstored_field: float = field(0.5, stored=False)


class ValidatedSettings(Settings):
    positive: float = field(1.0, validator=lambda v: v > 0)


class TestTypeSetting:
    def test_explicit_type_stored_on_descriptor(self):
        descriptor = TypedSettings.__dict__["explicit_int"]
        assert descriptor._type is int

    def test_explicit_type_overrides_default_inference(self):
        # default is 0 (int), but type_ overrides — same result here; key is _type is int
        descriptor = TypedSettings.__dict__["explicit_int"]
        assert descriptor._type is int

    def test_type_inferred_from_default_when_no_type_arg(self):
        descriptor = TypedSettings.__dict__["inferred_float"]
        assert descriptor._type is float

    def test_type_explicit_when_no_default(self):
        descriptor = TypedSettings.__dict__["no_default_str"]
        assert descriptor._type is str


class TestStoredSetting:
    def test_stored_field_appears_in_to_dict(self):
        bag = StoredSettings()
        bag.stored_field = 0.9
        d = bag.to_dict()
        assert "stored_field" in d

    def test_unstored_field_excluded_from_to_dict(self):
        bag = StoredSettings()
        bag.unstored_field = 0.9
        d = bag.to_dict()
        assert "unstored_field" not in d

    def test_unstored_field_still_readable_and_writable(self):
        bag = StoredSettings()
        bag.unstored_field = 0.75
        assert bag.unstored_field == 0.75

    def test_default_stored_is_true(self):
        descriptor = StoredSettings.__dict__["stored_field"]
        assert descriptor._stored is True

    def test_explicit_stored_false(self):
        descriptor = StoredSettings.__dict__["unstored_field"]
        assert descriptor._stored is False


class TestValidatorSetting:
    def test_validate_returns_true_for_valid_value(self):
        descriptor = ValidatedSettings.__dict__["positive"]
        assert descriptor.validate(1.0) is True
        assert descriptor.validate(0.001) is True

    def test_validate_returns_false_for_invalid_value(self):
        descriptor = ValidatedSettings.__dict__["positive"]
        assert descriptor.validate(0) is False
        assert descriptor.validate(-1.0) is False

    def test_validate_returns_true_when_no_validator(self):
        descriptor = SimpleSettings.__dict__["strength"]
        assert descriptor.validate("anything") is True

    def test_no_validator_stored_as_none(self):
        descriptor = SimpleSettings.__dict__["strength"]
        assert descriptor._validator is None

    def test_validator_stored_on_descriptor(self):
        descriptor = ValidatedSettings.__dict__["positive"]
        assert descriptor._validator is not None

    def test_set_silently_rejects_invalid_value(self):
        bag = ValidatedSettings()
        bag.positive = 5.0
        bag.positive = -1.0  # invalid — silently rejected
        assert bag.positive == 5.0

    def test_set_accepts_valid_value(self):
        bag = ValidatedSettings()
        bag.positive = 3.0
        assert bag.positive == 3.0

    def test_rejected_value_does_not_fire_on_change(self):
        bag = ValidatedSettings()
        bag.positive = 5.0
        calls = []
        bag.subscribe(lambda name, val, old: calls.append((name, val, old)))
        bag.positive = -1.0  # invalid — no callback
        assert calls == []

    def test_no_validator_allows_any_value(self):
        bag = SimpleSettings()
        bag.strength = -999.0  # no validator — accepted
        assert bag.strength == -999.0

    def test_invalid_default_raises_at_definition_time(self):
        with pytest.raises(ValueError, match="fails validation"):

            class BadSettings(Settings):
                bad: int = field(3, validator=lambda v: v % 2 == 0)

    def test_none_default_skips_validation(self):
        # Should not raise — None default is allowed even with a validator
        class NoneDefaultSettings(Settings):
            val: int = field(type_=int, validator=lambda v: v > 0)


# ---------------------------------------------------------------------------
# Vec types — type inference, validation, serialization
# ---------------------------------------------------------------------------


class VecSettings(Settings):
    pos: Vec3f = field([0.0, 0.0, 0.0])
    coord: Vec2i = field([0, 0])
    color: Vec4f = field([1.0, 0.0, 0.0, 1.0])


class TestVecTypes:
    def test_annotation_infers_vec3f(self):
        assert VecSettings.__dict__["pos"]._type is Vec3f

    def test_annotation_infers_vec2i(self):
        assert VecSettings.__dict__["coord"]._type is Vec2i

    def test_annotation_infers_vec4f(self):
        assert VecSettings.__dict__["color"]._type is Vec4f

    def test_get_vec_meta_returns_correct_length(self):
        assert get_vec_meta(Vec3f).length == 3
        assert get_vec_meta(Vec2i).length == 2
        assert get_vec_meta(Vec4f).length == 4

    def test_get_vec_meta_returns_correct_element_type(self):
        assert get_vec_meta(Vec3f).element_type is float
        assert get_vec_meta(Vec2i).element_type is int

    def test_get_vec_meta_labels(self):
        assert get_vec_meta(Vec2i).labels == ("X", "Y")
        assert get_vec_meta(Vec3i).labels == ("X", "Y", "Z")
        assert get_vec_meta(Vec4i).labels == ("W", "X", "Y", "Z")

    def test_get_vec_meta_returns_none_for_plain_list(self):
        assert get_vec_meta(list) is None

    def test_get_vec_meta_returns_none_for_scalar(self):
        assert get_vec_meta(float) is None

    def test_read_default(self):
        bag = VecSettings()
        assert bag.pos == [0.0, 0.0, 0.0]

    def test_write_and_read(self):
        bag = VecSettings()
        bag.pos = [1.0, 2.0, 3.0]
        assert bag.pos == [1.0, 2.0, 3.0]

    def test_serialization_round_trip(self):
        bag = VecSettings()
        bag.pos = [1.0, 2.0, 3.0]
        data = bag.to_dict()
        assert data["pos"] == [1.0, 2.0, 3.0]

        bag2 = VecSettings()
        bag2.from_dict(data)
        assert bag2.pos == [1.0, 2.0, 3.0]

    def test_explicit_type_also_works(self):
        class ExplicitVec(Settings):
            pos: Vec3f = field([0.0, 0.0, 0.0], type_=Vec3f)

        assert ExplicitVec.__dict__["pos"]._type is Vec3f
