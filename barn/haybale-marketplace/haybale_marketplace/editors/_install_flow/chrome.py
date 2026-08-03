"""Popup entry point and step→panel wiring for the Install / Update flow."""

from __future__ import annotations

from typing import Callable, Optional

from nicegui import ui

from haywire.core.marketstall import Haybale
from haywire.ui.components.stepper import Panel, show_step_flow

from ._state import InstallFlow, InstallSource, resolve_current_version
from .panels import _panel_checked, _panel_done, _panel_installing, _panel_selected


class ManagerInstallSource:
    """Adapts :class:`LibraryManager` to :class:`InstallSource`.

    The manager already exposes all three methods with matching signatures;
    this exists so the flow depends on the narrow protocol rather than on the
    manager, keeping the tests free of a library system.
    """

    def __init__(self, manager) -> None:
        self._manager = manager

    async def dry_run(self, install_spec: str) -> list[str]:
        return await self._manager.dry_run(install_spec)

    async def install(self, install_spec, on_output, source_pkg=None, known_removals=None):
        return await self._manager.install(install_spec, on_output, source_pkg, known_removals)

    def get_installed_version(self, dist_name: str) -> str:
        return self._manager.get_installed_version(dist_name)


def show_install_flow(
    source: InstallSource,
    install_spec: str,
    name: str,
    *,
    package: Optional[Haybale] = None,
    on_done: Callable[[], None] | None = None,
    on_block: Callable[[], None] | None = None,
) -> InstallFlow:
    """Open the Install / Update flow and return its state machine.

    Update is not a separate flow: pass an *install_spec* for a newer version
    of something already present and the panels adapt, which is how
    ``install_package`` always treated it.

    *on_block* wires the "don't offer this again" side exit — a first-install
    rejection that drops the haybale from the catalog rather than installing
    it. Omit it and no block affordance renders.
    """
    flow = InstallFlow(
        source=source,
        install_spec=install_spec,
        name=name,
        package=package,
        current_version=resolve_current_version(source, package),
    )

    def _selected(f: InstallFlow, rerender: Callable[[], None]) -> None:
        _panel_selected(f, rerender)
        if on_block is not None and not f.is_update:
            _render_block(f, on_block)

    panels: dict[str, Panel[InstallFlow]] = {
        "selected": _selected,
        "checked": _panel_checked,
        "installing": _panel_installing,
        # on_done fires from the popup's close handler, so Done only dismisses.
        "done": lambda f, _rerender: _panel_done(f, None),
    }

    flow.popup = show_step_flow(
        flow,
        panels,
        title=("Update" if flow.is_update else "Install") + f" {name}",
        width="620px",
        on_done=on_done,
    )
    return flow


def _render_block(flow: InstallFlow, on_block: Callable[[], None]) -> None:
    """The side exit off the first step: reject this source's offer entirely.

    A side exit rather than a step, mirroring the share wizard's precondition
    fixes — blocking means the user is not installing, so it leaves the flow
    instead of advancing it. Whether per-source blocking is the right model at
    all is a separate question, tracked in
    internals/handoff/marketplace-blocked-category-and-source-conflicts.md.
    """

    def _do_block() -> None:
        if flow.popup is not None:
            flow.popup.close()
        on_block()

    with ui.row().classes("w-full justify-start"):
        ui.button("Don't offer this again", on_click=_do_block).props("flat dense").style(
            "color: var(--hw-danger);"
        )
