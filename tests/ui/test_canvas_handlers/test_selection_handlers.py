"""
Tests for SelectionHandlers — manages selected_nodes, selected_edges, and clipboard state.
"""

import json
from typing import Any

import pytest
from unittest.mock import MagicMock, patch

from haywire.core.graph.clipboard import CLIPBOARD_FORMAT_VERSION
from haywire.core.node.layout import PATCH
from haywire.core.state import LibraryStateContainer, LibraryStateRegistry
from haywire.core.session.context import SessionContext
from haywire.core.signals import SelectionMoved
from haybale_graph_editor.editors.graph_canvas.handlers import selection as selection_module
from haybale_graph_editor.editors.graph_canvas.handlers.selection import SelectionHandlers
from haywire.ui.components.graph.event_definitions import (
    SelectionChangedEvent,
    UserCopySelectedEvent,
    UserPasteClipboardEvent,
    UserRemoveEvent,
)
from haybale_graph_editor.editors.graph_canvas.event_handlers import build_event_handler_map

pytestmark = pytest.mark.unit


@pytest.fixture
def graph():
    g = MagicMock()
    # Default: get_node_wrapper returns a wrapper whose serialize() yields a
    # real dict so build_clipboard_payload produces a sensible payload.
    wrapper = MagicMock()
    # An ordinary node: build_clipboard_payload filters Subgraph boundary nodes
    # out, and a bare MagicMock would report itself as one.
    wrapper.node.behavior.is_boundary_node = False
    wrapper.node.props.posX = 100.0
    wrapper.node.props.posY = 200.0
    wrapper.serialize.return_value = {
        "node_id": "n",
        "registry_key": "k",
        "node_data": {"props": {"values": {"posX": 100.0, "posY": 200.0}}},
    }
    g.get_node_wrapper.return_value = wrapper
    # Edges serialize to a dict with endpoints both inside the selection.
    edge_wrapper = MagicMock()
    edge_wrapper.serialize.return_value = {
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
    with patch.object(selection_module.ui, "run_javascript"), patch.object(selection_module.ui, "notify"):
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
    node_wrapper = MagicMock()
    node_wrapper.node.behavior.is_boundary_node = False
    graph.get_node_wrapper.return_value = node_wrapper
    graph.get_edge_wrapper.return_value = MagicMock()
    handler = SelectionHandlers(
        graph=graph,
        editor=MagicMock(),
        session_id=sid,
        session=session,
    )
    handler.process_selection_change(SelectionChangedEvent(selectedNodes=["n1"], selectedEdges=["e1"]))
    from haywire.core.signals import SelectionMoved

    published = [call.args[0] for call in session.publish.call_args_list]
    assert any(isinstance(s, SelectionMoved) for s in published)
    edit = ctx.data[EditStateCls]
    assert edit.selected_nodes == {"n1"}
    assert edit.selected_edges == {"e1"}


def test_selection_changed_no_callback_does_not_raise(handler):
    """No callback configured — must not raise."""
    handler.process_selection_change(SelectionChangedEvent(selectedNodes=[], selectedEdges=[]))


def test_active_node_follows_event_active_id(handler, session, edit_state_cls):
    """active_node is the event's activeNodeId, not an arbitrary set member."""
    handler.process_selection_change(
        SelectionChangedEvent(
            selectedNodes=["n1", "n2", "n3"],
            selectedEdges=[],
            activeNodeId="n2",
            activeEdgeId="",
        )
    )
    edit = session.context.data[edit_state_cls]
    # handler.graph.get_node_wrapper is a MagicMock; assert it was asked for n2.
    handler.graph.get_node_wrapper.assert_called_with("n2")
    assert edit.active_edge is None


def test_active_edge_clears_active_node_single_active(handler, session, edit_state_cls):
    """An active edge means no active node (single active element across kinds)."""
    handler.process_selection_change(
        SelectionChangedEvent(
            selectedNodes=["n1"],
            selectedEdges=["e1"],
            activeNodeId="",
            activeEdgeId="e1",
        )
    )
    edit = session.context.data[edit_state_cls]
    assert edit.active_node is None
    handler.graph.get_edge_wrapper.assert_called_with("e1")


def test_no_active_id_means_none(handler, session, edit_state_cls):
    """Bulk selection (drag-box) carries no active id -> active_node/edge are None."""
    handler.process_selection_change(
        SelectionChangedEvent(
            selectedNodes=["n1", "n2"],
            selectedEdges=[],
            activeNodeId="",
            activeEdgeId="",
        )
    )
    edit = session.context.data[edit_state_cls]
    assert edit.active_node is None
    assert edit.active_edge is None


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


def test_selection_changed_event_carries_active_ids():
    from haywire.ui.components.graph.event_definitions import SelectionChangedEvent

    e = SelectionChangedEvent(
        selectedNodes=["n1", "n2"],
        selectedEdges=[],
        activeNodeId="n2",
        activeEdgeId="",
    )
    assert e.activeNodeId == "n2"
    assert e.activeEdgeId == ""
    # survives Python wire serialization, nested under "data"
    d = e.to_dict()["data"]
    assert d["activeNodeId"] == "n2"
    assert d["activeEdgeId"] == ""

    # defaults stay empty for backward compat (existing call sites omit them)
    e2 = SelectionChangedEvent(selectedNodes=[], selectedEdges=[])
    assert e2.activeNodeId == ""
    assert e2.activeEdgeId == ""


def test_sync_selections_event_carries_active():
    from haywire.ui.components.graph.event_definitions import SyncSelectionsEvent

    e = SyncSelectionsEvent(nodes=["n1"], edges=[], active={"kind": "node", "id": "n1"})
    assert e.active == {"kind": "node", "id": "n1"}
    assert e.to_dict()["data"]["active"] == {"kind": "node", "id": "n1"}

    # default is the "no active" sentinel; existing emit sites omit it
    e2 = SyncSelectionsEvent(nodes=[], edges=[])
    assert e2.active == {"kind": "", "id": ""}


# ---------------------------------------------------------------------------
# Copy: real serialized payload + OS clipboard write
# ---------------------------------------------------------------------------


def test_copy_stores_serialized_payload_in_mirror(graph, session, edit_state_cls):
    graph.get_node_wrapper.return_value.serialize.return_value = {
        "node_id": "n1",
        "registry_key": "k",
        "node_data": {"props": {"values": {"posX": 10.0, "posY": 20.0}}},
    }
    h = SelectionHandlers(graph=graph, editor=MagicMock(), session_id="sess", session=session)
    with patch.object(selection_module.ui, "run_javascript") as rj:
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
        "format_version": CLIPBOARD_FORMAT_VERSION,
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
        "format_version": CLIPBOARD_FORMAT_VERSION,
        "source": {"session_id": "x", "timestamp": 1.0},
        "bounding_box": {"min_x": 0, "min_y": 0, "max_x": 0, "max_y": 0},
        "nodes": {},
        "edges": {},
    }
    session.context.data[edit_state_cls].clipboard = ClipboardData(payload=mirror_payload, timestamp=1.0)
    h.process_paste_clipboard(UserPasteClipboardEvent(canvasX=0.0, canvasY=0.0, clipboardText=""))
    editor.paste_clipboard.assert_called_once_with(mirror_payload, 0.0, 0.0, PATCH)


def test_paste_notifies_when_nothing_to_paste(graph, session, edit_state_cls):
    editor = MagicMock()
    h = SelectionHandlers(graph=graph, editor=editor, session_id="sess", session=session)
    with patch.object(selection_module.ui, "notify") as notify:
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
        "format_version": CLIPBOARD_FORMAT_VERSION,
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
    visual_layer.sync_selections.assert_called_once_with(
        ["new_n1", "new_n2"], ["new_e1"], active={"kind": "", "id": ""}
    )


def test_paste_clears_active(graph, session, edit_state_cls):
    """A pasted subgraph is selected but has no active primary."""
    editor = MagicMock()
    editor.paste_clipboard.return_value = (["new_n1", "new_n2"], [])
    visual_layer = MagicMock()
    h = SelectionHandlers(
        graph=graph,
        editor=editor,
        session_id="sess",
        session=session,
        visual_layer=visual_layer,
    )
    # seed a stale active so we can prove it gets cleared
    edit = session.context.data[edit_state_cls]
    edit.active_node = MagicMock()

    payload = {
        "haywire_clipboard": True,
        "format_version": CLIPBOARD_FORMAT_VERSION,
        "source": {"session_id": "x", "timestamp": 99.0},
        "bounding_box": {"min_x": 0, "min_y": 0, "max_x": 0, "max_y": 0},
        "nodes": {},
        "edges": {},
    }
    h.process_paste_clipboard(
        UserPasteClipboardEvent(canvasX=5.0, canvasY=6.0, clipboardText=json.dumps(payload))
    )
    assert edit.active_node is None
    assert edit.active_edge is None
    # sync_selections is called with the new selection; the no-active sentinel
    # is passed as the `active` kwarg.
    _, kwargs = visual_layer.sync_selections.call_args
    assert kwargs.get("active") == {"kind": "", "id": ""}


def test_paste_publishes_selection_moved(graph, session, edit_state_cls):
    """Property panels follow a pasted selection: the paste publishes SelectionMoved."""
    editor = MagicMock()
    editor.paste_clipboard.return_value = (["new_n1"], [])
    h = SelectionHandlers(graph=graph, editor=editor, session_id="sess", session=session)
    payload = {
        "haywire_clipboard": True,
        "format_version": CLIPBOARD_FORMAT_VERSION,
        "source": {"session_id": "x", "timestamp": 99.0},
        "bounding_box": {"min_x": 0, "min_y": 0, "max_x": 0, "max_y": 0},
        "nodes": {},
        "edges": {},
    }
    session.publish.reset_mock()

    h.process_paste_clipboard(
        UserPasteClipboardEvent(canvasX=5.0, canvasY=6.0, clipboardText=json.dumps(payload))
    )

    published = [call.args[0] for call in session.publish.call_args_list]
    assert any(isinstance(signal, SelectionMoved) for signal in published)


def test_paste_ignores_text_without_source_timestamp(graph, session, edit_state_cls):
    editor = MagicMock()
    h = SelectionHandlers(graph=graph, editor=editor, session_id="sess", session=session)
    # passes flag+version but is_haywire_payload now rejects it (no source.timestamp)
    bad = json.dumps(
        {
            "haywire_clipboard": True,
            "format_version": CLIPBOARD_FORMAT_VERSION,
            "nodes": {},
            "edges": {},
        }
    )
    # no mirror set -> nothing valid to paste
    with patch.object(selection_module.ui, "notify") as notify:
        h.process_paste_clipboard(UserPasteClipboardEvent(canvasX=0.0, canvasY=0.0, clipboardText=bad))
    editor.paste_clipboard.assert_not_called()
    notify.assert_called_once()  # "Nothing to paste"


def test_copy_uses_clipboard_script(handler):
    """The OS clipboard write carries the insecure-context fallback."""
    with patch.object(selection_module.ui, "run_javascript") as run_js:
        handler.process_copy_selection(UserCopySelectedEvent(selectedNodes=["n1"], selectedEdges=[]))
    run_js.assert_called_once()
    assert "execCommand('copy')" in run_js.call_args.args[0]


# ---------------------------------------------------------------------------
# Select all
# ---------------------------------------------------------------------------


def _select_all_handler(graph, session, locked=()):
    """A handler over nodes a, b, c with a mock visual layer and the given locked ids."""
    graph.node_wrappers = {"a": MagicMock(), "b": MagicMock(), "c": MagicMock()}
    visual_layer = MagicMock()
    h = SelectionHandlers(
        graph=graph,
        editor=MagicMock(),
        session_id="sess",
        session=session,
        visual_layer=visual_layer,
    )
    return h, visual_layer, lambda node_id: node_id in locked


def test_select_all_selects_every_unlocked_node(graph, session, edit_state_cls):
    h, visual_layer, is_locked = _select_all_handler(graph, session)
    edit = session.context.data[edit_state_cls]
    edit.active_node = MagicMock()
    session.context.active_component = "graph-canvas"
    session.publish.reset_mock()

    h.select_all_toggle(is_locked)

    assert h.selected_nodes == {"a", "b", "c"}
    assert h.selected_edges == set()
    assert edit.selected_nodes == {"a", "b", "c"}
    assert edit.selected_edges == set()
    assert edit.active_node is None
    assert edit.active_edge is None
    nodes, edges = visual_layer.sync_selections.call_args.args
    assert set(nodes) == {"a", "b", "c"}
    assert set(edges) == set()
    published = [call.args[0] for call in session.publish.call_args_list]
    assert any(isinstance(signal, SelectionMoved) for signal in published)
    assert session.context.active_component is None


def test_select_all_twice_clears(graph, session, edit_state_cls):
    h, visual_layer, is_locked = _select_all_handler(graph, session)

    h.select_all_toggle(is_locked)
    h.select_all_toggle(is_locked)

    assert h.selected_nodes == set()
    assert h.selected_edges == set()
    assert session.context.data[edit_state_cls].selected_nodes == set()
    nodes, edges = visual_layer.sync_selections.call_args.args
    assert set(nodes) == set()
    assert set(edges) == set()


def test_select_all_from_partial_selects_all(graph, session, edit_state_cls):
    h, _, is_locked = _select_all_handler(graph, session)
    h.selected_nodes = {"a"}
    h.selected_edges = {"e1"}

    h.select_all_toggle(is_locked)

    assert h.selected_nodes == {"a", "b", "c"}
    assert h.selected_edges == set()


def test_select_all_skips_locked_nodes(graph, session, edit_state_cls):
    h, _, is_locked = _select_all_handler(graph, session, locked=("c",))

    h.select_all_toggle(is_locked)
    assert h.selected_nodes == {"a", "b"}

    h.select_all_toggle(is_locked)
    assert h.selected_nodes == set()


# ---------------------------------------------------------------------------
# Keyboard copy/delete act on this canvas's graph only
# ---------------------------------------------------------------------------


def _keyboard_manager(session, node_ids=("a", "b"), edge_ids=("e1",)):
    """A GraphCanvasManager over a graph holding ``node_ids``/``edge_ids``, with a mock dispatch."""
    from haybale_graph_editor.editors.graph_canvas.graph_canvas_manager import GraphCanvasManager

    graph = MagicMock()
    graph.node_wrappers = {node_id: MagicMock() for node_id in node_ids}
    graph.edge_wrappers = {edge_id: MagicMock() for edge_id in edge_ids}
    graph.get_node_wrapper.side_effect = graph.node_wrappers.get
    graph.get_edge_wrapper.side_effect = graph.edge_wrappers.get
    manager: Any = object.__new__(GraphCanvasManager)
    manager.graph = graph
    manager._session = session
    dispatch = MagicMock()
    manager._handle_canvas_event = dispatch
    return manager, dispatch


def test_keyboard_copy_ignores_a_selection_from_another_graph(session, edit_state_cls):
    edit = session.context.data[edit_state_cls]
    edit.selected_nodes = {"x", "y"}
    edit.selected_edges = {"ex"}
    clipboard = MagicMock()
    edit.clipboard = clipboard
    manager, dispatch = _keyboard_manager(session)

    manager.copy_selection()

    dispatch.assert_not_called()
    assert edit.clipboard is clipboard


def test_keyboard_delete_ignores_a_selection_from_another_graph(session, edit_state_cls):
    edit = session.context.data[edit_state_cls]
    edit.selected_nodes = {"x", "y"}
    edit.selected_edges = {"ex"}
    manager, dispatch = _keyboard_manager(session)

    manager.delete_selection()

    dispatch.assert_not_called()


def test_keyboard_copy_and_delete_keep_only_this_graphs_ids(session, edit_state_cls):
    edit = session.context.data[edit_state_cls]
    edit.selected_nodes = {"a", "x"}
    edit.selected_edges = {"e1", "ex"}
    manager, dispatch = _keyboard_manager(session)

    manager.copy_selection()
    manager.delete_selection()

    copy_event, remove_event = (call.args[0] for call in dispatch.call_args_list)
    assert isinstance(copy_event, UserCopySelectedEvent)
    assert copy_event.selectedNodes == ["a"]
    assert copy_event.selectedEdges == ["e1"]
    assert isinstance(remove_event, UserRemoveEvent)
    assert remove_event.nodes == ["a"]
    assert remove_event.edges == ["e1"]


def test_keyboard_delete_of_only_edges_still_dispatches(session, edit_state_cls):
    edit = session.context.data[edit_state_cls]
    edit.selected_nodes = {"x"}
    edit.selected_edges = {"e1"}
    manager, dispatch = _keyboard_manager(session)

    manager.copy_selection()
    manager.delete_selection()

    (remove_event,) = (call.args[0] for call in dispatch.call_args_list)
    assert isinstance(remove_event, UserRemoveEvent)
    assert remove_event.nodes == []
    assert remove_event.edges == ["e1"]


# ---------------------------------------------------------------------------
# Keyboard cut and duplicate
# ---------------------------------------------------------------------------


def _duplicate_handler(graph, session, pasted=(["n2"], [])):
    """A handler whose editor pastes ``pasted`` (new node ids, new edge ids), with a mock visual layer."""
    editor = MagicMock()
    editor.paste_clipboard.return_value = pasted
    visual_layer = MagicMock()
    h = SelectionHandlers(
        graph=graph,
        editor=editor,
        session_id="sess",
        session=session,
        visual_layer=visual_layer,
    )
    return h, editor, visual_layer


def test_duplicate_offsets_and_selects_copy(graph, session, edit_state_cls):
    h, editor, visual_layer = _duplicate_handler(graph, session)

    h.duplicate_selection(["n1"], [])

    payload, x, y, channel = editor.paste_clipboard.call_args.args
    assert channel is PATCH
    bbox = payload["bounding_box"]
    assert (x, y) == (
        bbox["min_x"] + selection_module.DUPLICATE_OFFSET,
        bbox["min_y"] + selection_module.DUPLICATE_OFFSET,
    )
    assert (x, y) == (140.0, 240.0)
    assert h.selected_nodes == {"n2"}
    assert session.context.data[edit_state_cls].selected_nodes == {"n2"}
    visual_layer.sync_selections.assert_called_once_with(["n2"], [], active={"kind": "node", "id": "n2"})


def test_duplicate_publishes_selection_moved(graph, session, edit_state_cls):
    """Property panels follow the duplicated selection: duplicate publishes SelectionMoved."""
    h, _, _ = _duplicate_handler(graph, session)
    session.publish.reset_mock()

    h.duplicate_selection(["n1"], [])

    published = [call.args[0] for call in session.publish.call_args_list]
    assert any(isinstance(signal, SelectionMoved) for signal in published)


def test_duplicate_without_session_selects_copy(graph):
    editor = MagicMock()
    editor.paste_clipboard.return_value = (["n2"], [])
    h = SelectionHandlers(graph=graph, editor=editor, session_id="sess", session=None)

    h.duplicate_selection(["n1"], [])

    assert h.selected_nodes == {"n2"}


def test_duplicate_leaves_clipboard_untouched(graph, session, edit_state_cls):
    edit = session.context.data[edit_state_cls]
    clipboard = MagicMock()
    edit.clipboard = clipboard
    h, editor, _ = _duplicate_handler(graph, session)

    with patch.object(selection_module.ui, "run_javascript") as run_js:
        h.duplicate_selection(["n1"], [])

    editor.paste_clipboard.assert_called_once()
    assert edit.clipboard is clipboard
    run_js.assert_not_called()


def test_duplicate_nothing_selected_noop(graph, session, edit_state_cls):
    h, editor, visual_layer = _duplicate_handler(graph, session)

    h.duplicate_selection([], ["e1"])

    editor.paste_clipboard.assert_not_called()
    visual_layer.sync_selections.assert_not_called()
    session.publish.assert_not_called()


def test_keyboard_duplicate_keeps_only_this_graphs_ids(session, edit_state_cls):
    edit = session.context.data[edit_state_cls]
    edit.selected_nodes = {"a", "x"}
    edit.selected_edges = {"e1", "ex"}
    manager, _ = _keyboard_manager(session)
    manager.selection = MagicMock()

    manager.duplicate_selection()

    manager.selection.duplicate_selection.assert_called_once_with(["a"], ["e1"])


def test_keyboard_duplicate_ignores_a_selection_from_another_graph(session, edit_state_cls):
    edit = session.context.data[edit_state_cls]
    edit.selected_nodes = {"x"}
    edit.selected_edges = {"e1"}
    manager, _ = _keyboard_manager(session)
    manager.selection = MagicMock()

    manager.duplicate_selection()

    manager.selection.duplicate_selection.assert_not_called()


def test_cut_copies_then_deletes(session, edit_state_cls):
    edit = session.context.data[edit_state_cls]
    edit.selected_nodes = {"a", "x"}
    edit.selected_edges = {"e1"}
    manager, dispatch = _keyboard_manager(session)

    manager.cut_selection()

    copy_event, remove_event = (call.args[0] for call in dispatch.call_args_list)
    assert isinstance(copy_event, UserCopySelectedEvent)
    assert isinstance(remove_event, UserRemoveEvent)
    assert copy_event.selectedNodes == remove_event.nodes == ["a"]
    assert copy_event.selectedEdges == remove_event.edges == ["e1"]


@pytest.mark.integration
def test_cut_is_one_undo_step(graph_with_library_system, library_system, session, edit_state_cls):
    from haybale_testing.nodes.testbed.math_op_node import TestAddFloatNode
    from haybale_graph_editor.editors.graph_canvas.graph_canvas_manager import GraphCanvasManager
    from haybale_graph_editor.editors.graph_canvas.handlers import visual_layer as visual_layer_module
    from haybale_graph_editor.editors.graph_canvas.handlers.visual_layer import VisualLayerHandlers
    from haywire.core.graph.editor import Editor
    from haywire.core.undo.config import UndoConfig
    from haywire.core.undo.history_manager import HistoryManager
    from tests.conftest import make_node

    graph = graph_with_library_system
    key = TestAddFloatNode.class_identity.registry_key
    kept = make_node(graph, key, position=(100, 100))
    cut = make_node(graph, key, position=(300, 100))
    assert isinstance(kept.node, TestAddFloatNode)
    assert isinstance(cut.node, TestAddFloatNode)
    history = HistoryManager(UndoConfig())
    editor = Editor(graph, library_system.get_node_factory(), history_manager=history)

    selection = SelectionHandlers(graph=graph, editor=editor, session_id="sess", session=session)
    visual_layer: Any = VisualLayerHandlers.__new__(VisualLayerHandlers)
    visual_layer.graph = graph
    visual_layer.editor = editor
    routes = {
        UserCopySelectedEvent.event_type: selection.process_copy_selection,
        UserRemoveEvent.event_type: visual_layer.process_element_removal,
    }
    manager: Any = object.__new__(GraphCanvasManager)
    manager.graph = graph
    manager._session = session
    manager._handle_canvas_event = lambda event: routes[event.event_type](event)
    edit = session.context.data[edit_state_cls]
    edit.selected_nodes = {cut.node_id}
    edit.selected_edges = set()
    before = history.get_history_stats()["action_count"]

    with patch.object(visual_layer_module.ui, "notify"):
        manager.cut_selection()

    assert history.get_history_stats()["action_count"] == before + 1
    assert set(graph.node_wrappers) == {kept.node_id}
    assert cut.node_id in edit.clipboard.payload["nodes"]
    assert editor.undo()
    assert set(graph.node_wrappers) == {kept.node_id, cut.node_id}


# ---------------------------------------------------------------------------
# prune_node — a node that left the canvas leaves the selection
# ---------------------------------------------------------------------------


def test_prune_node_drops_it_from_both_selections_and_publishes(handler, session, edit_state_cls):
    wrapper = MagicMock()
    wrapper.node_id = "n2"
    handler.graph.get_node_wrapper.return_value = wrapper
    handler.process_selection_change(
        SelectionChangedEvent(selectedNodes=["n1", "n2"], selectedEdges=[], activeNodeId="n2")
    )
    session.publish.reset_mock()

    handler.prune_node("n2")

    edit = session.context.data[edit_state_cls]
    assert handler.selected_nodes == {"n1"}
    assert edit.selected_nodes == {"n1"}
    assert edit.active_node is None
    assert any(isinstance(c.args[0], SelectionMoved) for c in session.publish.call_args_list)


def test_prune_node_ignores_an_unselected_node(handler, session):
    handler.process_selection_change(SelectionChangedEvent(selectedNodes=["n1"], selectedEdges=[]))
    session.publish.reset_mock()

    handler.prune_node("other")

    assert handler.selected_nodes == {"n1"}
    session.publish.assert_not_called()
