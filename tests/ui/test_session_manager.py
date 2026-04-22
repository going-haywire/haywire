"""Tests for SessionManager broadcast and session injection."""

from unittest.mock import MagicMock

import haywire.core.graph.editor  # noqa: F401 — circular-import guard

from haywire.ui.context_events import ContextChangedEvent, ContextChangeType
from haywire.ui.session_manager import SessionManager


def test_broadcast_fans_event_to_every_session():
    """broadcast() calls notify_context_changed on every registered session."""
    manager = SessionManager()
    s1 = MagicMock()
    s1.session_id = "s1"
    s2 = MagicMock()
    s2.session_id = "s2"
    manager._sessions = {"s1": s1, "s2": s2}

    event = ContextChangedEvent(change_type=ContextChangeType.DATA_MUTATED)
    manager.broadcast(event)

    s1.notify_context_changed.assert_called_once_with(event)
    s2.notify_context_changed.assert_called_once_with(event)


def test_broadcast_swallows_session_errors_and_continues():
    """If one session raises, broadcast still reaches the others."""
    manager = SessionManager()
    good = MagicMock()
    good.session_id = "good"
    bad = MagicMock()
    bad.session_id = "bad"
    bad.notify_context_changed.side_effect = RuntimeError("boom")
    manager._sessions = {"bad": bad, "good": good}

    event = ContextChangedEvent(change_type=ContextChangeType.DATA_MUTATED)
    manager.broadcast(event)  # must not raise

    bad.notify_context_changed.assert_called_once_with(event)
    good.notify_context_changed.assert_called_once_with(event)
