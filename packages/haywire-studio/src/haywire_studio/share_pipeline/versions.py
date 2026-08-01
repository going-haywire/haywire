"""Lockstep version handling for the share pipeline.

Deliberately narrower than the ``bump_version()`` it replaces:

* Only ``barn/*/pyproject.toml`` is written. The root ``pyproject.toml`` is the
  uv workspace root at a fixed version, depends on the library **unversioned**,
  and nothing reads its version.
* When the barn versions disagree, no arithmetic is offered — the caller must
  supply an explicit target. ``bump_version``'s "first barn library found"
  heuristic silently downgraded higher-versioned siblings (ADR 0023).
* Committing and tagging live in the pipeline's step 5, not here.
"""

from __future__ import annotations

import re
from pathlib import Path

from haywire_studio import gitcmd
from haywire_studio.barn import barn_library_dirs
from haywire_studio.share import read_manifest_lenient
from haywire_studio.share_pipeline.errors import VersionError
from haywire_studio.share_pipeline.results import BumpResult, LibraryVersion, VersionPlan

BUMP_KEYWORDS = ("patch", "minor", "major")

_VERSION_RE = re.compile(r"^(\d+)\.(\d+)\.(\d+)")

__all__ = [
    "BUMP_KEYWORDS",
    "BumpResult",
    "next_version",
    "plan_versions",
    "read_barn_versions",
    "refresh_lockfile",
    "write_barn_versions",
]


def read_barn_versions(repo_root: Path) -> list[LibraryVersion]:
    """Read each barn library's declared name and version.

    ``version`` is None for a library whose pyproject has no version field,
    cannot be parsed, or declares an invalid ``[tool.haywire].os`` value —
    the caller decides whether that is fatal.
    """
    out: list[LibraryVersion] = []
    for lib_dir in barn_library_dirs(repo_root):
        project = read_manifest_lenient(lib_dir).get("project", {})
        name = project.get("name", lib_dir.name)
        version = project.get("version")
        out.append(LibraryVersion(lib_dir=lib_dir, name=name, version=version))
    return out


def plan_versions(repo_root: Path) -> VersionPlan:
    """Describe the current lockstep state and the bumps available from it."""
    current = read_barn_versions(repo_root)
    distinct = {v.version for v in current if v.version is not None}

    # A single distinct version across every library, and none missing, is the
    # only state where patch/minor/major arithmetic has an unambiguous input.
    agreeing = len(distinct) == 1 and all(v.version is not None for v in current)
    common = next(iter(distinct)) if agreeing else None

    suggestions: dict[str, str] = {}
    if common is not None:
        suggestions = {kw: next_version(kw, common) for kw in BUMP_KEYWORDS}

    return VersionPlan(current=current, common_version=common, suggestions=suggestions)


def next_version(spec: str, current: str | None) -> str:
    """Resolve *spec* to a concrete ``X.Y.Z``.

    *spec* is either a keyword from :data:`BUMP_KEYWORDS` (applied to
    *current*) or an explicit version. Raises :class:`VersionError` when a
    keyword has no parsable *current*, or when an explicit version is not
    ``X.Y.Z``.
    """
    if spec not in BUMP_KEYWORDS:
        if not _VERSION_RE.match(spec):
            raise VersionError(f"'{spec}' is not a valid version (expected X.Y.Z).")
        return spec

    match = _VERSION_RE.match(current or "")
    if match is None:
        raise VersionError(
            f"Cannot compute a '{spec}' bump: no parsable current version "
            f"({current!r}). Supply an explicit X.Y.Z target instead."
        )
    major, minor, patch = (int(g) for g in match.groups())
    if spec == "major":
        major, minor, patch = major + 1, 0, 0
    elif spec == "minor":
        minor, patch = minor + 1, 0
    else:
        patch += 1
    return f"{major}.{minor}.{patch}"


def write_barn_versions(repo_root: Path, version: str) -> list[Path]:
    """Write *version* into every ``barn/*/pyproject.toml``.

    Rewrites the ``version = "..."`` line with a regex rather than round-tripping
    through toml, so comments, key order, and formatting survive untouched.
    Returns the written paths, sorted.
    """
    if not _VERSION_RE.match(version):
        raise VersionError(f"'{version}' is not a valid version (expected X.Y.Z).")

    written: list[Path] = []
    for lib_dir in barn_library_dirs(repo_root):
        pyproject = lib_dir / "pyproject.toml"
        content = pyproject.read_text()
        new_content, count = re.subn(
            r'^(version\s*=\s*")[^"]*(")',
            rf"\g<1>{version}\g<2>",
            content,
            count=1,
            flags=re.MULTILINE,
        )
        if count == 0:
            raise VersionError(f"No version field to rewrite in {pyproject}.")
        pyproject.write_text(new_content)
        written.append(pyproject)
    return sorted(written)


def refresh_lockfile(repo_root: Path, *, timeout: float = 300.0) -> tuple[bool, str | None]:
    """Re-run ``uv lock`` so the bumped member versions land in uv.lock.

    Returns ``(refreshed, warning)``. Never raises and never blocks the
    pipeline: the lockfile records member versions and drifts one release
    behind if it isn't refreshed, but a failed lock is not a reason to abandon
    a publish. Matches ``bump_version``'s existing posture.
    """
    lock_file = repo_root / "uv.lock"
    if not lock_file.is_file():
        return (False, None)

    result = gitcmd.run(["uv", "lock"], cwd=repo_root, timeout=timeout)
    if result.ok:
        return (True, None)
    if result.returncode == 127:
        return (False, "uv not found on PATH — uv.lock left stale.")
    if result.timed_out:
        return (False, f"uv lock timed out after {timeout:g}s — uv.lock left stale.")
    return (False, f"uv lock failed (uv.lock left stale): {result.stderr.strip()}")
