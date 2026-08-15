"""haywire auth — enable/disable/status, each gated on a working admin login."""

import argparse

import pytest

from haywire.core.access import AccessTier
from haywire_studio.auth.operations import add_user, enable_auth
from haywire_studio.auth.roster import load_roster
from haywire_studio.cli import authcmd

STRONG = "Correct-Horse9"


def _run(argv, monkeypatch, path, username=None, password=None):
    if username is not None:
        monkeypatch.setattr(authcmd, "_prompt_username", lambda: username)
    if password is not None:
        monkeypatch.setattr(authcmd, "_prompt_password", lambda: password)
    monkeypatch.setattr(authcmd, "_studio_is_running", lambda: False)
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers()
    authcmd.register(subparsers)
    args = parser.parse_args(argv)
    args.roster = str(path)
    return args.handler(args)


@pytest.fixture
def path(tmp_path):
    return tmp_path / "auth.json"


def test_enable_with_valid_admin_credentials(monkeypatch, path):
    add_user("alice", STRONG, AccessTier.ADMIN, path=path)
    assert _run(["auth", "enable"], monkeypatch, path, "alice", STRONG) == 0
    assert load_roster(path).enabled is True


def test_enable_with_wrong_password_exits_1_and_does_not_enable(monkeypatch, path):
    add_user("alice", STRONG, AccessTier.ADMIN, path=path)
    assert _run(["auth", "enable"], monkeypatch, path, "alice", "Wrong-Horse9!") == 1
    assert load_roster(path).enabled is False


def test_enable_with_no_admin_exits_1(monkeypatch, path, capsys):
    assert _run(["auth", "enable"], monkeypatch, path, "alice", STRONG) == 1
    assert "haywire user add" in capsys.readouterr().out


def test_disable_requires_credentials(monkeypatch, path):
    add_user("alice", STRONG, AccessTier.ADMIN, path=path)
    enable_auth("alice", STRONG, path=path)
    assert _run(["auth", "disable"], monkeypatch, path, "alice", STRONG) == 0
    assert load_roster(path).enabled is False


def test_status_reports_disabled(monkeypatch, path, capsys):
    assert _run(["auth", "status"], monkeypatch, path) == 0
    assert "disabled" in capsys.readouterr().out


def test_status_reports_enabled_and_admin_count(monkeypatch, path, capsys):
    add_user("alice", STRONG, AccessTier.ADMIN, path=path)
    enable_auth("alice", STRONG, path=path)
    assert _run(["auth", "status"], monkeypatch, path) == 0
    out = capsys.readouterr().out
    assert "enabled" in out
    assert "1 admin" in out


def test_enable_refuses_while_a_studio_is_running(monkeypatch, path):
    add_user("alice", STRONG, AccessTier.ADMIN, path=path)
    monkeypatch.setattr(authcmd, "_prompt_username", lambda: "alice")
    monkeypatch.setattr(authcmd, "_prompt_password", lambda: STRONG)
    monkeypatch.setattr(authcmd, "_studio_is_running", lambda: True)

    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers()
    authcmd.register(subparsers)
    args = parser.parse_args(["auth", "enable"])
    args.roster = str(path)

    assert args.handler(args) == 1
    assert load_roster(path).enabled is False


def test_enable_imports_an_existing_farmhand_token(monkeypatch, path, tmp_path, capsys):
    from haywire_studio.auth.roster import load_roster

    workspace = tmp_path / "proj"
    (workspace / ".haywire").mkdir(parents=True)
    (workspace / ".haywire" / "farmhand_token").write_text("legacy-token-value")

    add_user("alice", STRONG, AccessTier.ADMIN, path=path)
    monkeypatch.chdir(workspace)
    monkeypatch.setattr(authcmd, "_confirm", lambda prompt: True)

    assert _run(["auth", "enable"], monkeypatch, path, "alice", STRONG) == 0

    imported = load_roster(path).find_by_token("legacy-token-value")
    assert imported is not None
    assert imported.is_agent
    assert imported.tier is AccessTier.EDIT
    assert imported.workspace == str(workspace.resolve())


def test_enable_skips_the_import_when_declined(monkeypatch, path, tmp_path):
    from haywire_studio.auth.roster import load_roster

    workspace = tmp_path / "proj"
    (workspace / ".haywire").mkdir(parents=True)
    (workspace / ".haywire" / "farmhand_token").write_text("legacy-token-value")

    add_user("alice", STRONG, AccessTier.ADMIN, path=path)
    monkeypatch.chdir(workspace)
    monkeypatch.setattr(authcmd, "_confirm", lambda prompt: False)

    assert _run(["auth", "enable"], monkeypatch, path, "alice", STRONG) == 0
    assert load_roster(path).find_by_token("legacy-token-value") is None


def test_enable_without_a_farmhand_token_asks_nothing(monkeypatch, path, tmp_path):
    add_user("alice", STRONG, AccessTier.ADMIN, path=path)
    monkeypatch.chdir(tmp_path)

    def _should_not_be_called(prompt):
        raise AssertionError("no token to import — must not prompt")

    monkeypatch.setattr(authcmd, "_confirm", _should_not_be_called)
    assert _run(["auth", "enable"], monkeypatch, path, "alice", STRONG) == 0
