"""SessionContext.clipboard is a reactive field carrying ClipboardData | None."""

from unittest.mock import MagicMock

from haywire.core.undo.actions.graph_actions import ClipboardData
from haywire.ui.context import SessionContext
from haywire.ui.reactive import Reactive, ReactivePath


def test_clipboard_class_access_is_reactive_path():
    p = SessionContext.clipboard
    assert isinstance(p, ReactivePath)
    assert p.owner is SessionContext
    assert p.attr == "clipboard"


def test_clipboard_instance_access_is_reactive():
    ctx = SessionContext(session_id="t", app=MagicMock())
    assert isinstance(ctx.clipboard, Reactive)
    assert ctx.clipboard.value is None


def test_clipboard_write_through_value():
    ctx = SessionContext(session_id="t", app=MagicMock())
    data = ClipboardData(
        nodes=["a", "b"],
        edges=[],
        original_to_new_ids={},
        bounding_box={"min_x": 0, "min_y": 0, "max_x": 0, "max_y": 0},
        timestamp=1.0,
        source_session_id="t",
    )
    ctx.clipboard.value = data
    assert ctx.clipboard.value is data


def test_copy_selection_handler_writes_to_session_context():
    """SelectionHandlers.process_copy_selection writes to ctx.clipboard.value."""
    from unittest.mock import MagicMock

    from haywire.core.undo.actions.graph_actions import ClipboardData
    from haywire.ui.context import SessionContext
    from haywire.ui.graph_canvas.event_definitions import UserCopySelectedEvent
    from haywire.ui.graph_canvas.handlers.selection import SelectionHandlers

    # Build a SessionContext + Session
    ctx = SessionContext(session_id="t", app=MagicMock())
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

    # Initially clipboard is None
    assert ctx.clipboard.value is None

    # Process a copy event
    handlers.process_copy_selection(UserCopySelectedEvent(selectedNodes=["a"], selectedEdges=[]))

    # Now ctx.clipboard.value is a ClipboardData
    assert ctx.clipboard.value is not None
    assert isinstance(ctx.clipboard.value, ClipboardData)
    assert ctx.clipboard.value.nodes == ["a"]


def test_paste_clipboard_handler_reads_from_session_context():
    """SelectionHandlers.process_paste_clipboard reads from ctx.clipboard.value."""
    from unittest.mock import MagicMock

    from haywire.core.undo.actions.graph_actions import ClipboardData
    from haywire.ui.context import SessionContext
    from haywire.ui.graph_canvas.event_definitions import UserPasteClipboardEvent
    from haywire.ui.graph_canvas.handlers.selection import SelectionHandlers

    ctx = SessionContext(session_id="t", app=MagicMock())
    session = MagicMock()
    session.context = ctx

    handlers = SelectionHandlers(graph=MagicMock(), editor=MagicMock(), session_id="t", session=session)

    # No clipboard → no-op (logs warning, doesn't crash)
    handlers.process_paste_clipboard(UserPasteClipboardEvent(canvasX=0, canvasY=0))
    # No assertion — just verify no crash.

    # With clipboard → handler reads ctx.clipboard.value
    ctx.clipboard.value = ClipboardData(
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
