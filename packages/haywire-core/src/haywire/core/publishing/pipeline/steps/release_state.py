"""Whether this checkout has already been released, from git facts and one marker file.

``detect`` answers from three facts, in order:

1. A ``v*`` tag points at ``HEAD``: ``HEAD`` is a release commit. Whether the tag
   is on ``origin`` decides ``RELEASED`` or ``UNPUSHED``.
2. The marker (``.git/haywire-share.json``) names ``HEAD`` as a commit that was
   made but never tagged: ``UNPUSHED`` with ``needs_tag``.
3. The declared version differs from the latest tag's, ``marketstall.toml`` is pinned to it
   and no ``v<version>`` tag exists locally or on ``origin``: ``MERGED_UNTAGGED``, a
   release that reached the branch (a merged release PR) without its tag.
4. A ``release/v<X>`` branch is on ``origin`` while no ``v<X>`` tag exists and the
   declared version is not ``<X>``: ``PR_OPEN``, a release PR waiting for its merge.
5. The latest ``v*`` tag is an ancestor of ``HEAD`` and nothing under ``barn/`` or
   the root ``pyproject.toml`` changed since: ``NOTHING_NEW``.

The marker lives inside ``.git`` so it never dirties the tree.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from enum import Enum
from pathlib import Path

from haywire.core.publishing.git import git, git_remote
from haywire.core.publishing.pipeline.versions import plan_versions

MARKER_NAME = "haywire-share.json"

#: Paths whose change makes a new release meaningful.
RELEASE_PATHS = ("barn", "pyproject.toml")


class ReleaseKind(str, Enum):
    NONE = "none"  # nothing blocks a release
    RELEASED = "released"  # HEAD is tagged and the tag is on origin
    UNPUSHED = "unpushed"  # HEAD is a release commit that never reached origin
    NOTHING_NEW = "nothing_new"  # nothing release-relevant changed since the last tag
    STALE_MARKER = "stale_marker"  # marker names a commit that is not HEAD
    MERGED_UNTAGGED = "merged_untagged"  # the declared version is new and has no tag
    PR_OPEN = "pr_open"  # a release branch is on origin and its version is not released yet


@dataclass(frozen=True)
class ReleaseState:
    kind: ReleaseKind
    tag: str = ""
    sha: str = ""
    #: True when the tag does not exist locally yet (commit made, tag step failed).
    needs_tag: bool = False
    #: The release branch of a ``PR_OPEN`` state.
    branch: str = ""


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
    """Record an unpushed release commit.

    Best effort: a read-only ``.git`` must not turn a good release into a failure --
    git facts still cover it.
    """
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


def _merged_untagged(repo_root: Path) -> str | None:
    """Return the tag the declared version lacks, or ``None``.

    Needs an earlier release tag to compare with, so a project that never released
    is never reported (its first release has its own flow).
    """
    declared = plan_versions(repo_root).common_version
    latest = git(["describe", "--tags", "--abbrev=0", "--match", "v*", "HEAD"], cwd=repo_root, timeout=10.0)
    if not declared or not latest.ok or latest.stdout.strip() == f"v{declared}":
        return None
    tag = f"v{declared}"
    # share pins every marketstall row to the version it releases; a hand-edited version leaves the old pins.
    try:
        stall = (repo_root / "marketstall.toml").read_text()
    except OSError:
        return None
    if tag not in stall and f"=={declared}" not in stall:
        return None
    if git(["rev-parse", "--verify", "--quiet", f"refs/tags/{tag}"], cwd=repo_root).ok:
        return None
    return None if _remote_has_tag(repo_root, tag) else tag


def _open_release_branch(repo_root: Path) -> tuple[str, str] | None:
    """Return ``(version, branch)`` of a release branch on origin that is still waiting, else ``None``.

    A branch is waiting while no ``v<version>`` tag is on origin and the declared
    version here differs from it (a merged release PR makes them equal, squash or not).
    """
    prefix = "refs/heads/"
    probe = git_remote(["ls-remote", "--heads", "origin", "refs/heads/release/v*"], cwd=repo_root)
    if not probe.ok:
        return None
    declared = plan_versions(repo_root).common_version
    for line in probe.stdout.splitlines():
        ref = line.split("\t")[-1].strip()
        if not ref.startswith(prefix + "release/v"):
            continue
        branch = ref.removeprefix(prefix)
        version = branch.removeprefix("release/v")
        if version != declared and not _remote_has_tag(repo_root, f"v{version}"):
            return version, branch
    return None


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

    untagged = _merged_untagged(repo_root)
    if untagged:
        return ReleaseState(ReleaseKind.MERGED_UNTAGGED, tag=untagged, sha=head, needs_tag=True)

    waiting = _open_release_branch(repo_root)
    if waiting:
        return ReleaseState(ReleaseKind.PR_OPEN, tag=f"v{waiting[0]}", branch=waiting[1])

    latest = git(["describe", "--tags", "--abbrev=0", "--match", "v*", "HEAD"], cwd=repo_root, timeout=10.0)
    if latest.ok and latest.stdout.strip():
        tag = latest.stdout.strip()
        unchanged = git(["diff", "--quiet", tag, "HEAD", "--", *RELEASE_PATHS], cwd=repo_root, timeout=30.0)
        if unchanged.ok:  # exit 0: no difference
            return ReleaseState(ReleaseKind.NOTHING_NEW, tag=tag, sha=head)
    return ReleaseState(ReleaseKind.NONE)
