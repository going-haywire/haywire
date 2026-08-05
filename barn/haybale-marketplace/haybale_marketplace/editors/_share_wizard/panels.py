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
from ._state import ShareWizard
from .copy import DETECT_SECTIONS, FLOOR_OPTIONS, PIN_OPTIONS


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


def _finding_rows(drift: object, field: str) -> list[str]:
    """One finding list rendered as display strings."""
    if field == "pyproject_version_lag":
        return [
            f"{dist}: declared {declared}, installed {installed}"
            for dist, declared, installed in getattr(drift, field)
        ]
    return list(getattr(drift, field))


def _panel_detect(wizard: ShareWizard, rerender: Callable[[], None]) -> None:
    """The read-only report. Writes nothing; every section is informational.

    Severity is carried by colour, not by grouping: only undeclared imports
    break a consumer's install. The rest are facts about the library, and the
    screens that follow offer them without implying they are defects.
    """
    report = wizard.drift_report
    if report is None or not report.libraries:
        ui.label("Nothing to report — every import is declared and nothing is stale.").classes(
            "text-xs hw-text-dim"
        )
    else:
        for drift in report.libraries:
            hui.section_label(drift.lib_dir.name)
            with ui.column().classes("gap-1 ml-1"):
                for field, (title, blurb, token) in DETECT_SECTIONS.items():
                    rows = _finding_rows(drift, field)
                    if not rows:
                        continue
                    ui.label(title).classes("text-xs font-medium").style(f"color: var({token});")
                    ui.label(blurb).classes("text-xs hw-text-dim")
                    for row in rows:
                        ui.label(row).classes("text-xs font-mono ml-2 hw-text-dim")

    with ui.row().classes("w-full justify-end gap-2"):
        ui.button(
            "Continue",
            on_click=lambda: _advance(rerender, wizard.advance_from_detect),
        ).props("flat dense").style("color: var(--hw-positive);")


def _panel_unused(wizard: ShareWizard, rerender: Callable[[], None]) -> None:
    """Declarations the source no longer imports. Nothing is pre-selected.

    The only destructive choice in the flow, and the one place ``detect_deps``'
    blind spot bites: a dynamic import looks exactly like an unused declaration,
    so removing is opt-in per item.
    """
    report = wizard.drift_report
    rows = [(d.lib_dir, dep) for d in (report.libraries if report else []) for dep in d.unused_declarations]

    if not rows:
        ui.label("Every declared dependency is imported somewhere.").classes("text-xs hw-text-dim")
        with ui.row().classes("w-full justify-end gap-2"):
            ui.button(
                "Continue",
                on_click=lambda: _advance(rerender, lambda: wizard.advance_from_unused({})),
            ).props("flat dense").style("color: var(--hw-positive);")
        return

    ui.label(
        "These are declared but never imported. Harmless to consumers — removing "
        "is a tidy-up, and it cannot be undone from here."
    ).classes("text-xs hw-text-dim")

    boxes: list[tuple[Path, str, ui.checkbox]] = []
    current: Path | None = None
    for lib_dir, dep in rows:
        if lib_dir != current:
            hui.section_label(lib_dir.name)
            current = lib_dir
        box = ui.checkbox(dep, value=False).props("dense").classes("text-xs ml-1")
        boxes.append((lib_dir, dep, box))

    def _selection() -> dict[Path, list[str]]:
        out: dict[Path, list[str]] = {}
        for lib_dir, dep, box in boxes:
            if box.value:
                out.setdefault(lib_dir, []).append(dep)
        return out

    with ui.row().classes("w-full justify-end gap-2"):
        cont = ui.button("Continue").props("flat dense").style("color: var(--hw-positive);")
        cont.on_click(
            lambda: _busy_advance(rerender, cont, lambda: wizard.advance_from_unused(_selection()))
        )


def _panel_undeclared(wizard: ShareWizard, rerender: Callable[[], None]) -> None:
    """Imports with no declaration. Per-item pin choice.

    The only screen whose "leave it" option is recorded: an undeclared import
    is the one dependency state that breaks a consumer's install, so choosing
    to publish it anyway sets the acknowledgement flag.
    """
    report = wizard.drift_report
    if report is None or not report.needs_decision:
        ui.label("Every import is declared.").classes("text-xs hw-text-dim")
        with ui.row().classes("w-full justify-end gap-2"):
            ui.button(
                "Continue",
                on_click=lambda: _advance(rerender, lambda: wizard.advance_from_undeclared({}, {})),
            ).props("flat dense").style("color: var(--hw-positive);")
        return

    ui.label(
        "The source imports these but the manifests do not declare them. "
        "Published as-is, consumers install the library and it fails on import."
    ).classes("text-xs hw-text-dim")

    controls: list[tuple[Path, str, str, ui.select, ui.input]] = []
    for drift in report.drifted:
        hui.section_label(drift.lib_dir.name)
        for dep in drift.pyproject_missing:
            installed = wizard.installed_version(dep)
            with ui.column().classes("gap-1 ml-1 w-full"):
                ui.label(dep).classes("text-xs font-mono")
                pin = hui.select_field(
                    options=PIN_OPTIONS,
                    value="none",
                    label="Declare as",
                    in_popup=True,
                ).classes("w-full")
                custom = hui.input_field(placeholder=f">={installed}" if installed else ">=1.0")
                custom.bind_visibility_from(pin, "value", lambda v: v == "custom")
                controls.append((drift.lib_dir, dep, installed, pin, custom))
        for dep in drift.decorator_missing:
            ui.label(f"@library(dependencies): {dep}").classes("text-xs font-mono ml-1 hw-text-dim")

    def _resolve() -> tuple[dict[Path, list[str]], dict[Path, list[str]], bool]:
        entries: dict[Path, list[str]] = {}
        skipped = False
        for lib_dir, dep, installed, pin, custom in controls:
            mode = str(pin.value)
            if mode == "skip":
                skipped = True
                continue
            if mode == "none":
                entries.setdefault(lib_dir, []).append(dep)
            elif mode == "installed":
                entries.setdefault(lib_dir, []).append(f"{dep}>={installed}" if installed else dep)
            else:
                entries.setdefault(lib_dir, []).append(f"{dep}{(custom.value or '').strip()}")
        decorators = {d.lib_dir: list(d.decorator_missing) for d in report.drifted if d.decorator_missing}
        return entries, decorators, skipped

    with ui.row().classes("w-full justify-end gap-2"):
        cont = ui.button("Continue").props("flat dense").style("color: var(--hw-positive);")

        async def _go() -> None:
            entries, decorators, skipped = _resolve()
            await wizard.advance_from_undeclared(entries, decorators, skipped=skipped)

        cont.on_click(lambda: _busy_advance(rerender, cont, _go))


def _panel_floors(wizard: ShareWizard, rerender: Callable[[], None]) -> None:
    """Declared floors below the installed version.

    Every control starts on **keep**, which writes nothing. A floor states the
    OLDEST version that works — not the newest available — and nothing here can
    compute that, so the default must be inert.
    """
    report = wizard.drift_report
    rows = [
        (d.lib_dir, dist, declared, installed)
        for d in (report.libraries if report else [])
        for dist, declared, installed in d.pyproject_version_lag
    ]

    if not rows:
        ui.label("Every declared floor is at or above the installed version.").classes("text-xs hw-text-dim")
        with ui.row().classes("w-full justify-end gap-2"):
            ui.button(
                "Continue",
                on_click=lambda: _advance(rerender, lambda: wizard.advance_from_floors({})),
            ).props("flat dense").style("color: var(--hw-positive);")
        return

    ui.label(
        "These declare a floor below what is installed here. That is not a defect: "
        "raising it locks out consumers who could have installed fine."
    ).classes("text-xs hw-text-dim")

    controls: list[tuple[Path, str, str, str, ui.select, ui.input]] = []
    current: Path | None = None
    for lib_dir, dist, declared, installed in rows:
        if lib_dir != current:
            hui.section_label(lib_dir.name)
            current = lib_dir
        with ui.column().classes("gap-1 ml-1 w-full"):
            ui.label(f"{dist} — declared {declared}, installed {installed}").classes("text-xs font-mono")
            mode = hui.select_field(
                options=FLOOR_OPTIONS, value="keep", label="Floor", in_popup=True
            ).classes("w-full")
            custom = hui.input_field(placeholder=f">={installed}")
            custom.bind_visibility_from(mode, "value", lambda v: v == "custom")
            controls.append((lib_dir, dist, declared, installed, mode, custom))

    def _selection() -> dict[Path, list[str]]:
        out: dict[Path, list[str]] = {}
        for lib_dir, dist, _declared, installed, mode, custom in controls:
            choice = str(mode.value)
            if choice == "keep":
                continue
            spec = f">={installed}" if choice == "sync" else (custom.value or "").strip()
            out.setdefault(lib_dir, []).append(f"{dist}{spec}")
        return out

    with ui.row().classes("w-full justify-end gap-2"):
        cont = ui.button("Continue").props("flat dense").style("color: var(--hw-positive);")
        cont.on_click(
            lambda: _busy_advance(rerender, cont, lambda: wizard.advance_from_floors(_selection()))
        )


def _panel_confirm(wizard: ShareWizard, rerender: Callable[[], None]) -> None:
    """What the dependency screens actually wrote, per library.

    Reached only once every custom specifier parses — an invalid one keeps the
    author on its own screen, so this never shows a line that would not survive
    a write.
    """
    written = wizard.dependency_writes()
    if not written:
        ui.label("No dependency declarations changed.").classes("text-xs hw-text-dim")
    else:
        ui.label("These libraries' dependencies now read:").classes("text-xs hw-text-dim")
        for lib_dir, entries in written.items():
            hui.section_label(lib_dir.name)
            with ui.column().classes("gap-0.5 ml-1"):
                for entry in entries:
                    ui.label(entry).classes("text-xs font-mono hw-text-dim")

    with ui.row().classes("w-full justify-end gap-2"):
        ui.button(
            "Continue",
            on_click=lambda: _advance(rerender, wizard.advance_from_confirm),
        ).props("flat dense").style("color: var(--hw-positive);")


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
