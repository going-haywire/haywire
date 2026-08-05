"""Per-step body content for the Share Project wizard."""

from __future__ import annotations

from pathlib import Path
from typing import Callable

from nicegui import ui

from haywire.ui import elements as hui
from haywire.ui.modals import restart_affordance

from haywire.ui.components.stepper import ErrorButtonOverride
from haywire.ui.components.stepper import advance as _advance
from haywire.ui.components.stepper import busy_advance as _busy_advance
from ._state import ShareWizard
from .copy import DETECT_SECTIONS, FLOOR_OPTIONS, PIN_OPTIONS
from .remedy_modal import show_remedy_modal, show_rollback_modal


def _restart_after_modal(wizard: ShareWizard, rerender: Callable[[], None]) -> None:
    """Reopen the wizard popup (Solve closed it to show the modal in its
    place) and retry the failed state, then rerender into it."""
    wizard.retry()
    if wizard.popup is not None:
        wizard.popup.open()
    rerender()


def _open_precondition_modal(wizard: ShareWizard, rerender: Callable[[], None]) -> None:
    """Close the wizard popup and open the remedy modal for the current
    precondition failure — the ONLY entry point for this modal, wired to the
    error banner's "Solve" button (`_precondition_error_detail`). Never
    called automatically on failure: a fresh `ui.dialog()` opened outside a
    click handler is how the modal used to stack on top of itself on every
    redraw, since dialogs are independent top-level elements the panel's own
    `body.clear()` does not reach.

    `popup.close()` also fires `Popup`'s `on_close` callback (`show_share_wizard`'s
    `on_done`) — today that's always `None` for this wizard (its one caller,
    `library_browser_editor.py`, never passes it), so this is safe. A future
    caller that DOES pass `on_done` would see it fire here too, mid-flow, not
    just on a genuine finish/dismiss — `Popup` has no "hide without firing
    on_close" primitive to route around that with.
    """
    failure = wizard.precondition_failure
    if failure is None:
        return
    if wizard.popup is not None:
        wizard.popup.close()
    show_remedy_modal(wizard, failure, on_restart=lambda: _restart_after_modal(wizard, rerender))


def _drain_pending_modal(wizard: ShareWizard, rerender: Callable[[], None]) -> None:
    """Auto-open the rollback modal if the last failure queued one.

    Called first thing by every panel. Only the mid-pipeline (rollback) case
    reaches here — a step-1 failure never populates `pending_modal` (see
    `_state.py`), since that modal opens only from the "Solve" button
    (`_precondition_error_detail` / `_open_precondition_modal`), never
    automatically. take_pending_modal() is one-shot, so redraws don't
    restack the rollback dialog — see
    .insights/feedback_nicegui_redraw_deletes_handler_slot.md.
    """
    pending = wizard.take_pending_modal()
    if pending is None:
        return
    if wizard.popup is not None:
        wizard.popup.close()
    show_rollback_modal(pending, on_close=lambda: _restart_after_modal(wizard, rerender))


def _precondition_error_detail(
    wizard: ShareWizard, rerender: Callable[[], None]
) -> bool | ErrorButtonOverride:
    """Relabels the preconditions step's banner button "Solve" instead of
    "Retry" — every precondition failure is resolved through its remedy modal
    (inform: dismiss only; act: dismiss or fix in place), opened ONLY by
    clicking this button, never automatically.

    Returns the button override only; the banner keeps rendering the failure
    message itself. The message must stay on the banner precisely BECAUSE the
    modal is gated behind a click — suppressing it left the user with an error
    icon and a Solve button explaining nothing. See the design note on
    `render_error`'s `ErrorDetail` for the mechanism, and
    `_open_precondition_modal` for why "only on click" matters.
    """
    if wizard.precondition_failure is None:
        return False
    return ("Solve", lambda: _open_precondition_modal(wizard, rerender))


def _panel_preconditions(wizard: ShareWizard, rerender: Callable[[], None]) -> None:
    _drain_pending_modal(wizard, rerender)

    ui.label(
        "Checks that your working tree is clean, that git is available, that barn/ "
        "holds at least one library, and that origin is set, recognized, and reachable."
    ).classes("text-xs hw-text-dim")
    with ui.row().classes("w-full justify-end gap-2"):
        check = ui.button("Check").props("flat dense").style("color: var(--hw-positive);")
        # Nothing changed since the last check until the user acts on the
        # failure through its remedy modal — re-running the same check would
        # just reproduce the same failure. See _precondition_error_detail.
        check.set_enabled(wizard.precondition_failure is None)
        check.on_click(lambda: _busy_advance(rerender, check, wizard.advance_from_preconditions))


def _panel_checked(wizard: ShareWizard, rerender: Callable[[], None]) -> None:
    """The pass report for step 1, and the entry point to the drift scan."""
    _drain_pending_modal(wizard, rerender)
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


def _finding_rows(drift: object, field: str) -> list[tuple[str, str]]:
    """One library's entries for one finding, as ``(subject, context)`` pairs.

    *subject* is the thing that needs attention; *context* names the library it
    belongs to. Kept as a pair rather than a formatted string so the caller can
    align the two columns.
    """
    library = drift.lib_dir.name  # type: ignore[attr-defined]
    if field == "pyproject_version_lag":
        return [
            (dist, f"in {library} — declares {declared}, {installed} installed")
            for dist, declared, installed in getattr(drift, field)
        ]
    return [(item, f"in {library}") for item in getattr(drift, field)]


def _panel_detect(wizard: ShareWizard, rerender: Callable[[], None]) -> None:
    """The read-only report. Writes nothing; every section is informational.

    Grouped by FINDING, not by library. The library-first shape put one heading
    and one explanation above every group, so the same paragraph repeated down
    the page and the reader had to work out which name was the subject and
    which was the container. Finding-first states the problem once, then lists
    every instance under it — and the rows read as sentences ("haybale_studio,
    in haybale-example") rather than as a notation with a direction to learn.

    Severity is carried by colour, not by order: only undeclared imports break
    a consumer's install. The rest are facts, and the screens that follow offer
    them without implying they are defects.
    """
    _drain_pending_modal(wizard, rerender)
    report = wizard.drift_report
    if report is None or not report.libraries:
        ui.label("Nothing to report — every import is declared and nothing is stale.").classes(
            "text-xs hw-text-dim"
        )
    else:
        for field, (title, blurb, token) in DETECT_SECTIONS.items():
            rows = [row for drift in report.libraries for row in _finding_rows(drift, field)]
            if not rows:
                continue
            hui.section_label(title)
            with ui.column().classes("gap-1 ml-1 w-full"):
                ui.label(blurb).classes("text-xs hw-text-dim")
                for subject, context in rows:
                    with ui.row().classes("items-baseline gap-2 ml-2"):
                        ui.label(subject).classes("text-xs font-mono").style(f"color: var({token});")
                        ui.label(context).classes("text-xs hw-text-dim")

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
    _drain_pending_modal(wizard, rerender)
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
        cont = ui.button("Apply").props("flat dense").style("color: var(--hw-positive);")
        cont.on_click(
            lambda: _busy_advance(rerender, cont, lambda: wizard.advance_from_unused(_selection()))
        )


def _panel_undeclared(wizard: ShareWizard, rerender: Callable[[], None]) -> None:
    """Imported distributions the pyproject omits. Per-item pin choice.

    Only ``pyproject_missing`` appears here. The ``@library(dependencies)``
    registrations were applied at the framework step without asking — they are
    provably true and constrain nothing, so listing them among things the
    author must decide about would offer a choice that does not exist.

    The only screen whose "leave it" option is recorded: an undeclared import
    is the one dependency state that breaks a consumer's install, so choosing
    to publish it anyway sets the acknowledgement flag.
    """
    _drain_pending_modal(wizard, rerender)
    report = wizard.drift_report
    if report is None or not report.needs_decision:
        ui.label("Every import the source uses is declared.").classes("text-xs hw-text-dim")
        with ui.row().classes("w-full justify-end gap-2"):
            ui.button(
                "Continue",
                on_click=lambda: _advance(rerender, lambda: wizard.advance_from_undeclared({})),
            ).props("flat dense").style("color: var(--hw-positive);")
        return

    ui.label(
        "The source imports these but pyproject.toml does not declare them. "
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

    def _resolve() -> tuple[dict[Path, list[str]], bool]:
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
        return entries, skipped

    with ui.row().classes("w-full justify-end gap-2"):
        cont = ui.button("Apply").props("flat dense").style("color: var(--hw-positive);")

        async def _go() -> None:
            entries, skipped = _resolve()
            await wizard.advance_from_undeclared(entries, skipped=skipped)

        cont.on_click(lambda: _busy_advance(rerender, cont, _go))


def _panel_floors(wizard: ShareWizard, rerender: Callable[[], None]) -> None:
    """Declared floors below the installed version.

    Every control starts on **keep**, which writes nothing. A floor states the
    OLDEST version that works — not the newest available — and nothing here can
    compute that, so the default must be inert.
    """
    _drain_pending_modal(wizard, rerender)
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
        cont = ui.button("Apply").props("flat dense").style("color: var(--hw-positive);")
        cont.on_click(
            lambda: _busy_advance(rerender, cont, lambda: wizard.advance_from_floors(_selection()))
        )


def _panel_confirm(wizard: ShareWizard, rerender: Callable[[], None]) -> None:
    """What the dependency screens actually wrote, per library.

    Reached only once every custom specifier parses — an invalid one keeps the
    author on its own screen, so this never shows a line that would not survive
    a write.

    Also the second and last place the automatic ``@library(dependencies)``
    edits are named. They were never offered as a choice, so the author's only
    protection against a surprise in ``git diff`` is that the wizard says what
    it did — twice, and unprompted.
    """
    _drain_pending_modal(wizard, rerender)
    written = wizard.dependency_writes()
    registrations = wizard.decorator_registrations

    if not written and not registrations:
        ui.label("No dependency declarations changed.").classes("text-xs hw-text-dim")
    else:
        if registrations:
            ui.label(
                "Added to @library(dependencies) automatically — imported haywire "
                "libraries the decorator did not list:"
            ).classes("text-xs hw-text-dim")
            for lib_dir, names in registrations.items():
                with ui.row().classes("items-baseline gap-2 ml-1"):
                    ui.label(", ".join(names)).classes("text-xs font-mono").style(
                        "color: var(--hw-warning);"
                    )
                    ui.label(f"in {lib_dir.name}").classes("text-xs hw-text-dim")

        if written:
            ui.label("These libraries' dependencies now read:").classes("text-xs hw-text-dim pt-2")
            for lib_dir, entries in written.items():
                hui.section_label(lib_dir.name)
                with ui.column().classes("gap-0.5 ml-1"):
                    for entry in entries:
                        ui.label(entry).classes("text-xs font-mono hw-text-dim")

    with ui.row().classes("w-full justify-end gap-2"):
        ui.button(
            "Confirm",
            on_click=lambda: _advance(rerender, wizard.advance_from_confirm),
        ).props("flat dense").style("color: var(--hw-positive);")


def _panel_framework(wizard: ShareWizard, rerender: Callable[[], None]) -> None:
    """One project-wide framework requirement, with counted consequences.

    A floor restricts CONSUMERS rather than recording what you tested, so the
    recommended option keeps the current declaration — it locks nobody out.

    The FIRST screen in the wizard that writes to disk, which is why its button
    says Apply rather than Continue. No section label: the stepper already
    titles this screen, and repeating it inside the body says nothing new.
    """
    _drain_pending_modal(wizard, rerender)
    plan = wizard.framework_plan
    if plan is None:
        return

    ui.label("Writes the haywire-core floor into every barn library's pyproject.toml.").classes(
        "text-xs hw-text-dim"
    )
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
            "Apply",
            on_click=lambda: _advance(rerender, lambda: wizard.advance_from_framework(_spec())),
        ).props("flat dense").style("color: var(--hw-positive);")


def _panel_version(wizard: ShareWizard, rerender: Callable[[], None]) -> None:
    _drain_pending_modal(wizard, rerender)
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
    _drain_pending_modal(wizard, rerender)
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
    _drain_pending_modal(wizard, rerender)
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

    if plan.diffstat:
        # hui.expansion_section, not ui.expansion — header styling is only
        # guaranteed correct through the wrapper (design guide §8.11).
        with hui.expansion_section("Diff summary", default_open=False):
            hui.code_snippet(plan.diffstat)

    message_input = hui.input_field(value=plan.message, placeholder="Commit message")
    ui.label(f"Tags this commit {plan.tag}.").classes("text-xs hw-text-dim")

    with ui.row().classes("w-full justify-end gap-2"):
        ui.button(
            "Commit and tag",
            on_click=lambda: _advance(
                rerender,
                lambda: wizard.advance_from_commit((message_input.value or plan.message).strip()),
            ),
        ).props("flat dense").style("color: var(--hw-positive);")


def _panel_push(wizard: ShareWizard, rerender: Callable[[], None]) -> None:
    _drain_pending_modal(wizard, rerender)
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
