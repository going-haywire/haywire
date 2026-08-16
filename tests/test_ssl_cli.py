"""haywire ssl — setup / update / status / trust.

The output assertions are not decoration: this subcommand exists for users who
do not understand TLS, so "does it warn about the browser interstitial" and
"does the loopback case read as a non-problem" are the actual requirements.
"""

import argparse
import hashlib
import json

import pytest

from haywire_studio.cli import sslcmd
from haywire_studio.network.names import LocalNames

pytestmark = pytest.mark.unit


@pytest.fixture
def env(tmp_path, monkeypatch):
    """Isolate certificates and settings from the real ~/.haywire."""

    class Env:
        directory = tmp_path / "certs"
        settings = tmp_path / "settings.json"

    # Reads resolve workspace-over-global, so run from an empty workspace: the
    # repo's own .haywire/settings.json would otherwise win over env.settings.
    workspace = tmp_path / "empty_workspace"
    workspace.mkdir()
    monkeypatch.chdir(workspace)

    monkeypatch.setattr(
        "haywire_studio.network.tls_operations.local_names",
        lambda: LocalNames(dns=("localhost", "box.local"), ip=("127.0.0.1", "::1", "10.0.0.5")),
    )
    monkeypatch.setattr("haywire_studio.network.tls_operations.primary_address", lambda: "10.0.0.5")
    # Route the default settings path at the temp file: the operations layer
    # takes an explicit path, but the CLI deliberately does not expose one.
    monkeypatch.setattr("haywire_studio.network.tls_settings.default_path", lambda: Env.settings)
    monkeypatch.setattr(sslcmd, "guard_running_studio", lambda subject: False)
    return Env


def _run(argv, env, running=False, monkeypatch=None):
    if running and monkeypatch is not None:
        monkeypatch.setattr(sslcmd, "guard_running_studio", lambda subject: _refuse(subject))
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers()
    sslcmd.register(subparsers)
    args = parser.parse_args(argv)
    args.dir = str(env.directory)
    return args.handler(args)


def _refuse(subject):
    print(f"ERROR: a studio is running in this workspace. {subject} is read once at startup.")
    return True


def _settings(env):
    return json.loads(env.settings.read_text(encoding="utf-8"))


def _digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


# ---------------------------------------------------------------------------
# setup
# ---------------------------------------------------------------------------


def test_setup_creates_files_and_configures_settings(env, capsys):
    assert _run(["ssl", "setup"], env) == 0
    assert (env.directory / "studio.crt").exists()
    assert (env.directory / "studio.key").exists()
    assert _settings(env)["network"]["ssl_certfile"]["value"]


def test_setup_explains_the_browser_warning(env, capsys):
    """A user who meets the interstitial unwarned concludes the command failed."""
    _run(["ssl", "setup"], env)
    out = capsys.readouterr().out
    assert "warning" in out.lower()
    assert "haywire ssl trust" in out


def test_setup_names_the_private_key_as_private(env, capsys):
    _run(["ssl", "setup"], env)
    assert "never share this file" in capsys.readouterr().out


def test_setup_accepts_extra_names(env, capsys):
    _run(["ssl", "setup", "--also", "studio.example.com"], env)
    assert "studio.example.com" in capsys.readouterr().out


def test_setup_twice_fails_and_points_at_update(env, capsys):
    _run(["ssl", "setup"], env)
    assert _run(["ssl", "setup"], env) == 1
    assert "haywire ssl update" in capsys.readouterr().out


def test_setup_adopts_an_orphan_without_touching_the_certificate(env, capsys):
    _run(["ssl", "setup"], env)
    cert = env.directory / "studio.crt"
    before = _digest(cert)
    env.settings.write_text(json.dumps({"network": {}}), encoding="utf-8")

    assert _run(["ssl", "setup"], env) == 0
    assert _digest(cert) == before
    assert "left untouched" in capsys.readouterr().out


def test_setup_refuses_while_the_studio_runs(env, capsys, monkeypatch):
    assert _run(["ssl", "setup"], env, running=True, monkeypatch=monkeypatch) == 1
    assert "studio is running" in capsys.readouterr().out


# ---------------------------------------------------------------------------
# update
# ---------------------------------------------------------------------------


def test_update_without_a_certificate_points_at_setup(env, capsys):
    assert _run(["ssl", "update"], env) == 1
    assert "haywire ssl setup" in capsys.readouterr().out


def test_update_warns_that_trust_must_be_redone(env, capsys):
    """Trust stores pin the certificate; silence here sends the user back to
    the interstitial believing the command failed."""
    _run(["ssl", "setup"], env)
    capsys.readouterr()
    assert _run(["ssl", "update", "--add", "10.9.9.9"], env) == 0
    out = capsys.readouterr().out
    assert "haywire ssl trust" in out
    assert "again" in out


def test_update_reuses_the_key(env):
    _run(["ssl", "setup"], env)
    key = env.directory / "studio.key"
    before = _digest(key)
    _run(["ssl", "update", "--add", "10.9.9.9"], env)
    assert _digest(key) == before


def test_update_refresh_succeeds(env, capsys):
    _run(["ssl", "setup"], env)
    assert _run(["ssl", "update", "--refresh"], env) == 0


def test_update_refuses_to_remove_loopback(env, capsys):
    _run(["ssl", "setup"], env)
    capsys.readouterr()
    assert _run(["ssl", "update", "--remove", "localhost"], env) == 1
    assert "localhost" in capsys.readouterr().out


def test_update_refuses_while_the_studio_runs(env, capsys, monkeypatch):
    assert _run(["ssl", "update"], env, running=True, monkeypatch=monkeypatch) == 1


# ---------------------------------------------------------------------------
# status
# ---------------------------------------------------------------------------


def test_status_loopback_reads_as_a_non_problem(env, capsys):
    """OFF_LOOPBACK is a correct configuration. Presenting it as a problem
    trains users to ignore the command (D7)."""
    assert _run(["ssl", "status"], env) == 0
    out = capsys.readouterr().out
    assert "That is fine for local use" in out
    assert "Fix" not in out


def test_status_exposed_names_only_real_consequences(env, capsys):
    """No secure-context symptom belongs here. The clipboard is fixed (the copy
    helper falls back to execCommand) and camera/mic never applied (capture is
    server-side Python). The one true consequence is readable traffic — a
    finding the user can disprove, or that cannot occur, costs credibility."""
    env.settings.write_text(
        json.dumps(
            {
                "network": {
                    "expose_to_network": {"value": True},
                    # Required: an empty allowlist rejects every remote peer, so
                    # without ranges nothing crosses the network to warn about.
                    "allowed_remote_ranges": {"value": "10.0.0.0/24"},
                }
            }
        ),
        encoding="utf-8",
    )
    assert _run(["ssl", "status"], env) == 0
    out = capsys.readouterr().out.lower()
    assert "clipboard" not in out
    assert "camera" not in out
    assert "unencrypted" in out
    assert "haywire ssl setup" in out


def test_status_exposed_but_fenced_does_not_warn_about_traffic(env, capsys):
    """`expose_to_network` alone does not mean anyone can connect.

    With an empty allowlist every remote peer is rejected, so warning that
    passwords "travel unencrypted on your network" describes traffic that
    cannot happen — the same false positive `security status` avoids. Both
    commands must agree about the same studio.
    """
    env.settings.write_text(
        json.dumps(
            {
                "network": {
                    "expose_to_network": {"value": True},
                    "allowed_remote_ranges": {"value": ""},
                }
            }
        ),
        encoding="utf-8",
    )
    assert _run(["ssl", "status"], env) == 0
    out = capsys.readouterr().out
    assert "only loopback can connect" in out
    assert "travel unencrypted" not in out


def _shadow_workspace(**values):
    """Set keys in <cwd>/.haywire/settings.json — the tier that wins."""
    from pathlib import Path

    target = Path.cwd() / ".haywire"
    target.mkdir(parents=True, exist_ok=True)
    (target / "settings.json").write_text(
        json.dumps({"network": {k: {"value": v} for k, v in values.items()}}), encoding="utf-8"
    )


def test_setup_warns_when_the_workspace_shadows_what_it_wrote(env, capsys):
    """setup writes the global tier, but workspace wins — without this the
    command reports success and the studio then refuses to start."""
    _shadow_workspace(ssl_certfile="/nonexistent/ws.crt", ssl_keyfile="/nonexistent/ws.key")
    assert _run(["ssl", "setup"], env) == 0
    out = capsys.readouterr().out
    assert "WARNING" in out
    assert "workspace" in out.lower()


def test_setup_is_quiet_when_nothing_shadows_it(env, capsys):
    assert _run(["ssl", "setup"], env) == 0
    assert "WARNING" not in capsys.readouterr().out


def test_file_missing_names_the_workspace_file_when_it_is_the_source(env, capsys):
    """Sending the user to edit ~/.haywire when the workspace tier holds the
    value points them at a setting that was never in force."""
    _shadow_workspace(ssl_certfile="/nonexistent/ws.crt", ssl_keyfile="/nonexistent/ws.key")
    assert _run(["ssl", "status"], env) == 0
    out = capsys.readouterr().out
    assert "workspace settings win" in out
    assert ".haywire/settings.json" in out


def test_status_ok_after_setup(env, capsys):
    _run(["ssl", "setup"], env)
    capsys.readouterr()
    assert _run(["ssl", "status"], env) == 0
    assert "TLS is configured." in capsys.readouterr().out


def test_status_not_covered_offers_the_local_alternative(env, capsys, monkeypatch):
    _run(["ssl", "setup"], env)
    capsys.readouterr()
    monkeypatch.setattr("haywire_studio.network.tls_operations.primary_address", lambda: "192.168.1.77")
    assert _run(["ssl", "status"], env) == 0
    out = capsys.readouterr().out
    assert "NOT covered" in out
    assert "haywire ssl update --refresh" in out
    assert "box.local" in out


def test_status_reports_a_missing_file(env, capsys):
    _run(["ssl", "setup"], env)
    (env.directory / "studio.crt").unlink()
    capsys.readouterr()
    assert _run(["ssl", "status"], env) == 0
    assert "missing" in capsys.readouterr().out.lower()


def test_status_exits_zero_in_every_state(env, capsys):
    """status reports; it does not judge."""
    assert _run(["ssl", "status"], env) == 0
    _run(["ssl", "setup"], env)
    assert _run(["ssl", "status"], env) == 0
    (env.directory / "studio.crt").write_text("broken", encoding="utf-8")
    assert _run(["ssl", "status"], env) == 0


def test_status_runs_while_the_studio_runs(env, capsys, monkeypatch):
    """Read-only: asking a user to quit the studio to diagnose HTTPS is backwards."""
    monkeypatch.setattr(sslcmd, "guard_running_studio", lambda subject: _refuse(subject))
    assert _run(["ssl", "status"], env) == 0


# ---------------------------------------------------------------------------
# trust
# ---------------------------------------------------------------------------


def test_trust_without_a_certificate_points_at_setup(env, capsys):
    assert _run(["ssl", "trust"], env) == 1
    assert "haywire ssl setup" in capsys.readouterr().out


def test_trust_prints_a_command_and_the_fingerprint(env, capsys):
    _run(["ssl", "setup"], env)
    capsys.readouterr()
    assert _run(["ssl", "trust"], env) == 0
    out = capsys.readouterr().out
    assert "studio.crt" in out
    assert "Fingerprint" in out


def test_trust_runs_while_the_studio_runs(env, monkeypatch):
    _run(["ssl", "setup"], env)
    monkeypatch.setattr(sslcmd, "guard_running_studio", lambda subject: _refuse(subject))
    assert _run(["ssl", "trust"], env) == 0
