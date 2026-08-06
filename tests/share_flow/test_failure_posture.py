"""ShareFlow.fail() — three distinct outcomes, one of which used to be a lie.

The predecessor wizard ran the same working-tree revert for every failure past
step 1 and then told the user "every change this run made has been reverted —
nothing was left behind". After a failed push that message was false: the
commit and tag were real, `revert_working_tree` is working-tree only by design
(tests/share_pipeline/test_rollback.py asserts committed history survives), and
the user was told the slate was clean while holding an unpushed release.
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest

from haybale_share._flow._state import ShareFlow
from haywire.core.publishing.pipeline import (
    CommitResult,
    PreconditionFailure,
    PreconditionsError,
    PushError,
    SharePipeline,
)

pytestmark = pytest.mark.unit


@pytest.fixture
def flow(tmp_path: Path) -> ShareFlow:
    return ShareFlow(pipeline=SharePipeline(tmp_path))


def test_preflight_failure_never_reverts(flow: ShareFlow) -> None:
    """Preflight mutates nothing, so a revert there is a guaranteed no-op that
    still costs a git subprocess."""
    flow.step = "preflight"
    failure = PreconditionFailure(message="No 'origin' remote is configured.", kind="act")

    with patch.object(SharePipeline, "rollback") as rollback:
        flow.fail(PreconditionsError([failure]))

    rollback.assert_not_called()
    assert flow.precondition_failure is failure
    assert flow.committed_unpushed is False


def test_mid_pipeline_failure_reverts_and_reports_it_truthfully(flow: ShareFlow) -> None:
    """No commit yet, so reverting the tree really does undo everything."""
    flow.step = "review"

    with patch.object(SharePipeline, "rollback") as rollback:
        flow.fail(RuntimeError("uv lock exploded"))

    rollback.assert_called_once()
    assert flow.committed_unpushed is False


def test_push_failure_after_a_commit_does_not_claim_a_revert(flow: ShareFlow) -> None:
    """The bug this whole branch exists for.

    A commit and tag exist on disk. Reverting the working tree cannot undo
    them, so the flow must not run it and must not imply it did.
    """
    flow.step = "publish"
    flow.commit_result = CommitResult(sha="4a3f1e9", tag="v0.3.2", files=[])

    with patch.object(SharePipeline, "rollback") as rollback:
        flow.fail(PushError(stderr="rejected", manual_command="git push origin main --tags"))

    rollback.assert_not_called()
    assert flow.committed_unpushed is True


def test_committed_unpushed_exposes_the_retry_command(flow: ShareFlow) -> None:
    """The user is holding an unpushed release; the panel must be able to say
    exactly how to finish it."""
    flow.commit_result = CommitResult(sha="4a3f1e9", tag="v0.3.2", files=[])
    flow.fail(PushError(stderr="rejected", manual_command="git push origin main --tags"))

    assert flow.retry_command is not None
    assert flow.retry_command.startswith("git push")


def test_retry_command_is_none_when_nothing_was_committed(flow: ShareFlow) -> None:
    assert flow.retry_command is None


def test_a_precondition_error_raised_late_does_not_revert(flow: ShareFlow) -> None:
    """verify_push_allowed() raises PreconditionsError from the publish step.
    Rolling back on it would be wrong — it is a remediable check, not damage."""
    flow.step = "publish"

    with patch.object(SharePipeline, "rollback") as rollback:
        flow.fail(PreconditionsError([PreconditionFailure(message="remote moved on")]))

    rollback.assert_not_called()


def test_retry_clears_the_precondition_failure(flow: ShareFlow) -> None:
    flow.fail(PreconditionsError([PreconditionFailure(message="no origin")]))
    assert flow.precondition_failure is not None

    flow.retry()

    assert flow.precondition_failure is None
    assert flow.error is None
