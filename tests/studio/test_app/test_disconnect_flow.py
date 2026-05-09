"""Test the shell-upstream disconnect flow.

Per Q7A in the design discussion: studio.app owns a shells dict
keyed by session_id. on_disconnect calls shell.cleanup() FIRST,
then sm.remove_session(sid). Session.cleanup() never reaches into
AppShell (it has no _shell field anymore — see PR1 Task 6).
"""

from unittest.mock import MagicMock, call
import pytest


@pytest.fixture
def app_under_test():
    """Construct a minimal HaywireApp-like object for disconnect testing.

    Avoids HaywireApp.__init__ (which boots the library system); we only
    need the disconnect-flow attributes.
    """
    from haywire_studio.app import HaywireApp

    app = HaywireApp.__new__(HaywireApp)
    app._is_shutting_down = False
    app._shells = {}
    app.session_manager = MagicMock()
    return app


def test_disconnect_calls_shell_cleanup_then_remove_session(app_under_test):
    """Verify the shell-upstream order: shell.cleanup() BEFORE sm.remove_session()."""
    sid = "abc12345"
    # Wire shell and session_manager to a shared parent so we can assert
    # the call sequence across both mocks.
    parent = MagicMock()
    shell = parent.shell
    app_under_test._shells[sid] = shell
    app_under_test.session_manager = parent.session_manager

    client = MagicMock()
    client._haywire_session_id = sid
    app_under_test.on_disconnect(client)

    # Shell cleanup MUST run before SessionManager removes the session.
    parent.assert_has_calls(
        [
            call.shell.cleanup(),
            call.session_manager.remove_session(sid),
        ]
    )
    # And the shell entry is gone from the dict.
    assert sid not in app_under_test._shells


def test_disconnect_with_no_shell_still_removes_session(app_under_test):
    """If there's no shell (race or buggy state), still detach the session."""
    sid = "noshell0"
    client = MagicMock()
    client._haywire_session_id = sid
    app_under_test.on_disconnect(client)

    app_under_test.session_manager.remove_session.assert_called_once_with(sid)


def test_disconnect_without_session_id_is_noop(app_under_test):
    """A client with no _haywire_session_id (e.g. failed handshake) is skipped."""
    client = MagicMock()
    client._haywire_session_id = None
    app_under_test.on_disconnect(client)

    app_under_test.session_manager.remove_session.assert_not_called()


def test_disconnect_during_shutdown_skips(app_under_test):
    app_under_test._is_shutting_down = True
    sid = "shutdown"
    shell = MagicMock()
    app_under_test._shells[sid] = shell

    client = MagicMock()
    client._haywire_session_id = sid
    app_under_test.on_disconnect(client)

    shell.cleanup.assert_not_called()
    app_under_test.session_manager.remove_session.assert_not_called()
