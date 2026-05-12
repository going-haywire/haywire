"""Tests for HaystackEditor dirty-removal confirmation flow."""

from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

import haywire.core.graph.editor  # noqa: F401 -- circular-import guard

from haywire.core.session.signals_and_lifecycle import (
    ActiveGraphMoved,
    BroadcastClose,
    Close,
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


def test_remove_clean_entry_opens_confirm_with_stays_on_disk_wording(editor_and_context):
    """Clean entries get a confirm modal that calls out the file stays on disk."""
    editor, context, app, haystack = editor_and_context
    entry = _make_entry(path="/tmp/a.haywire", unsaved=False)
    haystack.get_by_id = MagicMock(return_value=entry)

    with patch("haybale_haystack.editors.haystack_editor.confirm_modal") as mock_modal:
        editor._on_entry_delete(entry.entry_id, context)

    mock_modal.assert_called_once()
    kwargs = mock_modal.call_args.kwargs
    assert "stays on disk" in kwargs["message"].lower()
    assert kwargs["confirm_label"] == "Remove"
    # The handler must not have removed the entry yet — that's the on_confirm callback's job.
    haystack.remove_entry.assert_not_called()


def test_remove_clean_entry_on_confirm_callback_removes(editor_and_context):
    """Invoking the on_confirm callback supplied to confirm_modal removes the entry."""
    editor, context, app, haystack = editor_and_context
    entry = _make_entry(path="/tmp/a.haywire", unsaved=False)
    haystack.get_by_id = MagicMock(return_value=entry)

    with (
        patch("haybale_haystack.editors.haystack_editor.confirm_modal") as mock_modal,
        patch("haybale_haystack.editors.haystack_editor.ui.notify"),
    ):
        editor._on_entry_delete(entry.entry_id, context)
        on_confirm = mock_modal.call_args.kwargs["on_confirm"]
        on_confirm()

    haystack.remove_entry.assert_called_once_with(entry)


def test_remove_dirty_file_backed_entry_uses_discard_wording(editor_and_context):
    editor, context, app, haystack = editor_and_context
    entry = _make_entry(path="/tmp/a.haywire", unsaved=True)
    haystack.get_by_id = MagicMock(return_value=entry)

    with patch("haybale_haystack.editors.haystack_editor.confirm_modal") as mock_modal:
        editor._on_entry_delete(entry.entry_id, context)

    mock_modal.assert_called_once()
    kwargs = mock_modal.call_args.kwargs
    assert "unsaved changes" in kwargs["message"].lower()
    assert kwargs["confirm_label"] == "Discard"
    haystack.remove_entry.assert_not_called()


def test_remove_untitled_entry_uses_never_saved_wording(editor_and_context):
    editor, context, app, haystack = editor_and_context
    entry = _make_entry(path=None, unsaved=False)
    haystack.get_by_id = MagicMock(return_value=entry)

    with patch("haybale_haystack.editors.haystack_editor.confirm_modal") as mock_modal:
        editor._on_entry_delete(entry.entry_id, context)

    mock_modal.assert_called_once()
    kwargs = mock_modal.call_args.kwargs
    assert "never been saved" in kwargs["message"].lower()
    assert kwargs["confirm_label"] == "Discard"


def test_remove_stale_entry_id_does_not_crash_or_remove(editor_and_context):
    """A row click after the haystack was hot-reloaded resolves to None.

    Re-resolution via _resolve_entry returns None and notifies — the
    handler bails before confirm_modal is called. No crash, no orphan.
    """
    editor, context, app, haystack = editor_and_context
    haystack.get_by_id = MagicMock(return_value=None)

    with (
        patch("haybale_haystack.editors.haystack_editor.confirm_modal") as mock_modal,
        patch("haybale_haystack.editors.haystack_editor.ui.notify") as mock_notify,
    ):
        editor._on_entry_delete("__unsaved_42__", context)

    mock_modal.assert_not_called()
    haystack.remove_entry.assert_not_called()
    assert any("no longer available" in str(c).lower() for c in mock_notify.call_args_list)


def test_remove_executing_entry_blocked_before_dialog(editor_and_context):
    editor, context, app, haystack = editor_and_context
    entry = _make_entry(path="/tmp/a.haywire", unsaved=True, is_executing=True)
    haystack.get_by_id = MagicMock(return_value=entry)

    with (
        patch("haybale_haystack.editors.haystack_editor.confirm_modal") as mock_modal,
        patch("haybale_haystack.editors.haystack_editor.ui.notify") as mock_notify,
    ):
        editor._on_entry_delete(entry.entry_id, context)

    mock_modal.assert_not_called()
    haystack.remove_entry.assert_not_called()
    # The guard message should have been shown
    assert any("Stop execution" in str(c) for c in mock_notify.call_args_list)


def test_remove_entry_helper_fires_broadcast_close(editor_and_context):
    """_remove_entry issues a BroadcastClose so peer GraphEditor tabs close.

    GraphDataMutated cross-session refresh is broadcast by
    HaystackState.remove_entry itself (via session_manager.broadcast_signal),
    not via the editor — this mock-haystack test doesn't observe that path.
    """
    editor, context, app, haystack = editor_and_context
    entry = _make_entry(path="/tmp/a.haywire", unsaved=False)

    with patch("haybale_haystack.editors.haystack_editor.ui.notify"):
        editor._remove_entry(entry, context)

    # Lifecycle channel: a BroadcastClose for the removed entry — peer
    # sessions might have a GraphEditor open on the same entry, and the
    # entity is gone for everyone. BroadcastClose is-a Close, so the
    # isinstance(_, Close) check still holds for shared dispatch logic.
    emitted_commands = [call.args[0] for call in context.session.lifecycle.call_args_list]
    close_commands = [c for c in emitted_commands if isinstance(c, Close)]
    assert len(close_commands) == 1
    assert isinstance(close_commands[0], BroadcastClose)
    assert close_commands[0].binding_id == entry.entry_id


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
