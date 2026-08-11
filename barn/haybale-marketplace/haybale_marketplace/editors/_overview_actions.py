"""Enable / disable / uninstall actions for LibraryOverviewEditor."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from nicegui import ui
from nicegui.element import Element

from haywire.core.library.info import LibraryInfo
from haywire.core.session.signals import LibraryCatalogChanged
from haywire.ui import elements as hui

if TYPE_CHECKING:
    from haybale_marketplace.library_manager import LibraryManager
    from haywire.core.session.context import SessionContext

logger = logging.getLogger(__name__)


def notify_library_changed(context: "SessionContext") -> None:
    session = context.session
    if session is not None:
        session.publish(LibraryCatalogChanged())


def reload_installed(library_id: str, manager: "LibraryManager") -> LibraryInfo | None:
    """Reload the installed library with the given ID from the manager."""
    try:
        libs = manager.list_installed()
        return next((lib for lib in libs if lib.identity.id == library_id), None)
    except Exception:
        return None


def find_installed_by_dist_name(dist_name: str, manager: "LibraryManager") -> LibraryInfo | None:
    try:
        libs = manager.list_installed()
        return next((lib for lib in libs if lib.row.name == dist_name), None)
    except Exception:
        return None


def enable_library(library_id: str, manager: "LibraryManager", context: "SessionContext") -> None:
    manager.registry.enable_library(library_id)
    ui.notify(f"Enabled: {library_id}", type="positive")
    context.active_library = reload_installed(library_id, manager)
    notify_library_changed(context)


def disable_library(library_id: str, manager: "LibraryManager", context: "SessionContext") -> None:
    ok = manager.registry.disable_library(library_id)
    if ok:
        ui.notify(f"Disabled: {library_id}", type="warning")
    else:
        # The registry refuses FOLDER-mechanism libraries on its own (see
        # LibraryRegistry.disable_library) regardless of what the UI's own
        # block_reason gate decided — this branch is the defense-in-depth
        # backstop, not the primary gate (that's _origin.is_protected on the
        # Disable button itself).
        ui.notify(f"Cannot disable: {library_id}", type="negative")
    context.active_library = reload_installed(library_id, manager)
    notify_library_changed(context)


def confirm_uninstall(
    library_id: str,
    label: str,
    manager: "LibraryManager",
    context: "SessionContext",
) -> None:
    """Open the stepped uninstall flow.

    Replaces a single confirm modal whose warning ("any graph nodes using this
    library will show as errors") was asserted but never checked. The flow
    checks it — plus the pip reverse-dependencies ``uv uninstall`` does not
    resolve — and only then offers the destructive button.
    """
    from pathlib import Path

    from ._uninstall_flow import show_uninstall_flow
    from ._uninstall_flow.chrome import ManagerUninstallSource

    workspace_root = getattr(context.app, "workspace_root", None)

    # Mutable cell: on_done is wired before the flow object exists, and it
    # needs to know whether the uninstall actually happened.
    holder: dict[str, object] = {}

    def _after() -> None:
        # Only drop the selection when the library actually went away — a
        # flow abandoned at the impact step must leave the overview intact.
        flow = holder.get("flow")
        if flow is not None and getattr(flow, "succeeded", False):
            context.active_library = None
        notify_library_changed(context)

    holder["flow"] = show_uninstall_flow(
        ManagerUninstallSource(manager),
        library_id,
        label,
        workspace_root=Path(workspace_root) if workspace_root else None,
        on_done=_after,
    )


def create_log_in_card(container: Element, title: str) -> "ui.log":
    with container:
        with hui.expansion_section(title, icon=hui.icon.terminal):
            log = ui.log(max_lines=50).classes("w-full h-32")
    return log
