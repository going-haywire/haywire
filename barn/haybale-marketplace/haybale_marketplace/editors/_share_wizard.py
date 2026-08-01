"""Share Project wizard — a stepper over :class:`SharePipeline`.

The state machine (:class:`ShareWizard`) is deliberately free of NiceGUI calls:
every ``advance_from_*`` method drives the pipeline and updates ``step`` /
``error`` / ``warnings``, and the render functions read that state. That split
is what makes the flow testable without a browser.

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

from nicegui import ui
from nicegui.elements.log import Log

from haywire.ui import elements as hui
from haywire.ui.components.popup import Popup
from haywire_studio.share_pipeline import (
    CommitPlan,
    CommitResult,
    DocsResult,
    DriftReport,
    PreconditionFailure,
    PreconditionsError,
    PreconditionsReport,
    PushResult,
    ShareError,
    SharePipeline,
    VersionPlan,
)

logger = logging.getLogger(__name__)

STEPS = ("preconditions", "checked", "drift", "version", "docs", "commit", "push", "done")

_STEP_TITLES = {
    "preconditions": "Check the project",
    "checked": "Scan dependencies",
    "drift": "Dependencies",
    "version": "Version",
    "docs": "Documentation",
    "commit": "Review and commit",
    "push": "Publish",
    "done": "Shared",
}

# Union leads: it is the only choice that is both corrective and safe.
_DRIFT_OPTIONS = {
    "union": "Union — add what's missing",
    "replace": "Replace — overwrite declarations",
    "skip": "Skip — publish as-is",
}

# (explanation, colour token, icon). The words alone can't carry these
# semantics: the two that sound safest are the destructive one and the one
# that ships a knowingly-broken artifact.
_DRIFT_EXPLANATIONS = {
    "union": (
        "Adds the dependencies listed above to each library's pyproject.toml and "
        "@library decorator, and raises any lagging version floors. Nothing is "
        "removed — declarations you already have are kept as they are.",
        "--hw-positive",
        "add_circle",
    ),
    "replace": (
        "Overwrites each library's declarations with exactly what its source "
        "imports. Anything declared but no longer imported is REMOVED — including "
        "deps you added deliberately, such as optional or runtime-only ones. "
        "The wizard cannot undo this.",
        "--hw-danger",
        "warning",
    ),
    "skip": (
        "Changes nothing and publishes with the drift unresolved. The libraries "
        "above will install for consumers without these dependencies, so they "
        "fail on import until each one is installed by hand.",
        "--hw-warning",
        "info",
    ),
}


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


# ──────────────────────────────────────────────────────────────────────────────
# Rendering
# ──────────────────────────────────────────────────────────────────────────────


def show_share_wizard(
    repo_root: Path,
    *,
    on_done: Callable[[], None] | None = None,
) -> ShareWizard:
    """Open the Share Project wizard and return its state machine.

    Not closable mid-flight past the commit step: the popup's own close button
    stays available (the wizard mutates nothing that needs undoing), but the
    step buttons are the intended path.
    """
    popup = Popup(
        title="Share Project",
        width="620px",
        closable=True,
        backdrop_click_close=False,
        escape_close=False,
    )
    wizard = ShareWizard(pipeline=SharePipeline(repo_root), popup=popup)

    with popup:
        body = ui.column().classes("w-full gap-2")

    def _render() -> None:
        body.clear()
        with body:
            _render_progress(wizard)
            _render_step(wizard, _render, on_done)

    wizard.on_render = _render
    _render()
    popup.open()
    return wizard


def _render_progress(wizard: ShareWizard) -> None:
    """A one-line step indicator. Colours come from --hw-* tokens only."""
    index = STEPS.index(wizard.step)
    with ui.row().classes("w-full items-center gap-1"):
        for position, name in enumerate(STEPS[:-1]):
            done = position < index
            active = position == index
            colour = "var(--hw-positive)" if done else ("var(--hw-accent)" if active else "var(--hw-border)")
            ui.element("div").classes("flex-1 rounded").style(f"height: 3px; background: {colour};").tooltip(
                _STEP_TITLES[name]
            )
    ui.label(_STEP_TITLES[wizard.step]).classes("text-sm font-medium")


def _render_error(wizard: ShareWizard, rerender: Callable[[], None]) -> None:
    """Inline error banner with a Retry button. Same visual as the progress modal."""
    if wizard.error is None:
        return
    with (
        ui.row()
        .classes("w-full items-start gap-2 p-2 rounded")
        .style("border-left: 3px solid var(--hw-danger); background: var(--hw-danger-bg);")
    ):
        ui.icon("error", size="16px").classes("hw-text-danger flex-shrink-0 mt-0.5")
        with ui.column().classes("gap-1 flex-1"):
            if wizard.precondition_failures:
                # Structured failures: each gets its own message + remedy row
                # so a multi-line remedy (install commands, etc.) stays
                # readable instead of collapsing into wizard.error's one line.
                with ui.column().classes("gap-2 w-full"):
                    for failure in wizard.precondition_failures:
                        with ui.column().classes("gap-0.5"):
                            ui.label(failure.message).classes("text-xs hw-text-danger whitespace-pre-line")
                            if failure.remedy:
                                ui.label(failure.remedy).classes(
                                    "text-xs hw-text-dim font-mono whitespace-pre-line"
                                )
                            if failure.fix_id:
                                _render_fix(wizard, rerender, failure)
            else:
                ui.label(wizard.error).classes("text-xs hw-text-danger whitespace-pre-line")
            if wizard.manual_command:
                hui.code_snippet(wizard.manual_command)

    def _retry() -> None:
        wizard.retry()
        rerender()

    ui.button("Retry", on_click=_retry).props("flat dense")


def _render_fix(wizard: ShareWizard, rerender: Callable[[], None], failure: PreconditionFailure) -> None:
    """One failure's own repair button, inline in its message/remedy row.

    ``add_origin`` is the only fix that takes user input — its URL field is
    the wizard's one and only form, kept inline here rather than in a dialog.
    The button stays disabled until that field is non-empty; every other fix
    needs no input and its button is live immediately.
    """
    fix_id = failure.fix_id
    assert fix_id is not None  # guarded by the caller

    with ui.row().classes("w-full items-center gap-2 mt-1"):
        url_input: ui.input | None = None
        if fix_id == "add_origin":
            url_input = hui.input_field(placeholder="git remote URL").classes("flex-1")

        fix_button = (
            ui.button(failure.fix_label or "Fix").props("flat dense").style("color: var(--hw-positive);")
        )

        def _kwargs() -> dict[str, str]:
            if url_input is not None:
                return {"url": (url_input.value or "").strip()}
            return {"lib_dir": failure.lib_dir} if failure.lib_dir is not None else {}

        fix_button.on_click(
            lambda: _busy_advance(
                wizard,
                rerender,
                fix_button,
                lambda: wizard.advance_from_preconditions_fix(fix_id, **_kwargs()),
            )
        )

        if url_input is not None:
            fix_button.set_enabled(False)
            bound_input = url_input

            def _on_url_change() -> None:
                fix_button.set_enabled(bool((bound_input.value or "").strip()))

            bound_input.on_value_change(_on_url_change)


def _render_warnings(wizard: ShareWizard) -> None:
    for warning in wizard.warnings:
        with ui.row().classes("w-full items-start gap-2"):
            ui.icon("warning", size="14px").classes("flex-shrink-0 mt-0.5").style(
                "color: var(--hw-warning);"
            )
            ui.label(warning).classes("text-xs hw-text-muted")


def _render_step(
    wizard: ShareWizard,
    rerender: Callable[[], None],
    on_done: Callable[[], None] | None,
) -> None:
    """Dispatch to the current step's panel."""
    _render_warnings(wizard)
    _render_error(wizard, rerender)

    if wizard.step == "preconditions":
        _panel_preconditions(wizard, rerender)
    elif wizard.step == "checked":
        _panel_checked(wizard, rerender)
    elif wizard.step == "drift":
        _panel_drift(wizard, rerender)
    elif wizard.step == "version":
        _panel_version(wizard, rerender)
    elif wizard.step == "docs":
        _panel_docs(wizard, rerender)
    elif wizard.step == "commit":
        _panel_commit(wizard, rerender)
    elif wizard.step == "push":
        _panel_push(wizard, rerender)
    else:
        _panel_done(wizard, on_done)


def _advance(wizard: ShareWizard, rerender: Callable[[], None], coro_factory):
    """Wrap an advance call so the panel re-renders afterwards.

    Returns the coroutine rather than scheduling it: NiceGUI wraps a returned
    Awaitable with the parent slot before scheduling, which is what keeps
    ui.notify() and element creation working. Scheduling it ourselves would
    hand the work a task with an empty slot stack.
    See .insights/feedback_nicegui_async.md.
    """

    async def _run():
        await coro_factory()
        rerender()

    return _run()


def _busy_advance(
    wizard: ShareWizard,
    rerender: Callable[[], None],
    button: ui.button,
    coro_factory,
):
    """Put *button* in a loading state for the duration of the step.

    These steps take seconds (a network round-trip, a multi-library scan), so
    without this the UI looks dead while the thread works. Returned, not
    scheduled — see :func:`_advance` for why.
    """

    async def _run():
        button.props("loading")
        try:
            await coro_factory()
        finally:
            # The panel is about to be rebuilt, but the button survives when a
            # step fails and re-renders in place.
            button.props(remove="loading")
        rerender()

    return _run()


def _panel_preconditions(wizard: ShareWizard, rerender: Callable[[], None]) -> None:
    ui.label(
        "Checks that git is available, that barn/ holds at least one library, "
        "and that origin is set and reachable."
    ).classes("text-xs hw-text-dim")
    with ui.row().classes("w-full justify-end gap-2"):
        check = ui.button("Check").props("flat dense").style("color: var(--hw-positive);")
        check.on_click(lambda: _busy_advance(wizard, rerender, check, wizard.advance_from_preconditions))


def _panel_checked(wizard: ShareWizard, rerender: Callable[[], None]) -> None:
    """The pass report for step 1, and the entry point to the drift scan."""
    report = wizard.preconditions_report

    with ui.row().classes("w-full items-center gap-2"):
        ui.icon("check_circle", size="16px").style("color: var(--hw-positive);")
        ui.label("The project can be shared.").classes("text-sm").style("color: var(--hw-positive);")

    if report is not None:
        with ui.column().classes("gap-0.5 ml-1"):
            ui.label(
                f"{len(report.barn_libraries)} librar"
                + ("y" if len(report.barn_libraries) == 1 else "ies")
                + " under barn/"
            ).classes("text-xs hw-text-dim")
            for lib in report.barn_libraries:
                rel = lib.relative_to(wizard.pipeline.repo_root)
                ui.label(str(rel)).classes("text-xs font-mono hw-text-dim ml-3")
            if report.remote_url:
                ui.label(f"origin: {report.remote_url}").classes("text-xs font-mono hw-text-dim")

    ui.label(
        "Next: scan every library for imports that aren't declared as dependencies. "
        "This reads all library sources and takes a few seconds."
    ).classes("text-xs hw-text-dim")

    with ui.row().classes("w-full justify-end gap-2"):
        scan = ui.button("Scan").props("flat dense").style("color: var(--hw-positive);")
        scan.on_click(lambda: _busy_advance(wizard, rerender, scan, wizard.advance_from_checked))


def _panel_drift(wizard: ShareWizard, rerender: Callable[[], None]) -> None:
    report = wizard.drift_report
    if report is None or not report.needs_decision:
        ui.label("No dependency drift — every import is declared.").classes("text-xs hw-text-dim")
        with ui.row().classes("w-full justify-end gap-2"):
            ui.button(
                "Continue",
                on_click=lambda: _advance(wizard, rerender, lambda: wizard.advance_from_drift("skip")),
            ).props("flat dense").style("color: var(--hw-positive);")
        return

    ui.label("These imports are not declared:").classes("text-xs hw-text-dim")
    for drift in report.drifted:
        hui.section_label(drift.lib_dir.name)
        with ui.column().classes("gap-0.5 ml-1"):
            for dep in drift.pyproject_missing:
                ui.label(f"+ pyproject.toml: {dep}").classes("text-xs font-mono").style(
                    "color: var(--hw-positive);"
                )
            for dep in drift.decorator_missing:
                ui.label(f"+ @library(dependencies): {dep}").classes("text-xs font-mono").style(
                    "color: var(--hw-positive);"
                )
            for dist, declared, installed in drift.pyproject_version_lag:
                ui.label(f"~ {dist}: declared {declared}, installed {installed}").classes(
                    "text-xs font-mono hw-text-dim"
                )

    hui.section_label("How should this be resolved?")
    # Width comes from w-full, not min_width="100%": a percentage min-width
    # resolves against a content-sized parent and collapses the dropdown.
    #
    # in_popup lifts the dropdown above the Popup card; without it the QMenu
    # (z-6000) opens behind the card (z-7001) and the list looks empty.
    choice = hui.select_field(
        options=_DRIFT_OPTIONS,
        value=wizard.drift_choice,
        label="Action",
        in_popup=True,
    ).classes("w-full")

    # The explanation is the point of the select: the three words alone can't
    # convey that Replace deletes and Skip publishes known-undeclared deps.
    explanation = ui.column().classes("gap-1 w-full")

    def _describe() -> None:
        explanation.clear()
        selected = choice.value
        if selected is None:
            return
        body, token, icon = _DRIFT_EXPLANATIONS[selected]
        with explanation:
            with (
                ui.row()
                .classes("w-full items-start gap-2 p-2 rounded")
                .style(f"border-left: 3px solid var({token});")
            ):
                ui.icon(icon, size="16px").classes("flex-shrink-0 mt-0.5").style(f"color: var({token});")
                ui.label(body).classes("text-xs hw-text-dim")

    def _on_change() -> None:
        wizard.drift_choice = choice.value
        _describe()
        confirm.set_enabled(choice.value is not None)
        # Colour the commitment: Replace deletes, Skip ships undeclared deps.
        token = _DRIFT_EXPLANATIONS[choice.value][1] if choice.value else "--hw-positive"
        confirm.style(f"color: var({token});")

    choice.on_value_change(_on_change)

    with ui.row().classes("w-full justify-end gap-2"):
        confirm = ui.button("Confirm").props("flat dense")
        confirm.on_click(
            lambda: _busy_advance(
                wizard,
                rerender,
                confirm,
                lambda: wizard.advance_from_drift(str(choice.value)),
            )
        )

    # Applies the initial state (disabled until chosen) through the same path
    # the change handler uses, so a re-render after a failure restores the
    # previous selection rather than resetting it.
    _on_change()


def _panel_version(wizard: ShareWizard, rerender: Callable[[], None]) -> None:
    plan = wizard.version_plan
    if plan is None:
        return

    hui.section_label("Current versions")
    with ui.column().classes("gap-0.5 ml-1"):
        for lib in plan.current:
            ui.label(f"{lib.name}: {lib.version or '(none)'}").classes("text-xs font-mono")

    ui.label(
        "Every barn library is published at the same version (lockstep), and the repo is tagged with it."
    ).classes("text-xs hw-text-dim")

    if plan.versions_agree:
        options = {keyword: f"{keyword} → {resolved}" for keyword, resolved in plan.suggestions.items()}
        options["custom"] = "custom…"
        # in_popup for the same reason as the drift select above.
        choice = hui.select_field(
            options=options,
            value="patch",
            label="Bump",
            in_popup=True,
        ).classes("w-full")
        custom = hui.input_field(placeholder="X.Y.Z")
        custom.bind_visibility_from(choice, "value", lambda v: v == "custom")

        def _spec() -> str:
            return (custom.value or "").strip() if choice.value == "custom" else str(choice.value)
    else:
        ui.label(
            "These versions disagree. Name the version every library should be set to — "
            "picking one automatically would downgrade the others."
        ).classes("text-xs").style("color: var(--hw-warning);")
        custom = hui.input_field(placeholder="X.Y.Z")

        def _spec() -> str:
            return (custom.value or "").strip()

    with ui.row().classes("w-full justify-end gap-2"):
        ui.button(
            "Bump",
            on_click=lambda: _advance(wizard, rerender, lambda: wizard.advance_from_version(_spec())),
        ).props("flat dense").style("color: var(--hw-positive);")


def _panel_docs(wizard: ShareWizard, rerender: Callable[[], None]) -> None:
    ui.label(
        "Regenerates OVERVIEW, QUICKREF, and per-component docs for every barn "
        "library, then rebuilds marketstall.toml. Runs in a separate process."
    ).classes("text-xs hw-text-dim")
    log = ui.log(max_lines=200).classes("w-full text-xs").style("height: 160px; font-family: monospace;")
    for line in wizard.log_lines:
        log.push(line)
    wizard._log_element = log  # noqa: SLF001 — the wizard owns this element

    with ui.row().classes("w-full justify-end gap-2"):
        ui.button(
            "Generate",
            on_click=lambda: _advance(wizard, rerender, wizard.advance_from_docs),
        ).props("flat dense").style("color: var(--hw-positive);")


def _panel_commit(wizard: ShareWizard, rerender: Callable[[], None]) -> None:
    plan = wizard.commit_plan
    if plan is None:
        return

    if wizard.docs_result is not None and wizard.docs_result.total_gaps:
        hui.section_label(f"Documentation coverage: {wizard.docs_result.total_gaps} gap(s)")
        with ui.column().classes("gap-0.5 ml-1"):
            for lib_id, lines in sorted(wizard.docs_result.coverage.items()):
                for line in lines:
                    ui.label(f"{lib_id}: {line}").classes("text-xs hw-text-dim")

    hui.section_label(f"{len(plan.files)} file(s) in this commit")
    with ui.scroll_area().classes("w-full").style("height: 140px;"):
        with ui.column().classes("gap-0.5"):
            for path in plan.files:
                rel = path.relative_to(wizard.pipeline.repo_root)
                ui.label(str(rel)).classes("text-xs font-mono hw-text-dim")

    checkboxes: list[tuple[ui.checkbox, Path]] = []
    if plan.barn_dirty:
        hui.section_label("Uncommitted content under barn/")
        ui.label(
            "Consumers install from a clone of this repo, so anything left out here "
            "is silently missing for them."
        ).classes("text-xs").style("color: var(--hw-warning);")
        for entry in plan.barn_dirty:
            rel = entry.path.relative_to(wizard.pipeline.repo_root)
            marker = "new" if entry.untracked else "modified"
            box = ui.checkbox(f"{rel} ({marker})", value=True).props("dense")
            box.classes("text-xs")
            checkboxes.append((box, entry.path))

    if plan.diffstat:
        # hui.expansion_section, not ui.expansion — header styling is only
        # guaranteed correct through the wrapper (design guide §8.11).
        with hui.expansion_section("Diff summary", default_open=False):
            hui.code_snippet(plan.diffstat)

    message_input = hui.input_field(value=plan.message, placeholder="Commit message")
    ui.label(f"Tags this commit {plan.tag}.").classes("text-xs hw-text-dim")

    def _included() -> list[Path]:
        return [path for box, path in checkboxes if box.value]

    with ui.row().classes("w-full justify-end gap-2"):
        ui.button(
            "Commit and tag",
            on_click=lambda: _advance(
                wizard,
                rerender,
                lambda: wizard.advance_from_commit(
                    (message_input.value or plan.message).strip(), _included()
                ),
            ),
        ).props("flat dense").style("color: var(--hw-positive);")


def _panel_push(wizard: ShareWizard, rerender: Callable[[], None]) -> None:
    result = wizard.commit_result
    if result is not None:
        ui.label(f"Committed {result.sha[:8]}, tagged {result.tag}.").classes("text-xs hw-text-dim")
    ui.label("Pushes the commit and tag to origin.").classes("text-xs hw-text-dim")

    log = ui.log(max_lines=200).classes("w-full text-xs").style("height: 140px; font-family: monospace;")
    wizard._log_element = log  # noqa: SLF001

    with ui.row().classes("w-full justify-end gap-2"):
        ui.button(
            "Push",
            on_click=lambda: _advance(wizard, rerender, wizard.advance_from_push),
        ).props("flat dense").style("color: var(--hw-positive);")


def _panel_done(wizard: ShareWizard, on_done: Callable[[], None] | None) -> None:
    from haywire_studio.share import derive_share_url_only

    result = wizard.push_result
    if result is not None:
        ui.label(f"Published {result.tag} to {result.remote}/{result.branch}.").classes("text-sm").style(
            "color: var(--hw-positive);"
        )

    url = derive_share_url_only(wizard.pipeline.repo_root)
    if url.share_url:
        ui.label("Share this URL so others can subscribe to your feed:").classes("text-xs hw-text-dim")
        hui.code_snippet(url.share_url)
    elif url.warning:
        ui.label(url.warning).classes("text-xs hw-text-muted")

    def _close() -> None:
        if wizard.popup is not None:
            wizard.popup.close()
        if on_done is not None:
            on_done()

    with ui.row().classes("w-full justify-end gap-2"):
        ui.button("Done", on_click=_close).props("flat dense").style("color: var(--hw-positive);")
