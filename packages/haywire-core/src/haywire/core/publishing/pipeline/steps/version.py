"""Step 3 — lockstep bump, tag-collision pre-check, lockfile refresh."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from haywire.core.publishing.barn import barn_library_dirs
from haywire.core.publishing.git import git, git_remote
from haywire.core.publishing.pipeline.errors import TagCollisionError, VersionError
from haywire.core.publishing.pipeline.results import BumpResult
from haywire.core.publishing.pipeline.versions import (
    next_version,
    refresh_lockfile,
    write_barn_versions,
)

if TYPE_CHECKING:
    from haywire.core.publishing.pipeline.pipeline import SharePipeline


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


def write_barn_origins(repo_root: Path) -> list[Path]:
    """Record where each barn library is published from, into its haybale.toml.

    Phase A: written before anything generates, so the marketstall row and the
    consumer read one answer rather than two that could disagree.

    Regenerated on every publish rather than authored, because it is an
    observation about *this* checkout. That is also what makes a fork correct
    for free — cloning a fork gives origin = the fork, so the first publish from
    it records the fork's URL without the author doing anything.

    ``origin_provider`` comes from the same ``resolve_host()`` call preflight
    already makes to decide whether this repo can publish at all. Recording it
    is what lets a consumer resolve a self-hosted forge with no local config:
    the hostname→provider mapping otherwise lives only in
    ``~/.haywire/config.toml``, on the publisher's machine.

    Silent no-op when there is no remote or the host is unrecognised — preflight
    already reported both, and this runs after it passed.
    """
    from urllib.parse import urlparse

    from haywire.core.library.dep_detect import find_module_dir
    from haywire.core.library.haybale_toml import HAYBALE_TOML
    from haywire.core.marketstall.host_providers import resolve_host, ssh_to_https
    from haywire.core.publishing.git import git
    from haywire.core.tomlio import edit_toml

    remote = git(["remote", "get-url", "origin"], cwd=repo_root, timeout=10.0)
    if not remote.ok or not remote.stdout.strip():
        return []
    origin = ssh_to_https(remote.stdout.strip()).removesuffix(".git").rstrip("/")
    hostname = urlparse(origin).hostname
    provider = resolve_host(hostname) if hostname else None

    written: list[Path] = []
    for lib_dir in barn_library_dirs(repo_root):
        module_dir = find_module_dir(lib_dir)
        if module_dir is None or not (module_dir / HAYBALE_TOML).is_file():
            continue
        declared = module_dir / HAYBALE_TOML
        with edit_toml(declared) as doc:
            doc["origin"] = origin
            if provider is not None:
                doc["origin_provider"] = provider.name
            else:
                doc.pop("origin_provider", None)
        written.append(declared)
    return sorted(written)


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
    written += write_barn_origins(pipeline.repo_root)
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
