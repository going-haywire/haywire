"""Add Source dialog for the Library Manager.

Single input field accepting four forms per spec §4.2:
  - Blob URL  (github.com/.../blob/{ref}/marketstall.toml)
  - Raw URL   (raw.githubusercontent.com/.../...)
  - Plain TOML URL  (anything else)
  - Pasted TOML block (not a URL)

The body-shape decides whether the subscription writes to [[markets]] or [[stalls]].
"""

from __future__ import annotations

import logging
from typing import Callable

from nicegui import ui

from haywire.ui import elements as hui

logger = logging.getLogger(__name__)


def show_add_source_dialog(on_added: Callable[[], None]) -> None:
    """Open the single-field Add Source dialog.

    `on_added` is called after a successful add (and after any conflict-
    resolution prompt resolves). The caller typically refreshes the
    marketplace and re-renders the library list.
    """
    with ui.dialog() as dialog, hui.dialog_card():
        with ui.column().classes("p-4 gap-3 w-[28rem]"):
            ui.label("Add a marketplace source").classes("text-sm font-medium")
            ui.label("Paste a marketstall URL, a marketplace URL, or a [[haybales]] TOML block.").classes(
                "text-xs hw-text-dim"
            )

            # ui.textarea (not hui.input_field) so multi-line TOML paste preserves newlines.
            # A single-line input would collapse line breaks into spaces when pasting a
            # [[haybales]] block, producing invalid TOML.
            input_field = (
                ui.textarea(placeholder="https://github.com/.../blob/main/marketstall.toml")
                .props("dense autogrow")
                .classes("w-full text-xs")
            )

            with ui.column().classes("gap-0 text-xs hw-text-dim"):
                ui.label("Accepted forms:")
                ui.label("• Blob URL (github.com/.../blob/{ref}/marketstall.toml)")
                ui.label("• Raw URL (raw.githubusercontent.com/...)")
                ui.label("• Any URL that serves a TOML file (GitHub Pages, GitLab Pages, etc.)")
                ui.label("• A [[haybales]] TOML block pasted directly")

            with ui.row().classes("w-full justify-end gap-2"):
                ui.button("Cancel", on_click=dialog.close).props("flat")
                ui.button(
                    "Add source",
                    on_click=lambda: _handle_add_source(input_field.value, dialog, on_added),
                ).props("flat color=primary")

    dialog.open()


def _handle_add_source(user_input: str, dialog: "ui.dialog", on_added: Callable[[], None]) -> None:
    """Validate input, run the §4.3 algorithm, route the conflict prompt on success."""
    from haywire.core.marketstall import (
        BareRepoUrlRejectedError,
        SubscribeError,
        resolve_and_subscribe,
    )

    from haywire_studio.config import GLOBAL_MARKETPLACE_DIR, ensure_global_config

    if not (user_input or "").strip():
        ui.notify("Please paste a URL or TOML block.", type="warning")
        return

    try:
        ensure_global_config()
        result = resolve_and_subscribe(
            GLOBAL_MARKETPLACE_DIR / "marketplace.toml",
            user_input,
            paste_dir=GLOBAL_MARKETPLACE_DIR / "stalls",
        )
    except BareRepoUrlRejectedError as exc:
        ui.notify(str(exc), type="warning")
        return
    except SubscribeError as exc:
        logger.warning(f"Add Source failed: {exc}")
        ui.notify(f"Failed to add source: {exc}", type="negative")
        return
    except Exception as exc:
        logger.exception("Unexpected error in Add Source")
        ui.notify(f"Unexpected error: {exc}", type="negative")
        return

    ui.notify(f"Subscribed to {result.persist_url}", type="positive")
    dialog.close()
    _check_and_prompt_conflicts(
        new_source_url=result.persist_url,
        new_source_is_marketstall=(result.kind == "stall"),
        on_done=on_added,
    )


def _check_and_prompt_conflicts(
    new_source_url: str,
    new_source_is_marketstall: bool,
    on_done: Callable[[], None],
) -> None:
    """After a subscription is added, fetch + check for name conflicts, then prompt the user."""
    from pathlib import Path

    from haywire.core.marketstall import (
        RemoteFetchError,
        detect_subscription_conflicts,
        fetch_with_cache_fallback,
        parse_marketstall_body,
        parse_project_marketplace,
        parse_remote_marketplace_body,
    )
    from nicegui import app as ng_app

    try:
        result = fetch_with_cache_fallback(new_source_url)
    except RemoteFetchError:
        # Can't fetch → can't detect conflicts. Skip the prompt; refresh
        # will surface the source as unavailable in the banner.
        on_done()
        return

    if new_source_is_marketstall:
        new_pkgs = parse_marketstall_body(result.body)
    else:
        contents = parse_remote_marketplace_body(result.body)
        new_pkgs = list(contents.haybales)
        # NOTE: doesn't recurse into marketstalls discovered via the marketplace —
        # matches refresh's one-level-deep limit. Sub-marketstall conflicts are
        # detected by refresh's normal pipeline.

    workspace_root = getattr(ng_app, "workspace_root", None)
    if workspace_root is None:
        on_done()
        return
    project_mp = parse_project_marketplace(Path(workspace_root) / ".haywire" / "marketplace.toml")
    # Tag new packages with the new source_url so detect_subscription_conflicts'
    # source_origin fallback shows something useful for the prompt UI.
    for pkg in new_pkgs:
        if not pkg.source_origin:
            pkg.source_origin = new_source_url

    conflicts = detect_subscription_conflicts(project_mp.caches, new_pkgs)

    if not conflicts:
        on_done()
        return

    _show_conflict_resolution_dialog(
        conflicts=conflicts,
        new_source_url=new_source_url,
        on_resolved=on_done,
    )


def _show_conflict_resolution_dialog(
    conflicts: list,
    new_source_url: str,
    on_resolved: Callable[[], None],
) -> None:
    """Modal with one row per conflict: 'Keep existing' or 'Use new' radio."""
    from haywire.core.marketstall import record_ignore_on_source

    from haywire_studio.config import GLOBAL_MARKETPLACE_DIR

    # Map from package_name → "existing" | "new".
    choices: dict[str, str] = {}

    with ui.dialog() as dialog, hui.dialog_card():
        with ui.column().classes("p-4 gap-3 w-[28rem]"):
            ui.label("Marketplace conflicts").classes("text-sm font-medium")
            ui.label(
                f"The new source ({new_source_url}) provides packages also "
                "provided by existing sources. Pick which to keep for each."
            ).classes("text-xs hw-text-dim")

            for conflict in conflicts:
                with ui.column().classes("border rounded p-2 gap-1 w-full"):
                    ui.label(conflict.name).classes("text-xs font-medium")
                    radio = ui.radio(["Keep existing", "Use new"], value="Keep existing").props(
                        "inline dense"
                    )

                    def _on_choice(e, name=conflict.name, radio_el=radio):
                        choices[name] = "existing" if "existing" in radio_el.value.lower() else "new"

                    radio.on("update:model-value", _on_choice)
                    choices[conflict.name] = "existing"  # default

                    with ui.column().classes("gap-0 ml-2"):
                        ui.label(f"existing: {conflict.existing_source}").classes(
                            "text-xs hw-text-dim font-mono"
                        )
                        ui.label(f"new: {conflict.new_source}").classes("text-xs hw-text-dim font-mono")

            with ui.row().classes("w-full justify-end gap-2"):
                ui.button("Cancel", on_click=dialog.close).props("flat")

                def _apply():
                    global_mp = GLOBAL_MARKETPLACE_DIR / "marketplace.toml"
                    for c in conflicts:
                        if choices.get(c.name) == "existing":
                            # Losing side: the NEW subscription. Add to ITS ignores.
                            try:
                                record_ignore_on_source(
                                    global_mp,
                                    source_url=c.new_source,
                                    haybale_name=c.name,
                                )
                            except Exception:
                                logger.exception("Failed to record ignore on new source")
                        else:
                            # Losing side: the EXISTING source. Add to ITS ignores.
                            try:
                                record_ignore_on_source(
                                    global_mp,
                                    source_url=c.existing_source,
                                    haybale_name=c.name,
                                )
                            except Exception:
                                logger.exception("Failed to record ignore on existing source")
                    dialog.close()
                    on_resolved()

                ui.button("Apply", on_click=_apply).props("flat color=primary")

    dialog.open()
