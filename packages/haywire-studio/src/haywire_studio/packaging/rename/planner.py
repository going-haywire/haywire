"""The single planner. Both the dry run and --apply call this, so the plan
printed and the plan executed cannot diverge."""

from __future__ import annotations

from pathlib import Path

from haywire.core.library.haybale_toml import module_of

from .checks import (
    check_clean_tree,
    check_collisions,
    check_write_access,
    find_dependents,
    validate_target,
)
from .graphs import plan_graphs
from .model import Blocker, FileChange, RenamePlan, Warning_
from .pysource import plan_python


def plan_rename(old_dist: str, new_dist: str, workspace_root: Path) -> tuple[RenamePlan, bool]:
    """Enumerate every change and every blocker. Writes nothing.

    Returns ``(plan, needs_prefix_confirm)``.
    """
    workspace_root = Path(workspace_root)
    new_dist, name_blockers, needs_confirm = validate_target(new_dist)

    old_module = module_of(old_dist)
    new_module = module_of(new_dist)
    old_lib_dir = workspace_root / "barn" / old_dist

    plan = RenamePlan(
        old_dist=old_dist,
        new_dist=new_dist,
        old_module=old_module,
        new_module=new_module,
        workspace_root=workspace_root,
        old_lib_dir=old_lib_dir,
        new_lib_dir=workspace_root / "barn" / new_dist,
    )

    plan.blockers += name_blockers
    if name_blockers:
        return plan, needs_confirm

    plan.blockers += check_clean_tree(workspace_root)

    if not old_lib_dir.is_dir():
        plan.blockers.append(
            Blocker(
                message=f'Library directory "{old_lib_dir}" does not exist.',
                remedy=f"ls {workspace_root / 'barn'}   # to see available libraries",
            )
        )
        return plan, needs_confirm

    collision_blockers, collision_warnings = check_collisions(workspace_root, old_dist, new_dist)
    plan.blockers += collision_blockers
    plan.warnings += collision_warnings

    dependents, dependent_blockers = find_dependents(workspace_root, old_dist)
    plan.blockers += dependent_blockers

    # ── config files: identity fields only ──────────────────────────────
    for candidate, count in (
        (old_lib_dir / old_module / "haybale.toml", 1),  # name
        (old_lib_dir / "pyproject.toml", 3),  # name, entry-point key, wheel packages
        (workspace_root / "pyproject.toml", 2),  # dependency string, uv source key
        (workspace_root / ".haywire" / "marketplace.toml", 2),  # heap name + path
    ):
        if candidate.is_file():
            plan.toml_changes.append(FileChange(path=candidate, kind="toml", count=count))

    graph_changes, graph_drift = plan_graphs(workspace_root, old_dist, new_dist, old_module=old_module)
    plan.graph_changes = graph_changes
    plan.unrecognized += graph_drift

    py_changes, py_prose = plan_python([old_lib_dir], old_dist, new_dist, old_module, new_module)
    plan.python_changes = py_changes
    plan.unrecognized += py_prose

    for dependent in dependents:
        dep_py, dep_prose = plan_python([dependent], old_dist, new_dist, old_module, new_module)
        plan.dependent_changes += dep_py
        plan.unrecognized += dep_prose
        for toml_path in (*dependent.glob("*/haybale.toml"), dependent / "pyproject.toml"):
            if toml_path.is_file():
                plan.dependent_changes.append(FileChange(path=toml_path, kind="toml", count=1))

    # ── write access, derived from the plan itself ──────────────────────
    touched = [
        change.path
        for change in (
            *plan.toml_changes,
            *plan.graph_changes,
            *plan.python_changes,
            *plan.dependent_changes,
        )
    ]
    plan.blockers += check_write_access(touched, [old_lib_dir / old_module, old_lib_dir])

    # ── persisted storage does not follow the rename ────────────────────
    storage = Path.home() / ".haywire" / "db" / old_module
    if storage.is_dir():
        plan.warnings.append(
            Warning_(
                message=f"Persistent storage at {storage} will not follow the rename.",
                remedy=f"mv {storage} {storage.parent / new_module}",
            )
        )

    return plan, needs_confirm
