"""Upgrade impact modal — confirms collateral library upgrades before install.

Shown when `dry_run()` discovers that installing a requested library will
also upgrade other already-loaded libraries. Two sections:
  - "Installing": the package the user asked for
  - "Also upgrading": libraries that will be upgraded as side-effects

Two buttons: Cancel (abort) and Continue (proceed).
"""

from __future__ import annotations

from typing import Callable

from nicegui import ui

from haywire.ui.components.popup import Popup


def upgrade_impact_modal(
    *,
    installing: str,
    also_upgrading: list[str],
    on_continue: Callable[[], None],
    on_cancel: Callable[[], None] | None = None,
) -> Popup:
    """Open the upgrade impact confirmation modal and return the opened Popup.

    Args:
        installing: Display name of the package the user requested
            (e.g. "haybale-visiongraph").
        also_upgrading: List of pip distribution names that will be upgraded
            as collateral side-effects (e.g. ["haybale-core"]).
        on_continue: Called when the user clicks Continue. Popup closes after.
        on_cancel: Called when the user cancels. Optional.

    Returns:
        The opened Popup.
    """
    popup = Popup(
        title="Confirm install",
        width="400px",
        closable=True,
        backdrop_click_close=True,
        escape_close=True,
        backdrop_color="transparent",
    )

    confirmed = {"value": False}

    if on_cancel is not None:

        def _maybe_cancel() -> None:
            if not confirmed["value"]:
                on_cancel()

        popup.on_close(_maybe_cancel)

    with popup:
        with ui.column().classes("w-full gap-3 p-1"):
            with ui.column().classes("gap-1"):
                ui.label("Installing").classes("text-xs font-semibold hw-text-dim uppercase tracking-wide")
                ui.label(installing).classes("text-sm")

            ui.separator()

            with ui.column().classes("gap-1"):
                ui.label("Also upgrading").classes(
                    "text-xs font-semibold hw-text-dim uppercase tracking-wide"
                )
                ui.label(
                    "Installing this library requires upgrading the following already-loaded libraries."
                ).classes("text-xs hw-text-dim")
                for name in also_upgrading:
                    with ui.row().classes("items-center gap-1"):
                        ui.icon("upgrade", size="14px").classes("hw-text-accent")
                        ui.label(name).classes("text-sm font-mono")

            def _do_continue() -> None:
                confirmed["value"] = True
                on_continue()
                popup.close()

            with ui.row().classes("w-full justify-end gap-2 mt-1"):
                ui.button("Cancel", on_click=popup.close).props("flat dense")
                ui.button("Continue", on_click=_do_continue).props("flat dense").style(
                    "color: var(--hw-positive);"
                )

    popup.open()
    return popup
