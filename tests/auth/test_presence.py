"""Presence — browser sessions from SessionManager, agents from the gate's last_seen."""

from unittest.mock import MagicMock

import pytest

from haywire.core.access import AccessTier
from haywire_studio.auth.live import RosterCache
from haywire_studio.auth.operations import add_agent, add_user, enable_auth
from haywire_studio.auth.presence import collect_presence

STRONG = "Correct-Horse9"


@pytest.fixture
def path(tmp_path):
    target = tmp_path / "auth.json"
    add_user("alice", STRONG, AccessTier.ADMIN, path=target)
    enable_auth("alice", STRONG, path=target)
    return target


def _manager(principals):
    sessions = {}
    for index, name in enumerate(principals):
        session = MagicMock()
        session.context.principal = name
        sessions[f"s{index}"] = session
    manager = MagicMock()
    manager.active_sessions = sessions
    return manager


def test_connected_user_appears(path):
    entries = collect_presence(_manager(["alice"]), RosterCache(path))
    assert [e.name for e in entries] == ["alice"]
    assert entries[0].kind == "user"
    assert entries[0].tier is AccessTier.ADMIN


def test_two_tabs_of_one_user_collapse_to_one_entry_with_a_count(path):
    entries = collect_presence(_manager(["alice", "alice"]), RosterCache(path))
    assert len(entries) == 1
    assert entries[0].sessions == 2


def test_disconnected_user_is_absent(path):
    assert collect_presence(_manager([]), RosterCache(path)) == []


def test_recently_seen_agent_appears(path, monkeypatch):
    import time

    add_agent("builder", AccessTier.EDIT, path=path)
    from haywire_studio.auth import gate

    gate.last_seen().clear()
    gate.last_seen()["builder"] = time.monotonic()

    entries = collect_presence(_manager([]), RosterCache(path))
    assert [e.name for e in entries] == ["builder"]
    assert entries[0].kind == "agent"


def test_long_idle_agent_drops_out(path):
    import time

    add_agent("builder", AccessTier.EDIT, path=path)
    from haywire_studio.auth import gate

    gate.last_seen().clear()
    gate.last_seen()["builder"] = time.monotonic() - 10_000

    assert collect_presence(_manager([]), RosterCache(path)) == []


def test_agent_last_seen_seconds_is_reported(path):
    import time

    add_agent("builder", AccessTier.EDIT, path=path)
    from haywire_studio.auth import gate

    gate.last_seen().clear()
    gate.last_seen()["builder"] = time.monotonic() - 42

    entry = collect_presence(_manager([]), RosterCache(path))[0]
    assert 40 <= entry.last_seen_seconds <= 60


def test_users_sort_before_agents(path):
    import time

    add_agent("builder", AccessTier.EDIT, path=path)
    from haywire_studio.auth import gate

    gate.last_seen().clear()
    gate.last_seen()["builder"] = time.monotonic()

    entries = collect_presence(_manager(["alice"]), RosterCache(path))
    assert [e.kind for e in entries] == ["user", "agent"]


def test_presence_changed_is_cross_session():
    from haywire.core.signals import PresenceChanged

    assert PresenceChanged.cross_session is True
