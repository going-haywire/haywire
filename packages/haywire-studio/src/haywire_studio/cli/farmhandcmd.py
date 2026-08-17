"""``haywire farmhand`` — the MCP endpoint's two switches.

Both are read once at startup. Neither is a settings field any more (ADR 0028):
``enabled`` decides whether an agent API exists at all, and
``restrict_to_loopback`` is the DNS-rebinding defence — a control whose whole
value is that a user cannot casually toggle it while reading a tooltip.

MCP is the protocol; Farmhand is the component. The command is named for the
component, matching ``FarmhandHost``, ``farmhand://`` resource URIs and the
glossary.
"""

from __future__ import annotations

import argparse
from pathlib import Path

from haywire_studio.cli._guards import studio_is_running
from haywire_studio.security.document import load_document
from haywire_studio.security.errors import SecurityError
from haywire_studio.security.operations import set_farmhand_enabled, set_farmhand_loopback


def register(subparsers: argparse._SubParsersAction) -> None:
    parser = subparsers.add_parser("farmhand", help="Configure the Farmhand MCP endpoint at /mcp")
    parser.add_argument(
        "--document",
        default=None,
        help="Security document to operate on (default: ~/.haywire/security.json). Mainly for testing.",
    )
    actions = parser.add_subparsers(dest="farmhand_command", required=True)

    on = actions.add_parser("enable", help="Serve the MCP endpoint at /mcp")
    on.set_defaults(handler=_enable)

    off = actions.add_parser("disable", help="Stop serving the MCP endpoint")
    off.set_defaults(handler=_disable)

    local = actions.add_parser("local-only", help="Reject MCP requests whose Host is not loopback")
    local.set_defaults(handler=_local_only)

    remote = actions.add_parser("allow-remote", help="Accept MCP requests from any Host")
    remote.set_defaults(handler=_allow_remote)

    report = actions.add_parser("status", help="Show the Farmhand configuration")
    report.set_defaults(handler=_status)


def _path(args: argparse.Namespace) -> Path | None:
    raw = getattr(args, "document", None)
    return Path(raw) if raw else None


def _studio_is_running() -> bool:
    """Module-level seam, so tests can pin it (mirrors ``authcmd``)."""
    return studio_is_running()


def _guard() -> bool:
    if _studio_is_running():
        print(
            "ERROR: a studio is running in this workspace.\n"
            "  Farmhand configuration is read once at startup, so it must be changed with "
            "the studio stopped.\n"
            "  Quit the studio and run this again."
        )
        return True
    return False


def _enable(args: argparse.Namespace) -> int:
    if _guard():
        return 1
    try:
        set_farmhand_enabled(True, path=_path(args))
    except SecurityError as exc:
        print(f"ERROR: {exc}")
        return 1
    print("Farmhand enabled — the studio will serve MCP at /mcp. Restart it to apply.")
    return 0


def _disable(args: argparse.Namespace) -> int:
    if _guard():
        return 1
    try:
        set_farmhand_enabled(False, path=_path(args))
    except SecurityError as exc:
        print(f"ERROR: {exc}")
        return 1
    print("Farmhand disabled — /mcp will not be served. Restart the studio to apply.")
    return 0


def _local_only(args: argparse.Namespace) -> int:
    if _guard():
        return 1
    try:
        set_farmhand_loopback(True, path=_path(args))
    except SecurityError as exc:
        print(f"ERROR: {exc}")
        return 1
    print(
        "Farmhand now rejects MCP requests whose Host/Origin is not loopback.\n"
        "  This is DNS-rebinding protection: it stops a web page in your browser from\n"
        "  driving this studio's tools. Restart the studio to apply."
    )
    return 0


def _allow_remote(args: argparse.Namespace) -> int:
    if _guard():
        return 1
    try:
        set_farmhand_loopback(False, path=_path(args))
    except SecurityError as exc:
        print(f"ERROR: Farmhand still accepts loopback requests only.\n  {exc}")
        return 1
    print(
        "Farmhand now accepts MCP requests from any Host.\n"
        "  The DNS-rebinding check is off; the roster bearer token is what guards /mcp.\n"
        "  Restart the studio to apply."
    )
    return 0


def _status(args: argparse.Namespace) -> int:
    """Always exits 0 — reports rather than judges."""
    try:
        doc = load_document(_path(args))
    except SecurityError as exc:
        print(f"Farmhand state is UNKNOWN — the security document could not be read.\n  {exc}")
        return 0

    if not doc.farmhand.enabled:
        print("Farmhand: disabled — /mcp is not served.")
        return 0

    print("Farmhand: enabled — serving MCP at /mcp")
    if doc.farmhand.restrict_to_loopback:
        print("  Hosts:  loopback only (DNS-rebinding protection on)")
    else:
        print("  Hosts:  any (DNS-rebinding protection OFF)")
    if doc.auth.enabled:
        agents = [p for p in doc.auth.principals if p.is_agent]
        print(f"  Token:  required — {len(agents)} agent principal(s) in the roster")
    else:
        print("  Token:  not required (authentication is off, so the studio is loopback-only)")

    print("\nFull picture:  haywire security status")
    return 0
