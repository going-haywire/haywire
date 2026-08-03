"""Popup entry point and step→panel wiring for the Uninstall Library flow."""

from __future__ import annotations

from pathlib import Path
from typing import Callable, Optional

from haywire.ui.components.stepper import Panel, show_step_flow

from ._state import UninstallFlow, UninstallSource
from .panels import _panel_confirm, _panel_impact, _panel_removed, _panel_selected


class ManagerUninstallSource:
    """Adapts :class:`LibraryManager` to :class:`UninstallSource`.

    The two lookups the flow needs live on the *registry*, not the manager,
    and ``get_library_install_type`` returns an ``InstallType`` enum where the
    flow wants a plain name. Rather than widen the protocol to the manager's
    whole surface, this translates at the boundary.
    """

    def __init__(self, manager) -> None:
        self._manager = manager

    def get_library_distribution_name(self, library_id: str) -> str | None:
        return self._manager.registry.get_library_distribution_name(library_id)

    def get_library_install_type(self, library_id: str) -> str:
        install_type = self._manager.registry.get_library_install_type(library_id)
        return install_type.name if install_type is not None else ""

    async def uninstall_streaming(self, library_id: str, on_output):
        return await self._manager.uninstall_streaming(library_id, on_output)


def show_uninstall_flow(
    source: UninstallSource,
    library_id: str,
    label: str,
    *,
    workspace_root: Optional[Path] = None,
    on_done: Callable[[], None] | None = None,
) -> UninstallFlow:
    """Open the Uninstall Library flow and return its state machine.

    *on_done* fires when the popup closes — the caller refreshes its view
    there, since a completed uninstall changes what is installed. Passing no
    *workspace_root* means graphs are not scanned, and the impact step says so
    rather than implying none were found.
    """
    flow = UninstallFlow(
        source=source,
        library_id=library_id,
        label=label,
        workspace_root=workspace_root,
    )

    panels: dict[str, Panel[UninstallFlow]] = {
        "selected": _panel_selected,
        "impact": _panel_impact,
        "confirm": _panel_confirm,
        # on_done fires from the popup's close handler, so Done only dismisses.
        "removed": lambda f, _rerender: _panel_removed(f, None),
    }

    flow.popup = show_step_flow(
        flow,
        panels,
        title=f"Uninstall {label}",
        width="620px",
        on_done=on_done,
    )
    return flow
