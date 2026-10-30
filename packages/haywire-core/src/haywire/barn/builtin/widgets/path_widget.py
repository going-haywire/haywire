"""PathWidget — the picker for PATH, FILE_PATH and FOLDER_PATH ports."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from nicegui import ui

from haywire.core.volumes import VolumeError, VolumePath, list_volumes, location_of, resolve
from haywire.ui import elements as hui
from haywire.ui.elements import FolderTreeModel, folder_tree
from haywire.ui.elements.folder_tree import DEFAULT_EXCLUDE_DIRS
from haywire.ui.widget.base import BaseWidget
from haywire.ui.widget.decorator import widget

_MODES = ("file", "folder", "save")


@widget(description="Pick a file or folder inside a volume")
class PathWidget(BaseWidget):
    """Pick a file or folder inside a volume such as `project`, `home` or `models`.

    Choose the volume, then type the path inside it or browse to it. The line
    below shows where the path points on this machine, or what is wrong: a
    volume that is not defined here, or a volume whose folder is missing (an
    unplugged drive, say). Volumes are defined in the Volumes editor.

    Options (in `properties`):

    - `mode`: `"file"` (default) picks an existing file, `"folder"` a folder,
      `"save"` a folder plus a file name typed in the browser.
    - `extensions`: file endings such as `".png"` that the browser shows in
      `file` and `save` mode; empty shows every file.

    ```python
    PathWidget.config(properties={"mode": "folder"})
    PathWidget.config(properties={"mode": "file", "extensions": [".png", ".jpg"]})
    ```
    """

    def __init__(self, port: Any) -> None:
        super().__init__(port)
        props = self._config.get("properties", {})
        mode = props.get("mode", "file")
        self._mode: str = mode if mode in _MODES else "file"
        self._extensions = frozenset(props.get("extensions", []) or [])
        self._dialog: ui.dialog | None = None

    def build(self) -> Any:
        with ui.column().classes("w-full gap-0") as root:
            with ui.row().classes("w-full flex-nowrap items-center gap-1"):
                self._select = (
                    ui.select(options={}, value=None)
                    .classes("w-24 text-xs")
                    .props("dense options-dense")
                    .mark("path-volume")
                )
                self._select.on_value_change(self._on_volume_picked)
                self._input = (
                    ui.input(value="", placeholder="path inside the volume")
                    .classes("flex-1 min-w-0")
                    .props("dense")
                    .mark("path-relative")
                )
                # ui.input emits update:value for user edits; model writes to .value fire no event.
                self._input.on("update:value", self._on_relative_typed)
                self._browse = (
                    ui.button(icon=hui.icon.folder_open, on_click=self._open_browser)
                    .props("flat dense size=xs")
                    .mark("path-browse")
                    .tooltip("Browse")
                )
            self._status = ui.label("").classes("text-xs truncate").mark("path-status")
        self._root = root
        return root

    # ---- model → view ---------------------------------------------------

    def on_model_changed(self, value: Any) -> None:
        """Show *value* in the select, the path field and the status line."""
        path = self._current(value)
        options = {s.name: s.label for s in list_volumes()}
        options.setdefault(path.volume, path.volume)
        self._select.set_options(options, value=path.volume)
        if self._input.value != path.relative:
            self._input.value = path.relative
        text, ok = self._status_of(path)
        self._status.text = text
        self._status.classes(
            add="hw-text-muted" if ok else "hw-text-warning",
            remove="hw-text-warning" if ok else "hw-text-muted",
        )
        self._browse.set_enabled(self._location(path.volume) is not None)

    @staticmethod
    def _current(value: Any) -> VolumePath:
        return value if isinstance(value, VolumePath) else VolumePath("project", "")

    @staticmethod
    def _location(volume: str) -> Path | None:
        """Return the volume's existing root folder, or ``None`` when undefined or missing."""
        try:
            location = location_of(volume)
        except VolumeError:
            return None
        return location if location.is_dir() else None

    @staticmethod
    def _status_of(path: VolumePath) -> tuple[str, bool]:
        """Return the status text for *path* and whether it describes a usable location."""
        try:
            location = location_of(path.volume)
            if not location.exists():
                return f"location missing: {location}", False
            return str(resolve(path)), True
        except VolumeError as exc:
            return str(exc), False

    # ---- view → model ---------------------------------------------------

    def _write(self, path: VolumePath) -> None:
        if path != self.get_value():
            self.set_value(path)

    def _on_volume_picked(self, event: Any) -> None:
        if event.value:
            self._write(VolumePath(event.value, self._current(self.get_value()).relative))

    def _on_relative_typed(self, event: Any) -> None:
        text = event.sender.value
        self._write(VolumePath(self._current(self.get_value()).volume, "" if text is None else str(text)))

    # ---- browser --------------------------------------------------------

    def _open_browser(self) -> None:
        volume = self._current(self.get_value()).volume
        root = self._location(volume)
        if root is None:
            return
        if self._dialog is not None:
            self._dialog.delete()
        # One eager level: a volume can be a whole home folder, and expanding loads deeper on demand.
        model = FolderTreeModel(
            root,
            show_files=self._mode != "folder",
            extensions=self._extensions,
            exclude_dirs=DEFAULT_EXCLUDE_DIRS,
            batch_depth=1,
        )
        picked = {"folder": ""}

        def relative(path: Path) -> str:
            rel = path.relative_to(root).as_posix()
            return "" if rel == "." else rel

        def on_pick(path: Path) -> None:
            if self._mode == "file":
                if path.is_file():
                    self._write(VolumePath(volume, relative(path)))
                    dialog.close()
                return
            if path.is_file():
                name.value = path.name
                path = path.parent
            picked["folder"] = relative(path)
            picked_label.text = f"{volume}:{picked['folder'] or '/'}"

        def confirm() -> None:
            target = picked["folder"]
            if self._mode == "save":
                file_name = (name.value or "").strip()
                if not file_name:
                    return
                target = f"{target}/{file_name}" if target else file_name
            self._write(VolumePath(volume, target))
            dialog.close()

        # Parented to the widget root so the dialog goes away with the widget.
        with self._root, ui.dialog() as dialog, hui.dialog_card("w-[480px]"):
            hui.heading(f"Browse {volume}")
            with ui.scroll_area().classes("w-full h-72"):
                folder_tree(model, on_select=on_pick)
            with ui.row().classes("w-full flex-nowrap items-center gap-1") as picked_row:
                hui.hint("Selected:")
                picked_label = hui.hint(f"{volume}:/").classes("font-mono truncate").mark("path-picked")
            name = hui.input_field(label="File name").mark("path-save-name")
            picked_row.set_visibility(self._mode != "file")
            name.set_visibility(self._mode == "save")
            if self._mode == "file":
                with hui.action_row():
                    ui.button("Cancel", on_click=dialog.close).props("flat dense")
            else:
                hui.dialog_actions(on_confirm=confirm, on_cancel=dialog.close, confirm_label="Select")
        self._dialog = dialog
        dialog.open()
