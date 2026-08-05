"""Shape checks for the share pipeline's exceptions and result dataclasses."""

from pathlib import Path

import pytest

from haywire.core.publishing.pipeline import (
    BumpResult,
    CommitError,
    CommitPlan,
    DocsGenerationError,
    DriftReport,
    FrameworkOption,
    FrameworkPlan,
    LibraryVersion,
    ManifestError,
    MarketstallError,
    PipelineStateError,
    PreconditionFailure,
    PreconditionsError,
    PreconditionsReport,
    PushError,
    ShareError,
    TagCollisionError,
    VersionError,
    VersionPlan,
)

pytestmark = pytest.mark.unit


def test_every_error_is_a_share_error() -> None:
    for cls in (
        PreconditionsError,
        TagCollisionError,
        DocsGenerationError,
        CommitError,
        PushError,
        MarketstallError,
        ManifestError,
        VersionError,
        PipelineStateError,
    ):
        assert issubclass(cls, ShareError)
    assert issubclass(ShareError, RuntimeError)


def test_preconditions_error_carries_all_failures() -> None:
    failures = [PreconditionFailure(message="no git"), PreconditionFailure(message="no remote")]
    exc = PreconditionsError(failures)
    assert exc.failures == failures
    # Every failure appears in the message — the CLI prints str(exc) verbatim.
    assert "no git" in str(exc)
    assert "no remote" in str(exc)


def test_preconditions_error_indents_remedy_under_its_message() -> None:
    exc = PreconditionsError([PreconditionFailure(message="no origin", remedy="git remote add origin x")])
    lines = str(exc).splitlines()
    message_index = next(i for i, line in enumerate(lines) if "no origin" in line)
    assert lines[message_index + 1].strip() == "git remote add origin x"
    assert lines[message_index + 1].startswith("      ")


def test_preconditions_report_ok_iff_no_failures() -> None:
    assert PreconditionsReport(failures=[], remote_url="u", barn_libraries=[Path("a")]).ok is True
    assert (
        PreconditionsReport(
            failures=[PreconditionFailure(message="x")], remote_url=None, barn_libraries=[]
        ).ok
        is False
    )


def test_precondition_failure_kind_defaults_to_inform_and_accepts_act() -> None:
    """``kind`` is what selects the wizard's modal shape, so its default
    matters: every failure that does not opt in must present as inform-only,
    never accidentally offering a fix button it has no handler for."""
    assert PreconditionFailure(message="x").kind == "inform"
    assert PreconditionFailure(message="x", kind="act", fix_id="add_origin").kind == "act"


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


def test_drift_report_needs_decision_only_when_something_breaks() -> None:
    from haywire.core.publishing.pipeline import DepDrift

    broken = DepDrift(lib_dir=Path("barn/a"), pyproject_missing=["numpy"])
    noted = DepDrift(lib_dir=Path("barn/b"), unused_declarations=["requests"])

    assert DriftReport(drifted=[], findings_only=[]).needs_decision is False
    assert DriftReport(drifted=[broken], findings_only=[]).needs_decision is True
    # Unused declarations, lagging floors and unresolved imports are all
    # reportable facts — none of them gate the wizard.
    assert DriftReport(drifted=[], findings_only=[noted]).needs_decision is False


def test_drift_report_lists_every_library_with_findings() -> None:
    """The Detect screen renders both buckets; drifted leads."""
    from haywire.core.publishing.pipeline import DepDrift

    broken = DepDrift(lib_dir=Path("barn/a"), pyproject_missing=["numpy"])
    noted = DepDrift(lib_dir=Path("barn/b"), unused_declarations=["requests"])

    report = DriftReport(drifted=[broken], findings_only=[noted])

    assert report.libraries == [broken, noted]


def test_commit_plan_carries_the_accumulated_write_set() -> None:
    plan = CommitPlan(
        files=[Path("barn/a/pyproject.toml")],
        message="chore: share v0.2.0",
        tag="v0.2.0",
    )
    assert plan.files == [Path("barn/a/pyproject.toml")]
    assert plan.tag == "v0.2.0"


def test_push_error_carries_the_manual_command() -> None:
    exc = PushError(stderr="denied", manual_command="git p" + "ush origin master v0.2.0")
    assert exc.manual_command.endswith("v0.2.0")
    assert "denied" in str(exc)


def test_framework_plan_carries_installed_declared_and_options() -> None:
    option = FrameworkOption(
        specifier=">=0.0.31", label="keep the current declaration", consequence="", recommended=True
    )
    plan = FrameworkPlan(installed="0.0.34", declared=">=0.0.31", options=[option])
    assert plan.options[0].recommended
    assert plan.installed == "0.0.34"


@pytest.mark.unit
def test_drift_report_decorator_registrations_reads_every_library() -> None:
    """The registrations property must NOT be limited to `drifted`.

    A missing @library(dependencies) entry is not drift, so a library whose
    only gap is this appears in `findings_only`. Reading `drifted` alone
    silently skipped exactly those — the bug that made the wizard's and the
    CLI's duplicated copies of this comprehension diverge.
    """
    from haywire.core.publishing.pipeline import DepDrift, DriftReport

    broken = DepDrift(lib_dir=Path("barn/haybale-alpha"), pyproject_missing=["numpy"])
    registration_only = DepDrift(lib_dir=Path("barn/haybale-beta"), decorator_missing=["haybale_studio"])
    report = DriftReport(drifted=[broken], findings_only=[registration_only])

    assert report.decorator_registrations == {Path("barn/haybale-beta"): ["haybale_studio"]}


@pytest.mark.unit
def test_drift_report_decorator_registrations_omits_libraries_with_none() -> None:
    """A library with nothing to register must not appear as an empty entry —
    callers treat a present key as "there is a write to make"."""
    from haywire.core.publishing.pipeline import DepDrift, DriftReport

    clean = DepDrift(lib_dir=Path("barn/haybale-alpha"), unused_declarations=["requests"])
    report = DriftReport(drifted=[], findings_only=[clean])

    assert report.decorator_registrations == {}
