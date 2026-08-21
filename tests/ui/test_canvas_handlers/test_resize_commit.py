import haywire.core.graph.editor  # noqa: F401  (circular-import guard)

from unittest.mock import MagicMock

from haywire.core.signals import GraphDataMutated
from haywire.ui.components.graph.event_definitions import UserResizeEndEvent
from haybale_graph_editor.editors.graph_canvas.handlers.interaction import InteractionHandlers


def test_resize_end_event_registered():
    assert UserResizeEndEvent.event_type == "userResizeEnd"


def test_resize_commit_publishes_graph_data_mutated():
    """Size props are cosmetic — they never mark a node dirty, so nothing else
    broadcasts. The handler must publish GraphDataMutated so the toolbar's
    undo/redo enablement refreshes immediately after a resize (regression: the
    undo button stayed stale until the next validating op)."""
    editor = MagicMock()
    session = MagicMock()
    h = InteractionHandlers(editor, session=session)
    h.process_resize_end(
        UserResizeEndEvent(nodeId="n1", width=300.0, height=180.0, size_adapt="manual_width")
    )
    session.publish.assert_called_once()
    (published,) = session.publish.call_args.args
    assert isinstance(published, GraphDataMutated)


def test_resize_commit_without_session_does_not_raise():
    """Session is optional (default None); the guard must skip the publish."""
    editor = MagicMock()
    h = InteractionHandlers(editor)  # no session
    h.process_resize_end(UserResizeEndEvent(nodeId="n1", width=300.0, height=180.0, size_adapt="manual"))
    assert editor.add_fence.call_count == 2  # still commits normally


def test_size_only_commit_is_one_fence_no_move():
    editor = MagicMock()
    h = InteractionHandlers(editor)
    h.process_resize_end(
        UserResizeEndEvent(nodeId="n1", width=300.0, height=180.0, size_adapt="manual_width")
    )
    # fence opened and closed around the size writes; no move
    assert editor.add_fence.call_count == 2
    editor.move_nodes_to.assert_not_called()
    # prefer_setting=True: a node exposing a port named "width"/"height" must
    # not swallow the size-prop write (regression: resize didn't stick on a
    # frame-info node with width/height outlets).
    editor.set_property.assert_any_call("n1", "size_adapt", "manual_width", prefer_setting=True)
    editor.set_property.assert_any_call("n1", "width", 300.0, prefer_setting=True)
    editor.set_property.assert_any_call("n1", "height", 180.0, prefer_setting=True)


def test_top_left_commit_fences_size_and_move_together():
    editor = MagicMock()
    h = InteractionHandlers(editor)
    h.process_resize_end(
        UserResizeEndEvent(
            nodeId="n1",
            width=260.0,
            height=160.0,
            size_adapt="manual",
            posX=40.0,
            posY=20.0,
        )
    )
    assert editor.add_fence.call_count == 2  # one gesture = one undo group
    editor.move_nodes_to.assert_called_once_with({"n1": {"x": 40.0, "y": 20.0}})
    editor.set_property.assert_any_call("n1", "width", 260.0, prefer_setting=True)
