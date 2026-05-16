# tests/ui/panel/test_panel_decorator.py
"""@panel with actions= kwarg and focus= validates required args."""

from typing import Protocol, runtime_checkable

import pytest

from haywire.core.session.signals import SelectionMoved, GraphDataMutated
from haywire.ui.panel import BasePanel, panel
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


def test_action_protocol_set_from_decorator_kwarg():
    @panel(
        actions=_DummyActions,
        focus=_DummyFocus,
        label="My Panel",
    )
    class P(BasePanel):
        actions: _DummyActions  # type-checker visibility only

        def draw(self, ctx, layout):
            pass

    assert P.class_identity.label == "My Panel"
    assert P.class_identity.action_protocol is _DummyActions
    assert P.class_identity.focus is _DummyFocus


def test_decorator_actions_is_optional_defaults_to_none():
    """Display panels (no actions= decorator arg) get action_protocol=None."""

    @panel(
        focus=_DummyFocus,
        label="Display Panel",
    )
    class P(BasePanel):
        def draw(self, ctx, layout):
            pass

    assert P.class_identity.action_protocol is None
    assert P.class_identity.focus is _DummyFocus


def test_panel_focus_must_subclass_focus():
    class _NotAFocus:
        pass

    with pytest.raises(TypeError, match="focus"):

        @panel(
            focus=_NotAFocus,  # type: ignore[arg-type]
            label="Bad",
        )
        class P(BasePanel):
            def draw(self, ctx, layout):
                pass


def test_panel_focus_is_required():
    with pytest.raises(ValueError, match="focus"):

        @panel(label="No focus")
        class P(BasePanel):
            def draw(self, ctx, layout):
                pass


def test_panel_label_is_required():
    with pytest.raises(ValueError, match="label"):

        @panel(
            focus=_DummyFocus,
            # label missing
        )
        class P(BasePanel):
            def draw(self, ctx, layout):
                pass


# ---------------------------------------------------------------------------
# redraw_on= (event-bus redesign, PR #1, Step 3)
# ---------------------------------------------------------------------------


def test_panel_redraw_on_defaults_to_empty_tuple():
    """Panels that don't declare redraw_on= contribute no event subscriptions."""

    @panel(focus=_DummyFocus, label="No Subscriptions")
    class P(BasePanel):
        def draw(self, ctx, layout):
            pass

    assert P.class_identity.redraw_on == ()


def test_panel_redraw_on_accepts_single_event_type():
    @panel(
        focus=_DummyFocus,
        label="Selection",
        redraw_on=(SelectionMoved,),
    )
    class P(BasePanel):
        def draw(self, ctx, layout):
            pass

    assert P.class_identity.redraw_on == (SelectionMoved,)


def test_panel_redraw_on_accepts_multiple_event_types_in_order():
    @panel(
        focus=_DummyFocus,
        label="Two events",
        redraw_on=(SelectionMoved, GraphDataMutated),
    )
    class P(BasePanel):
        def draw(self, ctx, layout):
            pass

    assert P.class_identity.redraw_on == (SelectionMoved, GraphDataMutated)


def test_panel_redraw_on_rejects_signal_instance():
    """Passing an instance instead of the class is a common mistake."""
    with pytest.raises(TypeError, match="not a type"):

        @panel(
            focus=_DummyFocus,
            label="Bad",
            redraw_on=(SelectionMoved(),),  # type: ignore[arg-type]
        )
        class P(BasePanel):
            def draw(self, ctx, layout):
                pass


def test_panel_redraw_on_rejects_non_signal_type():
    class NotASignal:
        pass

    with pytest.raises(TypeError, match="not a Signal subclass"):

        @panel(
            focus=_DummyFocus,
            label="Bad",
            redraw_on=(NotASignal,),  # type: ignore[arg-type]
        )
        class P(BasePanel):
            def draw(self, ctx, layout):
                pass


def test_panel_redraw_on_error_mentions_panel_context():
    """Error message should make clear the failure is from @panel(redraw_on=...)."""
    with pytest.raises(TypeError, match=r"@panel\(\.\.\., redraw_on=\.\.\.\)"):

        @panel(
            focus=_DummyFocus,
            label="Bad",
            redraw_on=(str,),  # type: ignore[arg-type]
        )
        class P(BasePanel):
            def draw(self, ctx, layout):
                pass
