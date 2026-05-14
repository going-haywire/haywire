"""Tests for the @redraw_on / @react_on event-handler decorators.

Covers:
- Successful decoration stores metadata on the function object.
- Multiple event types per decorator are preserved as a tuple.
- Stacking the same decorator twice appends to the tuple.
- @redraw_on and @react_on are independent (a method can carry both).
- get_redraw_on_types / get_react_on_types return () for undecorated functions.
- Argument validation: empty args, signal instance, non-type, non-ContextSignal.
- Public re-export from haywire.core.session works (decorators are importable).
"""

import pytest

import haywire.core.graph.editor  # noqa: F401 — circular-import guard

from haywire.core.session import redraw_on, react_on
from haywire.core.session.handlers import (
    get_redraw_on_types,
    get_react_on_types,
)
from haywire.core.session.events import (
    ContextSignal,
    SelectionMoved,
    GraphDataMutated,
    ActiveGraphMoved,
)


# ---------------------------------------------------------------------------
# @redraw_on
# ---------------------------------------------------------------------------


def test_redraw_on_stores_single_event_type() -> None:
    @redraw_on(SelectionMoved)
    def handler(self, ctx, event):
        pass

    assert get_redraw_on_types(handler) == (SelectionMoved,)


def test_redraw_on_stores_multiple_event_types_in_order() -> None:
    @redraw_on(SelectionMoved, GraphDataMutated, ActiveGraphMoved)
    def handler(self, ctx, event):
        pass

    assert get_redraw_on_types(handler) == (SelectionMoved, GraphDataMutated, ActiveGraphMoved)


def test_redraw_on_stacking_appends_event_types() -> None:
    @redraw_on(SelectionMoved)
    @redraw_on(GraphDataMutated)
    def handler(self, ctx, event):
        pass

    # Decorators apply bottom-up: inner @redraw_on(GraphDataMutated) runs first,
    # outer @redraw_on(SelectionMoved) appends. Final tuple: (GraphDataMutated, SelectionMoved).
    assert get_redraw_on_types(handler) == (GraphDataMutated, SelectionMoved)


def test_redraw_on_returns_function_unchanged() -> None:
    """The decorator must not wrap the function — frameworks rely on identity."""

    def original(self, ctx, event):
        return "result"

    decorated = redraw_on(SelectionMoved)(original)
    assert decorated is original
    assert decorated.__name__ == "original"


def test_redraw_on_rejects_no_args() -> None:
    with pytest.raises(TypeError, match="requires at least one ContextSignal subclass"):
        redraw_on()  # type: ignore[call-overload]


def test_redraw_on_rejects_signal_instance() -> None:
    """Passing an instance instead of the class is a common mistake — catch it."""
    instance = SelectionMoved()
    with pytest.raises(TypeError, match="not a type"):
        redraw_on(instance)  # type: ignore[arg-type]


def test_redraw_on_rejects_non_type_argument() -> None:
    with pytest.raises(TypeError, match="not a type"):
        redraw_on("SelectionMoved")  # type: ignore[arg-type]


def test_redraw_on_rejects_non_contextsignal_type() -> None:
    class NotASignal:
        pass

    with pytest.raises(TypeError, match="not a ContextSignal subclass"):
        redraw_on(NotASignal)  # type: ignore[arg-type]


def test_redraw_on_rejects_str_type() -> None:
    with pytest.raises(TypeError, match="not a ContextSignal subclass"):
        redraw_on(str)  # type: ignore[arg-type]


def test_redraw_on_accepts_contextsignal_base_directly() -> None:
    """Catch-all subscription to the root ContextSignal class is legal (devtools use case)."""

    @redraw_on(ContextSignal)
    def handler(self, ctx, event):
        pass

    assert get_redraw_on_types(handler) == (ContextSignal,)


# ---------------------------------------------------------------------------
# @react_on
# ---------------------------------------------------------------------------


def test_react_on_stores_single_event_type() -> None:
    @react_on(SelectionMoved)
    def handler(self, ctx, event):
        pass

    assert get_react_on_types(handler) == (SelectionMoved,)


def test_react_on_stores_multiple_event_types_in_order() -> None:
    @react_on(SelectionMoved, GraphDataMutated)
    def handler(self, ctx, event):
        pass

    assert get_react_on_types(handler) == (SelectionMoved, GraphDataMutated)


def test_react_on_validation_matches_redraw_on() -> None:
    with pytest.raises(TypeError, match="requires at least one ContextSignal subclass"):
        react_on()  # type: ignore[call-overload]
    with pytest.raises(TypeError, match="not a type"):
        react_on(SelectionMoved())  # type: ignore[arg-type]
    with pytest.raises(TypeError, match="not a ContextSignal subclass"):
        react_on(int)  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# Cross-decorator interaction
# ---------------------------------------------------------------------------


def test_redraw_on_and_react_on_are_independent() -> None:
    """A single method can carry both decorators; metadata does not bleed."""

    @redraw_on(SelectionMoved)
    @react_on(GraphDataMutated)
    def handler(self, ctx, event):
        pass

    assert get_redraw_on_types(handler) == (SelectionMoved,)
    assert get_react_on_types(handler) == (GraphDataMutated,)


def test_undecorated_function_has_empty_metadata() -> None:
    def plain(self, ctx, event):
        pass

    assert get_redraw_on_types(plain) == ()
    assert get_react_on_types(plain) == ()


# ---------------------------------------------------------------------------
# Public re-export
# ---------------------------------------------------------------------------


def test_decorators_are_re_exported_from_session_package() -> None:
    """Authors should be able to ``from haywire.core.session import redraw_on, react_on``."""
    from haywire.core.session import redraw_on as redraw_on_imported
    from haywire.core.session import react_on as react_on_imported

    assert redraw_on_imported is redraw_on
    assert react_on_imported is react_on
