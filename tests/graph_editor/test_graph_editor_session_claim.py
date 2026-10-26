"""Which GraphEditor's level the session's graph state describes, with two editors shown at once.

Split panes show two graph editors side by side, each the focused tab of its
own slot. The session's ``active_graph`` / ``level_mode`` are what the
panels gate on, so they must describe the graph the selection lives in: the
editor a pointer-down lands in claims the session, and an editor the user is
not working in never does.
"""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any, cast
from unittest.mock import MagicMock

import pytest

from haybale_graph_editor.editors import graph_editor as graph_editor_module
from haybale_graph_editor.editors.graph_canvas.event_handlers import build_event_handler_map, handles_event
from haybale_graph_editor.editors.graph_canvas.graph_canvas_manager import (
    POINTER_GESTURE_EVENTS,
    GraphCanvasManager,
)
from haybale_graph_editor.editors.graph_canvas.handlers.selection import SelectionHandlers
from haybale_graph_editor.editors.graph_editor import DOCUMENT_LEVEL, GraphEditor
from haybale_graph_editor.protocols import SubgraphContainer
from haybale_graph_editor.state.edit_state import EditState
from haywire.core.access import AccessTier, LevelMode
from haywire.core.session.context import SessionContext
from haywire.core.session.handlers import _REACT_ON_ATTR
from haywire.core.signals import SelectionMoved
from haywire.ui.components.graph.event_definitions import (
    BaseGraphEvent,
    CanvasMountedEvent,
    ContextMenuCanvasEvent,
    ContextMenuEdgeEvent,
    ContextMenuPortEvent,
    ContextMenuSelectedEvent,
    ContextMenuSurfaceEvent,
    EdgeClickedEvent,
    EdgeCreatedEvent,
    EdgeReconnectStartedEvent,
    EnterGroupEvent,
    NodesMeasuredEvent,
    SelectionBoundsEvent,
    SelectionBoundsHideEvent,
    SelectionChangedEvent,
    UserDragStartEvent,
    UserResizeEndEvent,
)

from tests.graph_editor.test_graph_editor_lock import _locked_editor

from .test_graph_editor_levels import _assert_selection_dropped, _select, _two_tabs
from .test_graph_editor_placement_levels import _PLACEMENT_KEY, _open_placement, _placement_definition

pytestmark = pytest.mark.unit


def _binding(editor: GraphEditor, binding_id: str) -> str:
    """Give ``editor`` the editor binding id its root carries as ``data-hw-binding``; return it."""
    cast(Any, editor.wrapper).editor_binding_id = binding_id
    return binding_id


def _retarget(context: Any, binding_id: str, *editors: GraphEditor) -> None:
    """Point the session's target at ``binding_id`` and dispatch the change as the session bus does."""
    context.target_binding_id = binding_id
    for editor in editors:
        editor._on_target_moved(context, None)


def _published(context: Any) -> list[type]:
    return [type(call.args[0]) for call in context.session.publish.call_args_list]


def _split_panes() -> tuple[GraphEditor, GraphEditor, Any, Any]:
    """Editor A on an unlocked document, editor B inside a locked macro placement; A holds the session.

    Returns A, B, the session context and the session's EditState, which holds
    a node of A's document as its selection.
    """
    a, b, context, _b_document = _two_tabs()
    _binding(a, "graph::/tmp/graphs/main.haywire")
    _binding(b, "graph::/tmp/graphs/other.haywire")
    _open_placement(b, context)
    edit_state = _select(a, context, MagicMock(name="a_node"))
    context.target_binding_id = a.wrapper.editor_binding_id
    return a, b, context, edit_state


def _interior_graph(editor: GraphEditor) -> Any:
    return editor._levels[_PLACEMENT_KEY].container.editor.graph


class TestTheEditorAClickLandsInClaims:
    def test_the_editor_reacts_to_the_target_moving(self):
        assert getattr(GraphEditor._on_target_moved, _REACT_ON_ATTR, ()) == (
            SessionContext.target_binding_id,
        )

    def test_a_pointer_down_on_the_other_pane_moves_the_session_to_its_level(self):
        a, b, context, edit_state = _split_panes()

        _retarget(context, b.wrapper.editor_binding_id, a, b)

        assert edit_state.active_graph is _interior_graph(b)
        assert context.level_mode is LevelMode.OPERATE
        _assert_selection_dropped(context, edit_state)

    def test_the_click_selection_lands_after_the_claim_and_stays(self):
        a, b, context, edit_state = _split_panes()
        b_node = MagicMock(name="b_interior_node")

        _retarget(context, b.wrapper.editor_binding_id, a, b)
        edit_state.active_node = b_node  # the canvas's selection event, which follows the pointer-down
        _retarget(context, b.wrapper.editor_binding_id, a, b)

        assert edit_state.active_node is b_node
        assert edit_state.active_graph is _interior_graph(b)
        assert context.level_mode is LevelMode.OPERATE

    def test_clicking_back_in_the_first_pane_drops_the_other_panes_selection(self):
        a, b, context, edit_state = _split_panes()
        _retarget(context, b.wrapper.editor_binding_id, a, b)
        edit_state.active_node = MagicMock(name="b_interior_node")
        context.session.publish.reset_mock()

        _retarget(context, a.wrapper.editor_binding_id, a, b)

        assert edit_state.active_graph is a._levels[DOCUMENT_LEVEL].container.editor.graph
        assert context.level_mode is LevelMode.EDIT
        _assert_selection_dropped(context, edit_state)

    def test_a_pointer_down_in_another_editor_claims_nothing(self):
        a, b, context, edit_state = _split_panes()
        a_node = edit_state.active_node
        context.session.publish.reset_mock()

        _retarget(context, "studio:editors:Shortcuts", a, b)

        assert edit_state.active_graph is a._levels[DOCUMENT_LEVEL].container.editor.graph
        assert edit_state.active_node is a_node
        context.session.publish.assert_not_called()


class TestABackgroundEditorLeavesTheSessionAlone:
    """A level change in an editor the session is not on updates that editor only."""

    def test_a_reload_repointing_a_background_level_keeps_the_session(self):
        a, b, context, edit_state = _split_panes()
        a_graph, a_node = edit_state.active_graph, edit_state.active_node
        context.session.publish.reset_mock()
        reloaded = _placement_definition(_PLACEMENT_KEY)
        b._levels[DOCUMENT_LEVEL].container.editor.graph.subgraphs[_PLACEMENT_KEY] = reloaded

        b._prune_dead_levels(context)

        container = b._levels[_PLACEMENT_KEY].container
        assert isinstance(container, SubgraphContainer)
        assert container.definition is reloaded
        assert b._active_level == _PLACEMENT_KEY
        assert edit_state.active_graph is a_graph
        assert context.level_mode is LevelMode.EDIT
        assert edit_state.active_node is a_node
        assert SelectionMoved not in _published(context)

    def test_closing_a_background_editors_level_keeps_the_session(self):
        a, b, context, edit_state = _split_panes()
        a_graph, a_node = edit_state.active_graph, edit_state.active_node
        context.session.publish.reset_mock()
        del b._levels[DOCUMENT_LEVEL].container.editor.graph.subgraphs[_PLACEMENT_KEY]

        b._prune_dead_levels(context)

        assert list(b._levels) == [DOCUMENT_LEVEL]
        assert b._active_level == DOCUMENT_LEVEL
        assert edit_state.active_graph is a_graph
        assert edit_state.active_node is a_node
        assert SelectionMoved not in _published(context)

    def test_the_background_editor_claims_its_new_level_when_focused(self):
        _a, b, context, edit_state = _split_panes()
        reloaded = _placement_definition(_PLACEMENT_KEY)
        b._levels[DOCUMENT_LEVEL].container.editor.graph.subgraphs[_PLACEMENT_KEY] = reloaded
        b._prune_dead_levels(context)

        b.on_focus(context)

        assert edit_state.active_graph is reloaded
        assert context.level_mode is LevelMode.OPERATE

    def test_the_editor_the_session_is_on_still_follows_its_reload(self):
        _a, b, context, edit_state = _split_panes()
        _retarget(context, b.wrapper.editor_binding_id, b)
        reloaded = _placement_definition(_PLACEMENT_KEY)
        b._levels[DOCUMENT_LEVEL].container.editor.graph.subgraphs[_PLACEMENT_KEY] = reloaded

        b._prune_dead_levels(context)

        assert edit_state.active_graph is reloaded
        assert context.level_mode is LevelMode.OPERATE


_CONTEXT_MENU_EVENTS = [
    ContextMenuCanvasEvent(screenX=1, screenY=2, canvasX=3, canvasY=4),
    ContextMenuEdgeEvent(screenX=1, screenY=2, canvasX=3, canvasY=4, edge_id="e1"),
    ContextMenuSelectedEvent(
        screenX=1, screenY=2, canvasX=3, canvasY=4, selectedNodes=["b1"], selectedEdges=[]
    ),
    ContextMenuSurfaceEvent(screenX=1, screenY=2, canvasX=3, canvasY=4, nodeId="b1", surfaceId="s"),
    ContextMenuPortEvent(screenX=1, screenY=2, canvasX=3, canvasY=4, nodeId="b1", portId="p"),
]

_BACKGROUND_EVENTS = [
    CanvasMountedEvent(),
    NodesMeasuredEvent(measurements=[{"nodeId": "b1", "width": 10.0, "height": 10.0}]),
    SelectionBoundsEvent(left=0.0, top=0.0, right=10.0, bottom=10.0),
    SelectionBoundsHideEvent(),
]


class _Recorder:
    """Handler source recording the session's ``active_graph`` each event found on arrival."""

    def __init__(self, context: Any) -> None:
        self._context = context
        self.seen: list[Any] = []

    @handles_event(
        ContextMenuCanvasEvent,
        ContextMenuEdgeEvent,
        ContextMenuSelectedEvent,
        ContextMenuSurfaceEvent,
        ContextMenuPortEvent,
        CanvasMountedEvent,
        NodesMeasuredEvent,
        SelectionBoundsEvent,
        SelectionBoundsHideEvent,
        requires=LevelMode.VIEW,
    )
    def record(self, event: BaseGraphEvent) -> None:
        self.seen.append(self._context.data[EditState].active_graph)


def _mount_canvas(monkeypatch, editor: GraphEditor, context: Any, key: str) -> tuple[Any, _Recorder]:
    """Build the canvas of ``editor``'s level ``key`` through the real ``_build_canvas``.

    The manager is a real ``GraphCanvasManager`` holding only what
    ``_handle_canvas_event`` reads; it dispatches selection to real
    ``SelectionHandlers`` over the level's graph and everything else to a
    ``_Recorder``. Returns the manager and the recorder.
    """
    level = editor._levels[key]
    graph = level.container.editor.graph
    session = SimpleNamespace(context=context, publish=lambda signal: context.session.publish(signal))
    recorder = _Recorder(context)

    def construct(**kwargs: Any) -> Any:
        manager: Any = object.__new__(GraphCanvasManager)
        manager._session = session
        manager.route = level.route
        manager.visual_layer = MagicMock()
        manager.zoom_container = MagicMock()
        manager.sync_with_graph = MagicMock()
        manager._toolbar_provider = None
        if "on_user_event" in kwargs:
            manager._on_user_event = kwargs["on_user_event"]
        selection = SelectionHandlers(
            graph=graph, route=MagicMock(), session_id="s1", session=cast(Any, session)
        )
        manager._event_handlers = build_event_handler_map([selection, recorder])
        return manager

    monkeypatch.setattr(graph_editor_module, "GraphCanvasManager", construct)
    editor._project_state = MagicMock()
    context.session_id = "session-1"
    manager = editor._build_canvas(context, level.route)
    assert manager is not None
    level.canvases["patch"] = manager
    return manager, recorder


def _residual_path(monkeypatch) -> tuple[GraphEditor, GraphEditor, Any, Any, Any, _Recorder]:
    """Split panes after: a click in B (B claims), then a slot-tab click in A's pane (A claims).

    The target stays on B, so a further click in B reports no target move.
    Returns A, B, the context, the EditState, B's on-screen canvas and its recorder.
    """
    a, b, context, edit_state = _split_panes()
    context.can_access = AccessTier.ADMIN.satisfies
    _mount_canvas(monkeypatch, b, context, DOCUMENT_LEVEL)
    manager, recorder = _mount_canvas(monkeypatch, b, context, _PLACEMENT_KEY)
    _retarget(context, b.wrapper.editor_binding_id, a, b)
    a.on_focus(context)
    assert edit_state.active_graph is a._levels[DOCUMENT_LEVEL].container.editor.graph
    context.session.publish.reset_mock()
    return a, b, context, edit_state, manager, recorder


class TestAGestureOnACanvasClaimsTheSession:
    """A pointer gesture on a canvas claims the session for its editor, whatever the target says."""

    def test_the_gesture_events_are_the_pointer_initiated_ones(self):
        assert POINTER_GESTURE_EVENTS == {
            SelectionChangedEvent,
            ContextMenuCanvasEvent,
            ContextMenuEdgeEvent,
            ContextMenuSelectedEvent,
            ContextMenuSurfaceEvent,
            ContextMenuPortEvent,
            EdgeClickedEvent,
            EdgeReconnectStartedEvent,
            EdgeCreatedEvent,
            UserDragStartEvent,
            UserResizeEndEvent,
            EnterGroupEvent,
        }

    def test_a_click_on_the_other_pane_claims_its_level_and_selects_there_below_edit(self, monkeypatch):
        _a, b, context, edit_state, manager, _ = _residual_path(monkeypatch)
        interior_node = MagicMock(name="b_interior_node")
        _interior_graph(b).node_wrappers["b1"] = interior_node

        manager._handle_canvas_event(
            SelectionChangedEvent(selectedNodes=["b1"], selectedEdges=[], activeNodeId="b1")
        )

        assert edit_state.active_graph is _interior_graph(b)
        assert context.level_mode is LevelMode.OPERATE
        assert edit_state.active_node is interior_node
        assert edit_state.selected_nodes == {"b1"}

    @pytest.mark.parametrize("event", _CONTEXT_MENU_EVENTS, ids=lambda e: e.event_type)
    def test_a_context_menu_resolves_against_the_canvas_it_opened_on(self, monkeypatch, event):
        _a, b, context, edit_state, manager, recorder = _residual_path(monkeypatch)

        manager._handle_canvas_event(event)

        assert recorder.seen == [_interior_graph(b)]
        assert context.level_mode is LevelMode.OPERATE

    @pytest.mark.parametrize("event", _BACKGROUND_EVENTS, ids=lambda e: e.event_type)
    def test_an_event_the_canvas_sends_on_its_own_claims_nothing(self, monkeypatch, event):
        a, _b, context, edit_state, manager, recorder = _residual_path(monkeypatch)
        a_graph = a._levels[DOCUMENT_LEVEL].container.editor.graph

        manager._handle_canvas_event(event)

        assert recorder.seen == [a_graph]
        assert edit_state.active_graph is a_graph
        assert context.level_mode is LevelMode.EDIT
        context.session.publish.assert_not_called()

    def test_a_canvas_of_a_level_not_on_screen_claims_nothing(self, monkeypatch):
        a, b, context, edit_state, _manager, _ = _residual_path(monkeypatch)
        hidden = b._levels[DOCUMENT_LEVEL].canvas_manager
        assert hidden is not None

        hidden._handle_canvas_event(SelectionChangedEvent(selectedNodes=[], selectedEdges=[]))

        assert edit_state.active_graph is a._levels[DOCUMENT_LEVEL].container.editor.graph
        assert context.level_mode is LevelMode.EDIT

    def test_a_gesture_on_the_canvas_already_holding_the_session_publishes_no_move(self, monkeypatch):
        from haywire.core.signals import ActiveGraphMoved

        _a, b, context, _edit_state, manager, _ = _residual_path(monkeypatch)
        b.on_focus(context)
        context.session.publish.reset_mock()

        manager._handle_canvas_event(SelectionChangedEvent(selectedNodes=[], selectedEdges=[]))

        assert ActiveGraphMoved not in _published(context)


def _drawable(monkeypatch, context: Any) -> None:
    """Let ``GraphEditor.draw`` run without a page: its element factories become mocks."""
    monkeypatch.setattr(graph_editor_module, "ui", MagicMock())
    monkeypatch.setattr(graph_editor_module, "hui", MagicMock())
    context.app = MagicMock()


class TestARedrawDropsOnlyItsOwnSelection:
    def test_a_background_editors_redraw_keeps_the_focused_editors_selection(self, monkeypatch):
        a, b, context, edit_state = _split_panes()
        _drawable(monkeypatch, context)
        a_node = edit_state.active_node
        context.session.publish.reset_mock()

        b.draw(context, MagicMock())

        assert edit_state.active_graph is a._levels[DOCUMENT_LEVEL].container.editor.graph
        assert edit_state.active_node is a_node
        assert edit_state.selected_nodes == {"n1"}
        assert SelectionMoved not in _published(context)

    def test_the_focused_editors_redraw_drops_its_selection(self, monkeypatch):
        a, _b, context, edit_state = _split_panes()
        _drawable(monkeypatch, context)
        context.session.publish.reset_mock()

        a.draw(context, MagicMock())

        _assert_selection_dropped(context, edit_state)

    def test_a_redraw_after_focusing_the_other_pane_drops_its_selection(self, monkeypatch):
        _a, b, context, edit_state = _split_panes()
        _drawable(monkeypatch, context)
        b.on_focus(context)
        edit_state.active_node = MagicMock(name="b_interior_node")
        edit_state.selected_nodes = {"b1"}
        context.session.publish.reset_mock()

        b.draw(context, MagicMock())

        _assert_selection_dropped(context, edit_state)


def test_a_lock_toggle_publishes_the_session_level_mode():
    """A lock toggle moves ``SessionContext.level_mode`` through the signal, once.

    The other lock tests run on fake contexts where ``level_mode`` is a plain
    attribute, so they check the value but never that panels are told.
    """
    from haywire.core.session.session import Session

    editor, fake, _ = _locked_editor(AccessTier.EDIT, open_locked=False)
    session = Session(app_state=MagicMock(), workspace_manager=MagicMock(), dispatcher=MagicMock())
    context = session.context
    context.principal = "someone"
    context.data = fake.data
    context.can_access = fake.can_access  # type: ignore[method-assign]
    context.can_edit = fake.can_edit  # type: ignore[method-assign]
    editor._claim_session_state(context)
    assert context.level_mode is LevelMode.EDIT

    received: list[Any] = []
    session.subscribe(cast(Any, SessionContext.level_mode), received.append)

    assert editor.set_level_locked(context, DOCUMENT_LEVEL, True) is True

    assert context.level_mode is LevelMode.OPERATE
    assert len(received) == 1
