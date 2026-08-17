"""``haywire network`` — exposure is a verb with preconditions."""

from __future__ import annotations

import argparse

import pytest

from haywire.core.access import AccessTier

from haywire_studio.cli import networkcmd
from haywire_studio.security.document import (
    NetworkPolicy,
    SecurityDocument,
    load_document,
    save_document,
)
from haywire_studio.security.roster import KIND_USER, Principal, Roster


@pytest.fixture
def path(tmp_path):
    return tmp_path / "security.json"


@pytest.fixture(autouse=True)
def studio_stopped(monkeypatch):
    monkeypatch.setattr(networkcmd, "_studio_is_running", lambda: False)


def _parse(argv, path):
    """Parse, then stamp the document path on.

    Stamped afterwards rather than passed as ``--document`` in *argv*: the flag
    is declared on the parent ``network`` parser, so argparse only accepts it
    *before* the subcommand. Setting the attribute is what ``tests/test_auth_cli.py``
    already does, and it keeps the argv in these tests looking like what a user
    actually types.
    """
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers()
    networkcmd.register(subparsers)
    args = parser.parse_args(argv)
    args.document = str(path)
    return args


def _ready(path, tmp_path):
    cert, key = tmp_path / "c.pem", tmp_path / "k.pem"
    cert.write_text("c")
    key.write_text("k")
    save_document(
        SecurityDocument(
            auth=Roster(
                enabled=True,
                principals=[
                    Principal(name="root", kind=KIND_USER, tier=AccessTier.ADMIN, password_hash="x")
                ],
            ),
            network=NetworkPolicy(tls_certfile=str(cert), tls_keyfile=str(key)),
        ),
        path,
    )


def test_expose_requires_ranges(path):
    with pytest.raises(SystemExit):
        _parse(["network", "expose"], path)


def test_expose_refuses_without_auth(path, capsys):
    save_document(SecurityDocument(), path)
    args = _parse(["network", "expose", "--ranges", "192.168.1.0/24"], path)
    assert args.handler(args) == 1
    assert "haywire auth enable" in capsys.readouterr().out


def test_expose_succeeds_when_ready(path, tmp_path, capsys):
    _ready(path, tmp_path)
    args = _parse(["network", "expose", "--ranges", "192.168.1.0/24"], path)
    assert args.handler(args) == 0
    assert load_document(path).network.exposed is True
    assert "192.168.1.0/24" in capsys.readouterr().out


def test_expose_accepts_a_comma_list(path, tmp_path):
    _ready(path, tmp_path)
    args = _parse(["network", "expose", "--ranges", "192.168.1.0/24,10.0.0.0/16"], path)
    assert args.handler(args) == 0
    assert load_document(path).network.allowed_ranges == ("192.168.1.0/24", "10.0.0.0/16")


def test_seal_turns_exposure_off(path, tmp_path):
    _ready(path, tmp_path)
    expose_args = _parse(["network", "expose", "--ranges", "192.168.1.0/24"], path)
    expose_args.handler(expose_args)
    seal_args = _parse(["network", "seal"], path)
    assert seal_args.handler(seal_args) == 0
    assert load_document(path).network.exposed is False


def test_expose_refuses_while_the_studio_runs(path, tmp_path, monkeypatch, capsys):
    _ready(path, tmp_path)
    monkeypatch.setattr(networkcmd, "_studio_is_running", lambda: True)
    args = _parse(["network", "expose", "--ranges", "192.168.1.0/24"], path)
    assert args.handler(args) == 1
    assert "a studio is running" in capsys.readouterr().out


def test_status_always_exits_zero(path, tmp_path, capsys):
    save_document(SecurityDocument(), path)
    args = _parse(["network", "status"], path)
    args.dir = str(tmp_path / "certs")  # never read the real ~/.haywire/certs
    assert args.handler(args) == 0
    assert "loopback" in capsys.readouterr().out.lower()
