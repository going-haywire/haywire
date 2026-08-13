"""Preconditions. Every function here is read-only — the preflight promises
to change nothing, including temp probe files."""

from __future__ import annotations

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
