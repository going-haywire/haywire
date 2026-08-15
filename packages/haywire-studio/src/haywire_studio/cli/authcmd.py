"""``haywire auth`` — turn studio authentication on and off.

Both directions demand a working admin login. Anyone who can run this command
can also edit ``~/.haywire/auth.json`` by hand, so the check is not a barrier
against an attacker — it is a proof of recoverability. It makes the realistic
failure unreachable: enabling authentication with a roster whose passwords
nobody remembers.

Refuses to run while a studio is live in this workspace: the flag is read once
at startup, so flipping it under a running process produces a studio whose
behaviour no longer matches its own config file.
"""

from __future__ import annotations

import argparse
import getpass
from pathlib import Path

from haywire.core.access import AccessTier

from haywire_studio.auth.operations import disable_auth, enable_auth
from haywire_studio.auth.roster import Principal, RosterError, load_roster, save_roster


def register(subparsers: argparse._SubParsersAction) -> None:
    parser = subparsers.add_parser("auth", help="Enable or disable studio authentication")
    parser.add_argument(
        "--roster",
        default=None,
        help="Roster file to operate on (default: ~/.haywire/auth.json). Mainly for testing.",
    )
    actions = parser.add_subparsers(dest="auth_command", required=True)

    enable = actions.add_parser("enable", help="Turn authentication on (requires an admin login)")
    enable.set_defaults(handler=_enable)

    disable = actions.add_parser("disable", help="Turn authentication off (requires an admin login)")
    disable.set_defaults(handler=_disable)

    status = actions.add_parser("status", help="Show whether authentication is on")
    status.set_defaults(handler=_status)


def _roster_path(args: argparse.Namespace) -> Path | None:
    raw = getattr(args, "roster", None)
    return Path(raw) if raw else None


def _prompt_username() -> str:
    return input("Admin username: ").strip()


def _prompt_password() -> str:
    return getpass.getpass("Password: ")


def _confirm(prompt: str) -> bool:
    """Yes/no prompt. Patched in tests."""
    return input(f"{prompt} [y/N] ").strip().lower() in {"y", "yes"}


def _studio_is_running() -> bool:
    """True when this workspace has a live studio process.

    Best-effort, via the sidecar the studio writes when it mounts Farmhand. It
    cannot see a studio running for a *different* workspace against the same
    global roster — that case is handled by the roster's atomic writes, which
    make a concurrent write last-one-wins rather than corrupting.
    """
    from haywire_studio.farmhand.identity import identity_status, read_identity

    ident = read_identity(Path.cwd())
    return ident is not None and identity_status(ident) == "alive"


def _guard_running_studio() -> bool:
    if _studio_is_running():
        print(
            "ERROR: a studio is running in this workspace.\n"
            "  Authentication is read once at startup, so it must be changed with the studio stopped.\n"
            "  Quit the studio and run this again."
        )
        return True
    return False


def _offer_token_import(roster_path_arg: Path | None) -> None:
    """Offer to bring this workspace's existing Farmhand token into the roster.

    With authentication off, the token lives in ``<workspace>/.haywire/farmhand_token``
    and the gate is not involved. Once on, the roster is authoritative — so an
    agent configured before the flip would stop working with no obvious cause.
    Imported at EDIT and scoped to this workspace, matching the blast radius the
    token already had.
    """
    from haywire_studio.auth.roster import KIND_AGENT, load_roster

    workspace = Path.cwd().resolve()
    token_file = workspace / ".haywire" / "farmhand_token"
    if not token_file.exists():
        return

    token = token_file.read_text(encoding="utf-8").strip()
    if not token:
        return

    roster = load_roster(roster_path_arg)
    if roster.find_by_token(token) is not None:
        return

    print(f"\nThis workspace has a Farmhand token at {token_file}.")
    print("Agents using it will stop working once authentication is on unless it")
    print("becomes a roster principal.")
    if not _confirm("Import it as an 'edit' agent principal scoped to this workspace?"):
        print("Skipped. Create one later with: haywire user add <name> --agent --tier edit")
        return

    name = f"farmhand-{workspace.name}"
    suffix = 2
    while roster.find(name) is not None:
        name = f"farmhand-{workspace.name}-{suffix}"
        suffix += 1

    roster.principals.append(
        Principal(
            name=name,
            kind=KIND_AGENT,
            tier=AccessTier.EDIT,
            token=token,
            workspace=str(workspace),
        )
    )
    save_roster(roster, roster_path_arg)
    print(f"Imported as agent principal {name!r} (edit, scoped to {workspace}).")


def _enable(args: argparse.Namespace) -> int:
    if _guard_running_studio():
        return 1
    roster_path_arg = _roster_path(args)
    try:
        username, password = _prompt_username(), _prompt_password()
        _offer_token_import(roster_path_arg)
        enable_auth(username, password, path=roster_path_arg)
    except RosterError as exc:
        print(f"ERROR: {exc}")
        return 1
    print("Authentication enabled. Start the studio and sign in at /login.")
    return 0


def _disable(args: argparse.Namespace) -> int:
    if _guard_running_studio():
        return 1
    try:
        disable_auth(_prompt_username(), _prompt_password(), path=_roster_path(args))
    except RosterError as exc:
        print(f"ERROR: {exc}")
        return 1
    print("Authentication disabled. Everyone who can reach the studio is now a full operator.")
    return 0


def _status(args: argparse.Namespace) -> int:
    try:
        roster = load_roster(_roster_path(args))
    except RosterError as exc:
        print(f"ERROR: {exc}")
        return 1
    state = "enabled" if roster.enabled else "disabled"
    admins = len(roster.admins())
    print(
        f"Authentication is {state} — {len(roster.principals)} principal(s), "
        f"{admins} admin{'' if admins == 1 else 's'}."
    )
    return 0
