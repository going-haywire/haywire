"""Executing a RenamePlan in five fail-fast phases.

Later phases depend on earlier ones, so the first error stops the run.
A clean tree was proven in planning, so everything dirty afterwards is this
run's own work and ``git checkout . && git clean -fd`` restores the start
state exactly. The command never runs that itself.
"""

from __future__ import annotations

import os
import subprocess
from pathlib import Path
from typing import Any, Iterable

import toml

from haywire.core.tomlio import edit_toml

from .graphs import apply_graphs
from .model import FileChange, RenamePlan
from .pysource import apply_python

RECOVERY = "git checkout . && git clean -fd"


def _retarget(changes: Iterable[FileChange], old_root: Path, new_root: Path) -> None:
    """Rewrite each change's path from under *old_root* to under *new_root*.

    Plans are computed before the filesystem moves anything, so every path a
    plan carries is stale the moment a directory it lived under gets renamed.
    A change whose path is NOT under *old_root* (it genuinely lives
    elsewhere — e.g. a dependent in another library's directory) is left
    untouched rather than raising.
    """
    for change in changes:
        try:
            relative = change.path.relative_to(old_root)
        except ValueError:
            continue
        change.path = new_root / relative


def execute_plan(plan: RenamePlan, *, sink: Any = print) -> tuple[bool, str]:
    """Apply *plan*. Returns ``(ok, message)``."""
    old_pkg = plan.old_lib_dir / plan.old_module
    tmp_pkg = plan.old_lib_dir / plan.new_module

    # ── phase 1: module directory ───────────────────────────────────────
    sink(f"Renaming module directory: {plan.old_module} → {plan.new_module}")
    try:
        os.rename(old_pkg, tmp_pkg)
    except OSError as exc:
        return False, f"Failed to rename module directory: {exc}\nRecover with:\n  {RECOVERY}"

    # ── phase 2: the library's own config + sources ─────────────────────
    sink("Updating library metadata...")
    try:
        # Identity only: label/description/tags/homepage_url/notes/
        # linked_libraries are deliberately preserved.
        with edit_toml(tmp_pkg / "haybale.toml") as doc:
            doc["name"] = plan.new_dist

        with edit_toml(plan.old_lib_dir / "pyproject.toml") as doc:
            doc["project"]["name"] = plan.new_dist
            # Subscript through (not .get(..., {})) so a missing table raises
            # KeyError, caught below — same as the hatch-table write just
            # after it. Every real library carries this section; silently
            # discarding the write when it's absent would make the library
            # undiscoverable while reporting success.
            entry_points = doc["project"]["entry-points"]["haywire.libraries"]
            for key in list(entry_points):
                del entry_points[key]
            stem = plan.new_dist.removeprefix("haybale-").removeprefix("hay-")
            entry_points[stem] = f"{plan.new_module}:Library"
            doc["tool"]["hatch"]["build"]["targets"]["wheel"]["packages"] = [plan.new_module]
    except (OSError, KeyError, toml.TomlDecodeError) as exc:
        return False, f"Failed to update library metadata: {exc}\nRecover with:\n  {RECOVERY}"

    sink(f"Rewriting {len(plan.python_changes)} Python file(s)...")
    # Paths were planned against the pre-rename module dir; retarget every
    # plan-carried path that lived under it. A graph or dependent path can
    # live under old_pkg too (e.g. an examples/ folder inside the module
    # dir) — _retarget leaves non-matching paths alone rather than raising.
    _retarget(plan.python_changes, old_pkg, tmp_pkg)
    _retarget(plan.graph_changes, old_pkg, tmp_pkg)
    _retarget(plan.dependent_changes, old_pkg, tmp_pkg)
    try:
        apply_python(plan.python_changes, plan.old_dist, plan.new_dist, plan.old_module, plan.new_module)
    except OSError as exc:
        return False, f"Failed to rewrite Python sources: {exc}\nRecover with:\n  {RECOVERY}"

    # ── phase 3: library directory ──────────────────────────────────────
    sink(f"Renaming library directory: {plan.old_dist} → {plan.new_dist}")
    try:
        os.rename(plan.old_lib_dir, plan.new_lib_dir)
    except OSError as exc:
        return False, f"Failed to rename library directory: {exc}\nRecover with:\n  {RECOVERY}"

    # Any plan-carried path that lived under old_lib_dir is now stale — this
    # covers Python files outside the module dir (tests/, conftest.py, ...)
    # and graphs shipped inside the library directory (e.g. examples/).
    # dependent_changes live in OTHER libraries' directories, which did not
    # move, so this is a no-op for them — _retarget leaves non-matching
    # paths alone rather than raising.
    _retarget(plan.python_changes, plan.old_lib_dir, plan.new_lib_dir)
    _retarget(plan.graph_changes, plan.old_lib_dir, plan.new_lib_dir)
    _retarget(plan.dependent_changes, plan.old_lib_dir, plan.new_lib_dir)

    # ── phase 4: project config, graphs, dependents ─────────────────────
    sink("Updating project configuration...")
    try:
        project_pyproject = plan.workspace_root / "pyproject.toml"
        if project_pyproject.is_file():
            with edit_toml(project_pyproject) as doc:
                deps = doc.get("project", {}).get("dependencies", [])
                for i, dep in enumerate(list(deps)):
                    if str(dep).lower() == plan.old_dist.lower():
                        deps[i] = plan.new_dist
                sources = doc.get("tool", {}).get("uv", {}).get("sources", {})
                for key in [k for k in sources if k.lower() == plan.old_dist.lower()]:
                    value = sources[key]
                    del sources[key]
                    sources[plan.new_dist] = value

        marketplace = plan.workspace_root / ".haywire" / "marketplace.toml"
        if marketplace.is_file():
            with edit_toml(marketplace) as doc:
                for heap in doc.get("heaps", []):
                    if str(heap.get("name", "")).lower() == plan.old_dist.lower():
                        heap["name"] = plan.new_dist
                        heap["path"] = str(plan.new_lib_dir)
                    # Every heap's own linked_libraries (module names) may
                    # reference the renamed library, not just its own entry —
                    # a sibling heap's copy of this list is what the
                    # marketplace install gate actually reads.
                    linked = heap.get("linked_libraries")
                    if linked is not None:
                        for i, entry in enumerate(list(linked)):
                            if str(entry) == plan.old_module:
                                linked[i] = plan.new_module
    except (OSError, KeyError, toml.TomlDecodeError) as exc:
        return False, f"Failed to update project configuration: {exc}\nRecover with:\n  {RECOVERY}"

    sink(f"Patching {len(plan.graph_changes)} graph file(s)...")
    try:
        apply_graphs(plan.graph_changes, plan.old_dist, plan.new_dist)
    except (OSError, ValueError) as exc:
        return False, f"Failed to patch graphs: {exc}\nRecover with:\n  {RECOVERY}"

    if plan.dependent_changes:
        sink(f"Updating {len(plan.dependent_changes)} dependent file(s)...")
        try:
            for change in plan.dependent_changes:
                if change.kind == "python":
                    apply_python([change], plan.old_dist, plan.new_dist, plan.old_module, plan.new_module)
                elif change.path.name == "haybale.toml":
                    with edit_toml(change.path) as doc:
                        linked = doc.get("linked_libraries")
                        if linked is not None:
                            for i, entry in enumerate(list(linked)):
                                if str(entry) == plan.old_module:
                                    linked[i] = plan.new_module
                else:
                    with edit_toml(change.path) as doc:
                        deps = doc.get("project", {}).get("dependencies", [])
                        for i, dep in enumerate(list(deps)):
                            if str(dep).lower() == plan.old_dist.lower():
                                deps[i] = plan.new_dist
        except (OSError, KeyError, toml.TomlDecodeError) as exc:
            return False, f"Failed to update dependents: {exc}\nRecover with:\n  {RECOVERY}"

    # ── phase 5: uv sync ────────────────────────────────────────────────
    sink("Running uv sync...")
    try:
        result = subprocess.run(
            ["uv", "sync"],
            cwd=str(plan.workspace_root),
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
        )
    except OSError as exc:
        # The source rename is complete and correct — this is an environment
        # problem (e.g. `uv` missing from PATH). Advising a revert would
        # discard good work, so no RECOVERY hint here either.
        return False, (
            f"Source rename to {plan.new_dist} completed, but `uv sync` could not be run: {exc}\n"
            f"Fix the environment (e.g. install/fix `uv` on PATH) and re-run:\n  uv sync"
        )
    for line in result.stdout.decode().splitlines():
        sink(line)
    if result.returncode != 0:
        # The source rename is complete and correct — this is an environment
        # resolution problem. Advising a revert would discard good work.
        return False, (
            f"Source rename to {plan.new_dist} completed, but `uv sync` failed.\n"
            f"Fix the environment and re-run:\n  uv sync"
        )

    return True, f"Renamed {plan.old_dist} → {plan.new_dist}"
