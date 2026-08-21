"""Tests for SessionManager session lifecycle.

Cross-peer fan-out lives on SignalDispatcher, not here — see
``tests/core/test_signals/test_dispatcher_and_peer.py``.
"""

from unittest.mock import MagicMock


from haywire.core.state import LibraryStateContainer, LibraryStateRegistry
from haywire.core.session.session_manager import SessionManager
from haywire.core.signals import SignalDispatcher


def _make_manager() -> SessionManager:
    return SessionManager(
        dispatcher=SignalDispatcher(),
        container=LibraryStateContainer(LibraryStateRegistry()),
    )


def test_session_manager_starts_empty():
    manager = _make_manager()
    assert manager.session_count == 0


def test_create_session_registers_session():
    manager = _make_manager()
    session = manager.create_session(
        app_state=MagicMock(),
        workspace_manager=MagicMock(),
    )
    assert manager.get_session(session.session_id) is session
    assert manager.session_count == 1


def test_remove_session_calls_cleanup_and_drops_it():
    manager = _make_manager()
    session = manager.create_session(
        app_state=MagicMock(),
        workspace_manager=MagicMock(),
    )
    sid = session.session_id

    manager.remove_session(sid)

    assert manager.get_session(sid) is None
    assert manager.session_count == 0


def test_created_session_joins_the_dispatcher_fan_out():
    """SessionManager injects its dispatcher, so every session is a peer."""
    manager = _make_manager()
    session = manager.create_session(
        app_state=MagicMock(),
        workspace_manager=MagicMock(),
    )

    assert manager._dispatcher.peers[session.session_id] is session


def test_remove_session_unregisters_the_peer():
    """Via Session.cleanup(), which is why eviction needs no peer knowledge."""
    manager = _make_manager()
    session = manager.create_session(
        app_state=MagicMock(),
        workspace_manager=MagicMock(),
    )

    manager.remove_session(session.session_id)

    assert manager._dispatcher.peer_count == 0
