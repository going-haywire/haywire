#!/usr/bin/env python3
"""T3 Code's slot (ADR 0090): check T3's own settings that the task flow relies on.

``--check`` lists what is missing; ``--hook`` prints the check as ``session.sh``'s lines. Only T3's
global settings are checked (worktree cleanup, branch naming): whether a project's ``t3.json``
scripts are imported, T3 shows itself (*Import scripts*). T3's settings file is internal and
undocumented: one it does not recognise is reported, never changed. Standard library only.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

DOCS = "https://github.com/going-haywire/haywire/blob/master/docs/collaboration/orchestrators/t3.md#setup"
UNCHECKED = f"could not check the T3 settings, see {DOCS}"
CLEANUP = "*Settings → Worktrees → Cleanup*"


def settings_path() -> Path:
    return Path(os.environ.get("T3CODE_HOME") or Path.home() / ".t3") / "userdata" / "settings.json"


def check() -> list[str]:
    """What the user still sets in T3: worktree cleanup and branch naming."""
    path = settings_path()
    if not path.is_file():
        return []
    try:
        settings = json.loads(path.read_text(encoding="utf-8"))
        cleanup = settings.get("storageCleanup", {})
        gaps = []
        if cleanup.get("worktreeOnMerge") is not True:
            gaps.append(f"{CLEANUP} → *Delete merged worktrees* is off")
        if cleanup.get("worktreeKeepWhen", "uncommitted-changes") != "uncommitted-changes":
            gaps.append(f"{CLEANUP} → *Keep worktrees with local changes* is not *Uncommitted changes*")
        if settings.get("branchNamingMode") != "semantic":
            gaps.append("*Settings → Worktrees → Branch naming* is not *semantic*")
    except (OSError, ValueError, AttributeError):
        return [UNCHECKED]
    return gaps


def setup_command(repo: Path) -> str:
    """Return ``t3.json``'s worktree setup command, or core's when ``t3.json`` names none."""
    try:
        wanted = json.loads((repo / "t3.json").read_text(encoding="utf-8"))["scripts"]
        return next(w["command"] for w in wanted if w.get("runOnWorktreeCreate"))
    except (OSError, ValueError, KeyError, StopIteration):
        return "python3 scripts/worktree_setup.py"


def hook(repo: Path, unfinished: int | None) -> None:
    """Print the agent's line and the developer's ``user: `` lines, nothing when the setup is complete."""
    gaps = check()
    if unfinished is not None:
        gaps.insert(
            0,
            f"the worktree setup did not finish within {unfinished} s (if T3 never ran it, the t3.json"
            f" scripts are not imported): run `{setup_command(repo)}` in this worktree now",
        )
    if not gaps:
        return
    line = "T3 setup is incomplete; pass this list to the user in your first reply, before other work: "
    line += "; ".join(gaps) + f". See {DOCS}."
    print(line)
    print("user: T3 setup is incomplete:", *(f"user: - {g}" for g in gaps), sep="\n")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    mode = parser.add_mutually_exclusive_group(required=True)
    for flag in ("--check", "--hook"):
        mode.add_argument(flag, action="store_true")
    parser.add_argument("--repo", type=Path, default=Path.cwd(), help="the checkout (default: here)")
    parser.add_argument("--setup-unfinished", type=int, help=argparse.SUPPRESS)
    args = parser.parse_args()
    if args.hook:
        hook(args.repo, args.setup_unfinished)
    else:
        gaps = check()
        print(
            "The T3 setup lacks:" if gaps else "Nothing is missing in the T3 setup.",
            *(f"- {g}" for g in gaps),
            sep="\n",
        )
        return 1 if gaps else 0
    return 0


if __name__ == "__main__":
    sys.exit(main())
