"""The Share Project wizard's state machine, free of NiceGUI calls.

Every ``advance_from_*`` method drives :class:`SharePipeline` and updates
``step`` / ``error`` / ``warnings``; the render functions in ``chrome.py`` and
``panels.py`` read that state. That split is what makes the flow testable
without a browser.

Failure posture mirrors the pipeline's: a failed step stays put with an inline
error and is retryable in place. Nothing is rolled back, because nothing was
mutated past the point of failure — every precondition is checkable without
mutation.
"""

from __future__ import annotations

import asyncio
import logging
from pathlib import Path
from typing import Callable, Optional

from nicegui.elements.log import Log

from haywire.ui.components.popup import Popup
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

logger = logging.getLogger(__name__)


class ShareWizard:
    """Linear, resumable state machine for the Share Project flow."""

    def __init__(self, *, pipeline: SharePipeline, popup: Optional[Popup]) -> None:
        self.pipeline = pipeline
        self.popup = popup
        self.step: str = "preconditions"
        self.error: str | None = None
        self.precondition_failures: list[PreconditionFailure] | None = None
        self.manual_command: str | None = None
        self.warnings: list[str] = []
        self.log_lines: list[str] = []

        self.preconditions_report: PreconditionsReport | None = None
        self.drift_report: DriftReport | None = None
        self.drift_choice: str | None = None
        self.framework_plan: FrameworkPlan | None = None
        self.version_plan: VersionPlan | None = None
        self.docs_result: DocsResult | None = None
        self.commit_plan: CommitPlan | None = None
        self.commit_result: CommitResult | None = None
        self.push_result: PushResult | None = None

        self.on_render: Callable[[], None] | None = None
        self._log_element: Log | None = None

    # ── state transitions ────────────────────────────────────────────────────

    def retry(self) -> None:
        """Clear the error so the current step can be attempted again.

        Warnings are kept: a stale uv.lock is still stale after a retry.
        """
        self.error = None
        self.precondition_failures = None
        self.manual_command = None

    def _fail(self, exc: BaseException) -> None:
        """Record a failure without advancing. Keeps the user on the step.

        ``PreconditionsError`` carries structured ``PreconditionFailure``
        objects — stashed separately so ``_render_error`` can render each as
        its own message/remedy row instead of falling back to the single
        collapsed ``error`` string every other ``ShareError`` subtype gets.
        """
        logger.exception("Share wizard step %r failed", self.step)
        self.error = str(exc)
        self.precondition_failures = exc.failures if isinstance(exc, PreconditionsError) else None
        self.manual_command = getattr(exc, "manual_command", None)

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
            self._fail(exc)
            return
        self.step = "checked"

    async def advance_from_preconditions_fix(self, fix_id: str, **kwargs: str) -> None:
        """Apply one precondition repair, then re-check from scratch.

        This is the side step off "preconditions": a failure's own fix
        button, not the main Check button. The repair itself never proves the
        project is now shareable — only a full re-check does — so this always
        re-runs :meth:`SharePipeline.check_preconditions` afterwards and
        replaces ``precondition_failures`` with whatever it finds, same as a
        fresh Check click would. Success lands on "checked", exactly where
        the Check button lands; it never reaches past that on its own — the
        user still presses Scan.

        ``apply_precondition_fix`` can itself raise ``PreconditionsError``
        (e.g. add_origin finding a pre-existing remote) — a single
        synthesized failure from a wholly different call path than step 1's
        batch report, but still a ``ShareError``, so ``_fail`` renders it the
        same way: one failure, one message/remedy row, no fix_id on it.
        """
        self.retry()
        try:
            await asyncio.to_thread(self.pipeline.apply_precondition_fix, fix_id, **kwargs)
            report = await asyncio.to_thread(self.pipeline.check_preconditions)
        except ShareError as exc:
            self._fail(exc)
            return
        if not report.ok:
            self.preconditions_report = None
            self.precondition_failures = report.failures
            self.error = "Cannot share this project yet."
            return
        self.preconditions_report = report
        self.step = "checked"

    async def advance_from_checked(self) -> None:
        """Run the drift scan. Costs ~0.5s per barn library, so: a thread."""
        self.retry()
        try:
            self.drift_report = await asyncio.to_thread(self.pipeline.check_drift)
        except ShareError as exc:
            self._fail(exc)
            return
        self.step = "drift"

    async def advance_from_drift(self, choice: str) -> None:
        """*choice* is ``"union"``, ``"replace"``, or ``"skip"``.

        Replace can destructively remove declared deps, so it is a real
        decision the caller must have already confirmed — never an auto-fix.
        """
        self.retry()
        report = self.drift_report
        try:
            if report is not None and report.needs_decision:
                if choice == "union":
                    await asyncio.to_thread(self.pipeline.apply_drift_union, report)
                elif choice == "replace":
                    await asyncio.to_thread(self.pipeline.apply_drift_replace, report)
                else:
                    self.pipeline.acknowledge_drift()
            self.framework_plan = await asyncio.to_thread(self.pipeline.plan_framework)
        except ShareError as exc:
            self._fail(exc)
            return
        self.step = "framework"

    async def advance_from_framework(self, specifier: str) -> None:
        """Write the one project-wide framework requirement, then plan the bump.

        An invalid specifier raises InvalidSpecifierError (a ShareError), which
        keeps the user on this step with the message inline — same retry-in-place
        posture as every other step.
        """
        self.retry()
        try:
            self.pipeline.apply_framework(specifier)
            self.version_plan = await asyncio.to_thread(self.pipeline.plan_version)
        except ShareError as exc:
            self._fail(exc)
            return
        self.step = "version"

    async def advance_from_version(self, spec: str) -> None:
        self.retry()
        try:
            result = self.pipeline.apply_bump(spec)
        except ShareError as exc:
            self._fail(exc)
            return
        if result.lock_warning:
            self.warnings.append(result.lock_warning)
        self.step = "docs"

    async def advance_from_docs(self) -> None:
        self.retry()
        try:
            self.docs_result = await self.pipeline.apply_docs(on_output=self._push_log)
            stall = self.pipeline.apply_marketstall()
            if stall.warning:
                self.warnings.append(stall.warning)
            self.commit_plan = self.pipeline.plan_commit()
        except ShareError as exc:
            self._fail(exc)
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
            self._fail(exc)
            return
        self.step = "push"

    async def advance_from_push(self) -> None:
        self.retry()
        try:
            self.push_result = await self.pipeline.apply_push(on_output=self._push_log)
        except ShareError as exc:
            self._fail(exc)
            return
        self.step = "done"

    def _push_log(self, line: str) -> None:
        """Collect a streamed output line.

        Modifying an existing element from a background task is always safe (no
        slot context needed) — see .insights/feedback_nicegui_async.md case 3 —
        so the log element is updated directly when one is attached.
        """
        self.log_lines.append(line)
        log = getattr(self, "_log_element", None)
        if log is not None:
            log.push(line)
