"""Tests for SessionManager session lifecycle.

Cross-session broadcast (``broadcast_signal``) is covered by
``tests/ui/test_signals_and_lifecycle.py``.
"""

from unittest.mock import MagicMock

import haywire.core.graph.editor  # noqa: F401 — circular-import guard

from haywire.core.state import LibraryStateContainer, LibraryStateRegistry
from haywire.core.session.session_manager import SessionManager


def test_session_manager_starts_empty():
    manager = SessionManager(container=LibraryStateContainer(LibraryStateRegistry()))
    assert manager.session_count == 0


def test_create_session_registers_session():
    manager = SessionManager(container=LibraryStateContainer(LibraryStateRegistry()))
    session = manager.create_session(
        project_state=MagicMock(),
        workspace_manager=MagicMock(),
    )
    assert manager.get_session(session.session_id) is session
    assert manager.session_count == 1


def test_remove_session_calls_cleanup_and_drops_it():
    manager = SessionManager(container=LibraryStateContainer(LibraryStateRegistry()))
    session = manager.create_session(
        project_state=MagicMock(),
        workspace_manager=MagicMock(),
    )
    sid = session.session_id

    manager.remove_session(sid)

    assert manager.get_session(sid) is None
    assert manager.session_count == 0
