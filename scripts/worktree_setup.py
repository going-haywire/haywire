#!/usr/bin/env python3
"""Make a fresh worktree of this repository ready to work in. Safe to run again.

Run it from inside the worktree, with the system Python (the worktree has no
environment yet):

    python3 scripts/worktree_setup.py

It does what a new checkout lacks:

1. Starts a branch without commits of its own from the latest ``origin/master``
   (a branch with commits is only reported as behind).
2. Builds the environment: ``uv sync`` as CI runs it.
3. Gives the worktree's studio a port of its own in ``.haywire/settings.json``,
   starting from a copy of the main checkout's settings.

To run the full studio with the libraries of the other repositories against this
worktree's code, use the umbrella environment beside the repositories (see its
README).

Standard library only: it runs before ``uv sync``.
"""

from __future__ import annotations

import json
import shutil
import socket
import subprocess
import sys
from collections.abc import Callable
from pathlib import Path

MAIN_STUDIO_PORT = 8124
FIRST_WORKTREE_PORT = MAIN_STUDIO_PORT + 1
SETTINGS = Path(".haywire") / "settings.json"


def studio_port(settings: dict) -> int | None:
    """The studio port a workspace settings document sets, if any."""
    port = settings.get("network", {}).get("port", {}).get("value")
    return port if isinstance(port, int) else None


def with_studio_port(settings: dict, port: int) -> dict:
    """A copy of ``settings`` with the studio port set, everything else kept."""
    updated = json.loads(json.dumps(settings))
    updated.setdefault("network", {})["port"] = {"value": port}
    return updated


def choose_studio_port(claimed: set[int], busy: Callable[[int], bool]) -> int:
    """The lowest port above the main studio's that no worktree claims and nothing listens on."""
    port = FIRST_WORKTREE_PORT
    while port in claimed or busy(port):
        port += 1
    return port


def _listening(port: int) -> bool:
    with socket.socket() as sock:
        sock.settimeout(0.2)
        return sock.connect_ex(("127.0.0.1", port)) == 0


def _git(*args: str, cwd: Path) -> str:
    return subprocess.run(["git", *args], cwd=cwd, check=True, capture_output=True, text=True).stdout.strip()


def _read_settings(checkout: Path) -> dict:
    try:
        return json.loads((checkout / SETTINGS).read_text())
    except (OSError, ValueError):
        return {}


def _worktrees(checkout: Path) -> list[Path]:
    porcelain = _git("worktree", "list", "--porcelain", cwd=checkout)
    return [Path(line.split(" ", 1)[1]) for line in porcelain.splitlines() if line.startswith("worktree ")]


def update_branch(checkout: Path) -> str:
    _git("fetch", "--quiet", "origin", "master", cwd=checkout)
    behind = int(_git("rev-list", "--count", "HEAD..origin/master", cwd=checkout))
    if behind == 0:
        return "branch: up to date with origin/master"
    own = int(_git("rev-list", "--count", "origin/master..HEAD", cwd=checkout))
    dirty = _git("status", "--porcelain", "--untracked-files=no", cwd=checkout)
    if own or dirty:
        return (
            f"branch: {own} commits not on origin/master, {behind} behind it; "
            "merge origin/master when the work needs it"
        )
    _git("merge", "--ff-only", "--quiet", "origin/master", cwd=checkout)
    return f"branch: fast-forwarded {behind} commits to origin/master"


def build_environment(checkout: Path) -> None:
    sync = ["uv", "sync", "--all-extras", "--dev", "--compile-bytecode", "--quiet"]
    subprocess.run(sync, cwd=checkout, check=True)


def assign_studio_port(checkout: Path, main: Path) -> str:
    own = _read_settings(checkout)
    if (port := studio_port(own)) is not None:
        return f"studio port: {port} (kept)"
    claimed = {studio_port(_read_settings(main)) or MAIN_STUDIO_PORT}
    for other in _worktrees(checkout):
        if other.resolve() not in (checkout, main) and (port := studio_port(_read_settings(other))):
            claimed.add(port)
    port = choose_studio_port(claimed, _listening)
    base = own or _read_settings(main)
    path = checkout / SETTINGS
    path.parent.mkdir(exist_ok=True)
    path.write_text(json.dumps(with_studio_port(base, port), indent=2) + "\n")
    return f"studio port: {port}"


def main() -> int:
    checkout = Path(_git("rev-parse", "--show-toplevel", cwd=Path.cwd())).resolve()
    common = Path(_git("rev-parse", "--path-format=absolute", "--git-common-dir", cwd=checkout))
    main_checkout = common.parent.resolve()
    if checkout == main_checkout:
        print("This is the main checkout; the script is for worktrees.")
        return 1
    if shutil.which("uv") is None:
        print("uv is not installed: https://docs.astral.sh/uv/")
        return 1
    print(update_branch(checkout))
    build_environment(checkout)
    print("environment: synced")
    print(assign_studio_port(checkout, main_checkout))
    return 0


if __name__ == "__main__":
    sys.exit(main())
