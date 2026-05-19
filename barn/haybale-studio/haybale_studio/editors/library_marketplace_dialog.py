"""Add Source dialog for the Library Manager (Plan E Phase 4).

Three tabs:
  - Marketplace URL  → write to global [[marketplaces]]
  - Marketstall URL  → write to global [[marketstalls]]
  - Direct package   → write to global [[packages]]

Each tab validates input on click. On success, the dialog closes and
calls on_added() so the caller can refresh the marketplace and re-render
the library list.
"""

from __future__ import annotations

import logging
from typing import Callable

from nicegui import ui

from haywire.ui import elements as hui

logger = logging.getLogger(__name__)


def show_add_source_dialog(on_added: Callable[[], None]) -> None:
    """Open the Add Source dialog.

    `on_added` is called after a successful add — typically the caller
    refreshes the marketplace and re-renders the library list.

    The three tabs each call a per-kind handler (Task 27 wires the
    actual marketplace_runtime calls).
    """
    with ui.dialog() as dialog, hui.dialog_card():
        with ui.column().classes("p-4 gap-3 w-96"):
            ui.label("Add a marketplace source").classes("text-sm font-medium")
            ui.label("Subscribe to a remote feed or paste a direct package entry.").classes(
                "text-xs hw-text-dim"
            )

            with ui.tabs().classes("w-full") as tabs:
                tab_marketplace = ui.tab("Marketplace URL")
                tab_marketstall = ui.tab("Marketstall URL")
                tab_direct = ui.tab("Direct package")

            with ui.tab_panels(tabs, value=tab_marketplace).classes("w-full"):
                with ui.tab_panel(tab_marketplace):
                    ui.label("Subscribe to a remote marketplace (aggregates many marketstalls).").classes(
                        "text-xs hw-text-dim"
                    )
                    marketplace_input = hui.input_field(
                        placeholder="https://example.com/marketplace.toml",
                    )
                    ui.button(
                        "Add marketplace",
                        on_click=lambda: _handle_add_marketplace(marketplace_input.value, dialog, on_added),
                    ).props("flat dense size=sm")

                with ui.tab_panel(tab_marketstall):
                    ui.label("Subscribe to a single-author marketstall feed.").classes("text-xs hw-text-dim")
                    marketstall_input = hui.input_field(
                        placeholder="https://author.example/marketstall.toml",
                    )
                    ui.button(
                        "Add marketstall",
                        on_click=lambda: _handle_add_marketstall(marketstall_input.value, dialog, on_added),
                    ).props("flat dense size=sm")

                with ui.tab_panel(tab_direct):
                    ui.label("Paste a [[packages]] TOML block for a single library.").classes(
                        "text-xs hw-text-dim"
                    )
                    direct_input = (
                        ui.textarea(placeholder='[[packages]]\nname = "haybale-foo"\n...\n')
                        .classes("w-full font-mono text-xs")
                        .props("rows=10")
                    )
                    ui.button(
                        "Add package",
                        on_click=lambda: _handle_add_direct(direct_input.value, dialog, on_added),
                    ).props("flat dense size=sm")

            with ui.row().classes("w-full justify-end"):
                ui.button("Cancel", on_click=dialog.close).props("flat")

    dialog.open()


def _handle_add_marketplace(url: str, dialog: "ui.dialog", on_added: Callable[[], None]) -> None:
    """Validate URL, write to global [[marketplaces]], close dialog, trigger on_added."""
    from haywire.core.marketplace_runtime import (
        add_marketplace_subscription_to_global,
    )

    from haywire_studio.config import GLOBAL_CONFIG_DIR, ensure_global_config

    url = (url or "").strip()
    if not url:
        ui.notify("Please paste a URL.", type="warning")
        return
    if not (url.startswith("http://") or url.startswith("https://")):
        ui.notify("URL must start with http:// or https://", type="warning")
        return

    try:
        ensure_global_config()
        add_marketplace_subscription_to_global(GLOBAL_CONFIG_DIR / "marketplace.toml", url)
    except Exception as exc:
        logger.exception("Failed to add marketplace subscription")
        ui.notify(f"Failed to add: {exc}", type="negative")
        return

    ui.notify(f"Subscribed to {url}", type="positive")
    dialog.close()
    _check_and_prompt_conflicts(
        new_source_url=url,
        new_source_is_marketstall=False,
        on_done=on_added,
    )


def _handle_add_marketstall(url: str, dialog: "ui.dialog", on_added: Callable[[], None]) -> None:
    """Validate URL, write to global [[marketstalls]], close dialog, trigger on_added."""
    from haywire.core.marketplace_runtime import (
        add_marketstall_subscription_to_global,
    )

    from haywire_studio.config import GLOBAL_CONFIG_DIR, ensure_global_config

    url = (url or "").strip()
    if not url:
        ui.notify("Please paste a URL.", type="warning")
        return
    if not (url.startswith("http://") or url.startswith("https://")):
        ui.notify("URL must start with http:// or https://", type="warning")
        return

    try:
        ensure_global_config()
        add_marketstall_subscription_to_global(GLOBAL_CONFIG_DIR / "marketplace.toml", url)
    except Exception as exc:
        logger.exception("Failed to add marketstall subscription")
        ui.notify(f"Failed to add: {exc}", type="negative")
        return

    ui.notify(f"Subscribed to {url}", type="positive")
    dialog.close()
    _check_and_prompt_conflicts(
        new_source_url=url,
        new_source_is_marketstall=True,
        on_done=on_added,
    )


def _handle_add_direct(toml_block: str, dialog: "ui.dialog", on_added: Callable[[], None]) -> None:
    """Parse the pasted TOML, validate it has [[packages]], write to global [[packages]]."""
    from haywire.core.marketplace_runtime import add_direct_package_to_global

    from haywire_studio.config import GLOBAL_CONFIG_DIR, ensure_global_config

    toml_block = (toml_block or "").strip()
    if not toml_block:
        ui.notify("Please paste a [[packages]] TOML block.", type="warning")
        return

    try:
        ensure_global_config()
        add_direct_package_to_global(GLOBAL_CONFIG_DIR / "marketplace.toml", toml_block)
    except Exception as exc:
        logger.exception("Failed to add direct package")
        ui.notify(f"Failed to add: {exc}", type="negative")
        return

    ui.notify("Direct package added.", type="positive")
    dialog.close()
    on_added()


def _check_and_prompt_conflicts(
    new_source_url: str,
    new_source_is_marketstall: bool,
    on_done: Callable[[], None],
) -> None:
    """After a subscription is added, fetch + check for name conflicts, then prompt the user."""
    from pathlib import Path

    from haywire.core.marketplace_errors import RemoteFetchError
    from haywire.core.marketplace_runtime import (
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
        new_pkgs = list(contents.packages)
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

    conflicts = detect_subscription_conflicts(project_mp.packages, new_pkgs)

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
    from haywire.core.marketplace_runtime import record_ignore_on_source

    from haywire_studio.config import GLOBAL_CONFIG_DIR

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
                    global_mp = GLOBAL_CONFIG_DIR / "marketplace.toml"
                    for c in conflicts:
                        if choices.get(c.name) == "existing":
                            # Losing side: the NEW subscription. Add to ITS ignores.
                            try:
                                record_ignore_on_source(
                                    global_mp,
                                    source_url=c.new_source,
                                    package_name=c.name,
                                )
                            except Exception:
                                logger.exception("Failed to record ignore on new source")
                        else:
                            # Losing side: the EXISTING source. Add to ITS ignores.
                            try:
                                record_ignore_on_source(
                                    global_mp,
                                    source_url=c.existing_source,
                                    package_name=c.name,
                                )
                            except Exception:
                                logger.exception("Failed to record ignore on existing source")
                    dialog.close()
                    on_resolved()

                ui.button("Apply", on_click=_apply).props("flat color=primary")

    dialog.open()
