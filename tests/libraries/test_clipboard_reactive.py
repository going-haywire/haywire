"""EditState.clipboard is a reactive field carrying ClipboardData | None.

After v1.2 C5, ``clipboard`` lives only on
``haybale_studio.state.edit_state.EditState`` (accessed via
``ctx.data[EditState].clipboard``). The behavior tests below assert
the writer/reader contract over EditState.
"""

from unittest.mock import MagicMock

from haywire.core.state import LibraryStateContainer
from haywire.core.undo.actions.graph_actions import ClipboardData
from haywire.ui.context import SessionContext


def _make_ctx_with_edit_state(register_edit_state):
    """Build a SessionContext with EditState registered for one session."""
    container = LibraryStateContainer()
    sid = "t"
    EditStateCls = register_edit_state(container, sid)
    app = MagicMock()
    app.library_state_container = container
    ctx = SessionContext(session_id=sid, app=app)
    return ctx, EditStateCls


def test_copy_selection_handler_writes_to_session_context(register_edit_state):
    """SelectionHandlers.process_copy_selection writes the clipboard to EditState."""
    from haybale_studio.editors.graph_canvas.event_definitions import UserCopySelectedEvent
    from haybale_studio.editors.graph_canvas.handlers.selection import SelectionHandlers

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
    assert edit.clipboard.value is None

    # Process a copy event
    handlers.process_copy_selection(UserCopySelectedEvent(selectedNodes=["a"], selectedEdges=[]))

    # Now ctx.data[EditState].clipboard.value is a ClipboardData
    assert edit.clipboard.value is not None
    assert isinstance(edit.clipboard.value, ClipboardData)
    assert edit.clipboard.value.nodes == ["a"]


def test_paste_clipboard_handler_reads_from_session_context(register_edit_state):
    """SelectionHandlers.process_paste_clipboard reads the clipboard from EditState."""
    from haybale_studio.editors.graph_canvas.event_definitions import UserPasteClipboardEvent
    from haybale_studio.editors.graph_canvas.handlers.selection import SelectionHandlers

    ctx, EditStateCls = _make_ctx_with_edit_state(register_edit_state)
    session = MagicMock()
    session.context = ctx

    handlers = SelectionHandlers(graph=MagicMock(), editor=MagicMock(), session_id="t", session=session)

    # No clipboard → no-op (logs warning, doesn't crash)
    handlers.process_paste_clipboard(UserPasteClipboardEvent(canvasX=0, canvasY=0))
    # No assertion — just verify no crash.

    # With clipboard → handler reads ctx.data[EditState].clipboard.value
    ctx.data[EditStateCls].clipboard.value = ClipboardData(
        nodes=["a"],
        edges=[],
        original_to_new_ids={},
        bounding_box={"min_x": 0, "min_y": 0, "max_x": 0, "max_y": 0},
        timestamp=1.0,
        source_session_id="t",
    )
    handlers.process_paste_clipboard(UserPasteClipboardEvent(canvasX=10, canvasY=20))
    # Handler reads clipboard from ctx; the actual paste logic is pending.
    # Verify no crash.
