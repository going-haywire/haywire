# tests/core/test_reactive.py
"""
Unit tests for haywire.core.reactive — prop() descriptor + Reactive base class.

Coverage:
- prop() default values, class-level returns descriptor, instance-level returns value
- __set__ fires callbacks, skips when value unchanged
- to_dict() includes only non-default values
- from_dict(silent=True) restores without callbacks
- from_dict(silent=False) fires callbacks
- reset() / reset_all() return to defaults
- .choices property resolves callables
- _prop_fields() walks MRO correctly
- Inheritance: subclass adds fields, parent fields preserved
"""

import pytest
from haywire.core.reactive import prop, Reactive


# ---------------------------------------------------------------------------
# Shared fixtures
# ---------------------------------------------------------------------------

class _Simple(Reactive):
    threshold: float = prop(0.5, label='Threshold', min=0.0, max=1.0)
    verbose:   bool  = prop(False, label='Verbose')
    name:      str   = prop('default', label='Name')


class _WithChoices(Reactive):
    algorithm: str = prop('fast', choices=['fast', 'accurate'])
    dynamic:   str = prop('a',   choices=lambda: ['a', 'b', 'c'])


class _Parent(Reactive):
    x: int = prop(1, label='X')


class _Child(_Parent):
    y: int = prop(2, label='Y')


# ---------------------------------------------------------------------------
# prop descriptor
# ---------------------------------------------------------------------------

class TestPropDescriptor:

    def test_class_level_returns_descriptor(self):
        assert isinstance(_Simple.threshold, prop)

    def test_instance_level_returns_default(self):
        s = _Simple()
        assert s.threshold == 0.5

    def test_instance_level_returns_set_value(self):
        s = _Simple()
        s.threshold = 0.9
        assert s.threshold == 0.9

    def test_bool_default(self):
        s = _Simple()
        assert s.verbose is False

    def test_str_default(self):
        s = _Simple()
        assert s.name == 'default'

    def test_instances_are_independent(self):
        s1 = _Simple()
        s2 = _Simple()
        s1.threshold = 0.1
        assert s2.threshold == 0.5

    def test_attr_name_set(self):
        assert _Simple.threshold._attr_name == 'threshold'
        assert _Simple.verbose._attr_name == 'verbose'

    def test_metadata(self):
        d = _Simple.threshold
        assert d._label == 'Threshold'
        assert d._min == 0.0
        assert d._max == 1.0
        assert d._default == 0.5
        assert d._type is float

    def test_type_inferred_from_default(self):
        assert _Simple.threshold._type is float
        assert _Simple.verbose._type is bool
        assert _Simple.name._type is str

    def test_choices_list(self):
        assert _WithChoices.algorithm.choices == ['fast', 'accurate']

    def test_choices_callable_resolved(self):
        assert _WithChoices.dynamic.choices == ['a', 'b', 'c']

    def test_choices_none(self):
        assert _Simple.threshold.choices is None


# ---------------------------------------------------------------------------
# Callbacks
# ---------------------------------------------------------------------------

class TestCallbacks:

    def test_callback_fired_on_change(self):
        s = _Simple()
        received = []
        s.subscribe(lambda name, value, old: received.append((name, value, old)))
        s.threshold = 0.9
        assert received == [('threshold', 0.9, 0.5)]

    def test_callback_not_fired_when_value_unchanged(self):
        s = _Simple()
        received = []
        s.subscribe(lambda name, value, old: received.append((name, value, old)))
        s.threshold = 0.5  # same as default
        assert received == []

    def test_multiple_callbacks(self):
        s = _Simple()
        log1 = []
        log2 = []
        s.subscribe(lambda n, v, o: log1.append(v))
        s.subscribe(lambda n, v, o: log2.append(v))
        s.threshold = 0.3
        assert log1 == [0.3]
        assert log2 == [0.3]

    def test_unsubscribe(self):
        s = _Simple()
        received = []

        def cb(name, value, old):
            received.append(value)

        s.subscribe(cb)
        s.threshold = 0.1
        s.unsubscribe(cb)
        s.threshold = 0.2
        assert received == [0.1]

    def test_unsubscribe_unknown_is_silent(self):
        s = _Simple()
        s.unsubscribe(lambda: None)  # no error

    def test_duplicate_subscribe_ignored(self):
        s = _Simple()
        received = []

        def cb(name, value, old):
            received.append(value)

        s.subscribe(cb)
        s.subscribe(cb)  # second subscribe should be ignored
        s.threshold = 0.7
        assert received == [0.7]

    def test_callback_exception_does_not_propagate(self):
        s = _Simple()

        def bad_cb(name, value, old):
            raise RuntimeError("boom")

        s.subscribe(bad_cb)
        s.threshold = 0.3   # should not raise


# ---------------------------------------------------------------------------
# Serialization — to_dict
# ---------------------------------------------------------------------------

class TestToDict:

    def test_empty_when_all_defaults(self):
        s = _Simple()
        assert s.to_dict() == {}

    def test_includes_non_default_values(self):
        s = _Simple()
        s.threshold = 0.8
        assert s.to_dict() == {'threshold': 0.8}

    def test_multiple_non_default_values(self):
        s = _Simple()
        s.threshold = 0.8
        s.verbose = True
        data = s.to_dict()
        assert data == {'threshold': 0.8, 'verbose': True}

    def test_revert_to_default_not_included(self):
        s = _Simple()
        s.threshold = 0.8
        s.threshold = 0.5   # back to default
        assert s.to_dict() == {}


# ---------------------------------------------------------------------------
# Serialization — from_dict
# ---------------------------------------------------------------------------

class TestFromDict:

    def test_silent_restores_value(self):
        s = _Simple()
        s.from_dict({'threshold': 0.3})
        assert s.threshold == 0.3

    def test_silent_does_not_fire_callbacks(self):
        s = _Simple()
        received = []
        s.subscribe(lambda n, v, o: received.append(v))
        s.from_dict({'threshold': 0.3}, silent=True)
        assert received == []

    def test_not_silent_fires_callbacks(self):
        s = _Simple()
        received = []
        s.subscribe(lambda n, v, o: received.append(v))
        s.from_dict({'threshold': 0.3}, silent=False)
        assert received == [0.3]

    def test_unknown_keys_ignored(self):
        s = _Simple()
        s.from_dict({'threshold': 0.3, 'unknown_key': 'ignored'})
        assert s.threshold == 0.3  # no exception

    def test_empty_dict(self):
        s = _Simple()
        s.from_dict({})
        assert s.threshold == 0.5  # default unchanged

    def test_round_trip(self):
        s1 = _Simple()
        s1.threshold = 0.77
        s1.verbose = True
        data = s1.to_dict()

        s2 = _Simple()
        s2.from_dict(data)
        assert s2.threshold == 0.77
        assert s2.verbose is True


# ---------------------------------------------------------------------------
# Reset
# ---------------------------------------------------------------------------

class TestReset:

    def test_reset_single_field(self):
        s = _Simple()
        s.threshold = 0.9
        s.reset('threshold')
        assert s.threshold == 0.5

    def test_reset_fires_callback(self):
        s = _Simple()
        s.threshold = 0.9
        received = []
        s.subscribe(lambda n, v, o: received.append(v))
        s.reset('threshold')
        assert received == [0.5]

    def test_reset_all(self):
        s = _Simple()
        s.threshold = 0.9
        s.verbose = True
        s.name = 'changed'
        s.reset_all()
        assert s.threshold == 0.5
        assert s.verbose is False
        assert s.name == 'default'

    def test_reset_unknown_key_raises(self):
        s = _Simple()
        with pytest.raises(KeyError):
            s.reset('nonexistent')


# ---------------------------------------------------------------------------
# _prop_fields — MRO traversal
# ---------------------------------------------------------------------------

class TestPropFields:

    def test_returns_all_props(self):
        fields = _Simple._prop_fields()
        assert 'threshold' in fields
        assert 'verbose' in fields
        assert 'name' in fields

    def test_non_props_excluded(self):
        fields = _Simple._prop_fields()
        assert '_callbacks' not in fields

    def test_child_includes_parent_fields(self):
        fields = _Child._prop_fields()
        assert 'x' in fields
        assert 'y' in fields

    def test_parent_fields_not_polluted_by_child(self):
        parent_fields = _Parent._prop_fields()
        assert 'y' not in parent_fields

    def test_child_inherits_parent_defaults(self):
        c = _Child()
        assert c.x == 1
        assert c.y == 2

    def test_child_fields_independent_of_parent(self):
        p = _Parent()
        c = _Child()
        c.x = 10
        assert p.x == 1


# ---------------------------------------------------------------------------
# Inheritance — props from parent survive in child
# ---------------------------------------------------------------------------

class TestInheritance:

    def test_child_can_set_parent_prop(self):
        c = _Child()
        c.x = 99
        assert c.x == 99

    def test_child_to_dict_includes_parent_fields(self):
        c = _Child()
        c.x = 5
        data = c.to_dict()
        assert data == {'x': 5}

    def test_child_from_dict_restores_parent_field(self):
        c = _Child()
        c.from_dict({'x': 7})
        assert c.x == 7

    def test_child_callback_fires_for_parent_prop(self):
        c = _Child()
        received = []
        c.subscribe(lambda n, v, o: received.append((n, v)))
        c.x = 42
        assert received == [('x', 42)]
