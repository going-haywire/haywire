"""``haywire user`` — manage principals in the global roster.

Runs against a stopped studio. A running studio caches the roster against its
mtime, so changes made here are picked up within a request; but enabling or
disabling authentication needs a restart, which is why that lives in
``haywire auth`` rather than here.
"""

from __future__ import annotations

import argparse
import getpass
from pathlib import Path

from haywire.core.access import AccessTier

from haywire_studio.auth.operations import (
    add_agent,
    add_user,
    remove_principal,
    set_password,
    set_tier,
)
from haywire_studio.auth.passwords import POLICY_HELP
from haywire_studio.security.document import load_document
from haywire_studio.security.errors import SecurityError

_TIERS = [tier.value for tier in AccessTier]


def register(subparsers: argparse._SubParsersAction) -> None:
    parser = subparsers.add_parser("user", help="Manage studio principals (users and agents)")
    parser.add_argument(
        "--document",
        default=None,
        help="Security document to operate on (default: ~/.haywire/security.json). Mainly for testing.",
    )
    actions = parser.add_subparsers(dest="user_command", required=True)

    add = actions.add_parser("add", help="Add a user or agent principal")
    add.add_argument("name")
    add.add_argument("--tier", choices=_TIERS, default=AccessTier.VIEW.value)
    add.add_argument(
        "--agent", action="store_true", help="Create a token principal instead of a password one"
    )
    add.add_argument("--workspace", default="", help="Scope an agent token to one project path")
    add.set_defaults(handler=_add)

    remove = actions.add_parser("remove", help="Remove a principal")
    remove.add_argument("name")
    remove.set_defaults(handler=_remove)

    listing = actions.add_parser("list", help="List principals")
    listing.set_defaults(handler=_list)

    passwd = actions.add_parser("passwd", help="Set a user's password")
    passwd.add_argument("name")
    passwd.set_defaults(handler=_passwd)

    tier = actions.add_parser("tier", help="Change a principal's access tier")
    tier.add_argument("name")
    tier.add_argument("tier", choices=_TIERS)
    tier.set_defaults(handler=_tier)


def _document_path(args: argparse.Namespace) -> Path | None:
    raw = getattr(args, "document", None)
    return Path(raw) if raw else None


def _prompt_password(name: str) -> str:
    """Prompt twice and require a match. Patched in tests."""
    print(f"Password policy: {POLICY_HELP}")
    first = getpass.getpass(f"New password for {name}: ")
    second = getpass.getpass("Repeat: ")
    if first != second:
        raise SecurityError("The two passwords did not match.")
    return first


def _add(args: argparse.Namespace) -> int:
    path = _document_path(args)
    tier = AccessTier(args.tier)
    try:
        if args.agent:
            agent = add_agent(args.name, tier, workspace=args.workspace, path=path)
            print(f"Created agent principal {agent.name!r} ({tier.value}).")
            print(f"  Token: {agent.token}")
            print("  Give this to the agent — it is stored in the roster and can be re-read at any time.")
            print("  Connect with:  haywire farmhand status")
        else:
            add_user(args.name, _prompt_password(args.name), tier, path=path)
            print(f"Created user principal {args.name!r} ({tier.value}).")
    except SecurityError as exc:
        print(f"ERROR: {exc}")
        return 1
    return 0


def _remove(args: argparse.Namespace) -> int:
    try:
        remove_principal(args.name, path=_document_path(args))
    except SecurityError as exc:
        print(f"ERROR: {exc}")
        return 1
    print(f"Removed {args.name!r}.")
    return 0


def _list(args: argparse.Namespace) -> int:
    try:
        roster = load_document(_document_path(args)).auth
    except SecurityError as exc:
        print(f"ERROR: {exc}")
        return 1

    state = "enabled" if roster.enabled else "disabled"
    print(f"Authentication is {state}. {len(roster.principals)} principal(s):")
    for principal in roster.principals:
        scope = f"  workspace={principal.workspace}" if principal.workspace else ""
        print(f"  {principal.name:<24} {principal.kind:<6} {principal.tier.value:<6}{scope}")
    return 0


def _passwd(args: argparse.Namespace) -> int:
    try:
        set_password(args.name, _prompt_password(args.name), path=_document_path(args))
    except SecurityError as exc:
        print(f"ERROR: {exc}")
        return 1
    print(f"Password updated for {args.name!r}.")
    return 0


def _tier(args: argparse.Namespace) -> int:
    try:
        set_tier(args.name, AccessTier(args.tier), path=_document_path(args))
    except SecurityError as exc:
        print(f"ERROR: {exc}")
        return 1
    print(f"{args.name!r} is now {args.tier}.")
    return 0
