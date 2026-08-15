"""Push-based revocation for already-open sockets."""

from unittest.mock import MagicMock

from haywire_studio.auth.eviction import evict_all, evict_principal


def _session(principal):
    session = MagicMock()
    session.context.principal = principal
    return session


def _manager(sessions):
    manager = MagicMock()
    manager.active_sessions = sessions
    return manager


def test_evicts_only_the_named_principals_sessions():
    manager = _manager({"s1": _session("alice"), "s2": _session("bob")})
    assert evict_principal(manager, "alice") == 1
    manager.remove_session.assert_called_once_with("s1")


def test_evicts_every_session_of_one_principal():
    manager = _manager({"s1": _session("alice"), "s2": _session("alice")})
    assert evict_principal(manager, "alice") == 2
    assert manager.remove_session.call_count == 2


def test_unknown_principal_evicts_nothing():
    manager = _manager({"s1": _session("alice")})
    assert evict_principal(manager, "ghost") == 0
    manager.remove_session.assert_not_called()


def test_a_failing_session_does_not_abort_the_others():
    good, bad = _session("alice"), _session("alice")
    manager = _manager({"bad": bad, "good": good})
    manager.remove_session.side_effect = [RuntimeError("boom"), None]
    assert evict_principal(manager, "alice") == 1
    assert manager.remove_session.call_count == 2


def test_evict_all_removes_every_session():
    manager = _manager({"s1": _session("alice"), "s2": _session("bob"), "s3": _session(None)})
    assert evict_all(manager) == 3
