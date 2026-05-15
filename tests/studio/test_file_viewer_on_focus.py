"""Tests for FileViewerEditor.on_focus — editor-owned active_file mutation."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock

from haywire.core.session.context import SessionContext
from haybale_studio.editors.file_viewer import FileViewerEditor


def _make_context(existing_active_file=None):
    """Build a real SessionContext with a mock app + a captured-signal session.

    Using a real SessionContext (rather than a SimpleNamespace) exercises
    the signal_field descriptor: writes to ctx.active_file synthesize a
    SessionContext.active_file signal via session.publish.
    """
    ctx = SessionContext(session_id="test", app=MagicMock())

    captured: list = []

    class _Sess:
        def __init__(self, sink: list):
            self._sink = sink

        def publish(self, signal):
            self._sink.append(signal)

        # ``signal`` is the legacy alias for ``publish``.
        signal = publish

    session = _Sess(captured)
    ctx.session = session  # type: ignore[assignment]
    # Expose captured signals on the session for assertions.
    session.signals = captured  # type: ignore[attr-defined]

    if existing_active_file is not None:
        ctx.active_file = existing_active_file
        # Drop the setup-write emit so tests see only emits from on_focus.
        captured.clear()

    return ctx


def _make_editor_with_payload(binding_id) -> FileViewerEditor:
    wrapper = SimpleNamespace(editor_key="file_viewer", _binding_id=binding_id)
    return FileViewerEditor(wrapper)


def test_on_focus_sets_active_file_from_payload() -> None:
    ctx = _make_context()
    ed = _make_editor_with_payload("/tmp/a.txt")

    ed.on_focus(ctx)

    assert ctx.active_file == Path("/tmp/a.txt")


def test_on_focus_fires_active_file_signal() -> None:
    ctx = _make_context()
    ed = _make_editor_with_payload("/tmp/a.txt")

    ed.on_focus(ctx)

    # The signal_field descriptor synthesises a SessionContext.active_file
    # signal on assignment; that's what fires now (the editor no longer
    # calls session.signal(ActiveFileMoved()) manually).
    assert len(ctx.session.signals) == 1
    assert isinstance(ctx.session.signals[0], SessionContext.active_file)


def test_on_focus_short_circuits_when_file_unchanged() -> None:
    ctx = _make_context(existing_active_file=Path("/tmp/a.txt"))
    ed = _make_editor_with_payload("/tmp/a.txt")

    ed.on_focus(ctx)

    assert ctx.session.signals == []


def test_on_focus_no_binding_is_noop() -> None:
    ctx = _make_context()
    ed = _make_editor_with_payload(None)

    ed.on_focus(ctx)

    assert ctx.session.signals == []
