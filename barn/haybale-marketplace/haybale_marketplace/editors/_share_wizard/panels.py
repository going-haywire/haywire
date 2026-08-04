"""Per-step body content for the Share Project wizard."""

from __future__ import annotations

from pathlib import Path
from typing import Callable

from nicegui import ui

from haywire.ui import elements as hui
from haywire.ui.modals import restart_affordance
from haywire_studio.packaging.share.pipeline import PreconditionFailure

from haywire.ui.components.stepper import advance as _advance
from haywire.ui.components.stepper import busy_advance as _busy_advance
from .copy import _DRIFT_EXPLANATIONS, _DRIFT_OPTIONS
from ._state import ShareWizard


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


def _panel_preconditions(wizard: ShareWizard, rerender: Callable[[], None]) -> None:
    ui.label(
        "Checks that git is available, that barn/ holds at least one library, "
        "and that origin is set and reachable."
    ).classes("text-xs hw-text-dim")
    with ui.row().classes("w-full justify-end gap-2"):
        check = ui.button("Check").props("flat dense").style("color: var(--hw-positive);")
        check.on_click(lambda: _busy_advance(rerender, check, wizard.advance_from_preconditions))


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
        scan.on_click(lambda: _busy_advance(rerender, scan, wizard.advance_from_checked))


def _panel_drift(wizard: ShareWizard, rerender: Callable[[], None]) -> None:
    report = wizard.drift_report
    if report is None or not report.needs_decision:
        ui.label("No dependency drift — every import is declared.").classes("text-xs hw-text-dim")
        with ui.row().classes("w-full justify-end gap-2"):
            ui.button(
                "Continue",
                on_click=lambda: _advance(rerender, lambda: wizard.advance_from_drift("skip")),
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
                rerender,
                confirm,
                lambda: wizard.advance_from_drift(str(choice.value)),
            )
        )

    # Applies the initial state (disabled until chosen) through the same path
    # the change handler uses, so a re-render after a failure restores the
    # previous selection rather than resetting it.
    _on_change()


def _panel_framework(wizard: ShareWizard, rerender: Callable[[], None]) -> None:
    """One project-wide framework requirement, with counted consequences.

    A floor restricts CONSUMERS rather than recording what you tested, so the
    recommended option keeps the current declaration — it locks nobody out.
    """
    plan = wizard.framework_plan
    if plan is None:
        return

    hui.section_label("Framework requirement")
    ui.label(f"haywire-core, installed: {plan.installed or 'unknown'}").classes(
        "text-xs hw-text-dim font-mono"
    )

    options = {opt.specifier: f"{opt.specifier} — {opt.label}" for opt in plan.options}
    options["custom"] = "custom…"
    default = next((o.specifier for o in plan.options if o.recommended), next(iter(options)))
    # in_popup for the same reason as the drift and version selects.
    choice = hui.select_field(options=options, value=default, label="Requires", in_popup=True).classes(
        "w-full"
    )
    custom = hui.input_field(placeholder=">=0.0.31")
    custom.bind_visibility_from(choice, "value", lambda v: v == "custom")

    consequences = {opt.specifier: opt.consequence for opt in plan.options}
    note = ui.label("").classes("text-xs hw-text-dim")

    def _describe() -> None:
        note.text = consequences.get(str(choice.value), "")

    _describe()
    choice.on_value_change(lambda _: _describe())

    def _spec() -> str:
        return (custom.value or "").strip() if choice.value == "custom" else str(choice.value)

    with ui.row().classes("w-full justify-end gap-2"):
        ui.button(
            "Continue",
            on_click=lambda: _advance(rerender, lambda: wizard.advance_from_framework(_spec())),
        ).props("flat dense").style("color: var(--hw-positive);")


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
            on_click=lambda: _advance(rerender, lambda: wizard.advance_from_version(_spec())),
        ).props("flat dense").style("color: var(--hw-positive);")


def _panel_docs(wizard: ShareWizard, rerender: Callable[[], None]) -> None:
    ui.label(
        "Regenerates OVERVIEW, QUICKREF, and per-component docs for every barn "
        "library, then rebuilds marketstall.toml. Runs in a separate process."
    ).classes("text-xs hw-text-dim")
    log = ui.log(max_lines=200).classes("w-full text-xs").style("height: 160px; font-family: monospace;")
    for line in wizard.log_lines:
        log.push(line)
    wizard.attach_log(log)

    with ui.row().classes("w-full justify-end gap-2"):
        ui.button(
            "Generate",
            on_click=lambda: _advance(rerender, wizard.advance_from_docs),
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
    wizard.attach_log(log)

    with ui.row().classes("w-full justify-end gap-2"):
        ui.button(
            "Push",
            on_click=lambda: _advance(rerender, wizard.advance_from_push),
        ).props("flat dense").style("color: var(--hw-positive);")


def _panel_done(wizard: ShareWizard, on_done: Callable[[], None] | None) -> None:
    from haywire_studio.packaging.share import derive_share_url_only

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

    # advance_from_version() hot-swaps every bumped library it can reach in the
    # live registry (Option B) — remove_library() + rescan, same eviction
    # ShareWizard._hot_swap_bumped_libraries uses. When that ran and no
    # hot-swapped library declared needs_restart=True, the running registry is
    # already current and no restart is needed. Otherwise (no manager was
    # available — e.g. driven from the CLI — or a library demands it) the
    # affordance is still shown.
    if wizard.hot_swapped_libraries and not wizard.hot_swap_needs_restart:
        ui.label(
            f"Reloaded {len(wizard.hot_swapped_libraries)} bumped "
            f"librar{'y' if len(wizard.hot_swapped_libraries) == 1 else 'ies'} — no restart needed."
        ).classes("text-xs hw-text-dim")
    else:
        restart_affordance(
            reason="Publishing bumped every barn library's version, so the loaded registry is now stale.",
            compact=True,
        )

    with ui.row().classes("w-full justify-end gap-2"):
        ui.button("Done", on_click=_close).props("flat dense").style("color: var(--hw-positive);")
