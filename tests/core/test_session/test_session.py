"""Tests for Session core wiring (post-elevation).

Replaces tests/ui/test_session.py. Verifies that Session has no
AppShell back-reference. Per Q7A (shell-upstream model), AppShell
teardown is driven by studio.app.on_disconnect — Session itself
only manages its own bus subscriptions.
"""

from unittest.mock import MagicMock

import haywire.core.graph.editor  # noqa: F401 — circular-import guard

from haywire.core.session.session import Session
from haywire.core.session.events import SelectionMoved


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


def test_session_has_no_legacy_lifecycle_callback_slot():
    """The pre-merge ``_lifecycle_callback`` / ``set_lifecycle_orchestrator``
    surface is gone — AppShell is a normal bus subscriber now."""
    session = _make_session()
    assert not hasattr(session, "_lifecycle_callback")
    assert not hasattr(session, "set_lifecycle_orchestrator")
    assert not hasattr(session, "lifecycle")


def test_session_cleanup_clears_bus():
    """After cleanup, the bus is empty."""
    session = _make_session()
    session.subscribe(SelectionMoved, MagicMock())
    session.cleanup()
    assert session._bus.subscribed_types() == ()


def test_session_cleanup_is_idempotent():
    """Repeated cleanup() calls are safe."""
    session = _make_session()
    session.cleanup()
    session.cleanup()  # should not raise
