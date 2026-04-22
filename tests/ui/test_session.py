"""Tests for Session cross-session notifications."""

from unittest.mock import MagicMock

import haywire.core.graph.editor  # noqa: F401 — circular-import guard

from haywire.ui.context_events import ContextChangedEvent, ContextChangeType
from haywire.ui.session import Session


def _make_session(session_manager=None):
    return Session(
        project_state=MagicMock(),
        workspace_manager=MagicMock(),
        session_manager=session_manager or MagicMock(),
    )


def test_session_stores_session_manager():
    sm = MagicMock()
    session = _make_session(session_manager=sm)
    assert session._session_manager is sm


def test_notify_cross_session_delegates_to_session_manager():
    sm = MagicMock()
    session = _make_session(session_manager=sm)
    event = ContextChangedEvent(change_type=ContextChangeType.DATA_MUTATED)

    session.notify_cross_session_context_change(event)

    sm.broadcast.assert_called_once_with(event)


def test_notify_context_changed_stays_local_only():
    """Local notify does NOT go through session_manager."""
    sm = MagicMock()
    session = _make_session(session_manager=sm)
    orchestrator = MagicMock()
    session.set_orchestrator(orchestrator)

    event = ContextChangedEvent(change_type=ContextChangeType.SELECTION_CHANGED)
    session.notify_context_changed(event)

    orchestrator.assert_called_once_with(event, session.context)
    sm.broadcast.assert_not_called()
