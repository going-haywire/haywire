"""Step 6 — push the commit and tag to origin."""

from __future__ import annotations

from typing import TYPE_CHECKING, Callable

from haywire_studio.packaging.share.barn import current_ref
from haywire_studio.packaging.share.git import git_remote, git_remote_streaming
from haywire_studio.packaging.share.pipeline.errors import PipelineStateError, PushError
from haywire_studio.packaging.share.pipeline.results import PushResult

if TYPE_CHECKING:
    from haywire_studio.packaging.share.pipeline.pipeline import SharePipeline


def current_branch(pipeline: "SharePipeline") -> str | None:
    """The current branch name, or ``None`` when HEAD is detached.

    Delegates to :func:`haywire_studio.packaging.share.barn.current_ref`. Unlike the
    method this replaced, it never returns the literal string ``"HEAD"``
    — that was a detached-HEAD sentinel masquerading as a branch name,
    and it silently corrupted push refspecs (``HEAD:HEAD``) downstream.
    Every call site below is reached only after :meth:`SharePipeline.check_preconditions`
    has already rejected detached HEAD unconditionally, so ``None`` is
    not expected at runtime here — callers still handle it explicitly
    rather than trust that invariant blindly.
    """
    return current_ref(pipeline.repo_root)


def command(pipeline: "SharePipeline") -> list[str]:
    """The push argv, also shown verbatim in error panels for manual retry."""
    branch = current_branch(pipeline)
    if branch is None:
        raise PipelineStateError(
            "push_command() needs a checked-out branch, but HEAD is detached. "
            "check_preconditions() should have rejected this already."
        )
    tag = f"v{pipeline.version}" if pipeline.version else ""
    args = ["push", "origin", f"HEAD:{branch}"]
    if tag:
        args.append(tag)
    return args


def verify_allowed(pipeline: "SharePipeline") -> None:
    """``git push --dry-run`` — verify the remote will accept this push.

    Run immediately BEFORE the commit, closing the race window opened at
    step 1: someone else may have pushed meanwhile, and discovering that
    after a commit and tag exist means the user has to clean up.

    Mirrors the marketplace's ``dry_run()`` → ``install()`` pairing
    (library_manager.py:273): pre-flight verification over post-failure
    recovery, because nothing needs undoing if nothing was mutated.
    """
    branch = current_branch(pipeline)
    if branch is None:
        raise PipelineStateError(
            "verify_push_allowed() needs a checked-out branch, but HEAD is detached. "
            "check_preconditions() should have rejected this already."
        )
    probe = git_remote(
        ["push", "--dry-run", "origin", f"HEAD:{branch}"],
        cwd=pipeline.repo_root,
        timeout=120.0,
    )
    if not probe.ok:
        raise PushError(
            stderr=(probe.stderr or probe.stdout).strip(),
            manual_command="git " + " ".join(command(pipeline)),
        )


async def apply(pipeline: "SharePipeline", on_output: Callable[[str], None] | None = None) -> PushResult:
    """Push the commit and tag to ``origin``, for all callers.

    Env-hardened via :func:`git_remote_streaming`, so a missing credential
    becomes a clean error rather than an indefinite hang with no TTY. On
    failure the raised :class:`PushError` carries the exact command to run
    by hand, and the step is retryable in place — nothing here mutates
    pipeline state.
    """
    if pipeline.version is None:
        raise PipelineStateError("apply_push() needs a version — run apply_bump() (step 3) first.")

    sink = on_output or (lambda _line: None)
    branch = current_branch(pipeline)
    if branch is None:
        raise PipelineStateError(
            "apply_push() needs a checked-out branch, but HEAD is detached. "
            "check_preconditions() should have rejected this already."
        )
    args = command(pipeline)

    result = await git_remote_streaming(
        args,
        cwd=pipeline.repo_root,
        on_output=sink,
        timeout=600.0,
    )
    if not result.ok:
        raise PushError(
            stderr=(result.stderr or result.stdout).strip(),
            manual_command="git " + " ".join(args),
        )
    return PushResult(
        remote="origin",
        branch=branch,
        tag=f"v{pipeline.version}",
        output=result.stdout,
    )
