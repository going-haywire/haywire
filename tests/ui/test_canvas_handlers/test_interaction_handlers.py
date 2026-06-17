"""
Tests for InteractionHandlers — handles drag and edge-click events.

InteractionHandlers is a stateless handler object that translates canvas drag
events into Editor calls (which handle undo internally).
"""

import pytest
from unittest.mock import MagicMock

from haybale_graph_editor.editors.graph_canvas.handlers.interaction import InteractionHandlers
from haywire.ui.components.graph.event_definitions import (
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
    """DragStart must not call move_nodes_to — only fences."""
    handler.process_drag_start(UserDragStartEvent(nodes=["n1"]))
    editor.move_nodes_to.assert_not_called()


# ---------------------------------------------------------------------------
# Drag update
# ---------------------------------------------------------------------------


def test_drag_update_calls_move_nodes_to(handler, editor):
    """DragUpdate forwards absolute positions to editor.move_nodes_to."""
    positions = {"n1": {"x": 100.0, "y": 80.0}, "n2": {"x": 200.0, "y": 160.0}}
    handler.process_drag_update(UserDragUpdateEvent(positions=positions))
    editor.move_nodes_to.assert_called_once_with(positions)


def test_drag_update_with_empty_positions(handler, editor):
    """DragUpdate with no positions still forwards the call (editor decides)."""
    handler.process_drag_update(UserDragUpdateEvent(positions={}))
    editor.move_nodes_to.assert_called_once_with({})


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
