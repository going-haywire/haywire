"""Per-step body content for the Share flow — three screens.

Each panel returns nothing and renders into the current slot; the flow's
chrome clears and re-renders around them.

The predecessor rendered thirteen screens, one per pipeline concern. That is
the ENGINE's decomposition, not the user's: a clean repo walked six
consecutive screens of good news requiring six clicks, none of which offered a
decision. Here the user's three questions each get one screen — can I publish,
what am I publishing, ship it.
"""

from __future__ import annotations

from pathlib import Path
from typing import Callable

from nicegui import ui

from haywire.core.library.identity import LibraryReloadAction
from haywire.core.publishing.pipeline import ShareDecisions
from haywire.ui import elements as hui
from haywire.ui.components.stepper import busy_advance as _busy_advance
from haywire.ui.modals import restart_affordance

from ._state import ShareFlow
from .copy import DETECT_SECTIONS, FLOOR_OPTIONS, PIN_OPTIONS

_POSITIVE = "color: var(--hw-positive);"


def _footer(label: str) -> ui.button:
    """The one right-aligned action every screen ends with.

    Sixteen hand-rolled copies of this row lived in the predecessor's panels,
    along with nineteen repetitions of the colour literal.
    """
    with ui.row().classes("w-full justify-end gap-2"):
        return ui.button(label).props("flat dense").style(_POSITIVE)


# ── 1. Preflight ─────────────────────────────────────────────────────────────


def panel_preflight(flow: ShareFlow, rerender: Callable[[], None]) -> None:
    """Checking, failed-actionable, or failed-unfixable. Never the pass state.

    A passing preflight advances straight to Review, so the "everything is
    fine" receipt screen the predecessor showed does not exist: it reported an
    outcome the next screen already implies.

    Remedies render INLINE, in the panel body. The predecessor opened them in a
    `ui.dialog()`, which had to close the whole popup first — a dialog is a
    top-level element that a panel's own container clear cannot reach, so
    opening one outside a click handler stacked it on every redraw. Rendering
    here means a rerender simply replaces it.
    """
    failure = flow.precondition_failure

    if failure is None and flow.error is None:
        with ui.row().classes("w-full items-center gap-2"):
            ui.spinner(size="sm")
            ui.label("Checking the project…").classes("text-sm hw-text-dim")
        ui.label(
            "Working tree, git, barn/ contents, and whether origin is set, recognized and reachable."
        ).classes("text-xs hw-text-dim")
        return

    if failure is None:
        ui.label(flow.error or "").classes("text-xs hw-text-danger whitespace-pre-line")
        retry = _footer("Check again")
        retry.on_click(lambda: _busy_advance(rerender, retry, flow.advance))
        return

    ui.label(failure.message).classes("text-sm hw-text-danger whitespace-pre-line")
    if failure.remedy:
        # A plain label, not code_snippet: `remedy` is prose that explains WHY
        # publishing is blocked, with any command indented on its own line.
        # Rendering the whole thing as code made the explanation monospace and
        # offered to copy a paragraph.
        ui.label(failure.remedy).classes("text-xs hw-text-dim whitespace-pre-line")
    if failure.doc_url:
        # A real anchor. The URL arrives on its own field precisely so it can
        # be one — inside `remedy` it would render as dead text in that
        # pre-wrapped label, leaving the user to select and copy it.
        ui.link(failure.doc_label or failure.doc_url, failure.doc_url, new_tab=True).classes(
            "text-xs hw-text-accent"
        )

    note = ui.label("").classes("text-xs")

    if failure.kind == "act":
        _render_fix(flow, failure, note)

    with ui.row().classes("w-full justify-end gap-2"):
        ui.button("Close", on_click=lambda: flow.popup and flow.popup.close()).props("flat dense")
        recheck = ui.button("Check again").props("flat dense").style(_POSITIVE)
        recheck.on_click(lambda: _busy_advance(rerender, recheck, flow.advance))


def _render_fix(flow: ShareFlow, failure, note: ui.label) -> None:
    """The in-place repair an ``act``-kind failure offers.

    Every fix ends by telling the user to click "Check again" rather than
    re-running the check itself: a repair fixes one fault, not the report, and
    the check is cheap enough that re-running it from the top is free.
    """
    fix_id = failure.fix_id
    needs_input = {"add_origin": "git remote URL", "commit_dirty_tree": "Commit message"}

    field: ui.input | None = None
    if fix_id in needs_input:
        field = hui.input_field(placeholder=needs_input[fix_id]).classes("w-full mt-2")

    button = ui.button(failure.fix_label or "Fix").props("flat dense").classes("mt-2").style(_POSITIVE)
    if field is not None:
        button.set_enabled(False)
        field.on_value_change(lambda: button.set_enabled(bool((field.value or "").strip())))

    def _apply() -> None:
        kwargs: dict[str, str] = {}
        if fix_id == "add_origin":
            kwargs["url"] = (field.value or "").strip() if field else ""
        elif fix_id == "commit_dirty_tree":
            kwargs["message"] = (field.value or "").strip() if field else ""
        elif fix_id == "strip_os":
            kwargs["lib_dir"] = failure.lib_dir or ""
        elif fix_id == "add_host_config":
            written = _write_host_config(failure.lib_dir or "")
            note.text = written
            note.classes(replace="text-xs hw-text-dim")
            button.set_enabled(False)
            return

        error = flow.apply_precondition_fix(fix_id or "", **kwargs)
        if error:
            note.text = error
            note.classes(replace="text-xs hw-text-danger")
            return
        note.text = "Done — click Check again."
        note.classes(replace="text-xs hw-text-dim")
        button.set_enabled(False)
        if field is not None:
            field.set_enabled(False)

    button.on_click(_apply)


def _write_host_config(hostname: str, provider: str = "gitlab") -> str:
    """Append a ``[[hosts]]`` entry to the user's config.

    Not a pipeline fix (``fixes.py``): this writes ``~/.haywire/config.toml``,
    a file outside the repo the pipeline owns. Routed through
    ``_user_config_path()`` — the location's single source of truth, already
    wrapped for test monkeypatching.
    """
    from haywire.core.marketstall.host_providers.config import _user_config_path

    if not hostname:
        return "No hostname on this failure — cannot write the entry."
    path = _user_config_path()
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as handle:
            handle.write(f'\n[[hosts]]\nhostname = "{hostname}"\nprovider = "{provider}"\n')
    except OSError as exc:
        return f"Could not write the config: {exc}"
    return f"Written to {path} — click Check again."


# ── 2. Review ────────────────────────────────────────────────────────────────


def panel_review(flow: ShareFlow, rerender: Callable[[], None]) -> None:
    """Every dependency decision and the version, on one screen.

    Nothing here writes. The controls collect into a :class:`ShareDecisions`
    that is applied once, on Apply — so a flow abandoned on this screen leaves
    the tree exactly as it found it.

    Empty finding categories collapse to a single ✓ line instead of claiming a
    screen each.
    """
    report = flow.drift_report
    libraries = report.libraries if report else []

    registrations = report.decorator_registrations if report else {}
    controls = _render_findings(flow, libraries)
    _render_clean_lines(libraries, registrations)

    framework_spec = _render_framework(flow)
    version_spec = _render_version(flow)

    apply_button = _footer("Apply and bump")

    async def _go() -> None:
        await flow.advance_from_review(_collect(controls, framework_spec()), version_spec=version_spec())

    apply_button.on_click(lambda: _busy_advance(rerender, apply_button, _go))


def _render_findings(flow: ShareFlow, libraries) -> dict:
    """One section per non-empty finding kind, grouped by FINDING not library.

    Library-first put one heading and one explanation above every group, so the
    same paragraph repeated down the page and the reader had to work out which
    name was the subject and which the container.
    """
    controls: dict = {"additions": [], "removals": [], "floors": []}

    for field, (title, blurb, token) in DETECT_SECTIONS.items():
        rows = [(d.lib_dir, item) for d in libraries for item in getattr(d, field)]
        if not rows:
            continue
        with _section(title, blurb):
            for lib_dir, item in rows:
                if field == "pyproject_missing":
                    _render_addition_row(flow, lib_dir, item, controls, token)
                elif field == "unused_declarations":
                    _render_removal_row(lib_dir, item, controls, token)
                elif field == "pyproject_version_lag":
                    _render_floor_row(lib_dir, item, controls, token)
                else:
                    with ui.row().classes("items-baseline gap-2"):
                        ui.label(str(item)).classes("text-xs font-mono").style(f"color: var({token});")
                        ui.label(f"in {lib_dir.name}").classes("text-xs hw-text-dim")
    return controls


def _section(title: str, blurb: str = "") -> ui.column:
    """One finding kind, boxed. Returns the column its rows go into.

    A border rather than a raised background: the popup card is already
    `--hw-bg-elevated` (Layer 2), and the design guide's elevation rule says a
    container sits exactly one step above its parent — there is no Layer 3 for
    panel chrome, and `box-shadow` is reserved for canvas nodes (§2.1).

    Boxing matters because the screen stacks four of these. Without a boundary
    the eye has to infer where one finding ends and the next begins, and the
    section heading — which is what says whether you are looking at imports to
    declare or floors to raise — reads as belonging to whatever preceded it.

    The heading lives inside the box (not above it) so that boundary actually
    contains the thing it names.
    """
    box = (
        ui.column()
        .classes("w-full gap-2 p-2 rounded")
        .style("border: 1px solid var(--hw-border); background: var(--hw-bg-surface);")
    )
    with box:
        hui.section_label(title)
        if blurb:
            ui.label(blurb).classes("text-xs hw-text-dim")
    return box


def _decision(subject: str, context: str, token: str) -> ui.column:
    """One decision, boxed with its subject. Returns the column its control goes into.

    The proximity fix. These used to be `gap-1` columns in a `gap-2` parent,
    so the distance from a subject line UP to the previous control was smaller
    than the distance DOWN to its own — the eye grouped each label with the
    wrong widget, and reading the screen meant re-deriving which name each
    dropdown belonged to. Now the subject and its control share a bordered
    box, and only boxes are separated.
    """
    box = (
        ui.column()
        .classes("w-full gap-1 p-2 rounded")
        .style("border: 1px solid var(--hw-border); background: var(--hw-bg-elevated);")
    )
    with box:
        with ui.row().classes("items-baseline gap-2"):
            ui.label(subject).classes("text-xs font-mono").style(f"color: var({token});")
            ui.label(context).classes("text-xs hw-text-dim")
    return box


def _render_addition_row(flow: ShareFlow, lib_dir: Path, dep: str, controls: dict, token: str) -> None:
    installed = flow.installed_version(dep)
    with _decision(dep, f"in {lib_dir.name}", token):
        pin = hui.select_field(options=PIN_OPTIONS, value="none", label="Declare as", in_popup=True).classes(
            "w-full"
        )
        custom = hui.input_field(placeholder=f">={installed}" if installed else ">=1.0")
        custom.bind_visibility_from(pin, "value", lambda v: v == "custom")
    controls["additions"].append((lib_dir, dep, installed, pin, custom))


def _render_removal_row(lib_dir: Path, dep: str, controls: dict, token: str) -> None:
    """Nothing pre-selected: a dynamic import is indistinguishable from an
    unused declaration, and removing cannot be undone from here.

    Not boxed like the others: the checkbox carries its own label, so subject
    and control are already one element — a box would separate it from
    siblings it reads fine beside.

    `items-center`, not `items-baseline`: a checkbox has no text baseline, so
    Quasar's 24px control box got aligned against the label's baseline and
    both the tick and the trailing "in <library>" sat visibly low.
    """
    with ui.row().classes("items-center gap-2"):
        box = ui.checkbox(dep, value=False).props("dense").classes("text-xs")
        ui.label(f"in {lib_dir.name}").classes("text-xs hw-text-dim")
    controls["removals"].append((lib_dir, dep, box))


def _render_floor_row(lib_dir: Path, row: tuple[str, str, str], controls: dict, token: str) -> None:
    """Every control starts on keep, which writes nothing — a floor states the
    OLDEST version that works and nothing here can compute that."""
    dist, declared, installed = row
    with _decision(f"{dist} — declared {declared}, installed {installed}", f"in {lib_dir.name}", token):
        mode = hui.select_field(options=FLOOR_OPTIONS, value="keep", label="Floor", in_popup=True).classes(
            "w-full"
        )
        custom = hui.input_field(placeholder=f">={installed}")
        custom.bind_visibility_from(mode, "value", lambda v: v == "custom")
    controls["floors"].append((lib_dir, dist, installed, mode, custom))


def _render_clean_lines(libraries, registrations: dict) -> None:
    """One ✓ line per finding kind that found nothing, plus the auto-applied
    library-dependency registrations, if any.

    The predecessor gave each of the finding kinds a full screen with its own
    Continue button — six screens of good news for a clean repo.
    """
    for field, (title, _blurb, _token) in DETECT_SECTIONS.items():
        if any(getattr(d, field) for d in libraries):
            continue
        with ui.row().classes("items-center gap-2"):
            ui.icon("check_circle", size="14px").style(_POSITIVE)
            ui.label(f"{title}: none").classes("text-xs hw-text-dim")

    if registrations:
        # Never a choice — every entry is provably true and constrains nothing
        # — but it edits a hand-authored file, so it is always named.
        with _section(
            "Library dependencies",
            "Adding a detected haywire library dependency to the library's haybale.toml file.",
        ):
            for lib_dir, names in registrations.items():
                for name in names:
                    with ui.row().classes("items-baseline gap-2"):
                        with ui.row().classes("items-baseline gap-0"):
                            ui.label("linked_libraries = [..., ").classes("text-xs font-mono hw-text-dim")
                            ui.label(name).classes("text-xs font-mono hw-text-warning")
                            ui.label("]").classes("text-xs font-mono hw-text-dim")
                        ui.label(f"in {lib_dir.name}").classes("text-xs hw-text-dim")


def _render_framework(flow: ShareFlow) -> Callable[[], str | None]:
    """The one authored floor. Recommended option keeps what is declared —
    raising it locks out consumers who could have installed fine."""
    plan = flow.framework_plan
    if plan is None or not plan.options:
        return lambda: None

    options = {opt.specifier: f"{opt.specifier} — {opt.label}" for opt in plan.options}
    options["custom"] = "custom…"
    default = next((o.specifier for o in plan.options if o.recommended), next(iter(options)))

    with _section(
        "Framework requirement",
        f"haywire-core, installed: {plan.installed or 'unknown'}. Written into every "
        "barn library's pyproject.toml.",
    ):
        choice = hui.select_field(options=options, value=default, label="Requires", in_popup=True).classes(
            "w-full"
        )
        custom = hui.input_field(placeholder=">=0.0.31")
        custom.bind_visibility_from(choice, "value", lambda v: v == "custom")

        consequences = {opt.specifier: opt.consequence for opt in plan.options}
        note = ui.label(consequences.get(default, "")).classes("text-xs hw-text-dim")
        choice.on_value_change(lambda: setattr(note, "text", consequences.get(str(choice.value), "")))

    def _spec() -> str | None:
        if choice.value == "custom":
            return (custom.value or "").strip() or None
        return str(choice.value)

    return _spec


def _render_version(flow: ShareFlow) -> Callable[[], str]:
    """Lockstep: every barn library publishes at the same version."""
    plan = flow.version_plan
    if plan is None:
        return lambda: "patch"

    with _section(
        "Version",
        "Every barn library publishes at the same version (lockstep), and the repo is tagged with it.",
    ):
        with ui.column().classes("gap-0.5"):
            for lib in plan.current:
                ui.label(f"{lib.name}: {lib.version or '(none)'}").classes("text-xs font-mono")

        if not plan.versions_agree:
            ui.label(
                "These versions disagree. Name the version every library should be set to — "
                "picking one automatically would downgrade the others."
            ).classes("text-xs").style("color: var(--hw-warning);")
            explicit = hui.input_field(placeholder="X.Y.Z").classes("w-full")
            return lambda: (explicit.value or "").strip()

        options = {kw: f"{kw} → {resolved}" for kw, resolved in plan.suggestions.items()}
        options["custom"] = "custom…"
        choice = hui.select_field(options=options, value="patch", label="Bump", in_popup=True).classes(
            "w-full"
        )
        custom = hui.input_field(placeholder="X.Y.Z")
        custom.bind_visibility_from(choice, "value", lambda v: v == "custom")

    def _spec() -> str:
        return (custom.value or "").strip() if choice.value == "custom" else str(choice.value)

    return _spec


def _collect(controls: dict, framework: str | None) -> ShareDecisions:
    """Read every control into the decision set. Touches no file."""
    additions: dict[Path, list[str]] = {}
    skipped = False
    for lib_dir, dep, installed, pin, custom in controls["additions"]:
        mode = str(pin.value)
        if mode == "skip":
            skipped = True
            continue
        if mode == "installed":
            entry = f"{dep}>={installed}" if installed else dep
        elif mode == "custom":
            entry = f"{dep}{(custom.value or '').strip()}"
        else:
            entry = dep
        additions.setdefault(lib_dir, []).append(entry)

    removals: dict[Path, list[str]] = {}
    for lib_dir, dep, box in controls["removals"]:
        if box.value:
            removals.setdefault(lib_dir, []).append(dep)

    floors: dict[Path, list[str]] = {}
    for lib_dir, dist, installed, mode, custom in controls["floors"]:
        choice = str(mode.value)
        if choice == "keep":
            continue
        spec = f">={installed}" if choice == "sync" else (custom.value or "").strip()
        floors.setdefault(lib_dir, []).append(f"{dist}{spec}")

    return ShareDecisions(
        framework=framework,
        removals=removals,
        additions=additions,
        floors=floors,
        undeclared_acknowledged=skipped,
    )


# ── 3. Publish ───────────────────────────────────────────────────────────────


def panel_publish(flow: ShareFlow, rerender: Callable[[], None]) -> None:
    """Docs, marketstall, commit, tag, push — one authorized run.

    There is no decision between these steps, so asking for a click at each
    would request three authorizations for one intent. The commit message is a
    real input and stays.
    """
    if flow.committed_unpushed:
        _render_committed_unpushed(flow)
        return

    version = flow.pipeline.version
    ui.label(
        "Regenerates every library's docs, rebuilds marketstall.toml, then commits, "
        "tags and pushes to origin."
    ).classes("text-xs hw-text-dim")
    if version:
        ui.label(f"Publishing v{version}.").classes("text-xs font-mono hw-text-dim")

    message = hui.input_field(
        value=f"chore: share v{version}" if version else "", placeholder="Commit message"
    ).classes("w-full")

    log = ui.log(max_lines=200).classes("w-full text-xs").style("height: 150px; font-family: monospace;")
    for line in flow.log_lines:
        log.push(line)
    flow.attach_log(log)

    publish = _footer("Publish")
    publish.on_click(
        lambda: _busy_advance(
            rerender, publish, lambda: flow.advance_from_publish((message.value or "").strip() or None)
        )
    )


def _render_committed_unpushed(flow: ShareFlow) -> None:
    """The honest post-commit failure state.

    A commit and a tag exist locally and were NOT reverted — the working-tree
    revert cannot reach committed history. The predecessor ran that revert
    anyway and reported "nothing was left behind", which was false in exactly
    the case where the user most needed the truth.
    """
    result = flow.commit_result
    ui.label("The commit and tag were created, but the push failed.").classes("text-sm hw-text-danger")
    if result is not None:
        ui.label(f"Committed {result.sha[:8]}, tagged {result.tag} — both are still here.").classes(
            "text-xs hw-text-dim"
        )

    # `stderr`, not `str(exc)`: PushError's message already embeds the retry
    # command and the "Run this yourself" line, both of which this panel lays
    # out below. Rendering the whole message showed each of them twice.
    stderr = getattr(flow.last_error, "stderr", "") or ""
    if stderr:
        ui.label(stderr.strip()).classes("text-xs hw-text-danger whitespace-pre-line")

    command = flow.retry_command
    if command:
        ui.label("Finish the publish by running this yourself:").classes("text-xs hw-text-dim")
        hui.code_snippet(command)

    with ui.row().classes("w-full justify-end gap-2"):
        ui.button("Close", on_click=lambda: flow.popup and flow.popup.close()).props("flat dense")


# ── 4. Done ──────────────────────────────────────────────────────────────────


def panel_done(flow: ShareFlow, _rerender: Callable[[], None]) -> None:
    result = flow.push_result
    if result is not None:
        ui.label(f"Published {result.tag} to {result.remote}/{result.branch}.").classes("text-sm").style(
            _POSITIVE
        )

    pypi_url, url, tagged_url, warning = flow.share_url()
    if pypi_url:
        ui.label("Released packages (recommended):").classes("text-xs hw-text-dim")
        hui.code_snippet(pypi_url)
    if url:
        ui.label("Share this URL so others can subscribe to your feed:").classes("text-xs hw-text-dim")
        hui.code_snippet(url)
        if tagged_url:
            ui.label("Frozen to this version:").classes("text-xs hw-text-dim")
            hui.code_snippet(tagged_url)
    elif warning:
        ui.label(warning).classes("text-xs hw-text-muted")

    if flow.hot_swapped_libraries and flow.hot_swap_on_reload is not LibraryReloadAction.RESTART:
        count = len(flow.hot_swapped_libraries)
        ui.label(
            f"Reloaded {count} bumped librar{'y' if count == 1 else 'ies'} — no restart needed."
        ).classes("text-xs hw-text-dim")
        if flow.hot_swap_on_reload is LibraryReloadAction.REFRESH:
            ui.label("Reload the page to pick up their new front-end resources.").classes(
                "text-xs hw-text-muted"
            )
    elif flow.hot_swapped_libraries:
        # Reloaded fine; a library declares @library(on_reload="restart") — it
        # leaves the process in a state hot-reload cannot repair (C-extension
        # modules, import-time global mutation). The registry is NOT stale: the
        # restart is the library's own requirement, not a consequence of the bump.
        count = len(flow.hot_swapped_libraries)
        restart_affordance(
            reason=(
                f"Reloaded {count} bumped librar{'y' if count == 1 else 'ies'}, but one of them "
                "declares that it needs a Studio restart to load cleanly."
            ),
            compact=True,
        )
    else:
        # Nothing was swapped — no library was live in this process to reload
        # (none enabled, or no live library system at all), so whatever is
        # loaded still predates the bump.
        restart_affordance(
            reason="Publishing bumped every barn library's version, so the loaded registry is now stale.",
            compact=True,
        )

    done = _footer("Done")
    done.on_click(lambda: flow.popup and flow.popup.close())


def suppress_duplicate_error(flow: ShareFlow, _rerender: Callable[[], None]) -> "bool | str":
    """Stop the shared error banner from restating what a panel already shows.

    `flow.error` is `str(exception)`. For a `PreconditionsError` that string is
    CLI-shaped — "Cannot share this project:", the message bulleted under it,
    the remedy indented under that — because it is what a terminal prints. The
    Preflight panel renders `failure.message` and `failure.remedy` as real UI
    from the same structured fields, so letting the banner render too showed
    every line twice, once pre-formatted for a terminal.

    Same for the post-commit push failure: `PushError.__str__` already contains
    the stderr AND the retry command, both of which the Publish panel lays out
    itself.

    Returns "skip" rather than True: True would keep the banner shell and its
    Retry button, leaving an empty red box above the panel. Retry is also wrong
    for both states — on a post-commit failure it would re-enter a step that
    already committed. Each of these panels renders its own actions.
    """
    if flow.precondition_failure is not None or flow.committed_unpushed:
        return "skip"
    return False
