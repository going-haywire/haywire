"""haywire auth — enable/disable/status, each gated on a working admin login."""

import argparse

import pytest

from haywire.core.access import AccessTier
from haywire_studio.auth.operations import add_user, enable_auth
from haywire_studio.cli import authcmd
from haywire_studio.security.document import load_document

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
    args.document = str(path)
    return args.handler(args)


@pytest.fixture
def path(tmp_path):
    return tmp_path / "security.json"


def test_enable_with_valid_admin_credentials(monkeypatch, path):
    add_user("alice", STRONG, AccessTier.ADMIN, path=path)
    assert _run(["auth", "enable"], monkeypatch, path, "alice", STRONG) == 0
    assert load_document(path).auth.enabled is True


def test_enable_with_wrong_password_exits_1_and_does_not_enable(monkeypatch, path):
    add_user("alice", STRONG, AccessTier.ADMIN, path=path)
    assert _run(["auth", "enable"], monkeypatch, path, "alice", "Wrong-Horse9!") == 1
    assert load_document(path).auth.enabled is False


def test_enable_with_no_admin_exits_1(monkeypatch, path, capsys):
    assert _run(["auth", "enable"], monkeypatch, path, "alice", STRONG) == 1
    assert "haywire user add" in capsys.readouterr().out


def test_disable_requires_credentials(monkeypatch, path):
    add_user("alice", STRONG, AccessTier.ADMIN, path=path)
    enable_auth("alice", STRONG, path=path)
    assert _run(["auth", "disable"], monkeypatch, path, "alice", STRONG) == 0
    assert load_document(path).auth.enabled is False


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
    args.document = str(path)

    assert args.handler(args) == 1
    assert load_document(path).auth.enabled is False


def _ready_and_exposed(path, tmp_path):
    """Auth on with an admin, TLS configured, and exposed — the one state in
    which 'auth disable' must be refused."""
    from haywire.core.access import AccessTier

    from haywire_studio.auth.passwords import hash_password
    from haywire_studio.security.document import (
        NetworkPolicy,
        SecurityDocument,
        save_document,
    )
    from haywire_studio.security.operations import expose
    from haywire_studio.security.roster import KIND_USER, Principal, Roster

    cert, key = tmp_path / "c.pem", tmp_path / "k.pem"
    cert.write_text("c")
    key.write_text("k")
    save_document(
        SecurityDocument(
            auth=Roster(
                enabled=True,
                principals=[
                    Principal(
                        name="root",
                        kind=KIND_USER,
                        tier=AccessTier.ADMIN,
                        # STRONG, module-level — the password policy rejects weak ones
                        # and add_user is not on this path to check it for us.
                        password_hash=hash_password(STRONG),
                    )
                ],
            ),
            network=NetworkPolicy(tls_certfile=str(cert), tls_keyfile=str(key)),
        ),
        path,
    )
    expose(["192.168.1.0/24"], path=path)


def test_disable_refuses_while_exposed(path, tmp_path, monkeypatch, capsys):
    """The exposure invariant makes 'disable auth on an exposed studio' unwritable."""
    from haywire_studio.security.document import load_document

    _ready_and_exposed(path, tmp_path)
    assert _run(["auth", "disable"], monkeypatch, path, username="root", password=STRONG) == 1
    assert "haywire network seal" in capsys.readouterr().out
    assert load_document(path).auth.enabled is True
