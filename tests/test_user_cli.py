"""haywire user — add/remove/list/passwd against an explicit roster path."""

import argparse

import pytest

from haywire.core.access import AccessTier
from haywire_studio.auth.operations import add_user
from haywire_studio.auth.roster import load_roster
from haywire_studio.cli import user as user_cli

STRONG = "Correct-Horse9"


def _run(argv, monkeypatch, path, answers=None):
    """Parse argv through the real parser and run the handler."""
    if answers is not None:
        queue = list(answers)
        monkeypatch.setattr(user_cli, "_prompt_password", lambda *a, **k: queue.pop(0))
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers()
    user_cli.register(subparsers)
    args = parser.parse_args(argv)
    args.roster = str(path)
    return args.handler(args)


@pytest.fixture
def path(tmp_path):
    return tmp_path / "auth.json"


def test_add_user_creates_the_principal(monkeypatch, path, capsys):
    code = _run(["user", "add", "alice", "--tier", "admin"], monkeypatch, path, answers=[STRONG])
    assert code == 0
    found = load_roster(path).find("alice")
    assert found is not None
    assert found.tier is AccessTier.ADMIN


def test_add_user_defaults_to_view_tier(monkeypatch, path):
    _run(["user", "add", "bob"], monkeypatch, path, answers=[STRONG])
    found = load_roster(path).find("bob")
    assert found is not None
    assert found.tier is AccessTier.VIEW


def test_add_user_rejects_weak_password_with_exit_1(monkeypatch, path, capsys):
    code = _run(["user", "add", "alice"], monkeypatch, path, answers=["weak"])
    assert code == 1
    assert load_roster(path).find("alice") is None
    assert "12" in capsys.readouterr().out


def test_add_agent_prints_the_token(monkeypatch, path, capsys):
    code = _run(["user", "add", "builder", "--agent", "--tier", "edit"], monkeypatch, path)
    assert code == 0
    agent = load_roster(path).find("builder")
    assert agent is not None
    assert agent.is_agent
    assert agent.token in capsys.readouterr().out


def test_remove_user(monkeypatch, path):
    add_user("bob", STRONG, AccessTier.VIEW, path=path)
    assert _run(["user", "remove", "bob"], monkeypatch, path) == 0
    assert load_roster(path).find("bob") is None


def test_remove_unknown_user_exits_1(monkeypatch, path):
    assert _run(["user", "remove", "ghost"], monkeypatch, path) == 1


def test_list_shows_names_and_tiers(monkeypatch, path, capsys):
    add_user("alice", STRONG, AccessTier.ADMIN, path=path)
    assert _run(["user", "list"], monkeypatch, path) == 0
    out = capsys.readouterr().out
    assert "alice" in out
    assert "admin" in out


def test_list_never_prints_a_password_hash(monkeypatch, path, capsys):
    add_user("alice", STRONG, AccessTier.ADMIN, path=path)
    _run(["user", "list"], monkeypatch, path)
    assert "scrypt$" not in capsys.readouterr().out


def test_passwd_changes_the_password(monkeypatch, path):
    add_user("alice", STRONG, AccessTier.ADMIN, path=path)
    new = "Battery-Staple7"
    assert _run(["user", "passwd", "alice"], monkeypatch, path, answers=[new]) == 0

    from haywire_studio.auth.operations import authenticate

    assert authenticate("alice", new, path=path) is not None


def test_tier_change(monkeypatch, path):
    add_user("bob", STRONG, AccessTier.VIEW, path=path)
    assert _run(["user", "tier", "bob", "edit"], monkeypatch, path) == 0
    found = load_roster(path).find("bob")
    assert found is not None
    assert found.tier is AccessTier.EDIT
