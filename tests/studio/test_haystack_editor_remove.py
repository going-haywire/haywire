"""Tests for HaystackEditor dirty-removal confirmation flow."""

from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

import haywire.core.graph.editor  # noqa: F401 -- circular-import guard

from haywire.ui.context_signals import ActiveGraphMoved, GraphDataMutated, GraphRemoved


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
        signal=MagicMock(),
        reveal=MagicMock(),
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


def _make_entry(
    path=None,
    unsaved: bool = False,
    is_executing: bool = False,
    entry_id: str = "/tmp/a.haywire",
):
    graph = object()
    return SimpleNamespace(
        graph=graph,
        path=path,
        unsaved=unsaved,
        is_executing=is_executing,
        entry_id=entry_id,
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

    emitted_signals = [call.args[0] for call in context.session.signal.call_args_list]
    # GraphRemoved emitted (with the right entry_id), and GraphDataMutated emitted
    # via _notify_data_mutated. Both are cross_session=True per §11.
    graph_removed_signals = [s for s in emitted_signals if isinstance(s, GraphRemoved)]
    assert len(graph_removed_signals) == 1
    assert graph_removed_signals[0].entry_id == entry.entry_id
    assert any(isinstance(s, GraphDataMutated) for s in emitted_signals)


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
    emitted_signals = [call.args[0] for call in context.session.signal.call_args_list]
    assert any(isinstance(s, ActiveGraphMoved) for s in emitted_signals)
