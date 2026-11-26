#!/usr/bin/env python3
"""Start, stop or report the studio of the checkout or worktree you are in: one rule for core
and the org libraries, for people, agents and every orchestrator. In core:

    python3 dev/scripts/studio.py start [options of haywire studio start, e.g. --browser]
    python3 dev/scripts/studio.py stop
    python3 dev/scripts/studio.py status

In an org library, through core beside it (the worktree setup links it beside a worktree):

    python3 ../haywire-repo/dev/scripts/studio.py start

``start`` runs the full studio, every library of every repository, when the umbrella's
``haywire-studio`` is on the ``PATH`` (ADR 0081: in a worktree its own packages replace the
umbrella's copies for the run). Without it, the studio runs from the checkout's own
environment: core, or core and this library, with the libraries of other repositories
missing. It prints which of the two it started. ``stop`` and ``status`` read the folder's
studio files, so the checkout's own environment serves them either way.

Standard library only, like the other scripts here.
"""

from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

UMBRELLA = "haywire-studio"
ACTIONS = ("start", "stop", "status")
FULL = "studio: the full studio, every library (the umbrella's haywire-studio)"
OWN = (
    "studio: this checkout's environment only; libraries from other repositories are missing "
    "(link the umbrella's bin/haywire-studio onto the PATH for the full studio)"
)


def command(action: str, args: list[str], umbrella: str | None) -> tuple[list[str], str | None]:
    """The command that runs ``action`` and the line saying which studio ``start`` starts.

    Args:
        action: One of ``ACTIONS``.
        args: Further arguments for ``haywire studio <action>``.
        umbrella: The path of ``haywire-studio`` when it is on the ``PATH``, else ``None``.

    Returns:
        The argv, and for ``start`` the line to print first (``None`` for the others).
    """
    own = ["uv", "run", "--frozen", "haywire", "studio", action, *args]
    if action != "start":
        return own, None
    if umbrella is not None:
        return [umbrella, "studio", action, *args], FULL
    return own, OWN


def main(argv: list[str]) -> int:
    if not argv or argv[0] not in ACTIONS:
        print(f"usage: studio.py {{{'|'.join(ACTIONS)}}} [options of haywire studio]")
        return 2
    try:
        root = subprocess.run(
            ["git", "rev-parse", "--show-toplevel"], check=True, capture_output=True, text=True
        ).stdout.strip()
    except (OSError, subprocess.CalledProcessError):
        print("studio.py: run it inside a haywire or haybale checkout or worktree.")
        return 1
    argv_, note = command(argv[0], argv[1:], shutil.which(UMBRELLA))
    if note:
        print(note, flush=True)
    return subprocess.run(argv_, cwd=Path(root)).returncode


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
