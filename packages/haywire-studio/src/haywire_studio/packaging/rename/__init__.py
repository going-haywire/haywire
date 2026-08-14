"""``haywire rename`` — rename a project-local haybale library.

Renaming changes a library's IDENTITY only: its distribution name, module
name, and the registry-key prefix stamped into every saved graph.
Descriptive metadata (label, description, tags, homepage_url, notes) and
its dependents' references to it are preserved.
"""

from __future__ import annotations

from pathlib import Path

from .execute import execute_plan
from .model import Blocker, FileChange, Occurrence, RenamePlan, Warning_
from .planner import plan_rename
from .report import render_plan

__all__ = [
    "Blocker",
    "FileChange",
    "Occurrence",
    "RenamePlan",
    "Warning_",
    "execute_plan",
    "plan_rename",
    "render_plan",
    "run_rename_cli",
]


def _confirm(question: str) -> bool:
    try:
        return input(f"{question} [y/N] ").strip().lower() in ("y", "yes")
    except (EOFError, KeyboardInterrupt):
        return False


def run_rename_cli(
    *,
    old_library: str,
    new_name: str,
    workspace_root: Path,
    apply: bool,
    verbose: bool = False,
    assume_yes: bool = False,
) -> int:
    """Preflight, then optionally execute. Returns a process exit code."""
    plan, needs_prefix_confirm = plan_rename(old_library, new_name, Path(workspace_root))
    print(render_plan(plan, verbose=verbose))

    if not plan.ok:
        return 1

    if not apply:
        print("Dry run — nothing was changed.")
        print("Re-run with --apply to perform the rename.")
        return 0

    if not assume_yes:
        if needs_prefix_confirm and not _confirm(
            f'"{plan.new_dist}" does not start with "haybale-" or "hay-". Continue?'
        ):
            print("Aborted.")
            return 1
        if not _confirm(
            f"Rename {plan.old_dist} → {plan.new_dist}, rewriting {plan.total_changes} "
            f"reference(s) and running `uv sync`. Proceed?"
        ):
            print("Aborted.")
            return 1

    ok, message = execute_plan(plan, sink=print)
    print(message)
    if not ok:
        return 1

    print(
        "\nNext:\n"
        "  uv run haywire verify     # confirm every graph still resolves\n"
        "  git diff                  # review, then commit\n"
        "Restart the studio to pick up the change."
    )
    return 0
