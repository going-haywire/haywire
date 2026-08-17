"""``haywire security`` — the four defence axes in one answer.

``auth status`` and ``ssl status`` each report one axis correctly and neither
can report the thing that actually matters, which is the *combination*:
exposure decides whether the other two matter, and authentication-without-TLS
is a state only a joined view can name. This command exists for that, and
deliberately does not duplicate the actions — ``auth enable`` and ``ssl setup``
remain where they are, and every finding here names one of them.

Read-only and unguarded against a running studio, for the same reason
``ssl status`` is: telling someone to quit the studio to find out why their
studio is insecure is backwards. Because it reads files rather than the live
process, a running studio may have booted with different values — which the
output says, rather than quietly reporting something that is not in force.

Named ``securitycmd`` to match the ``authcmd``/``sslcmd`` dodge around stdlib
and namespace collisions.
"""

from __future__ import annotations

import argparse
from pathlib import Path

from haywire_studio.cli._guards import studio_is_running
from haywire_studio.network.tls_operations import TlsState
from haywire_studio.security.posture import Finding, Posture, Severity, assess

_MARKERS = {
    Severity.CRITICAL: "CRITICAL",
    Severity.WARNING: "WARNING",
    Severity.NOTE: "note",
}


def register(subparsers: argparse._SubParsersAction) -> None:
    parser = subparsers.add_parser(
        "security", help="Show exposure, authentication, TLS and Farmhand together"
    )
    parser.add_argument(
        "--document",
        default=None,
        help="Security document to read (default: ~/.haywire/security.json). Mainly for testing.",
    )
    parser.add_argument(
        "--dir",
        default=None,
        help="Certificate directory (default: ~/.haywire/certs). Mainly for testing.",
    )
    actions = parser.add_subparsers(dest="security_command", required=True)

    report = actions.add_parser("status", help="Assess the studio's overall security posture")
    report.set_defaults(handler=_status)


def _path(args: argparse.Namespace, name: str) -> Path | None:
    raw = getattr(args, name, None)
    return Path(raw) if raw else None


def _studio_is_running() -> bool:
    """Module-level seam, so tests can pin it (mirrors ``authcmd``)."""
    return studio_is_running()


def _status(args: argparse.Namespace) -> int:
    """Always exits 0 — like ``ssl status``, this reports rather than judges.

    An exit code would make the command's meaning depend on whether the user
    considers a NOTE a failure, and would make it useless in a shell that stops
    on error. The severity markers carry the judgement.
    """
    posture = assess(directory=_path(args, "dir"), path=_path(args, "document"))
    _print_posture(posture, running=_studio_is_running())
    return 0


# ---------------------------------------------------------------------------
# Output
# ---------------------------------------------------------------------------


def _print_posture(posture: Posture, *, running: bool) -> None:
    _print_axes(posture)
    print()
    _print_findings(posture)
    if running:
        # Never silently report something that is not in force.
        print(
            "\nNote: a studio is running in this workspace. These are the values on\n"
            "disk — if they changed since it started, it is still using the old ones."
        )


def _print_axes(posture: Posture) -> None:
    """The verdict first, then the four axes as facts behind it."""
    print("-" * 60)
    print(f" Security status: {_general_assesment(posture)}")
    print("-" * 60)
    print()
    print(f"  Network:  {_network_line(posture)}")
    print(f"  Auth:     {_auth_line(posture)}")
    print(f"  TLS:      {_tls_line(posture)}")
    print(f"  Farmhand: {_farmhand_line(posture)}")


def _farmhand_line(posture: Posture) -> str:
    if not posture.farmhand_enabled:
        return "disabled — /mcp is not served"
    hosts = "loopback only" if posture.farmhand_loopback else "ANY host (rebinding check off)"
    token = "roster token required" if posture.auth_enabled else "no token (studio is loopback-only)"
    return f"enabled at /mcp — {hosts}, {token}"


def _general_assesment(posture: Posture) -> str:
    """One line, read before anything else — the answer to "am I ok?".

    Keyed on the worst finding rather than on the axes directly, so it can
    never disagree with the list printed below it. The two clean cases are
    deliberately worded differently: "loopback" is fine because there is no
    exposure, "hardened" is fine because the exposure is defended, and a user
    deciding whether to expose the studio needs to know which one they have.
    """
    if posture.document_error:
        return "UNKNOWN — the roster could not be read"

    worst = posture.worst
    if worst is Severity.CRITICAL:
        return "EXPOSED — act on the critical findings below"
    if worst is Severity.WARNING:
        return "AT RISK — reachable from the network with gaps"
    if worst is Severity.NOTE:
        return "OK — defended, with one detail worth a look"
    if not posture.exposed:
        return "OK — loopback only"
    if not posture.allowlist_open:
        return "OK — allowlist empty, only loopback can connect"
    return "OK — exposed and defended"


def _network_line(posture: Posture) -> str:
    if not posture.exposed:
        return "loopback only (127.0.0.1) — nothing leaves this machine"
    where = posture.reachable_at or "this machine"
    if not posture.allowlist_open:
        # An empty allowlist rejects every remote peer, so "exposed" alone
        # would overstate it by a wide margin.
        return f"bound at {where}, but the allowlist is empty — only loopback can connect"
    line = f"exposed at {where}, allowed: {posture.allowed_ranges}"
    if posture.covers_own_address() is False:
        # NOT "this machine cannot reach its own studio" — loopback bypasses
        # the allowlist unconditionally (ip_filter.py), so the operator always
        # reaches it via 127.0.0.1. What is actually true is narrower: other
        # machines sharing this subnet are excluded.
        line += (
            f"\n            (localhost still works; {where} itself is outside that list,"
            "\n             so neighbours on this subnet are rejected)"
        )
    return line


def _auth_line(posture: Posture) -> str:
    if posture.document_error:
        return "UNREADABLE — the roster could not be parsed"
    if not posture.auth_enabled:
        if not posture.reachable_by_others:
            # Nobody else can connect, so "everyone is an operator" would read
            # as a threat when the set of everyone is just this machine.
            return "disabled — no login required (only this machine can connect)"
        return "disabled — everyone who can reach the studio is a full operator"
    admins = f"{posture.admins} admin{'' if posture.admins == 1 else 's'}"
    return f"enabled — {posture.principals} principal(s), {admins}"


def _tls_line(posture: Posture) -> str:
    if posture.tls.state is TlsState.OFF_LOOPBACK or posture.tls.state is TlsState.OFF_EXPOSED:
        return "off — plain HTTP"
    if posture.tls.state is TlsState.ORPHANED:
        return "off — a certificate exists but nothing points at it"
    if posture.tls_on:
        detail = {
            TlsState.NOT_COVERED: " (does not cover this network)",
            TlsState.EXPIRING: " (expiring soon)",
        }.get(posture.tls.state, "")
        return f"on — HTTPS{detail}"
    return f"BROKEN — {posture.tls.state.value} (the studio will refuse to start)"


def _print_findings(posture: Posture) -> None:
    if not posture.findings:
        print(_clean_verdict(posture))
        return

    count = len(posture.findings)
    print(f"{count} finding{'' if count == 1 else 's'}:\n")
    for finding in posture.findings:
        _print_finding(finding)


def _print_finding(finding: Finding) -> None:
    print(f"  [{_MARKERS[finding.severity]}] {finding.headline}")
    for line in finding.detail:
        print(f"      {line}")
    if finding.fix:
        print(f"      Fix: {finding.fix}")
    print()


def _clean_verdict(posture: Posture) -> str:
    """Say *why* it is fine, not just that it is.

    The loopback case is fine for a structurally different reason than the
    hardened-and-exposed case, and a user deciding whether to expose the studio
    needs to know which one they are looking at.
    """
    if not posture.reachable_by_others:
        reason = (
            "loopback-only"
            if not posture.exposed
            else "bound wide, but its allowlist rejects every remote address"
        )
        return (
            f"Nothing to fix. The studio is {reason}, so there is no network\n"
            "exposure to defend against.\n\n"
            "Before opening it up, run:  haywire auth enable  and  haywire ssl setup\n"
            "Then:  haywire network expose --ranges <your subnet>"
        )
    return "Nothing to fix. The studio is exposed, but requires a login and serves HTTPS."
