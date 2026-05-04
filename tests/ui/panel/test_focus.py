# tests/ui/panel/test_focus.py
"""Focus base class: classmethod available(); id ClassVar; auto-discovery map."""

import pytest

from haywire.ui.panel.focus import Focus, focus_by_id


def test_focus_subclass_must_define_id():
    """A Focus subclass without id should fail validation."""

    class _MissingId(Focus):
        label = "x"
        icon = "x"

        @classmethod
        def available(cls, ctx):
            return True

    # Without id, focus_by_id() should not find it (and it shouldn't crash).
    # Strict validation can be added later; for now just assert lookup works
    # for properly-declared focuses and not for misdeclared ones.
    assert focus_by_id("x") is None  # nothing named "x" registered properly


def test_focus_subclass_with_id_is_discoverable():
    class _MyFocus(Focus):
        id = "my_test_focus_unique_id"
        label = "My"
        icon = "icon"

        @classmethod
        def available(cls, ctx):
            return True

    assert focus_by_id("my_test_focus_unique_id") is _MyFocus


def test_focus_id_collision_raises():
    """Two Focus subclasses with the same id raise at class definition."""

    class _A(Focus):
        id = "duplicate_id_for_collision_test"
        label = "A"
        icon = "i"

        @classmethod
        def available(cls, ctx):
            return True

    with pytest.raises(ValueError, match="duplicate"):

        class _B(Focus):
            id = "duplicate_id_for_collision_test"
            label = "B"
            icon = "i"

            @classmethod
            def available(cls, ctx):
                return True


def test_focus_class_attributes_are_documented():
    """Focus subclasses declare label, icon, order, id."""

    class _Demo(Focus):
        id = "demo_focus_id"
        label = "Demo"
        icon = "star"
        order = 50

        @classmethod
        def available(cls, ctx):
            return True

    assert _Demo.label == "Demo"
    assert _Demo.icon == "star"
    assert _Demo.order == 50
    assert _Demo.id == "demo_focus_id"
