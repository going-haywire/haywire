"""Tests for HaystackEditor dirty-removal confirmation flow."""

from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

import haywire.core.graph.editor  # noqa: F401 -- circular-import guard

from haywire.ui.context_events import ContextChangeType


@pytest.fixture
def editor_and_context():
    """Return (editor, context, app, haystack) with a real HaystackEditor."""
    from haybale_studio.editors.haystack_editor import HaystackEditor

    editor = HaystackEditor()
    haystack = MagicMock()
    haystack.save_graph = MagicMock(return_value=True)
    haystack.remove_entry = MagicMock(return_value=True)

    session = SimpleNamespace(
        session_id="sess-1",
        workspace_manager=None,
        notify_context_changed=MagicMock(),
        notify_cross_session_context_change=MagicMock(),
    )

    app = SimpleNamespace(
        haystack=haystack,
        workspace_root="/tmp/ws",
        session_manager=None,
    )

    context = SimpleNamespace(
        app=app,
        session=session,
        active_graph=None,
        active_graph_path=None,
    )
    return editor, context, app, haystack


def _make_entry(path=None, unsaved: bool = False, is_executing: bool = False, key: str = "/tmp/a.haywire"):
    graph = object()
    return SimpleNamespace(
        graph=graph,
        path=path,
        unsaved=unsaved,
        is_executing=is_executing,
        key=key,
        display_name="a.haywire",
        stop_execution=MagicMock(),
    )


def test_remove_clean_entry_skips_dialog_and_removes(editor_and_context):
    editor, context, app, haystack = editor_and_context
    entry = _make_entry(path="/tmp/a.haywire", unsaved=False)

    with patch.object(editor, "_open_remove_confirm_dialog") as mock_dialog:
        editor._on_entry_delete(entry, context)

    mock_dialog.assert_not_called()
    haystack.remove_entry.assert_called_once_with(entry)


def test_remove_dirty_file_backed_entry_opens_dialog(editor_and_context):
    editor, context, app, haystack = editor_and_context
    entry = _make_entry(path="/tmp/a.haywire", unsaved=True)

    with patch.object(editor, "_open_remove_confirm_dialog") as mock_dialog:
        editor._on_entry_delete(entry, context)

    mock_dialog.assert_called_once_with(entry, context)
    haystack.remove_entry.assert_not_called()


def test_remove_untitled_entry_opens_dialog(editor_and_context):
    editor, context, app, haystack = editor_and_context
    entry = _make_entry(path=None, unsaved=False)

    with patch.object(editor, "_open_remove_confirm_dialog") as mock_dialog:
        editor._on_entry_delete(entry, context)

    mock_dialog.assert_called_once_with(entry, context)


def test_remove_executing_entry_blocked_before_dialog(editor_and_context):
    editor, context, app, haystack = editor_and_context
    entry = _make_entry(path="/tmp/a.haywire", unsaved=True, is_executing=True)

    with (
        patch.object(editor, "_open_remove_confirm_dialog") as mock_dialog,
        patch("haybale_studio.editors.haystack_editor.ui.notify") as mock_notify,
    ):
        editor._on_entry_delete(entry, context)

    mock_dialog.assert_not_called()
    haystack.remove_entry.assert_not_called()
    # The guard message should have been shown
    assert any("Stop execution" in str(c) for c in mock_notify.call_args_list)


def test_remove_entry_helper_fires_graph_removed(editor_and_context):
    editor, context, app, haystack = editor_and_context
    entry = _make_entry(path="/tmp/a.haywire", unsaved=False)

    with patch("haybale_studio.editors.haystack_editor.ui.notify"):
        editor._remove_entry(entry, context)

    local_event_types = [
        call.args[0].change_type for call in context.session.notify_context_changed.call_args_list
    ]
    cross_event_types = [
        call.args[0].change_type
        for call in context.session.notify_cross_session_context_change.call_args_list
    ]
    assert ContextChangeType.GRAPH_REMOVED in local_event_types
    assert ContextChangeType.DATA_MUTATED in cross_event_types


def test_remove_entry_helper_clears_active_graph_when_active(editor_and_context):
    editor, context, app, haystack = editor_and_context
    entry = _make_entry(path="/tmp/a.haywire", unsaved=False)
    # Mark this entry as the active one
    context.active_graph = entry.graph
    context.active_graph_path = entry.path

    with patch("haybale_studio.editors.haystack_editor.ui.notify"):
        editor._remove_entry(entry, context)

    assert context.active_graph is None
    assert context.active_graph_path is None
    event_types = [
        call.args[0].change_type for call in context.session.notify_context_changed.call_args_list
    ]
    assert ContextChangeType.ACTIVE_GRAPH_CHANGED in event_types
