"""A Save icon shows only while its document has something to save, as in the haystack editor.

A document that was never saved shows no Save either until it is edited; Save As
stays available. Ctrl+S works whether or not the icon shows. Without edit
access the icon never shows.
"""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from typing import Any
from unittest.mock import MagicMock

import pytest

from haybale_graph_editor.editors.graph_editor import GraphEditor

pytestmark = pytest.mark.unit


def _graph_editor(document: Any) -> Any:
    """A GraphEditor whose header refresh runs against ``document``, everything else stubbed."""
    editor: Any = GraphEditor.__new__(GraphEditor)
    editor._graph_name_label = MagicMock()
    editor._dirty_marker = MagicMock()
    editor._save_button = MagicMock()
    editor._levels = {}
    editor._active_level = None
    editor._document = lambda: document
    editor._resolve_document = lambda context: document
    editor._project_state = SimpleNamespace(workspace_root="/ws")
    for name in (
        "_update_undo_redo_buttons",
        "_update_lock_button",
        "_update_view_switch",
        "_sync_tab_dirty",
        "_update_breadcrumb",
    ):
        setattr(editor, name, MagicMock())
    return editor


@pytest.mark.parametrize("path", [Path("/ws/a.haywire"), None], ids=["saved", "never-saved"])
@pytest.mark.parametrize("unsaved", [False, True])
def test_the_graph_editor_shows_save_only_with_unsaved_edits(path, unsaved):
    editor = _graph_editor(SimpleNamespace(path=path, unsaved=unsaved))

    editor._update_header(SimpleNamespace(can_edit=lambda: True))

    editor._save_button.set_visibility.assert_called_with(unsaved)


def test_the_graph_editor_hides_save_without_edit_access():
    editor = _graph_editor(SimpleNamespace(path=Path("/ws/a.haywire"), unsaved=True))

    editor._update_header(SimpleNamespace(can_edit=lambda: False))

    editor._save_button.set_visibility.assert_called_with(False)


def test_the_code_editor_shows_save_only_with_changes():
    from haybale_studio.editors.code_editor import CodeEditor

    editor: Any = object.__new__(CodeEditor)
    editor.wrapper = MagicMock()
    editor._save_button = MagicMock()
    editor._original = "old"

    editor._content = "old"
    editor._update_save_state()
    editor._save_button.set_visibility.assert_called_with(False)

    editor._content = "new"
    editor._update_save_state()
    editor._save_button.set_visibility.assert_called_with(True)


def _component_source() -> Any:
    from haybale_studio.editors.component_source_editor import ComponentSourceEditor

    editor: Any = object.__new__(ComponentSourceEditor)
    editor._content = editor._original = "old"
    editor._pinned = False
    editor._conflict = False
    editor._pin_banner = None
    editor._conflict_banner = None
    editor._save_button = MagicMock()
    return editor


def test_component_source_shows_save_while_the_text_differs():
    editor = _component_source()

    editor._on_text_changed(SimpleNamespace(value="new"))
    editor._save_button.set_visibility.assert_called_with(True)

    editor._on_text_changed(SimpleNamespace(value="old"))
    editor._save_button.set_visibility.assert_called_with(False)


def test_component_source_hides_save_after_saving(tmp_path, monkeypatch):
    from nicegui import ui

    monkeypatch.setattr(ui, "notify", MagicMock())
    editor = _component_source()
    editor._path = tmp_path / "toggle.py"
    editor._on_text_changed(SimpleNamespace(value="new"))

    editor._save()

    editor._save_button.set_visibility.assert_called_with(False)
