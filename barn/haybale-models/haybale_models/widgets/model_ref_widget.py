"""ModelRefWidget — the picker for MODEL_REF ports: a compact card row and a picker dialog."""

from __future__ import annotations

import hashlib
import os
import re
from collections.abc import Callable
from dataclasses import dataclass
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
from haywire.ui.widget.base import BaseWidget
from haywire.ui.widget.decorator import widget

_SCHEMES = ("hf://", "https://")
_CHUNK = 1024 * 1024
_MODEL_SUFFIXES = frozenset({".safetensors", ".pth", ".pt", ".ckpt", ".onnx", ".bin", ".gguf"})
_SHA256 = re.compile(r"[0-9a-f]{64}")
_ROW_LIMIT = 200

# Card states: (icon, colour class, tooltip headline).
_RESOLVED = "resolved"
_UNPINNED = "unpinned"
_MISSING = "missing"
_NONE = "none"
_STATE_LOOK: dict[str, tuple[str, str, str]] = {
    _RESOLVED: (hui.icon.models, "hw-text-success", "On this machine"),
    _UNPINNED: ("online_prediction", "hw-text-warning", "Not pinned — the file at the address may change"),
    _MISSING: (hui.icon.models, "hw-text-warning", "Not on this machine — fetch it in the Models editor"),
    _NONE: (hui.icon.models, "hw-text-danger", "No model chosen"),
}

# Picker tabs, in order.
_TAB_CATALOG = "catalog"
_TAB_FILES = "files"
_TAB_HF = "hf"
_TAB_ADDRESS = "address"


@widget(description="Pick a model", min_width=220)
class ModelRefWidget(BaseWidget):
    """Pick the model a node uses.

    The card shows one line: a state icon, the model's name and an edit button.

    - Green icon: the model is on this machine.
    - Amber `online_prediction` icon: an address that is not pinned yet; the pin
      button next to it records the digest of the file on this machine.
    - Amber icon: the model is not on this machine; fetch it in the Models editor.
    - Red icon: no model chosen.

    Hover the name for the details. The edit button opens the picker, with the
    choice at the top and four tabs:

    - **Catalog**: the catalog entries this port accepts. A catalog entry follows
      the catalog: each machine uses the variant that suits it best.
    - **Models Volume**: a file in the Models volume, named by its sha256.
    - **Hugging Face**: a model file in the Hugging Face cache, named by its `hf://`
      address and its sha256, so it works offline.
    - **Address**: an `hf://` or `https://` address. An `hf://` address is pinned when
      the Hub answers; an `https://` address once the file is on this machine.

    **Use** stores the choice (pinned when its digest is known), **Cancel** drops it.
    The picker never downloads: missing models are fetched in the Models editor.

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
        self._dialog: ui.dialog | None = None
        self._draft: ModelRef = ModelRef.empty()
        self._current: ui.column | None = None

    def build(self) -> Any:
        with ui.row().classes("w-full flex-nowrap items-center gap-1") as root:
            self._icon = (
                ui.icon(hui.icon.models, size="xs")
                .classes("hw-use-props-color hw-text-danger")
                .mark("model-ref-state")
            )
            with self._icon:
                self._icon_tip = ui.tooltip("")
            self._name = ui.label("").classes("text-sm truncate flex-1 min-w-0").mark("model-ref-name")
            with self._name:
                self._name_tip = ui.tooltip("")
            self._pin = hui.icon_action("push_pin", tooltip="Pin the digest", on_click=self._on_pin).mark(
                "model-ref-pin"
            )
            stamp_requires(self._pin, LevelMode.EDIT)
            hui.icon_action(hui.icon.edit, tooltip="Choose a model", on_click=self._open_picker).mark(
                "model-ref-edit"
            )
        self._root = root
        return root

    # ---- model → card ---------------------------------------------------

    def on_model_changed(self, value: Any) -> None:
        """Show *value* on the card: state icon, name, details and the pin button."""
        ref = _as_ref(value)
        state, resolved = self._state_of(ref)
        icon, colour, headline = _STATE_LOOK[state]
        self._icon.name = icon
        self._icon.classes(remove=" ".join(look[1] for look in _STATE_LOOK.values()))
        self._icon.classes(add=colour)
        self._icon_tip.text = headline
        self._name.text = self._name_of(ref)
        if ref.is_empty:
            self._name.classes(add="hw-text-muted")
        else:
            self._name.classes(remove="hw-text-muted")
        self._name_tip.text = "\n".join([headline, *self._details(ref, resolved)])
        self._pin.set_visibility(state == _UNPINNED)

    def _state_of(self, ref: ModelRef) -> tuple[str, ResolvedModel | None]:
        if ref.is_empty:
            return _NONE, None
        try:
            resolved = self._resolve(ref)
        except ModelMissing:
            return _MISSING, None
        if ref.is_file and not ref.sha256:
            return _UNPINNED, resolved
        return _RESOLVED, resolved

    def _name_of(self, ref: ModelRef) -> str:
        """The short name: catalog entry name, the repo of an ``hf://`` address, else the file name."""
        if ref.is_empty:
            return "no model"
        if ref.is_catalog:
            entry = consumer.models_state().catalog.entry(ref.catalog or "")
            return entry.name if entry is not None else (ref.catalog or "").rsplit(":", 1)[-1]
        source = ref.source or ""
        if source.startswith("hf://"):
            try:
                return hf.parse_hf(source).repo_id.split("/", 1)[-1]
            except ValueError:
                pass
        if ref.label:
            return ref.label
        return source.rstrip("/").rsplit("/", 1)[-1] or "model file"

    def _details(self, ref: ModelRef, resolved: ResolvedModel | None) -> list[str]:
        """The tooltip lines after the headline: what is stored, and what it is here."""
        lines: list[str] = []
        if ref.is_catalog:
            lines.append(f"Catalog: {ref.catalog}")
        elif ref.source:
            lines.append(f"Address: {ref.source}")
        elif ref.is_file:
            lines.append(f"File: {ref.label or 'model file'}")
        if ref.sha256:
            lines.append(f"sha256: {ref.sha256[:12]}…")
        if resolved is not None:
            lines.append(f"Here: {_variant(resolved)}, {_size_text(resolved.size)} ({_where(resolved)})")
        elif ref.size is not None:
            lines.append(f"Size: {_size_text(ref.size)}")
        return lines

    # ---- shared ---------------------------------------------------------

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

    def _write(self, ref: ModelRef) -> None:
        if ref != _as_ref(self.get_value()):
            self.set_value(ref)

    async def _pinned_if_known(self, ref: ModelRef) -> ModelRef | None:
        """Return *ref* pinned to the digest of its file on this machine, or ``None`` if it is not here.

        Hashes the file on a worker thread when the index does not know its digest yet.
        """
        try:
            resolved = self._resolve(ref)
        except ModelMissing:
            return None
        sha: str | None = resolved.sha256
        if not sha:
            sha = await run.io_bound(_sha256_of, resolved.path)
            if sha is None:  # the app is shutting down
                return None
            consumer.models_state().index.add(resolved.path, sha, ref.source)
        return ref.pinned(sha, resolved.size)

    async def _on_pin(self) -> None:
        ref = _as_ref(self.get_value())
        if not ref.is_file or ref.sha256:
            return
        pinned = await self._pinned_if_known(ref)
        # Pin only the reference this was for; the value may have changed meanwhile.
        if pinned is not None and _as_ref(self.get_value()) == ref:
            self._write(pinned)

    # ---- picker ---------------------------------------------------------

    def _open_picker(self) -> None:
        if self._dialog is not None:
            self._dialog.delete()
        current = _as_ref(self.get_value())
        self._draft = current
        # Parented to the widget root so the dialog goes away with the widget.
        with self._root, ui.dialog() as dialog, hui.dialog_card("w-[520px]"):
            hui.heading("Choose a model")
            self._current = ui.column().classes("w-full gap-0").mark("model-ref-current")
            tabs_el, _tabs = hui.tabs(
                (_TAB_CATALOG, "Catalog", "menu_book"),
                (_TAB_FILES, "Models Volume", hui.icon.folder_open),
                (_TAB_HF, "Hugging Face", "hub"),
                (_TAB_ADDRESS, "Address", "link"),
            )
            with ui.tab_panels(tabs_el, value=_tab_for(current)).classes("w-full").mark("model-ref-tabs"):
                with ui.tab_panel(_TAB_CATALOG):
                    self._build_catalog_tab()
                with ui.tab_panel(_TAB_FILES):
                    self._build_list_tab("model-ref-file", self._file_rows, self._on_file_chosen)
                with ui.tab_panel(_TAB_HF):
                    self._build_list_tab("model-ref-hf", self._hf_rows, self._on_hf_chosen)
                with ui.tab_panel(_TAB_ADDRESS):
                    self._build_address_tab(current)
            with hui.action_row().classes("mt-2"):
                ui.button("Cancel", on_click=dialog.close).props("flat dense").mark("model-ref-cancel")
                use = hui.confirm_button("Use", on_click=self._on_use).mark("model-ref-use")
                stamp_requires(use, LevelMode.EDIT)
        self._dialog = dialog
        self._show_current()
        dialog.open()

    def _choose(self, ref: ModelRef) -> None:
        """Make *ref* the choice shown at the top; nothing is stored until **Use**."""
        self._draft = ref
        self._show_current()

    def _show_current(self) -> None:
        box = self._current
        if box is None or box.is_deleted:
            return
        ref = self._draft
        state, resolved = self._state_of(ref)
        icon, colour, headline = _STATE_LOOK[state]
        box.clear()
        with box:
            with ui.row().classes("w-full flex-nowrap items-center gap-2"):
                ui.icon(icon, size="sm").classes(f"hw-use-props-color {colour}")
                ui.label(self._name_of(ref)).classes("text-sm font-medium truncate flex-1 min-w-0").mark(
                    "model-ref-current-name"
                )
                if not ref.is_empty:
                    hui.icon_action(
                        hui.icon.close, tooltip="No model", on_click=lambda: self._choose(ModelRef.empty())
                    ).mark("model-ref-clear")
            hui.hint(headline).mark("model-ref-current-state")
            if ref.is_catalog:
                hui.info_row("Catalog", ref.catalog or "", copy_value=ref.catalog or "")
            elif ref.source:
                hui.info_row("Address", ref.source, copy_value=ref.source)
            if ref.sha256:
                hui.info_row("sha256", f"{ref.sha256[:12]}…", copy_value=ref.sha256)
            elif ref.is_file:
                hui.info_row("sha256", "not pinned — pinned on Use when the file is here", copyable=False)
            if resolved is not None:
                hui.info_row(
                    "Here",
                    f"{_variant(resolved)}, {_size_text(resolved.size)} ({_where(resolved)})",
                    copyable=False,
                )

    async def _on_use(self) -> None:
        ref = self._draft
        if ref.is_file and not ref.sha256:
            ref = await self._pinned_if_known(ref) or ref
        if self._dialog is not None:
            self._dialog.close()
        self._write(ref)

    # ---- catalog tab ----------------------------------------------------

    def _build_catalog_tab(self) -> None:
        search = hui.input_field(placeholder="Search…", clearable=True).mark("model-ref-catalog-search")
        holder = ui.column().classes("w-full gap-0").mark("model-ref-catalog-list")
        entries = [e for e in consumer.models_state().catalog.entries() if entry_matches(e, self._filter)]
        entries.sort(key=lambda e: (e.class_library.label.lower(), e.name.lower()))
        rows = [(e, self._entry_detail(e)) for e in entries]

        def draw() -> None:
            needle = str(search.value or "").strip().lower()
            holder.clear()
            with holder, ui.scroll_area().classes("w-full h-64"):
                library = None
                shown = 0
                for entry, detail in rows:
                    if needle and needle not in entry.name.lower() and needle not in detail.lower():
                        continue
                    if entry.class_library.label != library:
                        library = entry.class_library.label
                        hui.section_label(library)
                    key = entry.class_identity.registry_key
                    hui.list_item(
                        entry.name, sublabel=detail, on_click=lambda k=key: self._choose(ModelRef(catalog=k))
                    ).mark("model-ref-catalog-pick")
                    shown += 1
                if not shown:
                    hui.hint("No catalog entry fits this port" if not rows else "No match")

        search.on_value_change(lambda _e: draw())
        draw()

    def _entry_detail(self, entry: CatalogEntry) -> str:
        """The variant used here (or the preferred one), its state and size."""
        key = entry.class_identity.registry_key
        try:
            resolved = self._resolve(ModelRef(catalog=key))
        except ModelMissing:
            ranked = candidates(entry.resources, self._preference())
            if not ranked:
                return "no variant fits"
            resource = ranked[0][1]
            return f"{resource.variant_name()} · not downloaded · {_size_text(resource.total_size)}"
        return f"{_variant(resolved)} · {_where(resolved)} · {_size_text(resolved.size)}"

    # ---- list tabs (Models Volume, Hugging Face) -------------------------

    def _build_list_tab(
        self,
        mark: str,
        scan: Callable[[], list[_Row] | None],
        on_pick: Callable[[_Row], Any],
    ) -> None:
        search = hui.input_field(placeholder="Search…", clearable=True).mark(f"{mark}-search")
        holder = ui.column().classes("w-full gap-0").mark(f"{mark}-list")
        with holder:
            hui.hint("Scanning…")
        background_tasks.create(_fill_list(scan, holder, search, mark, on_pick), name=f"{mark}-scan")

    def _file_rows(self) -> list[_Row] | None:
        root = _location(MODELS_VOLUME)
        return _models_folder_rows(root) if root is not None else []

    def _hf_rows(self) -> list[_Row] | None:
        root = _location(HF_VOLUME)
        return _hf_model_rows(root) if root is not None else []

    async def _on_file_chosen(self, row: _Row) -> None:
        """Choose a Models-folder file by its digest, hashing it first when the index does not know it."""
        path = row.path
        index = consumer.models_state().index
        sha = index.sha256_at(path)
        if sha is None:
            sha = await run.io_bound(_sha256_of, path)
            if sha is None:  # the app is shutting down
                return
            index.add(path, sha, None)
        self._choose(ModelRef(sha256=sha, size=row.size, label=path.name))

    def _on_hf_chosen(self, row: _Row) -> None:
        """Choose a cached Hugging Face file by its ``hf://`` address and the digest its blob is named by."""
        sha = row.path.name if _SHA256.fullmatch(row.path.name) else None
        self._choose(ModelRef(urls=(row.uri or "",), sha256=sha, size=row.size, label=Path(row.label).name))

    # ---- address tab ----------------------------------------------------

    def _build_address_tab(self, current: ModelRef) -> None:
        uri = (
            hui.input_field(placeholder="hf://org/repo/file or https://…")
            .classes("w-full")
            .mark("model-ref-uri")
        )
        if current.source:
            uri.value = current.source
        note = hui.hint("Press Enter to take the address.").mark("model-ref-uri-note")

        async def take() -> None:
            text = str(uri.value or "").strip()
            if not text:
                return
            if not text.startswith(_SCHEMES):
                note.text = "An address starts with hf:// or https://"
                return
            ref = ModelRef(urls=(text,))
            if self._draft.source == text and self._draft.sha256:
                return
            self._choose(ref)
            if not text.startswith("hf://"):
                note.text = "Pinned on Use once the file is on this machine."
                return
            note.text = "Asking the Hub for the digest…"
            answer = await run.io_bound(hf.remote_sha256, text)
            # Pin only the choice this lookup was for; the user may have moved on.
            if answer is not None and self._draft == ref:
                self._choose(ref.pinned(*answer))
                note.text = "Pinned from the Hub."
            elif self._draft == ref:
                note.text = "The Hub did not answer; pinned on Use once the file is on this machine."

        uri.on("keydown.enter", lambda _e: take())


@dataclass(frozen=True)
class _Row:
    """One pickable file: what the list shows, where the file is, and its address if any."""

    label: str
    path: Path
    size: int
    uri: str | None = None


async def _fill_list(
    scan: Callable[[], list[_Row] | None],
    holder: ui.column,
    search: ui.input,
    mark: str,
    on_pick: Callable[[_Row], Any],
) -> None:
    """Scan off the UI thread, then list the rows under *holder*, filtered by *search*."""
    rows = await run.io_bound(scan)
    if rows is None or holder.is_deleted:  # shutting down, or the dialog went away
        return

    def draw() -> None:
        needle = str(search.value or "").strip().lower()
        shown = [r for r in rows if needle in r.label.lower()]
        holder.clear()
        with holder, ui.scroll_area().classes("w-full h-64"):
            if not shown:
                hui.hint("No model files" if not rows else "No match")
            for row in shown[:_ROW_LIMIT]:
                hui.list_item(
                    row.label, sublabel=_size_text(row.size), on_click=lambda r=row: on_pick(r)
                ).mark(f"{mark}-pick")
            if len(shown) > _ROW_LIMIT:
                hui.hint(f"{len(shown) - _ROW_LIMIT} more — narrow the search")

    search.on_value_change(lambda _e: draw())
    draw()


def _models_folder_rows(root: Path) -> list[_Row]:
    """Return every file in the Models volume (dot names skipped), as relative paths, ordered by label."""
    rows: list[_Row] = []
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if not d.startswith(".")]
        for name in filenames:
            if name.startswith(".") or name.endswith(".part"):
                continue
            path = Path(dirpath) / name
            try:
                size = path.stat().st_size
            except OSError:
                continue
            rows.append(_Row(path.relative_to(root).as_posix(), path, size))
    rows.sort(key=lambda r: (r.label.lower(), r.label))
    return rows


def _hf_model_rows(cache_dir: Path) -> list[_Row]:
    """Return the model files in the HF cache, one row per ``(repo, path)``, ordered by label.

    Only files with a model suffix (``.safetensors``, ``.pth``, ``.pt``, ``.ckpt``, ``.onnx``,
    ``.bin``, ``.gguf``, any case) are listed. When a path is cached at several revisions, the
    revision ``refs/main`` points to wins; otherwise the one whose blob is newest. The address
    omits ``@revision`` for ``main``. A row's ``path`` is the blob, named by its digest.
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
        rows.append(
            _Row(
                f"{file.repo_id}/{file.path_in_repo}",
                file.blob_path,
                file.size,
                f"hf://{file.repo_id}/{file.path_in_repo}{suffix}",
            )
        )
    rows.sort(key=lambda r: (r.label.lower(), r.label))
    return rows


def _main_revision(cache_dir: Path, repo_id: str) -> str | None:
    ref = cache_dir / ("models--" + repo_id.replace("/", "--")) / "refs" / "main"
    try:
        return ref.read_text().strip() or None
    except OSError:
        return None


def _tab_for(ref: ModelRef) -> str:
    """The tab that shows *ref*'s kind of reference; Catalog for none."""
    if ref.is_catalog or ref.is_empty:
        return _TAB_CATALOG
    source = ref.source or ""
    if source.startswith("hf://"):
        return _TAB_HF
    if source:
        return _TAB_ADDRESS
    return _TAB_FILES


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
