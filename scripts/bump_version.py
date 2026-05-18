"""Bump every haywire monorepo publishable package to a new version.

Reads [tool.haywire.release] from the workspace root pyproject.toml,
then surgically edits every listed package's pyproject.toml:
  - rewrites `version = "X.Y.Z"` to the new version,
  - rewrites every `"<sibling>~=A.B.C"` dep on a known sibling to
    `"<sibling>~=<new>"`.

Prints a unified diff of all changes and asks for confirmation before
writing. Use --yes to skip the prompt (for scripted use).
"""

from __future__ import annotations

import argparse
import difflib
import re
import sys
import tomllib  # type: ignore[import-not-found]  # stdlib 3.11+; mypy config pins 3.10
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class ReleaseConfig:
    publish_order: list[str]
    lockstep_unpublished: list[str]

    @property
    def all_packages(self) -> list[str]:
        return [*self.publish_order, *self.lockstep_unpublished]


def read_release_config(root_pyproject: Path) -> ReleaseConfig:
    data = tomllib.loads(root_pyproject.read_text(encoding="utf-8"))
    block = data["tool"]["haywire"]["release"]
    return ReleaseConfig(
        publish_order=list(block["publish_order"]),
        lockstep_unpublished=list(block.get("lockstep_unpublished", [])),
    )


class MissingPackageError(RuntimeError):
    """Raised when a package listed in [tool.haywire.release] has no pyproject on disk."""


def _expand_workspace_globs(root_pyproject: Path) -> list[Path]:
    """Return every pyproject.toml under [tool.uv.workspace].members globs."""
    data = tomllib.loads(root_pyproject.read_text(encoding="utf-8"))
    members = data.get("tool", {}).get("uv", {}).get("workspace", {}).get("members", [])
    root_dir = root_pyproject.parent
    found: list[Path] = []
    for pattern in members:
        # Workspace globs are filesystem patterns like "barn/*" — pyproject.toml lives inside.
        for member_dir in sorted(root_dir.glob(pattern)):
            candidate = member_dir / "pyproject.toml"
            if candidate.is_file():
                found.append(candidate)
    return found


def locate_packages(root_pyproject: Path, config: ReleaseConfig) -> dict[str, Path]:
    """Map every package name in `config.all_packages` to its pyproject.toml path."""
    wanted = set(config.all_packages)
    located: dict[str, Path] = {}
    for pyproject_path in _expand_workspace_globs(root_pyproject):
        data = tomllib.loads(pyproject_path.read_text(encoding="utf-8"))
        name = data.get("project", {}).get("name")
        if name in wanted:
            located[name] = pyproject_path
    missing = wanted - located.keys()
    if missing:
        raise MissingPackageError(
            f"release config references packages not found in workspace: {sorted(missing)}"
        )
    return located


# Matches `version = "X.Y.Z"` at the start of a line, with optional surrounding spaces.
# We anchor on start-of-line + optional spaces to skip occurrences inside dep strings or
# nested tables. `[project]` is the only top-level table where this should fire.
_VERSION_LINE_RE = re.compile(r'^(?P<lead>\s*version\s*=\s*")[^"]+(?P<trail>")', re.MULTILINE)

# Matches a quoted PEP 508 requirement like "pkg-name~=0.0.1" or "pkg-name>=0.1.0",
# capturing the name and operator separately. Used to rewrite sibling deps only.
_DEP_REQ_RE = re.compile(
    r'"(?P<name>[A-Za-z0-9_.-]+)(?P<op>~=|>=|==|>|<|<=)(?P<ver>[0-9][0-9A-Za-z.+!*-]*)"'
)


def rewrite_pyproject(
    source: str,
    new_version: str,
    known_siblings: set[str],
) -> tuple[str, list[str]]:
    """Return (new_source, list_of_human_edit_descriptions).

    Edits:
      * one `version = "..."` line at top of `[project]`
      * every `"<sibling>~=..."` (or other operator) dep — rewritten to `~=<new_version>`.

    Non-sibling deps are left untouched. If `new_version` already matches everywhere,
    returns source unchanged and edits == [].
    """
    edits: list[str] = []

    def _version_sub(m: re.Match[str]) -> str:
        existing = m.group(0)[len(m.group("lead")) : -len(m.group("trail"))]
        if existing == new_version:
            return m.group(0)
        edits.append(f'version: "{existing}" → "{new_version}"')
        return f"{m.group('lead')}{new_version}{m.group('trail')}"

    # Only rewrite the first occurrence — `version = ...` should appear once in [project].
    new_source, count = _VERSION_LINE_RE.subn(_version_sub, source, count=1)
    if count == 0:
        raise ValueError('could not find `version = "..."` line in pyproject')

    def _dep_sub(m: re.Match[str]) -> str:
        name = m.group("name")
        if name not in known_siblings:
            return m.group(0)
        old = m.group(0)
        new = f'"{name}~={new_version}"'
        if old == new:
            return old
        edits.append(f"dep {name}: {old} → {new}")
        return new

    new_source = _DEP_REQ_RE.sub(_dep_sub, new_source)
    return new_source, edits


def apply_bump(
    root_pyproject: Path,
    new_version: str,
    dry_run: bool,
) -> tuple[str, int]:
    """Apply the bump to every release package; return (combined_unified_diff, edited_count).

    `edited_count` is the number of files whose content changed.
    """
    config = read_release_config(root_pyproject)
    located = locate_packages(root_pyproject, config)
    known_siblings = set(config.all_packages)
    root_dir = root_pyproject.parent

    diff_parts: list[str] = []
    edited = 0

    # Walk in publish_order first, then lockstep_unpublished — deterministic ordering.
    for pkg_name in config.all_packages:
        path = located[pkg_name]
        original = path.read_text(encoding="utf-8")
        new_text, edits = rewrite_pyproject(original, new_version, known_siblings)
        if not edits:
            continue
        edited += 1
        rel = path.relative_to(root_dir).as_posix()
        diff_parts.append(
            "".join(
                difflib.unified_diff(
                    original.splitlines(keepends=True),
                    new_text.splitlines(keepends=True),
                    fromfile=f"a/{rel}",
                    tofile=f"b/{rel}",
                )
            )
        )
        if not dry_run:
            path.write_text(new_text, encoding="utf-8")

    return "\n".join(diff_parts), edited


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="bump_version",
        description="Bump every haywire monorepo package to a new lockstep version.",
    )
    parser.add_argument("new_version", help="Target version, e.g. 0.0.2")
    parser.add_argument(
        "--root",
        type=Path,
        default=Path("pyproject.toml"),
        help="Path to the workspace root pyproject.toml (default: ./pyproject.toml)",
    )
    parser.add_argument(
        "--yes",
        action="store_true",
        help="Skip the confirmation prompt (for scripted use).",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print the diff but do not write any files.",
    )
    args = parser.parse_args(argv)

    # First pass: dry-run so we can show the diff before writing.
    diff_text, edited = apply_bump(args.root, args.new_version, dry_run=True)
    if edited == 0:
        print(f"Nothing to do: all packages already at version {args.new_version}.")
        return 0

    print(diff_text)
    print(f"\n{edited} file(s) will change. Target version: {args.new_version}.")

    if args.dry_run:
        return 0

    if not args.yes:
        try:
            response = input("Apply changes? [y/N] ").strip().lower()
        except EOFError:
            response = ""
        if response != "y":
            print("Aborted.")
            return 1

    # Second pass: actually write.
    apply_bump(args.root, args.new_version, dry_run=False)
    print(f"Wrote {edited} file(s).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
