"""Revert the whole working tree after a mid-pipeline failure (steps 2-6).

Safe specifically because ``steps/preconditions.py``'s clean-working-tree
check (step 1) guarantees nothing existed to lose before this run started —
so anything dirty by the time a later step fails is provably THIS run's own
writes, and a blanket revert cannot destroy pre-existing uncommitted work.
Whole-repo scope, matching the clean-tree check's own scope (not narrowed to
barn/ or marketstall.toml).
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from haywire_studio.packaging.share.git import git
from haywire_studio.packaging.share.pipeline.errors import ShareError

if TYPE_CHECKING:
    from haywire_studio.packaging.share.pipeline.pipeline import SharePipeline


class RollbackError(ShareError):
    """The revert itself failed. Nothing further is attempted automatically."""


def revert_working_tree(pipeline: "SharePipeline") -> None:
    """``git checkout -- .`` + ``git clean -fd``, whole repo.

    Purely local — never touches a remote — so uses the unhardened ``git``
    helper, not ``git_remote``. ``git clean -fd`` (no ``-x``) deliberately
    leaves gitignored files (``.venv/``, ``__pycache__/``, build output)
    alone; only untracked-and-unignored files are removed.
    """
    checkout = git(["checkout", "--", "."], cwd=pipeline.repo_root, timeout=30.0)
    if not checkout.ok:
        raise RollbackError(
            f"Could not revert tracked changes: {(checkout.stderr or checkout.stdout).strip()}"
        )
    clean = git(["clean", "-fd"], cwd=pipeline.repo_root, timeout=30.0)
    if not clean.ok:
        raise RollbackError(f"Could not remove untracked files: {(clean.stderr or clean.stdout).strip()}")
