"""Tests for Session core wiring (post-elevation).

Replaces tests/ui/test_session.py. Verifies that Session has no
AppShell back-reference. Per Q7A (shell-upstream model), AppShell
teardown is driven by studio.app.on_disconnect — Session itself
only manages its own callback slots.
"""

from unittest.mock import MagicMock

import haywire.core.graph.editor  # noqa: F401 — circular-import guard

from haywire.core.session.session import Session


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


def test_session_has_no_shell_attr():
    """The _shell back-reference and set_shell() are gone."""
    session = _make_session()
    assert not hasattr(session, "_shell")
    assert not hasattr(session, "set_shell")


def test_session_cleanup_clears_callback_slots():
    """After cleanup, the signal/lifecycle callbacks are cleared."""
    session = _make_session()
    session.set_signal_orchestrator(MagicMock())
    session.set_lifecycle_orchestrator(MagicMock())
    session.cleanup()
    assert session._signal_callback is None
    assert session._lifecycle_callback is None


def test_session_cleanup_is_idempotent():
    """Repeated cleanup() calls are safe."""
    session = _make_session()
    session.cleanup()
    session.cleanup()  # should not raise
