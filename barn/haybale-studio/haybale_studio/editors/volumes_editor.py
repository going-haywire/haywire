"""VolumesEditor — see and set where each volume lives on this machine.

Admin-only. A volume is a named root that graphs reference by
``(volume, relative)``; this editor writes the per-machine location of each one
to the volumes file through ``VolumeStore``. Locations are typed as absolute
server paths: the browser cannot pick a folder on the server.
"""

from __future__ import annotations

import logging
from pathlib import Path

from haywire.core.access import AccessTier
from haywire.core.volumes import VolumeStatus, get_volume_store, list_volumes
from haywire.ui import elements as hui
from haywire.ui.editor.base import BaseEditor
from haywire.ui.editor.decorator import editor
from haywire.ui.editor.identity import SlotName
from nicegui import ui

logger = logging.getLogger(__name__)


@editor(
    label="Volumes",
    icon="storage",
    default_slot=SlotName.ACTION,
    requires=AccessTier.ADMIN,
    description="Where each volume lives on this machine",
)
class VolumesEditor(BaseEditor):
    """One row per volume: name, location, where the location came from, and set/remove controls.

    A location that does not exist on this machine (unplugged drive, folder
    not created yet) is marked *missing*; it is still a valid location.
    """

    _GRID_COLUMNS = "grid-cols-[10rem_1fr_6rem_auto]"

    def __init__(self, wrapper) -> None:
        super().__init__(wrapper)
        self._rows: ui.column | None = None
        self._error: ui.label | None = None

    def draw(self, context, container) -> None:
        container.clear()
        with container:
            with ui.column().classes("w-full gap-4 p-4"):
                hui.section_label("Volumes")
                hui.hint(
                    "Graphs refer to files as (volume, relative path); set where each volume lives here."
                )
                self._error = hui.error_label("")
                self._error.set_visibility(False)
                self._rows = ui.column().classes("w-full gap-0 hw-panel")
                self._draw_rows()
                self._draw_add_form()

    # -- rows -----------------------------------------------------------

    def _draw_rows(self) -> None:
        """Re-read ``list_volumes()`` and rebuild the rows."""
        if self._rows is None:
            return
        self._rows.clear()
        with self._rows:
            with ui.row().classes(f"grid {self._GRID_COLUMNS} w-full items-center gap-2 px-2 py-1"):
                hui.hint("Name")
                hui.hint("Location")
                hui.hint("Source")
                ui.label()
            try:
                statuses = list_volumes()
            except Exception as exc:
                hui.error_label(f"Volumes unreadable: {exc}")
                return
            for status in statuses:
                self._draw_row(status)

    def _draw_row(self, status: VolumeStatus) -> None:
        name = status.name
        with ui.row().classes(
            f"grid {self._GRID_COLUMNS} w-full items-center gap-2 px-2 py-1 hw-list-item-hover"
        ):
            with ui.column().classes("gap-0"):
                ui.label(name).classes("font-medium truncate")
                if status.label and status.label != name:
                    hui.hint(status.label)

            if status.configurable:
                field = (
                    ui.input(value=str(status.location) if status.location else "")
                    .props('dense outlined autocomplete="off" placeholder="/absolute/folder"')
                    .classes("w-full")
                    .mark(f"volume-location-{name}")
                )
            else:
                field = None
                ui.label(str(status.location) if status.location else "").classes("truncate")
            with ui.row().classes("items-center gap-1").mark(f"volume-status-{name}"):
                ui.label(status.source)
                if status.location is not None and not status.exists:
                    ui.label("missing").classes("text-negative").mark(f"volume-missing-{name}")

            with ui.row().classes("items-center gap-0 no-wrap"):
                if field is not None:
                    hui.icon_action(
                        "check",
                        tooltip="Set location",
                        on_click=lambda n=name, f=field: self._set_location(n, f.value),
                    ).mark(f"volume-set-{name}")
                    if status.source == "configured":
                        hui.icon_action(
                            "delete",
                            tooltip="Remove the configured location",
                            on_click=lambda n=name: self._remove(n),
                        ).mark(f"volume-remove-{name}")

    # -- add form -------------------------------------------------------

    def _draw_add_form(self) -> None:
        hui.section_label("Add a volume")
        with ui.row().classes("w-full items-end gap-2 flex-wrap"):
            name = (
                ui.input("Name")
                .classes("min-w-[8rem]")
                .props('dense outlined autocomplete="off"')
                .mark("volume-add-name")
            )
            location = (
                ui.input("Location (absolute folder)")
                .classes("min-w-[12rem] flex-1")
                .props('dense outlined autocomplete="off"')
                .mark("volume-add-location")
            )
            ui.button(
                icon="add",
                on_click=lambda: self._add(name, location),
            ).classes("flex-shrink-0").props("flat dense").mark("volume-add")

    # -- mutations ------------------------------------------------------

    def _show_error(self, message: str) -> None:
        if self._error is not None:
            self._error.set_text(message)
            self._error.set_visibility(bool(message))

    def _write(self, action) -> bool:
        """Run a store write; show any failure instead of crashing. Returns success."""
        client = ui.context.client
        try:
            action(get_volume_store())
        except Exception as exc:  # ValueError, TOML decode error, TypeError on a malformed file
            logger.debug("VolumesEditor: write failed", exc_info=True)
            self._show_error(str(exc))
            with client:
                ui.notify(str(exc), type="negative")
            return False
        self._show_error("")
        self._draw_rows()
        return True

    def _set_location(self, name: str, location: str) -> None:
        self._write(lambda store: store.set(name, Path((location or "").strip())))

    def _remove(self, name: str) -> None:
        self._write(lambda store: store.remove(name))

    def _add(self, name_input: ui.input, location_input: ui.input) -> None:
        name = (name_input.value or "").strip()
        location = (location_input.value or "").strip()
        if self._write(lambda store: store.set(name, Path(location))):
            name_input.set_value("")
            location_input.set_value("")
