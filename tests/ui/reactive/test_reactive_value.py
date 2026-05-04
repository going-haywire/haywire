"""Phase 1: Reactive[T] is a value holder. No tracking yet."""

from haywire.ui.reactive import Reactive


def test_reactive_holds_initial_value():
    r: Reactive[int] = Reactive(42)
    assert r.value == 42


def test_reactive_value_setter_updates():
    r: Reactive[int] = Reactive(0)
    r.value = 7
    assert r.value == 7


def test_reactive_equal_write_is_noop():
    """Writing an equal-but-different-identity value short-circuits and preserves the original object."""
    original = [1, 2]
    r: Reactive[list[int]] = Reactive(original)
    r.value = [1, 2]  # equal by value, different object
    assert r.value is original  # short-circuit fired: identity preserved


def test_reactive_handles_none_initial():
    r: Reactive[int | None] = Reactive(None)
    assert r.value is None
    r.value = 3
    assert r.value == 3


def test_reactive_repr_includes_value():
    r: Reactive[str] = Reactive("hello")
    assert "hello" in repr(r)
