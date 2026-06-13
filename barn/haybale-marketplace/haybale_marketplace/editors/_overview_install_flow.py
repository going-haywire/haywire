"""Install / update / version-picker flow for LibraryOverviewEditor."""

from __future__ import annotations

import asyncio
import logging
from typing import TYPE_CHECKING

from nicegui import background_tasks, ui
from nicegui.elements.button import Button

from haywire.core.marketstall import Haybale

from haybale_marketplace.editors._overview_actions import (
    find_installed_by_dist_name,
    notify_library_changed,
)

if TYPE_CHECKING:
    from haybale_marketplace.library_manager import LibraryManager
    from haywire.core.session.context import SessionContext

logger = logging.getLogger(__name__)


def install_with_safety_check(
    pkg: Haybale,
    button: Button | None,
    manager: "LibraryManager",
    context: "SessionContext",
) -> None:
    """Interpose the safety modal before install_package.

    The modal fires on every Install click. The user can Cancel, Block the
    source (drops the haybale from AVAILABLE permanently), or Install.
    """
    from haywire.core.marketstall import (
        record_block_on_source,
        resolve_block_target,
    )
    from haywire.ui.modals import install_safety_modal

    from haybale_marketplace.state.marketplace_state import MarketplaceState

    def _on_install():
        # Return the coroutine (don't schedule it). The modal awaits it,
        # which keeps the NiceGUI slot context intact so ui.notify() inside
        # install_package works. See .insights/feedback_nicegui_async.md.
        return install_package(pkg.install_spec, pkg.name, button, manager, context, pkg)

    def _on_block() -> None:
        if context.app_data is None or MarketplaceState not in context.app_data:
            ui.notify("Marketplace state not available", type="warning")
            return
        state = context.app_data[MarketplaceState]
        global_path = state._global_path()
        target = resolve_block_target(global_path, pkg.via)
        if target is None:
            ui.notify(
                f"Cannot block {pkg.name}: not from a subscription you can edit.",
                type="warning",
            )
            return
        try:
            record_block_on_source(global_path, source_url=target, haybale_name=pkg.name)
        except Exception as exc:
            logger.exception("Failed to record block")
            ui.notify(f"Failed to block: {exc}", type="negative")
            return
        ui.notify(f"Blocked {pkg.name} from {target}", type="positive")
        state.refresh()
        active = getattr(context, "active_library", None)
        if active is not None and getattr(active, "name", None) == pkg.name:
            context.active_library = None
        notify_library_changed(context)

    def _on_cancel() -> None:
        ui.notify(f"Install of {pkg.name} cancelled", type="info")

    install_safety_modal(
        haybale_name=pkg.name,
        source_url=pkg.source_url or "",
        on_install=_on_install,
        on_block=_on_block,
        on_cancel=_on_cancel,
    )


async def install_package(
    install_spec: str,
    name: str,
    button: Button | None,
    manager: "LibraryManager",
    context: "SessionContext",
    source_pkg: Haybale | None = None,
) -> None:
    """Install a package using the 3-step flow:
    dry-run → optional upgrade-impact confirmation → streaming progress popup.

    ``source_pkg`` enables write-back to the project's pyproject.toml so the
    install is reproducible via ``uv sync``.
    """
    from haywire.ui.modals import library_operation_progress_modal, upgrade_impact_modal

    if button:
        try:
            button.disable()
            button.props("loading")
        except Exception:
            pass

    # Step 1: dry-run to discover collateral upgrades
    try:
        removals = await manager.dry_run(install_spec)
    except RuntimeError as exc:
        ui.notify(str(exc), type="negative")
        if button:
            try:
                button.enable()
                button.props(remove="loading")
            except Exception:
                pass
        return

    # Step 2: if collateral upgrades exist, confirm with the user
    if removals:
        loop = asyncio.get_event_loop()
        decision: asyncio.Future[bool] = loop.create_future()

        def _on_continue() -> None:
            if not decision.done():
                decision.set_result(True)

        def _on_cancel() -> None:
            if not decision.done():
                decision.set_result(False)

        upgrade_impact_modal(
            installing=name,
            also_upgrading=removals,
            on_continue=_on_continue,
            on_cancel=_on_cancel,
        )

        try:
            proceed = await decision
        finally:
            pass

        if not proceed:
            if button:
                try:
                    button.enable()
                    button.props(remove="loading")
                except Exception:
                    pass
            return

    # Step 3: open progress popup and run the install
    try:
        progress = library_operation_progress_modal(title=f"Installing {name}…")

        success, message, hints = await manager.install(install_spec, progress.push, source_pkg)

        if success:
            progress.push(f"--- {name} installed successfully ---")
            progress.finish(hints=hints)
            ui.notify(f"Installed: {name}", type="positive")
            installed = find_installed_by_dist_name(name, manager)
            if installed:
                context.active_library = installed
            notify_library_changed(context)
        else:
            progress.push(f"--- ERROR: {message} ---")
            progress.finish(error=message, hints=hints)
            ui.notify(message, type="negative")
    finally:
        if button:
            try:
                button.enable()
                button.props(remove="loading")
            except Exception:
                pass


def open_version_picker(pkg: Haybale, manager: "LibraryManager", context: "SessionContext") -> None:
    """Dialog to fetch and select a specific version for installation."""
    with ui.dialog() as dialog, ui.card().classes("min-w-80"):
        ui.label(f"Install specific version — {pkg.name}").classes("text-lg font-bold mb-2")
        version_select = (
            ui.select(
                options=["Loading…"],
                value="Loading…",
                label="Version",
            )
            .classes("w-full")
            .props("dense")
        )
        status = ui.label("Fetching versions…").classes("text-xs hw-text-dim")

        async def load_versions():
            versions = await manager.fetch_versions(pkg)
            if versions:
                version_select.options = versions
                version_select.value = versions[0]
                status.text = f"{len(versions)} versions available"
            else:
                version_select.options = ["(unavailable)"]
                version_select.value = "(unavailable)"
                status.text = "Could not fetch version list"

        async def install_selected(e):
            selected = version_select.value
            if not selected or selected in ("Loading…", "(unavailable)"):
                return
            dialog.close()
            spec = manager.build_versioned_spec(pkg, selected)
            from dataclasses import replace

            versioned_pkg = replace(pkg, install_spec=spec)
            install_with_safety_check(versioned_pkg, None, manager, context)

        with ui.row().classes("w-full justify-end gap-2 mt-4"):
            ui.button("Cancel", on_click=dialog.close).props("flat")
            ui.button("Install", on_click=install_selected).props("color=positive")

    dialog.open()
    background_tasks.create(load_versions(), name=f"version-picker-{pkg.name}")
