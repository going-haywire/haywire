"""Tests for Session core wiring.

Signal/reveal routing, cross-session broadcast, and ordering are
covered by ``tests/ui/test_context_signals.py``.
"""

from unittest.mock import MagicMock

import haywire.core.graph.editor  # noqa: F401 — circular-import guard

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
