"""Precondition-fix handlers dispatched by ``SharePipeline.apply_precondition_fix``."""

from __future__ import annotations

from typing import TYPE_CHECKING, Callable

import toml

from haywire_studio.packaging.share.git import git
from haywire_studio.packaging.share.manifest.errors import ManifestReadError
from haywire_studio.packaging.share.manifest.os_field import strip_undeclarable_os_values
from haywire_studio.packaging.share.pipeline.errors import (
    ManifestError,
    PipelineStateError,
    PreconditionsError,
)
from haywire_studio.packaging.share.pipeline.results import PreconditionFailure

if TYPE_CHECKING:
    from haywire_studio.packaging.share.pipeline.pipeline import SharePipeline

# Shared by every step that reads/writes a library manifest (pyproject.toml,
# and the __init__.py decorator kept in sync with it): a malformed file or an
# I/O failure must translate to a ShareError subclass before it can reach a
# wizard step handler's `except ShareError`, never surface as the raw
# exception type.
_MANIFEST_FAILURE_TYPES = (ManifestReadError, toml.TomlDecodeError, OSError)


def _fix_add_origin(pipeline: "SharePipeline", **kwargs: str) -> None:
    """Handler for fix_id="add_origin". Requires a `url` kwarg.

    The one input-taking repair (see the plan's "The rule"): running
    `git remote add origin <url>` when no origin is configured. The url is
    stored VERBATIM — no SSH->HTTPS normalisation (`_ssh_to_https` handles
    that at derivation time, not here) and no host allow-listing against
    `resolve_host()` (that governs share-URL derivation, not pushability).

    A purely local operation (`gitcmd.git`, not `gitcmd.git_remote`) — it
    never talks to a remote, so it needs none of the credential-prompt
    hardening reserved for network-facing commands.
    """
    url = kwargs.get("url")
    if not url:
        raise PipelineStateError("apply_precondition_fix('add_origin', ...) requires a url kwarg.")

    existing = git(["remote", "get-url", "origin"], cwd=pipeline.repo_root, timeout=10.0)
    if existing.ok and existing.stdout.strip():
        raise PreconditionsError(
            [
                PreconditionFailure(
                    message=f"An 'origin' remote already exists ({existing.stdout.strip()}).",
                    remedy="Remove it first if you meant to replace it: `git remote remove origin`.",
                )
            ]
        )

    added = git(["remote", "add", "origin", url], cwd=pipeline.repo_root, timeout=10.0)
    if not added.ok:
        raise PreconditionsError(
            [
                PreconditionFailure(
                    message=f"Could not add 'origin': {(added.stderr or added.stdout).strip()}",
                    remedy="Check the URL and try again.",
                )
            ]
        )
    # No record(): `git remote add` mutates repo config, not a tracked file —
    # there is nothing here for step 5's commit to stage.


def _fix_strip_os(pipeline: "SharePipeline", **kwargs: str) -> None:
    """Handler for fix_id="strip_os". Requires a `lib_dir` kwarg: the barn
    library's directory, relative to `pipeline.repo_root` (e.g.
    "barn/haybale-alpha"), taken from the failing `PreconditionFailure.lib_dir`
    — needed because a repo can have multiple barn libraries, each with its
    own independent os fault.
    """
    lib_dir_rel = kwargs.get("lib_dir")
    if not lib_dir_rel:
        raise PipelineStateError("apply_precondition_fix('strip_os', ...) requires a lib_dir kwarg.")
    lib_dir = pipeline.repo_root / lib_dir_rel
    try:
        strip_undeclarable_os_values(lib_dir)
    except _MANIFEST_FAILURE_TYPES as exc:
        raise ManifestError(str(exc)) from exc
    pipeline.record([lib_dir / "pyproject.toml"])


# Dispatch table for `SharePipeline.apply_precondition_fix`, keyed by
# `PreconditionFailure.fix_id`. Each handler takes `(pipeline, **kwargs)` and
# performs the repair in place. An absent key is an unknown fix, not a silent
# no-op.
_PRECONDITION_FIXES: dict[str, Callable[..., None]] = {
    "strip_os": _fix_strip_os,
    "add_origin": _fix_add_origin,
}
