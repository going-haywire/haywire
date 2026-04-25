"""Tests for FileViewerEditor.on_focus — editor-owned active_file mutation."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

from haywire.ui.context_events import ContextChangeType
from haybale_studio.editors.file_viewer import FileViewerEditor


class _FakeSession:
    def __init__(self) -> None:
        self.notified_events: list = []
        self.context = None

    def notify_context_changed(self, event) -> None:
        self.notified_events.append(event)


def _make_context(existing_active_file=None):
    session = _FakeSession()
    ctx = SimpleNamespace(
        active_file=existing_active_file,
        session=session,
    )
    session.context = ctx
    return ctx


def _make_editor_with_payload(payload) -> FileViewerEditor:
    ed = FileViewerEditor()
    ed.wrapper = SimpleNamespace(editor_key="file_viewer", payload=payload)
    return ed


def test_on_focus_sets_active_file_from_payload() -> None:
    ctx = _make_context()
    ed = _make_editor_with_payload("/tmp/a.txt")

    ed.on_focus(ctx)

    assert ctx.active_file == Path("/tmp/a.txt")


def test_on_focus_fires_file_selected() -> None:
    ctx = _make_context()
    ed = _make_editor_with_payload("/tmp/a.txt")

    ed.on_focus(ctx)

    assert len(ctx.session.notified_events) == 1
    ev = ctx.session.notified_events[0]
    assert ev.change_type == ContextChangeType.FILE_SELECTED
    assert ev.detail == Path("/tmp/a.txt")


def test_on_focus_short_circuits_when_file_unchanged() -> None:
    ctx = _make_context(existing_active_file=Path("/tmp/a.txt"))
    ed = _make_editor_with_payload("/tmp/a.txt")

    ed.on_focus(ctx)

    assert ctx.session.notified_events == []


def test_on_focus_no_binding_is_noop() -> None:
    ctx = _make_context()
    ed = FileViewerEditor()
    ed.wrapper = None

    ed.on_focus(ctx)

    assert ctx.session.notified_events == []
