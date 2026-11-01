"""ModelRefWidget — the picker for MODEL_REF ports."""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from pathlib import Path
from collections.abc import Callable
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
_MODEL_SUFFIXES = frozenset({".safetensors", ".pth", ".pt", ".ckpt", ".onnx", ".bin", ".gguf"})
_SHA256 = re.compile(r"[0-9a-f]{64}")
_HF_ROW_LIMIT = 200


@widget(description="Pick a model", min_width=220)
class ModelRefWidget(BaseWidget):
    """Pick a model from the catalog, or name a file.

    The list shows the catalog entries the port accepts, by library, each with
    whether it is on this machine (`local`, `HF cache` or `not downloaded`) and
    its size. A catalog entry follows the catalog: an update to the entry
    reaches every graph that uses it.

    Choose **Other…** to name one file instead: type its address (`hf://org/repo/file`
    or `https://…`) and press Enter, or browse. The browser shows the Models folder and the
    model files in the Hugging Face cache, listed as `org/repo/file`. A file picked
    from the Models folder is named by its sha256; one picked from the cache is named
    by its `hf://` address and its sha256, so it works offline. An address
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
                    tooltip="Browse the model files",
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
        index = consumer.models_state().index
        sha = index.sha256_at(path)
        if sha is None:
            sha = await run.io_bound(_sha256_of, path)
            if sha is None:  # the app is shutting down
                return
            index.add(path, sha, None)
        self._write(ModelRef(sha256=sha, size=size, label=path.name))

    def _on_hf_picked(self, row: _HfRow) -> None:
        """Write a pinned ``hf://`` reference for a cached file; it resolves from the cache."""
        file = row.file
        sha = file.blob_path.name if _SHA256.fullmatch(file.blob_path.name) else None
        self._write(
            ModelRef(urls=(row.uri,), sha256=sha, size=file.size, label=Path(file.path_in_repo).name)
        )

    # ---- browser --------------------------------------------------------

    def _open_browser(self) -> None:
        models_root = _location(MODELS_VOLUME)
        hf_root = _location(HF_VOLUME)
        if models_root is None and hf_root is None:
            return
        if self._dialog is not None:
            self._dialog.delete()

        def on_pick(path: Path) -> None:
            if path.is_file():
                dialog.close()
                # Hashing an unindexed file runs on a worker thread; the write follows on the loop.
                background_tasks.create(self._on_file_picked(path), name="model-ref-pick")

        def on_hf_pick(row: _HfRow) -> None:
            dialog.close()
            self._on_hf_picked(row)

        # Parented to the widget root so the dialog goes away with the widget.
        with self._root, ui.dialog() as dialog, hui.dialog_card("w-[480px]"):
            hui.heading("Browse models")
            with ui.scroll_area().classes("w-full h-72"):
                if models_root is not None:
                    hui.section_label("Models")
                    model = FolderTreeModel(models_root, exclude_dirs=DEFAULT_EXCLUDE_DIRS)
                    folder_tree(model, on_select=on_pick).mark("model-ref-tree-models")
                if hf_root is not None:
                    hui.section_label("Hugging Face cache")
                    search = hui.input_field(placeholder="Search…", clearable=True).mark(
                        "model-ref-hf-search"
                    )
                    holder = ui.column().classes("w-full gap-0").mark("model-ref-hf-list")
                    with holder:
                        ui.label("Scanning…").classes("text-xs hw-text-muted")
                    background_tasks.create(
                        _fill_hf_list(hf_root, holder, search, on_hf_pick), name="model-ref-hf-scan"
                    )
            with hui.action_row():
                hui.button("Cancel", on_click=dialog.close).classes("w-auto").mark("model-ref-cancel")
        self._dialog = dialog
        dialog.open()


@dataclass(frozen=True)
class _HfRow:
    """One pickable cached model file and the address that names it."""

    file: hf.HfCachedFile
    uri: str

    @property
    def label(self) -> str:
        return f"{self.file.repo_id}/{self.file.path_in_repo}"


async def _fill_hf_list(
    cache_dir: Path, holder: ui.column, search: ui.input, on_pick: Callable[[_HfRow], None]
) -> None:
    """Scan the HF cache off the UI thread, then list its model files under *holder*."""
    rows = await run.io_bound(_hf_model_rows, cache_dir)
    if rows is None or holder.is_deleted:  # shutting down, or the dialog went away
        return

    def draw() -> None:
        needle = str(search.value or "").strip().lower()
        shown = [r for r in rows if needle in r.label.lower()]
        holder.clear()
        with holder:
            if not shown:
                ui.label("No model files cached" if not rows else "No match").classes(
                    "text-xs hw-text-muted"
                )
            for row in shown[:_HF_ROW_LIMIT]:
                hui.list_item(
                    row.label, sublabel=_size_text(row.file.size), on_click=lambda r=row: on_pick(r)
                ).mark("model-ref-hf-pick")
            if len(shown) > _HF_ROW_LIMIT:
                ui.label(f"{len(shown) - _HF_ROW_LIMIT} more — narrow the search").classes(
                    "text-xs hw-text-muted"
                )

    search.on_value_change(lambda _e: draw())
    draw()


def _hf_model_rows(cache_dir: Path) -> list[_HfRow]:
    """Return the model files in the HF cache, one row per ``(repo, path)``, ordered by label.

    Only files with a model suffix (``.safetensors``, ``.pth``, ``.pt``, ``.ckpt``, ``.onnx``,
    ``.bin``, ``.gguf``, any case) are listed. When a path is cached at several revisions, the
    revision ``refs/main`` points to wins; otherwise the one whose blob is newest. The address
    omits ``@revision`` for ``main``.
    """
    best: dict[tuple[str, str], tuple[tuple[bool, float], hf.HfCachedFile]] = {}
    mains: dict[str, str | None] = {}
    for file in hf.list_cache(cache_dir):
        if Path(file.path_in_repo).suffix.lower() not in _MODEL_SUFFIXES:
            continue
        if file.repo_id not in mains:
            mains[file.repo_id] = _main_revision(cache_dir, file.repo_id)
        try:
            mtime = file.blob_path.stat().st_mtime
        except OSError:
            mtime = 0.0
        rank = (file.revision == mains[file.repo_id], mtime)
        key = (file.repo_id, file.path_in_repo)
        if key not in best or rank >= best[key][0]:
            best[key] = (rank, file)
    rows = []
    for _rank, file in best.values():
        suffix = "" if file.revision == mains[file.repo_id] else f"@{file.revision}"
        rows.append(_HfRow(file, f"hf://{file.repo_id}/{file.path_in_repo}{suffix}"))
    rows.sort(key=lambda r: (r.label.lower(), r.label))
    return rows


def _main_revision(cache_dir: Path, repo_id: str) -> str | None:
    ref = cache_dir / ("models--" + repo_id.replace("/", "--")) / "refs" / "main"
    try:
        return ref.read_text().strip() or None
    except OSError:
        return None


def _location(volume: str) -> Path | None:
    try:
        root = location_of(volume)
    except VolumeError:
        return None
    return root if root.is_dir() else None


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
