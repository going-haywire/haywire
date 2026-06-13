"""Enable / disable / uninstall actions for LibraryOverviewEditor."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from nicegui import background_tasks, ui
from nicegui.element import Element

from haywire.core.library.info import LibraryInfo
from haywire.core.session.signals import LibraryCatalogChanged
from haywire.ui import elements as hui
from haywire.ui.modals import confirm_modal

if TYPE_CHECKING:
    from haybale_marketplace.library_manager import LibraryManager
    from haywire.core.session.context import SessionContext

logger = logging.getLogger(__name__)


def notify_library_changed(context: "SessionContext") -> None:
    session = context.session
    if session is not None:
        session.publish(LibraryCatalogChanged())


def reload_installed(
        library_id: str, 
        manager: "LibraryManager"
    ) -> LibraryInfo | None:
    try:
        libs = manager.list_installed()
        return next((lib for lib in libs if lib.identity.id == library_id), None)
    except Exception:
        return None


def find_installed_by_dist_name(
        dist_name: str, 
        manager: "LibraryManager"
    ) -> LibraryInfo | None:
    try:
        libs = manager.list_installed()
        return next((lib for lib in libs if lib.distribution_name == dist_name), None)
    except Exception:
        return None


def enable_library(
        library_id: str, 
        manager: "LibraryManager", 
        context: "SessionContext"
    ) -> None:
    manager.registry.enable_library(library_id)
    ui.notify(f"Enabled: {library_id}", type="positive")
    context.active_library = reload_installed(library_id, manager)
    notify_library_changed(context)


def disable_library(
        library_id: str, 
        manager: "LibraryManager", 
        context: "SessionContext"
    ) -> None:
    manager.registry.disable_library(library_id)
    ui.notify(f"Disabled: {library_id}", type="warning")
    context.active_library = reload_installed(library_id, manager)
    notify_library_changed(context)


def confirm_uninstall(
    library_id: str,
    label: str,
    manager: "LibraryManager",
    context: "SessionContext",
) -> None:
    def _on_confirm():
        client = ui.context.client

        async def _run_with_client():
            with client:
                await do_uninstall(library_id, label, manager, context)

        background_tasks.create(_run_with_client(), name=f"uninstall-{library_id}")

    confirm_modal(
        title=f"Uninstall {label}?",
        message=(
            "This will disable the library and remove it from the venv. "
            "Any graph nodes using this library will show as errors."
        ),
        confirm_label="Uninstall",
        danger=True,
        on_confirm=_on_confirm,
    )


def create_log_in_card(container: Element, title: str) -> "ui.log":
    with container:
        with hui.expansion_section(title, icon=hui.icon.terminal):
            log = ui.log(max_lines=50).classes("w-full h-32")
    return log


async def do_uninstall(
    library_id: str,
    label: str,
    manager: "LibraryManager",
    context: "SessionContext",
) -> None:
    from haywire.ui.modals import library_operation_progress_modal

    ui.notify(f"Uninstalling {label}…", type="info")
    progress = library_operation_progress_modal(title=f"Uninstalling {label}…")

    success, message, hints = await manager.uninstall_streaming(library_id, progress.push)

    if success:
        progress.push(f"--- {label} uninstalled successfully ---")
        progress.finish(hints=hints)
        ui.notify(f"Uninstalled: {label}", type="positive")
        context.active_library = None
        notify_library_changed(context)
    else:
        progress.push(f"--- ERROR: {message} ---")
        progress.finish(error=message, hints=hints)
        ui.notify(message, type="negative")
