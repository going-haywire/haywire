"""Shape checks for the share pipeline's exceptions and result dataclasses."""

from pathlib import Path

import pytest

from haywire_studio.share_pipeline import (
    BarnDirtyFile,
    BumpResult,
    CommitError,
    CommitPlan,
    DocsGenerationError,
    DriftReport,
    LibraryVersion,
    PreconditionsError,
    PreconditionsReport,
    PushError,
    ShareError,
    TagCollisionError,
    VersionPlan,
)

pytestmark = pytest.mark.unit


def test_every_error_is_a_share_error() -> None:
    for cls in (PreconditionsError, TagCollisionError, DocsGenerationError, CommitError, PushError):
        assert issubclass(cls, ShareError)
    assert issubclass(ShareError, RuntimeError)


def test_preconditions_error_carries_all_failures() -> None:
    exc = PreconditionsError(["no git", "no remote"])
    assert exc.failures == ["no git", "no remote"]
    # Every failure appears in the message — the CLI prints str(exc) verbatim.
    assert "no git" in str(exc)
    assert "no remote" in str(exc)


def test_preconditions_report_ok_iff_no_failures() -> None:
    assert PreconditionsReport(failures=[], remote_url="u", barn_libraries=[Path("a")]).ok is True
    assert PreconditionsReport(failures=["x"], remote_url=None, barn_libraries=[]).ok is False


def test_tag_collision_error_reports_where() -> None:
    exc = TagCollisionError(tag="v1.2.3", local=True, remote=False)
    assert exc.tag == "v1.2.3"
    assert exc.local is True
    assert exc.remote is False
    assert "v1.2.3" in str(exc)


def test_version_plan_flags_disagreement() -> None:
    agreeing = VersionPlan(
        current=[LibraryVersion(lib_dir=Path("a"), name="a", version="0.1.0")],
        common_version="0.1.0",
        suggestions={"patch": "0.1.1", "minor": "0.2.0", "major": "1.0.0"},
    )
    assert agreeing.versions_agree is True

    disagreeing = VersionPlan(
        current=[
            LibraryVersion(lib_dir=Path("a"), name="a", version="0.1.0"),
            LibraryVersion(lib_dir=Path("b"), name="b", version="0.2.0"),
        ],
        common_version=None,
        suggestions={},
    )
    assert disagreeing.versions_agree is False


def test_bump_result_lists_written_files() -> None:
    result = BumpResult(
        version="0.2.0",
        written=[Path("barn/a/pyproject.toml")],
        lock_refreshed=False,
        lock_warning="uv lock failed",
    )
    assert result.version == "0.2.0"
    assert result.written == [Path("barn/a/pyproject.toml")]
    assert result.lock_warning == "uv lock failed"


def test_drift_report_needs_decision_only_when_actionable() -> None:
    assert DriftReport(drifted=[], unresolved_only=[]).needs_decision is False
    assert DriftReport(drifted=[object()], unresolved_only=[]).needs_decision is True
    # Unresolved imports are informational — they never gate the wizard.
    assert DriftReport(drifted=[], unresolved_only=[object()]).needs_decision is False


def test_commit_plan_separates_accumulated_from_dirty_barn() -> None:
    plan = CommitPlan(
        files=[Path("barn/a/pyproject.toml")],
        barn_dirty=[BarnDirtyFile(path=Path("barn/a/asset.png"), untracked=True)],
        message="chore: share v0.2.0",
        tag="v0.2.0",
    )
    assert plan.files == [Path("barn/a/pyproject.toml")]
    assert plan.barn_dirty[0].untracked is True
    assert plan.tag == "v0.2.0"


def test_push_error_carries_the_manual_command() -> None:
    exc = PushError(stderr="denied", manual_command="git p" + "ush origin master v0.2.0")
    assert exc.manual_command.endswith("v0.2.0")
    assert "denied" in str(exc)
