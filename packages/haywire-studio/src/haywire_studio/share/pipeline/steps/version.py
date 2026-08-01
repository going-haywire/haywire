"""Step 3 — lockstep bump, tag-collision pre-check, lockfile refresh."""

from __future__ import annotations

from typing import TYPE_CHECKING

from haywire_studio.share.git import git, git_remote
from haywire_studio.share.pipeline.errors import TagCollisionError, VersionError
from haywire_studio.share.pipeline.results import BumpResult
from haywire_studio.share.pipeline.versions import next_version, refresh_lockfile, write_barn_versions

if TYPE_CHECKING:
    from haywire_studio.share.pipeline.pipeline import SharePipeline


def check_tag_available(pipeline: "SharePipeline", version: str) -> None:
    """Raise :class:`TagCollisionError` if ``v<version>`` already exists.

    Checked here, before anything is written, because this is where the fix
    is cheapest — "pick 0.3.2 instead" costs nothing, whereas discovering
    the collision at tag time leaves a commit already made.

    An unreachable remote is NOT treated as a collision: that is step 1's
    job to report, and inferring "taken" from "could not ask" would block a
    legitimate publish.
    """
    tag = f"v{version}"

    local = git(["rev-parse", "-q", "--verify", f"refs/tags/{tag}"], cwd=pipeline.repo_root)
    remote_probe = git_remote(["ls-remote", "--tags", "origin", tag], cwd=pipeline.repo_root)
    remote_hit = remote_probe.ok and f"refs/tags/{tag}" in remote_probe.stdout

    if local.ok or remote_hit:
        raise TagCollisionError(tag=tag, local=local.ok, remote=remote_hit)


def apply_bump(pipeline: "SharePipeline", spec: str) -> BumpResult:
    """Resolve *spec*, verify the tag is free, then bump every barn library.

    *spec* is ``"patch"``/``"minor"``/``"major"`` or an explicit ``X.Y.Z``.
    A keyword against libraries whose versions disagree raises
    :class:`VersionError`: there is no honest arithmetic to apply, and
    picking one sibling's version would downgrade the others.

    ``uv lock`` is always attempted (the lockfile records member versions
    and drifts a release behind otherwise) but never blocks — a failure
    comes back as ``lock_warning``.
    """
    plan = pipeline.plan_version()
    if spec not in ("patch", "minor", "major"):
        version = next_version(spec, None)
    elif plan.common_version is None:
        versions = ", ".join(f"{v.name} {v.version or '(none)'}" for v in plan.current)
        raise VersionError(
            f"Barn library versions disagree ({versions}), so a '{spec}' bump is ambiguous. "
            "Supply an explicit X.Y.Z target."
        )
    else:
        version = next_version(spec, plan.common_version)

    check_tag_available(pipeline, version)

    written = write_barn_versions(pipeline.repo_root, version)
    pipeline.record(written)

    lock_refreshed, lock_warning = refresh_lockfile(pipeline.repo_root)
    if lock_refreshed:
        pipeline.record([pipeline.repo_root / "uv.lock"])

    pipeline.version = version
    return BumpResult(
        version=version,
        written=written,
        lock_refreshed=lock_refreshed,
        lock_warning=lock_warning,
    )
