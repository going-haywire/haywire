"""The Share Project wizard's state machine, free of NiceGUI calls.

Every ``advance_from_*`` method drives :class:`SharePipeline` and updates
``step`` / ``error`` / ``warnings``; the render functions in ``chrome.py`` and
``panels.py`` read that state. That split is what makes the flow testable
without a browser.

The generic machinery (step/error/warnings/log bookkeeping, retry, fail) lives
in :class:`haywire.ui.components.stepper.StepFlow`; this class adds only the
share-specific transitions and the structured ``PreconditionFailure`` list
that the wizard's error banner renders row by row.

Failure posture mirrors the pipeline's: a failed step stays put with an inline
error and is retryable in place. Nothing is rolled back, because nothing was
mutated past the point of failure — every precondition is checkable without
mutation.
"""

from __future__ import annotations

import asyncio
import logging
from pathlib import Path
from typing import TYPE_CHECKING, Optional

from haywire.ui.components.popup import Popup
from haywire.ui.components.stepper import StepFlow
from haywire_studio.packaging.share.pipeline import (
    CommitPlan,
    CommitResult,
    DocsResult,
    DriftReport,
    FrameworkPlan,
    PreconditionFailure,
    PreconditionsError,
    PreconditionsReport,
    PushResult,
    ShareError,
    SharePipeline,
    VersionPlan,
)

from .copy import STEP_TITLES, STEPS

if TYPE_CHECKING:
    from haybale_marketplace.library_manager import LibraryManager

logger = logging.getLogger(__name__)


class ShareWizard(StepFlow):
    """Linear, resumable state machine for the Share Project flow."""

    STEPS = STEPS
    STEP_TITLES = STEP_TITLES

    def __init__(
        self,
        *,
        pipeline: SharePipeline,
        popup: Optional[Popup],
        manager: "LibraryManager | None" = None,
    ) -> None:
        super().__init__()
        self.pipeline = pipeline
        self.popup = popup
        # Optional: lets advance_from_version() hot-swap the live registry after
        # a bump (Option B). None when the wizard is driven without a running
        # studio (e.g. the CLI) — the bump is then file-only, same as before.
        self.manager = manager
        self.precondition_failure: PreconditionFailure | None = None
        # One-shot: set by fail(), drained by the current panel on its next
        # render (see _drain_pending_modal in panels.py). Either a
        # PreconditionFailure (step 1 -> remedy modal) or the plain error
        # string of a rolled-back mid-pipeline failure (-> rollback modal,
        # Task 7). Kept separate from `precondition_failure` (which persists
        # so the open modal can read it) precisely so a redraw does not
        # reopen the dialog — see
        # .insights/feedback_nicegui_redraw_deletes_handler_slot.md.
        self.pending_modal: PreconditionFailure | str | None = None

        self.preconditions_report: PreconditionsReport | None = None
        self.drift_report: DriftReport | None = None
        self.drift_choice: str | None = None
        self.framework_plan: FrameworkPlan | None = None
        self.version_plan: VersionPlan | None = None
        self.docs_result: DocsResult | None = None
        self.commit_plan: CommitPlan | None = None
        self.commit_result: CommitResult | None = None
        self.push_result: PushResult | None = None
        # Set by advance_from_version() when it hot-swaps at least one library.
        # _panel_done reads this to decide whether the restart affordance is
        # still needed (a library that declared needs_restart=True) or the
        # hot-swap already made the running registry current.
        self.hot_swap_needs_restart: bool = False
        self.hot_swapped_libraries: list[str] = []

    # ── read-only helpers for the panels ─────────────────────────────────────

    def installed_version(self, dist_name: str) -> str:
        """The installed version of *dist_name*, or "" when it cannot be read.

        Feeds the "floor at the installed version" pin option. Empty means the
        option degrades to a bare declaration rather than inventing a floor.
        """
        import importlib.metadata as _meta

        try:
            return _meta.version(dist_name)
        except _meta.PackageNotFoundError:
            return ""

    @property
    def decorator_registrations(self) -> dict[Path, list[str]]:
        """Per-library ``@library(dependencies)`` entries the wizard adds itself.

        Not a decision, so not a screen: every name here is a registered haywire
        library the source demonstrably imports. Surfaced on Findings and again
        on Confirm so the author sees the edit, but never asked about.
        """
        report = self.drift_report
        if report is None:
            return {}
        return {
            drift.lib_dir: list(drift.decorator_missing)
            for drift in report.libraries
            if drift.decorator_missing
        }

    def dependency_writes(self) -> dict[Path, list[str]]:
        """Each touched library's current ``[project] dependencies``, from disk.

        Read back rather than reconstructed from the choices: the confirm screen
        exists to show what the writes actually produced, and a preview built
        from intent would agree with itself even when the write disagreed.
        """
        from haywire.core.library.dep_edit import read_dependencies

        out: dict[Path, list[str]] = {}
        for path in self.pipeline.written:
            if path.name != "pyproject.toml":
                continue
            lib_dir = path.parent
            try:
                out[lib_dir] = read_dependencies(lib_dir)
            except (OSError, ValueError):
                continue
        return out

    # ── state transitions ────────────────────────────────────────────────────

    def retry(self) -> None:
        """Clear the error so the current step can be attempted again.

        Warnings are kept: a stale uv.lock is still stale after a retry.
        """
        super().retry()
        self.precondition_failure = None
        self.pending_modal = None

    def fail(self, exc: BaseException) -> None:
        """Record a failure without advancing. Keeps the user on the step.

        ``PreconditionsError`` carries a single structured ``PreconditionFailure``
        — stashed separately so the wizard can open a remedy modal instead of
        the shared chrome's generic one-line error banner. ``pending_modal`` is
        the one-shot request the panel drains on its next render; see
        :meth:`take_pending_modal`.
        """
        super().fail(exc)
        self.precondition_failure = exc.failure if isinstance(exc, PreconditionsError) else None
        if self.precondition_failure is not None:
            self.pending_modal = self.precondition_failure

    def take_pending_modal(self) -> PreconditionFailure | str | None:
        """Return the queued modal request, clearing it. One-shot by design.

        Pure state, no NiceGUI: the panel calls this during its own render and
        opens the dialog itself, keeping this class testable without a browser
        (the split this module's docstring describes).
        """
        pending, self.pending_modal = self.pending_modal, None
        return pending

    async def advance_from_preconditions(self) -> None:
        """Report only on the project's health — the drift scan is step 2.

        Both halves used to run here, which mislabelled the wait: most of it
        was the drift scan while the progress bar still said "Check the
        project". Splitting them means each step's wait matches its label.
        """
        self.retry()
        try:
            # git ls-remote is a real network round-trip (~2s). On the event
            # loop it starves NiceGUI's heartbeat and the browser shows
            # "connection lost" — so it runs in a thread.
            self.preconditions_report = await asyncio.to_thread(self.pipeline.require_preconditions)
        except ShareError as exc:
            self.fail(exc)
            return
        self.step = "checked"

    async def advance_from_checked(self) -> None:
        """Run the detect scan. Costs ~0.5s per barn library, so: a thread."""
        self.retry()
        try:
            self.drift_report = await asyncio.to_thread(self.pipeline.check_drift)
            self.framework_plan = await asyncio.to_thread(self.pipeline.plan_framework)
        except ShareError as exc:
            self.fail(exc)
            return
        self.step = "detect"

    async def advance_from_detect(self) -> None:
        """Detect writes nothing, so there is nothing to apply — just move on."""
        self.retry()
        self.step = "framework"

    async def advance_from_framework(self, specifier: str) -> None:
        """Write the one authored floor: ``haywire-core``, everywhere.

        Runs BEFORE the other dependency screens so ``plan_framework()`` reads
        the author's actual prior declaration. When this ran after them, "keep
        the current declaration" computed from a value another step had already
        rewritten, and the recommended option silently raised the floor.

        Also applies the ``@library(dependencies)`` registrations, which need no
        author input — see ``apply_decorator_registrations``. Done here, at the
        first writing step, so it lands exactly once no matter which of the
        later screens the author interacts with.

        An invalid specifier raises InvalidSpecifierError (a ShareError), which
        keeps the user on this step with the message inline — same retry-in-place
        posture as every other step.
        """
        self.retry()
        try:
            self.pipeline.apply_framework(specifier)
            if self.decorator_registrations:
                await asyncio.to_thread(
                    self.pipeline.apply_decorator_registrations, self.decorator_registrations
                )
        except ShareError as exc:
            self.fail(exc)
            return
        self.step = "unused"

    async def advance_from_unused(self, removals: dict[Path, list[str]]) -> None:
        """Drop the declarations the author ticked. An empty mapping writes nothing.

        Irreversible here, and a dynamic import is indistinguishable from an
        unused declaration, so nothing is pre-selected.
        """
        self.retry()
        try:
            if removals:
                await asyncio.to_thread(self.pipeline.apply_removals, removals)
        except ShareError as exc:
            self.fail(exc)
            return
        self.step = "undeclared"

    async def advance_from_undeclared(
        self,
        pyproject_entries: dict[Path, list[str]],
        *,
        skipped: bool = False,
    ) -> None:
        """Declare the imports the author chose to declare, with their chosen pins.

        *skipped* marks that at least one import is being published undeclared —
        the one dependency state that breaks a consumer's install, and therefore
        the only one that is recorded rather than silently allowed.
        """
        self.retry()
        try:
            if pyproject_entries:
                await asyncio.to_thread(self.pipeline.apply_additions, pyproject_entries)
            if skipped:
                self.pipeline.acknowledge_undeclared()
        except ShareError as exc:
            self.fail(exc)
            return
        self.step = "floors"

    async def advance_from_floors(self, floors: dict[Path, list[str]]) -> None:
        """Rewrite only the floors the author actively changed.

        Every control defaults to the declared specifier, so an untouched screen
        yields an empty mapping and nothing narrows.
        """
        self.retry()
        try:
            if floors:
                await asyncio.to_thread(self.pipeline.apply_floors, floors)
        except ShareError as exc:
            self.fail(exc)
            return
        self.step = "confirm"

    async def advance_from_confirm(self) -> None:
        """The dependency writes are done; plan the version bump."""
        self.retry()
        try:
            self.version_plan = await asyncio.to_thread(self.pipeline.plan_version)
        except ShareError as exc:
            self.fail(exc)
            return
        self.step = "version"

    async def advance_from_version(self, spec: str) -> None:
        self.retry()
        try:
            result = self.pipeline.apply_bump(spec)
        except ShareError as exc:
            self.fail(exc)
            return
        if result.lock_warning:
            self.warnings.append(result.lock_warning)
        await self._hot_swap_bumped_libraries()
        self.step = "docs"

    async def _hot_swap_bumped_libraries(self) -> None:
        """Re-import every bumped barn library still live in this process.

        apply_bump() only rewrote each library's @library(version=...) decorator
        on disk — same file-level edit update_library_identity() makes for a
        metadata-only change, and like that path this evicts the stale module
        (registry.remove_library()) and rescans, so the running registry picks
        up the new version without a restart in the common case.

        Best-effort: a library not found live (not yet enabled, or this wizard
        is driven without a manager — e.g. the CLI) is skipped, not an error —
        the bump itself already succeeded and is not rolled back.

        needs_restart is OR'd across every hot-swapped library, same semantics
        as install()'s eviction path: a library's author-declared flag is
        binding, and the running process may still hold stale module objects
        underneath the freshly reloaded class even after remove_library().
        """
        if self.manager is None or self.pipeline.version is None:
            return
        registry = self.manager.registry
        plan = self.version_plan
        dist_names = [lib.name for lib in plan.current] if plan is not None else []

        swapped: list[str] = []
        needs_restart = False
        for dist_name in dist_names:
            lib_id = registry.find_library_by_distribution_name(dist_name)
            if lib_id is None:
                continue
            identity = registry.get_library_identity(lib_id)
            needs_restart = needs_restart or identity.needs_restart
            registry.remove_library(lib_id)
            swapped.append(lib_id)

        if not swapped:
            return

        await asyncio.to_thread(registry.scan_for_libraries)
        registry.enable_all_libraries()
        self.hot_swapped_libraries = swapped
        self.hot_swap_needs_restart = needs_restart

    async def advance_from_docs(self) -> None:
        self.retry()
        try:
            self.docs_result = await self.pipeline.apply_docs(on_output=self.push_log)
            stall = self.pipeline.apply_marketstall()
            if stall.warning:
                self.warnings.append(stall.warning)
            self.commit_plan = self.pipeline.plan_commit()
        except ShareError as exc:
            self.fail(exc)
            return
        self.step = "commit"

    async def advance_from_commit(self, message: str, include_barn: list[Path]) -> None:
        self.retry()
        try:
            # Verified BEFORE committing: someone may have pushed since step 1,
            # and discovering that after a commit and tag exist leaves cleanup.
            self.pipeline.verify_push_allowed()
            plan = self.pipeline.plan_commit(message=message)
            self.commit_plan = plan
            self.commit_result = self.pipeline.apply_commit(plan, include_barn=include_barn)
        except ShareError as exc:
            self.fail(exc)
            return
        self.step = "push"

    async def advance_from_push(self) -> None:
        self.retry()
        try:
            self.push_result = await self.pipeline.apply_push(on_output=self.push_log)
        except ShareError as exc:
            self.fail(exc)
            return
        self.step = "done"
