"""ModelsEditor — the model files on this machine and where they come from.

A **Needed** section lists what the open graphs lack; below it the **Catalog** (every resource
of every installed catalog entry, with its status), **Local** (files in the models volume that
no catalog resource claims) and the **Hugging Face cache** (read-only; haywire never deletes
there), which lists only files a catalog entry or an open graph refers to. Download, cancel,
remove and *Fetch all* need admin access and are re-checked at click time.
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
from haywire.ui.editor.base import BaseEditor
from haywire.ui.editor.decorator import editor
from haywire.ui.editor.identity import SlotName
from haywire.ui.modals import confirm_modal
from nicegui import core, ui

from haybale_graph_editor.notices import GraphNoticesChanged
from haybale_graph_editor.state.graph_app_state import GraphAppState
from haybale_models.consumer import preference_for
from haybale_models.download import DownloadJob
from haybale_models.hf import HfCachedFile, list_cache, parse_hf
from haybale_models.keys import MODELS_VOLUME
from haybale_models.needs import NeededModel, format_size, iter_model_refs, job_matches
from haybale_models.resolver import FetchSpec, ModelMissing, locate_resource, resolve
from haybale_models.signals import ModelsChanged
from haybale_models.state.models_state import ModelsState
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
    """What a Remove click deletes: the files of one or more digests."""

    label: str
    shas: set[str] = field(default_factory=set)


@dataclass
class _Located:
    """One catalog resource with where it was found, computed once per draw."""

    entry: CatalogEntry
    resource: Resource
    found: tuple[dict[str, Path], str, str, int] | None
    in_hf: bool

    @property
    def local(self) -> bool:
        return self.found is not None and not self.in_hf


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


def _files_summary(count: int, size: int) -> str:
    """Return the section-header summary "N file(s), SIZE"."""
    return f"{count} {'file' if count == 1 else 'files'}, {format_size(size)}"


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

    The **Show:** row picks the sections — **Catalog**, **Models**, **Huggingface** — and the
    search toggle opens a field that narrows every section. The **Needed** section is always
    shown: per open graph, the models it lacks; **Fetch all** downloads them. Each section
    header counts what the section lists; hover it for the whole volume's size.

    Each catalog resource shows its status: `local`, `HF cache`, `downloading`, `failed` or
    `not downloaded`. **Models** lists the files in the Models volume that no catalog entry
    occupies. **Huggingface** lists the cached files that catalog entries or open graphs use,
    and what uses each; the Volumes editor shows where the cache lives. Download, Cancel and
    Remove need admin access; a removal names the open graphs that use the file and the bytes
    it frees. Opening the editor and **Rescan** index the Models volume on a background thread.
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
            tuple((j.id, j.state) for j in models.queue.jobs()),
            frozenset(r.sha256 for r in models.index.records()),
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
                self._draw_filter_row(context)
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
        query = self._query.strip().lower() if self._search_on else ""
        box.clear()
        with box:
            self._draw_needed(context, models, graphs, jobs, admin)
            claimed, shown = self._draw_catalog(
                context, models, jobs, admin, visible=self._show[_SHOW_CATALOG], query=query
            )
            self._draw_downloads(context, models, jobs, shown, admin, query=query)
            if self._show[_SHOW_MODELS]:
                self._draw_local(context, models, records, claimed, admin, query=query)
            if self._show[_SHOW_HF]:
                self._draw_hf(models, graphs, query=query)

    # -- filter row -------------------------------------------------------------

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
        with (
            ui.row()
            .classes("w-full items-center no-wrap gap-2 pl-5 pr-2 rounded hw-list-item-hover")
            .mark("models-needed-model")
        ):
            hui.hint(label).classes("truncate flex-1 min-w-0").tooltip(address or label)
            hui.hint(f"{variant} · {size}" if variant else size).classes("flex-shrink-0")
            self._live_status(
                hui.hint(resource_status(False, False, matching))
                .classes("flex-shrink-0")
                .mark("models-needed-status"),
                self._job_status(False, False, [j.id for j in matching]),
            )
            if not admin:
                return
            if active:
                hui.icon_action(
                    hui.icon.close,
                    tooltip="Cancel download",
                    on_click=lambda ids=[j.id for j in active]: self._cancel(context, models, ids),
                ).mark("models-needed-cancel")
            else:
                hui.icon_action(
                    hui.icon.download,
                    tooltip="Download",
                    on_click=lambda: self._download(context, models, spec),
                ).mark("models-needed-download")

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
        hf_root = models.hf_cache
        grouped: list[tuple[str, list[_Located]]] = []
        for library in sorted(by_library, key=str.lower):
            rows: list[_Located] = []
            for entry in sorted(by_library[library], key=lambda e: e.name.lower()):
                for resource in entry.resources:
                    found = locate_resource(resource, models.index, hf_root)
                    in_hf = found is not None and hf_root is not None and self._under(found[0], hf_root)
                    if found is not None:
                        claimed.update(sha for p in found[0].values() if (sha := models.index.sha256_at(p)))
                    if query and query not in f"{library} {entry.name} {resource.variant_name()}".lower():
                        continue
                    rows.append(_Located(entry, resource, found, in_hf))
            if rows:
                grouped.append((library, rows))
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
            hui.hint("No match." if query else "Nothing in the catalog.").classes("px-2")
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
            and (not query or query in f"{j.label} {' '.join(j.sources)}".lower())
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
                    hui.hint(resource_status(False, False, [job]))
                    .classes("flex-shrink-0")
                    .mark("models-status"),
                    self._job_status(False, False, [job.id]),
                )
                if admin and job.state in ("queued", "running"):
                    hui.icon_action(
                        hui.icon.close,
                        tooltip="Cancel download",
                        on_click=lambda jid=job.id: self._cancel(context, models, [jid]),
                    ).mark("models-cancel")

    @staticmethod
    def _indexing_status(path: Path, fraction: float) -> _LiveText:
        def text_of(_jobs: dict[str, DownloadJob], pending: dict[Path, float]) -> str:
            return f"indexing… {int(pending.get(path, fraction) * 100)} %"

        return text_of

    @staticmethod
    def _job_status(local: bool, in_hf: bool, job_ids: list[str]) -> _LiveText:
        """Return a function giving the status text of a row from the current jobs."""

        def text_of(by_id: dict[str, DownloadJob], _pending: dict[Path, float]) -> str:
            return resource_status(local, in_hf, [by_id[i] for i in job_ids if i in by_id])

        return text_of

    @staticmethod
    def _under(files: dict[str, Path], root: Path) -> bool:
        return any(p.is_relative_to(root) for p in files.values())

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
        in_hf = row.in_hf
        matching = [j for j in jobs if job_matches(j, spec)]
        active = [j for j in matching if j.state in ("queued", "running")]
        status = resource_status(local is not None, in_hf, matching)
        size = resource.total_size
        with ui.column().classes("w-full gap-0 px-2 py-1 rounded hw-list-item-hover").mark("models-row"):
            with ui.row().classes("w-full items-center no-wrap gap-2"):
                _dot(_SHOW_CATALOG)
                title = _variant_title(entry, resource)
                hui.subject(title).classes("truncate flex-1 min-w-0").tooltip(
                    f"{title} — {resource.variant_name()}"
                )
                if admin:
                    self._catalog_actions(context, models, entry, resource, spec, local, in_hf, active)
            with ui.row().classes("w-full items-center no-wrap gap-1"):
                detail = f"{_format_of(resource)} · {format_size(size) if size is not None else '—'}"
                hui.hint(f"{detail} · {entry.license or '—'} ·").classes("truncate min-w-0")
                self._live_status(
                    hui.hint(status).classes("flex-shrink-0").mark("models-status"),
                    self._job_status(local is not None, in_hf, [j.id for j in matching]),
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
        in_hf: bool,
        active: list[DownloadJob],
    ) -> None:
        """Draw the Cancel, Download and Remove actions of a catalog row."""
        if active:
            hui.icon_action(
                hui.icon.close,
                tooltip="Cancel download",
                on_click=lambda ids=[j.id for j in active]: self._cancel(context, models, ids),
            ).mark("models-cancel")
        elif local is None and not in_hf:
            hui.icon_action(
                hui.icon.download,
                tooltip="Download",
                on_click=lambda: self._download(context, models, spec),
            ).mark("models-download")
        if local is not None:
            shas = {sha for p in local[0].values() if (sha := models.index.sha256_at(p))}
            hui.icon_action(
                hui.icon.delete,
                tooltip="Remove",
                on_click=lambda: self._confirm_remove(
                    context, models, _Removal(_variant_title(entry, resource), shas)
                ),
            ).mark("models-remove")

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
                if r.sha256 not in claimed
                and (not query or query in f"{r.relative} {r.source or ''}".lower())
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
            pending = {p: f for p, f in pending.items() if query in p.name.lower()}
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
    ) -> dict[tuple[str, str], tuple[set[str], set[str]]]:
        """Map ``(repo id, path)`` of every ``hf://`` file in use to its catalog entries and open graphs."""
        users: dict[tuple[str, str], tuple[set[str], set[str]]] = {}

        def add(url: str, catalog_name: str | None, graph_name: str | None) -> None:
            if not url.startswith("hf://"):
                return
            try:
                uri = parse_hf(url)
            except ValueError:
                return
            names, graph_names = users.setdefault((uri.repo_id.lower(), uri.path), (set(), set()))
            if catalog_name:
                names.add(catalog_name)
            if graph_name:
                graph_names.add(graph_name)

        def entry_urls(entry: CatalogEntry) -> list[str]:
            urls: list[str] = []
            for resource in entry.resources:
                urls.extend(resource.urls)
                for f in resource.files:
                    urls.extend(f.urls)
            return urls

        for entry in models.catalog.entries():
            for url in entry_urls(entry):
                add(url, entry.name, None)
        for container in graphs.all_containers():
            graph = container.editor.graph
            if graph is None:
                continue
            for _wrapper, _port_id, ref in iter_model_refs(graph):
                found = models.catalog.entry(ref.catalog) if ref.catalog else None
                for url in entry_urls(found) if found is not None else ref.urls:
                    add(url, None, container.display_name)
        return users

    def _draw_hf(self, models: ModelsState, graphs: GraphAppState, *, query: str = "") -> None:
        """Draw the cached Hugging Face files that a catalog entry or an open graph refers to."""
        root = models.hf_cache
        if root is None or not self._hf_rows:
            return
        users = self._hf_users(models, graphs)
        rows = [
            (r, users[key])
            for r in self._hf_rows
            if (key := (r.repo_id.lower(), r.path_in_repo)) in users
            and (not query or query in f"{r.repo_id}/{r.path_in_repo}".lower())
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
        for job_id in job_ids:
            models.queue.cancel(job_id)

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

    def _using_graphs(self, context: SessionContext, models: ModelsState, shas: set[str]) -> list[str]:
        """Names of the open graphs holding a model reference that resolves to one of *shas*."""
        names: list[str] = []
        for graph_container in context.app_data[GraphAppState].all_containers():
            graph = graph_container.editor.graph
            if graph is not None and self._graph_uses(models, graph, shas):
                names.append(graph_container.display_name)
        return names

    @staticmethod
    def _graph_uses(models: ModelsState, graph: Any, shas: set[str]) -> bool:
        for wrapper, port_id, ref in iter_model_refs(graph):
            try:
                preference = preference_for(wrapper.node, port_id)
            except Exception:
                preference = [{}]
            try:
                found = resolve(ref, preference, catalog=models.catalog, index=models.index, hf_cache=None)
            except ModelMissing:
                continue
            if found.sha256 in shas or any(models.index.sha256_at(p) in shas for p in found.files.values()):
                return True
        return False

    def _confirm_remove(self, context: SessionContext, models: ModelsState, removal: _Removal) -> None:
        client = ui.context.client
        if not context.can_access(AccessTier.ADMIN):
            self._refuse(client)
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

    def _remove(self, context: SessionContext, models: ModelsState, removal: _Removal, client: Any) -> None:
        """Delete the files and their index records; only ever inside the models volume."""
        if not context.can_access(AccessTier.ADMIN):
            self._refuse(client)
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
