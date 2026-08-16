"""The false negative is the failure mode this command must not have.

Reporting a problem that is not there is a nuisance. Reporting **no problem on
a studio that is wide open** is the one outcome that makes this command worse
than not existing, because it converts "I did not check" into "I checked and it
is fine".

These tests attack that specific failure from four directions:

1. **Every dangerous configuration produces a CRITICAL** — driven from an
   exhaustive product of the inputs rather than hand-picked cases, so a
   combination nobody thought of cannot slip through silently.
2. **No rule can silence another** — each rule is called directly with a
   posture that should trigger it, proving the flat ``RULES`` structure has no
   early exit that skips the rest.
3. **The truth table for reachability is complete** — that value gates most
   rules, so all four combinations are pinned.
4. **The verdict never contradicts the findings** — the headline cannot say OK
   while a CRITICAL sits below it.
"""

import itertools

import pytest

from haywire_studio.network.names import LocalNames
from haywire_studio.network.security import (
    RULES,
    Posture,
    Severity,
    _findings,
    _with_findings,
)
from haywire_studio.network.tls_operations import TlsState, TlsStatus

pytestmark = pytest.mark.unit


def _posture(
    *,
    exposed=True,
    ranges="192.168.0.0/24",
    auth=False,
    admins=1,
    tls_state=TlsState.OFF_EXPOSED,
    roster_error="",
    trusted_proxies="",
) -> Posture:
    tls = TlsStatus(
        state=tls_state,
        certfile="/c" if tls_state not in (TlsState.OFF_EXPOSED, TlsState.OFF_LOOPBACK) else "",
        keyfile="/k" if tls_state not in (TlsState.OFF_EXPOSED, TlsState.OFF_LOOPBACK) else "",
        covered=LocalNames.empty(),
        reachable_at="10.0.0.5",
        exposed=exposed,
        expires=None,
        fingerprint=None,
        detail="detail",
    )
    return _with_findings(
        Posture(
            exposed=exposed,
            reachable_at="10.0.0.5",
            auth_enabled=auth,
            principals=1 if auth else 0,
            admins=admins,
            tls=tls,
            allowed_ranges=ranges,
            trusted_proxies=trusted_proxies,
            findings=(),
            roster_error=roster_error,
        )
    )


# ---------------------------------------------------------------------------
# 1. Exhaustive: every reachable-and-undefended combination must be CRITICAL
# ---------------------------------------------------------------------------

_TLS_OFF = (TlsState.OFF_EXPOSED, TlsState.ORPHANED)
_TLS_ON = (TlsState.OK, TlsState.NOT_COVERED, TlsState.EXPIRING)
_TLS_BROKEN = (
    TlsState.HALF_CONFIGURED,
    TlsState.FILE_MISSING,
    TlsState.KEY_MISMATCH,
    TlsState.UNREADABLE,
)


@pytest.mark.parametrize("tls_state", _TLS_OFF + _TLS_ON + _TLS_BROKEN)
@pytest.mark.parametrize("ranges", ["192.168.0.0/24", "10.0.0.0/8", "0.0.0.0/0"])
def test_reachable_without_auth_is_always_critical(tls_state, ranges):
    """Whatever else is true, a reachable studio with no login is CRITICAL."""
    posture = _posture(exposed=True, ranges=ranges, auth=False, tls_state=tls_state)
    assert posture.worst is Severity.CRITICAL, (
        f"no CRITICAL for reachable+no-auth (tls={tls_state.value}, ranges={ranges})"
    )
    assert any("authentication OFF" in f.headline for f in posture.findings)


@pytest.mark.parametrize("tls_state", _TLS_OFF)
@pytest.mark.parametrize("ranges", ["192.168.0.0/24", "10.0.0.0/8"])
def test_reachable_with_auth_but_no_tls_is_always_critical(tls_state, ranges):
    """Auth on + no TLS puts a live credential on the wire."""
    posture = _posture(exposed=True, ranges=ranges, auth=True, tls_state=tls_state)
    assert posture.worst is Severity.CRITICAL
    assert any("plain HTTP" in f.headline for f in posture.findings)


@pytest.mark.parametrize("tls_state", _TLS_BROKEN)
def test_broken_tls_is_always_critical_even_on_loopback(tls_state):
    """A studio that will not start is not a reachability question."""
    posture = _posture(exposed=False, ranges="", tls_state=tls_state)
    assert posture.worst is Severity.CRITICAL


def test_unreadable_roster_is_critical_not_assumed_safe():
    """An unreadable roster could be a disabled one; guessing benign is the
    exact false negative this suite exists to prevent."""
    posture = _posture(exposed=True, roster_error="boom")
    assert posture.worst is Severity.CRITICAL


def test_the_only_clean_reachable_configuration_is_fully_defended():
    """Exhaustive sweep: enumerate every combination and assert that the ONLY
    ones producing no CRITICAL are the ones that genuinely deserve it."""
    for exposed, ranges, auth, tls_state in itertools.product(
        [True, False],
        ["", "192.168.0.0/24"],
        [True, False],
        _TLS_OFF + _TLS_ON,
    ):
        posture = _posture(
            exposed=exposed,
            ranges=ranges,
            auth=auth,
            tls_state=tls_state,
            trusted_proxies="10.0.0.1/32",
        )
        reachable = exposed and bool(ranges)
        has_critical = posture.worst is Severity.CRITICAL

        if not reachable:
            assert not has_critical, f"CRITICAL on an unreachable studio: {posture.findings}"
            continue

        defended = auth and tls_state in _TLS_ON
        assert has_critical is not defended, (
            f"reachable={reachable} auth={auth} tls={tls_state.value}: "
            f"expected critical={not defended}, got {has_critical}"
        )


# ---------------------------------------------------------------------------
# 2. Structural: no rule can silence another
# ---------------------------------------------------------------------------


def test_every_rule_is_reached_even_when_an_earlier_one_fires():
    """The old structure had a `return` that skipped all remaining rules.

    A posture that trips several rules at once must produce all of them; if any
    rule can short-circuit the list, this fails.
    """
    posture = _posture(
        exposed=True,
        ranges="10.0.0.0/8",  # broad -> WARNING
        auth=False,  # -> CRITICAL
        tls_state=TlsState.FILE_MISSING,  # broken -> CRITICAL
        trusted_proxies="",  # -> NOTE
    )
    headlines = " ".join(f.headline for f in posture.findings)
    assert "authentication OFF" in headlines
    assert "refuse to start" in headlines
    assert "very broad" in headlines
    assert "trusted proxies" in headlines


def test_rules_are_independent_functions():
    """Each rule must be callable on its own and return a list.

    Guarantees the structure stays flat: a rule that depended on another's
    result could not satisfy this.
    """
    posture = _posture()
    for rule in RULES:
        result = rule(posture)
        assert isinstance(result, list)
        assert all(hasattr(f, "severity") for f in result)


def test_findings_is_exactly_the_union_of_the_rules():
    """No finding may be produced outside the RULES list — that is what makes
    the list a complete description of what this command checks."""
    posture = _posture(exposed=True, ranges="10.0.0.0/8", auth=False)
    from_rules = [f for rule in RULES for f in rule(posture)]
    assert len(_findings(posture)) == len(from_rules)


def test_no_rule_contains_a_compound_condition():
    """The user's requirement: simple, assertable ifs — no and/or chains.

    Enforced structurally rather than by review, because a compound condition
    is where a false negative hides.
    """
    import ast
    import inspect

    for rule in RULES:
        tree = ast.parse(inspect.getsource(rule))
        boolops = [n for n in ast.walk(tree) if isinstance(n, ast.BoolOp)]
        assert not boolops, f"{rule.__name__} uses and/or — split it into sequential ifs"


# ---------------------------------------------------------------------------
# 3. The reachability truth table, exhaustively
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("exposed", "ranges", "expected"),
    [
        (False, "", False),
        (False, "192.168.0.0/24", False),
        (True, "", False),
        (True, "192.168.0.0/24", True),
    ],
)
def test_reachable_by_others_truth_table(exposed, ranges, expected):
    assert _posture(exposed=exposed, ranges=ranges).reachable_by_others is expected


# ---------------------------------------------------------------------------
# 4. The verdict cannot contradict the findings
# ---------------------------------------------------------------------------


def test_no_status_command_contains_a_compound_condition():
    """All three status commands must follow the same structure.

    ``security status`` was hardened first; ``auth status`` and ``ssl status``
    report on the same studio and must not drift into a different — and
    differently-wrong — way of deciding things. Display fallbacks
    (``x or "this machine"``) are exempt: they pick a string, not a verdict.
    """
    import ast
    import pathlib

    checked = {
        "packages/haywire-studio/src/haywire_studio/network/tls_operations.py": {
            "status",
            "setup",
            "update",
            "configured",
        },
        "packages/haywire-studio/src/haywire_studio/cli/sslcmd.py": {
            "_status",
            "_trust",
            "_print_off_exposed",
            "_print_off_loopback",
        },
        "packages/haywire-studio/src/haywire_studio/cli/authcmd.py": {
            "_status",
            "_print_findings",
        },
    }

    def _is_display_fallback(node):
        """`a or "literal"` used as a value, not as a test."""
        if not isinstance(node.op, ast.Or):
            return False
        return any(isinstance(v, ast.Constant) for v in node.values)

    offenders = []
    for path, names in checked.items():
        tree = ast.parse(pathlib.Path(path).read_text())
        for node in ast.walk(tree):
            if not isinstance(node, ast.FunctionDef):
                continue
            if node.name not in names:
                continue
            for inner in ast.walk(node):
                if isinstance(inner, ast.BoolOp) and not _is_display_fallback(inner):
                    offenders.append(f"{path.split('/')[-1]}::{node.name}")
    assert not offenders, f"compound conditions in status logic: {sorted(set(offenders))}"


def test_ssl_status_and_security_status_agree_on_reachability():
    """The two commands must never describe the same studio differently.

    `ssl status` used to warn about traffic crossing the network whenever
    `expose_to_network` was on, even with an allowlist that rejected everyone —
    disagreeing with `security status` about the identical config.
    """
    import inspect

    from haywire_studio.cli import sslcmd

    source = inspect.getsource(sslcmd._print_off_exposed)
    # It must consult the shared assessment rather than re-deriving exposure.
    assert "_reachable_by_others" in source


def test_auth_status_never_suppresses_a_critical():
    """`auth status` must print every CRITICAL the assessment produced.

    Two historical bugs, both suppressing a real warning via an unrelated
    condition: an early `return` unless `posture.exposed` (hiding non-exposure
    criticals), and a `return 1` on an unreadable roster (hiding everything on
    exactly the studio that most needed reporting).

    Asserted behaviourally rather than by reading the source, so it survives
    renames and cannot be satisfied by a differently-shaped mistake.
    """
    import io
    from contextlib import redirect_stdout

    from haywire_studio.cli import authcmd

    for posture in (
        _posture(exposed=True, ranges="192.168.0.0/24", auth=False),
        _posture(exposed=False, ranges="", tls_state=TlsState.KEY_MISMATCH),
        _posture(exposed=True, ranges="192.168.0.0/24", roster_error="corrupt"),
    ):
        criticals = [f for f in posture.findings if f.severity is Severity.CRITICAL]
        if not criticals:
            continue
        buffer = io.StringIO()
        with redirect_stdout(buffer):
            authcmd._print_findings(posture)
        printed = buffer.getvalue()
        for finding in criticals:
            assert finding.headline in printed, f"auth status dropped a CRITICAL: {finding.headline!r}"


def test_verdict_is_never_ok_while_a_critical_exists():
    from haywire_studio.cli.securitycmd import _general_assesment

    for exposed, ranges, auth, tls_state in itertools.product(
        [True, False],
        ["", "192.168.0.0/24"],
        [True, False],
        _TLS_OFF + _TLS_ON + _TLS_BROKEN,
    ):
        posture = _posture(exposed=exposed, ranges=ranges, auth=auth, tls_state=tls_state)
        verdict = _general_assesment(posture)
        if posture.worst is Severity.CRITICAL:
            assert not verdict.startswith("OK"), (
                f"verdict {verdict!r} says OK while a CRITICAL finding exists: {posture.findings}"
            )
