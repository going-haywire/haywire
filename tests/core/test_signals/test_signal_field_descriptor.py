"""Tests for _SignalFieldDescriptor, signal_field(), iter_signal_fields,
_seed_signal_fields. Exercises identity short-circuit, class-level
synthetic class access, shadowing rejection, host validation, mutable-
default deep-copy seeding."""

import pytest
from haywire.core.session.signals import Signal, SignalSource, signal_field
from haywire.core.session.signals.descriptor import (
    iter_signal_fields,
    _seed_signal_fields,
)


class _Recorder(SignalSource):
    """Test-only SignalSource that captures emitted signals in self.emitted.

    Subclasses must NOT define __init__ — they rely on inheriting this
    one to get both the emitted list and signal-field seeding.
    """

    def __init__(self) -> None:
        self.emitted: list[Signal] = []
        _seed_signal_fields(self)

    def _signal_emit(self, signal: Signal) -> None:
        self.emitted.append(signal)


def test_class_level_access_returns_synthetic_signal_class():
    class H(_Recorder):
        x: int = signal_field(0)

    # Class-level access returns the synthetic class.
    assert isinstance(H.x, type)
    assert issubclass(H.x, Signal)


def test_instance_level_access_returns_value():
    class H(_Recorder):
        x: int = signal_field(7)

    h = H()
    assert h.x == 7


def test_write_emits_signal():
    class H(_Recorder):
        x: int = signal_field(0)

    h = H()
    h.x = 5
    assert len(h.emitted) == 1
    assert isinstance(h.emitted[0], H.x)


def test_identity_short_circuit():
    """Same object reassigned is a no-op."""

    class H(_Recorder):
        x: object = signal_field(None)

    h = H()
    sentinel = object()
    h.x = sentinel
    h.emitted.clear()
    h.x = sentinel  # identity-equal — must NOT emit
    assert h.emitted == []


def test_value_equal_but_identity_distinct_fires():
    """Two distinct equal-but-not-identical objects emit on second write."""
    from dataclasses import dataclass

    @dataclass
    class Wrap:
        v: int

    class H(_Recorder):
        x: object = signal_field(None)

    h = H()
    h.x = Wrap(1)
    h.emitted.clear()
    h.x = Wrap(1)  # == True, is False — must emit
    assert len(h.emitted) == 1


def test_non_signal_source_host_rejected_at_class_definition():
    """Using signal_field on a non-SignalSource class raises TypeError."""
    with pytest.raises(TypeError) as ei:

        class Wrong:
            x: int = signal_field(0)

    assert "SignalSource" in str(ei.value)


def test_shadowing_rejected_at_class_definition():
    """Redeclaring a signal field in a subclass raises TypeError."""

    class Base(_Recorder):
        x: int = signal_field(0)

    with pytest.raises(TypeError) as ei:

        class Sub(Base):
            x: int = signal_field(99)  # type: ignore[assignment]

    assert "shadow" in str(ei.value).lower() or "redeclare" in str(ei.value).lower()


def test_mutable_default_deepcopied_per_instance():
    """Mutable defaults like set() are not shared across instances."""

    class H(_Recorder):
        items: set[str] = signal_field(set())

    h1 = H()
    h2 = H()
    h1.items.add("a")
    assert "a" not in h2.items


def test_iter_signal_fields_walks_mro():
    """iter_signal_fields yields (name, initial) for every signal field
    on the class and its bases."""

    class Base(_Recorder):
        a: int = signal_field(1)

    class Sub(Base):
        b: int = signal_field(2)

    fields = dict(iter_signal_fields(Sub))
    assert fields == {"a": 1, "b": 2}


def test_synthetic_signal_class_has_readable_qualname():
    class HostClass(_Recorder):
        field_name: int = signal_field(0)

    # __qualname__ includes the enclosing scope (test function adds <locals>),
    # so assert the suffix and the bare name instead of a literal.
    assert HostClass.field_name.__qualname__.endswith("HostClass.field_name")
    assert HostClass.field_name.__name__ == "field_name"
