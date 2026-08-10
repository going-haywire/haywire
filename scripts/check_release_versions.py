"""Verify every release package agrees on one version.

Two checks, both of which `scripts/bump_version.py` is *supposed* to have
already made true — this asserts it actually did:

  1. Every package in [tool.haywire.release] declares the same
     `[project] version`, and (with --expect) that version is the one asked
     for. The release is lockstep; a package left behind is a broken release.
  2. Every package's `haybale.toml`, where it has one, declares that same
     version. `haybale.toml` is canon (consumed by `LibraryIdentity`) and
     `pyproject.toml`'s `[project] version` is its generated copy, but nothing
     else ever reads the two back to confirm they agree — the bump writes both
     and moves on. If they disagree, `haybale.toml` names the intended version.

Run in CI before wheels are built, so a tag pushed without a bump fails loudly
instead of publishing nothing (see .github/workflows/publish.yml). Exits 0 when
consistent, 1 otherwise, printing every disagreement.
"""

from __future__ import annotations

import argparse
import sys
import tomllib
from pathlib import Path

# Invoked by path (`python scripts/check_release_versions.py`), which puts
# scripts/ on sys.path rather than the repo root — same as scripts/check_deps.py.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from scripts.bump_version import (  # noqa: E402
    find_haybale_toml,
    locate_packages,
    read_release_config,
)


def collect_versions(root_pyproject: Path) -> dict[str, str | None]:
    """Map every release-relevant file to its declared version.

    Keys are repo-relative paths, so a failure message points straight at the
    file to fix. A None value means the file exists but declares no version.
    """
    config = read_release_config(root_pyproject)
    located = locate_packages(root_pyproject, config)
    root_dir = root_pyproject.parent

    found: dict[str, str | None] = {}
    for pkg_name in config.all_packages:
        pyproject_path = located[pkg_name]
        data = tomllib.loads(pyproject_path.read_text(encoding="utf-8"))
        rel = pyproject_path.relative_to(root_dir).as_posix()
        found[rel] = data.get("project", {}).get("version")

        haybale_path = find_haybale_toml(pyproject_path.parent)
        if haybale_path is not None:
            haybale_data = tomllib.loads(haybale_path.read_text(encoding="utf-8"))
            rel = haybale_path.relative_to(root_dir).as_posix()
            found[rel] = haybale_data.get("version")
    return found


def check(root_pyproject: Path, expected: str | None) -> list[str]:
    """Return a list of human-readable problems; empty means consistent."""
    found = collect_versions(root_pyproject)
    problems: list[str] = []

    missing = sorted(path for path, version in found.items() if version is None)
    problems.extend(f"{path}: no version declared" for path in missing)

    declared = {version for version in found.values() if version is not None}

    # With no --expect, any single agreed version is acceptable — this is then
    # purely a lockstep/sync check, usable outside a tagged release.
    target = expected if expected is not None else (next(iter(declared)) if len(declared) == 1 else None)

    if target is None and not problems:
        problems.append(f"packages disagree on version: {sorted(declared)}")

    if target is not None:
        problems.extend(
            f'{path}: version "{version}" != expected "{target}"'
            for path, version in sorted(found.items())
            if version is not None and version != target
        )
    return problems


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="check_release_versions",
        description="Verify every release package (and its haybale.toml) declares one version.",
    )
    parser.add_argument(
        "--expect",
        help="Require this exact version (e.g. the tag being built, minus its 'v').",
    )
    parser.add_argument(
        "--root",
        type=Path,
        default=Path("pyproject.toml"),
        help="Path to the workspace root pyproject.toml (default: ./pyproject.toml)",
    )
    args = parser.parse_args(argv)

    problems = check(args.root, args.expect)
    if problems:
        print("Release version check FAILED:", file=sys.stderr)
        for problem in problems:
            print(f"  - {problem}", file=sys.stderr)
        if args.expect:
            print(
                f"\nRun `uv run python scripts/bump_version.py {args.expect} --yes` "
                "and commit before tagging.",
                file=sys.stderr,
            )
        return 1

    target = args.expect or "the committed version"
    print(f"Release version check passed: every package agrees on {target}.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
