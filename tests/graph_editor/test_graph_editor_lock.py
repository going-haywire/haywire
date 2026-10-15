"""GraphEditor's per-level canvas lock."""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any
from unittest.mock import MagicMock

import pytest

from haybale_graph_editor.editors.graph_editor import DOCUMENT_LEVEL, GraphEditor
from haybale_graph_editor.state.graph_app_state import GraphAppState
from haybale_graph_editor.state.edit_state import EditState
from haywire.core.access import AccessTier, access_resolver, set_access_resolver
from haywire.core.session.context import SessionContext
from haywire.core.signals import ActiveGraphMoved

from .test_graph_editor_levels import _definition, _editor, _FakeDocument, _FakeGraph

pytestmark = pytest.mark.unit


@pytest.fixture(autouse=True)
def _restore_resolver():
    previous = access_resolver()
    yield
    set_access_resolver(previous)


def _session_context(tier: AccessTier) -> SessionContext:
    set_access_resolver(lambda name: tier)
    app = MagicMock()
    app.library_state_container = MagicMock()
    ctx = SessionContext(session_id="s1", app=app)
    ctx.principal = "someone"
    return ctx


def _locked_editor(tier: AccessTier, open_locked: bool = True) -> tuple[GraphEditor, Any, _FakeDocument]:
    document = _FakeDocument()
    document.editor.graph.props = SimpleNamespace(open_locked=open_locked)  # type: ignore[attr-defined,assignment]
    editor, context, document = _editor(document)
    real = _session_context(tier)
    context.can_access = real.can_access
    context.can_edit = real.can_edit
    # The default fixture stubs the claim; the lock tests need the real one.
    editor._claim_session_state = GraphEditor._claim_session_state.__get__(editor)  # type: ignore[method-assign]
    context.data = {
        EditState: SimpleNamespace(active_graph=None, active_graph_path=None, active_locked=False)
    }
    return editor, context, document


def test_a_document_opens_with_the_graph_default():
    editor, context, document = _locked_editor(AccessTier.EDIT)
    editor._levels.pop(DOCUMENT_LEVEL)
    context.app_data[GraphAppState].get.return_value = document
    assert editor._ensure_document_level(context) is document
    assert editor._levels[DOCUMENT_LEVEL].locked is True


def test_locking_is_per_level():
    editor, context, document = _locked_editor(AccessTier.EDIT)
    editor._levels[DOCUMENT_LEVEL].locked = True
    group = SimpleNamespace(editor=SimpleNamespace(graph=_FakeGraph("g")))
    definition = _definition()
    from haybale_graph_editor.protocols import SubgraphContainer

    container = SubgraphContainer.__new__(SubgraphContainer)
    container.definition = definition
    container.host = document
    container.editor = group.editor
    key = editor._open_level(context, container)
    assert editor._levels[key].locked is False
    assert editor._levels[DOCUMENT_LEVEL].locked is True


def test_unlock_needs_real_edit():
    editor, context, _ = _locked_editor(AccessTier.OPERATE)
    editor._levels[DOCUMENT_LEVEL].locked = True
    assert editor.set_level_locked(context, DOCUMENT_LEVEL, False) is False
    assert editor._levels[DOCUMENT_LEVEL].locked is True

    editor, context, _ = _locked_editor(AccessTier.EDIT)
    editor._levels[DOCUMENT_LEVEL].locked = True
    assert editor.set_level_locked(context, DOCUMENT_LEVEL, False) is True
    assert editor._levels[DOCUMENT_LEVEL].locked is False


def test_claim_publishes_the_lock():
    editor, context, _ = _locked_editor(AccessTier.EDIT, open_locked=False)
    editor._claim_session_state(context)
    context.session.publish.reset_mock()
    assert editor.set_level_locked(context, DOCUMENT_LEVEL, True) is True
    assert context.data[EditState].active_locked is True
    assert isinstance(context.session.publish.call_args.args[0], ActiveGraphMoved)


class _Popup:
    """The parts of the toolbar ``Popup`` the provider drives, with its open state."""

    def __init__(self) -> None:
        self.is_open = True

    def open(self) -> None:
        self.is_open = True

    def close(self) -> None:
        self.is_open = False

    def run_method(self, *_args: Any) -> None:
        pass


def test_locking_with_a_selection_leaves_the_toolbar_hidden(monkeypatch):
    """Locking hides the toolbar, and the session-state claim that follows does not re-show it."""
    from haybale_graph_editor.editors.graph_canvas.graph_canvas_manager import GraphCanvasManager
    from haybale_graph_editor.editors.graph_canvas.handlers import selection_toolbar as toolbar_module
    from haybale_graph_editor.editors.graph_canvas.handlers.selection_toolbar import SelectionToolbarProvider

    editor, context, _ = _locked_editor(AccessTier.EDIT, open_locked=False)
    manager: Any = object.__new__(GraphCanvasManager)
    manager._session = SimpleNamespace(context=SimpleNamespace(can_access=AccessTier.EDIT.satisfies))
    manager.locked = False
    manager.canvas_vue = MagicMock()
    manager.context_menu_handlers = SimpleNamespace(provider=MagicMock())
    registry = MagicMock()
    registry.get_panels.return_value = [object()]
    provider = SelectionToolbarProvider(
        context=MagicMock(),
        session=MagicMock(),
        panel_registry=registry,
        menu_provider=MagicMock(),
        allows=manager.allows,
    )
    monkeypatch.setattr(toolbar_module, "_poll_surface", lambda surface, ctx: True)
    monkeypatch.setattr(toolbar_module, "partition_panels", lambda classes, ctx: (classes, []))
    provider._render_into_popup = lambda applies, disabled: True  # type: ignore[method-assign]
    popup = _Popup()
    provider._toolbar_popup = popup  # type: ignore[assignment]
    provider._last_bounds = (0.0, 0.0, 10.0, 10.0)
    manager._toolbar_provider = provider
    editor._levels[DOCUMENT_LEVEL].canvases["patch"] = manager

    assert editor.set_level_locked(context, DOCUMENT_LEVEL, True) is True

    assert popup.is_open is False


def test_a_mounted_canvas_follows_the_level_lock(monkeypatch):
    from haybale_graph_editor.editors import graph_editor as graph_editor_module

    editor, context, _ = _locked_editor(AccessTier.EDIT)
    level = editor._levels[DOCUMENT_LEVEL]
    level.locked = True
    manager = MagicMock()
    monkeypatch.setattr(graph_editor_module, "ui", MagicMock())
    editor._level_panels = MagicMock()
    editor._build_canvas = MagicMock(return_value=manager)  # type: ignore[method-assign]
    # The default fixture stubs _mount_level; this test needs the real one.
    GraphEditor._mount_level(editor, context, level)
    manager.set_locked.assert_called_once_with(True)


def test_an_operate_principal_mounts_a_read_only_canvas_on_an_unlocked_level(monkeypatch):
    """Below edit the browser canvas starts no editing gesture, lock or no lock."""
    from haybale_graph_editor.editors import graph_editor as graph_editor_module
    from haybale_graph_editor.editors.graph_canvas.graph_canvas_manager import GraphCanvasManager

    editor, context, _ = _locked_editor(AccessTier.OPERATE, open_locked=False)
    level = editor._levels[DOCUMENT_LEVEL]
    manager: Any = object.__new__(GraphCanvasManager)
    manager._session = SimpleNamespace(context=context)
    manager.locked = False
    manager.canvas_vue = MagicMock()
    manager._toolbar_provider = MagicMock()
    manager.context_menu_handlers = SimpleNamespace(provider=MagicMock())
    monkeypatch.setattr(graph_editor_module, "ui", MagicMock())
    editor._level_panels = MagicMock()
    editor._build_canvas = MagicMock(return_value=manager)  # type: ignore[method-assign]

    GraphEditor._mount_level(editor, context, level)

    assert manager.locked is False
    manager.canvas_vue.set_locked.assert_called_once_with(True)
