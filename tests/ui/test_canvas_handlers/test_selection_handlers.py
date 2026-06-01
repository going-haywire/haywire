"""
Tests for SelectionHandlers — manages selected_nodes, selected_edges, and clipboard state.
"""

import json
import pytest
from unittest.mock import MagicMock, patch

from haywire.core.state import LibraryStateContainer, LibraryStateRegistry
from haywire.core.session.context import SessionContext
from haybale_graph_editor.editors.graph_canvas.handlers.selection import SelectionHandlers
from haywire.ui.components.graph.event_definitions import (
    SelectionChangedEvent,
    UserCopySelectedEvent,
    UserPasteClipboardEvent,
)
from haybale_graph_editor.editors.graph_canvas.event_handlers import build_event_handler_map

pytestmark = pytest.mark.unit


@pytest.fixture
def graph():
    g = MagicMock()
    # Default: get_node_wrapper returns a wrapper whose serialize() yields a
    # real dict so build_clipboard_payload produces a sensible payload.
    wrapper = MagicMock()
    wrapper.node.props.posX = 100.0
    wrapper.node.props.posY = 200.0
    wrapper.serialize.return_value = {
        "node_id": "n",
        "registry_key": "k",
        "position": [100.0, 200.0],
        "node_data": {},
    }
    g.get_node_wrapper.return_value = wrapper
    # Edges serialize to a dict with endpoints both inside the selection.
    edge_wrapper = MagicMock()
    edge_wrapper.edge.to_dict.return_value = {
        "edge_id": "e",
        "source_node_id": "n1",
        "sink_node_id": "n1",
    }
    g.get_edge_wrapper.return_value = edge_wrapper
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
    ctx.session = s
    return s, EditStateCls


@pytest.fixture
def session(session_with_edit):
    return session_with_edit[0]


@pytest.fixture
def edit_state_cls(session_with_edit):
    return session_with_edit[1]


@pytest.fixture(autouse=True)
def _stub_nicegui_io():
    """Copy/paste now touch the OS clipboard / notifications via NiceGUI.

    Outside a live client there is no slot stack, so ``ui.run_javascript`` and
    ``ui.notify`` would raise. Stub them so handler logic is tested in isolation.
    Tests that assert on these calls patch them again locally (the inner patch
    wins for the duration of its ``with`` block).
    """
    mod = "haybale_graph_editor.editors.graph_canvas.handlers.selection"
    with patch(f"{mod}.ui.run_javascript"), patch(f"{mod}.ui.notify"):
        yield


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
    assert session.context.data[edit_state_cls].clipboard is None


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
    ctx.session = session
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
    from haywire.core.session.signals import SelectionMoved

    published = [call.args[0] for call in session.publish.call_args_list]
    assert any(isinstance(s, SelectionMoved) for s in published)
    edit = ctx.data[EditStateCls]
    assert edit.selected_nodes == {"n1"}
    assert edit.selected_edges == {"e1"}


def test_selection_changed_no_callback_does_not_raise(handler):
    """No callback configured — must not raise."""
    handler.process_selection_change(SelectionChangedEvent(selectedNodes=[], selectedEdges=[]))


# ---------------------------------------------------------------------------
# UserCopySelected
# ---------------------------------------------------------------------------


def test_copy_stores_clipboard_with_node_ids(handler, session, edit_state_cls):
    handler.process_copy_selection(UserCopySelectedEvent(selectedNodes=["n1", "n2"], selectedEdges=[]))
    clipboard = session.context.data[edit_state_cls].clipboard
    assert clipboard is not None
    assert "n1" in clipboard.payload["nodes"]
    assert "n2" in clipboard.payload["nodes"]


def test_copy_stores_edge_ids(handler, session, edit_state_cls):
    handler.process_copy_selection(UserCopySelectedEvent(selectedNodes=["n1"], selectedEdges=["e1"]))
    assert "e1" in session.context.data[edit_state_cls].clipboard.payload["edges"]


def test_copy_records_session_id(handler, session, edit_state_cls):
    handler.process_copy_selection(UserCopySelectedEvent(selectedNodes=["n1"], selectedEdges=[]))
    clipboard = session.context.data[edit_state_cls].clipboard
    assert clipboard.payload["source"]["session_id"] == "test-session"


def test_copy_overwrites_previous_clipboard(handler, session, edit_state_cls):
    handler.process_copy_selection(UserCopySelectedEvent(selectedNodes=["n1"], selectedEdges=[]))
    handler.process_copy_selection(UserCopySelectedEvent(selectedNodes=["n2"], selectedEdges=[]))
    clipboard = session.context.data[edit_state_cls].clipboard
    assert "n2" in clipboard.payload["nodes"]
    assert "n1" not in clipboard.payload["nodes"]


# ---------------------------------------------------------------------------
# Handler registration
# ---------------------------------------------------------------------------


def test_all_selection_events_are_registered(handler):
    result = build_event_handler_map([handler])
    assert "selectionChanged" in result
    assert "userCopySelected" in result
    assert "userPasteClipboard" in result


def test_paste_event_carries_clipboard_text():
    from haywire.ui.components.graph.event_definitions import UserPasteClipboardEvent

    e = UserPasteClipboardEvent(canvasX=1.0, canvasY=2.0, clipboardText='{"x":1}')
    assert e.clipboardText == '{"x":1}'

    # clipboardText must survive the Python→Vue wire serialization, nested under "data"
    assert e.to_dict()["data"]["clipboardText"] == '{"x":1}'

    # default stays empty for backward compat
    e2 = UserPasteClipboardEvent(canvasX=0.0, canvasY=0.0)
    assert e2.clipboardText == ""


# ---------------------------------------------------------------------------
# Copy: real serialized payload + OS clipboard write
# ---------------------------------------------------------------------------


def test_copy_stores_serialized_payload_in_mirror(graph, session, edit_state_cls):
    graph.get_node_wrapper.return_value.serialize.return_value = {
        "node_id": "n1",
        "registry_key": "k",
        "position": [10.0, 20.0],
        "node_data": {},
    }
    h = SelectionHandlers(graph=graph, editor=MagicMock(), session_id="sess", session=session)
    with patch("haybale_graph_editor.editors.graph_canvas.handlers.selection.ui.run_javascript") as rj:
        h.process_copy_selection(UserCopySelectedEvent(selectedNodes=["n1"], selectedEdges=[]))
    clip = session.context.data[edit_state_cls].clipboard
    assert clip is not None
    assert clip.payload["haywire_clipboard"] is True
    assert "n1" in clip.payload["nodes"]
    assert rj.called
    assert "navigator.clipboard.writeText" in rj.call_args[0][0]


# ---------------------------------------------------------------------------
# Paste: source arbitration (OS clipboard text vs mirror)
# ---------------------------------------------------------------------------


def test_paste_uses_event_text_when_valid(graph, session, edit_state_cls):
    editor = MagicMock()
    editor.paste_clipboard.return_value = ([], [])  # (new_node_ids, new_edge_ids)
    h = SelectionHandlers(graph=graph, editor=editor, session_id="sess", session=session)
    payload = {
        "haywire_clipboard": True,
        "format_version": 1,
        "source": {"session_id": "x", "timestamp": 99.0},
        "bounding_box": {"min_x": 0, "min_y": 0, "max_x": 0, "max_y": 0},
        "nodes": {},
        "edges": {},
    }
    h.process_paste_clipboard(
        UserPasteClipboardEvent(canvasX=5.0, canvasY=6.0, clipboardText=json.dumps(payload))
    )
    editor.paste_clipboard.assert_called_once()
    args = editor.paste_clipboard.call_args[0]
    assert args[0]["source"]["timestamp"] == 99.0
    assert (args[1], args[2]) == (5.0, 6.0)


def test_paste_falls_back_to_mirror_when_text_empty(graph, session, edit_state_cls):
    from haywire.core.undo.actions.graph_actions import ClipboardData

    editor = MagicMock()
    editor.paste_clipboard.return_value = ([], [])  # (new_node_ids, new_edge_ids)
    h = SelectionHandlers(graph=graph, editor=editor, session_id="sess", session=session)
    mirror_payload = {
        "haywire_clipboard": True,
        "format_version": 1,
        "source": {"session_id": "x", "timestamp": 1.0},
        "bounding_box": {"min_x": 0, "min_y": 0, "max_x": 0, "max_y": 0},
        "nodes": {},
        "edges": {},
    }
    session.context.data[edit_state_cls].clipboard = ClipboardData(payload=mirror_payload, timestamp=1.0)
    h.process_paste_clipboard(UserPasteClipboardEvent(canvasX=0.0, canvasY=0.0, clipboardText=""))
    editor.paste_clipboard.assert_called_once_with(mirror_payload, 0.0, 0.0)


def test_paste_notifies_when_nothing_to_paste(graph, session, edit_state_cls):
    editor = MagicMock()
    h = SelectionHandlers(graph=graph, editor=editor, session_id="sess", session=session)
    with patch("haybale_graph_editor.editors.graph_canvas.handlers.selection.ui.notify") as notify:
        h.process_paste_clipboard(UserPasteClipboardEvent(canvasX=0.0, canvasY=0.0, clipboardText=""))
    editor.paste_clipboard.assert_not_called()
    notify.assert_called_once()


def test_paste_auto_selects_pasted_elements(graph, session, edit_state_cls):
    """After a successful paste, the new nodes/edges become the selection and
    are pushed to the canvas via visual_layer.sync_selections."""
    editor = MagicMock()
    editor.paste_clipboard.return_value = (["new_n1", "new_n2"], ["new_e1"])
    visual_layer = MagicMock()
    h = SelectionHandlers(
        graph=graph,
        editor=editor,
        session_id="sess",
        session=session,
        visual_layer=visual_layer,
    )
    payload = {
        "haywire_clipboard": True,
        "format_version": 1,
        "source": {"session_id": "x", "timestamp": 99.0},
        "bounding_box": {"min_x": 0, "min_y": 0, "max_x": 0, "max_y": 0},
        "nodes": {},
        "edges": {},
    }
    h.process_paste_clipboard(
        UserPasteClipboardEvent(canvasX=5.0, canvasY=6.0, clipboardText=json.dumps(payload))
    )

    edit = session.context.data[edit_state_cls]
    assert edit.selected_nodes == {"new_n1", "new_n2"}
    assert edit.selected_edges == {"new_e1"}
    visual_layer.sync_selections.assert_called_once_with(["new_n1", "new_n2"], ["new_e1"])


def test_paste_ignores_text_without_source_timestamp(graph, session, edit_state_cls):
    editor = MagicMock()
    h = SelectionHandlers(graph=graph, editor=editor, session_id="sess", session=session)
    # passes flag+version but is_haywire_payload now rejects it (no source.timestamp)
    bad = json.dumps({"haywire_clipboard": True, "format_version": 1, "nodes": {}, "edges": {}})
    # no mirror set -> nothing valid to paste
    with patch("haybale_graph_editor.editors.graph_canvas.handlers.selection.ui.notify") as notify:
        h.process_paste_clipboard(UserPasteClipboardEvent(canvasX=0.0, canvasY=0.0, clipboardText=bad))
    editor.paste_clipboard.assert_not_called()
    notify.assert_called_once()  # "Nothing to paste"
