"""Executing a RenamePlan in five fail-fast phases.

Later phases depend on earlier ones, so the first error stops the run.
A clean tree was proven in planning, so everything dirty afterwards is this
run's own work and ``git checkout . && git clean -fd`` restores the start
state exactly. The command never runs that itself.
"""

from __future__ import annotations

import os
import subprocess
from typing import Any

from haywire.core.tomlio import edit_toml

from .graphs import apply_graphs
from .model import RenamePlan
from .pysource import apply_python

RECOVERY = "git checkout . && git clean -fd"


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
            entry_points = doc.get("project", {}).get("entry-points", {}).get("haywire.libraries", {})
            for key in list(entry_points):
                del entry_points[key]
            stem = plan.new_dist.removeprefix("haybale-").removeprefix("hay-")
            entry_points[stem] = f"{plan.new_module}:Library"
            doc["tool"]["hatch"]["build"]["targets"]["wheel"]["packages"] = [plan.new_module]
    except (OSError, KeyError) as exc:
        return False, f"Failed to update library metadata: {exc}\nRecover with:\n  {RECOVERY}"

    sink(f"Rewriting {len(plan.python_changes)} Python file(s)...")
    # Paths were planned against the pre-rename module dir; retarget them.
    for change in plan.python_changes:
        change.path = tmp_pkg / change.path.relative_to(old_pkg)
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
    except (OSError, KeyError) as exc:
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
        except (OSError, KeyError) as exc:
            return False, f"Failed to update dependents: {exc}\nRecover with:\n  {RECOVERY}"

    # ── phase 5: uv sync ────────────────────────────────────────────────
    sink("Running uv sync...")
    result = subprocess.run(
        ["uv", "sync"],
        cwd=str(plan.workspace_root),
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
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
