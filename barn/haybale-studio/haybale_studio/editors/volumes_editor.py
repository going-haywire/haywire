"""VolumesEditor — the volumes on this machine and where each one lives.

Admin-only. A volume is a named root that graphs reference by
``(volume key, relative)``; this editor adds, edits and deletes the entries of
the volumes file through ``VolumeStore``. Locations are typed as absolute server
paths: the browser cannot pick a folder on the server.
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from pathlib import Path

from haywire.core.access import AccessTier
from haywire.core.session.context import SessionContext
from haywire.core.volumes import (
    VolumeStatus,
    VolumeStore,
    get_volume_store,
    is_user_volume_key,
    list_volumes,
    user_volume_key,
    volume_name,
)
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
    """One row per volume: its label, and below it where it lives on this machine.

    A row's button opens the volume's details: to change its label, description
    and location when this session may, to read them otherwise. A volume a user
    added can be deleted; a volume a library added cannot, and is reset to the
    location its library suggests instead. The project volume is always the open
    project's folder and cannot be changed. The header's add button adds a volume.
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
                # QScrollArea's content box is absolute and shrinks to its widest line; a full
                # width pins rows to the slot so the location line crops instead of overflowing.
                with (
                    ui.scroll_area()
                    .classes("flex-1 w-full")
                    .props('content-style="width: 100%" content-active-style="width: 100%"')
                ):
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
                self._draw_row(status, editable=can_write and status.editable)

    def _draw_row(self, status: VolumeStatus, *, editable: bool) -> None:
        name = volume_name(status.key)
        with (
            ui.row()
            .classes("w-full items-center no-wrap gap-1 px-2 py-1 rounded hw-list-item-hover")
            .mark(f"volume-row-{name}")
        ):
            with ui.column().classes("gap-0 flex-1 min-w-0"):
                hui.subject(status.label or name).classes("truncate w-full")
                if status.location is None:
                    hui.hint("not defined on this machine").classes("truncate w-full").mark(
                        f"volume-undefined-{name}"
                    )
                else:
                    with ui.row().classes("w-full items-center no-wrap gap-1 min-w-0"):
                        hui.fitted_path(status.location).classes("hw-hint flex-1 h-4").mark(
                            f"volume-location-{name}"
                        )
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
        key = status.key
        location_text = str(status.location) if status.location is not None else ""
        dialog = self._new_dialog().mark("volume-dialog")
        with dialog, hui.dialog_card("w-[480px] max-w-full"):
            hui.heading(status.label or volume_name(key))
            if not editable:
                if status.description:
                    ui.label(status.description).classes("text-sm")
                with ui.column().classes("w-full gap-0"):
                    hui.info_row("Key", key, label_width="w-20").mark("volume-dialog-key")
                    hui.info_row(
                        "Location", location_text or "not defined on this machine", label_width="w-20"
                    )
                    hui.info_row(
                        "Exists",
                        "yes" if status.exists else ("missing" if status.location else "—"),
                        label_width="w-20",
                        copyable=False,
                    )
                with hui.action_row().classes("mt-2"):
                    ui.button("Close", on_click=dialog.close).props("flat dense")
                dialog.open()
                return
            hui.info_row("Key", key, label_width="w-20").mark("volume-dialog-key")
            label = hui.input_field(label="Label", value=status.label).mark("volume-dialog-label")
            description = hui.input_field(label="Description", value=status.description).mark(
                "volume-dialog-description"
            )
            field = (
                hui.input_field(label="Location (absolute folder)", value=location_text)
                .props('autocomplete="off"')
                .mark("volume-dialog-location")
            )
            user_volume = is_user_volume_key(key)
            if not user_volume:
                hui.hint(
                    f"Suggested location: {status.suggested}"
                    if status.suggested is not None
                    else "Its library has not recorded a suggested location."
                ).mark("volume-dialog-suggested")
            error = _dialog_error()
            with hui.action_row().classes("mt-2"):
                if user_volume:
                    ui.button(
                        "Delete",
                        on_click=lambda: self._write(dialog, error, lambda store: store.remove(key)),
                    ).props("flat dense").classes("hw-text-danger mr-auto").mark("volume-dialog-delete")
                elif status.suggested is not None:
                    ui.button(
                        "Reset to suggested location",
                        on_click=lambda: self._write(dialog, error, lambda store: store.reset(key)),
                    ).props("flat dense").classes("mr-auto").mark("volume-dialog-reset")
                ui.button("Cancel", on_click=dialog.close).props("flat dense")
                hui.confirm_button(
                    "Save",
                    on_click=lambda: self._write(
                        dialog,
                        error,
                        lambda store: store.update(
                            key,
                            label=(label.value or "").strip(),
                            description=(description.value or "").strip(),
                            location=Path((field.value or "").strip()),
                        ),
                    ),
                ).mark("volume-dialog-save")
        dialog.open()

    def _open_add(self) -> None:
        dialog = self._new_dialog().mark("volume-dialog")
        with dialog, hui.dialog_card("w-[480px] max-w-full"):
            hui.heading("Add a volume")
            name = hui.input_field(label="Name").props('autocomplete="off"').mark("volume-add-name")
            key_hint = hui.hint("Key: user:volume:").mark("volume-add-key")
            name.on_value_change(lambda e: key_hint.set_text(f"Key: user:volume:{(e.value or '').strip()}"))
            label = hui.input_field(label="Label").mark("volume-add-label")
            description = hui.input_field(label="Description").mark("volume-add-description")
            location = (
                hui.input_field(label="Location (absolute folder)")
                .props('autocomplete="off"')
                .mark("volume-add-location")
            )
            error = _dialog_error()

            def add(store: VolumeStore) -> None:
                text = (name.value or "").strip()
                store.add(
                    user_volume_key(text),
                    label=(label.value or "").strip() or text,
                    description=(description.value or "").strip(),
                    location=Path((location.value or "").strip()),
                )

            hui.dialog_actions(
                on_confirm=lambda: self._write(dialog, error, add),
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
        except Exception as exc:  # ValueError from the store, an OS error writing the file
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
