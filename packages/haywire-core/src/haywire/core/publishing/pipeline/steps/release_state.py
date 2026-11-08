"""Whether this checkout has already been released, from git facts and one marker file.

``detect`` answers from three facts, in order:

1. A ``v*`` tag points at ``HEAD``: ``HEAD`` is a release commit. Whether the tag
   is on ``origin`` decides ``RELEASED`` or ``UNPUSHED``.
2. The marker (``.git/haywire-share.json``) names ``HEAD`` as a commit that was
   made but never tagged: ``UNPUSHED`` with ``needs_tag``.
3. The latest ``v*`` tag is an ancestor of ``HEAD`` and nothing under ``barn/`` or
   the root ``pyproject.toml`` changed since: ``NOTHING_NEW``.

The marker lives inside ``.git`` so it never dirties the tree.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from enum import Enum
from pathlib import Path

from haywire.core.publishing.git import git, git_remote

MARKER_NAME = "haywire-share.json"

#: Paths whose change makes a new release meaningful.
RELEASE_PATHS = ("barn", "pyproject.toml")


class ReleaseKind(str, Enum):
    NONE = "none"  # nothing blocks a release
    RELEASED = "released"  # HEAD is tagged and the tag is on origin
    UNPUSHED = "unpushed"  # HEAD is a release commit that never reached origin
    NOTHING_NEW = "nothing_new"  # nothing release-relevant changed since the last tag
    STALE_MARKER = "stale_marker"  # marker names a commit that is not HEAD


@dataclass(frozen=True)
class ReleaseState:
    kind: ReleaseKind
    tag: str = ""
    sha: str = ""
    #: True when the tag does not exist locally yet (commit made, tag step failed).
    needs_tag: bool = False


def marker_path(repo_root: Path) -> Path:
    found = git(["rev-parse", "--git-path", MARKER_NAME], cwd=repo_root, timeout=10.0)
    raw = found.stdout.strip() if found.ok and found.stdout.strip() else f".git/{MARKER_NAME}"
    path = Path(raw)
    return path if path.is_absolute() else repo_root / path


def read_marker(repo_root: Path) -> dict[str, str] | None:
    try:
        data = json.loads(marker_path(repo_root).read_text())
    except (OSError, ValueError):
        return None
    return data if isinstance(data, dict) else None


def write_marker(repo_root: Path, *, tag: str, sha: str, phase: str) -> None:
    """Record an unpushed release commit. Best effort: a read-only ``.git``
    must not turn a good release into a failure -- git facts still cover it."""
    try:
        marker_path(repo_root).write_text(json.dumps({"tag": tag, "sha": sha, "phase": phase}))
    except OSError:
        pass


def clear_marker(repo_root: Path) -> None:
    try:
        marker_path(repo_root).unlink()
    except OSError:
        pass


def _head(repo_root: Path) -> str:
    return git(["rev-parse", "HEAD"], cwd=repo_root, timeout=10.0).stdout.strip()


def _tags_at_head(repo_root: Path) -> list[str]:
    out = git(["tag", "--points-at", "HEAD", "--list", "v*"], cwd=repo_root, timeout=10.0)
    return sorted(out.stdout.split()) if out.ok else []


def _remote_has_tag(repo_root: Path, tag: str) -> bool:
    probe = git_remote(["ls-remote", "--tags", "origin", tag], cwd=repo_root)
    return probe.ok and f"refs/tags/{tag}" in probe.stdout


def detect(repo_root: Path) -> ReleaseState:
    """Classify *repo_root*. Writes nothing."""
    head = _head(repo_root)
    if not head:  # unborn branch: nothing has ever been released
        return ReleaseState(ReleaseKind.NONE)

    tags = _tags_at_head(repo_root)
    if tags:
        tag = tags[-1]
        kind = ReleaseKind.RELEASED if _remote_has_tag(repo_root, tag) else ReleaseKind.UNPUSHED
        return ReleaseState(kind, tag=tag, sha=head)

    marker = read_marker(repo_root)
    if marker:
        if marker.get("sha") == head and marker.get("tag"):
            return ReleaseState(ReleaseKind.UNPUSHED, tag=marker["tag"], sha=head, needs_tag=True)
        return ReleaseState(ReleaseKind.STALE_MARKER, tag=marker.get("tag", ""), sha=marker.get("sha", ""))

    latest = git(["describe", "--tags", "--abbrev=0", "--match", "v*", "HEAD"], cwd=repo_root, timeout=10.0)
    if latest.ok and latest.stdout.strip():
        tag = latest.stdout.strip()
        unchanged = git(["diff", "--quiet", tag, "HEAD", "--", *RELEASE_PATHS], cwd=repo_root, timeout=30.0)
        if unchanged.ok:  # exit 0: no difference
            return ReleaseState(ReleaseKind.NOTHING_NEW, tag=tag, sha=head)
    return ReleaseState(ReleaseKind.NONE)
