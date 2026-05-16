"""
Tests for InteractionHandlers — handles drag and edge-click events.

InteractionHandlers is a stateless handler object that translates canvas drag
events into Editor calls (which handle undo internally).
"""

import pytest
from unittest.mock import MagicMock

from haybale_graph_editor.editors.graph_canvas.handlers.interaction import InteractionHandlers
from haybale_graph_editor.editors.graph_canvas.event_definitions import (
    UserDragStartEvent,
    UserDragUpdateEvent,
    UserDragEndEvent,
)
from haybale_graph_editor.editors.graph_canvas.event_handlers import build_event_handler_map

pytestmark = pytest.mark.unit


@pytest.fixture
def editor():
    return MagicMock()


@pytest.fixture
def handler(editor):
    return InteractionHandlers(editor=editor)


# ---------------------------------------------------------------------------
# Drag start
# ---------------------------------------------------------------------------


def test_drag_start_calls_add_fence(handler, editor):
    """DragStart places an undo fence on the editor."""
    handler.process_drag_start(UserDragStartEvent(nodes=["n1"]))
    editor.add_fence.assert_called_once()


def test_drag_start_does_not_move_nodes(handler, editor):
    """DragStart must not call move_nodes — only fences."""
    handler.process_drag_start(UserDragStartEvent(nodes=["n1"]))
    editor.move_nodes.assert_not_called()


# ---------------------------------------------------------------------------
# Drag update
# ---------------------------------------------------------------------------


def test_drag_update_calls_move_nodes(handler, editor):
    """DragUpdate forwards node IDs and delta to editor.move_nodes."""
    handler.process_drag_update(UserDragUpdateEvent(nodes=["n1", "n2"], deltaX=15.0, deltaY=-8.5))
    editor.move_nodes.assert_called_once_with(["n1", "n2"], 15.0, -8.5)


def test_drag_update_with_empty_node_list(handler, editor):
    """DragUpdate with no nodes still forwards the call (editor decides)."""
    handler.process_drag_update(UserDragUpdateEvent(nodes=[], deltaX=0.0, deltaY=0.0))
    editor.move_nodes.assert_called_once_with([], 0.0, 0.0)


# ---------------------------------------------------------------------------
# Drag end
# ---------------------------------------------------------------------------


def test_drag_end_calls_add_fence(handler, editor):
    """DragEnd places a closing undo fence on the editor."""
    handler.process_drag_end(UserDragEndEvent(nodes=["n1"]))
    editor.add_fence.assert_called_once()


# ---------------------------------------------------------------------------
# Handler registration
# ---------------------------------------------------------------------------


def test_all_interaction_events_are_registered(handler):
    """All expected event types are discoverable via @handles_event."""
    result = build_event_handler_map([handler])

    assert "userDragStart" in result
    assert "userDragUpdate" in result
    assert "userDragEnd" in result
    assert "edgeClicked" in result
