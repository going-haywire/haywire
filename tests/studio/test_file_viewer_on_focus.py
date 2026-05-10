"""Tests for FileViewerEditor.on_focus — editor-owned active_file mutation."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

from haywire.core.session.signals_and_lifecycle import ActiveFileMoved
from haywire.core.session.reactive import Reactive
from haybale_studio.editors.file_viewer import FileViewerEditor


class _FakeSession:
    def __init__(self) -> None:
        self.signals: list = []
        self.context = None

    def signal(self, signal) -> None:
        self.signals.append(signal)


def _make_context(existing_active_file=None):
    session = _FakeSession()
    ctx = SimpleNamespace(
        active_file=Reactive(existing_active_file),
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

    assert ctx.active_file.value == Path("/tmp/a.txt")


def test_on_focus_fires_active_file_moved() -> None:
    ctx = _make_context()
    ed = _make_editor_with_payload("/tmp/a.txt")

    ed.on_focus(ctx)

    assert len(ctx.session.signals) == 1
    assert isinstance(ctx.session.signals[0], ActiveFileMoved)


def test_on_focus_short_circuits_when_file_unchanged() -> None:
    ctx = _make_context(existing_active_file=Path("/tmp/a.txt"))
    ed = _make_editor_with_payload("/tmp/a.txt")

    ed.on_focus(ctx)

    assert ctx.session.signals == []


def test_on_focus_no_binding_is_noop() -> None:
    ctx = _make_context()
    ed = FileViewerEditor()
    ed.wrapper = None

    ed.on_focus(ctx)

    assert ctx.session.signals == []
