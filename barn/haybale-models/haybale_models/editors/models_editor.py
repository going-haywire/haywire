"""ModelsEditor — the model files on this machine and where they come from.

A **Needed** section lists what the open graphs lack; below it the **Catalog** (every resource
of every installed catalog entry, with its status), **Local** (files in the models volume that
no catalog resource claims) and the **Hugging Face cache**, which lists only files a catalog
entry or an open graph refers to. A catalog row removes its own files from whichever volume
holds them. Download, cancel, remove and *Fetch all* need admin access and are re-checked at
click time.
"""

from __future__ import annotations

import logging
import threading
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path, PurePosixPath
from typing import TYPE_CHECKING, Any
from urllib.parse import urlparse

from haywire.core.access import AccessTier
from haywire.core.session.handlers import react_on
from haywire.core.volumes import VolumeError, location_of
from haywire.ui import elements as hui
from haywire.ui.elements.flyout import MENU_CARD_CLASS
from haywire.ui.hover_tip import set_hover_tip
from haywire.ui.editor.base import BaseEditor
from haywire.ui.editor.decorator import editor
from haywire.ui.editor.identity import SlotName
from haywire.ui.modals import confirm_modal
from huggingface_hub.utils import filter_repo_objects
from nicegui import core, ui

from haybale_graph_editor.notices import GraphNoticesChanged
from haybale_graph_editor.states.graph_app_state import GraphAppState
from haybale_models.consumer import preference_for
from haybale_models.describe import (
    entry_description,
    entry_search_text,
    entry_summary,
    search_matches,
)
from haybale_models.download import DownloadJob
from haybale_models.editors.assisted_dialog import assisted_slots, open_assisted_dialog
from haybale_models.filters import FILTER_FIELDS, entry_facts, row_matches, values_on_offer
from haybale_models.hf import HfCachedFile, is_whole_repo, list_cache, parse_hf, parse_hf_repo
from haybale_models.keys import HF_VOLUME, MODELS_VOLUME
from haybale_models.needs import NeededModel, format_size, iter_model_refs, job_matches
from haybale_models.resolver import (
    FetchSpec,
    ModelMissing,
    addresses_of,
    files_of,
    locate_resource,
    place_of,
    resolve,
    unserved_cache,
)
from haybale_models.signals import ModelsChanged
from haybale_models.sources import ModelSource, SourceSet
from haybale_models.sources.https import HttpsSource
from haybale_models.states.models_state import ModelsState
from haybale_models.status import resource_status
from haybale_models.store.index import IndexRecord

if TYPE_CHECKING:
    from haywire.core.catalog import CatalogEntry, Resource
    from haywire.core.session.context import SessionContext
    from haywire.ui.editor.wrapper import EditorWrapper
    from nicegui.element import Element

logger = logging.getLogger(__name__)

NOT_USED = "not used by an open graph"


@dataclass
class _Removal:
    """What a Remove click deletes: Models-volume files by digest, and files in cache volumes."""

    label: str
    shas: set[str] = field(default_factory=set)
    """Digests of the Models-volume files."""
    cache_paths: tuple[Path, ...] = ()
    """Files in cache volumes (framework caches and the Hugging Face cache)."""


@dataclass
class _Located:
    """One catalog resource with where it was found, computed once per draw."""

    entry: CatalogEntry
    resource: Resource
    found: tuple[dict[str, Path], str, str, int] | None
    place: str | None
    """The ``ModelSource.place`` of the found files; ``None`` when not found."""

    @property
    def local(self) -> bool:
        return self.place == "local"


@dataclass(frozen=True)
class _CacheFile:
    """A file in a cache volume, checked to resolve inside it."""

    source: ModelSource
    root: Path
    """The volume root, resolved."""
    path: Path
    """The path as found (a Hugging Face snapshot file is a link to its blob)."""
    relative: str
    """Posix path inside the volume, as a fetch record keeps it."""


_LiveText = Callable[[dict[str, DownloadJob], dict[Path, float]], str]

# The "Show:" toggles: (key, icon, Quasar colour when on, tooltip).
_SHOW_CATALOG = "catalog"
_SHOW_MODELS = "models"
_SHOW_HF = "hf"
_SHOW_TOGGLES = (
    (_SHOW_CATALOG, "menu_book", "blue", "Catalog"),
    (_SHOW_MODELS, "folder", "green", "Models"),
    (_SHOW_HF, "hub", "orange", "Huggingface"),
)
_SHOW_COLOUR = {key: colour for key, _icon, colour, _tip in _SHOW_TOGGLES}


def _variant_title(entry: CatalogEntry, resource: Resource | None) -> str:
    """Return the entry's name with what tells its variants apart: scale and precision, when known."""
    parts = [entry.name]
    if entry.scale:
        parts.append(f"{entry.scale}x")
    if resource is not None and resource.precision:
        parts.append(resource.precision)
    return " · ".join(parts)


def _format_of(resource: Resource) -> str:
    """Return the file format of a variant (``onnx``, ``pth``), else its platform."""
    return resource.type or resource.platform or resource.variant_name()


def _status_hint(status: str) -> ui.label:
    """Draw a row's status; a long error is cut, with the whole text as its tooltip."""
    label = hui.hint(status).classes("truncate min-w-0 max-w-[50%]")
    if status.startswith("failed"):
        label.tooltip(status)
    return label


def _files_summary(count: int, size: int) -> str:
    """Return the section-header summary "N file(s), SIZE"."""
    return f"{count} {'file' if count == 1 else 'files'}, {format_size(size)}"


def _in_cache_volume(sources: SourceSet, path: Path) -> bool:
    """Whether a model source other than the Models volume's holds *path*."""
    held = sources.holding(path)
    return held is not None and held.place != "local"


def _stoppable(jobs: list[DownloadJob]) -> list[DownloadJob]:
    """The active jobs Cancel can stop now: queued ones, and running ones whose source stops."""
    return [j for j in jobs if j.state == "queued" or (j.state == "running" and j.cancellable)]


def _dot(section: str) -> None:
    """Draw the coloured dot that marks a row as belonging to *section*, in its toggle's colour."""
    ui.element("div").classes(f"w-2 h-2 rounded-full bg-{_SHOW_COLOUR[section]}-500 flex-shrink-0").mark(
        f"models-dot-{section}"
    )


@editor(
    label="Models",
    icon=hui.icon.models,
    default_slot=SlotName.ACTION,
    requires=AccessTier.VIEW,
    description="Model files on this machine and where they come from",
)
class ModelsEditor(BaseEditor):
    """Lists the model catalog, the files in the Models volume and the Hugging Face files in use.

    The **Filters** icon in the header opens the filter section. Its **Show:** row picks the sections
    (**Catalog**, **Models**, **Huggingface**). Its search toggle opens a field that narrows every
    section: each word must appear, in any order, and scale, licence and `commercial` count too. Its
    **+** adds a filter on library, purpose, tags, architecture, scale, commercial use or status, which
    narrows the catalog. Closing it switches them all off, so a closed section always means the full
    list, and reopening it brings them back.
    The **Needed** section is always shown: per open graph, the models it lacks; **Fetch all**
    downloads them. Each section header counts what the section lists; hover it for the whole
    volume's size.

    A catalog row reads `non-commercial` unless its author states the model may be used commercially.
    Each catalog resource shows its status: `local`, `HF cache`, `downloading`, `failed` or
    `not downloaded`. **Models** lists the files in the Models volume that no catalog entry
    occupies. **Huggingface** lists the cached files that catalog entries or open graphs use,
    and what uses each; the Volumes editor shows where the cache lives. Download, Cancel and
    Remove need admin access; a removal names the open graphs that use the file and the bytes
    it frees. Cancel is offered only while a download can still be stopped: a Hugging Face
    download, once started, runs to the end. Opening the editor and **Rescan** index the Models
    volume on a background thread.
    """

    def __init__(self, wrapper: EditorWrapper) -> None:
        super().__init__(wrapper)
        self._scan_thread: threading.Thread | None = None
        self._hf_rows: list[HfCachedFile] | None = None
        self._hf_thread: threading.Thread | None = None
        self._hf_again = False
        self._hf_seen: frozenset[str] = frozenset()
        self._started = False
        self._structure: tuple[Any, ...] | None = None
        self._live: list[tuple[ui.label, _LiveText]] = []
        self._scroll_top = 0.0
        self._show = {_SHOW_CATALOG: True, _SHOW_MODELS: True, _SHOW_HF: True}
        self._filters_open = False
        self._selected: dict[str, set[str]] = {}
        self._offered: dict[str, list[str]] = {}
        self._filter_host: ui.column | None = None
        self._fields_slot: ui.column | None = None
        self._added: list[str] = []
        self._selects: dict[str, ui.select] | None = None
        self._search_on = False
        self._query = ""
        self._list: ui.column | None = None
        self._search_slot: ui.column | None = None

    @react_on(ModelsChanged, GraphNoticesChanged)
    def _on_models_changed(self, ctx: SessionContext, signal: object) -> None:
        """Redraw on a structural change; a download progress tick only rewrites the status labels."""
        if not self._started or not isinstance(signal, ModelsChanged):
            self.wrapper.redraw()
            return
        models = ctx.app_data[ModelsState]
        finished = self._finished_hf_jobs(models)
        if finished != self._hf_seen:
            self._hf_seen = finished
            self._refresh_hf(models)
        if self._structure_of(ctx, models) != self._structure:
            self.wrapper.redraw()
            return
        by_id = {j.id: j for j in models.queue.jobs()}
        pending = models.index.pending()
        for label, text_of in self._live:
            if not label.is_deleted:
                label.set_text(text_of(by_id, pending))

    def _structure_of(self, context: SessionContext, models: ModelsState) -> tuple[Any, ...]:
        """Return what decides the rows of a draw; a progress tick leaves it unchanged."""
        return (
            context.can_access(AccessTier.ADMIN),
            tuple((j.id, j.state, j.cancellable) for j in models.queue.jobs()),
            frozenset(r.sha256 for r in models.index.records()),
            frozenset(models.records.all()),
            tuple((e.library.name, e.name) for e in models.catalog.entries()),
            tuple(
                sorted(
                    (
                        b,
                        self._graph_name(context, b),
                        tuple(m.spec.identity for m in r.missing),
                        r.total_bytes,
                    )
                    for b, r in models.needed_reports().items()
                )
            ),
            frozenset(models.index.pending()),
            self._finished_hf_jobs(models),
            models.index.problem,
        )

    @staticmethod
    def _graph_name(context: SessionContext, binding_id: str) -> str:
        container = context.app_data[GraphAppState].get(binding_id)
        return container.display_name if container is not None else ""

    def _live_status(self, label: ui.label, text_of: _LiveText) -> ui.label:
        """Register *label* to be rewritten by progress ticks, and return it."""
        self._live.append((label, text_of))
        return label

    def _on_scroll(self, e: Any) -> None:
        self._scroll_top = float(e.vertical_position)

    @staticmethod
    def _finished_hf_jobs(models: ModelsState) -> frozenset[str]:
        """Return the ids of the finished downloads into the Hugging Face cache."""
        return frozenset(
            j.id
            for j in models.queue.jobs()
            if j.state == "done" and any(s.startswith("hf://") for s in j.sources)
        )

    # -- scan -----------------------------------------------------------------

    def _start_scan(self, models: ModelsState) -> None:
        """Index the models volume and read the HF cache on a daemon thread; one at a time."""
        thread = self._scan_thread
        if thread is not None and thread.is_alive():
            return
        hf_root = models.hf_cache
        self._hf_seen = self._finished_hf_jobs(models)

        def run() -> None:
            try:
                models.index.scan()
                models.index.hash_pending()
                self._hf_rows = list_cache(hf_root) if hf_root is not None else []
            except Exception:
                logger.exception("model scan failed")
                self._hf_rows = self._hf_rows or []
            finally:
                self._request_redraw()

        self._scan_thread = threading.Thread(target=run, name="models-editor-scan", daemon=True)
        self._scan_thread.start()

    def _refresh_hf(self, models: ModelsState) -> None:
        """Re-read the HF cache on a daemon thread; a request during a read schedules one more read."""
        thread = self._hf_thread
        if thread is not None and thread.is_alive():
            self._hf_again = True
            return
        hf_root = models.hf_cache
        self._hf_again = False

        def run() -> None:
            try:
                self._hf_rows = list_cache(hf_root) if hf_root is not None else []
            except Exception:
                logger.exception("HF cache read failed")
            finally:
                self._request_redraw()
                if self._hf_again:
                    self._refresh_hf(models)

        self._hf_thread = threading.Thread(target=run, name="models-editor-hf", daemon=True)
        self._hf_thread.start()

    def _request_redraw(self) -> None:
        loop = core.loop
        if loop is None or not loop.is_running():
            return
        try:
            loop.call_soon_threadsafe(self.wrapper.redraw)
        except RuntimeError:
            logger.debug("loop closed before the models redraw", exc_info=True)

    # -- draw -------------------------------------------------------------------

    def draw(self, context: SessionContext, container: Element) -> None:
        models = context.app_data[ModelsState]
        if not self._started:
            self._started = True
            self._start_scan(models)
        self._structure = self._structure_of(context, models)
        with container:
            with ui.column().classes("w-full h-full gap-0"):
                with hui.slot_header("Models", icon=hui.icon.models):
                    hui.icon_action(
                        hui.icon.refresh, tooltip="Rescan", on_click=lambda: self._rescan(models)
                    ).mark("models-rescan")
                    with (
                        ui.button()
                        .props("flat round dense size=sm")
                        .tooltip("Filters")
                        .mark("models-filters") as filters_btn
                    ):
                        filters_icon = ui.icon(hui.icon.filter).classes("hw-use-props-color")
                        filters_icon.props(f"color={'blue' if self._filters_open else 'grey'}")
                    filters_btn.on("click", lambda ie=filters_icon: self._toggle_filters(context, ie))
                self._filter_host = ui.column().classes("w-full gap-0 flex-shrink-0")
                self._draw_filter_section(context)
                with (
                    ui.scroll_area(on_scroll=self._on_scroll)
                    .classes("flex-1 w-full")
                    .props('content-style="width: 100%" content-active-style="width: 100%"') as area
                ):
                    self._list = ui.column().classes("w-full gap-0 p-1")
                    self._draw_list(context)
                if self._scroll_top > 0:
                    area.scroll_to(pixels=self._scroll_top)

    def _draw_list(self, context: SessionContext) -> None:
        """(Re)draw the sections below the filter row, as the toggles and the search ask."""
        box = self._list
        if box is None or box.is_deleted:
            return
        models = context.app_data[ModelsState]
        self._live = []
        admin = context.can_access(AccessTier.ADMIN)
        graphs = context.app_data[GraphAppState]
        jobs = models.queue.jobs()
        records = models.index.records()
        query = self._query.strip().lower() if self._filters_open and self._search_on else ""
        box.clear()
        with box:
            self._draw_needed(context, models, graphs, jobs, admin)
            claimed, shown = self._draw_catalog(
                context, models, jobs, admin, visible=self._shows(_SHOW_CATALOG), query=query
            )
            self._draw_downloads(context, models, jobs, shown, admin, query=query)
            if self._shows(_SHOW_MODELS):
                self._draw_local(context, models, records, claimed, admin, query=query)
            if self._shows(_SHOW_HF):
                self._draw_hf(models, graphs, query=query)
        self._sync_fields(context)

    # -- filter row -------------------------------------------------------------

    def _shows(self, section: str) -> bool:
        """Return whether *section* is drawn: always while the filter section is closed."""
        return not self._filters_open or self._show[section]

    def _toggle_filters(self, context: SessionContext, icon_el: ui.icon) -> None:
        """Open or close the filter section; while closed its settings stay but do not apply."""
        self._filters_open = not self._filters_open
        icon_el.props(f"color={'blue' if self._filters_open else 'grey'}")
        self._draw_filter_section(context)
        self._draw_list(context)

    def _draw_filter_section(self, context: SessionContext) -> None:
        """Draw the filter section into its host while it is open."""
        host = self._filter_host
        if host is None or host.is_deleted:
            return
        host.clear()
        self._search_slot = None
        self._fields_slot = None
        self._selects = None
        if self._filters_open:
            with host:
                self._draw_filter_row(context)

    def _sync_fields(self, context: SessionContext) -> None:
        """Bring the filter fields up to date, keeping their selects so an open dropdown stays open."""
        if self._fields_slot is None or self._fields_slot.is_deleted:
            return
        if self._selects is None or list(self._selects) != self._added:
            self._draw_fields(context)
            return
        for key, select in self._selects.items():
            values = self._offered.get(key, [])
            if select.options != values:
                select.set_options(values, value=self._selected_values(key))

    def _selected_values(self, key: str) -> list[str]:
        chosen = self._selected.get(key, set())
        return [value for value in self._offered.get(key, []) if value in chosen]

    def _draw_fields(self, context: SessionContext) -> None:
        """Draw a row per added field, then the button that adds another."""
        slot = self._fields_slot
        if slot is None or slot.is_deleted:
            return
        slot.clear()
        self._selects = {}
        labels = dict(FILTER_FIELDS)
        with slot:
            for key in self._added:
                with ui.row().classes("w-full items-center no-wrap gap-1"):
                    hui.hint(labels[key]).classes("w-20 flex-shrink-0 truncate")
                    self._selects[key] = (
                        hui.select_field(
                            options=self._offered.get(key, []),
                            value=self._selected_values(key),
                            multiple=True,
                            with_input=True,
                            min_width="0",
                            on_change=lambda e, k=key: self._on_field(context, k, e.value),
                        )
                        .props("use-chips")
                        .classes("flex-1 min-w-0")
                        .mark(f"models-select-{key}")
                    )
                    hui.icon_action(
                        hui.icon.close,
                        tooltip="Remove this filter",
                        on_click=lambda k=key: self._remove_field(context, k),
                    ).mark(f"models-filter-remove-{key}")
            unused = [(key, label) for key, label in FILTER_FIELDS if key not in self._added]
            if unused:
                with hui.icon_action(hui.icon.add, tooltip="Add a filter").mark("models-filter-add"):
                    menu = ui.menu().classes(MENU_CARD_CLASS)

                    def close_menu() -> None:
                        # Adding a field redraws this row's slot, which deletes the menu first.
                        if not menu.is_deleted:
                            menu.close()

                    with menu, hui.open_flyout_group(dismiss=close_menu):
                        for key, label in unused:
                            hui.menu_row(label, on_click=lambda k=key: self._add_field(context, k)).mark(
                                f"models-filter-add-{key}"
                            )

    def _add_field(self, context: SessionContext, key: str) -> None:
        self._added.append(key)
        self._draw_fields(context)

    def _remove_field(self, context: SessionContext, key: str) -> None:
        self._added.remove(key)
        self._selected.pop(key, None)
        self._draw_fields(context)
        self._draw_list(context)

    def _on_field(self, context: SessionContext, key: str, values: list[str] | None) -> None:
        chosen = set(values or [])
        if chosen != self._selected.get(key, set()):
            self._selected[key] = chosen
            self._draw_list(context)

    def _draw_filter_row(self, context: SessionContext) -> None:
        """Draw the "Show:" toggles and the search toggle, with the search field below when it is on."""
        with (
            ui.column()
            .classes("w-full px-2 py-1.5 gap-1 flex-shrink-0")
            .style("border-bottom: 1px solid var(--hw-border);")
            .mark("models-filter")
        ):
            with ui.row().classes("items-center gap-0.5 w-full"):
                hui.hint("Show:").classes("mr-1")
                for key, icon, colour, tip in _SHOW_TOGGLES:
                    self._make_toggle(context, key, icon, colour, tip)
                with (
                    ui.button()
                    .props("flat round dense size=xs")
                    .tooltip("Search")
                    .mark("models-filter-search") as btn
                ):
                    search_icon = ui.icon("search").classes("hw-use-props-color")
                    search_icon.props(f"color={'blue' if self._search_on else 'grey'}")
                btn.on("click", lambda ie=search_icon: self._toggle_search(context, ie))
            self._search_slot = ui.column().classes("w-full gap-0")
            self._draw_search_field(context)
            self._fields_slot = (
                ui.column().classes("w-full gap-0.5 max-h-40 overflow-y-auto").mark("models-filter-fields")
            )

    def _make_toggle(self, context: SessionContext, key: str, icon: str, colour: str, tip: str) -> None:
        with ui.button().props("flat round dense size=xs").tooltip(tip).mark(f"models-filter-{key}") as btn:
            icon_el = ui.icon(icon).classes("hw-use-props-color")
            icon_el.props(f"color={colour if self._show[key] else 'grey'}")

        def toggle() -> None:
            self._show[key] = not self._show[key]
            icon_el.props(f"color={colour if self._show[key] else 'grey'}")
            self._draw_list(context)

        btn.on("click", lambda: toggle())

    def _toggle_search(self, context: SessionContext, icon_el: ui.icon) -> None:
        self._search_on = not self._search_on
        icon_el.props(f"color={'blue' if self._search_on else 'grey'}")
        if not self._search_on:
            # Hiding the search clears it, so a hidden query never narrows the list.
            self._query = ""
            self._draw_list(context)
        self._draw_search_field(context)

    def _draw_search_field(self, context: SessionContext) -> None:
        slot = self._search_slot
        if slot is None or slot.is_deleted:
            return
        slot.clear()
        if not self._search_on:
            return
        with slot:
            field = hui.input_field(
                placeholder="Search models…", value=self._query, clearable=True, autofocus=True
            ).mark("models-search")

            def changed(e: Any) -> None:
                self._query = str(e.value or "")
                self._draw_list(context)

            field.on_value_change(changed)

    def _draw_needed(
        self,
        context: SessionContext,
        models: ModelsState,
        graphs: GraphAppState,
        jobs: list[DownloadJob],
        admin: bool,
    ) -> None:
        """Draw each open graph that misses models: a header line, then one line per missing model."""
        rows = []
        for binding_id, report in models.needed_reports().items():
            container = graphs.get(binding_id)
            if container is not None and report.missing:
                rows.append((binding_id, container.display_name, report))
        if not rows:
            return
        hui.section_label("Needed")
        for _binding_id, name, report in sorted(rows, key=lambda r: r[1].lower()):
            n = len(report.missing)
            size = format_size(report.total_bytes)
            if report.unknown_size:
                size += f", {report.unknown_size} of unknown size"
            with ui.column().classes("w-full gap-0 pb-1").mark("models-needed-row"):
                with ui.row().classes("w-full items-center no-wrap gap-2 px-2 py-1"):
                    hui.subject(name).classes("truncate flex-1 min-w-0").tooltip(name)
                    hui.hint(f"{n} {'model' if n == 1 else 'models'}, {size}").classes("flex-shrink-0")
                    if admin:
                        hui.button(
                            "Fetch all",
                            icon=hui.icon.download,
                            on_click=lambda r=report: self._fetch_all(context, models, r.missing),
                        ).classes("w-auto").mark("models-needed-fetch")
                for needed in report.missing:
                    self._draw_needed_model(context, models, jobs, needed, admin)

    def _draw_needed_model(
        self,
        context: SessionContext,
        models: ModelsState,
        jobs: list[DownloadJob],
        needed: NeededModel,
        admin: bool,
    ) -> None:
        """Draw one compact line for a missing model: label, variant and size, status, action."""
        spec = needed.spec
        source = (spec.ref.source if spec.ref is not None else None) or ""
        if spec.entry is not None:
            label = _variant_title(spec.entry, spec.resource)
            variant = _format_of(spec.resource) if spec.resource is not None else ""
            address = None
        else:
            label = needed.label if needed.label and needed.label != source else ""
            sha = (spec.ref.sha256 or "")[:12] if spec.ref else ""
            label = label or (self._basename(source) if source else sha)
            variant = ""
            address = source or None
        size = format_size(needed.size) if needed.size is not None else "—"
        matching = [j for j in jobs if job_matches(j, spec)]
        active = [j for j in matching if j.state in ("queued", "running")]
        if spec.entry is not None and spec.resource is not None:
            addresses = addresses_of(spec.resource)
        else:
            addresses = spec.ref.urls if spec.ref is not None else ()
        unavailable = models.sources.unavailable(addresses)
        if spec.resource is not None:
            unavailable = unserved_cache(spec.resource, models.sources) or unavailable
        with (
            ui.row()
            .classes("w-full items-center no-wrap gap-2 pl-5 pr-2 rounded hw-list-item-hover")
            .mark("models-needed-model")
        ):
            hui.hint(label).classes("truncate flex-1 min-w-0").tooltip(address or label)
            hui.hint(f"{variant} · {size}" if variant else size).classes("flex-shrink-0")
            self._live_status(
                _status_hint(resource_status(None, matching, unavailable=unavailable)).mark(
                    "models-needed-status"
                ),
                self._job_status(None, [j.id for j in matching], unavailable),
            )
            if not admin:
                return
            if active:
                if stoppable := _stoppable(active):
                    hui.icon_action(
                        hui.icon.close,
                        tooltip="Cancel download",
                        on_click=lambda ids=[j.id for j in stoppable]: self._cancel(context, models, ids),
                    ).mark("models-needed-cancel")
            elif unavailable is None:
                hui.icon_action(
                    hui.icon.download,
                    tooltip="Download",
                    on_click=lambda: self._download(context, models, spec),
                ).mark("models-needed-download")
            if not active:
                self._assisted_action(context, models, matching, "models-needed-assisted")

    @staticmethod
    def _header(title: str, summary: str, total: str | None = None) -> None:
        """Draw a section header "TITLE — summary", with the whole volume's total as its tooltip."""
        label = hui.section_label(f"{title} — {summary}").mark(f"models-header-{title.lower()}")
        if total:
            label.tooltip(total)

    # -- catalog -----------------------------------------------------------------

    def _draw_catalog(
        self,
        context: SessionContext,
        models: ModelsState,
        jobs: list[DownloadJob],
        admin: bool,
        *,
        visible: bool = True,
        query: str = "",
    ) -> tuple[set[str], set[str]]:
        """Draw the Catalog section; returns the occupied digests and the job ids its rows show.

        The digests are collected even when the section is hidden, so the Models section still
        lists only the files no catalog entry occupies.
        """
        claimed: set[str] = set()
        shown: set[str] = set()
        by_library: dict[str, list[CatalogEntry]] = {}
        for entry in models.catalog.entries():
            by_library.setdefault(entry.library.label or entry.library.name, []).append(entry)
        needed = {m.spec.identity for r in models.needed_reports().values() for m in r.missing}
        candidates: list[tuple[str, _Located, dict[str, set[str]]]] = []
        for library in sorted(by_library, key=str.lower):
            rows: list[_Located] = []
            for entry in sorted(by_library[library], key=lambda e: e.name.lower()):
                for resource in entry.resources:
                    found = locate_resource(resource, models.index, models.sources)
                    place = None if found is None else place_of(found[0].values(), models.sources)
                    if found is not None:
                        claimed.update(sha for p in found[0].values() if (sha := models.index.sha256_at(p)))
                    identity = FetchSpec(entry=entry, resource=resource).identity
                    facts = entry_facts(entry, on_machine=found is not None, needed=identity in needed)
                    candidates.append((library, _Located(entry, resource, found, place), facts))
        self._offered = values_on_offer(facts for _library, _row, facts in candidates)
        # A value the catalog no longer offers has no chip to clear it with.
        self._selected = {
            key: chosen & set(self._offered[key])
            for key, chosen in self._selected.items()
            if key in self._offered
        }
        grouped: list[tuple[str, list[_Located]]] = []
        for library, row, facts in candidates:
            haystack = f"{library} {row.resource.variant_name()} {entry_search_text(row.entry)}".lower()
            if not search_matches(query, haystack) or (
                self._filters_open and not row_matches(facts, self._selected)
            ):
                continue
            if not grouped or grouped[-1][0] != library:
                grouped.append((library, []))
            grouped[-1][1].append(row)
        if not visible:
            return claimed, shown
        located = [row for _library, rows in grouped for row in rows]
        size = sum(r.resource.total_size or 0 for r in located)
        self._header("Catalog", _files_summary(len(located), size))
        for library, rows in grouped:
            hui.hint(library).classes("px-2 pt-1")
            for row in rows:
                shown.update(self._draw_catalog_row(context, models, jobs, row, admin))
        if not grouped:
            narrowed = query or any(self._selected.values())
            hui.hint("No match." if narrowed else "Nothing in the catalog.").classes("px-2")
        return claimed, shown

    @staticmethod
    def _basename(url: str) -> str:
        return PurePosixPath(urlparse(url).path).name or url

    @staticmethod
    def _shorten(text: str, limit: int = 48) -> str:
        return text if len(text) <= limit else text[: limit - 1] + "…"

    def _draw_downloads(
        self,
        context: SessionContext,
        models: ModelsState,
        jobs: list[DownloadJob],
        shown: set[str],
        admin: bool,
        *,
        query: str = "",
    ) -> None:
        """Draw the active and failed jobs that no catalog row shows."""
        rest = [
            j
            for j in jobs
            if j.state in ("queued", "running", "failed")
            and j.id not in shown
            and search_matches(query, f"{j.label} {' '.join(j.sources)}")
        ]
        if not rest:
            return
        hui.section_label("Downloads")
        for job in rest:
            source = job.sources[0] if job.sources else ""
            with (
                ui.row()
                .classes("w-full items-center no-wrap gap-2 px-2 py-1 rounded hw-list-item-hover")
                .mark("models-download-row")
            ):
                hui.subject(job.label or (self._basename(source) if source else job.id)).classes(
                    "truncate flex-1 min-w-0"
                )
                if source:
                    hui.hint(self._shorten(source)).classes("truncate flex-shrink-0 max-w-[12rem]").tooltip(
                        source
                    )
                self._live_status(
                    _status_hint(resource_status(None, [job])).mark("models-status"),
                    self._job_status(None, [job.id]),
                )
                if admin and _stoppable([job]):
                    hui.icon_action(
                        hui.icon.close,
                        tooltip="Cancel download",
                        on_click=lambda jid=job.id: self._cancel(context, models, [jid]),
                    ).mark("models-cancel")
                if admin and job.state == "failed":
                    self._assisted_action(context, models, [job], "models-download-assisted")

    @staticmethod
    def _indexing_status(path: Path, fraction: float) -> _LiveText:
        def text_of(_jobs: dict[str, DownloadJob], pending: dict[Path, float]) -> str:
            return f"indexing… {int(pending.get(path, fraction) * 100)} %"

        return text_of

    @staticmethod
    def _job_status(place: str | None, job_ids: list[str], unavailable: str | None = None) -> _LiveText:
        """Return a function giving the status text of a row from the current jobs."""

        def text_of(by_id: dict[str, DownloadJob], _pending: dict[Path, float]) -> str:
            return resource_status(place, [by_id[i] for i in job_ids if i in by_id], unavailable=unavailable)

        return text_of

    def _draw_catalog_row(
        self,
        context: SessionContext,
        models: ModelsState,
        jobs: list[DownloadJob],
        row: _Located,
        admin: bool,
    ) -> list[str]:
        """Draw one catalog resource row; returns the ids of the jobs it shows."""
        entry, resource = row.entry, row.resource
        spec = FetchSpec(entry=entry, resource=resource)
        local = row.found if row.local else None
        place = row.place
        matching = [j for j in jobs if job_matches(j, spec)]
        unavailable = unserved_cache(resource, models.sources) or models.sources.unavailable(
            addresses_of(resource)
        )
        status = resource_status(place, matching, unavailable=unavailable)
        size = resource.total_size
        with ui.column().classes("w-full gap-0 px-2 py-1 rounded hw-list-item-hover").mark("models-row"):
            with ui.row().classes("w-full items-center no-wrap gap-2"):
                _dot(_SHOW_CATALOG)
                title = _variant_title(entry, resource)
                subject = hui.subject(title).classes("truncate flex-1 min-w-0")
                set_hover_tip(
                    subject,
                    entry.name,
                    type_name=resource.variant_name(),
                    description=entry_description(entry),
                )
                if admin:
                    cached = (
                        () if row.found is None or row.local else tuple(files_of(row.found[0], resource))
                    )
                    self._catalog_actions(
                        context,
                        models,
                        entry,
                        resource,
                        spec,
                        local,
                        place,
                        matching,
                        unavailable,
                        cached,
                    )
            with ui.row().classes("w-full items-center no-wrap gap-1"):
                detail = f"{_format_of(resource)} · {format_size(size) if size is not None else '—'}"
                summary = entry_summary(entry, scale=False)
                hui.hint(" · ".join(p for p in (summary, detail, entry.license or "—") if p) + " ·").classes(
                    "truncate min-w-0"
                )
                if not entry.commercial:
                    # Its own element: a long summary before it must not cut it off.
                    hui.hint("non-commercial ·").classes("flex-shrink-0").mark("models-non-commercial")
                self._live_status(
                    _status_hint(status).mark("models-status"),
                    self._job_status(place, [j.id for j in matching], unavailable),
                )
        return [j.id for j in matching]

    def _catalog_actions(
        self,
        context: SessionContext,
        models: ModelsState,
        entry: CatalogEntry,
        resource: Resource,
        spec: FetchSpec,
        local: tuple[dict[str, Path], str, str, int] | None,
        place: str | None,
        matching: list[DownloadJob],
        unavailable: str | None,
        cached: tuple[Path, ...] = (),
    ) -> None:
        """Draw the Cancel, Download, Download in browser and Remove actions of a catalog row.

        No Download action is drawn when *unavailable* names a prefix no model source serves.
        A found row gets Remove wherever its files lie: the catalog entry entitles it. Files in
        the Models volume must each be indexed; files in cache volumes must resolve inside them.
        """
        active = [j for j in matching if j.state in ("queued", "running")]
        if active:
            if stoppable := _stoppable(active):
                hui.icon_action(
                    hui.icon.close,
                    tooltip="Cancel download",
                    on_click=lambda ids=[j.id for j in stoppable]: self._cancel(context, models, ids),
                ).mark("models-cancel")
        elif place is None:
            if unavailable is None:
                hui.icon_action(
                    hui.icon.download,
                    tooltip="Download",
                    on_click=lambda: self._download(context, models, spec),
                ).mark("models-download")
            self._assisted_action(context, models, matching, "models-assisted")
        if local is not None:
            shas = {sha for p in local[0].values() if (sha := models.index.sha256_at(p))}
            hui.icon_action(
                hui.icon.delete,
                tooltip="Remove",
                on_click=lambda: self._confirm_remove(
                    context, models, _Removal(_variant_title(entry, resource), shas)
                ),
            ).mark("models-remove")
            return
        in_cache = tuple(p for p in cached if _in_cache_volume(models.sources, p))
        in_models = [models.index.sha256_at(p) for p in cached if p not in in_cache]
        if not in_cache or not all(in_models) or self._cache_files(models, in_cache) is None:
            return
        removal = _Removal(
            _variant_title(entry, resource),
            {sha for sha in in_models if sha},
            cache_paths=in_cache,
        )
        hui.icon_action(
            hui.icon.delete,
            tooltip="Remove",
            on_click=lambda: self._confirm_remove(context, models, removal),
        ).mark("models-remove")

    def _assisted_action(
        self, context: SessionContext, models: ModelsState, jobs: list[DownloadJob], mark: str
    ) -> None:
        """Draw Download in browser when one of *jobs* can be finished that way."""
        slots = assisted_slots(models.queue, jobs)
        if slots:
            hui.icon_action(
                hui.icon.open_external,
                tooltip="Download in browser",
                on_click=lambda: self._open_assisted(context, models, slots),
            ).mark(mark)

    def _open_assisted(self, context: SessionContext, models: ModelsState, slots: list[DownloadJob]) -> None:
        client = ui.context.client
        if not context.can_access(AccessTier.ADMIN):
            self._refuse(client)
            return
        open_assisted_dialog(models, context.principal, slots)

    # -- local ---------------------------------------------------------------------

    def _draw_local(
        self,
        context: SessionContext,
        models: ModelsState,
        records: list[IndexRecord],
        claimed: set[str],
        admin: bool,
        *,
        query: str = "",
    ) -> None:
        loose = sorted(
            (
                r
                for r in records
                if r.sha256 not in claimed and search_matches(query, f"{r.relative} {r.source or ''}")
            ),
            key=lambda r: (r.relative.lower(), r.relative),
        )
        try:
            root: Path | None = location_of(MODELS_VOLUME)
        except VolumeError:
            root = None
        pending = models.index.pending() if root is not None else {}
        if models.index.problem:
            hui.error_label(models.index.problem)
        if query:
            pending = {p: f for p, f in pending.items() if search_matches(query, p.name)}
        count = len(loose) + len(pending)
        self._header(
            "Models",
            _files_summary(count, sum(r.size for r in loose)),
            f"Models volume: {format_size(sum(r.size for r in records))} in all",
        )
        if not loose and not pending:
            hui.hint("No match." if query else "No other files in the models volume.").classes("px-2")
        for rec in loose:
            with (
                ui.row()
                .classes("w-full items-center no-wrap gap-2 px-2 py-1 rounded hw-list-item-hover")
                .mark("models-row")
            ):
                _dot(_SHOW_MODELS)
                hui.subject(rec.relative).classes("truncate flex-1 min-w-0")
                hui.hint(format_size(rec.size)).classes("flex-shrink-0")
                hui.hint(rec.sha256[:12]).classes("font-mono flex-shrink-0")
                hui.hint(rec.source or "—").classes("truncate flex-shrink-0 max-w-[10rem]")
                if admin:
                    hui.icon_action(
                        hui.icon.delete,
                        tooltip="Remove",
                        on_click=lambda r=rec: self._confirm_remove(
                            context, models, _Removal(r.relative, {r.sha256})
                        ),
                    ).mark("models-remove")
        for path, fraction in pending.items():
            try:
                name = path.relative_to(root).as_posix() if root is not None else path.name
            except ValueError:
                name = path.name
            with ui.row().classes("w-full items-center no-wrap gap-2 px-2 py-1").mark("models-row"):
                _dot(_SHOW_MODELS)
                hui.subject(name).classes("truncate flex-1 min-w-0")
                self._live_status(
                    hui.hint(f"indexing… {int(fraction * 100)} %").classes("flex-shrink-0"),
                    self._indexing_status(path, fraction),
                )

    # -- HF cache -------------------------------------------------------------------

    def _hf_users(
        self, models: ModelsState, graphs: GraphAppState
    ) -> tuple[
        dict[tuple[str, str], tuple[set[str], set[str]]],
        dict[tuple[str, str, tuple[str, ...]], tuple[set[str], set[str]]],
    ]:
        """Map the ``hf://`` files and whole-repo uses in play to their catalog entries and open graphs.

        The first map is keyed ``(repo id, path)`` for file addresses; the second
        ``(repo id, commit, include)`` for whole-repo addresses. Repo ids are lower-cased.
        """
        users: dict[tuple[str, str], tuple[set[str], set[str]]] = {}
        repo_users: dict[tuple[str, str, tuple[str, ...]], tuple[set[str], set[str]]] = {}

        def add(
            url: str, include: tuple[str, ...], catalog_name: str | None, graph_name: str | None
        ) -> None:
            if not url.startswith("hf://"):
                return
            try:
                if is_whole_repo(url):
                    repo = parse_hf_repo(url)
                    names, graph_names = repo_users.setdefault(
                        (repo.repo_id.lower(), repo.commit, include), (set(), set())
                    )
                else:
                    uri = parse_hf(url)
                    names, graph_names = users.setdefault((uri.repo_id.lower(), uri.path), (set(), set()))
            except ValueError:
                return
            if catalog_name:
                names.add(catalog_name)
            if graph_name:
                graph_names.add(graph_name)

        def entry_urls(entry: CatalogEntry) -> list[tuple[str, tuple[str, ...]]]:
            urls: list[tuple[str, tuple[str, ...]]] = []
            for resource in entry.resources:
                urls.extend((u, resource.include) for u in resource.urls)
                for f in resource.files:
                    urls.extend((u, resource.include) for u in f.urls)
            return urls

        for entry in models.catalog.entries():
            for url, include in entry_urls(entry):
                add(url, include, entry.name, None)
        for container in graphs.all_containers():
            graph = container.editor.graph
            if graph is None:
                continue
            for _wrapper, _port_id, ref in iter_model_refs(graph):
                found = models.catalog.entry(ref.catalog) if ref.catalog else None
                for url, include in entry_urls(found) if found is not None else [(u, ()) for u in ref.urls]:
                    add(url, include, None, container.display_name)
        return users, repo_users

    def _draw_hf(self, models: ModelsState, graphs: GraphAppState, *, query: str = "") -> None:
        """Draw the cached Hugging Face files that a catalog entry or an open graph refers to."""
        root = models.hf_cache
        if root is None or not self._hf_rows:
            return
        users, repo_users = self._hf_users(models, graphs)

        def users_of(r: HfCachedFile) -> tuple[set[str], set[str]] | None:
            entries: set[str] = set()
            graph_names: set[str] = set()
            found = False
            if (hit := users.get((r.repo_id.lower(), r.path_in_repo))) is not None:
                found = True
                entries |= hit[0]
                graph_names |= hit[1]
            for (repo, commit, include), (e, g) in repo_users.items():
                if repo != r.repo_id.lower() or commit != r.revision:
                    continue
                if list(filter_repo_objects([r.path_in_repo], allow_patterns=list(include) or None)):
                    found = True
                    entries |= e
                    graph_names |= g
            return (entries, graph_names) if found else None

        rows = [
            (r, hit)
            for r in self._hf_rows
            if (hit := users_of(r)) is not None and search_matches(query, f"{r.repo_id}/{r.path_in_repo}")
        ]
        if not rows:
            return
        listed = sum(r.size for r, _u in rows)
        cache = format_size(sum(r.size for r in self._hf_rows))
        self._header(
            "Huggingface",
            _files_summary(len(rows), listed),
            f"Hugging Face cache: {cache} in all, shared with other tools",
        )
        with ui.row().classes("w-full items-center gap-2 px-2").mark("models-hf-section"):
            hui.hint("From Hugging Face chache.")
        for row, (entries, graph_names) in rows:
            used = "; ".join(
                part
                for part in (
                    f"catalog: {', '.join(sorted(entries, key=str.lower))}" if entries else "",
                    f"graph: {', '.join(sorted(graph_names, key=str.lower))}" if graph_names else "",
                )
                if part
            )
            with ui.column().classes("w-full gap-0 px-2 py-1").mark("models-hf-row"):
                with ui.row().classes("w-full items-center no-wrap gap-2"):
                    _dot(_SHOW_HF)
                    hui.subject(f"{row.repo_id}/{row.path_in_repo}").classes("truncate flex-1 min-w-0")
                    hui.hint(format_size(row.size)).classes("flex-shrink-0")
                hui.hint(used).classes("truncate").mark("models-hf-used")

    # -- actions ----------------------------------------------------------------------

    def _rescan(self, models: ModelsState) -> None:
        self._hf_rows = None
        self._start_scan(models)
        self.wrapper.redraw()

    @staticmethod
    def _refuse(client: Any) -> None:
        with client:
            ui.notify("This needs admin access.", type="warning")

    def _download(self, context: SessionContext, models: ModelsState, spec: FetchSpec) -> None:
        client = ui.context.client
        if not context.can_access(AccessTier.ADMIN):
            self._refuse(client)
            return
        models.fetch([spec], context.principal)

    def _fetch_all(self, context: SessionContext, models: ModelsState, missing: list[Any]) -> None:
        client = ui.context.client
        if not context.can_access(AccessTier.ADMIN):
            self._refuse(client)
            return
        models.fetch([m.spec for m in missing], context.principal)

    def _cancel(self, context: SessionContext, models: ModelsState, job_ids: list[str]) -> None:
        client = ui.context.client
        if not context.can_access(AccessTier.ADMIN):
            self._refuse(client)
            return
        refused = [job_id for job_id in job_ids if not models.queue.cancel(job_id)]
        if refused:
            with client:
                ui.notify("This download can no longer be stopped; it runs to the end.", type="warning")

    # -- remove -------------------------------------------------------------------------

    def _files_of(self, models: ModelsState, shas: set[str]) -> list[tuple[IndexRecord, Path]]:
        """The indexed files of *shas* that lie inside the models volume."""
        try:
            root = location_of(MODELS_VOLUME).resolve()
        except VolumeError:
            return []
        found: list[tuple[IndexRecord, Path]] = []
        for rec in models.index.records():
            if rec.sha256 not in shas:
                continue
            path = (root / rec.relative).resolve()
            if path.is_relative_to(root) and path != root:
                found.append((rec, path))
        return found

    @staticmethod
    def _cache_files(models: ModelsState, paths: tuple[Path, ...]) -> list[_CacheFile] | None:
        """The cache files of *paths*, or ``None`` unless every one lies inside a cache volume.

        A path counts when a source other than the Models volume's holds it, and both the path
        and what it resolves to lie inside that source's volume.
        """
        if not paths:
            return None
        files: list[_CacheFile] = []
        for path in paths:
            source = models.sources.holding(path)
            root = source.root() if source is not None and source.place != "local" else None
            if source is None or root is None:
                return None
            resolved, resolved_root = path.resolve(), root.resolve()
            if not resolved.is_relative_to(resolved_root) or resolved == resolved_root:
                return None
            if not (path.absolute().is_relative_to(root.absolute()) or path.is_relative_to(resolved_root)):
                return None
            try:
                relative = path.relative_to(root)
            except ValueError:
                relative = path.relative_to(resolved_root)
            files.append(_CacheFile(source, resolved_root, path, relative.as_posix()))
        return files

    def _using_graphs(
        self,
        context: SessionContext,
        models: ModelsState,
        shas: set[str],
        cache_paths: frozenset[Path] = frozenset(),
    ) -> list[str]:
        """Names of the open graphs referring to a file of *shas* or *cache_paths*."""
        names: list[str] = []
        for graph_container in context.app_data[GraphAppState].all_containers():
            graph = graph_container.editor.graph
            if graph is not None and self._graph_uses(models, graph, shas, cache_paths):
                names.append(graph_container.display_name)
        return names

    @staticmethod
    def _graph_uses(
        models: ModelsState, graph: Any, shas: set[str], cache_paths: frozenset[Path] = frozenset()
    ) -> bool:
        """Whether *graph* refers to a file of *shas* (by digest) or of *cache_paths* (by path)."""
        sources = models.sources if cache_paths else SourceSet([HttpsSource(models.index)])
        for wrapper, port_id, ref in iter_model_refs(graph):
            try:
                preference = preference_for(wrapper.node, port_id)
            except Exception:
                preference = [{}]
            try:
                found = resolve(
                    ref,
                    preference,
                    catalog=models.catalog,
                    index=models.index,
                    sources=sources,
                )
            except ModelMissing:
                continue
            if found.sha256 in shas or any(models.index.sha256_at(p) in shas for p in found.files.values()):
                return True
            files = files_of(found.files, found.resource) if found.resource else list(found.files.values())
            if cache_paths and any(p.resolve() in cache_paths for p in files):
                return True
        return False

    def _confirm_remove(self, context: SessionContext, models: ModelsState, removal: _Removal) -> None:
        client = ui.context.client
        if not context.can_access(AccessTier.ADMIN):
            self._refuse(client)
            return
        if removal.cache_paths:
            self._confirm_cache_remove(context, models, removal, client)
            return
        files = self._files_of(models, removal.shas)
        if not files:
            with client:
                ui.notify(
                    "Nothing to delete: no file of this model is in the models volume.", type="warning"
                )
            return
        freed = sum(rec.size for rec, _ in files)
        users = ", ".join(self._using_graphs(context, models, removal.shas)) or NOT_USED
        confirm_modal(
            title="Remove model file",
            message=f"Delete {removal.label} ({format_size(freed)})? Used by: {users}",
            confirm_label="Delete",
            danger=True,
            on_confirm=lambda: self._remove(context, models, removal, client),
        )

    def _confirm_cache_remove(
        self, context: SessionContext, models: ModelsState, removal: _Removal, client: Any
    ) -> None:
        files = self._cache_files(models, removal.cache_paths)
        if files is None:
            with client:
                ui.notify("Nothing to delete: the file is not inside its cache volume.", type="warning")
            return
        in_models = self._files_of(models, removal.shas) if removal.shas else []
        freed = sum(f.path.stat().st_size for f in files if f.path.is_file())
        freed += sum(rec.size for rec, _ in in_models)
        resolved = frozenset(f.path.resolve() for f in files)
        titles = self._entries_sharing(models, resolved)
        users = ", ".join(self._using_graphs(context, models, removal.shas, resolved))
        shared = "; ".join(
            dict.fromkeys(
                f"This file is in the shared {f.source.label} cache; other tools may use it." for f in files
            )
        )
        confirm_modal(
            title="Remove model file",
            message=(
                f"Delete {removal.label} ({format_size(freed)})? "
                f"Catalog entries: {', '.join(sorted(titles))}. Used by: {users or NOT_USED}. {shared}"
            ),
            confirm_label="Delete",
            danger=True,
            on_confirm=lambda: self._remove(context, models, removal, client),
        )

    @staticmethod
    def _entries_sharing(models: ModelsState, paths: frozenset[Path]) -> set[str]:
        """Titles of the catalog entries whose located files include one of *paths*."""
        titles: set[str] = set()
        for entry in models.catalog.entries():
            for resource in entry.resources:
                found = locate_resource(resource, models.index, models.sources)
                if found is not None and any(p.resolve() in paths for p in files_of(found[0], resource)):
                    titles.add(_variant_title(entry, None))
        return titles

    def _remove_cache_files(self, models: ModelsState, removal: _Removal, client: Any) -> bool:
        """Delete the cache files through their model sources, and any fetch records of them.

        Returns ``False`` when a path is not inside a cache volume; nothing is deleted then.
        """
        files = self._cache_files(models, removal.cache_paths)
        if files is None:
            with client:
                ui.notify("Nothing to delete: the file is not inside its cache volume.", type="warning")
            return False
        failed: list[str] = []
        for f in files:
            try:
                f.source.remove(f.path)
            except (OSError, ValueError) as exc:
                failed.append(f"{f.path.name}: {exc}")
                continue
            try:
                models.records.remove(f.source.volume, f.relative)
            except OSError:
                logger.warning("could not save the fetch records after deleting %s", f.path, exc_info=True)
        if failed:
            with client:
                ui.notify("Could not delete " + "; ".join(failed), type="negative")
        if any(f.source.volume == HF_VOLUME for f in files):
            self._refresh_hf(models)
        models.files_changed()
        self.wrapper.redraw()
        return True

    def _remove(self, context: SessionContext, models: ModelsState, removal: _Removal, client: Any) -> None:
        """Delete the files and their records: recorded cache files, then those inside the models volume."""
        if not context.can_access(AccessTier.ADMIN):
            self._refuse(client)
            return
        if removal.cache_paths and not self._remove_cache_files(models, removal, client):
            return
        if not removal.shas:
            return
        try:
            root = location_of(MODELS_VOLUME).resolve()
        except VolumeError:
            return
        failed: list[str] = []
        deleted: set[str] = set()
        for rec, path in self._files_of(models, removal.shas):
            try:
                path.unlink(missing_ok=True)
            except OSError as exc:
                failed.append(f"{path.name}: {exc}")
                continue
            deleted.add(rec.sha256)
            parent = path.parent
            while parent != root and parent.is_relative_to(root):
                try:
                    parent.rmdir()  # only when empty
                except OSError:
                    break
                parent = parent.parent
        for sha in deleted:
            models.index.remove(sha)
        if failed:
            with client:
                ui.notify("Could not delete " + "; ".join(failed), type="negative")
