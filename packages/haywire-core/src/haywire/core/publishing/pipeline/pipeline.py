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

from haywire.core.publishing.barn import barn_library_dirs
from haywire.core.publishing.marketstall import MarketstallWriteResult
from haywire.core.publishing.pipeline.errors import PipelineStateError, PreconditionsError
from haywire.core.publishing.pipeline.fixes import _PRECONDITION_FIXES
from haywire.core.publishing.pipeline.results import (
    BumpResult,
    CommitPlan,
    CommitResult,
    DocsResult,
    DriftReport,
    FrameworkPlan,
    PreconditionsReport,
    ShareDecisions,
    PushResult,
    VersionPlan,
)
from haywire.core.publishing.pipeline.steps import commit as steps_commit
from haywire.core.publishing.pipeline.steps import dependencies as steps_dependencies
from haywire.core.publishing.pipeline.steps import detect as steps_detect
from haywire.core.publishing.pipeline.steps import docs as steps_docs
from haywire.core.publishing.pipeline.steps import framework as steps_framework
from haywire.core.publishing.pipeline.steps import preconditions as steps_preconditions
from haywire.core.publishing.pipeline.steps import push as steps_push
from haywire.core.publishing.pipeline.steps import rollback as steps_rollback
from haywire.core.publishing.pipeline.steps import version as steps_version
from haywire.core.publishing.pipeline.steps.preconditions import GIT_INSTALL_HINT  # noqa: F401
from haywire.core.publishing.pipeline.versions import plan_versions


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
        # Set when the author chose to publish a library WITHOUT declaring
        # something its source imports. Narrow on purpose: an undeclared import
        # is the one dependency state that breaks a consumer's install, so it
        # is the one that `--yes` refuses to guess at. Unused declarations,
        # lagging floors and pin choices all have safe defaults and need no
        # acknowledgement.
        self.undeclared_acknowledged = False
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

    def rollback(self) -> None:
        """Revert every write this run made — safe because step 1 guaranteed
        a clean tree before anything was written. See steps/rollback.py."""
        steps_rollback.revert_working_tree(self)

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

    # ── Step 2: detect (pure) ────────────────────────────────────────────────

    def check_drift(self) -> DriftReport:
        """Report every barn library's dependency findings. Writes nothing."""
        return steps_detect.check(self)

    def acknowledge_undeclared(self) -> None:
        """Record that the author is publishing a knowingly-undeclared import."""
        self.undeclared_acknowledged = True

    def _barn_library_dirs(self) -> list[Path]:
        """Every ``barn/*`` directory holding a pyproject.toml, sorted."""
        return barn_library_dirs(self.repo_root)

    # ── Steps 2b–2e: the dependency writes ───────────────────────────────────
    #
    # Each apply touches only the entries it owns; see steps/dependencies.py
    # for why that is a correctness property and not a style choice.

    def plan_framework(self) -> FrameworkPlan:
        """The framework requirement on offer: keep, raise, or compatible."""
        return steps_framework.plan(self)

    def apply_framework(self, specifier: str) -> list[Path]:
        """Write *specifier* as the haywire-core floor in every barn library."""
        return steps_dependencies.apply_framework(self, specifier)

    def apply_removals(self, removals: dict[Path, list[str]]) -> list[Path]:
        """Drop declarations the source no longer imports, per library."""
        return steps_dependencies.apply_removals(self, removals)

    def apply_additions(self, pyproject_entries: dict[Path, list[str]]) -> list[Path]:
        """Declare imports the pyproject omits, using the author's chosen pins."""
        return steps_dependencies.apply_additions(self, pyproject_entries)

    def apply_decorator_registrations(self, registrations: dict[Path, list[str]]) -> list[Path]:
        """Register imported haywire libraries in ``@library(dependencies)``.

        Applied without asking — every entry is provably true and constrains
        nothing. Callers report it rather than offering it.
        """
        return steps_dependencies.apply_decorator_registrations(self, registrations)

    def apply_floors(self, floors: dict[Path, list[str]]) -> list[Path]:
        """Rewrite the declared floors the author chose to change."""
        return steps_dependencies.apply_floors(self, floors)

    def apply_all(self, decisions: ShareDecisions) -> list[Path]:
        """Write every dependency answer in one pass. Returns the write set.

        The collect-then-apply-once entry point: a caller assembles a
        :class:`ShareDecisions` (free — nothing is written while the author
        revises), then calls this once. Five writing steps become one, so a
        flow abandoned before this point leaves the tree untouched and a
        failure here has a single region to revert.

        The ORDER is load-bearing and matches what the incremental path did:
        ``framework`` first, because :func:`plan_framework` must read the
        author's actual prior declaration — when the framework write ran after
        the other dependency writes, "keep the current declaration" computed
        from a value another step had already rewritten, and the recommended
        option silently raised the floor. Registrations follow immediately, at
        the first writing step, so they land exactly once.

        Each apply is skipped when its mapping is empty, so this makes no
        subprocess calls and no writes for a decision set that changes nothing.
        """
        written: list[Path] = []
        if decisions.framework is not None:
            written += self.apply_framework(decisions.framework)
        if decisions.registrations:
            written += self.apply_decorator_registrations(decisions.registrations)
        if decisions.removals:
            written += self.apply_removals(decisions.removals)
        if decisions.additions:
            written += self.apply_additions(decisions.additions)
        if decisions.floors:
            written += self.apply_floors(decisions.floors)
        if decisions.undeclared_acknowledged:
            self.acknowledge_undeclared()
        return written

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

    def apply_commit(self, plan: CommitPlan) -> CommitResult:
        """Stage exactly ``plan.files``, commit, then tag."""
        return steps_commit.apply(self, plan)

    # ── Step 6: push ─────────────────────────────────────────────────────────

    async def apply_push(self, on_output: Callable[[str], None] | None = None) -> PushResult:
        """Push the commit and tag to ``origin``, for all callers."""
        return await steps_push.apply(self, on_output)
