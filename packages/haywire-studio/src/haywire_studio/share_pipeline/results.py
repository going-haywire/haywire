"""Frozen result dataclasses returned by each share-pipeline step."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class PreconditionsReport:
    """Outcome of step 1. ``ok`` is True iff nothing failed."""

    failures: list[str]
    remote_url: str | None
    barn_libraries: list[Path]

    @property
    def ok(self) -> bool:
        return not self.failures


@dataclass(frozen=True)
class LibraryVersion:
    """One barn library's declared version."""

    lib_dir: Path
    name: str
    version: str | None


@dataclass(frozen=True)
class VersionPlan:
    """What step 3 could do, before the user picks.

    ``common_version`` is the shared version when every library agrees, else
    None. ``suggestions`` maps "patch"/"minor"/"major" to the resolved X.Y.Z
    and is EMPTY when the versions disagree — there is no honest arithmetic to
    offer, so the user must name a target explicitly (ADR 0023).
    """

    current: list[LibraryVersion]
    common_version: str | None
    suggestions: dict[str, str]

    @property
    def versions_agree(self) -> bool:
        return self.common_version is not None


@dataclass(frozen=True)
class BumpResult:
    """Step 3's mutation record. ``lock_warning`` is set when uv lock failed."""

    version: str
    written: list[Path]
    lock_refreshed: bool
    lock_warning: str | None = None


@dataclass(frozen=True)
class DriftReport:
    """Step 2's findings, aggregated across barn libraries.

    ``drifted`` holds ``DepDrift`` objects with actionable drift;
    ``unresolved_only`` holds those with only unmapped imports. Only the former
    is a decision — unresolved imports are usually dynamic and would otherwise
    gate every run.
    """

    drifted: list[Any]
    unresolved_only: list[Any]

    @property
    def needs_decision(self) -> bool:
        return bool(self.drifted)


@dataclass(frozen=True)
class DocsResult:
    """Step 4's outcome. ``coverage`` maps library id → coverage-gap lines."""

    coverage: dict[str, list[str]]
    written: list[Path]
    output: str = ""

    @property
    def total_gaps(self) -> int:
        return sum(len(lines) for lines in self.coverage.values())


@dataclass(frozen=True)
class BarnDirtyFile:
    """An uncommitted file under barn/ — invisible to consumers if left out."""

    path: Path
    untracked: bool


@dataclass(frozen=True)
class CommitPlan:
    """Step 5's preview: exactly what would be staged, committed, and tagged.

    ``files`` is the pipeline's own accumulated write set. ``barn_dirty`` is
    offered as opt-in extras — uncommitted barn content is silently absent for
    consumers, which is the one working-tree state that corrupts a publish.
    """

    files: list[Path]
    barn_dirty: list[BarnDirtyFile]
    message: str
    tag: str
    diffstat: str = ""


@dataclass(frozen=True)
class CommitResult:
    """Step 5's mutation record."""

    sha: str
    tag: str
    files: list[Path]


@dataclass(frozen=True)
class PushResult:
    """Step 6's outcome."""

    remote: str
    branch: str
    tag: str
    output: str = ""


@dataclass(frozen=True)
class SharePlan:
    """Everything ``plan()`` can determine without mutating anything.

    Drives ``haywire share --check`` and the wizard's summary panel.
    """

    preconditions: PreconditionsReport
    drift: DriftReport
    versions: VersionPlan
    stale_docs: list[Path] = field(default_factory=list)
    stale_marketstall: bool = False

    @property
    def is_clean(self) -> bool:
        """True when nothing drifted and nothing is stale — ``--check`` exits 0."""
        return (
            self.preconditions.ok
            and not self.drift.needs_decision
            and not self.stale_docs
            and not self.stale_marketstall
        )
