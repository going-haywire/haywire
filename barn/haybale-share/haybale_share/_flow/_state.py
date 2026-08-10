"""The Share flow's state machine, free of NiceGUI calls.

Three screens over :class:`SharePipeline`; the render functions in
``chrome.py``/``panels.py`` read the state this class exposes. That split is
what makes the flow testable without a browser.

**Failure posture.** Three distinct outcomes, because the predecessor collapsed
them into one and told the user something false:

1. *preflight* never mutates, so a failure there stays put and the panel
   renders the remedy inline. No modal — a `ui.dialog()` opened outside a click
   handler is what made the old wizard's remedy modal stack on itself, since
   dialogs are top-level elements a panel's own container clear does not reach.
2. *review* → *publish*, before the commit lands: whatever was written is
   reverted (``pipeline.rollback()``), which is safe because preflight proved
   the tree was clean. Reporting "everything was reverted" here is TRUE.
3. *after the commit* — a failed tag or a failed push: the commit and tag are
   real and are NOT reverted (``revert_working_tree`` is working-tree only, by
   design). The predecessor ran the same rollback and showed the same
   "nothing was left behind" message, which was a lie in exactly the case
   where the user most needed the truth. :attr:`committed_unpushed` marks it,
   and the panel shows the retry command instead.
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from haywire.core.publishing.pipeline import (
    CommitPlan,
    CommitResult,
    DocsResult,
    DriftReport,
    FrameworkPlan,
    PreconditionFailure,
    PreconditionsError,
    PreconditionsReport,
    PushResult,
    ShareDecisions,
    ShareError,
    SharePipeline,
    VersionPlan,
)
from haywire.ui.components.popup import Popup
from haywire.ui.components.stepper import StepFlow

from .copy import STEP_TITLES, STEPS

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class ProjectStatus:
    """What the Share editor shows without opening the flow.

    Every field has an inert default: the editor renders whatever could be
    read and stays quiet about the rest, so an unreadable project degrades to
    a sparse card rather than an error.
    """

    libraries: list[str] = field(default_factory=list)
    version: str | None = None
    disagree: bool = False


class ShareFlow(StepFlow):
    """Linear, resumable state machine for publishing a project."""

    STEPS = STEPS
    STEP_TITLES = STEP_TITLES

    def __init__(self, *, pipeline: SharePipeline, popup: Optional[Popup] = None) -> None:
        super().__init__()
        self.pipeline = pipeline
        self.popup = popup

        # Preflight
        self.preconditions_report: PreconditionsReport | None = None
        self.precondition_failure: PreconditionFailure | None = None

        # Review — read by the panel to build its controls
        self.drift_report: DriftReport | None = None
        self.framework_plan: FrameworkPlan | None = None
        self.version_plan: VersionPlan | None = None

        # Publish
        self.docs_result: DocsResult | None = None
        self.commit_plan: CommitPlan | None = None
        self.commit_result: CommitResult | None = None
        self.push_result: PushResult | None = None

        # See the module docstring: distinguishes "reverted, nothing left
        # behind" from "a commit and tag exist locally and were NOT reverted".
        self.committed_unpushed = False

        # The exception itself, kept alongside StepFlow's `error` string.
        # Panels that lay a failure out field by field need the structured
        # form — rendering str(exc) as well would restate what they just drew
        # (PushError's message embeds both the stderr and the retry command).
        self.last_error: BaseException | None = None

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
    def retry_command(self) -> str | None:
        """The push command to run by hand, when a commit exists but is unpushed.

        Taken from the exception (``PushError.manual_command``) via
        ``StepFlow.manual_command``, never recomputed: ``push_command()``
        raises on a detached HEAD, and "the remote moved under us" is exactly
        the kind of failure that can coincide with one. Recomputing here would
        crash the panel in the one state it exists to explain.
        """
        if not self.committed_unpushed:
            return None
        return self.manual_command

    # ── state transitions ────────────────────────────────────────────────────

    def retry(self) -> None:
        """Clear the error so the current step can be attempted again.

        Warnings are kept: a stale uv.lock is still stale after a retry.
        """
        super().retry()
        self.precondition_failure = None
        self.last_error = None

    def fail(self, exc: BaseException) -> None:
        """Record a failure without advancing. Keeps the user on the step.

        Three branches, matching the three outcomes in the module docstring.
        The order matters: the post-commit check comes FIRST, because a push
        failure would otherwise fall into the mid-pipeline branch and trigger a
        revert that reports having undone a commit it cannot reach.
        """
        super().fail(exc)
        self.last_error = exc
        self.precondition_failure = exc.failure if isinstance(exc, PreconditionsError) else None
        if self.precondition_failure is not None:
            return

        if self.commit_result is not None:
            # A commit and tag exist. Nothing to revert — and saying otherwise
            # is the bug this branch exists to prevent.
            self.committed_unpushed = True
            return

        if self.step != "preflight":
            try:
                self.pipeline.rollback()
            except ShareError as rollback_exc:
                logger.error("Rollback after step %r failed: %s", self.step, rollback_exc)
                self.error = f"{self.error}\n\nAdditionally, rollback failed: {rollback_exc}"

    async def advance_from_preflight(self) -> None:
        """Check the project, then scan for drift and plan the writable steps.

        Both halves run here so the Review screen has everything it needs the
        moment it renders. `git ls-remote` is a real network round-trip (~2s)
        and the drift scan costs ~0.5s per library, so both go to a thread —
        on the event loop they starve NiceGUI's heartbeat and the browser
        shows "connection lost".
        """
        self.retry()
        try:
            self.preconditions_report = await asyncio.to_thread(self.pipeline.require_preconditions)
            self.drift_report = await asyncio.to_thread(self.pipeline.check_drift)
            self.framework_plan = await asyncio.to_thread(self.pipeline.plan_framework)
            self.version_plan = await asyncio.to_thread(self.pipeline.plan_version)
        except ShareError as exc:
            self.fail(exc)
            return
        self.step = "review"

    def apply_precondition_fix(self, fix_id: str, **kwargs: str) -> str | None:
        """Run a preflight repair. Returns an error message, or None on success.

        Returns rather than raises so the panel can show the message beside the
        button that produced it without a try/except in render code.
        """
        try:
            self.pipeline.apply_precondition_fix(fix_id, **kwargs)
        except ShareError as exc:
            return str(exc)
        return None

    async def advance_from_review(self, decisions: ShareDecisions, *, version_spec: str) -> None:
        """Write every dependency answer, then bump. The flow's first writes.

        Everything up to here was read-only, so a flow abandoned before this
        point leaves the tree exactly as it found it — which is what makes the
        revert in :meth:`fail` a narrow, provable operation rather than a
        blanket guess.
        """
        self.retry()
        try:
            await asyncio.to_thread(self.pipeline.apply_all, decisions)
            result = await asyncio.to_thread(self.pipeline.apply_bump, version_spec)
        except ShareError as exc:
            self.fail(exc)
            return
        if result.lock_warning:
            self.warnings.append(result.lock_warning)
        self.step = "publish"

    async def advance_from_publish(self, message: str | None = None) -> None:
        """Docs, marketstall, commit, tag, push, then done.

        The user decided on Review; there is no decision between these, so
        splitting them into screens would ask for three clicks to authorize one
        intent. verify_push_allowed() runs BEFORE the commit: someone may have
        pushed since preflight, and discovering that after a commit and tag
        exist leaves cleanup.

        No registry reload happens here: the bump only rewrites
        ``pyproject.toml``/``haybale.toml`` on disk, and every already-running
        library keeps its already-decorated ``class_identity`` — the version
        bump changes nothing about how the loaded modules behave. The next
        process that imports the library (a hot-reload for an unrelated code
        change, or a restart) reads the new version off disk at decoration
        time, same as always.
        """
        self.retry()
        try:
            self.docs_result = await self.pipeline.apply_docs(on_output=self.push_log)
            stall = await asyncio.to_thread(self.pipeline.apply_marketstall)
            if stall.warning:
                self.warnings.append(stall.warning)

            await asyncio.to_thread(self.pipeline.verify_push_allowed)

            plan = await asyncio.to_thread(self.pipeline.plan_commit, message=message)
            self.commit_plan = plan
            self.commit_result = await asyncio.to_thread(self.pipeline.apply_commit, plan)

            self.push_result = await self.pipeline.apply_push(on_output=self.push_log)
        except ShareError as exc:
            self.fail(exc)
            return

        self.step = "done"

    def share_url(self) -> tuple[str | None, str | None, str | None, str | None]:
        """``(pypi_url, url, tagged_url, warning)`` for the terminal screen.

        ``pypi_url`` leads because a released package is the primary way to
        consume a library; it is independent of the git URLs and present only
        when the project declares a deployed PyPI feed.
        """
        from haywire.core.publishing.marketstall import read_pypi_marketplace_url
        from haywire.core.publishing.url import derive_share_url_only

        tag = f"v{self.pipeline.version}" if self.pipeline.version else None
        derived = derive_share_url_only(self.pipeline.repo_root, tag=tag)
        pypi_url = read_pypi_marketplace_url(self.pipeline.repo_root)
        return pypi_url, derived.share_url, derived.tagged_url, derived.warning

    @staticmethod
    def project_status(repo_root: Path) -> ProjectStatus:
        """Publishing-relevant facts about *repo_root*, for the editor.

        Static and self-contained so the editor can render a status line
        without constructing a flow or writing anything. Every value is
        best-effort: the editor reports what it can read and stays silent about
        the rest rather than refusing to render — an unreadable manifest is
        preflight's story to tell, with a remedy attached, not this one's.
        """
        from haywire.core.publishing.barn import barn_library_dirs
        from haywire.core.publishing.pipeline.versions import plan_versions

        try:
            libraries = [d.name for d in barn_library_dirs(repo_root)]
        except OSError:
            return ProjectStatus()
        try:
            plan = plan_versions(repo_root)
        except Exception:  # noqa: BLE001 — see the docstring
            return ProjectStatus(libraries=libraries)
        return ProjectStatus(
            libraries=libraries,
            version=plan.common_version,
            disagree=not plan.versions_agree,
        )
