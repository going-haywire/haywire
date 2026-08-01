"""``SharePipeline`` — the stateful engine behind every share caller.

Later steps consume earlier steps' outputs: drift resolution precedes docs, the
bumped version feeds both the docs render and the marketstall entry, and the
final commit's file list is the union of every step's writes. A stateful object
keeps that sequencing in one place instead of re-derived by each caller, and
maps onto the wizard's linear resumable stepper.

Each step is a check/plan call that mutates nothing plus an apply call that
does.
"""

from __future__ import annotations

from pathlib import Path
from typing import Callable

from haywire_studio.share.barn import barn_library_dirs
from haywire_studio.share.marketstall import MarketstallWriteResult
from haywire_studio.share.pipeline.errors import PipelineStateError, PreconditionsError
from haywire_studio.share.pipeline.fixes import _PRECONDITION_FIXES
from haywire_studio.share.pipeline.results import (
    BarnDirtyFile,
    BumpResult,
    CommitPlan,
    CommitResult,
    DocsResult,
    DriftReport,
    PreconditionsReport,
    PushResult,
    VersionPlan,
)
from haywire_studio.share.pipeline.steps import commit as steps_commit
from haywire_studio.share.pipeline.steps import docs as steps_docs
from haywire_studio.share.pipeline.steps import drift as steps_drift
from haywire_studio.share.pipeline.steps import preconditions as steps_preconditions
from haywire_studio.share.pipeline.steps import push as steps_push
from haywire_studio.share.pipeline.steps import version as steps_version
from haywire_studio.share.pipeline.steps.preconditions import GIT_INSTALL_HINT  # noqa: F401
from haywire_studio.share.pipeline.versions import plan_versions


class SharePipeline:
    """Drives one project's publish, one step at a time.

    Args:
        repo_root: The project root — the uv workspace root holding ``barn/``,
            ``marketstall.toml``, and the git repo.
    """

    def __init__(self, repo_root: Path) -> None:
        self.repo_root = Path(repo_root)
        # Accumulated write set. Every apply step appends the files it wrote;
        # step 5 stages exactly this list (plus any barn files the user opted
        # in) and never uses `git add -A`.
        self.written: list[Path] = []
        self.remote_url: str | None = None
        # Set when the user chose to continue past unresolved drift rather than
        # fix it. Step 5 records it in nothing — it exists so a caller can tell
        # "clean" from "acknowledged" without re-running detection.
        self.drift_acknowledged = False
        self.version: str | None = None

    # ── Step 1: preconditions ────────────────────────────────────────────────

    def check_preconditions(self) -> PreconditionsReport:
        """Verify everything needed to publish, collecting ALL failures."""
        return steps_preconditions.check(self)

    def require_preconditions(self) -> PreconditionsReport:
        """:meth:`check_preconditions`, raising :class:`PreconditionsError` on failure."""
        report = self.check_preconditions()
        if not report.ok:
            raise PreconditionsError(report.failures)
        return report

    def apply_precondition_fix(self, fix_id: str, **kwargs: str) -> None:
        """Perform the repair named by a PreconditionFailure's ``fix_id``.

        Raises ShareError on failure. Callers re-run check_preconditions()
        afterwards rather than trusting this to have made the project
        publishable — a repair fixes one fault, not the report.
        """
        handler = _PRECONDITION_FIXES.get(fix_id)
        if handler is None:
            raise PipelineStateError(f"Unknown fix_id: {fix_id!r}")
        handler(self, **kwargs)

    def record(self, paths: list[Path]) -> list[Path]:
        """Append *paths* to the accumulated write set, de-duplicated, and return them.

        Public to the step modules in ``steps/`` — they call this to register
        what they wrote. Not part of the CLI/wizard surface: callers drive the
        pipeline through the step methods and read ``written``.

        Step 5 stages exactly ``self.written``, so a duplicate would make the
        commit preview lie about how many files changed.
        """
        for path in paths:
            if path not in self.written:
                self.written.append(path)
        return paths

    # ── Step 2: dependency drift ─────────────────────────────────────────────

    def check_drift(self) -> DriftReport:
        """Scan every barn library for dependency drift."""
        return steps_drift.check(self)

    def apply_drift_union(self, report: DriftReport) -> list[Path]:
        """Additively merge detected dependencies into what is declared."""
        return steps_drift.apply_union(self, report)

    def apply_drift_replace(self, report: DriftReport) -> list[Path]:
        """Overwrite declared dependencies with exactly what was detected."""
        return steps_drift.apply_replace(self, report)

    def acknowledge_drift(self) -> None:
        """Record that the user chose to publish without resolving drift."""
        self.drift_acknowledged = True

    def _barn_library_dirs(self) -> list[Path]:
        """Every ``barn/*`` directory holding a pyproject.toml, sorted."""
        return barn_library_dirs(self.repo_root)

    # ── Step 3: version bump (lockstep) ──────────────────────────────────────

    def plan_version(self) -> VersionPlan:
        """The current lockstep state plus the bumps available from it."""
        return plan_versions(self.repo_root)

    def check_tag_available(self, version: str) -> None:
        """Raise TagCollisionError if the version tag already exists."""
        steps_version.check_tag_available(self, version)

    def apply_bump(self, spec: str) -> BumpResult:
        """Write the new version to every barn library and refresh the lock."""
        return steps_version.apply_bump(self, spec)

    # ── Step 4: regenerate docs ──────────────────────────────────────────────

    def docs_command(self, json_path: Path | None = None) -> list[str]:
        """The `haywire docs --all` argv this step will run."""
        return steps_docs.command(self, json_path)

    async def apply_docs(self, on_output: Callable[[str], None] | None = None) -> DocsResult:
        """Regenerate every library's docs in a subprocess."""
        return await steps_docs.apply(self, on_output)

    def docs_write_set(self) -> list[Path]:
        """Every doc file the generator may have written."""
        return steps_docs.write_set(self)

    # ── Step 5: marketstall + commit + tag ───────────────────────────────────

    def apply_marketstall(self) -> MarketstallWriteResult:
        """Rebuild ``marketstall.toml`` from every ``barn/*`` library."""
        return steps_commit.apply_marketstall(self)

    def barn_dirty_files(self) -> list[BarnDirtyFile]:
        """Uncommitted ``barn/`` content the pipeline did not write itself."""
        return steps_commit.barn_dirty_files(self)

    def plan_commit(self, *, message: str | None = None) -> CommitPlan:
        """Preview exactly what would be staged, committed, and tagged."""
        return steps_commit.plan(self, message=message)

    def current_branch(self) -> str | None:
        """The current branch name, or ``None`` when HEAD is detached."""
        return steps_push.current_branch(self)

    def push_command(self) -> list[str]:
        """The push argv, also shown verbatim in error panels for manual retry."""
        return steps_push.command(self)

    def verify_push_allowed(self) -> None:
        """``git push --dry-run`` — verify the remote will accept this push."""
        steps_push.verify_allowed(self)

    def apply_commit(
        self,
        plan: CommitPlan,
        *,
        include_barn: list[Path] | None = None,
    ) -> CommitResult:
        """Stage exactly ``plan.files`` plus ``include_barn``, commit, then tag."""
        return steps_commit.apply(self, plan, include_barn=include_barn)

    # ── Step 6: push ─────────────────────────────────────────────────────────

    async def apply_push(self, on_output: Callable[[str], None] | None = None) -> PushResult:
        """Push the commit and tag to ``origin``, for all callers."""
        return await steps_push.apply(self, on_output)
