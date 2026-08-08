"""CLI-facing core logic for renaming a local haybale library; no asyncio, no live-registry."""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


from haywire.core.library.decorator_io import _set_decorator_str_field
from haywire.core.tomlio import edit_toml


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def sanitize_rename(new_name: str) -> str | None:
    """Convert *new_name* to a valid Python identifier suffix, or ``None`` if unsafe."""
    if "/" in new_name or "\\" in new_name or ".." in new_name:
        return None
    sanitized = re.sub(r"[^a-zA-Z0-9_]", "_", new_name.lower())
    if sanitized and sanitized[0].isdigit():
        sanitized = "_" + sanitized
    return sanitized or None


def _sanitize_name_raw(name: str) -> str:
    """Unconditionally slugify *name* to a valid identifier, prefixing ``_`` if it starts with a digit."""
    s = re.sub(r"[^a-zA-Z0-9_]", "_", name.lower())
    return ("_" + s) if s and s[0].isdigit() else s


# ---------------------------------------------------------------------------
# Main rename function
# ---------------------------------------------------------------------------


def rename_library(
    old_library: str,
    new_name: str,
    workspace_root: Path,
    *,
    sink: Any = print,
) -> tuple[bool, str]:
    """Rename a local haybale library in *workspace_root*; returns ``(ok, message)``."""
    workspace = Path(workspace_root)
    marketplace_path = workspace / ".haywire" / "marketplace.toml"

    # --- 1. Validate new_name ---
    new_name = new_name.strip()
    if not new_name:
        return False, "New name cannot be empty."
    if "/" in new_name or "\\" in new_name or ".." in new_name:
        return False, "New name must not contain path separators."
    sanitized = sanitize_rename(new_name)
    if not sanitized:
        return False, f'"{new_name}" produces an empty module name.'

    new_lib_name = f"haybale-{new_name}"
    new_module = f"haybale_{sanitized}"

    # Locate the old library directory under barn/
    barn_dir = workspace / "barn"
    old_lib_dir = barn_dir / old_library
    if not old_lib_dir.is_dir():
        return False, f'Library directory "{old_lib_dir}" does not exist.'

    dist_name = old_library  # e.g. "haybale-foo"

    if new_lib_name.lower() == dist_name.lower():
        return False, "New name is the same as the current name."

    # Check whether the new name already exists as a barn directory
    new_lib_dir = workspace / "barn" / new_lib_name
    if new_lib_dir.exists():
        return False, f'Directory "{new_lib_dir}" already exists.'

    from haywire.core.marketstall import parse_project_marketplace

    marketplace_pm = parse_project_marketplace(marketplace_path) if marketplace_path.exists() else None
    marketplace_entries = marketplace_pm.caches if marketplace_pm else []
    if any(
        pkg.name.lower() == new_lib_name.lower() and pkg.name.lower() != dist_name.lower()
        for pkg in marketplace_entries
    ):
        return False, f'"{new_lib_name}" already exists in the marketplace.'

    # --- 2. Derive old paths ---
    old_name_part = dist_name.removeprefix("haybale-") if dist_name.startswith("haybale-") else dist_name
    old_module_sanitized = sanitize_rename(old_name_part) or _sanitize_name_raw(old_name_part)
    old_module = f"haybale_{old_module_sanitized}"
    old_pkg_dir = old_lib_dir / old_module
    new_pkg_dir_tmp = old_lib_dir / new_module  # inside old lib dir before lib rename
    new_label = new_name.replace("-", " ").replace("_", " ").title()

    # Resolve all identity values (defaults only; no new_identity override in CLI).
    # version/description/url/author/tags are no longer decorator fields — the
    # identity reads them from the distribution's metadata, so `description` is
    # written to pyproject.toml below and the rest are not this function's to set.
    label_val = new_label
    desc_val = f"Local library for {new_name} project"

    # --- 3. (Studio: disable old library — skipped in CLI) ---
    sink(f"Renaming {dist_name} → {new_lib_name}...")

    # --- 4. Rename module directory ---
    sink(f"Renaming module directory:  {old_module}  →  {new_module}")
    try:
        os.rename(old_pkg_dir, new_pkg_dir_tmp)
    except OSError as e:
        return False, f"Failed to rename module directory: {e}"

    # --- 5. Update __init__.py ---
    sink("Updating __init__.py...")
    try:
        init_file = new_pkg_dir_tmp / "__init__.py"
        content = init_file.read_text()
        # Quote-agnostic. The regexes these replace matched single quotes only,
        # so they no-opped against any library ruff had formatted — and `id`
        # not being rewritten is the damaging one: patch_graph_references
        # rewrites every graph's registry keys to the new id, which then
        # resolves against nothing.
        content = _set_decorator_str_field(content, "id", new_name)
        content = _set_decorator_str_field(content, "label", label_val)
        content = re.sub(
            r"(Local haybale library for the )[^\n]*(\.)",
            rf"\g<1>{new_name} project\2",
            content,
        )
        init_file.write_text(content)
    except OSError as e:
        return False, f"Failed to update __init__.py: {e}"

    # --- 6. Update lib's pyproject.toml ---
    sink("Updating lib pyproject.toml...")
    try:
        lib_pyproject = old_lib_dir / "pyproject.toml"
        with edit_toml(lib_pyproject) as data:
            data["project"]["name"] = new_lib_name
            data["project"]["description"] = desc_val
            ep = data.get("project", {}).get("entry-points", {}).get("haywire.libraries", {})
            old_ep_key = next(iter(ep), None)
            if old_ep_key:
                del ep[old_ep_key]
            ep[new_name] = f"{new_module}:Library"
            data["tool"]["hatch"]["build"]["targets"]["wheel"]["packages"] = [new_module]
    except (OSError, KeyError) as e:
        return False, f"Failed to update lib pyproject.toml: {e}"

    # --- 7. Rename library directory ---
    sink(f"Renaming library directory:  {dist_name}  →  {new_lib_name}")
    try:
        os.rename(old_lib_dir, new_lib_dir)
    except OSError as e:
        return False, f"Failed to rename library directory: {e}"

    # --- 8. Update project pyproject.toml ---
    sink("Updating project pyproject.toml...")
    try:
        project_pyproject = workspace / "pyproject.toml"
        with edit_toml(project_pyproject) as data:
            deps = data.get("project", {}).get("dependencies", [])
            data["project"]["dependencies"] = [
                new_lib_name if str(d).lower() == dist_name.lower() else str(d) for d in deps
            ]
            sources = data.get("tool", {}).get("uv", {}).get("sources", {})
            old_key = next((k for k in sources if k.lower() == dist_name.lower()), None)
            if old_key:
                del sources[old_key]
            sources[new_lib_name] = {"workspace": True}
    except (OSError, KeyError) as e:
        return False, f"Failed to update project pyproject.toml: {e}"

    # --- 9. Update marketplace.toml ---
    sink("Updating marketplace.toml...")
    try:
        if marketplace_path.exists():
            with edit_toml(marketplace_path) as data:
                for heap in data.get("heaps", []):
                    if heap.get("name", "").lower() == dist_name.lower():
                        heap["name"] = new_lib_name
                        heap["path"] = str(new_lib_dir)
                        heap["label"] = label_val
                        heap["description"] = desc_val
                        break
    except (OSError, KeyError) as e:
        return False, f"Failed to update marketplace.toml: {e}"

    # --- 10. Run uv sync ---
    sink("Running uv sync...")
    result = subprocess.run(
        ["uv", "sync"],
        cwd=str(workspace),
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
    )
    for line in result.stdout.decode().splitlines():
        sink(line)
    if result.returncode != 0:
        return (
            False,
            f'uv sync failed — filesystem already renamed, run "uv sync" manually in {workspace}',
        )

    # --- 11. Rescan/re-enable omitted (restart studio to pick up changes) ---

    return True, f"Renamed to haybale-{new_name}"


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------


def run_rename_cli(*, old_library: str, new_name: str, workspace_root: Path, apply: bool) -> int:
    """Atomic: package rename + graph-reference patch. Dry-run unless apply=True.

    Returns a process exit code (0 ok, non-zero on failure).
    """
    sanitized = sanitize_rename(new_name)
    if sanitized is None:
        print(f"error: '{new_name}' is not a valid library name")
        return 2

    graphs_dir = workspace_root / "graphs"
    plan = patch_graph_references(graphs_dir, old_library.removeprefix("haybale-"), sanitized, apply=False)
    print(f"Will rename {old_library} -> haybale-{sanitized}")
    print(f"Graph references: {plan.replacements} key(s) in {plan.files_changed} file(s)")
    for name in plan.changed_files:
        print(f"  - {name}")

    if not apply:
        print("\nDry run. Re-run with --apply to perform the rename.")
        return 0

    ok, msg = rename_library(old_library, sanitized, workspace_root, sink=print)
    if not ok:
        print(f"error: {msg}")
        return 1
    patch_graph_references(graphs_dir, old_library.removeprefix("haybale-"), sanitized, apply=True)
    print(f"Renamed to haybale-{sanitized}. Restart studio to pick up the change.")
    return 0


# ---------------------------------------------------------------------------
# Graph-reference patching
# ---------------------------------------------------------------------------


@dataclass
class PatchResult:
    files_changed: int = 0
    replacements: int = 0
    changed_files: list[str] = field(default_factory=list)


# JSON fields whose VALUES are registry keys ("<lib>:<kind>:<name>").
_KEY_FIELDS = ("type",)


def _rewrite_keys(obj: object, old_prefix: str, new_prefix: str) -> int:
    """Recursively rewrite registry-key fields in-place. Returns replacement count."""
    n = 0
    if isinstance(obj, dict):
        for k, v in obj.items():
            if k in _KEY_FIELDS and isinstance(v, str) and v.startswith(old_prefix):
                obj[k] = new_prefix + v[len(old_prefix) :]
                n += 1
            else:
                n += _rewrite_keys(v, old_prefix, new_prefix)
    elif isinstance(obj, list):
        for item in obj:
            n += _rewrite_keys(item, old_prefix, new_prefix)
    return n


def patch_graph_references(graphs_dir: Path, old_id: str, new_id: str, *, apply: bool) -> PatchResult:
    """Rewrite old_id: registry-key prefixes to new_id: in graphs/**/*.json.

    JSON-aware: only fields in _KEY_FIELDS are candidates. Dry-run (apply=False)
    reports without writing. On apply, backs up each changed file to <name>.json.bak.
    """
    result = PatchResult()
    if not graphs_dir.is_dir():
        return result
    old_prefix, new_prefix = old_id + ":", new_id + ":"
    for f in sorted(graphs_dir.glob("**/*.json")):
        try:
            data = json.loads(f.read_text())
        except (OSError, json.JSONDecodeError):
            continue
        count = _rewrite_keys(data, old_prefix, new_prefix)
        if count:
            result.files_changed += 1
            result.replacements += count
            result.changed_files.append(f.name)
            if apply:
                shutil.copy2(f, f.with_suffix(".json.bak"))
                f.write_text(json.dumps(data, indent=2))
    return result
