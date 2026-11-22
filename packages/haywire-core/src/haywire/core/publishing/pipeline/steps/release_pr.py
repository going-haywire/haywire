"""The release branch of a release PR: where the release commit goes instead of the default branch."""

from __future__ import annotations

import os
import shutil
from typing import TYPE_CHECKING

from haywire.core.publishing.git import git, git_remote, run
from haywire.core.publishing.pipeline.errors import CommitError, PipelineStateError

if TYPE_CHECKING:
    from haywire.core.publishing.pipeline.pipeline import SharePipeline

BRANCH_PREFIX = "release/v"


def branch_name(version: str) -> str:
    return f"{BRANCH_PREFIX}{version}"


def verify_branch_free(pipeline: SharePipeline) -> None:
    """Raise :class:`PipelineStateError` when the release branch exists locally or on ``origin``."""
    if pipeline.version is None:
        raise PipelineStateError("A release PR needs a version: run the bump first.")
    branch = branch_name(pipeline.version)
    if git(["rev-parse", "--verify", "--quiet", f"refs/heads/{branch}"], cwd=pipeline.repo_root).ok:
        raise PipelineStateError(
            f"The branch {branch} already exists locally. Delete it, or finish the release it holds."
        )
    probe = git_remote(["ls-remote", "--heads", "origin", branch], cwd=pipeline.repo_root)
    if probe.ok and f"refs/heads/{branch}" in probe.stdout:
        raise PipelineStateError(
            f"The branch {branch} already exists on origin: a release PR for this version may be open."
        )


def start(pipeline: SharePipeline) -> str:
    """Create and switch to the release branch, carrying the working tree; return its name."""
    assert pipeline.version is not None
    pipeline.start_branch = pipeline.current_branch()
    branch = branch_name(pipeline.version)
    made = git(["switch", "-c", branch], cwd=pipeline.repo_root)
    if not made.ok:
        raise CommitError(f"Could not create branch {branch}: {made.stderr.strip()}", stderr=made.stderr)
    return branch


def pull_request_args(version: str, *, base: str, title: str) -> list[str]:
    """The ``gh`` command line that opens the release PR of *version* into *base*."""
    body = f"Release v{version}, committed by `haywire share --pr`. Merging it publishes v{version}."
    head = branch_name(version)
    return ["gh", "pr", "create", "--base", base, "--head", head, "--title", title, "--body", body]


def open_pull_request(pipeline: SharePipeline, *, base: str, title: str) -> tuple[str | None, str | None]:
    """Open the release PR of the pushed release branch with the GitHub CLI.

    Returns:
        ``(url, None)`` when the PR was opened, else ``(None, reason)``: ``gh`` is
        not installed, not signed in, the remote is not on GitHub, or ``gh``
        refused for another reason it states.
    """
    assert pipeline.version is not None
    if shutil.which("gh") is None:
        return None, "The GitHub CLI (gh) is not installed, so the PR was not opened."
    created = run(
        pull_request_args(pipeline.version, base=base, title=title),
        cwd=pipeline.repo_root,
        timeout=60.0,
        env={**os.environ, "GH_PROMPT_DISABLED": "1"},
    )
    if not created.ok:
        detail = (created.stderr or created.stdout).strip().splitlines()
        return None, f"gh could not open the PR: {detail[-1] if detail else 'no output'}"
    lines = created.stdout.strip().splitlines()
    return (lines[-1] if lines else None), None


def leave(pipeline: SharePipeline) -> None:
    """Switch back to the branch the run started on. Best effort."""
    if pipeline.start_branch:
        git(["switch", pipeline.start_branch], cwd=pipeline.repo_root)
