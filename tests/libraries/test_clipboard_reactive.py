"""EditState.clipboard is a reactive field carrying ClipboardData | None.

After v1.2 C5, ``clipboard`` lives only on
``haybale_graph_editor.state.edit_state.EditState`` (accessed via
``ctx.data[EditState].clipboard``). The behavior tests below assert
the writer/reader contract over EditState.
"""

from unittest.mock import MagicMock

from haywire.core.state import LibraryStateContainer, LibraryStateRegistry
from haywire.core.undo.actions.graph_actions import ClipboardData
from haywire.core.session.context import SessionContext


def _make_ctx_with_edit_state(register_edit_state):
    """Build a SessionContext with EditState registered for one session."""
    container = LibraryStateContainer(LibraryStateRegistry())
    sid = "t"
    EditStateCls = register_edit_state(container, sid)
    app = MagicMock()
    app.library_state_container = container
    ctx = SessionContext(session_id=sid, app=app)
    return ctx, EditStateCls


def test_copy_selection_handler_writes_to_session_context(register_edit_state):
    """SelectionHandlers.process_copy_selection writes the clipboard to EditState."""
    from haywire.ui.components.graph.event_definitions import UserCopySelectedEvent
    from haybale_graph_editor.editors.graph_canvas.handlers.selection import SelectionHandlers

    ctx, EditStateCls = _make_ctx_with_edit_state(register_edit_state)
    session = MagicMock()
    session.context = ctx

    # Build a fake graph with one node
    wrapper = MagicMock()
    wrapper.node = MagicMock()
    wrapper.node.props.posX = 10.0
    wrapper.node.props.posY = 20.0

    graph = MagicMock()
    graph.get_node_wrapper.return_value = wrapper

    handlers = SelectionHandlers(graph=graph, editor=MagicMock(), session_id="t", session=session)

    edit = ctx.data[EditStateCls]
    # Initially clipboard is None
    assert edit.clipboard is None

    # Process a copy event
    handlers.process_copy_selection(UserCopySelectedEvent(selectedNodes=["a"], selectedEdges=[]))

    # Now ctx.data[EditState].clipboard is a ClipboardData
    assert edit.clipboard is not None
    assert isinstance(edit.clipboard, ClipboardData)
    assert list(edit.clipboard.payload["nodes"].keys()) == ["a"]


def test_paste_clipboard_handler_reads_from_session_context(register_edit_state):
    """SelectionHandlers.process_paste_clipboard reads the clipboard from EditState."""
    from unittest.mock import patch

    from haywire.ui.components.graph.event_definitions import UserPasteClipboardEvent
    from haybale_graph_editor.editors.graph_canvas.handlers.selection import SelectionHandlers

    ctx, EditStateCls = _make_ctx_with_edit_state(register_edit_state)
    session = MagicMock()
    session.context = ctx

    editor = MagicMock()
    editor.paste_clipboard.return_value = (["a_new"], [])  # (new_node_ids, new_edge_ids)
    handlers = SelectionHandlers(graph=MagicMock(), editor=editor, session_id="t", session=session)

    # Mock ui.notify for the whole test: both paths call it and require a NiceGUI context.
    with patch("nicegui.ui.notify") as mock_notify:
        # No clipboard → "Nothing to paste" warning.
        handlers.process_paste_clipboard(UserPasteClipboardEvent(canvasX=0, canvasY=0))
        assert mock_notify.call_count == 1

        # With clipboard → handler reads ctx.data[EditState].clipboard and pastes it.
        ctx.data[EditStateCls].clipboard = ClipboardData(
            payload={
                "haywire_clipboard": True,
                "format_version": 1,
                "source": {"session_id": "t", "timestamp": 1.0},
                "bounding_box": {"min_x": 0, "min_y": 0, "max_x": 0, "max_y": 0},
                "nodes": {"a": {"node_id": "a"}},
                "edges": {},
            },
            timestamp=1.0,
        )
        handlers.process_paste_clipboard(UserPasteClipboardEvent(canvasX=10, canvasY=20))
        # Handler routes clipboard to editor.paste_clipboard.
        editor.paste_clipboard.assert_called_once()
