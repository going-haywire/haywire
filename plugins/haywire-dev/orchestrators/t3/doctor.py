#!/usr/bin/env python3
"""T3 Code's slot (ADR 0090): check the user's T3 setup against the checkout's ``t3.json``.

``--check`` lists what is missing; ``--fix`` backs up T3's settings file, then adds the missing
``t3.json`` scripts and sets their ``async``; ``--hook`` prints the check as ``session.sh``'s
lines. T3's settings file is internal and undocumented: one it does not recognise is left
untouched. Standard library only.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import sys
import time
from pathlib import Path

DOCS = "https://github.com/going-haywire/haywire/blob/master/docs/collaboration/orchestrators/t3.md#setup"
UNCHECKED = f"could not check the T3 settings, see {DOCS}"
NOT_IMPORTED = (
    "the t3.json scripts are not imported: *Project settings → Actions → Import scripts → Import from"
    f" t3.json*, not with `t3_project_update` (pingdotgg/t3code#14991), see {DOCS}"
)
CLEANUP = "*Settings → Worktrees → Cleanup*"


def settings_path() -> Path:
    return Path(os.environ.get("T3CODE_HOME") or Path.home() / ".t3") / "userdata" / "settings.json"


def manual_gaps(settings: dict) -> list[str]:
    """What the user sets in T3 by hand: worktree cleanup and branch naming."""
    cleanup = settings.get("storageCleanup", {})
    gaps = []
    if cleanup.get("worktreeOnMerge") is not True:
        gaps.append(f"{CLEANUP} → *Delete merged worktrees* is off")
    if cleanup.get("worktreeKeepWhen", "uncommitted-changes") != "uncommitted-changes":
        gaps.append(f"{CLEANUP} → *Keep worktrees with local changes* is not *Uncommitted changes*")
    if settings.get("branchNamingMode") != "semantic":
        gaps.append("*Settings → Worktrees → Branch naming* is not *semantic*")
    return gaps


def check(repo: Path) -> tuple[dict, list[dict], list[str], list[str]]:
    """Return the settings, the project's scripts, the fixable gaps and the manual ones.

    The project's scripts are the list holding ``t3.json``'s worktree setup command, ``[]`` if none.
    """
    path = settings_path()
    if not path.is_file():
        return {}, [], [], []
    try:
        settings = json.loads(path.read_text(encoding="utf-8"))
        manual = manual_gaps(settings)
        t3_json = repo / "t3.json"
        wanted = json.loads(t3_json.read_text(encoding="utf-8"))["scripts"] if t3_json.is_file() else []
        setup = next((w["command"] for w in wanted if w.get("runOnWorktreeCreate")), None)
        if setup is None:
            return settings, [], [], manual
        # Other projects' overrides may hold no scripts (only a model, say), or not be objects.
        overrides = settings["projectSettingsOverrides"].values()
        lists = [e.get("defaultProjectScripts") or [] for e in overrides if isinstance(e, dict)]
        scripts = next((s for s in lists if any(x.get("command") == setup for x in s)), None)
    except (OSError, ValueError, KeyError, TypeError, AttributeError):
        return {}, [], [], [UNCHECKED]
    if scripts is None:
        return settings, [], [], [NOT_IMPORTED, *manual]
    fixable = []
    for want in wanted:
        have = next((s for s in scripts if s.get("command") == want["command"]), None)
        if have is None:
            fixable.append(f"the T3 project lacks the t3.json script *{want['name']}*")
        elif "async" in want and have.get("async") != want["async"]:
            fixable.append(
                f"*{want['name']}* lacks `async: {json.dumps(want['async'])}`, which T3's import drops"
            )
    return settings, scripts, fixable, manual


def fix(repo: Path) -> None:
    settings, scripts, fixable, manual = check(repo)
    if fixable:
        path = settings_path()
        backup = path.with_name(f"{path.name}.{time.strftime('%Y%m%d-%H%M%S')}.bak")
        shutil.copy2(path, backup)
        for want in json.loads((repo / "t3.json").read_text(encoding="utf-8"))["scripts"]:
            have = next((s for s in scripts if s.get("command") == want["command"]), None)
            if have is None:
                scripts.append({"id": re.sub(r"[^a-z0-9]+", "-", want["name"].lower()).strip("-"), **want})
            elif "async" in want:
                have["async"] = want["async"]
        tmp = path.with_name(path.name + ".haywire-tmp")
        tmp.write_text(json.dumps(settings, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        shutil.copymode(path, tmp)
        os.replace(tmp, path)
        print(f"Backed up T3's settings to `{backup}`. Fixed:", *(f"- {g}" for g in fixable), sep="\n")
    else:
        print("Nothing to fix in T3's settings file.")
    if manual:
        print("Still to do by hand, in T3:", *(f"- {g}" for g in manual), sep="\n")


def hook(repo: Path, unfinished: int | None) -> None:
    """Print the agent's line and the developer's ``user: `` lines, nothing when the setup is complete."""
    _, _, fixable, manual = check(repo)
    if unfinished is not None:
        manual.insert(
            0,
            f"the worktree setup did not finish within {unfinished} s (if T3 never ran it, the t3.json"
            " scripts are not imported): run `python3 scripts/worktree_setup.py` in this worktree now",
        )
    gaps = [f"{g} [fix]" for g in fixable] + manual
    if not gaps:
        return
    line = "T3 setup is incomplete; pass this list to the user in your first reply, before other work: "
    line += "; ".join(gaps) + "."
    if fixable:
        line += (
            f" Offer to fix the [fix] items with `python3 {Path(__file__).resolve()} --fix` (it backs up"
            " T3's settings file first), and run it only on the user's yes."
        )
    print(line)
    print("user: T3 setup is incomplete:", *(f"user: - {g}" for g in gaps), sep="\n")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    mode = parser.add_mutually_exclusive_group(required=True)
    for flag in ("--check", "--fix", "--hook"):
        mode.add_argument(flag, action="store_true")
    parser.add_argument("--repo", type=Path, default=Path.cwd(), help="the checkout (default: here)")
    parser.add_argument("--setup-unfinished", type=int, help=argparse.SUPPRESS)
    args = parser.parse_args()
    if args.hook:
        hook(args.repo, args.setup_unfinished)
    elif args.fix:
        fix(args.repo)
    else:
        _, _, fixable, manual = check(args.repo)
        gaps = [f"{g} [--fix]" for g in fixable] + manual
        print(
            "The T3 setup lacks:" if gaps else "Nothing is missing in the T3 setup.",
            *(f"- {g}" for g in gaps),
            sep="\n",
        )
        return 1 if gaps else 0
    return 0


if __name__ == "__main__":
    sys.exit(main())
