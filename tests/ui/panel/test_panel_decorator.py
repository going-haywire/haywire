# tests/ui/panel/test_panel_decorator.py
"""@panel(surface=..., hosts=...) — validation and identity."""

from typing import Protocol, runtime_checkable

import pytest

from haywire.core.signals import SelectionMoved, GraphDataMutated
from haywire.ui.panel import BasePanel, panel
from haywire.ui.surface import Surface


@runtime_checkable
class _DummyActions(Protocol):
    def do_thing(self) -> None: ...


class _DummySurface(Surface):
    id = "decorator_test_surface"


class _NestedSurface(Surface):
    id = "decorator_test_nested"


def test_surface_set_from_decorator_kwarg():
    @panel(
        surface=_DummySurface,
        label="My Panel",
    )
    class P(BasePanel):
        actions: _DummyActions  # type-checker visibility only

        def draw(self, ctx, layout):
            pass

    assert P.class_identity.label == "My Panel"
    assert P.class_identity.surface is _DummySurface


def test_hosts_defaults_to_empty_tuple():
    """A panel declaring no hosts= is a leaf — what the emptiness rule counts."""

    @panel(
        surface=_DummySurface,
        label="Leaf Panel",
    )
    class P(BasePanel):
        def draw(self, ctx, layout):
            pass

    assert P.class_identity.hosts == ()


def test_hosts_stored_as_declared():
    @panel(
        surface=_DummySurface,
        hosts=(_NestedSurface,),
        label="Hosting Panel",
    )
    class P(BasePanel):
        def draw(self, ctx, layout):
            pass

    assert P.class_identity.hosts == (_NestedSurface,)


def test_panel_surface_must_subclass_surface():
    class _NotASurface:
        pass

    with pytest.raises(TypeError, match="surface"):

        @panel(
            surface=_NotASurface,  # type: ignore[arg-type]
            label="Bad",
        )
        class P(BasePanel):
            def draw(self, ctx, layout):
                pass


def test_panel_hosts_entries_must_subclass_surface():
    class _NotASurface:
        pass

    with pytest.raises(TypeError, match="hosts"):

        @panel(
            surface=_DummySurface,
            hosts=(_NotASurface,),  # type: ignore[arg-type]
            label="Bad",
        )
        class P(BasePanel):
            def draw(self, ctx, layout):
                pass


def test_panel_surface_is_required():
    with pytest.raises(ValueError, match="surface"):

        @panel(label="No surface")
        class P(BasePanel):
            def draw(self, ctx, layout):
                pass


def test_panel_rejects_focus_kwarg():
    """Clean break: focus= is not an accepted-but-deprecated alias."""
    with pytest.raises((ValueError, TypeError)):

        @panel(focus=_DummySurface, label="Old vocabulary")  # type: ignore[call-arg]
        class P(BasePanel):
            def draw(self, ctx, layout):
                pass


def test_panel_label_is_required():
    with pytest.raises(ValueError, match="label"):

        @panel(
            surface=_DummySurface,
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

    @panel(surface=_DummySurface, label="No Subscriptions")
    class P(BasePanel):
        def draw(self, ctx, layout):
            pass

    assert P.class_identity.redraw_on == ()


def test_panel_redraw_on_accepts_single_event_type():
    @panel(
        surface=_DummySurface,
        label="Selection",
        redraw_on=(SelectionMoved,),
    )
    class P(BasePanel):
        def draw(self, ctx, layout):
            pass

    assert P.class_identity.redraw_on == (SelectionMoved,)


def test_panel_redraw_on_accepts_multiple_event_types_in_order():
    @panel(
        surface=_DummySurface,
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
            surface=_DummySurface,
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
            surface=_DummySurface,
            label="Bad",
            redraw_on=(NotASignal,),  # type: ignore[arg-type]
        )
        class P(BasePanel):
            def draw(self, ctx, layout):
                pass


def test_deprecation_warning_stored_on_identity():
    @panel(
        surface=_DummySurface,
        label="Old Panel",
        deprecation_warning="Use NewPanel instead.",
    )
    class OldPanel(BasePanel):
        def draw(self, ctx, layout):
            pass

    assert OldPanel.class_identity.deprecation_warning == "Use NewPanel instead."


def test_deprecation_warning_defaults_to_empty_string():
    @panel(
        surface=_DummySurface,
        label="Fine Panel",
    )
    class FinePanel(BasePanel):
        def draw(self, ctx, layout):
            pass

    assert FinePanel.class_identity.deprecation_warning == ""


def test_panel_redraw_on_error_mentions_panel_context():
    """Error message should make clear the failure is from @panel(redraw_on=...)."""
    with pytest.raises(TypeError, match=r"@panel\(\.\.\., redraw_on=\.\.\.\)"):

        @panel(
            surface=_DummySurface,
            label="Bad",
            redraw_on=(str,),  # type: ignore[arg-type]
        )
        class P(BasePanel):
            def draw(self, ctx, layout):
                pass
