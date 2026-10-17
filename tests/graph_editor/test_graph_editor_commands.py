"""GraphEditor answers the keyboard EditorCommands on the canvas of the level on screen."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from typing import Any, cast
from unittest.mock import MagicMock

import pytest

from haywire.core.access import LevelMode
from haywire.core.graph.edit_route import EditRoute
from haywire.core.signals import (
    Copy,
    Cut,
    Delete,
    Duplicate,
    GraphDataMutated,
    Paste,
    Redo,
    SelectAll,
    ToggleLock,
    ToggleStageView,
    Undo,
)
from haybale_graph_editor.access import level_mode
from haybale_graph_editor.editors import graph_editor as graph_editor_module
from haybale_graph_editor.editors.graph_editor import DOCUMENT_LEVEL, GraphEditor, _Level

pytestmark = pytest.mark.unit

BINDING = "/tmp/graphs/main.haywire"


def _editor(canvas_manager: Any = None) -> tuple[GraphEditor, Any, Any]:
    """A GraphEditor with one document level holding ``canvas_manager``."""
    from haywire.ui.editor.wrapper import EditorWrapper

    document = SimpleNamespace(editor=MagicMock(), path=Path(BINDING), unsaved=False)
    wrapper = MagicMock()
    wrapper._binding_id = BINDING
    editor = GraphEditor(cast(EditorWrapper, wrapper))
    level = _Level(
        key=DOCUMENT_LEVEL,
        container=cast(Any, document),
        canvases={"patch": canvas_manager} if canvas_manager is not None else {},
    )
    level.route = EditRoute(lambda: document.editor, lambda: LevelMode.EDIT)
    editor._levels[DOCUMENT_LEVEL] = level
    context = SimpleNamespace(session=MagicMock(), data=MagicMock())
    return editor, context, document


def test_graph_editor_routes_commands():
    manager = MagicMock()
    editor, context, _ = _editor(manager)

    editor._on_copy(cast(Any, context), Copy(binding_id=BINDING))
    manager.copy_selection.assert_called_once_with()

    editor._on_delete(cast(Any, context), Delete(binding_id=BINDING))
    manager.delete_selection.assert_called_once_with()

    editor._on_select_all(cast(Any, context), SelectAll(binding_id=BINDING))
    manager.select_all_toggle.assert_called_once_with()

    editor._on_cut(cast(Any, context), Cut(binding_id=BINDING))
    manager.cut_selection.assert_called_once_with()

    editor._on_duplicate(cast(Any, context), Duplicate(binding_id=BINDING))
    manager.duplicate_selection.assert_called_once_with()


def test_undo_and_redo_go_through_the_document_history():
    editor, context, document = _editor(MagicMock())
    document.editor.can_undo.return_value = True
    document.editor.can_redo.return_value = True

    editor._on_undo(cast(Any, context), Undo(binding_id=BINDING))
    document.editor.undo.assert_called_once_with()
    published = [call.args[0] for call in context.session.publish.call_args_list]
    assert any(isinstance(signal, GraphDataMutated) for signal in published)

    editor._on_redo(cast(Any, context), Redo(binding_id=BINDING))
    document.editor.redo.assert_called_once_with()


def test_graph_editor_paste_uses_position(monkeypatch):
    notify = MagicMock()
    monkeypatch.setattr(graph_editor_module.ui, "notify", notify)
    manager = MagicMock()
    editor, context, _ = _editor(manager)

    editor._on_paste(cast(Any, context), Paste(binding_id=BINDING, position=(5.0, 6.0), text="t"))
    manager.paste.assert_called_once_with((5.0, 6.0), "t")

    manager.paste.reset_mock()
    editor._on_paste(cast(Any, context), Paste(binding_id=BINDING, position=None, text="t"))
    manager.paste.assert_not_called()
    notify.assert_called_once_with("Nothing to paste here", type="warning")


def test_commands_no_op_before_the_first_draw():
    editor, context, document = _editor(None)

    editor._on_copy(cast(Any, context), Copy(binding_id=BINDING))
    editor._on_delete(cast(Any, context), Delete(binding_id=BINDING))
    editor._on_select_all(cast(Any, context), SelectAll(binding_id=BINDING))
    editor._on_cut(cast(Any, context), Cut(binding_id=BINDING))
    editor._on_duplicate(cast(Any, context), Duplicate(binding_id=BINDING))

    context.session.publish.assert_not_called()
    context.data.__getitem__.assert_not_called()
    assert document.editor.method_calls == []


def _real_context(tier: Any) -> Any:
    from haywire.core.session.context import SessionContext

    from haywire.core.access import set_access_resolver

    set_access_resolver(lambda name: tier)
    ctx = SessionContext(session_id="s1", app=MagicMock())
    ctx.principal = "someone"
    return ctx


@pytest.fixture(autouse=True)
def _restore_resolver():
    from haywire.core.access import access_resolver, set_access_resolver

    previous = access_resolver()
    yield
    set_access_resolver(previous)


def _route_for(editor: GraphEditor, ctx: Any) -> None:
    """Give the document level the route the editor builds: its mode follows ``ctx`` and the lock."""
    level = editor._levels[DOCUMENT_LEVEL]
    level.route = EditRoute(lambda: level.container.editor, lambda: level_mode(ctx.can_access, level.locked))


def test_locked_level_refuses_every_command_but_the_toggles():
    from haywire.core.access import AccessTier

    editor, _, _ = _editor(MagicMock())
    editor._levels[DOCUMENT_LEVEL].locked = True
    ctx = _real_context(AccessTier.ADMIN)
    _route_for(editor, ctx)
    for command in (Undo, Redo, Delete, Paste, Cut, Duplicate):
        assert editor.accepts_command(ctx, command(binding_id=BINDING)) is False
    for allowed in (ToggleLock, ToggleStageView):
        assert editor.accepts_command(ctx, allowed(binding_id=BINDING)) is True


def test_select_all_passes_below_edit_and_copy_does_not():
    """Selecting is looking; copying acts on the selection."""
    from haywire.core.access import AccessTier

    editor, _, _ = _editor(MagicMock())
    editor._levels[DOCUMENT_LEVEL].locked = True
    ctx = _real_context(AccessTier.ADMIN)
    _route_for(editor, ctx)
    assert editor.accepts_command(ctx, Copy(binding_id=BINDING)) is False
    assert editor.accepts_command(ctx, SelectAll(binding_id=BINDING)) is True


def test_an_unlocked_edit_level_accepts_every_command():
    from haywire.core.access import AccessTier

    editor, _, _ = _editor(MagicMock())
    ctx = _real_context(AccessTier.EDIT)
    _route_for(editor, ctx)
    for command in (Copy, SelectAll, Undo, Delete, Paste, ToggleLock, ToggleStageView):
        assert editor.accepts_command(ctx, command(binding_id=BINDING)) is True


def test_toggle_stage_view_passes_in_view():
    from haywire.core.access import AccessTier

    editor, _, _ = _editor(MagicMock())
    ctx = _real_context(AccessTier.VIEW)
    _route_for(editor, ctx)
    assert editor.accepts_command(ctx, ToggleStageView(binding_id=BINDING)) is True
    assert editor.accepts_command(ctx, Copy(binding_id=BINDING)) is False


def test_toggle_lock_always_passes():
    from haywire.core.access import AccessTier

    editor, _, _ = _editor(MagicMock())
    for tier in (AccessTier.VIEW, AccessTier.OPERATE, AccessTier.EDIT):
        ctx = _real_context(tier)
        _route_for(editor, ctx)
        assert editor.accepts_command(ctx, ToggleLock(binding_id=BINDING)) is True


def test_no_level_open_accepts_only_the_toggles():
    from haywire.core.access import AccessTier

    editor, _, _ = _editor(MagicMock())
    editor._levels.clear()
    ctx = _real_context(AccessTier.ADMIN)
    assert editor.accepts_command(ctx, Copy(binding_id=BINDING)) is False
    assert editor.accepts_command(ctx, ToggleStageView(binding_id=BINDING)) is True


def test_toggle_lock_unlocks_for_edit():
    from haywire.core.access import AccessTier

    editor, _, _ = _editor(MagicMock())
    editor._claim_session_state = MagicMock()  # type: ignore[method-assign]
    editor._levels[DOCUMENT_LEVEL].locked = True
    ctx = _real_context(AccessTier.EDIT)
    editor._on_toggle_lock(ctx, ToggleLock(binding_id=BINDING))
    assert editor._levels[DOCUMENT_LEVEL].locked is False
    editor._on_toggle_lock(ctx, ToggleLock(binding_id=BINDING))
    assert editor._levels[DOCUMENT_LEVEL].locked is True


def test_save_ignores_the_lock(monkeypatch):
    from haywire.core.access import AccessTier

    monkeypatch.setattr(graph_editor_module.ui, "notify", MagicMock())
    editor, _, document = _editor(MagicMock())
    editor._levels[DOCUMENT_LEVEL].locked = True
    editor._update_header = MagicMock()  # type: ignore[method-assign]
    document.save = MagicMock(return_value=None)
    ctx = _real_context(AccessTier.EDIT)
    ctx.session = MagicMock()
    editor._save_graph(ctx)
    document.save.assert_called_once_with()


def test_save_refused_below_edit(monkeypatch):
    from haywire.core.access import AccessTier

    notify = MagicMock()
    monkeypatch.setattr(graph_editor_module.ui, "notify", notify)
    editor, _, document = _editor(MagicMock())
    document.save = MagicMock()
    ctx = _real_context(AccessTier.OPERATE)
    editor._save_graph(ctx)
    document.save.assert_not_called()
    notify.assert_called_once()


def test_a_refused_undo_publishes_nothing():
    manager = MagicMock()
    editor, context, document = _editor(manager)
    document.editor.can_undo.return_value = False

    editor._do_undo(cast(Any, context))
    document.editor.undo.assert_not_called()
    context.session.publish.assert_not_called()


def test_locked_level_undo_and_redo_do_nothing():
    from haywire.core.access import AccessTier

    ctx = _real_context(AccessTier.ADMIN)
    editor, context, document = _editor(None)
    editor._levels[DOCUMENT_LEVEL].locked = True
    _route_for(editor, ctx)
    document.editor.can_undo.return_value = True
    document.editor.can_redo.return_value = True

    editor._do_undo(cast(Any, context))
    editor._do_redo(cast(Any, context))

    document.editor.undo.assert_not_called()
    document.editor.redo.assert_not_called()
    context.session.publish.assert_not_called()


def test_view_principal_lock_button_is_disabled():
    from haywire.core.access import AccessTier

    editor, _, _ = _editor(MagicMock())
    editor._active_level = DOCUMENT_LEVEL
    editor._lock_button = MagicMock()

    editor._update_lock_button(_real_context(AccessTier.VIEW))
    editor._lock_button.set_enabled.assert_called_once_with(False)

    editor._lock_button.reset_mock()
    editor._update_lock_button(_real_context(AccessTier.EDIT))
    editor._lock_button.set_enabled.assert_called_once_with(True)


def _noop_page() -> None:  # registration target for a headless Client
    pass


def test_lock_button_tooltip_names_the_action_a_click_takes():
    from nicegui import Client, ui

    from haywire.core.access import AccessTier
    from haywire.ui import elements as hui

    editor, _, _ = _editor(MagicMock())
    with Client(cast(Any, _noop_page), request=None):
        editor._lock_button = hui.icon_action(hui.icon.unlocked)
        with editor._lock_button:
            tooltip = editor._lock_tooltip = ui.tooltip()

    editor._levels[DOCUMENT_LEVEL].locked = True
    editor._update_lock_button(_real_context(AccessTier.EDIT))
    assert tooltip.text == "Unlock (Ctrl+E)"

    editor._levels[DOCUMENT_LEVEL].locked = False
    editor._update_lock_button(_real_context(AccessTier.EDIT))
    assert tooltip.text == "Lock (Ctrl+E)"
