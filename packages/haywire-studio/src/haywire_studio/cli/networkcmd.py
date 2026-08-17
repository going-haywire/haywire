"""``haywire network`` — where the studio can be reached from.

Exposure used to be a checkbox in a settings panel. It is a verb here because
safe exposure is three coordinated decisions, and a checkbox cannot express a
precondition: it can only be flipped, after which the studio is open and the
operator finds out what that meant later.

Every refusal names the one command that clears it. The refusals themselves
live in the document's ``validate`` (ADR 0028), not here — a second copy in the
CLI is a second copy that can disagree with the one the studio boots against.

Named ``networkcmd`` to match the ``authcmd``/``sslcmd``/``securitycmd`` dodge
around stdlib and namespace collisions.
"""

from __future__ import annotations

import argparse
from pathlib import Path

from haywire_studio.cli._guards import studio_is_running
from haywire_studio.security.errors import SecurityError
from haywire_studio.security.operations import expose, seal
from haywire_studio.security.posture import assess


def register(subparsers: argparse._SubParsersAction) -> None:
    parser = subparsers.add_parser("network", help="Expose the studio to the network, or seal it")
    parser.add_argument(
        "--document",
        default=None,
        help="Security document to operate on (default: ~/.haywire/security.json). Mainly for testing.",
    )
    parser.add_argument(
        "--dir",
        default=None,
        help="Certificate directory (default: ~/.haywire/certs). Mainly for testing.",
    )
    actions = parser.add_subparsers(dest="network_command", required=True)

    opened = actions.add_parser("expose", help="Bind beyond loopback for the given CIDR ranges")
    opened.add_argument(
        "--ranges",
        required=True,
        help="Comma-separated CIDR ranges allowed to reach the studio (e.g. '192.168.1.0/24')",
    )
    opened.add_argument(
        "--hostname",
        default=None,
        help="Public hostname the studio is reachable at, for the MCP Host/Origin list",
    )
    opened.add_argument(
        "--trusted-proxies",
        default=None,
        help="Comma-separated CIDR ranges whose X-Forwarded-For headers are trusted",
    )
    opened.set_defaults(handler=_expose)

    closed = actions.add_parser("seal", help="Bind to loopback again (the allowlist is kept)")
    closed.set_defaults(handler=_seal)

    report = actions.add_parser("status", help="Show where the studio can be reached from")
    report.set_defaults(handler=_status)


def _path(args: argparse.Namespace, name: str) -> Path | None:
    raw = getattr(args, name, None)
    return Path(raw) if raw else None


def _studio_is_running() -> bool:
    """Module-level seam, so tests can pin it (mirrors ``authcmd``)."""
    return studio_is_running()


def _guard() -> bool:
    if _studio_is_running():
        print(
            "ERROR: a studio is running in this workspace.\n"
            "  The bind address is read once at startup, so it must be changed with the "
            "studio stopped.\n"
            "  Quit the studio and run this again."
        )
        return True
    return False


def _split(raw: str | None) -> list[str] | None:
    if raw is None:
        return None
    return [entry.strip() for entry in raw.split(",") if entry.strip()]


def _expose(args: argparse.Namespace) -> int:
    if _guard():
        return 1
    path = _path(args, "document")
    try:
        doc = expose(
            _split(args.ranges) or [],
            public_hostname=args.hostname,
            trusted_proxies=_split(args.trusted_proxies),
            path=path,
        )
    except SecurityError as exc:
        print(f"ERROR: the studio was not exposed.\n  {exc}")
        return 1

    print("The studio is now exposed beyond loopback.")
    print(f"  Allowed: {', '.join(doc.network.allowed_ranges)}")
    print("  Authentication is on and TLS is configured.")
    if not doc.network.trusted_proxies:
        print(
            "\nNote: no trusted proxies are configured, so X-Forwarded-For headers are\n"
            "  ignored. Only matters behind a reverse proxy — there, every client would\n"
            "  otherwise appear to be the proxy."
        )
    print("\nStart the studio for this to take effect.")
    return 0


def _seal(args: argparse.Namespace) -> int:
    if _guard():
        return 1
    try:
        doc = seal(path=_path(args, "document"))
    except SecurityError as exc:
        print(f"ERROR: {exc}")
        return 1
    kept = ", ".join(doc.network.allowed_ranges)
    print("The studio is now loopback-only. Restart it for this to take effect.")
    if kept:
        print(f"  The allowlist was kept ({kept}) and applies again after 'haywire network expose'.")
    return 0


def _status(args: argparse.Namespace) -> int:
    """Always exits 0 — reports rather than judges, like ``ssl status``."""
    posture = assess(directory=_path(args, "dir"), path=_path(args, "document"))
    net = posture.document.network

    if not posture.exposed:
        print("Network: loopback only (127.0.0.1) — nothing leaves this machine.")
    elif not posture.allowlist_open:
        print("Network: bound beyond loopback, but the allowlist is empty — only loopback connects.")
    else:
        where = posture.reachable_at or "this machine"
        print(f"Network: exposed at {where}")
        print(f"  Allowed:  {posture.allowed_ranges}")

    if net.trusted_proxies:
        print(f"  Proxies:  {posture.trusted_proxies}")
    if net.public_hostname:
        print(f"  Hostname: {net.public_hostname}")

    print("\nFull picture:  haywire security status")
    return 0
