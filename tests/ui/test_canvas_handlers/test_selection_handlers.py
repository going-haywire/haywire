"""
Tests for SelectionHandlers — manages selected_nodes, selected_edges, and clipboard state.
"""

import pytest
from unittest.mock import MagicMock

from haywire.core.state import LibraryStateContainer, LibraryStateRegistry
from haywire.core.session.context import SessionContext
from haybale_studio.editors.graph_canvas.handlers.selection import SelectionHandlers
from haybale_studio.editors.graph_canvas.event_definitions import (
    SelectionChangedEvent,
    UserCopySelectedEvent,
)
from haybale_studio.editors.graph_canvas.event_handlers import build_event_handler_map

pytestmark = pytest.mark.unit


@pytest.fixture
def graph():
    g = MagicMock()
    # Default: get_node_wrapper returns a wrapper with node.props
    wrapper = MagicMock()
    wrapper.node.props.posX = 100.0
    wrapper.node.props.posY = 200.0
    g.get_node_wrapper.return_value = wrapper
    return g


@pytest.fixture
def session_with_edit(register_edit_state):
    """A real SessionContext + container with EditState registered.

    Returns ``(session, EditState)`` so tests can read/write
    ``session.context.data[EditState]`` against the container's class
    reference (survives library hot-reloads).
    """
    container = LibraryStateContainer(LibraryStateRegistry())
    sid = "test-session"
    EditStateCls = register_edit_state(container, sid)
    app = MagicMock()
    app.library_state_container = container
    ctx = SessionContext(session_id=sid, app=app)
    s = MagicMock()
    s.context = ctx
    return s, EditStateCls


@pytest.fixture
def session(session_with_edit):
    return session_with_edit[0]


@pytest.fixture
def edit_state_cls(session_with_edit):
    return session_with_edit[1]


@pytest.fixture
def handler(graph, session):
    return SelectionHandlers(
        graph=graph,
        editor=MagicMock(),
        session_id="test-session",
        session=session,
    )


# ---------------------------------------------------------------------------
# Initial state
# ---------------------------------------------------------------------------


def test_initial_selection_is_empty(handler):
    assert handler.selected_nodes == set()
    assert handler.selected_edges == set()


def test_initial_clipboard_is_none(handler, session, edit_state_cls):
    assert session.context.data[edit_state_cls].clipboard.value is None


# ---------------------------------------------------------------------------
# SelectionChanged
# ---------------------------------------------------------------------------


def test_selection_changed_updates_nodes(handler):
    handler.process_selection_change(SelectionChangedEvent(selectedNodes=["n1", "n2"], selectedEdges=[]))
    assert handler.selected_nodes == {"n1", "n2"}
    assert handler.selected_edges == set()


def test_selection_changed_updates_edges(handler):
    handler.process_selection_change(SelectionChangedEvent(selectedNodes=[], selectedEdges=["e1", "e2"]))
    assert handler.selected_edges == {"e1", "e2"}


def test_selection_changed_replaces_previous(handler):
    handler.process_selection_change(SelectionChangedEvent(selectedNodes=["n1"], selectedEdges=[]))
    handler.process_selection_change(SelectionChangedEvent(selectedNodes=["n2"], selectedEdges=["e1"]))
    assert handler.selected_nodes == {"n2"}
    assert handler.selected_edges == {"e1"}


def test_selection_changed_notifies_session(register_edit_state):
    container = LibraryStateContainer(LibraryStateRegistry())
    sid = "s"
    EditStateCls = register_edit_state(container, sid)
    app = MagicMock()
    app.library_state_container = container
    ctx = SessionContext(session_id=sid, app=app)
    session = MagicMock()
    session.context = ctx
    graph = MagicMock()
    graph.get_node_wrapper.return_value = MagicMock()
    graph.get_edge_wrapper.return_value = MagicMock()
    handler = SelectionHandlers(
        graph=graph,
        editor=MagicMock(),
        session_id=sid,
        session=session,
    )
    handler.process_selection_change(SelectionChangedEvent(selectedNodes=["n1"], selectedEdges=["e1"]))
    session.signal.assert_called_once()
    from haywire.core.session.events import SelectionMoved

    assert isinstance(session.signal.call_args.args[0], SelectionMoved)
    edit = ctx.data[EditStateCls]
    assert edit.selected_nodes.value == {"n1"}
    assert edit.selected_edges.value == {"e1"}


def test_selection_changed_no_callback_does_not_raise(handler):
    """No callback configured — must not raise."""
    handler.process_selection_change(SelectionChangedEvent(selectedNodes=[], selectedEdges=[]))


# ---------------------------------------------------------------------------
# UserCopySelected
# ---------------------------------------------------------------------------


def test_copy_stores_clipboard_with_node_ids(handler, session, edit_state_cls):
    handler.process_copy_selection(UserCopySelectedEvent(selectedNodes=["n1", "n2"], selectedEdges=[]))
    clipboard = session.context.data[edit_state_cls].clipboard.value
    assert clipboard is not None
    assert "n1" in clipboard.nodes
    assert "n2" in clipboard.nodes


def test_copy_stores_edge_ids(handler, session, edit_state_cls):
    handler.process_copy_selection(UserCopySelectedEvent(selectedNodes=["n1"], selectedEdges=["e1"]))
    assert "e1" in session.context.data[edit_state_cls].clipboard.value.edges


def test_copy_records_session_id(handler, session, edit_state_cls):
    handler.process_copy_selection(UserCopySelectedEvent(selectedNodes=["n1"], selectedEdges=[]))
    assert session.context.data[edit_state_cls].clipboard.value.source_session_id == "test-session"


def test_copy_overwrites_previous_clipboard(handler, session, edit_state_cls):
    handler.process_copy_selection(UserCopySelectedEvent(selectedNodes=["n1"], selectedEdges=[]))
    handler.process_copy_selection(UserCopySelectedEvent(selectedNodes=["n2"], selectedEdges=[]))
    clipboard = session.context.data[edit_state_cls].clipboard.value
    assert "n2" in clipboard.nodes
    assert "n1" not in clipboard.nodes


# ---------------------------------------------------------------------------
# Handler registration
# ---------------------------------------------------------------------------


def test_all_selection_events_are_registered(handler):
    result = build_event_handler_map([handler])
    assert "selectionChanged" in result
    assert "userCopySelected" in result
    assert "userPasteClipboard" in result
