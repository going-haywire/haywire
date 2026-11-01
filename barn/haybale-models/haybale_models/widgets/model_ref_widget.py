"""ModelRefWidget — the picker for MODEL_REF ports."""

from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any

from nicegui import background_tasks, run, ui

from haybale_models import consumer, hf
from haybale_models.keys import HF_VOLUME, MODELS_VOLUME
from haybale_models.matcher import candidates, entry_matches
from haybale_models.resolver import ModelMissing, ResolvedModel, resolve
from haybale_models.store.layout import volume_path_of
from haybale_models.value.model_ref import ModelRef

from haywire.core.access import LevelMode
from haywire.core.models import CatalogEntry
from haywire.core.volumes import VolumeError, location_of
from haywire.ui import elements as hui
from haywire.ui.access_stamp import stamp_requires
from haywire.ui.elements import FolderTreeModel, folder_tree
from haywire.ui.elements.folder_tree import DEFAULT_EXCLUDE_DIRS
from haywire.ui.widget.base import BaseWidget
from haywire.ui.widget.decorator import widget

_OTHER = "__other__"
_SCHEMES = ("hf://", "https://")
_CHUNK = 1024 * 1024
# The HF cache keeps file contents in blobs/ and names them in snapshots/; only names are picked.
_HF_EXCLUDE_DIRS = DEFAULT_EXCLUDE_DIRS | {"blobs", "refs"}


@widget(description="Pick a model", min_width=220)
class ModelRefWidget(BaseWidget):
    """Pick a model from the catalog, or name a file.

    The list shows the catalog entries the port accepts, by library, each with
    whether it is on this machine (`local`, `HF cache` or `not downloaded`) and
    its size. A catalog entry follows the catalog: an update to the entry
    reaches every graph that uses it.

    Choose **Other…** to name one file instead: type its address (`hf://org/repo/file`
    or `https://…`) and press Enter, or browse the Models and Hugging Face cache
    folders. A file picked from a folder is named by its sha256. An address
    without a digest works, but the card says **not pinned**; **Pin digest** records
    the digest of the file on this machine so the graph always gets exactly that
    file. For an `hf://` address the digest is asked from the Hub once, when the
    address is entered.

    The line below says what the reference resolves to, or what is wrong. The
    picker never downloads: missing models are fetched in the Models editor.

    Options (in `properties`):

    - `filter`: catalog field to allowed values, such as `{"architecture": ["esrgan"]}`;
      only matching entries are listed.
    - `prefer`: ordered list of tag sets for choosing a variant, such as
      `[{"precision": "fp16"}, {}]`.

    ```python
    MODEL_REF.as_inlet("model", widget_config={"properties": {"filter": {"scale": [4]}}})
    ```
    """

    def __init__(self, port: Any) -> None:
        super().__init__(port)
        props = self._config.get("properties", {})
        self._filter: dict[str, list[Any]] = dict(props.get("filter") or {})
        prefer = props.get("prefer")
        self._prefer: list[dict[str, str]] = list(prefer) if prefer else [{}]
        self._other = False
        self._syncing = False
        self._dialog: ui.dialog | None = None
        self._texts: dict[str, str] = {}

    def build(self) -> Any:
        with ui.column().classes("w-full gap-0") as root:
            self._select = (
                hui.select_field(options={}, value=None, min_width="0")
                .classes("w-full")
                .props("options-dense")
                .mark("model-ref-select")
            )
            self._select.on_value_change(self._on_picked)
            # Status and newly installed entries are re-read each time the list opens.
            self._select.on("popup-show", lambda _e: self._refresh_options(statuses=True))
            with ui.row().classes("w-full flex-nowrap items-center gap-1") as other_row:
                self._uri = (
                    hui.input_field(placeholder="hf://… or https://…")
                    .classes("flex-1 min-w-0")
                    .mark("model-ref-uri")
                )
                # Typing writes nothing; Enter or leaving the field enters the address.
                self._uri.on("keydown.enter", lambda _e: self._on_uri_entered())
                self._uri.on("blur", lambda _e: self._on_uri_entered())
                self._browse = hui.icon_action(
                    hui.icon.folder_open,
                    tooltip="Browse the model folders",
                    on_click=self._open_browser,
                ).mark("model-ref-browse")
            self._other_row = other_row
            with ui.row().classes("w-full flex-nowrap items-center gap-1"):
                self._status = (
                    ui.label("").classes("text-xs truncate flex-1 min-w-0").mark("model-ref-status")
                )
                self._pin = (
                    hui.button("Pin digest", on_click=self._on_pin).classes("w-auto").mark("model-ref-pin")
                )
                stamp_requires(self._pin, LevelMode.EDIT)
        self._root = root
        return root

    # ---- model → view ---------------------------------------------------

    def on_model_changed(self, value: Any) -> None:
        """Show *value* in the select, the address field and the status line."""
        ref = _as_ref(value)
        if ref.is_catalog:
            self._other = False
        self._refresh_options(ref)
        source = ref.source or ""
        if self._uri.value != source:
            self._uri.value = source
        self._other_row.set_visibility(self._other or ref.is_file)
        self._show_status(ref)

    def _refresh_options(self, ref: ModelRef | None = None, *, statuses: bool = False) -> None:
        """Rebuild the option list; resolve every entry for its status only when *statuses* is set."""
        if ref is None:
            ref = _as_ref(self.get_value())
        options: dict[str, str] = {}
        entries = [e for e in consumer.models_state().catalog.entries() if entry_matches(e, self._filter)]
        entries.sort(key=lambda e: (e.class_library.label.lower(), e.name.lower()))
        for entry in entries:
            key = entry.class_identity.registry_key
            if statuses:
                self._texts[key] = self._option_text(entry)
            elif key not in self._texts:
                self._texts[key] = self._plain_text(entry)
            options[key] = self._texts[key]
        if ref.is_catalog and ref.catalog not in options:
            # A pasted or filtered-out reference stays shown under its key.
            options[ref.catalog or ""] = f"{ref.catalog} — not installed"
        options[_OTHER] = "Other…"
        if ref.is_catalog:
            selected: str | None = ref.catalog
        elif ref.is_file or self._other:
            selected = _OTHER
        else:
            selected = None
        self._syncing = True
        try:
            self._select.set_options(options, value=selected)
        finally:
            self._syncing = False

    def _plain_text(self, entry: CatalogEntry) -> str:
        """Option text without a local status: the name and the size of the preferred variant."""
        ranked = candidates(entry.resources, self._preference())
        size = ranked[0][1].total_size if ranked else None
        return f"{entry.name} — {_size_text(size)}"

    def _option_text(self, entry: CatalogEntry) -> str:
        key = entry.class_identity.registry_key
        try:
            resolved = self._resolve(ModelRef(catalog=key))
        except ModelMissing:
            ranked = candidates(entry.resources, self._preference())
            size = ranked[0][1].total_size if ranked else None
            return f"{entry.name} — not downloaded, {_size_text(size)}"
        return f"{entry.name} — {_where(resolved)}, {_size_text(resolved.size)}"

    def _preference(self) -> list[dict[str, str]]:
        """Return the node's ``model_preference`` if it has one, else the port's ``prefer``."""
        wrapper = getattr(self.port, "_wrapper", None)
        if wrapper is None or wrapper.is_cleaned_up:
            return self._prefer
        try:
            node = wrapper.node
        except RuntimeError:  # not built yet, or cleaned up since the check above
            return self._prefer
        return list(consumer.preference_for(node, self.port.id))

    def _resolve(self, ref: ModelRef) -> ResolvedModel:
        state = consumer.models_state()
        return resolve(
            ref, self._preference(), catalog=state.catalog, index=state.index, hf_cache=state.hf_cache
        )

    def _show_status(self, ref: ModelRef) -> None:
        unpinned = False
        if ref.is_empty:
            text, ok = "no model chosen", True
        else:
            try:
                resolved = self._resolve(ref)
            except ModelMissing:
                text, ok = "missing — Show in Models", False
            else:
                if ref.is_file and not ref.sha256:
                    text, ok, unpinned = "not pinned — Pin digest", False, True
                else:
                    text, ok = f"resolved: {_variant(resolved)}, {_size_text(resolved.size)}", True
        self._status.text = text
        self._status.classes(
            add="hw-text-muted" if ok else "hw-text-warning",
            remove="hw-text-warning" if ok else "hw-text-muted",
        )
        self._pin.set_visibility(unpinned)

    # ---- view → model ---------------------------------------------------

    def _write(self, ref: ModelRef) -> None:
        if ref != _as_ref(self.get_value()):
            self.set_value(ref)

    def _on_picked(self, event: Any) -> None:
        if self._syncing or event.value is None:
            return
        if event.value == _OTHER:
            if not self._other:
                self._other = True
                self._other_row.set_visibility(True)
            return
        self._other = False
        self._write(ModelRef(catalog=event.value))

    async def _on_uri_entered(self) -> None:
        text = str(self._uri.value or "").strip()
        current = _as_ref(self.get_value())
        if not text or text == current.source:
            return
        if not text.startswith(_SCHEMES):
            self._status.text = "an address starts with hf:// or https://"
            self._status.classes(add="hw-text-warning", remove="hw-text-muted")
            return
        ref = ModelRef(urls=(text,))
        self._write(ref)
        if not text.startswith("hf://") or _as_ref(self.get_value()) != ref:
            return
        answer = await run.io_bound(hf.remote_sha256, text)
        # Pin only the reference this lookup was for; the user may have moved on.
        if answer is not None and _as_ref(self.get_value()) == ref:
            self._write(ref.pinned(*answer))

    async def _on_pin(self) -> None:
        ref = _as_ref(self.get_value())
        if not ref.is_file or ref.sha256:
            return
        try:
            resolved = self._resolve(ref)
        except ModelMissing:
            return
        sha: str | None = resolved.sha256
        if not sha:
            sha = await run.io_bound(_sha256_of, resolved.path)
            if sha is None:  # the app is shutting down
                return
            consumer.models_state().index.add(resolved.path, sha, ref.source)
        if _as_ref(self.get_value()) == ref:
            self._write(ref.pinned(sha, resolved.size))

    async def _on_file_picked(self, path: Path) -> None:
        """Write a file reference for *path*, hashing it first when no digest is known."""
        size = path.stat().st_size
        hf_uri = _hf_uri_of(path)
        if hf_uri is not None:
            blob = path.resolve().name
            sha = blob if len(blob) == 64 and all(c in "0123456789abcdef" for c in blob) else None
            self._write(ModelRef(urls=(hf_uri,), sha256=sha, size=size if sha else None, label=path.name))
            return
        index = consumer.models_state().index
        sha = index.sha256_at(path)
        if sha is None:
            sha = await run.io_bound(_sha256_of, path)
            if sha is None:  # the app is shutting down
                return
            index.add(path, sha, None)
        self._write(ModelRef(sha256=sha, size=size, label=path.name))

    # ---- browser --------------------------------------------------------

    def _open_browser(self) -> None:
        roots = [(label, root) for label, root in _browse_roots() if root.is_dir()]
        if not roots:
            return
        if self._dialog is not None:
            self._dialog.delete()

        def on_pick(path: Path) -> None:
            if path.is_file():
                dialog.close()
                # Hashing an unindexed file runs on a worker thread; the write follows on the loop.
                background_tasks.create(self._on_file_picked(path), name="model-ref-pick")

        # Parented to the widget root so the dialog goes away with the widget.
        with self._root, ui.dialog() as dialog, hui.dialog_card("w-[480px]"):
            hui.heading("Browse models")
            with ui.scroll_area().classes("w-full h-72"):
                for label, root in roots:
                    hui.section_label(label)
                    excluded = _HF_EXCLUDE_DIRS if label == "Hugging Face cache" else DEFAULT_EXCLUDE_DIRS
                    model = FolderTreeModel(root, exclude_dirs=excluded)
                    folder_tree(model, on_select=on_pick).mark(f"model-ref-tree-{label.split()[0].lower()}")
            with hui.action_row():
                hui.button("Cancel", on_click=dialog.close).classes("w-auto").mark("model-ref-cancel")
        self._dialog = dialog
        dialog.open()


def _as_ref(value: Any) -> ModelRef:
    if isinstance(value, ModelRef):
        return value
    return ModelRef.from_dict(value) if isinstance(value, dict) else ModelRef.empty()


def _where(resolved: ResolvedModel) -> str:
    found = volume_path_of(resolved.path)
    return "HF cache" if found is not None and found.volume == HF_VOLUME else "local"


def _variant(resolved: ResolvedModel) -> str:
    if resolved.resource is not None:
        return resolved.resource.variant_name()
    return resolved.ref.label or resolved.path.name


def _size_text(size: int | None) -> str:
    if size is None:
        return "size unknown"
    value = float(size)
    for unit in ("B", "KB", "MB", "GB"):
        if value < 1000 or unit == "GB":
            return f"{value:.0f} {unit}" if unit == "B" else f"{value:.1f} {unit}"
        value /= 1000
    return f"{value:.1f} TB"


def _sha256_of(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as fh:
        while chunk := fh.read(_CHUNK):
            digest.update(chunk)
    return digest.hexdigest()


def _browse_roots() -> list[tuple[str, Path]]:
    roots: list[tuple[str, Path]] = []
    for label, volume in (("Models", MODELS_VOLUME), ("Hugging Face cache", HF_VOLUME)):
        try:
            roots.append((label, location_of(volume)))
        except VolumeError:
            continue
    return roots


def _hf_uri_of(path: Path) -> str | None:
    """``hf://org/repo/file@commit`` for a snapshot file in the HF cache volume, else ``None``."""
    found = volume_path_of(path)
    if found is None or found.volume != HF_VOLUME:
        return None
    parts = found.relative.split("/")
    # models--<org>--<repo>/snapshots/<commit>/<path in repo>
    if len(parts) < 4 or parts[1] != "snapshots" or not parts[0].startswith("models--"):
        return None
    repo = parts[0][len("models--") :].replace("--", "/")
    return f"hf://{repo}/{'/'.join(parts[3:])}@{parts[2]}"
