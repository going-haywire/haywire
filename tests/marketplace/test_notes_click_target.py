"""LibraryOverviewEditor._notes_click_target — local-first Notes resolution.

Pure decision logic: whether a "Notes" link should point at the local file
(installed, editable via CodeEditor) versus fall back to
collect_overview_links's remote resolution (not installed, or nothing
declared). See docs/reference/files/haybale-toml.md and
barn/haybale-marketplace/haybale_marketplace/editors/library_overview_editor.py.
"""

from __future__ import annotations

import pytest
from unittest.mock import Mock

from haywire.core.library.haybale import Haybale
from haywire.core.library.identity import LibraryIdentity
from haywire.core.library.info import LibraryInfo
from haywire.core.library.install_type import InstallType
from haywire.ui import elements as hui


def _make_context():
    """Create a minimal mock SessionContext for testing."""
    return Mock()


def _installed(tmp_path, **row_kwargs) -> LibraryInfo:
    folder = tmp_path / "barn" / "haybale-x" / "haybale_x"
    folder.mkdir(parents=True, exist_ok=True)
    row = Haybale(name="haybale-x", version="1.0.0", **row_kwargs)
    return LibraryInfo(
        row=row,
        identity=LibraryIdentity(name="x", label="Ex", version="1.0.0", folder_path=str(folder)),
        enabled=True,
        install_type=InstallType.REGULAR,
    )


@pytest.mark.unit
def test_none_when_not_installed():
    from haybale_marketplace.editors.library_overview_editor import LibraryOverviewEditor

    editor = LibraryOverviewEditor(wrapper=None)  # type: ignore[arg-type]
    row = Haybale(name="haybale-x", version="1.0.0", notes="notes.md")
    context = _make_context()

    assert editor._notes_click_target(None, row, context=context) is None


@pytest.mark.unit
def test_none_when_notes_not_declared(tmp_path):
    from haybale_marketplace.editors.library_overview_editor import LibraryOverviewEditor

    editor = LibraryOverviewEditor(wrapper=None)  # type: ignore[arg-type]
    info = _installed(tmp_path)
    assert not info.row.notes
    context = _make_context()

    assert editor._notes_click_target(info, info.row, context=context) is None


@pytest.mark.unit
def test_installed_with_notes_yields_a_click_target_and_edit_icon(tmp_path):
    from haybale_marketplace.editors.library_overview_editor import LibraryOverviewEditor

    editor = LibraryOverviewEditor(wrapper=None)  # type: ignore[arg-type]
    info = _installed(tmp_path, notes="notes.md")
    context = _make_context()

    result = editor._notes_click_target(info, info.row, context=context)

    assert result is not None
    click, icon = result
    assert callable(click)
    assert icon == hui.icon.edit_document


@pytest.mark.unit
def test_click_target_opens_the_file_even_when_it_does_not_exist_yet(tmp_path, monkeypatch):
    """CodeEditor creates the file on Save — the link must not require the
    file to already exist."""
    from haybale_marketplace.editors.library_overview_editor import LibraryOverviewEditor

    editor = LibraryOverviewEditor(wrapper=None)  # type: ignore[arg-type]
    info = _installed(tmp_path, notes="notes.md")
    notes_path = tmp_path / "barn" / "haybale-x" / "haybale_x" / "notes.md"
    assert not notes_path.exists()
    context = _make_context()

    seen: dict = {}

    def _fake_open_file_in_studio(filepath, line_number, ctx):
        seen["filepath"] = filepath
        seen["line_number"] = line_number
        seen["context"] = ctx

    monkeypatch.setattr(
        "haybale_studio.editors.error_navigation.open_file_in_studio",
        _fake_open_file_in_studio,
    )

    result = editor._notes_click_target(info, info.row, context=context)
    assert result is not None
    click, _icon = result
    click()

    assert seen == {"filepath": str(notes_path), "line_number": None, "context": context}
