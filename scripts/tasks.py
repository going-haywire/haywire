#!/usr/bin/env python3
"""List the tasks in flight: every worktree beside the main folder, with its pull request and agent.

A task is a branch in its own worktree. Nothing is stored: the view is derived from
``git worktree list`` in each repository folder beside the main folder, ``gh pr list`` for
the branch's pull request, and, when ``hc`` is present, the agent session whose working
folder is the worktree. A repository's main folder on its default branch is not a task; a
worktree left detached (after ``finish``) is listed so the leftover shows.

Usage::

    uv run python scripts/tasks.py
    uv run python scripts/tasks.py --json
    uv run python scripts/tasks.py --root /path/to/folder/holding/the/repositories

Each line reads ``<repo> / <branch> (<address>) · #<pr> <state> · checks <✓|✗|…> · <agent status>``,
followed by ``dirty``, ``ahead N`` or ``behind N`` against the branch's upstream when they apply.
Without ``gh`` or without network the pull request reads ``pr unknown``; without ``hc`` the
agent part is left out.

Output is ``key: value`` lines on stdout, errors included (``error:`` then ``help:``).
Exit codes: 0 listed, 1 a command failed, 2 usage.
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

DEFAULT_BRANCHES = frozenset({"master", "main"})
SHELLS = frozenset({"zsh", "bash", "fish", "sh"})
PR_FIELDS = "number,state,isDraft,url,mergeable,statusCheckRollup"
PASSING = frozenset({"SUCCESS", "SKIPPED", "NEUTRAL"})


class CommandFailed(Exception):
    """A git command failed; its message says which and why."""


@dataclass(frozen=True)
class Worktree:
    path: Path
    branch: str | None
    """Short branch name, or ``None`` for a detached checkout."""
    is_main: bool


def run(*cmd: str, cwd: Path | None = None) -> str:
    try:
        proc = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, check=False, timeout=60)
    except (FileNotFoundError, subprocess.TimeoutExpired) as exc:
        raise CommandFailed(f"{cmd[0]}: {exc}") from exc
    if proc.returncode != 0:
        raise CommandFailed(f"`{' '.join(cmd)}` failed: {proc.stderr.strip()}")
    return proc.stdout


# --- repositories and worktrees ----------------------------------------------


def default_root() -> Path:
    """Return the folder holding the repositories: the parent of this repository's main folder."""
    common = Path(run("git", "rev-parse", "--path-format=absolute", "--git-common-dir").strip())
    return common.parent.parent.resolve()


def repositories(root: Path) -> list[Path]:
    """Return the main folders directly under *root*: those whose ``.git`` is a directory."""
    return sorted(p for p in root.iterdir() if (p / ".git").is_dir())


def worktrees(repo: Path) -> list[Worktree]:
    """Return every worktree of *repo*, the main folder first."""
    found: list[Worktree] = []
    for index, block in enumerate(
        run("git", "worktree", "list", "--porcelain", cwd=repo).strip().split("\n\n")
    ):
        fields = dict(line.partition(" ")[::2] for line in block.splitlines())
        if "prunable" in fields or "bare" in fields:
            continue
        branch = fields.get("branch", "")
        found.append(
            Worktree(
                path=Path(fields["worktree"]).resolve(),
                branch=branch.removeprefix("refs/heads/") if branch else None,
                is_main=index == 0,
            )
        )
    return found


def tasks_of(repo: Path) -> list[Worktree]:
    """Return the worktrees of *repo* that are tasks."""
    return [
        w for w in worktrees(repo) if not (w.is_main and (w.branch is None or w.branch in DEFAULT_BRANCHES))
    ]


def slug_of(repo: Path) -> str | None:
    """Return ``owner/name`` of the repository's ``origin``, or ``None`` when it is not on GitHub."""
    try:
        url = run("git", "config", "--get", "remote.origin.url", cwd=repo).strip()
    except CommandFailed:
        return None
    match = re.search(r"github\.com[:/]([^/]+/[^/]+?)(?:\.git)?/?$", url)
    return match.group(1) if match else None


def state_of(tree: Worktree) -> dict:
    """Return whether the worktree is dirty and how far its branch is ahead of and behind its upstream."""
    dirty = bool(run("git", "status", "--porcelain", cwd=tree.path).strip())
    state: dict = {"dirty": dirty, "ahead": 0, "behind": 0, "upstream": False}
    if tree.branch:
        try:
            counts = run("git", "rev-list", "--left-right", "--count", "@{upstream}...HEAD", cwd=tree.path)
        except CommandFailed:
            return state
        behind, ahead = counts.split()
        state.update(ahead=int(ahead), behind=int(behind), upstream=True)
    return state


# --- pull requests and agents ------------------------------------------------


def checks_summary(rollup: list[dict]) -> str | None:
    """Return ``pass``, ``fail`` or ``pending`` for a status check rollup, ``None`` when it is empty."""
    if not rollup:
        return None
    verdicts = []
    for check in rollup:
        if check.get("status", "COMPLETED") != "COMPLETED":
            verdicts.append("pending")
        else:
            outcome = check.get("conclusion") or check.get("state") or ""
            verdicts.append("pass" if outcome in PASSING else "fail")
    if "fail" in verdicts:
        return "fail"
    return "pending" if "pending" in verdicts else "pass"


def pull_request(slug: str | None, branch: str) -> dict | None:
    """Return the branch's newest pull request, ``{}`` when there is none, ``None`` when gh cannot say."""
    if slug is None:
        return None
    try:
        raw = run(
            "gh", "pr", "list", "--repo", slug, "--head", branch, "--state", "all", "--json", PR_FIELDS
        )
        prs = json.loads(raw)
    except (CommandFailed, json.JSONDecodeError):
        return None
    if not prs:
        return {}
    pr = max(prs, key=lambda p: p["number"])
    state = "draft" if pr.get("isDraft") and pr["state"] == "OPEN" else pr["state"].lower()
    return {
        "number": pr["number"],
        "state": state,
        "checks": checks_summary(pr.get("statusCheckRollup") or []),
        "mergeable": pr.get("mergeable", "UNKNOWN").lower(),
        "url": pr["url"],
    }


def agents() -> dict[Path, dict]:
    """Return ``{working folder: agent}`` of the live ``hc`` terminals, empty without ``hc``."""
    try:
        terminals = json.loads(run("hc", "ls", "--json")).get("terminals", [])
    except (CommandFailed, json.JSONDecodeError, AttributeError):
        return {}
    found: dict[Path, dict] = {}
    for terminal in terminals:
        if terminal.get("state") != "live" or terminal.get("agent") in SHELLS:
            continue
        folder = Path(terminal.get("cwd", "")).resolve()
        found.setdefault(folder, terminal)
    return found


# --- the view ----------------------------------------------------------------


def collect(root: Path) -> list[dict]:
    """Return one row per task under *root*."""
    live = agents()
    rows: list[dict] = []
    for repo in repositories(root):
        try:
            trees = tasks_of(repo)
        except CommandFailed:
            continue
        slug = slug_of(repo)
        for tree in trees:
            pr = pull_request(slug, tree.branch) if tree.branch else {}
            agent = live.get(tree.path)
            rows.append(
                {
                    "repo": repo.name,
                    "branch": tree.branch,
                    "path": str(tree.path),
                    "pr": pr,
                    "agent": agent and {"address": agent["address"], "status": agent.get("status", "")},
                    **state_of(tree),
                }
            )
    return rows


def describe(row: dict) -> str:
    """Return the one-line reading of a task row."""
    name = f"{row['repo']} / {row['branch'] or '(detached, empty)'}"
    if row["agent"]:
        name += f" ({row['agent']['address']})"
    parts = [name]
    pr = row["pr"]
    if pr is None:
        parts.append("pr unknown")
    elif not pr:
        parts.append("no PR")
    else:
        parts.append(f"#{pr['number']} {pr['state']}")
        if pr["checks"]:
            parts.append("checks " + {"pass": "✓", "fail": "✗", "pending": "…"}[pr["checks"]])
        if pr["mergeable"] == "conflicting":
            parts.append("conflicts")
    if row["agent"] and row["agent"]["status"]:
        parts.append(row["agent"]["status"])
    if row["dirty"]:
        parts.append("dirty")
    if row["ahead"]:
        parts.append(f"ahead {row['ahead']}")
    if row["behind"]:
        parts.append(f"behind {row['behind']}")
    if row["branch"] and not row["upstream"]:
        parts.append("not pushed")
    return " · ".join(parts)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument(
        "--root", type=Path, help="the folder holding the repositories (default: beside this repository)"
    )
    parser.add_argument("--json", action="store_true", help="one JSON object on stdout")
    args = parser.parse_args(argv)

    try:
        root = (args.root or default_root()).resolve()
        if not root.is_dir():
            print(f"error: {root} is not a folder\nhelp: pass the folder that holds the repositories")
            return 1
        rows = collect(root)
    except CommandFailed as exc:
        print(f"error: {exc}")
        return 1
    if args.json:
        print(json.dumps({"tasks": rows}, indent=2))
    elif not rows:
        print(f"tasks: 0 (no worktree besides a main folder on its default branch under {root})")
    else:
        print(f"tasks[{len(rows)}]:")
        for row in rows:
            print(f"  {describe(row)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
