"""
Tests for build_event_handler_map — the standalone routing utility that scans
handler sources for @handles_event-decorated methods.

These tests exercise the mechanism that allows GraphCanvasManager to delegate
event dispatch to external handler objects instead of hosting every handler
method itself.
"""

import pytest
from haybale_studio.editors.graph_canvas.event_handlers import handles_event, build_event_handler_map
from haybale_studio.editors.graph_canvas.event_definitions import (
    UserDragStartEvent,
    UserDragUpdateEvent,
    SelectionChangedEvent,
)

pytestmark = pytest.mark.unit


# ---------------------------------------------------------------------------
# Scanning behaviour
# ---------------------------------------------------------------------------


def test_scans_single_source():
    """Finds @handles_event methods on a single handler source."""

    class FakeHandlers:
        @handles_event(UserDragStartEvent)
        def on_drag_start(self, event):
            pass

    source = FakeHandlers()
    result = build_event_handler_map([source])

    assert "userDragStart" in result
    assert result["userDragStart"] == source.on_drag_start


def test_scans_multiple_sources():
    """Merges handlers from multiple independent sources."""

    class DragHandlers:
        @handles_event(UserDragStartEvent)
        def on_drag_start(self, event):
            pass

    class SelectionHandlers:
        @handles_event(SelectionChangedEvent)
        def on_selection(self, event):
            pass

    drag = DragHandlers()
    selection = SelectionHandlers()
    result = build_event_handler_map([drag, selection])

    assert "userDragStart" in result
    assert "selectionChanged" in result
    assert result["userDragStart"] == drag.on_drag_start
    assert result["selectionChanged"] == selection.on_selection


def test_later_source_wins_on_collision():
    """When two sources register the same event, the later source takes precedence."""

    class First:
        @handles_event(UserDragStartEvent)
        def handler_a(self, event):
            pass

    class Second:
        @handles_event(UserDragStartEvent)
        def handler_b(self, event):
            pass

    first, second = First(), Second()
    result = build_event_handler_map([first, second])

    assert result["userDragStart"] == second.handler_b


def test_method_handles_multiple_events():
    """A single method decorated with multiple event classes is registered for all of them."""

    class MultiHandler:
        @handles_event(UserDragStartEvent, UserDragUpdateEvent)
        def on_drag(self, event):
            pass

    source = MultiHandler()
    result = build_event_handler_map([source])

    assert "userDragStart" in result
    assert "userDragUpdate" in result
    assert result["userDragStart"] == source.on_drag
    assert result["userDragUpdate"] == source.on_drag


def test_empty_source_list_returns_empty_map():
    """Empty source list produces an empty handler map."""
    result = build_event_handler_map([])
    assert result == {}


def test_source_with_no_handlers_produces_empty_map():
    """Source with no @handles_event methods contributes nothing."""

    class NoHandlers:
        def some_method(self):
            pass

    result = build_event_handler_map([NoHandlers()])
    assert result == {}
