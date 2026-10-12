"""HaystackEditor Save and Save-as need the principal's real edit tier."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from typing import Any, cast
from unittest.mock import MagicMock

import pytest

from haybale_haystack.editors import haystack_editor as haystack_editor_module
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


def test_save_allowed_for_edit(monkeypatch):
    editor, context, haystack, dialog = _setup(AccessTier.EDIT, monkeypatch)
    editor._on_entry_save("id", context)
    haystack.save_graph.assert_called_once()

    editor._on_entry_save_as("id", context)
    dialog.assert_called_once()
    save_fn = dialog.call_args.kwargs["save_fn"]
    save_fn(Path("/tmp/b.haywire"))
    assert haystack.save_graph.call_count == 2
