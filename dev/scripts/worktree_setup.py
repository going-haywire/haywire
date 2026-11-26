#!/usr/bin/env python3
"""Make a fresh worktree of an org repository ready to work in. Safe to run again.

The neutral part of a task's "created" event (ADR 0090): an orchestrator runs it in every
worktree it creates, with the system Python (the worktree has no environment yet). In core:

    python3 scripts/worktree_setup.py

In an org library, through the library's main folder, wherever the worktree is
(``$main`` being ``git rev-parse --path-format=absolute --git-common-dir``):

    python3 "$main/../../haywire-repo/dev/scripts/worktree_setup.py"

It does what a new checkout lacks:

1. Starts a branch without commits of its own from the latest default branch of ``origin``
   (a branch with commits is only reported as behind).
2. In a library, links core beside the worktree (``../haywire-repo``) when the worktree is not
   already beside it, so the library's ``pyproject.toml`` and its committed hooks find core.
3. Builds the environment: ``uv sync`` as CI runs it (``--frozen`` in a library, whose lock
   stays as committed).
4. Gives the worktree's studio a port of its own in ``.haywire/settings.json``, starting from
   a copy of the main checkout's settings (``haywire studio start`` moves it again if another
   folder's studio holds it). The copy leaves out the haystack the main studio reopens, so a
   worktree's studio starts with no graph open.
5. Writes ``haywire-setup-done`` into the worktree's git folder last, which an orchestrator's
   session-start slot waits for (outside the checkout, so no repository sees it). It writes
   ``haywire-setup-started`` there first, so the slot waits only while a setup runs.

``--lead <link>`` also records the task's lead (a T3 thread link, a herdr address) in
``haywire-lead`` in the worktree's git folder, which the session-start slot reads back. Where
a setup already ran or is running, it only records the lead.

Standard library only: it runs before ``uv sync``.
"""

from __future__ import annotations

import argparse
import json
import shutil
import socket
import subprocess
import sys
from collections.abc import Callable
from pathlib import Path

CORE = "haywire-repo"
STARTED = "haywire-setup-started"
DONE = "haywire-setup-done"
LEAD = "haywire-lead"
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


def without_open_haystack(settings: dict) -> dict:
    """A copy of ``settings`` without the haystack the studio reopens at startup."""
    updated = json.loads(json.dumps(settings))
    haystack = updated.get("haystack")
    if not isinstance(haystack, dict):
        return updated
    haystack.pop("last_haystack_name", None)
    if not haystack:
        updated.pop("haystack", None)
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


def default_branch(checkout: Path) -> str:
    """Return ``origin``'s default branch, from the clone's record or else from ``origin`` itself."""
    try:
        return _git("symbolic-ref", "--short", "refs/remotes/origin/HEAD", cwd=checkout).split("/", 1)[1]
    except subprocess.CalledProcessError:
        pass
    # A clone made by `git remote add` has no record of the remote's HEAD.
    for line in _git("ls-remote", "--symref", "origin", "HEAD", cwd=checkout).splitlines():
        if line.startswith("ref: refs/heads/"):
            return line.split()[1].removeprefix("refs/heads/")
    return "master"


def update_branch(checkout: Path) -> str:
    branch = default_branch(checkout)
    _git("fetch", "--quiet", "origin", branch, cwd=checkout)
    behind = int(_git("rev-list", "--count", f"HEAD..origin/{branch}", cwd=checkout))
    if behind == 0:
        return f"branch: up to date with origin/{branch}"
    own = int(_git("rev-list", "--count", f"origin/{branch}..HEAD", cwd=checkout))
    dirty = _git("status", "--porcelain", "--untracked-files=no", cwd=checkout)
    if own or dirty:
        return (
            f"branch: {own} commits not on origin/{branch}, {behind} behind it; "
            f"merge origin/{branch} when the work needs it"
        )
    _git("merge", "--ff-only", "--quiet", f"origin/{branch}", cwd=checkout)
    return f"branch: fast-forwarded {behind} commits to origin/{branch}"


def core_link(checkout: Path, main: Path) -> tuple[Path, Path] | None:
    """Return the link to make as ``(link, core)``, or ``None`` when none is needed.

    None is needed in core itself, when the worktree already sits beside core, or when the
    main folder has no core beside it either.
    """
    if (checkout / "dev" / "scripts" / "worktree_setup.py").is_file():
        return None
    core = main.parent / CORE
    link = checkout.parent / CORE
    if not core.is_dir() or link.exists() or link.is_symlink():
        return None
    return link, core


def _read_settings(checkout: Path) -> dict:
    try:
        return json.loads((checkout / SETTINGS).read_text())
    except (OSError, ValueError):
        return {}


def _worktrees(checkout: Path) -> list[Path]:
    porcelain = _git("worktree", "list", "--porcelain", cwd=checkout)
    return [Path(line.split(" ", 1)[1]) for line in porcelain.splitlines() if line.startswith("worktree ")]


def assign_studio_port(checkout: Path, main: Path) -> str:
    own = _read_settings(checkout)
    if (port := studio_port(own)) is not None:
        return f"studio port: {port} (kept)"
    claimed = {studio_port(_read_settings(main)) or MAIN_STUDIO_PORT}
    for other in _worktrees(checkout):
        if other.resolve() not in (checkout, main) and (port := studio_port(_read_settings(other))):
            claimed.add(port)
    port = choose_studio_port(claimed, _listening)
    base = own or without_open_haystack(_read_settings(main))
    path = checkout / SETTINGS
    path.parent.mkdir(exist_ok=True)
    # Core's helper (ensure_haywire_dir, ADR 0096) is not importable before uv sync.
    gitignore = path.parent / ".gitignore"
    if not gitignore.exists():
        gitignore.write_text("*\n")
    path.write_text(json.dumps(with_studio_port(base, port), indent=2) + "\n")
    return f"studio port: {port}"


def write_lead(git_dir: Path, lead: str) -> None:
    """Record ``lead`` as the worktree's lead, in its git folder."""
    (git_dir / LEAD).write_text(lead.strip() + "\n")


def read_lead(git_dir: Path) -> str | None:
    """The lead recorded for the worktree, or ``None`` when there is none."""
    try:
        return (git_dir / LEAD).read_text().strip() or None
    except OSError:
        return None


def build_environment(checkout: Path, *, library: bool) -> None:
    sync = ["uv", "sync", "--all-extras", "--dev", "--compile-bytecode", "--quiet"]
    # A library's lock records the core release it was locked against, while its development
    # project builds against the core clone; --frozen leaves the lock as committed.
    subprocess.run([*sync, "--frozen"] if library else sync, cwd=checkout, check=True)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--lead", help="the lead's T3 thread link or herdr address, to record")
    args = parser.parse_args(argv)
    checkout = Path(_git("rev-parse", "--show-toplevel", cwd=Path.cwd())).resolve()
    common = Path(_git("rev-parse", "--path-format=absolute", "--git-common-dir", cwd=checkout))
    main_checkout = common.parent.resolve()
    if checkout == main_checkout:
        print("This is the main checkout; the script is for worktrees.")
        return 1
    git_dir = Path(_git("rev-parse", "--path-format=absolute", "--git-dir", cwd=checkout))
    if args.lead:
        write_lead(git_dir, args.lead)
        print(f"lead: {read_lead(git_dir)}")
        if (git_dir / STARTED).exists() or (git_dir / DONE).exists():
            return 0
    if shutil.which("uv") is None:
        print("uv is not installed: https://docs.astral.sh/uv/")
        return 1
    (git_dir / STARTED).write_text("")
    print(update_branch(checkout))
    if (link := core_link(checkout, main_checkout)) is not None:
        link[0].symlink_to(link[1], target_is_directory=True)
        print(f"core: linked {link[0]} -> {link[1]}")
    library = not (checkout / "dev" / "scripts" / "worktree_setup.py").is_file()
    build_environment(checkout, library=library)
    print("environment: synced")
    print(assign_studio_port(checkout, main_checkout))
    (git_dir / DONE).write_text("")
    return 0


if __name__ == "__main__":
    sys.exit(main())
