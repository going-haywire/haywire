"""HaystackEditor Save and Save-as need the principal's real edit tier."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from typing import Any, cast
from unittest.mock import MagicMock

import pytest

from haybale_haystack.editors import haystack_editor as haystack_editor_module
from haybale_graph_editor.state.edit_state import EditState
from haybale_haystack.editors.haystack_editor import HaystackEditor
from haywire.core.access import AccessTier, access_resolver, set_access_resolver
from haywire.core.session.context import SessionContext
from haywire.ui.editor.wrapper import EditorWrapper

pytestmark = pytest.mark.unit


@pytest.fixture(autouse=True)
def _restore_resolver():
    previous = access_resolver()
    yield
    set_access_resolver(previous)


def _setup(tier: AccessTier, monkeypatch: pytest.MonkeyPatch) -> tuple[HaystackEditor, Any, Any, MagicMock]:
    set_access_resolver(lambda name: tier)
    haystack = MagicMock()
    haystack.save_graph = MagicMock(return_value=True)
    entry = SimpleNamespace(path=Path("/tmp/a.haywire"), unsaved=True, graph=object())
    haystack.get_by_id = MagicMock(return_value=entry)
    context = SessionContext(session_id="s1", app=MagicMock())
    context.principal = "someone"
    app_data = MagicMock()
    app_data.__getitem__.return_value = haystack
    context.app_data = app_data  # type: ignore[assignment]
    dialog = MagicMock()
    monkeypatch.setattr(haystack_editor_module, "open_graph_save_as_dialog", dialog)
    monkeypatch.setattr(haystack_editor_module.ui, "notify", MagicMock())
    monkeypatch.setattr(haystack_editor_module.ui, "context", SimpleNamespace(client=MagicMock()))
    editor = HaystackEditor(cast(EditorWrapper, object()))
    return editor, context, haystack, dialog


@pytest.mark.parametrize("tier", [AccessTier.VIEW, AccessTier.OPERATE])
def test_save_refused_below_edit(tier, monkeypatch):
    editor, context, haystack, dialog = _setup(tier, monkeypatch)
    editor._on_entry_save("id", context)
    editor._on_entry_save_as("id", context)
    haystack.save_graph.assert_not_called()
    dialog.assert_not_called()
    assert haystack_editor_module.ui.notify.call_count == 2  # type: ignore[attr-defined]


def _haystack_header_setup(tier: AccessTier, monkeypatch: pytest.MonkeyPatch) -> tuple[Any, Any, Any, Any]:
    """An editor with a loaded haystack named ``hs1``, and the modal Save As opens, mocked."""
    editor, context, haystack, _dialog = _setup(tier, monkeypatch)
    editor._get_active_haystack_name = lambda ctx: "hs1"  # type: ignore[method-assign]
    haystack.is_haystack_dirty = True
    context.data[EditState].active_graph_path = None
    modal = MagicMock()
    monkeypatch.setattr(haystack_editor_module, "rename_modal", modal)
    return editor, context, haystack, modal


@pytest.mark.parametrize("tier", [AccessTier.VIEW, AccessTier.OPERATE])
def test_haystack_save_refused_below_edit(tier, monkeypatch):
    editor, context, haystack, modal = _haystack_header_setup(tier, monkeypatch)
    editor._on_save_haystack_in_place(context)
    editor._on_save_haystack(context)
    haystack.save_haystack.assert_not_called()
    modal.assert_not_called()
    assert haystack_editor_module.ui.notify.call_count == 2  # type: ignore[attr-defined]


def test_haystack_save_allowed_for_edit(monkeypatch):
    editor, context, haystack, modal = _haystack_header_setup(AccessTier.EDIT, monkeypatch)
    editor._on_save_haystack_in_place(context)
    haystack.save_haystack.assert_called_once_with("hs1", active_path=None)
    editor._on_save_haystack(context)
    modal.assert_called_once()


def _noop_page() -> None:  # registration target for a headless Client
    pass


@pytest.mark.parametrize(("tier", "enabled"), [(AccessTier.OPERATE, False), (AccessTier.EDIT, True)])
def test_haystack_save_controls_draw_disabled_below_edit(tier, enabled, monkeypatch):
    from nicegui import Client, ui

    editor, context, _haystack, _modal = _haystack_header_setup(tier, monkeypatch)
    client = Client(cast(Any, _noop_page), request=None)
    with client:
        with ui.column():
            editor._render_header(context)

    save_icons = [
        el for el in client.elements.values() if isinstance(el, ui.button) and el.props.get("icon") == "save"
    ]
    save_as = [
        el
        for el in client.elements.values()
        if isinstance(el, ui.menu_item)
        and any(getattr(child, "text", None) == "Save As…" for child in el.descendants())
    ]
    assert len(save_icons) == 1
    assert len(save_as) == 1
    assert save_icons[0].enabled is enabled
    assert save_as[0].enabled is enabled


def test_save_allowed_for_edit(monkeypatch):
    editor, context, haystack, dialog = _setup(AccessTier.EDIT, monkeypatch)
    editor._on_entry_save("id", context)
    haystack.save_graph.assert_called_once()

    editor._on_entry_save_as("id", context)
    dialog.assert_called_once()
    save_fn = dialog.call_args.kwargs["save_fn"]
    save_fn(Path("/tmp/b.haywire"))
    assert haystack.save_graph.call_count == 2
