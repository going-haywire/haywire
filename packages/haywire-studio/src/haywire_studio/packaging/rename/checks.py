"""Preconditions. Every function here is read-only — the preflight promises
to change nothing, including temp probe files."""

from __future__ import annotations

import os
from importlib.metadata import distributions
from pathlib import Path

from haywire.core.library.haybale_toml import module_of

from .model import Blocker, Warning_

#: Prefixes a project library conventionally carries. ``haywire-`` is
#: deliberately absent — the framework owns it, so a user library aiming
#: there gets the confirmation prompt rather than a silent pass.
CONVENTIONAL_PREFIXES = ("haybale-", "hay-")


def validate_target(new_dist: str) -> tuple[list[Blocker], bool]:
    """Validate the target distribution name.

    Returns ``(blockers, needs_prefix_confirm)``. The name is taken verbatim —
    nothing is prefixed, stripped, or slugified on the user's behalf.
    """
    blockers: list[Blocker] = []
    name = new_dist.strip()

    if not name:
        return [Blocker(message="Target name cannot be empty.")], False

    if "/" in name or "\\" in name or ".." in name:
        return [
            Blocker(
                message=f'"{name}" contains a path separator.',
                remedy="Use a plain package name.",
            )
        ], False

    if not module_of(name).isidentifier():
        return [
            Blocker(
                message=f'"{name}" does not produce a valid Python module name '
                f'(would be "{module_of(name)}").',
                remedy="Use letters, digits, hyphens and underscores; do not start with a digit.",
            )
        ], False

    return blockers, not name.lower().startswith(CONVENTIONAL_PREFIXES)


def _installed_dist_names() -> set[str]:
    names: set[str] = set()
    for dist in distributions():
        raw = dist.metadata["Name"] if dist.metadata else None
        if raw:
            names.add(raw.lower())
    return names


def check_collisions(
    workspace_root: Path, old_dist: str, new_dist: str
) -> tuple[list[Blocker], list[Warning_]]:
    """Check the five namespaces the target could land in.

    Blocks on: same name, ``barn/`` directory, ``[[heaps]]``, an installed
    distribution, and a module-name clash. Warns on a remote ``[[caches]]``
    row — shadowing a catalog entry can be deliberate.
    """
    blockers: list[Blocker] = []
    warnings: list[Warning_] = []
    new_module = module_of(new_dist)

    if new_dist.lower() == old_dist.lower():
        return [Blocker(message="Target name is the same as the current name.")], warnings

    barn = workspace_root / "barn"
    if (barn / new_dist).exists():
        blockers.append(
            Blocker(
                message=f'A barn directory "{barn / new_dist}" already exists.',
                remedy="Pick a different name, or remove that directory.",
            )
        )

    # Module-name clash: haybale-TEST_A and haybale-test-a both normalise to
    # haybale_test_a, so two dists would install into one importable package.
    if barn.is_dir():
        for sibling in barn.iterdir():
            if not sibling.is_dir() or sibling.name.lower() == old_dist.lower():
                continue
            if module_of(sibling.name) == new_module:
                blockers.append(
                    Blocker(
                        message=f'Module name "{new_module}" collides with barn library "{sibling.name}".',
                        remedy="Pick a name that normalises to a different module.",
                    )
                )

    if new_dist.lower() in _installed_dist_names():
        blockers.append(
            Blocker(
                message=f'"{new_dist}" is already installed in this environment.',
                remedy=f"uv pip uninstall {new_dist}   # if it is not needed",
            )
        )

    marketplace_path = workspace_root / ".haywire" / "marketplace.toml"
    if marketplace_path.is_file():
        from haywire.core.marketstall import parse_project_marketplace

        parsed = parse_project_marketplace(marketplace_path)
        for heap in parsed.heaps:
            if str(heap.get("name", "")).lower() == new_dist.lower():
                blockers.append(
                    Blocker(
                        message=f'"{new_dist}" already has a [[heaps]] entry in marketplace.toml.',
                        remedy="Remove that entry, or pick a different name.",
                    )
                )
        for row in parsed.caches:
            if row.name.lower() == new_dist.lower():
                warnings.append(
                    Warning_(
                        message=f'"{new_dist}" matches a marketplace catalog entry — '
                        f"the local library will shadow it."
                    )
                )

    return blockers, warnings


def check_clean_tree(workspace_root: Path) -> list[Blocker]:
    """A clean tree is a hard precondition — there is no override flag.

    This is what makes ``git checkout . && git clean -fd`` a complete
    rollback: if the tree is proven clean before the rename writes anything,
    everything dirty afterwards is provably the rename's own work. Same
    reasoning as the share pipeline (steps/preconditions.py:115).
    """
    from haywire.core.publishing.git import git

    if not git(["--version"], cwd=workspace_root, timeout=10.0).ok:
        return [
            Blocker(
                message="git is not available.",
                remedy="Install git — the rename relies on it for rollback.",
            )
        ]

    if not git(["rev-parse", "--is-inside-work-tree"], cwd=workspace_root, timeout=10.0).ok:
        return [
            Blocker(
                message=f"{workspace_root} is not a git repository.",
                remedy=(
                    "Initialise one first — a rename is only safely reversible with git:\n"
                    "  git init && git add -A && git commit -m 'initial'"
                ),
            )
        ]

    status = git(["status", "--porcelain"], cwd=workspace_root, timeout=10.0)
    if status.ok and status.stdout.strip():
        files = [line[3:].strip() for line in status.stdout.splitlines() if line.strip()]
        listed = "\n".join(f"  {f}" for f in files)
        return [
            Blocker(
                message=f"Working tree is not clean:\n{listed}",
                remedy=(
                    "A rename rewrites files across the whole project, and git is its only\n"
                    "undo. Commit or stash first:\n"
                    '  git add -A && git commit -m "wip before rename"\n'
                    "  # or\n"
                    "  git stash --include-untracked"
                ),
            )
        ]
    return []


def check_write_access(paths: list[Path], dir_renames: list[Path]) -> list[Blocker]:
    """Verify every planned write is permitted, without writing anything.

    Renaming a directory requires write+execute on its PARENT — the entry
    being renamed lives there. Checking the directory itself passes while the
    rename still fails, which is the easy bug here.
    """
    blockers: list[Blocker] = []

    for path in paths:
        if path.exists() and not os.access(path, os.W_OK):
            blockers.append(Blocker(message=f"No write permission: {path}"))

    for target in dir_renames:
        parent = target.parent
        if parent.exists() and not os.access(parent, os.W_OK | os.X_OK):
            blockers.append(
                Blocker(
                    message=f"No write permission on {parent} (needed to rename {target.name}).",
                    remedy=f"chmod u+wx {parent}",
                )
            )

    return blockers


def find_dependents(workspace_root: Path, old_dist: str) -> tuple[list[Path], list[Blocker]]:
    """In-workspace barn libraries referencing *old_dist*.

    A dependent references it four ways: ``linked_libraries`` (module name),
    ``[project] dependencies`` (distribution name), imports (module name),
    and registry-key literals (distribution name). A broken
    ``linked_libraries`` entry does not raise — it silently breaks hot-reload
    scope tracking — so these must be patched, not merely reported.

    Out-of-workspace dependents are returned as blockers: site-packages
    cannot be rewritten from here.
    """
    from .pysource import _import_line_numbers

    old_module = module_of(old_dist)
    barn = workspace_root / "barn"
    dependents: list[Path] = []
    blockers: list[Blocker] = []

    if not barn.is_dir():
        return dependents, blockers

    for lib in sorted(barn.iterdir()):
        if not lib.is_dir() or lib.name.lower() == old_dist.lower():
            continue

        referenced = False

        pyproject = lib / "pyproject.toml"
        if pyproject.is_file():
            try:
                text = pyproject.read_text(encoding="utf-8")
                if f'"{old_dist}"' in text or f"'{old_dist}'" in text:
                    referenced = True
            except OSError:
                pass

        for toml_path in lib.glob("*/haybale.toml"):
            try:
                if f'"{old_module}"' in toml_path.read_text(encoding="utf-8"):
                    referenced = True
            except OSError:
                pass

        if not referenced:
            for py in lib.glob("**/*.py"):
                if "__pycache__" in py.parts:
                    continue
                try:
                    source = py.read_text(encoding="utf-8")
                except (OSError, UnicodeDecodeError):
                    continue
                if _import_line_numbers(source, old_module) or f"{old_dist}:" in source:
                    referenced = True
                    break

        if referenced:
            dependents.append(lib)

    return dependents, blockers
