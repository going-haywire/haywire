"""Tests for HaystackEditor dirty-removal confirmation flow."""

from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

import haywire.core.graph.editor  # noqa: F401 -- circular-import guard

from haywire.core.session.context_signals import (
    ActiveGraphMoved,
    BroadcastClose,
    Close,
    GraphRemoved,
)
from haywire.core.session.reactive import Reactive


@pytest.fixture
def editor_and_context():
    """Return (editor, context, app, haystack) with a real HaystackEditor."""
    from haybale_haystack.editors.haystack_editor import HaystackEditor

    editor = HaystackEditor()
    haystack = MagicMock()
    haystack.save_graph = MagicMock(return_value=True)
    haystack.remove_entry = MagicMock(return_value=True)

    session = SimpleNamespace(
        session_id="sess-1",
        workspace_manager=None,
        signal=MagicMock(),
        lifecycle=MagicMock(),
    )

    app = SimpleNamespace(
        haystack=haystack,
        workspace_root="/tmp/ws",
        session_manager=None,
    )

    # _remove_entry reads/writes is_active via
    # ctx.data[EditState].active_graph. Build a fake `data` whose
    # `[EditState]` lookup yields a stub with real Reactive fields,
    # regardless of the EditState class identity passed (important after
    # library hot-reload swaps in a new class object).
    edit_stub = SimpleNamespace(
        active_graph=Reactive(None),
        active_graph_path=Reactive(None),
        active_node=Reactive(None),
        active_edge=Reactive(None),
        active_port=Reactive(None),
        selected_nodes=Reactive(set()),
        selected_edges=Reactive(set()),
        clipboard=Reactive(None),
    )
    data = MagicMock()
    data.__getitem__.return_value = edit_stub
    data.edit_stub = edit_stub

    # Post-PR2: the editor calls ``ctx.app_data[HaystackState]`` instead
    # of ``app.haystack``. Make the AppDataNamespace stub return the same
    # haystack mock for any class key, so the existing assertions still
    # work without needing to import HaystackState here.
    app_data = MagicMock()
    app_data.__getitem__.return_value = haystack

    context = SimpleNamespace(
        app=app,
        session=session,
        active_graph=Reactive(None),
        active_graph_path=Reactive(None),
        data=data,
        app_data=app_data,
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
    haystack.get_by_id = MagicMock(return_value=entry)

    with patch.object(editor, "_open_remove_confirm_dialog") as mock_dialog:
        editor._on_entry_delete(entry.entry_id, context)

    mock_dialog.assert_not_called()
    haystack.remove_entry.assert_called_once_with(entry)


def test_remove_dirty_file_backed_entry_opens_dialog(editor_and_context):
    editor, context, app, haystack = editor_and_context
    entry = _make_entry(path="/tmp/a.haywire", unsaved=True)
    haystack.get_by_id = MagicMock(return_value=entry)

    with patch.object(editor, "_open_remove_confirm_dialog") as mock_dialog:
        editor._on_entry_delete(entry.entry_id, context)

    mock_dialog.assert_called_once_with(entry, context)
    haystack.remove_entry.assert_not_called()


def test_remove_untitled_entry_opens_dialog(editor_and_context):
    editor, context, app, haystack = editor_and_context
    entry = _make_entry(path=None, unsaved=False)
    haystack.get_by_id = MagicMock(return_value=entry)

    with patch.object(editor, "_open_remove_confirm_dialog") as mock_dialog:
        editor._on_entry_delete(entry.entry_id, context)

    mock_dialog.assert_called_once_with(entry, context)


def test_remove_stale_entry_id_does_not_crash_or_remove(editor_and_context):
    """A row click after the haystack was hot-reloaded resolves to None.

    Re-resolution via _resolve_entry returns None and notifies — the
    handler bails before remove_entry is called. No crash, no orphan.
    """
    editor, context, app, haystack = editor_and_context
    haystack.get_by_id = MagicMock(return_value=None)

    with (
        patch.object(editor, "_open_remove_confirm_dialog") as mock_dialog,
        patch("haybale_haystack.editors.haystack_editor.ui.notify") as mock_notify,
    ):
        editor._on_entry_delete("__unsaved_42__", context)

    mock_dialog.assert_not_called()
    haystack.remove_entry.assert_not_called()
    assert any("no longer available" in str(c).lower() for c in mock_notify.call_args_list)


def test_remove_executing_entry_blocked_before_dialog(editor_and_context):
    editor, context, app, haystack = editor_and_context
    entry = _make_entry(path="/tmp/a.haywire", unsaved=True, is_executing=True)
    haystack.get_by_id = MagicMock(return_value=entry)

    with (
        patch.object(editor, "_open_remove_confirm_dialog") as mock_dialog,
        patch("haybale_haystack.editors.haystack_editor.ui.notify") as mock_notify,
    ):
        editor._on_entry_delete(entry.entry_id, context)

    mock_dialog.assert_not_called()
    haystack.remove_entry.assert_not_called()
    # The guard message should have been shown
    assert any("Stop execution" in str(c) for c in mock_notify.call_args_list)


def test_remove_entry_helper_fires_graph_removed_signal_and_close_command(editor_and_context):
    editor, context, app, haystack = editor_and_context
    entry = _make_entry(path="/tmp/a.haywire", unsaved=False)

    with patch("haybale_haystack.editors.haystack_editor.ui.notify"):
        editor._remove_entry(entry, context)

    # Signal channel: GraphRemoved (the editor still fires this for
    # cross-session view refresh that isn't tied to mutator semantics).
    # GraphDataMutated is now broadcast by HaystackState.remove_entry
    # itself via session_manager.broadcast_signal, not via the editor's
    # session.signal — so this mock-haystack test doesn't observe it.
    emitted_signals = [call.args[0] for call in context.session.signal.call_args_list]
    assert any(isinstance(s, GraphRemoved) for s in emitted_signals)

    # Lifecycle channel: a BroadcastClose for the removed entry — peer
    # sessions might have a GraphEditor open on the same entry, and the
    # entity is gone for everyone. BroadcastClose is-a Close, so the
    # isinstance(_, Close) check still holds for shared dispatch logic.
    emitted_commands = [call.args[0] for call in context.session.lifecycle.call_args_list]
    close_commands = [c for c in emitted_commands if isinstance(c, Close)]
    assert len(close_commands) == 1
    assert isinstance(close_commands[0], BroadcastClose)
    assert close_commands[0].payload == entry.entry_id


def test_remove_entry_helper_clears_active_graph_when_active(editor_and_context):
    editor, context, app, haystack = editor_and_context
    entry = _make_entry(path="/tmp/a.haywire", unsaved=False)
    # Mark this entry as the active one — the reader sources active_graph
    # from EditState (post-C3).
    edit = context.data.edit_stub
    edit.active_graph.value = entry.graph
    edit.active_graph_path.value = entry.path

    with patch("haybale_haystack.editors.haystack_editor.ui.notify"):
        editor._remove_entry(entry, context)

    assert edit.active_graph.value is None
    assert edit.active_graph_path.value is None
    emitted_signals = [call.args[0] for call in context.session.signal.call_args_list]
    assert any(isinstance(s, ActiveGraphMoved) for s in emitted_signals)
