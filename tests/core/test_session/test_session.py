"""Tests for Session core wiring (post-elevation).

Replaces tests/ui/test_session.py. Verifies that Session has no
AppShell back-reference. Per Q7A (shell-upstream model), AppShell
teardown is driven by studio.app.on_disconnect — Session itself
only manages its own bus subscriptions.
"""

from unittest.mock import MagicMock


from haywire.core.session.session import Session
from haywire.core.signals import SelectionMoved


def _make_session(dispatcher=None):
    return Session(
        app_state=MagicMock(),
        workspace_manager=MagicMock(),
        dispatcher=dispatcher or MagicMock(),
    )


def test_session_stores_dispatcher():
    dispatcher = MagicMock()
    session = _make_session(dispatcher=dispatcher)
    assert session._dispatcher is dispatcher


def test_session_is_a_signal_peer():
    """Bus mechanics are inherited, not reimplemented on Session."""
    from haywire.core.signals import SignalPeer

    assert issubclass(Session, SignalPeer)


def test_session_id_aliases_peer_id():
    """One identity under two names — they must never diverge."""
    session = _make_session()
    assert session.session_id == session.peer_id


def test_session_registers_itself_with_the_dispatcher():
    from haywire.core.signals import SignalDispatcher

    dispatcher = SignalDispatcher()
    session = _make_session(dispatcher=dispatcher)

    assert dispatcher.peers[session.session_id] is session


def test_session_cleanup_unregisters_from_the_dispatcher():
    from haywire.core.signals import SignalDispatcher

    dispatcher = SignalDispatcher()
    session = _make_session(dispatcher=dispatcher)

    session.cleanup()

    assert dispatcher.peer_count == 0


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
