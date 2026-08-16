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
from haywire_studio.auth.roster import Principal, RosterError, save_roster
from haywire_studio.cli._guards import studio_is_running


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

    Thin wrapper over :func:`haywire_studio.cli._guards.studio_is_running` —
    kept as a module-level name because it is the seam tests patch.
    """
    return studio_is_running()


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
    """Report authentication, then any critical finding about this studio.

    Reads through the shared assessment rather than ``load_roster`` directly,
    for one reason: an unreadable roster used to ``return 1`` here, which
    skipped the security warning entirely. A studio reachable from the network
    with unusable authentication is precisely when that warning matters most,
    so no failure may sit between reading the roster and printing it.
    """
    from haywire_studio.network.security import assess

    posture = assess(roster_path=_roster_path(args))

    if posture.roster_error:
        # Headline only — the detail arrives below as a CRITICAL finding, with
        # a fix command attached. Printing the parse error twice would read as
        # two unrelated problems.
        print("Authentication state is UNKNOWN — the roster could not be read.")
    else:
        state = "enabled" if posture.auth_enabled else "disabled"
        admins = posture.admins
        print(
            f"Authentication is {state} — {posture.principals} principal(s), "
            f"{admins} admin{'' if admins == 1 else 's'}."
        )

    _print_findings(posture)
    return 1 if posture.roster_error else 0


def _print_findings(posture) -> None:
    """Print every CRITICAL the shared assessment found.

    Authentication alone cannot be assessed: 'disabled' is correct on loopback
    and dangerous when reachable, and a user who types ``auth status`` should
    not have to already know ``security status`` exists to learn which one they
    have. The wording comes from the shared assessment, never a second copy.

    Gated on severity ONLY, never on exposure. An earlier version returned
    early unless ``posture.exposed``, which silently swallowed every CRITICAL
    that is not about exposure — a broken TLS pair, an unreadable roster.
    Suppressing a CRITICAL because of an unrelated condition is the false
    negative this whole feature is built to avoid.
    """
    from haywire_studio.network.security import Severity

    relevant = [f for f in posture.findings if f.severity is Severity.CRITICAL]
    if not relevant:
        return

    if posture.reachable_by_others:
        print(f"\nThe studio is reachable at {posture.reachable_at or 'this machine'}:")
    else:
        print("\nThis studio has a critical problem:")
    for finding in relevant:
        print(f"  [CRITICAL] {finding.headline}")
        for line in finding.detail:
            print(f"      {line}")
        if finding.fix:
            print(f"      Fix: {finding.fix}")
    print("\nFull picture:  haywire security status")
