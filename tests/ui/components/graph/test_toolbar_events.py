"""Round-trip tests for the floating-toolbar graph events."""

from haywire.ui.components.graph.event_definitions import (
    GRAPH_EVENT_REGISTRY,
    SelectionBoundsEvent,
    SelectionBoundsHideEvent,
    ToolbarActionEvent,
)


def test_selection_bounds_event_registered_and_roundtrips():
    assert "selectionBounds" in GRAPH_EVENT_REGISTRY
    ev = SelectionBoundsEvent(left=10.0, top=20.0, right=110.0, bottom=70.0)
    data = ev.to_dict()
    assert data["event_type"] == "selectionBounds"
    back = SelectionBoundsEvent.from_dict(data)
    assert (back.left, back.top, back.right, back.bottom) == (10.0, 20.0, 110.0, 70.0)


def test_selection_bounds_hide_event_registered():
    assert "selectionBoundsHide" in GRAPH_EVENT_REGISTRY
    ev = SelectionBoundsHideEvent()
    assert ev.to_dict()["event_type"] == "selectionBoundsHide"


def test_toolbar_action_event_registered_and_roundtrips():
    assert "toolbarAction" in GRAPH_EVENT_REGISTRY
    ev = ToolbarActionEvent(actionId="copy")
    back = ToolbarActionEvent.from_dict(ev.to_dict())
    assert back.actionId == "copy"
