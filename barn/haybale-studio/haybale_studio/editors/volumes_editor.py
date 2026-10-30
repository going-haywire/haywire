"""VolumesEditor — see and set where each volume lives on this machine.

Admin-only. A volume is a named root that graphs reference by
``(volume, relative)``; this editor writes the per-machine location of each one
to the volumes file through ``VolumeStore``. Locations are typed as absolute
server paths: the browser cannot pick a folder on the server.
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from pathlib import Path

from haybale_studio.editors.path_fit import fitted_path, install_path_fit
from haywire.core.access import AccessTier
from haywire.core.session.context import SessionContext
from haywire.core.volumes import VolumeStatus, VolumeStore, get_volume_store, list_volumes
from haywire.ui import elements as hui
from haywire.ui.editor.base import BaseEditor
from haywire.ui.editor.decorator import editor
from haywire.ui.editor.identity import SlotName
from nicegui import ui

logger = logging.getLogger(__name__)


@editor(
    label="Volumes",
    icon=hui.icon.volumes,
    default_slot=SlotName.ACTION,
    requires=AccessTier.ADMIN,
    description="Where each volume lives on this machine",
)
class VolumesEditor(BaseEditor):
    """One row per volume: its name, and below it where it lives on this machine.

    A row's button opens the volume's details: to change its location when this
    session may, to read them otherwise. The header's add button adds a volume.
    A location that does not exist on this machine (unplugged drive, folder not
    created yet) is marked *missing*; it is still a valid location.
    """

    def __init__(self, wrapper) -> None:
        super().__init__(wrapper)
        self._context: SessionContext | None = None
        self._rows: ui.column | None = None
        self._dialog_host: ui.element | None = None
        self._dialog: ui.dialog | None = None

    def draw(self, context, container) -> None:
        self._context = context
        container.clear()
        with container:
            with ui.column().classes("w-full h-full gap-0") as root:
                with hui.slot_header("Volumes", icon=hui.icon.volumes):
                    if self._can_write():
                        hui.icon_action(hui.icon.add, tooltip="Add a volume", on_click=self._open_add).mark(
                            "volume-add"
                        )
                with ui.scroll_area().classes("flex-1 w-full"):
                    self._rows = ui.column().classes("w-full gap-0 p-1")
            self._dialog_host = root
            self._draw_rows()

    def _can_write(self) -> bool:
        """Whether this session may change the volumes file (the editor's own ``admin`` tier)."""
        return self._context is not None and bool(self._context.can_admin())

    # -- rows -----------------------------------------------------------

    def _draw_rows(self) -> None:
        """Re-read ``list_volumes()`` and rebuild the rows."""
        if self._rows is None:
            return
        self._rows.clear()
        with self._rows:
            try:
                statuses = list_volumes()
            except Exception as exc:
                hui.error_label(f"Volumes unreadable: {exc}")
                return
            can_write = self._can_write()
            for status in statuses:
                self._draw_row(status, editable=can_write and status.configurable)
            install_path_fit()

    def _draw_row(self, status: VolumeStatus, *, editable: bool) -> None:
        name = status.name
        with (
            ui.row()
            .classes("w-full items-center no-wrap gap-1 px-2 py-1 rounded hw-list-item-hover")
            .mark(f"volume-row-{name}")
        ):
            with ui.column().classes("gap-0 flex-1 min-w-0"):
                hui.subject(name).classes("truncate w-full")
                if status.location is None:
                    hui.hint("not defined on this machine").classes("truncate w-full").mark(
                        f"volume-undefined-{name}"
                    )
                else:
                    with ui.row().classes("w-full items-center no-wrap gap-1 min-w-0"):
                        fitted_path(status.location).classes("flex-1").mark(f"volume-location-{name}")
                        if not status.exists:
                            ui.label("missing").classes("text-xs text-negative flex-shrink-0").mark(
                                f"volume-missing-{name}"
                            )
            hui.icon_action(
                hui.icon.edit if editable else hui.icon.view,
                tooltip="Edit" if editable else "Details",
                on_click=lambda s=status, e=editable: self._open_details(s, editable=e),
            ).classes("flex-shrink-0").mark(f"volume-open-{name}")

    # -- modals ---------------------------------------------------------

    def _new_dialog(self) -> ui.dialog:
        """Return a fresh dialog, deleting the one opened before it."""
        if self._dialog is not None and not self._dialog.is_deleted:
            self._dialog.delete()
        assert self._dialog_host is not None
        # The host is a stable parent: a dialog opened from a row outlives that row's redraw.
        with self._dialog_host:
            self._dialog = ui.dialog()
        return self._dialog

    def _open_details(self, status: VolumeStatus, *, editable: bool) -> None:
        name = status.name
        location_text = str(status.location) if status.location is not None else ""
        dialog = self._new_dialog().mark("volume-dialog")
        with dialog, hui.dialog_card("w-[480px] max-w-full"):
            hui.heading(name)
            if status.label and status.label != name:
                hui.hint(status.label)
            if status.description:
                ui.label(status.description).classes("text-sm")
            with ui.column().classes("w-full gap-0"):
                hui.info_row("Source", status.source, label_width="w-20", copyable=False)
                hui.info_row(
                    "Exists",
                    "yes" if status.exists else ("missing" if status.location else "—"),
                    label_width="w-20",
                    copyable=False,
                )
                if not editable:
                    hui.info_row(
                        "Location", location_text or "not defined on this machine", label_width="w-20"
                    )
            error = _dialog_error()
            if editable:
                field = (
                    hui.input_field(label="Location (absolute folder)", value=location_text)
                    .props('autocomplete="off"')
                    .mark("volume-dialog-location")
                )
                with hui.action_row().classes("mt-2"):
                    if status.source == "configured":
                        ui.button(
                            "Remove",
                            on_click=lambda: self._write(dialog, error, lambda store: store.remove(name)),
                        ).props("flat dense").classes("hw-text-danger mr-auto").mark("volume-dialog-remove")
                    ui.button("Cancel", on_click=dialog.close).props("flat dense")
                    hui.confirm_button(
                        "Save",
                        on_click=lambda: self._write(
                            dialog, error, lambda store: store.set(name, Path((field.value or "").strip()))
                        ),
                    ).mark("volume-dialog-save")
            else:
                with hui.action_row().classes("mt-2"):
                    ui.button("Close", on_click=dialog.close).props("flat dense")
        dialog.open()

    def _open_add(self) -> None:
        dialog = self._new_dialog().mark("volume-dialog")
        with dialog, hui.dialog_card("w-[480px] max-w-full"):
            hui.heading("Add a volume")
            name = hui.input_field(label="Name").props('autocomplete="off"').mark("volume-add-name")
            location = (
                hui.input_field(label="Location (absolute folder)")
                .props('autocomplete="off"')
                .mark("volume-add-location")
            )
            error = _dialog_error()
            hui.dialog_actions(
                on_confirm=lambda: self._write(
                    dialog,
                    error,
                    lambda store: store.set(
                        (name.value or "").strip(), Path((location.value or "").strip())
                    ),
                ),
                on_cancel=dialog.close,
                confirm_label="Add",
            ).mark("volume-add-confirm")
        dialog.open()

    # -- mutations ------------------------------------------------------

    def _write(self, dialog: ui.dialog, error: ui.label, action: Callable[[VolumeStore], object]) -> None:
        """Run a store write; a failure shows in ``error`` and keeps ``dialog`` open, success closes it."""
        if not self._can_write():
            _show(error, "Changing volumes needs admin access.")
            return
        try:
            action(get_volume_store())
        except Exception as exc:  # ValueError, TOML decode error, TypeError on a malformed file
            logger.debug("VolumesEditor: write failed", exc_info=True)
            _show(error, str(exc))
            return
        dialog.close()
        self._draw_rows()


def _dialog_error() -> ui.label:
    """Draw a hidden error line for a dialog."""
    label = hui.error_label("").classes("whitespace-pre-line").mark("volume-dialog-error")
    label.set_visibility(False)
    return label


def _show(error: ui.label, message: str) -> None:
    error.set_text(message)
    error.set_visibility(True)
