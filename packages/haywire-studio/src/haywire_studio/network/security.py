"""The joined view of the studio's three defence axes.

``expose_to_network``, authentication and TLS are not independent settings that
happen to sit near each other — they are a **chain**. Exposure decides whether
the other two matter at all: on loopback, an empty roster and plain HTTP are
both correct, and warning about them there trains users to ignore the warning.
Exposed, the same two facts are the difference between a private tool and an
open one.

That is why the assessment lives here rather than in either subcommand.
``ssl status`` already reads ``expose_to_network`` to choose between its two
"no TLS" states, so the joining had already begun; this module finishes it
instead of letting a second, differently-worded copy grow in ``authcmd``.

The interesting findings are the *combinations*, and one of them is invisible
to either axis alone: authentication ON with TLS OFF is worse than it looks,
because enabling auth introduces a password that then crosses the network in
cleartext. Neither ``auth status`` nor ``ssl status`` can say that.

Like :func:`~haywire_studio.network.tls_operations.status`, everything here is
read-only, never raises, and reads *files* rather than a live registry — the
CLI runs with the studio stopped, where no registry exists. The consequence is
reported rather than hidden: see :attr:`Posture.studio_running`.
"""

from __future__ import annotations

import ipaddress
from collections.abc import Callable
from dataclasses import dataclass
from enum import Enum
from pathlib import Path

from haywire_studio.auth.roster import Roster, RosterError, load_roster
from haywire_studio.network.tls_operations import TlsState, TlsStatus
from haywire_studio.network.tls_operations import status as tls_status
from haywire_studio.network.tls_settings import read_network_setting


class Severity(Enum):
    """How loudly a finding should read.

    Only three levels, because the printing has to stay scannable. ``CRITICAL``
    is reserved for "someone else can already do this", never for "this is not
    ideal" — the moment a warning is arguable, the whole report becomes
    something users learn to skip.
    """

    CRITICAL = "critical"
    WARNING = "warning"
    NOTE = "note"


_ORDER = {Severity.CRITICAL: 0, Severity.WARNING: 1, Severity.NOTE: 2}


@dataclass(frozen=True)
class Finding:
    """One thing that is true, and exactly one command that changes it.

    The shape enforces the discipline ``sslcmd`` already sets out in its
    docstring: state what is true, then name one next command. A finding with
    no ``fix`` is one the user cannot act on directly (or need not).
    """

    severity: Severity
    headline: str
    detail: tuple[str, ...] = ()
    fix: str = ""


@dataclass(frozen=True)
class Posture:
    """The whole security picture, gathered without printing any of it."""

    exposed: bool
    reachable_at: str | None
    auth_enabled: bool
    principals: int
    admins: int
    tls: TlsStatus
    allowed_ranges: str
    trusted_proxies: str
    findings: tuple[Finding, ...]
    roster_error: str = ""
    studio_running: bool = False

    @property
    def worst(self) -> Severity | None:
        """The severity of the most serious finding, or ``None`` when clean."""
        return self.findings[0].severity if self.findings else None

    @property
    def tls_on(self) -> bool:
        """True when TLS is configured *and* usable.

        The broken states are not "on": each of them is a studio that refuses
        to start, so counting them as encryption would be the one direction of
        error this report must not make.
        """
        return self.tls.state in (TlsState.OK, TlsState.NOT_COVERED, TlsState.EXPIRING)

    @property
    def ranges(self) -> tuple[str, ...]:
        """The parsed ``allowed_remote_ranges`` entries."""
        return tuple(entry.strip() for entry in self.allowed_ranges.split(",") if entry.strip())

    @property
    def fenced(self) -> bool:
        """Bound beyond loopback, but the allowlist admits nobody."""
        if not self.exposed:
            return False
        return not self.allowlist_open

    @property
    def allowlist_open(self) -> bool:
        """True when the allowlist permits addresses beyond loopback.

        **This mirrors** ``IPAllowlistMiddleware``; it does not consult it. The
        middleware's ``_is_allowed`` is ``any(ip in network ...)`` over the
        parsed ranges, which for an empty sequence is always False — so an
        empty list is **closed**, not open, and only loopback bypasses it. That
        is the opposite of the usual "unset means unrestricted" convention, and
        getting it backwards is how this report came to warn that an empty list
        allowed everyone.

        The duplication is deliberate: the CLI runs with the studio stopped, so
        there is no middleware instance to ask. It is also the risk — if
        ``_is_allowed`` ever grows a rule (a default range, a deny list), this
        property goes quietly stale. ``tests/studio/test_network`` pins both
        against the same cases to make that divergence fail loudly.
        """
        return bool(self.ranges)

    @property
    def reachable_by_others(self) -> bool:
        """True when a machine other than this one can actually connect.

        **The single most load-bearing value in this module.** Most rules are
        gated on it, so a wrong ``True`` costs a spurious finding while a wrong
        ``False`` hides real ones — the failure this command must not have.

        Written as two sequential rejections rather than ``exposed and
        allowlist_open`` so each precondition is separately readable and
        separately testable. Both must hold; the complete truth table is
        exhaustively asserted in ``test_allowlist_agreement.py``:

            exposed  allowlist_open  reachable_by_others
            False    False           False   (loopback bind)
            False    True            False   (ranges set, but bound to loopback)
            True     False           False   (bound wide, allowlist rejects all)
            True     True            True    (the only reachable case)
        """
        if not self.exposed:
            return False
        if not self.allowlist_open:
            return False
        return True

    def covers_own_address(self) -> bool | None:
        """Whether this machine's *LAN* address is inside the allowlist.

        ``None`` when it cannot be determined (no detected address).

        **This says nothing about whether the operator can reach the studio.**
        Loopback bypasses the allowlist unconditionally, so ``127.0.0.1`` always
        works no matter what this returns. False here means only that peers
        sharing this machine's subnet are rejected — a narrower and much less
        alarming fact, which callers must not inflate into "you are locked out".
        """
        if not self.reachable_at or not self.ranges:
            return None
        try:
            address = ipaddress.ip_address(self.reachable_at)
        except ValueError:
            return None
        for entry in self.ranges:
            try:
                if address in ipaddress.ip_network(entry, strict=False):
                    return True
            except ValueError:
                continue
        return False


def assess(
    *, directory: Path | None = None, settings_path: Path | None = None, roster_path: Path | None = None
) -> Posture:
    """Read all three axes and classify the result. Never raises.

    A corrupt roster is carried as :attr:`Posture.roster_error` rather than
    propagated: this command's entire job is to report on a broken security
    setup, so failing to run because the setup is broken would be exactly
    backwards.
    """
    tls = tls_status(directory=directory, settings_path=settings_path)
    roster, roster_error = _load_roster_quietly(roster_path)

    exposed = tls.exposed
    allowed_ranges = _text(read_network_setting("allowed_remote_ranges", path=settings_path))
    trusted_proxies = _text(read_network_setting("trusted_proxies", path=settings_path))

    posture = Posture(
        exposed=exposed,
        reachable_at=tls.reachable_at,
        auth_enabled=roster.enabled,
        principals=len(roster.principals),
        admins=len(roster.admins()),
        tls=tls,
        allowed_ranges=allowed_ranges,
        trusted_proxies=trusted_proxies,
        findings=(),
        roster_error=roster_error,
    )
    return _with_findings(posture)


def _load_roster_quietly(path: Path | None) -> tuple[Roster, str]:
    try:
        return load_roster(path), ""
    except RosterError as exc:
        return Roster(), str(exc)


def _text(value: object) -> str:
    return value.strip() if isinstance(value, str) else ""


def _with_findings(posture: Posture) -> Posture:
    """Attach the ordered finding list to a gathered posture."""
    findings = sorted(_findings(posture), key=lambda f: _ORDER[f.severity])
    return Posture(
        exposed=posture.exposed,
        reachable_at=posture.reachable_at,
        auth_enabled=posture.auth_enabled,
        principals=posture.principals,
        admins=posture.admins,
        tls=posture.tls,
        allowed_ranges=posture.allowed_ranges,
        trusted_proxies=posture.trusted_proxies,
        findings=tuple(findings),
        roster_error=posture.roster_error,
        studio_running=posture.studio_running,
    )


def _findings(posture: Posture) -> list[Finding]:
    """Run every rule. No early exit, no rule able to silence another.

    **Why this shape.** The dangerous error for this command is the false
    negative — reporting "nothing to fix" on a studio that is wide open. The
    previous version had a single ``return`` that skipped all remaining rules
    when it judged the studio unreachable, so one wrong boolean silenced
    *everything*. Now each rule is a standalone function evaluated
    unconditionally, and the worst a broken rule can do is lose its own
    finding.

    Each rule states its own precondition in one place (``RULES`` below). Read
    top to bottom, they are the complete list of things this command checks.
    """
    findings: list[Finding] = []
    for rule in RULES:
        findings.extend(rule(posture))
    return findings


# ---------------------------------------------------------------------------
# Rules
#
# One function per finding. Each takes the Posture and returns zero or one
# Finding. They are deliberately independent: no rule reads another's result,
# and none can prevent another from running.
#
# The guiding constraint is that a *wrong* answer must fail loud rather than
# quiet. Where a condition is uncertain, these err toward reporting — an
# unnecessary finding is a nuisance, a missing one is the failure mode this
# command exists to prevent.
# ---------------------------------------------------------------------------


def _rule_roster_unreadable(posture: Posture) -> list[Finding]:
    """A roster that cannot be parsed means authentication state is UNKNOWN.

    Reported as CRITICAL rather than assumed-safe: an unreadable roster could
    equally be a disabled one, and guessing the benign reading is precisely the
    false negative this command must not produce.
    """
    if not posture.roster_error:
        return []
    return [
        Finding(
            Severity.CRITICAL,
            "The roster cannot be read, so authentication state is unknown.",
            (posture.roster_error,),
            "Fix ~/.haywire/auth.json by hand, or move it aside and run 'haywire auth enable'.",
        )
    ]


def _rule_auth_off_while_reachable(posture: Posture) -> list[Finding]:
    """No login required, and somebody other than this machine can connect."""
    if not posture.reachable_by_others:
        return []
    if posture.roster_error:
        return []  # already reported as UNKNOWN by _rule_roster_unreadable
    if posture.auth_enabled:
        return []
    return [
        Finding(
            Severity.CRITICAL,
            "The studio is reachable from the network with authentication OFF.",
            (
                f"Anyone in {_range_text(posture)} is a full operator — they can",
                "edit, run and delete graphs, and install libraries.",
            ),
            "haywire auth enable",
        )
    ]


def _rule_plain_http_while_reachable(posture: Posture) -> list[Finding]:
    """Traffic readable on the wire, and somebody can connect to produce some.

    CRITICAL when authentication is on, because enabling auth is what puts a
    password and a session cookie on that wire; WARNING otherwise, when there
    is no credential to steal.
    """
    if not posture.reachable_by_others:
        return []
    if posture.tls_on:
        return []

    if posture.auth_enabled:
        detail = (
            "Authentication is on, so passwords and session cookies are what is exposed.",
            "Anyone who can observe one request can replay it and become that principal.",
        )
        severity = Severity.CRITICAL
    else:
        # Only the cleartext traffic. Two secure-context symptoms were tried
        # here and both were wrong: the clipboard (fixed — `clipboard_script()`
        # falls back to `document.execCommand`, so copy buttons do work over
        # LAN http) and camera/mic/geolocation (never applicable — Haywire's
        # cameras are server-side Python). A finding must name something that
        # actually happens; one the user can disprove and one that cannot occur
        # fail that test the same way.
        detail = (
            "Traffic crosses the network unencrypted.",
            # NOT "on every Farmhand call": the token only exists when
            # FarmhandSettings.require_auth is on (farmhand/host.py passes
            # token=None otherwise, and the middleware is not installed).
            "Any Farmhand bearer token in use is readable on the wire.",
        )
        severity = Severity.WARNING

    return [
        Finding(
            severity,
            "The studio is reachable from the network over plain HTTP.",
            detail,
            "haywire ssl setup",
        )
    ]


def _rule_no_admin(posture: Posture) -> list[Finding]:
    """Authentication on with nobody who can administer it.

    Not gated on reachability: this locks the operator out of the roster editor
    (``AccessTier.ADMIN``) whether or not anyone else can connect.
    """
    if posture.roster_error:
        return []
    if not posture.auth_enabled:
        return []
    if posture.admins:
        return []
    return [
        Finding(
            Severity.WARNING,
            "Authentication is on but the roster has no admin.",
            ("The roster editor and account panel are ADMIN-gated, so nobody can open them.",),
            "haywire user add <name> --tier admin",
        )
    ]


def _rule_broken_tls(posture: Posture) -> list[Finding]:
    """The TLS states that stop the studio booting.

    Not gated on reachability: a studio that will not start is not a network
    question, and catching it here beats discovering it at the next boot.

    "Will refuse to start" is true for all four, by two different mechanisms —
    both checked rather than assumed. ``HALF_CONFIGURED`` and ``FILE_MISSING``
    are caught by ``app._ssl_kwargs``, which prints and raises ``SystemExit``.
    ``KEY_MISMATCH`` and ``UNREADABLE`` pass that check and fail one layer
    deeper, when uvicorn builds its SSL context: verified that
    ``SSLContext.load_cert_chain`` on a mismatched pair raises
    ``SSLError [X509: KEY_VALUES_MISMATCH]``.
    """
    broken = {
        TlsState.HALF_CONFIGURED,
        TlsState.FILE_MISSING,
        TlsState.KEY_MISMATCH,
        TlsState.UNREADABLE,
    }
    if posture.tls.state not in broken:
        return []
    return [
        Finding(
            Severity.CRITICAL,
            "TLS is misconfigured — the studio will refuse to start.",
            tuple(posture.tls.detail.splitlines()),
            "haywire ssl status",
        )
    ]


def _rule_broad_allowlist(posture: Posture) -> list[Finding]:
    """An allowlist wide enough to be no real limit.

    A ``/8`` or shorter admits millions of hosts — not meaningfully narrower
    than unrestricted. Anything tighter is a deliberate choice this report has
    no business second-guessing.
    """
    if not posture.reachable_by_others:
        return []
    wide = [entry for entry in posture.ranges if _is_broad(entry)]
    if not wide:
        return []
    return [
        Finding(
            Severity.WARNING,
            f"The allowlist is very broad: {', '.join(wide)}.",
            ("That admits millions of addresses — barely narrower than allowing everyone.",),
            "Narrow 'allowed_remote_ranges' to the subnet you actually use.",
        )
    ]


def _rule_no_trusted_proxies(posture: Posture) -> list[Finding]:
    """Only matters behind a reverse proxy, where it collapses every client
    into one apparent address. NOTE, because most exposed studios have no
    proxy at all."""
    if not posture.reachable_by_others:
        return []
    if posture.trusted_proxies:
        return []
    return [
        Finding(
            Severity.NOTE,
            "No trusted proxies are configured — X-Forwarded-For headers are ignored.",
            ("Only matters behind a reverse proxy; there, every client appears to be the proxy.",),
            "Set 'trusted_proxies' under Network settings if this studio sits behind one.",
        )
    ]


def _rule_closed_allowlist(posture: Posture) -> list[Finding]:
    """Exposure on, but the allowlist admits nobody.

    Looks alarming in the settings file and is in fact the most restrictive
    combination there is. Saying so is the difference between a user trusting
    this report and disbelieving it.
    """
    if not posture.exposed:
        return []
    if posture.allowlist_open:
        return []
    return [
        Finding(
            Severity.NOTE,
            "Exposure is on, but the allowlist is empty — every remote address is rejected.",
            (
                "A remote peer gets a 403; only loopback gets through. The studio",
                "behaves as if it were loopback-only.",
            ),
            "Add your subnet to 'allowed_remote_ranges' to actually reach it from elsewhere.",
        )
    ]


#: Every check this command performs, in evaluation order (output is sorted by
#: severity afterwards, so this order is for reading, not for precedence).
RULES: tuple[Callable[[Posture], list[Finding]], ...] = (
    _rule_roster_unreadable,
    _rule_broken_tls,
    _rule_auth_off_while_reachable,
    _rule_plain_http_while_reachable,
    _rule_no_admin,
    _rule_broad_allowlist,
    _rule_no_trusted_proxies,
    _rule_closed_allowlist,
)


def _is_broad(entry: str) -> bool:
    """True for a CIDR that admits an implausibly large address space.

    An unparseable entry is **not** treated as broad — the studio refuses to
    start on invalid CIDR (``app.py`` validates eagerly), so this cannot be a
    live configuration and guessing at it would only add noise.
    """
    try:
        network = ipaddress.ip_network(entry, strict=False)
    except ValueError:
        return False
    return network.prefixlen <= (8 if network.version == 4 else 32)


def _range_text(posture: Posture) -> str:
    """How to describe who can connect, in a sentence."""
    return ", ".join(posture.ranges) if posture.ranges else "reach of this machine"
