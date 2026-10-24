"""The canvas takes each gesture's level mode from the server's handler table."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock

import pytest

from haybale_graph_editor.editors.graph_canvas.graph_canvas_manager import GraphCanvasManager
from haywire.core.access import LevelMode
from haywire.core.graph.edit_route import EditRoute
from haywire.ui.components.graph import canvas as canvas_module
from haywire.ui.components.graph.canvas import GraphCanvasVue

pytestmark = pytest.mark.unit

CANVAS_VUE = Path(canvas_module.__file__).with_name("canvas.vue")
GRAPH_EVENTS_JS = CANVAS_VUE.with_name("generated") / "graph_events.js"

GESTURE_EVENT_TYPES = {
    "userResizeEnd",
    "userDragStart",
    "userDragUpdate",
    "userDragEnd",
    "edgeCreated",
    "edgeReconnectStarted",
    "userPasteClipboard",
    "contextMenuSelected",
    "contextMenuCanvas",
    "contextMenuEdge",
    "contextMenuPort",
    "contextMenuSurface",
    "enterGroup",
    "selectionChanged",
}


def _bare_canvas_vue() -> Any:
    """A GraphCanvasVue outside any page: its props are a plain dict, updates go nowhere."""
    canvas: Any = object.__new__(GraphCanvasVue)
    canvas._props = {}
    canvas.update = lambda: None
    return canvas


@pytest.fixture
def manager(monkeypatch) -> Any:
    """A GraphCanvasManager with its real handler sources over a canvas outside any page."""
    canvas_vue = _bare_canvas_vue()
    monkeypatch.setattr(GraphCanvasManager, "_setup_canvas", lambda self: (MagicMock(), canvas_vue))
    monkeypatch.setattr(GraphCanvasManager, "_follow_graph_props", lambda self: None)
    return GraphCanvasManager(
        route=EditRoute(lambda: MagicMock(), lambda: LevelMode.EDIT),
        skin_factory=MagicMock(),
        node_factory=MagicMock(),
        panel_registry=MagicMock(),
        session=MagicMock(session_id="session-1"),
    )


def test_every_gesture_event_type_has_a_mode_requirement(manager):
    assert GESTURE_EVENT_TYPES <= manager.canvas_vue._props["gestureRequires"].keys()


def _user_interaction_constants() -> dict[str, str]:
    """``GraphEvents.UserInteractions`` from the generated JS: constant name -> event type."""
    source = GRAPH_EVENTS_JS.read_text()
    block = re.search(r"UserInteractions: \{(.*?)\n  \}", source, re.S)
    assert block is not None
    return dict(re.findall(r"(\w+): '(\w+)'", block.group(1)))


def _checked_constants(source: str) -> list[str]:
    """The constant names the canvas resolves a gesture's mode requirement by."""
    calls = re.findall(r"_allows\(GraphEvents\.UserInteractions\.(\w+)\)", source)
    lookups = re.findall(r"gestureRequires\[GraphEvents\.UserInteractions\.(\w+)\]", source)
    return calls + lookups


def test_every_type_the_canvas_checks_is_a_gesture_event_type():
    source = CANVAS_VUE.read_text()
    constants = _user_interaction_constants()
    names = _checked_constants(source)
    assert names
    assert set(names) <= constants.keys()
    assert {constants[name] for name in names} <= GESTURE_EVENT_TYPES


def test_the_canvas_names_every_checked_type_by_its_constant():
    """A gesture check by string literal (or any other expression) is not resolved above."""
    source = CANVAS_VUE.read_text()
    # Every call but the method's own definition, `_allows(eventType) {`.
    calls = re.findall(r"_allows\(([^)]*)\)(?!\s*\{)", source)
    calls = [arg for arg in calls if arg != "eventType"]
    assert all(arg.startswith("GraphEvents.UserInteractions.") for arg in calls), calls
    assert not re.search(r"gestureRequires\.\w+", source)
    assert not re.search(r"gestureRequires\[['\"]", source)


def test_the_pushed_modes_are_the_handlers_requirements(manager):
    requires = manager.canvas_vue._props["gestureRequires"]
    assert requires["selectionChanged"] == "view"
    assert requires["enterGroup"] == "operate"
    assert requires["userDragStart"] == "edit"
    assert requires["contextMenuSelected"] == "edit"


def test_set_gesture_requires_pushes_mode_values():
    canvas = _bare_canvas_vue()
    canvas.set_gesture_requires({"enterGroup": LevelMode.OPERATE, "userDragStart": LevelMode.EDIT})
    assert canvas._props["gestureRequires"] == {"enterGroup": "operate", "userDragStart": "edit"}
