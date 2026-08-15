"""The roster document — ~/.haywire/auth.json, one file, atomic writes."""

import json
import stat

import pytest

from haywire.core.access import AccessTier
from haywire_studio.auth.passwords import hash_password
from haywire_studio.auth.roster import (
    Principal,
    Roster,
    RosterError,
    load_roster,
    save_roster,
)


@pytest.fixture
def path(tmp_path):
    return tmp_path / "auth.json"


def test_load_missing_file_returns_disabled_empty_roster(path):
    roster = load_roster(path)
    assert roster.enabled is False
    assert roster.principals == []
    assert roster.session_days == 30


def test_round_trip(path):
    roster = Roster(
        enabled=True,
        session_days=7,
        principals=[
            Principal(
                name="alice", kind="user", tier=AccessTier.ADMIN, password_hash=hash_password("x" * 20)
            ),
            Principal(name="agent1", kind="agent", tier=AccessTier.EDIT, token="tok", workspace="/w"),
        ],
    )
    save_roster(roster, path)
    loaded = load_roster(path)

    assert loaded.enabled is True
    assert loaded.session_days == 7
    assert [p.name for p in loaded.principals] == ["alice", "agent1"]
    found_alice = loaded.find("alice")
    assert found_alice is not None
    assert found_alice.tier is AccessTier.ADMIN
    found_agent = loaded.find("agent1")
    assert found_agent is not None
    assert found_agent.workspace == "/w"


def test_saved_file_is_0600(path):
    save_roster(Roster(), path)
    assert stat.S_IMODE(path.stat().st_mode) == 0o600


def test_saved_file_carries_a_version(path):
    save_roster(Roster(), path)
    assert json.loads(path.read_text())["version"] == 1


def test_unknown_version_refuses_to_load(path):
    path.write_text(json.dumps({"version": 99, "enabled": True, "principals": []}))
    with pytest.raises(RosterError, match="version"):
        load_roster(path)


def test_corrupt_json_refuses_to_load_rather_than_defaulting_open(path):
    path.write_text("{not json")
    with pytest.raises(RosterError):
        load_roster(path)


def test_find_is_exact_not_case_folded(path):
    roster = Roster(principals=[Principal(name="alice", kind="user", tier=AccessTier.VIEW)])
    assert roster.find("alice") is not None
    assert roster.find("Alice") is None
    assert roster.find("bob") is None


def test_find_by_token_ignores_empty_tokens(path):
    roster = Roster(
        principals=[
            Principal(name="alice", kind="user", tier=AccessTier.ADMIN, password_hash="h"),
            Principal(name="agent1", kind="agent", tier=AccessTier.EDIT, token="secret"),
        ]
    )
    found = roster.find_by_token("secret")
    assert found is not None
    assert found.name == "agent1"
    assert roster.find_by_token("") is None


def test_admins_lists_only_admin_tier():
    roster = Roster(
        principals=[
            Principal(name="a", kind="user", tier=AccessTier.ADMIN),
            Principal(name="b", kind="user", tier=AccessTier.EDIT),
            Principal(name="c", kind="agent", tier=AccessTier.ADMIN),
        ]
    )
    assert [p.name for p in roster.admins()] == ["a", "c"]


def test_is_user_and_is_agent():
    user = Principal(name="a", kind="user", tier=AccessTier.VIEW)
    agent = Principal(name="b", kind="agent", tier=AccessTier.VIEW)
    assert (user.is_user, user.is_agent) == (True, False)
    assert (agent.is_user, agent.is_agent) == (False, True)


def test_save_leaves_no_temp_file_behind(path):
    save_roster(Roster(), path)
    assert [p.name for p in path.parent.iterdir()] == ["auth.json"]


def test_save_creates_the_parent_directory(tmp_path):
    nested = tmp_path / "deep" / "auth.json"
    save_roster(Roster(), nested)
    assert nested.exists()


def test_unknown_tier_string_refuses_to_load(path):
    path.write_text(
        json.dumps(
            {
                "version": 1,
                "enabled": True,
                "principals": [{"name": "a", "kind": "user", "tier": "superuser"}],
            }
        )
    )
    with pytest.raises(RosterError):
        load_roster(path)
