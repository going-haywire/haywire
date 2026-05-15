"""FileBrowserState — per-session, holds transient right-clicked file."""

from pathlib import Path

import haywire.core.graph.editor  # noqa: F401 — circular-import guard

from tests.conftest import attach_stub_session


def test_file_browser_state_starts_empty():
    from haybale_studio.state.file_browser_state import FileBrowserState

    state = FileBrowserState()
    assert state.right_clicked_file is None


def test_right_clicked_file_can_be_set_and_cleared():
    from haybale_studio.state.file_browser_state import FileBrowserState

    state = attach_stub_session(FileBrowserState())
    p = Path("/tmp/foo.haywire")
    state.right_clicked_file = p
    assert state.right_clicked_file == p
    state.right_clicked_file = None
    assert state.right_clicked_file is None


def test_state_class_is_a_session_state():
    from haybale_studio.state.file_browser_state import FileBrowserState
    from haywire.core.state.base import SessionState

    assert issubclass(FileBrowserState, SessionState)
