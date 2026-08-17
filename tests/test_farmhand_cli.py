"""``haywire farmhand`` — the MCP mount's two switches."""

from __future__ import annotations

import argparse

import pytest

from haywire.core.access import AccessTier

from haywire_studio.cli import farmhandcmd
from haywire_studio.security.document import SecurityDocument, load_document, save_document
from haywire_studio.security.roster import KIND_USER, Principal, Roster


@pytest.fixture
def path(tmp_path):
    return tmp_path / "security.json"


@pytest.fixture(autouse=True)
def studio_stopped(monkeypatch):
    monkeypatch.setattr(farmhandcmd, "_studio_is_running", lambda: False)


def _parse(argv, path):
    """Parse, then stamp the document path on.

    Stamped afterwards rather than passed as ``--document`` in *argv*: the flag
    is declared on the parent ``farmhand`` parser, so argparse only accepts it
    *before* the subcommand. Matches ``tests/test_auth_cli.py``.
    """
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers()
    farmhandcmd.register(subparsers)
    args = parser.parse_args(argv)
    args.document = str(path)
    return args


def test_disable_turns_the_mount_off(path):
    save_document(SecurityDocument(), path)
    args = _parse(["farmhand", "disable"], path)
    assert args.handler(args) == 0
    assert load_document(path).farmhand.enabled is False


def test_enable_turns_it_back_on(path):
    save_document(SecurityDocument(), path)
    for verb in ("disable", "enable"):
        args = _parse(["farmhand", verb], path)
        args.handler(args)
    assert load_document(path).farmhand.enabled is True


def test_allow_remote_refuses_without_auth(path, capsys):
    save_document(SecurityDocument(), path)
    args = _parse(["farmhand", "allow-remote"], path)
    assert args.handler(args) == 1
    assert "haywire auth enable" in capsys.readouterr().out


def test_allow_remote_works_with_auth_on(path):
    save_document(
        SecurityDocument(
            auth=Roster(
                enabled=True,
                principals=[
                    Principal(name="root", kind=KIND_USER, tier=AccessTier.ADMIN, password_hash="x")
                ],
            )
        ),
        path,
    )
    args = _parse(["farmhand", "allow-remote"], path)
    assert args.handler(args) == 0
    assert load_document(path).farmhand.restrict_to_loopback is False


def test_local_only_needs_no_auth(path):
    save_document(SecurityDocument(), path)
    args = _parse(["farmhand", "local-only"], path)
    assert args.handler(args) == 0
    assert load_document(path).farmhand.restrict_to_loopback is True


def test_status_reports_both_switches(path, capsys):
    save_document(SecurityDocument(), path)
    args = _parse(["farmhand", "status"], path)
    assert args.handler(args) == 0
    out = capsys.readouterr().out
    assert "/mcp" in out
    assert "loopback" in out.lower()
