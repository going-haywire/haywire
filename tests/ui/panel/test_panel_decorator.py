# tests/ui/panel/test_panel_decorator.py
"""@panel with action= and focus= validates required args."""

from typing import Protocol, runtime_checkable

import pytest

from haywire.ui.panel import Panel, panel
from haywire.ui.panel.focus import Focus


@runtime_checkable
class _DummyActions(Protocol):
    def do_thing(self) -> None: ...


class _DummyFocus(Focus):
    id = "decorator_test_focus"
    label = "Test"
    icon = "x"

    @classmethod
    def available(cls, ctx):
        return True


def test_panel_with_action_and_focus_validates_and_sets_identity():
    @panel(
        action=_DummyActions,
        focus=_DummyFocus,
        label="My Panel",
    )
    class P(Panel):
        def draw(self, ctx, layout, actions):
            pass

    assert P.class_identity.label == "My Panel"
    assert P.class_identity.action is _DummyActions
    assert P.class_identity.focus is _DummyFocus


def test_panel_action_must_be_a_class():
    with pytest.raises(TypeError, match="action"):

        @panel(
            action="not_a_class",  # type: ignore[arg-type]
            focus=_DummyFocus,
            label="Bad",
        )
        class P(Panel):
            def draw(self, ctx, layout, actions):
                pass


def test_panel_focus_must_subclass_focus():
    class _NotAFocus:
        pass

    with pytest.raises(TypeError, match="focus"):

        @panel(
            action=_DummyActions,
            focus=_NotAFocus,  # type: ignore[arg-type]
            label="Bad",
        )
        class P(Panel):
            def draw(self, ctx, layout, actions):
                pass


def test_panel_action_is_required():
    with pytest.raises(ValueError, match="action"):

        @panel(focus=_DummyFocus, label="No action")
        class P(Panel):
            def draw(self, ctx, layout, actions):
                pass


def test_panel_focus_is_required():
    with pytest.raises(ValueError, match="focus"):

        @panel(action=_DummyActions, label="No focus")
        class P(Panel):
            def draw(self, ctx, layout, actions):
                pass


def test_panel_label_is_required():
    with pytest.raises(ValueError, match="label"):

        @panel(
            action=_DummyActions,
            focus=_DummyFocus,
            # label missing
        )
        class P(Panel):
            def draw(self, ctx, layout, actions):
                pass
