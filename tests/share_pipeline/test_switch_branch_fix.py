"""The switch_branch precondition fix, and the safety condition gating it.

`git switch` moves HEAD. When the current commit is already contained in the
target branch that is lossless — it just re-points HEAD. When it is NOT, the
commit becomes unreachable (recoverable via reflog, but a user would not know
to look), so the fix must refuse rather than offer a one-click way to lose work.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from haywire.core.publishing.pipeline import PreconditionsError, SharePipeline

pytestmark = pytest.mark.unit


def _git(repo: Path, *args: str) -> str:
    return subprocess.run(
        ["git", *args], cwd=repo, check=True, capture_output=True, text=True
    ).stdout.strip()


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    """A repo on `main` with one commit."""
    path = tmp_path / "repo"
    path.mkdir()
    _git(path, "init", "-b", "main")
    _git(path, "config", "user.email", "t@t.test")
    _git(path, "config", "user.name", "T")
    (path / "a.txt").write_text("a")
    _git(path, "add", "-A")
    _git(path, "commit", "-m", "first")
    return path


def test_switches_back_onto_a_branch_that_contains_head(repo: Path) -> None:
    """The common detached case: checked out a commit, made nothing new."""
    sha = _git(repo, "rev-parse", "HEAD")
    _git(repo, "checkout", "--detach", sha)

    SharePipeline(repo).apply_precondition_fix("switch_branch", branch="main")

    assert _git(repo, "rev-parse", "--abbrev-ref", "HEAD") == "main"


def test_refuses_when_the_commit_would_be_orphaned(repo: Path) -> None:
    """The whole reason this fix is conditional.

    A commit made while detached, contained by no branch: switching would
    leave it unreachable, so the fix must refuse and say how to keep it.
    """
    _git(repo, "checkout", "--detach", "HEAD")
    (repo / "b.txt").write_text("work done while detached")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-m", "detached work")
    orphan = _git(repo, "rev-parse", "HEAD")

    with pytest.raises(PreconditionsError) as caught:
        SharePipeline(repo).apply_precondition_fix("switch_branch", branch="main")

    failure = caught.value.failure
    assert failure is not None
    assert "not contained" in failure.message
    assert "git switch -c" in failure.remedy
    # And it really did not move: the work is still checked out.
    assert _git(repo, "rev-parse", "HEAD") == orphan


def test_requires_a_branch_kwarg(repo: Path) -> None:
    from haywire.core.publishing.pipeline import PipelineStateError

    with pytest.raises(PipelineStateError, match="branch kwarg"):
        SharePipeline(repo).apply_precondition_fix("switch_branch")


def test_reports_a_failed_switch_rather_than_raising_raw(repo: Path) -> None:
    """A nonexistent target is a ShareError with a hand-run remedy, not a
    subprocess traceback."""
    with pytest.raises(PreconditionsError) as caught:
        SharePipeline(repo).apply_precondition_fix("switch_branch", branch="no-such-branch")

    failure = caught.value.failure
    assert failure is not None
    assert "no-such-branch" in failure.message or "no-such-branch" in failure.remedy


# ── the failures that offer the fix ──────────────────────────────────────────


def test_detached_head_offers_the_switch_when_it_is_safe(repo: Path) -> None:
    from haywire.core.publishing.pipeline.steps.preconditions import _detached_head_failure

    _git(repo, "checkout", "--detach", "HEAD")
    failure = _detached_head_failure(SharePipeline(repo))

    assert failure.kind == "act"
    assert failure.fix_id == "switch_branch"
    assert failure.lib_dir == "main"
    # States WHY publishing is blocked, not just what to type.
    assert "nothing to push to" in failure.remedy


def test_detached_head_offers_no_button_when_work_would_be_orphaned(repo: Path) -> None:
    from haywire.core.publishing.pipeline.steps.preconditions import _detached_head_failure

    _git(repo, "checkout", "--detach", "HEAD")
    (repo / "b.txt").write_text("detached work")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-m", "detached work")

    failure = _detached_head_failure(SharePipeline(repo))

    assert failure.kind == "inform"
    assert failure.fix_id is None
    assert "unreachable" in failure.remedy


def test_wrong_branch_offers_the_switch_when_nothing_is_unmerged(repo: Path) -> None:
    from haywire.core.publishing.pipeline.steps.preconditions import _wrong_branch_failure

    _git(repo, "switch", "-c", "feature")
    failure = _wrong_branch_failure(SharePipeline(repo), current="feature", default="main")

    assert failure.kind == "act"
    assert failure.fix_id == "switch_branch"
    assert failure.lib_dir == "main"


def test_wrong_branch_offers_no_button_with_unmerged_commits(repo: Path) -> None:
    """Nothing is destroyed by switching here — the branch keeps its commits —
    but moving someone off unmerged work is their decision, not the wizard's."""
    from haywire.core.publishing.pipeline.steps.preconditions import _wrong_branch_failure

    _git(repo, "switch", "-c", "feature")
    (repo / "c.txt").write_text("unmerged")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-m", "unmerged work")

    failure = _wrong_branch_failure(SharePipeline(repo), current="feature", default="main")

    assert failure.kind == "inform"
    assert failure.fix_id is None
    assert "keeps its commits" in failure.remedy
