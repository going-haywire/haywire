"""haywire ssl — setup / update / status / trust.

The domain rules (certificate generation, TLS status classification) are
pinned in ``tests/studio/test_network/test_tls_operations.py``. This file
covers only what that layer cannot: argparse wiring, exit codes, and the
exact printed wording — this subcommand exists for users who do not
understand TLS, so "does it warn about the browser interstitial" and "does
the loopback case read as a non-problem" are the actual requirements, and
only a test of the CLI's own output can pin them.
"""

from __future__ import annotations

import argparse
import hashlib
import json

import pytest

from haywire_studio.cli import sslcmd
from haywire_studio.network.names import LocalNames
from haywire_studio.security.document import SecurityDocument, load_document, save_document

pytestmark = pytest.mark.unit


@pytest.fixture
def path(tmp_path):
    return tmp_path / "security.json"


@pytest.fixture
def env(tmp_path, monkeypatch):
    """Isolate certificates from the real ~/.haywire and pin this machine's identity."""

    class Env:
        directory = tmp_path / "certs"

    monkeypatch.setattr(
        "haywire_studio.network.tls_operations.local_names",
        lambda: LocalNames(dns=("localhost", "box.local"), ip=("127.0.0.1", "::1", "10.0.0.5")),
    )
    monkeypatch.setattr("haywire_studio.network.tls_operations.primary_address", lambda: "10.0.0.5")
    monkeypatch.setattr(sslcmd, "guard_running_studio", lambda subject: False)
    return Env


def _run(argv, env, path, running=False, monkeypatch=None):
    if running and monkeypatch is not None:
        monkeypatch.setattr(sslcmd, "guard_running_studio", lambda subject: _refuse(subject))
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers()
    sslcmd.register(subparsers)
    args = parser.parse_args(argv)
    args.dir = str(env.directory)
    args.document = str(path)
    return args.handler(args)


def _refuse(subject):
    print(f"ERROR: a studio is running in this workspace. {subject} is read once at startup.")
    return True


def _digest(file_path):
    return hashlib.sha256(file_path.read_bytes()).hexdigest()


# ---------------------------------------------------------------------------
# setup
# ---------------------------------------------------------------------------


def test_setup_creates_files_and_configures_the_document(env, path, capsys):
    assert _run(["ssl", "setup"], env, path) == 0
    assert (env.directory / "studio.crt").exists()
    assert (env.directory / "studio.key").exists()
    assert load_document(path).network.tls_certfile


def test_setup_explains_the_browser_warning(env, path, capsys):
    """A user who meets the interstitial unwarned concludes the command failed."""
    _run(["ssl", "setup"], env, path)
    out = capsys.readouterr().out
    assert "warning" in out.lower()
    assert "haywire ssl trust" in out


def test_setup_names_the_private_key_as_private(env, path, capsys):
    _run(["ssl", "setup"], env, path)
    assert "never share this file" in capsys.readouterr().out


def test_setup_accepts_extra_names(env, path, capsys):
    _run(["ssl", "setup", "--also", "studio.example.com"], env, path)
    assert "studio.example.com" in capsys.readouterr().out


def test_setup_twice_fails_and_points_at_update(env, path, capsys):
    _run(["ssl", "setup"], env, path)
    assert _run(["ssl", "setup"], env, path) == 1
    assert "haywire ssl update" in capsys.readouterr().out


def test_setup_adopts_an_orphan_without_touching_the_certificate(env, path, capsys):
    _run(["ssl", "setup"], env, path)
    cert = env.directory / "studio.crt"
    before = _digest(cert)
    save_document(SecurityDocument(), path)  # clears the document; the cert stays on disk

    assert _run(["ssl", "setup"], env, path) == 0
    assert _digest(cert) == before
    assert "left untouched" in capsys.readouterr().out


def test_setup_refuses_while_the_studio_runs(env, path, capsys, monkeypatch):
    assert _run(["ssl", "setup"], env, path, running=True, monkeypatch=monkeypatch) == 1
    assert "studio is running" in capsys.readouterr().out


# ---------------------------------------------------------------------------
# update
# ---------------------------------------------------------------------------


def test_update_without_a_certificate_points_at_setup(env, path, capsys):
    assert _run(["ssl", "update"], env, path) == 1
    assert "haywire ssl setup" in capsys.readouterr().out


def test_update_warns_that_trust_must_be_redone(env, path, capsys):
    """Trust stores pin the certificate; silence here sends the user back to
    the interstitial believing the command failed."""
    _run(["ssl", "setup"], env, path)
    capsys.readouterr()
    assert _run(["ssl", "update", "--add", "10.9.9.9"], env, path) == 0
    out = capsys.readouterr().out
    assert "haywire ssl trust" in out
    assert "again" in out


def test_update_reuses_the_key(env, path):
    _run(["ssl", "setup"], env, path)
    key = env.directory / "studio.key"
    before = _digest(key)
    _run(["ssl", "update", "--add", "10.9.9.9"], env, path)
    assert _digest(key) == before


def test_update_refresh_succeeds(env, path, capsys):
    _run(["ssl", "setup"], env, path)
    assert _run(["ssl", "update", "--refresh"], env, path) == 0


def test_update_refuses_to_remove_loopback(env, path, capsys):
    _run(["ssl", "setup"], env, path)
    capsys.readouterr()
    assert _run(["ssl", "update", "--remove", "localhost"], env, path) == 1
    assert "localhost" in capsys.readouterr().out


def test_update_refuses_while_the_studio_runs(env, path, capsys, monkeypatch):
    assert _run(["ssl", "update"], env, path, running=True, monkeypatch=monkeypatch) == 1


# ---------------------------------------------------------------------------
# status
# ---------------------------------------------------------------------------


def test_status_loopback_reads_as_a_non_problem(env, path, capsys):
    """OFF_LOOPBACK is a correct configuration. Presenting it as a problem
    trains users to ignore the command (D7)."""
    save_document(SecurityDocument(), path)
    assert _run(["ssl", "status"], env, path) == 0
    out = capsys.readouterr().out
    assert "That is fine for local use" in out
    assert "Fix" not in out


def test_status_exposed_names_only_real_consequences(env, path, capsys, tmp_path):
    """No secure-context symptom belongs here. The clipboard is fixed (the copy
    helper falls back to execCommand) and camera/mic never applied (capture is
    server-side Python). The one true consequence is readable traffic — a
    finding the user can disprove, or that cannot occur, costs credibility."""
    from haywire.core.access import AccessTier

    from haywire_studio.auth.passwords import hash_password
    from haywire_studio.security.operations import expose
    from haywire_studio.security.roster import KIND_USER, Principal, Roster

    save_document(
        SecurityDocument(
            auth=Roster(
                enabled=True,
                principals=[
                    Principal(
                        name="root", kind=KIND_USER, tier=AccessTier.ADMIN, password_hash=hash_password("x")
                    )
                ],
            )
        ),
        path,
    )
    _run(["ssl", "setup"], env, path)
    capsys.readouterr()
    expose(["10.0.0.0/24"], path=path)
    assert _run(["ssl", "status"], env, path) == 0
    out = capsys.readouterr().out.lower()
    assert "clipboard" not in out
    assert "camera" not in out


def test_status_exposed_but_fenced_does_not_warn_about_traffic(env, path, capsys):
    """``network.exposed`` alone does not mean anyone can connect.

    With an empty allowlist every remote peer is rejected, so warning that
    passwords "travel unencrypted on your network" describes traffic that
    cannot happen — the same false positive `security status` avoids. Both
    commands must agree about the same studio.
    """
    path.write_text(
        json.dumps(
            {
                "version": 1,
                "network": {"exposed": True, "allowed_ranges": [], "tls_certfile": "", "tls_keyfile": ""},
            }
        ),
        encoding="utf-8",
    )
    assert _run(["ssl", "status"], env, path) == 0
    out = capsys.readouterr().out
    assert "only loopback can connect" in out
    assert "travel unencrypted" not in out


def test_status_ok_after_setup(env, path, capsys):
    _run(["ssl", "setup"], env, path)
    capsys.readouterr()
    assert _run(["ssl", "status"], env, path) == 0
    assert "TLS is configured." in capsys.readouterr().out


def test_status_not_covered_offers_the_local_alternative(env, path, capsys, monkeypatch):
    _run(["ssl", "setup"], env, path)
    capsys.readouterr()
    monkeypatch.setattr("haywire_studio.network.tls_operations.primary_address", lambda: "192.168.1.77")
    assert _run(["ssl", "status"], env, path) == 0
    out = capsys.readouterr().out
    assert "NOT covered" in out
    assert "haywire ssl update --refresh" in out
    assert "box.local" in out


def test_status_reports_a_missing_file(env, path, capsys):
    _run(["ssl", "setup"], env, path)
    (env.directory / "studio.crt").unlink()
    capsys.readouterr()
    assert _run(["ssl", "status"], env, path) == 0
    assert "missing" in capsys.readouterr().out.lower()


def test_status_exits_zero_in_every_state(env, path, capsys):
    """status reports; it does not judge."""
    assert _run(["ssl", "status"], env, path) == 0
    _run(["ssl", "setup"], env, path)
    assert _run(["ssl", "status"], env, path) == 0
    (env.directory / "studio.crt").write_text("broken", encoding="utf-8")
    assert _run(["ssl", "status"], env, path) == 0


def test_status_runs_while_the_studio_runs(env, path, capsys, monkeypatch):
    """Read-only: asking a user to quit the studio to diagnose HTTPS is backwards."""
    monkeypatch.setattr(sslcmd, "guard_running_studio", lambda subject: _refuse(subject))
    assert _run(["ssl", "status"], env, path) == 0


# ---------------------------------------------------------------------------
# trust
# ---------------------------------------------------------------------------


def test_trust_without_a_certificate_points_at_setup(env, path, capsys):
    assert _run(["ssl", "trust"], env, path) == 1
    assert "haywire ssl setup" in capsys.readouterr().out


def test_trust_prints_a_command_and_the_fingerprint(env, path, capsys):
    _run(["ssl", "setup"], env, path)
    capsys.readouterr()
    assert _run(["ssl", "trust"], env, path) == 0
    out = capsys.readouterr().out
    assert "studio.crt" in out
    assert "Fingerprint" in out


def test_trust_runs_while_the_studio_runs(env, path, monkeypatch):
    _run(["ssl", "setup"], env, path)
    monkeypatch.setattr(sslcmd, "guard_running_studio", lambda subject: _refuse(subject))
    assert _run(["ssl", "trust"], env, path) == 0
