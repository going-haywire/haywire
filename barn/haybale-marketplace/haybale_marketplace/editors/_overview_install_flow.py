"""Install / update / version-picker entry points for LibraryOverviewEditor.

Both install entry points now open the stepped flow in ``_install_flow/``.
The three modals they used to drive — ``install_safety_modal``,
``upgrade_impact_modal`` and ``library_operation_progress_modal`` — are no
longer called from here; their content became the flow's first, second and
third steps respectively. They remain in ``haywire.ui.modals`` as public API
rather than being deleted, since third-party libraries may use them.
"""

from __future__ import annotations

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
    """Open the Install / Update flow for *pkg*.

    Replaces the old modal chain (safety modal → upgrade-impact modal →
    progress modal, with an asyncio.Future hand-rolled to await the middle
    one's decision). The flow's first step carries the trust notice the safety
    modal used to show, and its resolve step carries the collateral-upgrade
    list, so the same three decisions happen in one place with the resolver
    run once instead of twice.

    *button* is accepted for call-site compatibility and no longer used: the
    flow owns its own busy state.
    """
    from haywire.core.marketstall import (
        record_block_on_source,
        resolve_block_target,
    )

    from haybale_marketplace.state.marketplace_state import MarketplaceState

    from ._install_flow import ManagerInstallSource, show_install_flow

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
        if active is not None and active.row.name == pkg.name:
            context.active_library = None
        notify_library_changed(context)

    def _after() -> None:
        flow = holder.get("flow")
        if flow is not None and getattr(flow, "succeeded", False):
            installed = find_installed_by_dist_name(pkg.name, manager)
            if installed:
                context.active_library = installed
        notify_library_changed(context)

    holder: dict[str, object] = {}
    holder["flow"] = show_install_flow(
        ManagerInstallSource(manager),
        pkg.install_spec,
        pkg.name,
        package=pkg,
        on_done=_after,
        on_block=_on_block,
    )


def install_package(
    install_spec: str,
    name: str,
    button: Button | None,
    manager: "LibraryManager",
    context: "SessionContext",
    source_pkg: Haybale | None = None,
) -> None:
    """Open the Install / Update flow for *install_spec*.

    The Update button's entry point, and the version picker's. Was a coroutine
    that drove three modals in sequence; the flow owns that sequence now, so
    this is synchronous and the call sites no longer await anything.

    ``source_pkg`` still enables write-back to the project's pyproject.toml so
    the install is reproducible via ``uv sync`` — it is handed to install()
    unchanged.

    *button* is accepted for call-site compatibility and no longer used: the
    flow owns its own busy state.
    """
    from ._install_flow import ManagerInstallSource, show_install_flow

    def _after() -> None:
        flow = holder.get("flow")
        if flow is not None and getattr(flow, "succeeded", False):
            installed = find_installed_by_dist_name(name, manager)
            if installed:
                context.active_library = installed
        notify_library_changed(context)

    holder: dict[str, object] = {}
    holder["flow"] = show_install_flow(
        ManagerInstallSource(manager),
        install_spec,
        name,
        package=source_pkg,
        on_done=_after,
    )


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
