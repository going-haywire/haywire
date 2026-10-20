"""A page's session ends when NiceGUI discards the page, not when its websocket drops.

studio.app owns a shells dict keyed by session_id. on_client_deleted calls
shell.cleanup() FIRST, then sm.remove_session(sid). Session.cleanup() never
reaches into AppShell.
"""

from unittest.mock import MagicMock, call
import pytest


@pytest.fixture
def app_under_test():
    """Construct a minimal HaywireApp-like object for client-lifecycle testing.

    Avoids HaywireApp.__init__ (which boots the library system); we only
    need the client-lifecycle attributes.
    """
    from haywire_studio.app import HaywireApp

    app = HaywireApp.__new__(HaywireApp)
    app._is_shutting_down = False
    app._shells = {}
    app._client_to_session = {}
    app.session_manager = MagicMock()
    app.signal_dispatcher = MagicMock()
    return app


def test_deletion_calls_shell_cleanup_then_remove_session(app_under_test):
    """Verify the shell-upstream order: shell.cleanup() BEFORE sm.remove_session()."""
    sid = "abc12345"
    # Wire shell and session_manager to a shared parent so we can assert
    # the call sequence across both mocks.
    parent = MagicMock()
    shell = parent.shell
    app_under_test._shells[sid] = shell
    app_under_test.session_manager = parent.session_manager

    client = MagicMock()
    client.id = "client-abc"
    app_under_test._client_to_session[client.id] = sid
    app_under_test.on_client_deleted(client)

    # Shell cleanup MUST run before SessionManager removes the session.
    parent.assert_has_calls(
        [
            call.shell.cleanup(),
            call.session_manager.remove_session(sid),
        ]
    )
    # And the shell entry is gone from the dict.
    assert sid not in app_under_test._shells
    # The client→session mapping is consumed (popped) on deletion.
    assert client.id not in app_under_test._client_to_session


def test_deletion_with_no_shell_still_removes_session(app_under_test):
    """If there's no shell (race or buggy state), still detach the session."""
    sid = "noshell0"
    client = MagicMock()
    client.id = "client-noshell"
    app_under_test._client_to_session[client.id] = sid
    app_under_test.on_client_deleted(client)

    app_under_test.session_manager.remove_session.assert_called_once_with(sid)


def test_deletion_without_session_id_is_noop(app_under_test):
    """A client with no mapping (e.g. failed handshake) is skipped."""
    client = MagicMock()
    client.id = "client-unmapped"
    # _client_to_session doesn't contain this client.id
    app_under_test.on_client_deleted(client)

    app_under_test.session_manager.remove_session.assert_not_called()


def test_deletion_during_shutdown_skips(app_under_test):
    app_under_test._is_shutting_down = True
    sid = "shutdown"
    shell = MagicMock()
    app_under_test._shells[sid] = shell

    client = MagicMock()
    client.id = "client-shutdown"
    app_under_test._client_to_session[client.id] = sid
    app_under_test.on_client_deleted(client)

    shell.cleanup.assert_not_called()
    app_under_test.session_manager.remove_session.assert_not_called()


def test_the_session_is_bound_to_client_deletion(app_under_test):
    """A websocket drop the page reconnects from keeps its session; only deletion ends it."""
    from unittest.mock import patch

    from haywire_studio.app import HaywireApp

    with patch("haywire_studio.app.app") as fake:
        HaywireApp._register_lifecycle(app_under_test)

    fake.on_delete.assert_called_once_with(app_under_test.on_client_deleted)
    fake.on_disconnect.assert_not_called()


def test_deletion_broadcasts_presence(app_under_test):
    from haywire.core.signals import PresenceChanged

    client = MagicMock()
    client.id = "client-presence"
    app_under_test._client_to_session[client.id] = "presence"
    app_under_test.on_client_deleted(client)

    (signal,), _ = app_under_test.signal_dispatcher.broadcast.call_args
    assert isinstance(signal, PresenceChanged)
