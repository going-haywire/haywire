"""``haywire ssl`` — serve the studio over HTTPS without knowing what a SAN is.

The whole point of this subcommand is that its users do not understand the
topic, so **the printing is the feature**, not decoration around it. Every
message states what is true, then names exactly one next command. In
particular ``setup`` pre-empts the browser warning: a user who meets a
full-page "not private" interstitial with no warning that it was coming
concludes the command failed.

Named ``sslcmd`` rather than ``ssl`` because ``ssl`` is a stdlib module and a
sibling of that name inside a package that imports it transitively is a trap
not worth setting — the same dodge ``authcmd`` makes.

``setup`` and ``update`` are guarded against a running studio: the settings
they write are read once at startup. ``status`` and ``trust`` are read-only and
deliberately unguarded — telling someone to quit the studio to find out why
HTTPS is broken is backwards.
"""

from __future__ import annotations

import argparse
from pathlib import Path

from haywire_studio.cli._guards import guard_running_studio
from haywire_studio.network.certs import CertError
from haywire_studio.network.tls_operations import (
    SetupResult,
    TlsState,
    TlsStatus,
    setup,
    status,
    trust_command,
    update,
)
from haywire_studio.network.tls_settings import (
    SettingsWriteError,
    workspace_overrides,
    workspace_path,
)

_GUARD_SUBJECT = "TLS configuration"


def register(subparsers: argparse._SubParsersAction) -> None:
    parser = subparsers.add_parser("ssl", help="Serve the studio over HTTPS (self-signed)")
    parser.add_argument(
        "--dir",
        default=None,
        help="Certificate directory (default: ~/.haywire/certs). Mainly for testing.",
    )
    actions = parser.add_subparsers(dest="ssl_command", required=True)

    create = actions.add_parser("setup", help="Create a certificate and configure the studio")
    create.add_argument(
        "--also",
        action="append",
        default=[],
        metavar="NAME",
        help="Extra hostname or IP the certificate should cover. Repeatable.",
    )
    create.set_defaults(handler=_setup)

    amend = actions.add_parser("update", help="Change which names the certificate covers")
    amend.add_argument("--add", action="append", default=[], metavar="NAME", help="Add a name.")
    amend.add_argument("--remove", action="append", default=[], metavar="NAME", help="Remove a name.")
    amend.add_argument(
        "--refresh",
        action="store_true",
        help="Re-detect this machine's addresses and add them (use after changing networks).",
    )
    amend.set_defaults(handler=_update)

    report = actions.add_parser("status", help="Show the current TLS setup")
    report.set_defaults(handler=_status)

    trust = actions.add_parser("trust", help="Show how to make this machine trust the certificate")
    trust.set_defaults(handler=_trust)


def _directory(args: argparse.Namespace) -> Path | None:
    raw = getattr(args, "dir", None)
    return Path(raw) if raw else None


def _setup(args: argparse.Namespace) -> int:
    if guard_running_studio(_GUARD_SUBJECT):
        return 1
    try:
        result = setup(getattr(args, "also", []), directory=_directory(args))
    except (CertError, SettingsWriteError) as exc:
        print(f"ERROR: {exc}")
        return 1

    if result.adopted:
        print("Found an existing certificate and configured the studio to use it.")
        print("  (The certificate itself was left untouched.)\n")
    else:
        print("Certificate created and configured.\n")

    _print_summary(result)
    _warn_if_shadowed()
    print("\nRestart the studio, then visit https://… (note the s).")
    print(_BROWSER_WARNING)
    return 0


def _update(args: argparse.Namespace) -> int:
    if guard_running_studio(_GUARD_SUBJECT):
        return 1
    try:
        result = update(
            add=getattr(args, "add", []),
            remove=getattr(args, "remove", []),
            refresh=getattr(args, "refresh", False),
            directory=_directory(args),
        )
    except (CertError, SettingsWriteError) as exc:
        print(f"ERROR: {exc}")
        return 1

    print("Certificate updated (the private key was reused).\n")
    _print_summary(result)
    _warn_if_shadowed()
    # Trust stores pin the certificate, not the key, so re-signing invalidates
    # every previous 'ssl trust'. Saying so is mandatory: otherwise the user
    # meets the interstitial again and believes the command failed.
    print(
        "\nAnyone who ran 'haywire ssl trust' must run it again — trust stores\n"
        "pin the certificate, and this is a new one."
    )
    return 0


def _status(args: argparse.Namespace) -> int:
    """Always exits 0. ``status`` reports; it does not judge."""
    result = status(directory=_directory(args))
    printer = _PRINTERS.get(result.state, _print_generic)
    printer(result)
    return 0


def _trust(args: argparse.Namespace) -> int:
    directory = _directory(args)
    result = status(directory=directory)
    # An orphan has files on disk that nothing points at — trustable, so it is
    # not "no certificate yet". Split from the configured check because the two
    # reasons to continue are unrelated.
    if not result.configured:
        if result.state is not TlsState.ORPHANED:
            print("No certificate yet. Run 'haywire ssl setup' first.")
            return 1

    print("To make this machine trust the studio certificate, run:\n")
    print(f"  {trust_command(directory)}\n")
    print("You will be asked for your password — the command changes a system")
    print("trust store, which is why Haywire does not run it for you.")
    if result.fingerprint:
        print(f"\nFingerprint (SHA-256):\n  {result.fingerprint}")
    return 0


# ---------------------------------------------------------------------------
# Output
# ---------------------------------------------------------------------------

_BROWSER_WARNING = """
Your browser will show a warning the first time — "not private", or
"unknown issuer". That is expected: the certificate is signed by this
machine rather than by a company browsers already trust. The connection
is fully encrypted either way.

  To make the warning go away:  haywire ssl trust
  To use it as-is:              click "Advanced" and continue"""


def _warn_if_shadowed() -> None:
    """Say so when the workspace tier will win over what was just written.

    Settings resolve workspace-over-global and these commands write global, so
    without this the command reports success and the studio then refuses to
    start on a path the user was never shown.
    """
    shadowed = workspace_overrides("ssl_certfile", "ssl_keyfile")
    if not shadowed:
        return
    print(
        f"\nWARNING: {workspace_path()} also sets "
        f"{' and '.join(shadowed)}.\n"
        "  Workspace settings win over the global ones just written, so the studio\n"
        "  will keep using the workspace values. Remove them from that file for\n"
        "  this certificate to take effect."
    )


def _print_summary(result: SetupResult) -> None:
    print(f"  Covers:  {_names(result.covered)}")
    print(f"  Expires: {result.expires:%Y-%m-%d}")
    print(f"  Key:     {result.key_path}   (private — never share this file)")


def _names(covered) -> str:
    return ", ".join([*covered.dns, *covered.ip]) or "(nothing)"


def _print_off_loopback(result: TlsStatus) -> None:
    """A correct configuration. No warning wording, no fix command — saying
    otherwise trains users to ignore this command (D7)."""
    print("TLS is not configured — the studio serves plain HTTP.\n")
    print("  Reachable at: 127.0.0.1 (loopback only)\n")
    print("That is fine for local use. Traffic never leaves this machine,")
    print("so there is nothing to encrypt.\n")
    print("If you later expose the studio to your network, run:")
    print("  haywire ssl setup")


def _print_off_exposed(result: TlsStatus) -> None:
    """Plain HTTP with ``expose_to_network`` on.

    ``TlsState`` only knows the bind address, so this state does NOT by itself
    mean anyone can connect: the allowlist may reject every remote peer. Asking
    the shared assessment rather than re-deriving it here is what keeps this
    command from warning about traffic that cannot happen — the same false
    positive ``security status`` was built to avoid.
    """
    print("TLS is not configured — the studio serves plain HTTP.\n")
    print(f"  Reachable at:      {result.reachable_at or 'this machine'}")
    print("  expose_to_network: on\n")

    if not _reachable_by_others():
        print("The allowlist is empty, so every remote address is rejected and")
        print("only loopback can connect. Nothing crosses the network today, so")
        print("there is nothing to encrypt yet.\n")
        print("Before opening it up (adding 'allowed_remote_ranges'), run:")
        print("  haywire ssl setup")
        return

    print("What that means right now:")
    print("  - Passwords, session cookies and agent tokens travel unencrypted")
    print("    on your network. Anyone who can observe one request can replay it.\n")
    print("  Fix:  haywire ssl setup")


def _reachable_by_others() -> bool:
    """Whether any machine but this one can open a connection.

    Delegates to :mod:`haywire_studio.network.security` so the reachability
    rule lives in exactly one place. A second copy here is how the two commands
    would drift into disagreeing about the same studio.
    """
    from haywire_studio.network.security import assess

    return assess().reachable_by_others


def _print_ok(result: TlsStatus) -> None:
    print("TLS is configured.\n")
    print(f"  Certificate: {result.certfile}")
    print(f"  Covers:      {_names(result.covered)}")
    if result.expires:
        print(f"  Expires:     {result.expires:%Y-%m-%d}")
    if result.reachable_at:
        print(f"  Reachable here as {result.reachable_at} — covered\n")
    print("Browsers will still warn unless this machine trusts the certificate:")
    print("  haywire ssl trust")


def _print_not_covered(result: TlsStatus) -> None:
    print("TLS is configured, but does not cover this network.\n")
    print(f"  Covers:            {_names(result.covered)}")
    print(f"  Reachable here as: {result.reachable_at} — NOT covered\n")
    print("Browsers will reject the certificate at this address even if you")
    print("have trusted it before.\n")
    print("  Add this network:  haywire ssl update --refresh")
    alternative = result.covered_alternative()
    if alternative:
        # Often no action is needed at all — the .local name still resolves.
        # Saying so beats making the user re-run a command (D6).
        print(f"\n  Note: {alternative} IS covered — if mDNS works on this")
        print(f"  network, https://{alternative}:8124 works right now with no change.")


def _print_orphaned(result: TlsStatus) -> None:
    print("A certificate exists but is not configured — the studio serves plain HTTP.\n")
    print(f"  {result.detail}\n")
    print("  Wire it up:  haywire ssl setup")


def _print_half_configured(result: TlsStatus) -> None:
    print("TLS is half-configured — the studio will refuse to start.\n")
    print(f"  {result.detail}\n")
    print("Set both 'ssl_certfile' and 'ssl_keyfile' under Network settings, or neither.")
    print("  Recreate both:  haywire ssl setup")


def _print_file_missing(result: TlsStatus) -> None:
    print("TLS is configured, but a file is missing — the studio will refuse to start.\n")
    print(f"  {result.detail}\n")
    # Name the file that actually holds the value. Pointing at the global file
    # when the workspace tier is the one winning sends the user to edit a
    # setting that was never in force.
    shadowed = workspace_overrides("ssl_certfile", "ssl_keyfile")
    source = workspace_path() if shadowed else "~/.haywire/settings.json"
    if shadowed:
        print(f"  That value comes from {source} (workspace settings win).\n")
    print("  Recreate:  haywire ssl setup")
    print(f"  Or clear:  remove ssl_certfile / ssl_keyfile from {source}")


def _print_key_mismatch(result: TlsStatus) -> None:
    print("The key and certificate do not match — the studio will refuse to start.\n")
    print(f"  {result.detail}\n")
    print("  Make a new pair:  haywire ssl setup")


def _print_unreadable(result: TlsStatus) -> None:
    print("The certificate could not be read — the studio will refuse to start.\n")
    print(f"  {result.detail}\n")
    print("  Make a new one:  haywire ssl setup")


def _print_expiring(result: TlsStatus) -> None:
    print("TLS is configured, but the certificate is about to expire.\n")
    print(f"  Covers:  {_names(result.covered)}")
    print(f"  {result.detail}\n")
    print("  Renew:  haywire ssl update --refresh")


def _print_generic(result: TlsStatus) -> None:
    print(f"TLS status: {result.state.value}")
    if result.detail:
        print(f"  {result.detail}")


_PRINTERS = {
    TlsState.OFF_LOOPBACK: _print_off_loopback,
    TlsState.OFF_EXPOSED: _print_off_exposed,
    TlsState.OK: _print_ok,
    TlsState.NOT_COVERED: _print_not_covered,
    TlsState.ORPHANED: _print_orphaned,
    TlsState.HALF_CONFIGURED: _print_half_configured,
    TlsState.FILE_MISSING: _print_file_missing,
    TlsState.KEY_MISMATCH: _print_key_mismatch,
    TlsState.UNREADABLE: _print_unreadable,
    TlsState.EXPIRING: _print_expiring,
}
