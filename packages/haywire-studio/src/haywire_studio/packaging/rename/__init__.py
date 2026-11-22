"""``haywire rename`` — rename a project-local haybale library.

Renaming changes a library's IDENTITY only: its distribution name, module
name, and the registry-key prefix stamped into every saved graph.
Descriptive metadata (label, description, tags, homepage_url, notes) and
its dependents' references to it are preserved.

``haywire rename --map <file>`` renames components instead: it rewrites the
registry keys a key map lists in every saved graph, and nothing else.
"""

from __future__ import annotations

from pathlib import Path

from .execute import execute_plan
from .keymap import execute_key_map, load_key_map, plan_key_map
from .model import Blocker, FileChange, KeyMapPlan, KeyRename, Occurrence, RenamePlan, Warning_
from .planner import plan_rename
from .report import render_key_map_plan, render_plan

__all__ = [
    "Blocker",
    "FileChange",
    "KeyMapPlan",
    "KeyRename",
    "Occurrence",
    "RenamePlan",
    "Warning_",
    "execute_key_map",
    "execute_plan",
    "load_key_map",
    "plan_key_map",
    "plan_rename",
    "render_key_map_plan",
    "render_plan",
    "run_key_map_cli",
    "run_rename_cli",
]


def run_rename_cli(
    *,
    old_library: str,
    new_name: str,
    workspace_root: Path,
    dry_run: bool = False,
    verbose: bool = False,
) -> int:
    """Preflight, then execute unless *dry_run*. Never prompts. Returns a process exit code."""
    plan = plan_rename(old_library, new_name, Path(workspace_root))
    print(render_plan(plan, verbose=verbose))

    if not plan.ok:
        return 1

    if dry_run:
        print("Dry run — nothing was changed.")
        print("Re-run without --dry-run to perform the rename.")
        return 0

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


def run_key_map_cli(
    *,
    map_path: Path,
    workspace_root: Path,
    dry_run: bool = False,
    verbose: bool = False,
) -> int:
    """Preflight a key-map rename, then apply it unless *dry_run*. Never prompts. Returns an exit code."""
    plan = plan_key_map(Path(map_path), Path(workspace_root))
    print(render_key_map_plan(plan, verbose=verbose))

    if not plan.ok:
        return 1

    if dry_run:
        print("Dry run — nothing was changed.")
        print("Re-run without --dry-run to rewrite the graphs.")
        return 0

    if not plan.graph_changes:
        print("No graph holds a key from the map — nothing to do.")
        return 0

    ok, message = execute_key_map(plan)
    print(message)
    if not ok:
        return 1

    print(
        "\nNext:\n"
        "  uv run haywire verify     # resolves once the renamed classes are installed\n"
        "  git diff                  # review, then commit"
    )
    return 0
