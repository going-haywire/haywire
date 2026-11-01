"""ModelsEditor — the model files on this machine and where they come from.

Three sections: the **Catalog** (every resource of every installed catalog entry, with its
status), **Local** (files in the models volume that no catalog resource claims) and the
**Hugging Face cache** (read-only; haywire never deletes there). Download, cancel, remove and
*Fetch all* need admin access and are re-checked at click time.
"""

from __future__ import annotations

import logging
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Any

from haywire.core.access import AccessTier
from haywire.core.session.handlers import redraw_on
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
from haybale_models.hf import HfCachedFile, list_cache
from haybale_models.keys import MODELS_VOLUME
from haybale_models.needs import NeedsReport, job_matches, tree, collect_needs, format_size
from haybale_models.resolver import FetchSpec, ModelMissing, locate_resource, resolve
from haybale_models.signals import ModelsChanged
from haybale_models.state.models_state import ModelsState
from haybale_models.state.models_view_state import ModelsViewState
from haybale_models.status import resource_status
from haybale_models.store.index import IndexRecord
from haybale_models.value.model_ref import ModelRef

if TYPE_CHECKING:
    from haywire.core.models import CatalogEntry, Resource
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


NEEDS_TTL_S = 1.0


@editor(
    label="Models",
    icon=hui.icon.models,
    default_slot=SlotName.ACTION,
    requires=AccessTier.VIEW,
    description="Model files on this machine and where they come from",
)
class ModelsEditor(BaseEditor):
    """Lists the catalog, the local model files and the Hugging Face cache, with disk usage.

    Each catalog resource shows its status: `local`, `HF cache`, `downloading`, `failed` or
    `not downloaded`. Download, Cancel and Remove need admin access; a removal names the open
    graphs that use the file and the bytes it frees. Opening the editor and **Rescan** index
    the files in the models volume on a background thread. When the notice of a graph sent you
    here, only the resources that graph needs are listed, and **Fetch all** downloads them.
    The Hugging Face cache is read-only: **Reveal location** shows where it lives.
    """

    def __init__(self, wrapper: EditorWrapper) -> None:
        super().__init__(wrapper)
        self._scan_thread: threading.Thread | None = None
        self._hf_rows: list[HfCachedFile] | None = None
        self._hf_revealed = False
        self._started = False
        self._needs_cache: tuple[str, float, NeedsReport | None] | None = None
        self._trailing: Any = None

    @redraw_on(ModelsChanged, GraphNoticesChanged, ModelsViewState.graph_filter)
    def _on_models_changed(self, ctx: SessionContext, signal: object) -> None:
        pass

    # -- scan -----------------------------------------------------------------

    def _start_scan(self, models: ModelsState) -> None:
        """Index the models volume and read the HF cache on a daemon thread; one at a time."""
        thread = self._scan_thread
        if thread is not None and thread.is_alive():
            return
        hf_root = models.hf_cache

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
        admin = context.can_access(AccessTier.ADMIN)
        graphs = context.app_data[GraphAppState]
        filter_id = context.data[ModelsViewState].graph_filter
        graph_container = graphs.get(filter_id) if filter_id else None
        report = (
            self._cached_needs(models, filter_id, graph_container, container) if graph_container else None
        )
        needed = {s.spec.identity for s in report.missing} if report else None
        jobs = models.queue.jobs()
        records = models.index.records()
        with container:
            with ui.column().classes("w-full h-full gap-0"):
                with hui.slot_header("Models", icon=hui.icon.models):
                    hui.icon_action(
                        hui.icon.refresh, tooltip="Rescan", on_click=lambda: self._rescan(models)
                    ).mark("models-rescan")
                self._draw_usage(records)
                if graph_container is not None and report is not None:
                    self._draw_filter(context, models, graph_container.display_name, report, admin)
                with (
                    ui.scroll_area()
                    .classes("flex-1 w-full")
                    .props('content-style="width: 100%" content-active-style="width: 100%"')
                ):
                    with ui.column().classes("w-full gap-0 p-1"):
                        claimed = self._draw_catalog(context, models, jobs, needed, admin)
                        if needed is None:
                            self._draw_local(context, models, records, claimed, admin)
                            self._draw_hf(models)

    def _cached_needs(
        self, models: ModelsState, filter_id: str | None, container: Any, host: Element
    ) -> NeedsReport | None:
        """Return the needs of the filtered graph, reusing a report younger than ``NEEDS_TTL_S``.

        A reused report schedules one trailing redraw at its expiry, which recomputes it.
        """
        key = filter_id or ""
        cached = self._needs_cache
        now = time.monotonic()
        if cached is not None and cached[0] == key and now - cached[1] < NEEDS_TTL_S:
            self._schedule_trailing(host, NEEDS_TTL_S - (now - cached[1]))
            return cached[2]
        report = self._needs_of(models, container.editor.graph)
        self._needs_cache = (key, now, report)
        return report

    def _schedule_trailing(self, host: Element, delay: float) -> None:
        """Arrange one redraw after *delay* seconds unless one is already pending."""
        pending = self._trailing
        if pending is not None and not pending.is_deleted and not pending._is_canceled:
            return
        # Parented above the redrawn container: a timer inside it would be deleted by the next redraw.
        parent = host.parent_slot.parent if host.parent_slot is not None else host
        with parent:
            self._trailing = ui.timer(delay + 0.05, self.wrapper.redraw, once=True)

    def cleanup(self) -> None:
        pending = self._trailing
        self._trailing = None
        if pending is not None and not pending.is_deleted:
            pending.cancel()

    @staticmethod
    def _needs_of(models: ModelsState, graph: Any) -> NeedsReport | None:
        if graph is None:
            return None

        def resolve_fn(ref: ModelRef, preference: Any) -> Any:
            return resolve(
                ref, preference, catalog=models.catalog, index=models.index, hf_cache=models.hf_cache
            )

        return collect_needs(graph, resolve_fn)

    def _draw_usage(self, records: list[IndexRecord]) -> None:
        used = format_size(sum(r.size for r in records))
        if self._hf_rows is None:
            hf_text = "HF cache: scanning…"
        else:
            hf_text = f"HF cache: {format_size(sum(r.size for r in self._hf_rows))}"
        with ui.row().classes("w-full items-center gap-3 px-2 py-1"):
            hui.hint(f"models: {used}").mark("models-usage")
            hui.hint(hf_text).mark("models-hf-usage")

    def _draw_filter(
        self, context: SessionContext, models: ModelsState, name: str, report: NeedsReport, admin: bool
    ) -> None:
        with ui.row().classes("w-full items-center no-wrap gap-1 px-2 py-1"):
            hui.tag(f"Needed by {name}", color="primary").mark("models-filter-chip")
            hui.icon_action(
                hui.icon.close, tooltip="Show everything", on_click=lambda: self._clear_filter(context)
            ).mark("models-filter-clear")
            ui.element("div").classes("flex-1")
            if admin and report.missing:
                hui.button(
                    "Fetch all",
                    icon=hui.icon.download,
                    on_click=lambda: self._fetch_all(context, models, report.missing),
                ).classes("w-auto").mark("models-fetch-all")

    # -- catalog -----------------------------------------------------------------

    def _draw_catalog(
        self,
        context: SessionContext,
        models: ModelsState,
        jobs: list[DownloadJob],
        needed: set[tuple[Any, ...]] | None,
        admin: bool,
    ) -> set[str]:
        """Draw the Catalog section; returns the digests its resources occupy."""
        hui.section_label("Catalog")
        claimed: set[str] = set()
        by_library: dict[str, list[CatalogEntry]] = {}
        for entry in models.catalog.entries():
            by_library.setdefault(entry.library.label or entry.library.name, []).append(entry)
        filtered = needed is not None
        hf_root = models.hf_cache
        drawn = False
        for library in sorted(by_library):
            rows: list[_Located] = []
            for entry in sorted(by_library[library], key=lambda e: e.name):
                for resource in entry.resources:
                    if (
                        needed is not None
                        and FetchSpec(entry=entry, resource=resource).identity not in needed
                    ):
                        continue
                    # One locate per resource; HF and claimed-set work only when unfiltered.
                    found = locate_resource(resource, models.index, None if filtered else hf_root)
                    in_hf = found is not None and hf_root is not None and self._under(found[0], hf_root)
                    if found is not None and not filtered:
                        claimed.update(sha for p in found[0].values() if (sha := models.index.sha256_at(p)))
                    rows.append(_Located(entry, resource, found, in_hf))
            if not rows:
                continue
            drawn = True
            hui.hint(library).classes("px-2 pt-1")
            for row in rows:
                self._draw_catalog_row(context, models, jobs, row, admin)
        if not drawn:
            if needed is None:
                text = "Nothing in the catalog."
            elif not needed:
                text = "Everything this graph needs is present"
            else:
                text = "None of the missing models are in the catalog."
            hui.hint(text).classes("px-2")
        return claimed

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
    ) -> None:
        entry, resource = row.entry, row.resource
        spec = FetchSpec(entry=entry, resource=resource)
        local = row.found if row.local else None
        in_hf = row.in_hf
        matching = [j for j in jobs if job_matches(j, spec)]
        active = [j for j in matching if j.state in ("queued", "running")]
        status = resource_status(local is not None, in_hf, matching)
        size = resource.total_size
        with (
            ui.row()
            .classes("w-full items-center no-wrap gap-2 px-2 py-1 rounded hw-list-item-hover")
            .mark("models-row")
        ):
            hui.subject(entry.name).classes("truncate flex-1 min-w-0")
            hui.hint(resource.variant_name()).classes("flex-shrink-0")
            hui.hint(format_size(size) if size is not None else "—").classes("flex-shrink-0")
            hui.hint(entry.license or "—").classes("truncate flex-shrink-0 max-w-[6rem]")
            hui.hint(status).classes("flex-shrink-0").mark("models-status")
            if not admin:
                return
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
                        context, models, _Removal(f"{entry.name} ({resource.variant_name()})", shas)
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
    ) -> None:
        hui.section_label("Local")
        loose = sorted((r for r in records if r.sha256 not in claimed), key=lambda r: r.relative)
        try:
            root: Path | None = location_of(MODELS_VOLUME)
        except VolumeError:
            root = None
        pending = models.index.pending() if root is not None else {}
        if models.index.problem:
            hui.error_label(models.index.problem)
        if not loose and not pending:
            hui.hint("No other files in the models volume.").classes("px-2")
        for rec in loose:
            with (
                ui.row()
                .classes("w-full items-center no-wrap gap-2 px-2 py-1 rounded hw-list-item-hover")
                .mark("models-row")
            ):
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
                hui.subject(name).classes("truncate flex-1 min-w-0")
                hui.hint(f"indexing… {int(fraction * 100)} %").classes("flex-shrink-0")

    # -- HF cache -------------------------------------------------------------------

    def _draw_hf(self, models: ModelsState) -> None:
        hui.section_label("Hugging Face cache")
        root = models.hf_cache
        with ui.row().classes("w-full items-center gap-2 px-2"):
            hui.hint("External: shared with other tools, never deleted here.")
            if root is not None:
                hui.button("Reveal location", on_click=self._toggle_reveal).classes("w-auto").mark(
                    "models-hf-reveal"
                )
        if self._hf_revealed and root is not None:
            with ui.column().classes("w-full px-2"):
                hui.info_row("Location", str(root), label_width="w-16").mark("models-hf-location")
        if root is None:
            hui.hint("The Hugging Face cache volume is not available.").classes("px-2")
            return
        rows = self._hf_rows
        if rows is None:
            hui.hint("Scanning…").classes("px-2")
            return
        if not rows:
            hui.hint("Nothing cached.").classes("px-2")
        for row in rows:
            with ui.row().classes("w-full items-center no-wrap gap-2 px-2 py-1").mark("models-hf-row"):
                hui.subject(f"{row.repo_id}/{row.path_in_repo}").classes("truncate flex-1 min-w-0")
                hui.hint(row.revision[:8]).classes("font-mono flex-shrink-0")
                hui.hint(format_size(row.size)).classes("flex-shrink-0")

    def _toggle_reveal(self) -> None:
        self._hf_revealed = not self._hf_revealed
        self.wrapper.redraw()

    # -- actions ----------------------------------------------------------------------

    def _rescan(self, models: ModelsState) -> None:
        self._hf_rows = None
        self._needs_cache = None
        self._start_scan(models)
        self.wrapper.redraw()

    @staticmethod
    def _clear_filter(context: SessionContext) -> None:
        context.data[ModelsViewState].graph_filter = None

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
        from haybale_models.types.model_ref import MODEL_REF

        for level in tree(graph):
            for wrapper in list(level.node_wrappers.values()):
                node = wrapper.node
                for port_id, port in list(getattr(node, "ports", {}).items()):
                    if not (port.is_inlet() or port.is_config()):
                        continue
                    if not (isinstance(port.type_cls, type) and issubclass(port.type_cls, MODEL_REF)):
                        continue
                    if port.is_linked():
                        continue
                    value = port.get_value()
                    ref = value if isinstance(value, ModelRef) else ModelRef.from_dict(value or {})
                    if ref.is_empty:
                        continue
                    try:
                        preference = preference_for(node, port_id)
                    except Exception:
                        preference = [{}]
                    try:
                        found = resolve(
                            ref, preference, catalog=models.catalog, index=models.index, hf_cache=None
                        )
                    except ModelMissing:
                        continue
                    if found.sha256 in shas or any(
                        models.index.sha256_at(p) in shas for p in found.files.values()
                    ):
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
