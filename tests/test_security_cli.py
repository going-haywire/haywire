"""haywire security status — the joined view of exposure, auth and TLS.

The assertions here are about *combinations*, because that is the only thing
this command adds over the two single-axis commands it composes. The two that
matter most: loopback must produce no findings at all (a report that cries wolf
on a correct setup is worse than no report), and auth-on-with-TLS-off must read
as critical rather than as a mild TLS remark.
"""

import argparse
import json

import pytest

from haywire.core.access import AccessTier
from haywire_studio.auth.operations import add_user, enable_auth
from haywire_studio.cli import authcmd, securitycmd
from haywire_studio.network.names import LocalNames
from haywire_studio.network.security import Severity, assess

pytestmark = pytest.mark.unit

STRONG = "Correct-Horse9"


@pytest.fixture
def env(tmp_path, monkeypatch):
    """Isolate certificates, settings and the roster from the real ~/.haywire.

    Also chdir into an empty workspace: reads are tier-resolved (workspace
    beats global), so without this the *repo's own* ``.haywire/settings.json``
    overrides everything these tests write — which is the bug the tier fix
    addresses, and would silently invert every assertion here.
    """

    class Env:
        directory = tmp_path / "certs"
        settings = tmp_path / "settings.json"
        roster = tmp_path / "auth.json"
        workspace = tmp_path / "workspace"

    Env.workspace.mkdir()
    monkeypatch.chdir(Env.workspace)

    monkeypatch.setattr(
        "haywire_studio.network.tls_operations.local_names",
        lambda: LocalNames(dns=("localhost", "box.local"), ip=("127.0.0.1", "::1", "10.0.0.5")),
    )
    monkeypatch.setattr("haywire_studio.network.tls_operations.primary_address", lambda: "10.0.0.5")
    monkeypatch.setattr("haywire_studio.network.tls_settings.default_path", lambda: Env.settings)
    # `auth status` has no --dir flag (it is not a TLS command), so its own
    # assess() call resolves the certificate directory through the default.
    monkeypatch.setattr("haywire_studio.network.certs.default_dir", lambda: Env.directory)
    monkeypatch.setattr(securitycmd, "_studio_is_running", lambda: False)
    return Env


def _expose(env, on=True, **extra):
    """Write the network namespace the way the settings store does.

    Defaults ``allowed_remote_ranges`` to a real subnet: an empty allowlist
    rejects every remote peer, so ``expose_to_network`` alone does NOT make the
    studio reachable. Tests that want the closed-allowlist case pass
    ``allowed_remote_ranges=""`` explicitly.
    """
    data = json.loads(env.settings.read_text(encoding="utf-8")) if env.settings.exists() else {}
    namespace = data.setdefault("network", {})
    namespace["expose_to_network"] = {"value": on}
    extra.setdefault("allowed_remote_ranges", "10.0.0.0/24")
    for key, value in extra.items():
        namespace[key] = {"value": value}
    env.settings.write_text(json.dumps(data), encoding="utf-8")


def _auth_on(env):
    add_user("alice", STRONG, AccessTier.ADMIN, path=env.roster)
    enable_auth("alice", STRONG, path=env.roster)


def _tls_on(env):
    from haywire_studio.network.tls_operations import setup

    setup(directory=env.directory)


def _run(env, argv=("security", "status")):
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers()
    securitycmd.register(subparsers)
    args = parser.parse_args(list(argv))
    args.dir = str(env.directory)
    args.roster = str(env.roster)
    return args.handler(args)


def _assess(env):
    return assess(directory=env.directory, roster_path=env.roster)


def _headlines(posture):
    return " ".join(f.headline for f in posture.findings)


# ---------------------------------------------------------------------------
# The combination matrix
# ---------------------------------------------------------------------------


def test_loopback_produces_no_findings_at_all(env):
    """Auth off + TLS off on loopback is a correct setup, not a finding.

    Warning here is what teaches users to ignore the command entirely.
    """
    posture = _assess(env)
    assert posture.findings == ()
    assert posture.worst is None


def test_loopback_stays_clean_even_with_everything_off(env):
    _expose(env, on=False)
    posture = _assess(env)
    assert posture.findings == ()


def test_exposed_without_auth_is_critical(env):
    _expose(env)
    posture = _assess(env)
    assert posture.worst is Severity.CRITICAL
    assert "authentication OFF" in _headlines(posture)


def test_exposed_with_auth_but_no_tls_is_critical_not_a_warning(env):
    """The combination neither single-axis command can see: enabling auth
    created a password that now crosses the network in cleartext."""
    _expose(env)
    _auth_on(env)
    posture = _assess(env)

    plain_http = [f for f in posture.findings if "plain HTTP" in f.headline]
    assert len(plain_http) == 1
    assert plain_http[0].severity is Severity.CRITICAL
    assert any("passwords and session cookies" in line for line in plain_http[0].detail)


def test_exposed_without_auth_and_without_tls_warns_about_http_only(env):
    """With no auth there is no password to leak, so the HTTP finding is a
    WARNING — the missing login is the critical one."""
    _expose(env)
    posture = _assess(env)
    plain_http = [f for f in posture.findings if "plain HTTP" in f.headline]
    assert plain_http[0].severity is Severity.WARNING


def test_fully_hardened_exposed_studio_has_no_critical_findings(env):
    _expose(env, allowed_remote_ranges="10.0.0.0/24", trusted_proxies="10.0.0.1/32")
    _auth_on(env)
    _tls_on(env)
    posture = _assess(env)
    assert posture.worst is None
    assert posture.findings == ()


def test_findings_are_ordered_worst_first(env):
    _expose(env)
    posture = _assess(env)
    severities = [f.severity for f in posture.findings]
    assert severities == sorted(
        severities, key=lambda s: {Severity.CRITICAL: 0, Severity.WARNING: 1, Severity.NOTE: 2}[s]
    )
    assert severities[0] is Severity.CRITICAL


# ---------------------------------------------------------------------------
# Settings tiers — workspace beats global
# ---------------------------------------------------------------------------


def _workspace_setting(env, **values):
    """Write the workspace tier, which the studio resolves ahead of global."""
    target = env.workspace / ".haywire"
    target.mkdir(exist_ok=True)
    namespace = {key: {"value": value} for key, value in values.items()}
    (target / "settings.json").write_text(json.dumps({"network": namespace}), encoding="utf-8")


def test_workspace_false_overrides_global_true(env):
    """The reported bug: a globally-exposed machine whose workspace turns
    exposure off was reported as exposed, so the command warned about a
    configuration the studio would never run."""
    _expose(env, on=True)
    _workspace_setting(env, expose_to_network=False)

    posture = _assess(env)
    assert posture.exposed is False
    assert posture.findings == ()


def test_workspace_true_overrides_global_false(env):
    """The dangerous direction — under-reporting must not be possible either."""
    _expose(env, on=False)
    _workspace_setting(env, expose_to_network=True)

    posture = _assess(env)
    assert posture.exposed is True
    assert posture.worst is Severity.CRITICAL


def test_global_applies_when_the_workspace_is_silent(env):
    _expose(env, on=True)
    _workspace_setting(env, allowed_remote_ranges="10.0.0.0/24")

    posture = _assess(env)
    assert posture.exposed is True
    assert posture.allowed_ranges == "10.0.0.0/24"


def test_workspace_tls_paths_win(env):
    """read_tls_paths is tier-resolved too — it had the same single-tier bug."""
    from haywire_studio.network.tls_settings import read_tls_paths

    _expose(env, on=True, ssl_certfile="/global/studio.crt", ssl_keyfile="/global/studio.key")
    _workspace_setting(env, ssl_certfile="/ws/studio.crt", ssl_keyfile="/ws/studio.key")

    assert read_tls_paths() == ("/ws/studio.crt", "/ws/studio.key")


# ---------------------------------------------------------------------------
# Individual axes
# ---------------------------------------------------------------------------


def test_an_empty_allowlist_closes_the_studio_rather_than_opening_it(env):
    """``_is_allowed`` is ``any(ip in net ...)`` over an empty list — always
    False. So exposure + empty ranges is the MOST restrictive combination, not
    the least. This report previously warned the exact opposite."""
    _expose(env, allowed_remote_ranges="")
    posture = _assess(env)

    assert posture.exposed is True
    assert posture.allowlist_open is False
    assert posture.reachable_by_others is False
    # No auth/TLS findings at all: nobody outside this machine can connect.
    assert posture.worst is Severity.NOTE
    assert "allowlist is empty" in _headlines(posture)


def test_a_closed_allowlist_suppresses_the_auth_and_tls_findings(env):
    """Auth off and TLS off are only dangerous if someone can reach you."""
    _expose(env, allowed_remote_ranges="")
    headlines = _headlines(_assess(env))
    assert "authentication OFF" not in headlines
    assert "plain HTTP" not in headlines


def test_a_populated_allowlist_makes_the_studio_reachable(env):
    _expose(env, allowed_remote_ranges="192.168.1.0/24")
    posture = _assess(env)
    assert posture.reachable_by_others is True
    assert "authentication OFF" in _headlines(posture)


def test_findings_name_who_can_actually_connect(env):
    """The user's question: 'only 192.168.0.0/24 is allowed, how am I exposed?'
    The answer must name the allowlist rather than imply everyone."""
    _expose(env, allowed_remote_ranges="192.168.0.0/24, 10.21.136.0/21")
    posture = _assess(env)
    critical = [f for f in posture.findings if "authentication OFF" in f.headline]
    assert "192.168.0.0/24" in " ".join(critical[0].detail)


def test_a_very_broad_allowlist_warns(env):
    """A /8 admits millions of hosts — barely a restriction."""
    _expose(env, allowed_remote_ranges="10.0.0.0/8")
    assert "very broad" in _headlines(_assess(env))


def test_a_narrow_allowlist_is_not_second_guessed(env):
    _expose(env, allowed_remote_ranges="192.168.1.0/24")
    assert "very broad" not in _headlines(_assess(env))


def test_own_address_outside_the_allowlist_is_detected(env):
    """primary_address() is pinned to 10.0.0.5 by the fixture."""
    _expose(env, allowed_remote_ranges="192.168.1.0/24")
    assert _assess(env).covers_own_address() is False

    _expose(env, allowed_remote_ranges="10.0.0.0/24")
    assert _assess(env).covers_own_address() is True


def test_own_address_outside_the_allowlist_is_reported(env, capsys):
    _expose(env, allowed_remote_ranges="192.168.1.0/24")
    _run(env)
    out = capsys.readouterr().out
    assert "outside that list" in out
    assert "neighbours on this subnet are rejected" in out


def test_own_address_outside_the_allowlist_never_claims_lockout(env, capsys):
    """Loopback bypasses the allowlist unconditionally (ip_filter.py), so the
    operator always reaches the studio at 127.0.0.1. Saying otherwise sends
    someone to 'fix' a setting to restore access they never lost."""
    _expose(env, allowed_remote_ranges="192.168.1.0/24")
    _run(env)
    out = capsys.readouterr().out
    assert "cannot reach its own studio" not in out
    assert "localhost still works" in out


def test_plain_http_finding_names_no_secure_context_symptom(env):
    """Neither the clipboard (fixed — execCommand fallback) nor camera/mic
    (never applicable — capture is server-side Python) is a consequence of
    plain HTTP. A finding the user can disprove and one that cannot occur are
    the same kind of mistake: they describe something that does not happen."""
    _expose(env)
    posture = _assess(env)
    plain_http = [f for f in posture.findings if "plain HTTP" in f.headline]
    detail = " ".join(plain_http[0].detail).lower()
    assert "clipboard" not in detail
    assert "camera" not in detail
    assert "unencrypted" in detail


def test_missing_trusted_proxies_is_only_a_note(env):
    """Most exposed studios are not behind a proxy; a WARNING here would be noise."""
    _expose(env)
    posture = _assess(env)
    proxy = [f for f in posture.findings if "trusted proxies" in f.headline]
    assert len(proxy) == 1
    assert proxy[0].severity is Severity.NOTE


def test_auth_on_with_no_admin_warns(env):
    _expose(env)
    add_user("bob", STRONG, AccessTier.EDIT, path=env.roster)
    from haywire_studio.auth.roster import load_roster, save_roster

    roster = load_roster(env.roster)
    roster.enabled = True
    save_roster(roster, env.roster)

    posture = _assess(env)
    assert "no admin" in _headlines(posture)


def test_a_corrupt_roster_is_reported_not_raised(env):
    """This command's job is reporting broken security setups, so failing to
    run because the setup is broken would be exactly backwards."""
    env.roster.write_text("{ not json", encoding="utf-8")
    posture = _assess(env)
    assert posture.roster_error
    assert posture.worst is Severity.CRITICAL
    assert "roster cannot be read" in _headlines(posture)


def test_broken_tls_is_reported_even_on_loopback(env):
    """A studio that will not start is not a reachability question."""
    _expose(env, on=False)
    data = json.loads(env.settings.read_text(encoding="utf-8"))
    data["network"]["ssl_certfile"] = {"value": "/nonexistent/studio.crt"}
    data["network"]["ssl_keyfile"] = {"value": "/nonexistent/studio.key"}
    env.settings.write_text(json.dumps(data), encoding="utf-8")

    posture = _assess(env)
    assert "refuse to start" in _headlines(posture)


def test_broken_tls_does_not_count_as_encryption(env):
    _expose(env)
    _auth_on(env)
    data = json.loads(env.settings.read_text(encoding="utf-8"))
    data["network"]["ssl_certfile"] = {"value": "/nonexistent/studio.crt"}
    data["network"]["ssl_keyfile"] = {"value": "/nonexistent/studio.key"}
    env.settings.write_text(json.dumps(data), encoding="utf-8")

    posture = _assess(env)
    assert posture.tls_on is False


# ---------------------------------------------------------------------------
# Output
# ---------------------------------------------------------------------------


def test_status_exits_zero_in_every_state(env, capsys):
    assert _run(env) == 0
    _expose(env)
    assert _run(env) == 0
    _auth_on(env)
    _tls_on(env)
    assert _run(env) == 0


def test_verdict_line_comes_first(env, capsys):
    """The one-line answer to "am I ok?" must be readable without scrolling."""
    _expose(env)
    _run(env)
    lines = [line for line in capsys.readouterr().out.splitlines() if line.strip()]
    assert "Security status:" in lines[0] or "Security status:" in lines[1]


def test_verdict_says_exposed_when_a_critical_finding_exists(env, capsys):
    _expose(env)
    _run(env)
    assert "EXPOSED" in capsys.readouterr().out


def test_verdict_says_at_risk_for_warnings_only(env, capsys):
    """Exposed, authenticated and encrypted, but the allowlist is a /8 —
    a WARNING-level gap with no CRITICAL alongside it."""
    _expose(env, allowed_remote_ranges="10.0.0.0/8", trusted_proxies="10.0.0.1/32")
    _auth_on(env)
    _tls_on(env)
    _run(env)
    assert "AT RISK" in capsys.readouterr().out


def test_verdict_is_ok_with_a_note_when_only_notes_remain(env, capsys):
    _expose(env, allowed_remote_ranges="10.0.0.0/24")
    _auth_on(env)
    _tls_on(env)
    _run(env)
    out = capsys.readouterr().out
    assert "OK" in out
    assert "AT RISK" not in out
    assert "EXPOSED" not in out


def test_verdict_distinguishes_loopback_from_hardened(env, capsys):
    """Both are clean, for structurally different reasons — a user deciding
    whether to expose the studio needs to know which one they have."""
    _run(env)
    assert "loopback only" in capsys.readouterr().out

    _expose(env, allowed_remote_ranges="10.0.0.0/24", trusted_proxies="10.0.0.1/32")
    _auth_on(env)
    _tls_on(env)
    _run(env)
    assert "exposed and defended" in capsys.readouterr().out


def test_verdict_never_contradicts_the_findings(env, capsys):
    """Keyed on `worst`, so the headline and the list cannot disagree."""
    for setup in (lambda: None, lambda: _expose(env), lambda: _auth_on(env)):
        setup()
        posture = _assess(env)
        verdict = securitycmd._general_assesment(posture)
        if posture.worst is Severity.CRITICAL:
            assert "EXPOSED" in verdict
        elif posture.worst is None:
            assert verdict.startswith("OK")


def test_verdict_reports_unknown_on_a_corrupt_roster(env, capsys):
    env.roster.write_text("{ not json", encoding="utf-8")
    _run(env)
    assert "UNKNOWN" in capsys.readouterr().out


def test_auth_line_is_not_alarming_when_nobody_else_can_connect(env, capsys):
    """ "Everyone is a full operator" reads as a threat; on loopback the set of
    "everyone" is just this machine."""
    _run(env)
    assert "only this machine can connect" in capsys.readouterr().out

    _expose(env, allowed_remote_ranges="192.168.1.0/24")
    _run(env)
    assert "everyone who can reach the studio" in capsys.readouterr().out


def test_output_shows_all_three_axes(env, capsys):
    _run(env)
    out = capsys.readouterr().out
    assert "Network:" in out
    assert "Auth:" in out
    assert "TLS:" in out


def test_loopback_output_says_why_it_is_fine(env, capsys):
    _run(env)
    out = capsys.readouterr().out
    assert "Nothing to fix" in out
    assert "loopback" in out.lower()
    # A user deciding whether to expose needs the two commands named.
    assert "haywire auth enable" in out
    assert "haywire ssl setup" in out


def test_every_finding_names_one_command(env, capsys):
    _expose(env)
    posture = _assess(env)
    assert all(f.fix for f in posture.findings)


def test_output_marks_critical_findings(env, capsys):
    _expose(env)
    _run(env)
    assert "[CRITICAL]" in capsys.readouterr().out


def test_running_studio_note_is_printed(env, capsys, monkeypatch):
    monkeypatch.setattr(securitycmd, "_studio_is_running", lambda: True)
    _run(env)
    out = capsys.readouterr().out
    assert "a studio is running" in out
    assert "values on" in out


def test_status_runs_while_the_studio_runs(env, monkeypatch):
    """Read-only, so never guarded — telling someone to quit the studio to find
    out why it is insecure is backwards."""
    monkeypatch.setattr(securitycmd, "_studio_is_running", lambda: True)
    assert _run(env) == 0


# ---------------------------------------------------------------------------
# auth status carries the warning too
# ---------------------------------------------------------------------------


def _run_auth_status(env, monkeypatch):
    monkeypatch.setattr(authcmd, "_studio_is_running", lambda: False)
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers()
    authcmd.register(subparsers)
    args = parser.parse_args(["auth", "status"])
    args.roster = str(env.roster)
    return args.handler(args)


def test_auth_status_warns_when_exposed_without_auth(env, monkeypatch, capsys):
    """The original ask: a user typing 'auth status' should not need to know
    'security status' exists to learn the studio is wide open."""
    _expose(env)
    assert _run_auth_status(env, monkeypatch) == 0
    out = capsys.readouterr().out
    assert "disabled" in out
    assert "[CRITICAL]" in out
    assert "haywire security status" in out


def test_auth_status_still_warns_when_the_roster_is_corrupt(env, monkeypatch, capsys):
    """A corrupt roster used to `return 1` before the warning ever ran.

    A studio reachable from the network whose authentication is unusable is
    exactly when that warning matters most, so no failure may sit between
    reading the roster and reporting on it.
    """
    _expose(env, allowed_remote_ranges="192.168.1.0/24")
    env.roster.write_text("{ not json", encoding="utf-8")

    assert _run_auth_status(env, monkeypatch) == 1
    out = capsys.readouterr().out
    assert "UNKNOWN" in out
    assert "[CRITICAL]" in out
    assert "reachable at" in out
    assert "haywire security status" in out


def test_auth_status_and_security_status_report_the_same_criticals(env, monkeypatch, capsys):
    """Both read one assessment, so their CRITICAL sets must be identical."""
    _expose(env, allowed_remote_ranges="192.168.1.0/24")
    env.roster.write_text("{ not json", encoding="utf-8")

    posture = _assess(env)
    expected = {f.headline for f in posture.findings if f.severity is Severity.CRITICAL}

    _run_auth_status(env, monkeypatch)
    out = capsys.readouterr().out
    for headline in expected:
        assert headline in out


def test_auth_status_stays_quiet_on_loopback(env, monkeypatch, capsys):
    assert _run_auth_status(env, monkeypatch) == 0
    out = capsys.readouterr().out
    assert "disabled" in out
    assert "CRITICAL" not in out


def test_auth_status_quiet_when_exposed_and_hardened(env, monkeypatch, capsys):
    _expose(env, allowed_remote_ranges="10.0.0.0/24")
    _auth_on(env)
    _tls_on(env)
    assert _run_auth_status(env, monkeypatch) == 0
    assert "CRITICAL" not in capsys.readouterr().out
