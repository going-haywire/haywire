"""Remedy modals for Share Wizard preflight failures.

Every ``check_preconditions()`` failure (Task 1-4) is one of two shapes:

- ``kind == "inform"``: nothing the wizard can do about it — message, remedy
  text, and a Restart Wizard button. No fix affordance.
- ``kind == "act"``: the wizard CAN repair this in place — same content plus
  a button that performs the fix. Success does NOT auto-continue: per the
  settled design, EVERY act-modal ends with an explicit "Restart Wizard"
  click, even on a successful fix — no auto-continue. Preflight is cheap
  enough that re-running it from #0 is free, and an explicit click keeps the
  user in control of when the wizard re-engages rather than silently
  reacting to a background git operation.

A third shape (rollback, for mid-pipeline failures at steps 2-6) is handled
by :func:`show_rollback_modal` in the same module — distinct from these two
because it also has to trigger a working-tree revert as a side effect of
opening, not just report.
"""

from __future__ import annotations

import json as _json
from pathlib import Path
from typing import Callable

from nicegui import ui

from haywire.ui import elements as hui
from haywire_studio.packaging.share.pipeline import PreconditionFailure, ShareError

from ._state import ShareWizard


def _copy_button(value: str) -> ui.button:
    """Copy-to-clipboard button, matching hui's internal ``_copy_button`` pattern
    (elements.py) — duplicated locally rather than imported since that name is
    module-private to ``elements.py`` by convention."""
    return (
        ui.button(
            icon="content_copy",
            on_click=lambda: ui.run_javascript(f"navigator.clipboard.writeText({_json.dumps(value)})"),
        )
        .props("flat round dense size=xs")
        .tooltip("Copy to clipboard")
    )


def show_remedy_modal(
    wizard: ShareWizard,
    failure: PreconditionFailure,
    *,
    on_restart: Callable[[], None],
) -> None:
    """Open the inform or act remedy modal for one preflight failure."""
    with ui.dialog() as dialog, hui.dialog_card("w-[480px]"):
        ui.label(failure.message).classes("text-sm hw-text-danger whitespace-pre-line")
        if failure.remedy:
            ui.label(failure.remedy).classes("text-xs hw-text-dim font-mono whitespace-pre-line")

        error_label = ui.label("").classes("text-xs hw-text-danger")

        if failure.kind == "act":
            _render_act_body(wizard, failure, error_label)

        def _restart() -> None:
            dialog.close()
            on_restart()

        with ui.row().classes("w-full justify-end gap-2 mt-2"):
            ui.button("Restart Wizard", on_click=_restart).props("flat dense").style(
                "color: var(--hw-positive);"
            )
    dialog.open()


def _render_act_body(wizard: ShareWizard, failure: PreconditionFailure, error_label: ui.label) -> None:
    """The extra widgets an act-kind failure needs, above the Restart Wizard row."""
    fix_id = failure.fix_id
    if fix_id == "add_origin":
        url_input = hui.input_field(placeholder="git remote URL").classes("w-full mt-2")
        fix_button = ui.button("Add origin remote").props("flat dense").style("color: var(--hw-positive);")
        fix_button.set_enabled(False)
        url_input.on_value_change(lambda: fix_button.set_enabled(bool((url_input.value or "").strip())))

        def _apply_add_origin() -> None:
            try:
                wizard.pipeline.apply_precondition_fix("add_origin", url=(url_input.value or "").strip())
            except ShareError as exc:
                error_label.text = str(exc)
                return
            error_label.text = "Done — click Restart Wizard to re-check."
            fix_button.set_enabled(False)

        fix_button.on_click(_apply_add_origin)

    elif fix_id == "strip_os":
        fix_button = (
            ui.button(failure.fix_label or "Fix")
            .props("flat dense")
            .classes("mt-2")
            .style("color: var(--hw-positive);")
        )

        def _apply_strip_os() -> None:
            try:
                wizard.pipeline.apply_precondition_fix("strip_os", lib_dir=failure.lib_dir or "")
            except ShareError as exc:
                error_label.text = str(exc)
                return
            error_label.text = "Done — click Restart Wizard to re-check."
            fix_button.set_enabled(False)

        fix_button.on_click(_apply_strip_os)

    elif fix_id == "commit_dirty_tree":
        message_input = hui.input_field(placeholder="Commit message").classes("w-full mt-2")
        fix_button = ui.button("Commit changes").props("flat dense").style("color: var(--hw-positive);")
        fix_button.set_enabled(False)
        message_input.on_value_change(
            lambda: fix_button.set_enabled(bool((message_input.value or "").strip()))
        )

        def _apply_commit_dirty_tree() -> None:
            try:
                wizard.pipeline.apply_precondition_fix(
                    "commit_dirty_tree", message=(message_input.value or "").strip()
                )
            except ShareError as exc:
                error_label.text = str(exc)
                return
            error_label.text = "Committed — click Restart Wizard to re-check."
            fix_button.set_enabled(False)
            message_input.set_enabled(False)

        fix_button.on_click(_apply_commit_dirty_tree)

    elif fix_id == "add_host_config":
        # Not dispatched through _PRECONDITION_FIXES (fixes.py): this writes
        # ~/.haywire/config.toml, a file outside the repo the pipeline owns —
        # a different concern than the repo-mutation handlers in fixes.py.
        ui.label("Add this entry?").classes("text-xs hw-text-dim mt-2")
        with ui.row().classes("items-center gap-1"):
            ui.label(failure.remedy).classes("text-xs font-mono whitespace-pre-line flex-1")
            _copy_button(failure.remedy)
        fix_button = (
            ui.button("Write to ~/.haywire/config.toml")
            .props("flat dense")
            .classes("mt-2")
            .style("color: var(--hw-positive);")
        )

        def _apply_add_host_config() -> None:
            # hostname arrives as data on the failure (lib_dir), not parsed
            # back out of the remedy prose.
            hostname = failure.lib_dir or ""
            if not hostname:
                error_label.text = "No hostname on this failure — cannot write the entry."
                return
            try:
                written = append_host_config(hostname)
            except OSError as exc:
                error_label.text = f"Could not write the config: {exc}"
                return
            error_label.text = f"Written to {written} — click Restart Wizard to re-check."
            fix_button.set_enabled(False)

        fix_button.on_click(_apply_add_host_config)


def append_host_config(hostname: str, provider: str = "gitlab") -> Path:
    """Append a ``[[hosts]]`` entry for *hostname* to the user's config.

    Separate from the click handler so it is testable without a browser, and
    routed through ``_user_config_path()`` — the location's single source of
    truth, already documented there as "wrapped for test monkeypatching"
    (host_providers/config.py). Do not rebuild ``Path.home() / ...`` here.
    """
    from haywire.core.marketstall.host_providers.config import _user_config_path

    path = _user_config_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(f'\n[[hosts]]\nhostname = "{hostname}"\nprovider = "{provider}"\n')
    return path


def show_rollback_modal(message: str, *, on_close: Callable[[], None]) -> None:
    """Class C: a mid-pipeline failure (steps 2-6). Distinct from
    show_remedy_modal — this always reports that a revert has ALREADY run
    (see ShareWizard.fail()), so there is nothing to act on and no fix
    affordance is offered, only acknowledgement."""
    with ui.dialog() as dialog, hui.dialog_card("w-[480px]"):
        ui.icon("error", size="20px").classes("hw-text-danger")
        ui.label("Something went wrong, and it could not be fixed automatically.").classes(
            "text-sm hw-text-danger"
        )
        ui.label(message).classes("text-xs hw-text-dim whitespace-pre-line")
        ui.label("Every change this run made has been reverted — nothing was left behind.").classes(
            "text-xs hw-text-dim"
        )

        def _close() -> None:
            dialog.close()
            on_close()

        with ui.row().classes("w-full justify-end gap-2 mt-2"):
            ui.button("Close", on_click=_close).props("flat dense").style("color: var(--hw-positive);")
    dialog.open()
