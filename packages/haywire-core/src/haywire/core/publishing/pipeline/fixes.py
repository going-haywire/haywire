"""Precondition-fix handlers dispatched by ``SharePipeline.apply_precondition_fix``.

Called directly from the Share Wizard's act-modal button handlers
(``_share_wizard/remedy_modal.py``) — NOT auto-rechecked afterward. The user
clicks the modal's own "Restart Wizard" button to re-run
``check_preconditions()`` from the top; there is no in-place recheck loop.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Callable

import toml

from haywire.core.library.dep_detect import find_module_dir
from haywire.core.library.decorator_io import _remove_decorator_field
from haywire.core.publishing.git import git
from haywire.core.publishing.manifest.errors import ManifestReadError
from haywire.core.publishing.manifest.os_field import strip_undeclarable_os_values
from haywire.core.publishing.pipeline.errors import (
    ManifestError,
    PipelineStateError,
    PreconditionsError,
)
from haywire.core.publishing.pipeline.results import PreconditionFailure

if TYPE_CHECKING:
    from haywire.core.publishing.pipeline.pipeline import SharePipeline

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


def _fix_commit_dirty_tree(pipeline: "SharePipeline", **kwargs: str) -> None:
    """Handler for fix_id="commit_dirty_tree". Requires a `message` kwarg.

    `git add -A && git commit -m <message>`, whole repo — deliberately not
    scoped to `barn/`, matching the precondition probe's own "whole repo,
    period" scope (steps/preconditions.py). This is the one act-fix that
    talks about the *entire* working tree rather than one library, because
    the failure it repairs is itself about the entire working tree.

    A purely local operation, same as the other fix handlers: no `git push`
    happens here, so no hardened env is needed.
    """
    message = kwargs.get("message")
    if not message:
        raise PipelineStateError(
            "apply_precondition_fix('commit_dirty_tree', ...) requires a message kwarg."
        )

    added = git(["add", "-A"], cwd=pipeline.repo_root, timeout=30.0)
    if not added.ok:
        raise PreconditionsError(
            [
                PreconditionFailure(
                    message=f"Could not stage changes: {(added.stderr or added.stdout).strip()}",
                    remedy="Check the working tree and try again.",
                )
            ]
        )

    committed = git(["commit", "-m", message], cwd=pipeline.repo_root, timeout=30.0)
    if not committed.ok:
        raise PreconditionsError(
            [
                PreconditionFailure(
                    message=f"Could not commit: {(committed.stderr or committed.stdout).strip()}",
                    remedy="Check the commit message and try again.",
                )
            ]
        )
    # No record(): this commits the repo's pre-existing state, not a file the
    # pipeline itself wrote — there is nothing here for step 5's commit to stage.


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


def _fix_clear_declared_path(pipeline: "SharePipeline", field: str, **kwargs: str) -> None:
    """Remove *field* from a library's ``@library(...)`` call.

    Requires a `lib_dir` kwarg relative to `pipeline.repo_root` — a repo can
    have several barn libraries, each with its own independent path fault, same
    reasoning as :func:`_fix_strip_os`.

    Clearing rather than correcting: preflight knows the declared path is wrong
    but not what the author meant instead. Repointing it is an edit, and the
    wizard's `edit` screen already offers that with inline validation.
    """
    lib_dir_rel = kwargs.get("lib_dir")
    if not lib_dir_rel:
        raise PipelineStateError(f"apply_precondition_fix('clear_{field}', ...) requires a lib_dir kwarg.")
    lib_dir = pipeline.repo_root / lib_dir_rel
    module_dir = find_module_dir(lib_dir)
    if module_dir is None:
        raise PipelineStateError(f"No module directory found under {lib_dir_rel}.")
    init_py = module_dir / "__init__.py"
    if not init_py.is_file():
        raise PipelineStateError(f"No __init__.py found under {lib_dir_rel}.")

    try:
        init_py.write_text(_remove_decorator_field(init_py.read_text(), field))
    except OSError as exc:
        raise ManifestError(str(exc)) from exc
    pipeline.record([init_py])


def _fix_clear_examples_path(pipeline: "SharePipeline", **kwargs: str) -> None:
    """Handler for fix_id="clear_examples_path"."""
    _fix_clear_declared_path(pipeline, "examples_path", **kwargs)


def _fix_clear_tests_path(pipeline: "SharePipeline", **kwargs: str) -> None:
    """Handler for fix_id="clear_tests_path"."""
    _fix_clear_declared_path(pipeline, "tests_path", **kwargs)


def _fix_switch_branch(pipeline: "SharePipeline", **kwargs: str) -> None:
    """Handler for fix_id="switch_branch". Requires a `branch` kwarg.

    Offered ONLY when the current commit is already contained in *branch* —
    the caller establishes that with ``git merge-base --is-ancestor`` before
    setting the fix (see ``steps/preconditions.py``). Re-checked here anyway,
    because the check and the click are separated by however long the user
    spent reading, and a commit made in between would be orphaned silently.

    That is the whole risk this fix guards: `git switch` moves HEAD, and any
    commit made while detached that no branch contains becomes unreachable
    (recoverable via reflog, but the user would not know to look). When HEAD
    is an ancestor of the target, there is nothing to lose — switching is
    purely a re-pointing of HEAD.

    Purely local, like every other fix handler: no remote is contacted.
    """
    branch = kwargs.get("branch")
    if not branch:
        raise PipelineStateError("apply_precondition_fix('switch_branch', ...) requires a branch kwarg.")

    contained = git(["merge-base", "--is-ancestor", "HEAD", branch], cwd=pipeline.repo_root, timeout=10.0)
    if not contained.ok:
        raise PreconditionsError(
            [
                PreconditionFailure(
                    message=(
                        f"This commit is not contained in `{branch}`, so switching would "
                        f"leave it unreachable."
                    ),
                    remedy=(
                        f"Keep the work first — `git switch -c my-branch` to put it on a "
                        f"branch, or `git branch my-branch` to mark it without moving. "
                        f"Then publish from `{branch}`."
                    ),
                )
            ]
        )

    switched = git(["switch", branch], cwd=pipeline.repo_root, timeout=30.0)
    if not switched.ok:
        raise PreconditionsError(
            [
                PreconditionFailure(
                    message=(
                        f"Could not switch to `{branch}`: {(switched.stderr or switched.stdout).strip()}"
                    ),
                    remedy=f"Switch by hand with `git switch {branch}`, then try again.",
                )
            ]
        )
    # No record(): switching branches moves HEAD, it does not write a tracked
    # file — there is nothing here for step 5's commit to stage.


# Dispatch table for `SharePipeline.apply_precondition_fix`, keyed by
# `PreconditionFailure.fix_id`. Each handler takes `(pipeline, **kwargs)` and
# performs the repair in place. An absent key is an unknown fix, not a silent
# no-op.
_PRECONDITION_FIXES: dict[str, Callable[..., None]] = {
    "strip_os": _fix_strip_os,
    "add_origin": _fix_add_origin,
    "commit_dirty_tree": _fix_commit_dirty_tree,
    "switch_branch": _fix_switch_branch,
    "clear_examples_path": _fix_clear_examples_path,
    "clear_tests_path": _fix_clear_tests_path,
}
