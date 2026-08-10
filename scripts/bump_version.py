"""Bump every haywire monorepo publishable package to a new version.

Reads [tool.haywire.release] from the workspace root pyproject.toml,
then surgically edits every listed package's pyproject.toml:
  - rewrites `version = "X.Y.Z"` to the new version,
  - rewrites every `"<sibling>>=A.B.C"` dep on a known sibling to
    `"<sibling>>=<new>"`.

`pyproject.toml` is canon for `version`. Any package that also carries a
`haybale.toml` (its runtime-read copy, consumed by `LibraryIdentity`) gets
that file's `version` line rewritten too, so the two never disagree after a
release. This mirrors the share wizard's per-library version write
(`write_barn_versions`), minus the commit/tag/push that skill handles
separately.

Prints a unified diff of all changes and asks for confirmation before
writing. Use --yes to skip the prompt (for scripted use).
"""

from __future__ import annotations

import argparse
import difflib
import re
import sys
import tomllib
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class ReleaseConfig:
    pip_publish_order: list[str]
    git_publish_order: list[str]
    lockstep_unpublished: list[str]

    @property
    def all_packages(self) -> list[str]:
        return [*self.pip_publish_order, *self.git_publish_order, *self.lockstep_unpublished]


def read_release_config(root_pyproject: Path) -> ReleaseConfig:
    data = tomllib.loads(root_pyproject.read_text(encoding="utf-8"))
    block = data["tool"]["haywire"]["release"]
    return ReleaseConfig(
        pip_publish_order=list(block["pip_publish_order"]),
        git_publish_order=list(block.get("git_publish_order", [])),
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
# nested tables. `[project]` is the only top-level table where this should fire in
# pyproject.toml; haybale.toml has no nested tables above `version` either, so the same
# pattern is reused for both files.
_VERSION_LINE_RE = re.compile(r'^(?P<lead>\s*version\s*=\s*")[^"]+(?P<trail>")', re.MULTILINE)

# Matches a quoted PEP 508 requirement like "pkg-name>=0.0.1" or "pkg-name~=0.1.0",
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
      * every `"<sibling>>=..."` (or other operator) dep — rewritten to `>=<new_version>`.

    A floor, not a compatible release: `~=X.Y.Z` means `>=X.Y.Z, ==X.Y.*`, so a
    lockstep `~=0.0.37` silently excludes 0.1.0 for every consumer. The bump
    script's operator is a tool default, not an author policy — it must not
    stamp a ceiling nobody asked for.

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
        new = f'"{name}>={new_version}"'
        if old == new:
            return old
        edits.append(f"dep {name}: {old} → {new}")
        return new

    new_source = _DEP_REQ_RE.sub(_dep_sub, new_source)
    return new_source, edits


#: `haywire-core` ships the framework-owned `builtin` haybale nested three
#: levels inside its own source tree (`src/haywire/barn/builtin/`), not at the
#: one-library-per-package depth every other haybale uses — so it can't be
#: found by the same flat/src-layout search. Named explicitly rather than
#: generalizing the search, since nothing else in the workspace nests this way.
_BUILTIN_HAYBALE_TOML = Path("src/haywire/barn/builtin/haybale.toml")


def find_haybale_toml(pkg_dir: Path) -> Path | None:
    """Locate `haybale.toml` inside a package directory, or None if absent.

    Mirrors `haywire.core.library.dep_detect.find_module_dir`'s flat/src-layout
    search, kept as a local copy rather than an import: this script runs before
    any package is guaranteed installed, and stays dependency-free by design
    (stdlib only) so it works in a bare CI checkout.
    """
    builtin_candidate = pkg_dir / _BUILTIN_HAYBALE_TOML
    if builtin_candidate.is_file():
        return builtin_candidate

    for search_root in (pkg_dir, pkg_dir / "src"):
        if not search_root.is_dir():
            continue
        for child in sorted(search_root.iterdir()):
            if not child.is_dir() or child.name.startswith((".", "_")):
                continue
            candidate = child / "haybale.toml"
            if candidate.is_file():
                return candidate
    return None


def rewrite_haybale_toml(source: str, new_version: str) -> tuple[str, list[str]]:
    """Return (new_source, list_of_human_edit_descriptions) for one `haybale.toml`.

    Same regex-substitution approach as :func:`rewrite_pyproject`'s version line —
    a single top-level `version = "..."` key, no nested tables above it, so a
    full TOML parse buys nothing here and this script stays stdlib-only.
    """
    edits: list[str] = []

    def _version_sub(m: re.Match[str]) -> str:
        existing = m.group(0)[len(m.group("lead")) : -len(m.group("trail"))]
        if existing == new_version:
            return m.group(0)
        edits.append(f'version: "{existing}" → "{new_version}"')
        return f"{m.group('lead')}{new_version}{m.group('trail')}"

    new_source, count = _VERSION_LINE_RE.subn(_version_sub, source, count=1)
    if count == 0:
        raise ValueError('could not find `version = "..."` line in haybale.toml')
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

    # Walk in pip_publish_order, git_publish_order, then lockstep_unpublished — deterministic ordering.
    for pkg_name in config.all_packages:
        path = located[pkg_name]
        original = path.read_text(encoding="utf-8")
        new_text, edits = rewrite_pyproject(original, new_version, known_siblings)
        if edits:
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

        # A package's haybale.toml (if it has one) is the runtime-read copy of
        # `version` — kept in sync here so LibraryIdentity never lags behind
        # the pyproject.toml this bump just wrote. Not every package has one
        # (haywire-studio is the app shell, not a haybale library).
        haybale_path = find_haybale_toml(path.parent)
        if haybale_path is not None:
            haybale_original = haybale_path.read_text(encoding="utf-8")
            haybale_new, haybale_edits = rewrite_haybale_toml(haybale_original, new_version)
            if haybale_edits:
                edited += 1
                rel = haybale_path.relative_to(root_dir).as_posix()
                diff_parts.append(
                    "".join(
                        difflib.unified_diff(
                            haybale_original.splitlines(keepends=True),
                            haybale_new.splitlines(keepends=True),
                            fromfile=f"a/{rel}",
                            tofile=f"b/{rel}",
                        )
                    )
                )
                if not dry_run:
                    haybale_path.write_text(haybale_new, encoding="utf-8")

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
