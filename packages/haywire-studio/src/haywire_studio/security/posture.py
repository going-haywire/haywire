"""The joined view of the studio's four defence axes (ADR 0028).

Exposure, authentication, TLS and the Farmhand mount are not independent
settings that happen to sit near each other — they are a chain. Exposure
decides whether the others matter at all: on loopback, an empty roster and
plain HTTP are both correct, and warning about them there trains users to
ignore the warning.

Two entry points, one rule set. :func:`assess_document` is pure and takes the
document the studio actually booted with — that is what the settings panel
renders. :func:`assess` reads the files, for a CLI running against a stopped
studio. Splitting them is what lets the panel report what is *in force* rather
than what happens to be on disk.

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

from haywire_studio.network.tls_operations import TlsState, TlsStatus
from haywire_studio.network.tls_operations import status as tls_status
from haywire_studio.security.document import SecurityDocument, load_document, validate
from haywire_studio.security.errors import SecurityError


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

    document: SecurityDocument
    tls: TlsStatus
    findings: tuple[Finding, ...]
    document_error: str = ""
    studio_running: bool = False

    @property
    def exposed(self) -> bool:
        return self.document.network.exposed

    @property
    def reachable_at(self) -> str | None:
        return self.tls.reachable_at

    @property
    def auth_enabled(self) -> bool:
        return self.document.auth.enabled

    @property
    def principals(self) -> int:
        return len(self.document.auth.principals)

    @property
    def admins(self) -> int:
        return len(self.document.auth.admins())

    @property
    def farmhand_enabled(self) -> bool:
        return self.document.farmhand.enabled

    @property
    def farmhand_loopback(self) -> bool:
        return self.document.farmhand.restrict_to_loopback

    @property
    def ranges(self) -> tuple[str, ...]:
        return self.document.network.allowed_ranges

    @property
    def allowed_ranges(self) -> str:
        """The ranges as one comma-joined string, for printing."""
        return ", ".join(self.ranges)

    @property
    def trusted_proxies(self) -> str:
        return ", ".join(self.document.network.trusted_proxies)

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
    def fenced(self) -> bool:
        """Bound beyond loopback, but the allowlist admits nobody."""
        if not self.exposed:
            return False
        return not self.allowlist_open

    @property
    def allowlist_open(self) -> bool:
        """True when the allowlist permits addresses beyond loopback.

        **This mirrors** ``IPAllowlistMiddleware``; it does not consult it. An
        empty list is **closed**, not open — the opposite of the usual "unset
        means unrestricted" convention, and getting it backwards is how this
        report once came to warn that an empty list allowed everyone.
        ``tests/security/test_allowlist_agreement.py`` pins both against the
        same cases so a divergence fails loudly.
        """
        return self.document.network.allowlist_open

    @property
    def reachable_by_others(self) -> bool:
        """True when a machine other than this one can actually connect.

        **The single most load-bearing value in this module.** Most rules are
        gated on it, so a wrong ``True`` costs a spurious finding while a wrong
        ``False`` hides real ones — the failure this command must not have. The
        complete truth table is asserted in ``test_posture.py``.
        """
        return self.document.network.reachable_by_others

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


def assess_document(
    doc: SecurityDocument,
    tls: TlsStatus,
    *,
    document_error: str = "",
    studio_running: bool = False,
) -> Posture:
    """Classify an already-loaded document. Pure — no file reads, never raises."""
    posture = Posture(
        document=doc,
        tls=tls,
        findings=(),
        document_error=document_error,
        studio_running=studio_running,
    )
    return _with_findings(posture)


def assess(*, directory: Path | None = None, path: Path | None = None) -> Posture:
    """Read every axis off disk and classify it. Never raises.

    A corrupt document is carried as :attr:`Posture.document_error` rather than
    propagated: this command's entire job is to report on a broken security
    setup, so failing to run because the setup is broken would be exactly
    backwards.
    """
    doc, error = _load_quietly(path)
    tls = tls_status(directory=directory, document=doc)
    return assess_document(doc, tls, document_error=error)


def _load_quietly(path: Path | None) -> tuple[SecurityDocument, str]:
    try:
        return load_document(path), ""
    except SecurityError as exc:
        return SecurityDocument(), str(exc)


def _with_findings(posture: Posture) -> Posture:
    """Attach the ordered finding list to a gathered posture."""
    findings = sorted(_findings(posture), key=lambda f: _ORDER[f.severity])
    return Posture(
        document=posture.document,
        tls=posture.tls,
        findings=tuple(findings),
        document_error=posture.document_error,
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


def _rule_document_unreadable(posture: Posture) -> list[Finding]:
    """A document that cannot be parsed means authentication state is UNKNOWN.

    Reported as CRITICAL rather than assumed-safe: an unreadable document could
    equally be a disabled one, and guessing the benign reading is precisely the
    false negative this command must not produce.
    """
    if not posture.document_error:
        return []
    return [
        Finding(
            Severity.CRITICAL,
            "The roster cannot be read, so authentication state is unknown.",
            (posture.document_error,),
            "Fix ~/.haywire/security.json by hand, or move it aside and run 'haywire auth enable'.",
        )
    ]


def _rule_auth_off_while_reachable(posture: Posture) -> list[Finding]:
    """No login required, and somebody other than this machine can connect."""
    if not posture.reachable_by_others:
        return []
    if posture.document_error:
        return []  # already reported as UNKNOWN by _rule_document_unreadable
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

    detail: tuple[str, ...]
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
        detail = ("Traffic crosses the network unencrypted.",)
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
    if posture.document_error:
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
            "haywire network expose --ranges <a tighter subnet>",
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
            "haywire network expose --ranges <cidr> --trusted-proxies <cidr>",
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
            "haywire network expose --ranges <your subnet>",
        )
    ]


def _rule_invariants_violated(posture: Posture) -> list[Finding]:
    """The document on disk describes a state the studio will not enter.

    Only reachable by hand-editing: every write path validates. Reported as
    CRITICAL because the gap between what the file says and what the studio
    does is exactly the misunderstanding that gets someone exposed — they read
    the file, believe it, and are wrong.
    """
    if posture.document_error:
        return []  # already reported; a default document has no violations to find
    problems = validate(posture.document)
    if not problems:
        return []
    return [
        Finding(
            Severity.CRITICAL,
            "The security document contradicts itself, so parts of it are not in force.",
            tuple(problems),
            "haywire network seal, then re-apply the settings you want through the CLI.",
        )
    ]


def _rule_farmhand_remote_without_auth(posture: Posture) -> list[Finding]:
    """The DNS-rebinding check is off and nothing else is guarding /mcp.

    CRITICAL without authentication, because with the check off and no token a
    web page the operator visits can drive this studio's tools. A NOTE with
    authentication on, where the gate demands a roster token regardless of what
    Host header the request carried.
    """
    if not posture.farmhand_enabled:
        return []
    if posture.farmhand_loopback:
        return []
    if posture.auth_enabled:
        return [
            Finding(
                Severity.NOTE,
                "Farmhand accepts MCP requests from any Host (DNS-rebinding check off).",
                ("Authentication is on, so a bearer token is still required.",),
                "haywire farmhand local-only  (to turn the check back on)",
            )
        ]
    return [
        Finding(
            Severity.CRITICAL,
            "Farmhand's DNS-rebinding check is off with authentication off.",
            (
                "Any web page you visit can post to this studio's /mcp endpoint and",
                "run its tools — including adding and executing a Python node.",
            ),
            "haywire farmhand local-only",
        )
    ]


def _rule_farmhand_reachable(posture: Posture) -> list[Finding]:
    """The MCP endpoint is served on a studio others can reach.

    A NOTE, not a warning: the gate requires a roster token here (exposure
    implies authentication), so this is a fact worth knowing rather than a gap.
    It exists because "the studio is exposed" and "an agent API is exposed with
    it" are not the same sentence in most operators' heads.
    """
    if not posture.farmhand_enabled:
        return []
    if not posture.reachable_by_others:
        return []
    return [
        Finding(
            Severity.NOTE,
            "The Farmhand MCP endpoint is reachable from the network at /mcp.",
            ("Agent principals with a roster token can drive this studio remotely.",),
            "haywire farmhand disable  (if no remote agent needs it)",
        )
    ]


#: Every check this command performs, in evaluation order (output is sorted by
#: severity afterwards, so this order is for reading, not for precedence).
RULES: tuple[Callable[[Posture], list[Finding]], ...] = (
    _rule_document_unreadable,
    _rule_invariants_violated,
    _rule_broken_tls,
    _rule_auth_off_while_reachable,
    _rule_plain_http_while_reachable,
    _rule_no_admin,
    _rule_farmhand_remote_without_auth,
    _rule_broad_allowlist,
    _rule_no_trusted_proxies,
    _rule_closed_allowlist,
    _rule_farmhand_reachable,
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
