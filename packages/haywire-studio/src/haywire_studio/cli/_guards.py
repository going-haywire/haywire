"""Preconditions shared by the subcommands that change startup-time config.

Lives here rather than in one subcommand module because two of them need the
same check and two copies would drift.
"""

from __future__ import annotations

from pathlib import Path


def studio_is_running() -> bool:
    """True when this workspace has a live studio process.

    Best-effort, via the sidecar the studio writes when it mounts Farmhand. It
    cannot see a studio running for a *different* workspace against the same
    global config — that case is handled by atomic writes, which make a
    concurrent write last-one-wins rather than corrupting.
    """
    from haywire_studio.farmhand.identity import identity_status, read_identity

    ident = read_identity(Path.cwd())
    return ident is not None and identity_status(ident) == "alive"


def guard_running_studio(subject: str) -> bool:
    """Print and return True when a running studio blocks this change.

    *subject* names what is read once at startup, e.g. ``"Authentication"`` or
    ``"TLS configuration"``.
    """
    if studio_is_running():
        print(
            f"ERROR: a studio is running in this workspace.\n"
            f"  {subject} is read once at startup, so it must be changed with the studio stopped.\n"
            "  Quit the studio and run this again."
        )
        return True
    return False
