"""ModelsState — app-wide state of haybale-models: the two model volumes."""

from __future__ import annotations

import logging
import os
import threading
from pathlib import Path
from typing import TYPE_CHECKING

from haywire.core.di.context import get_catalog_registry
from haywire.core.catalog import CatalogRegistry
from haywire.core.state.base import AppState
from haywire.core.state.decorator import state
from haywire.core.storage import library_storage_dir
from haywire.core.volumes import VolumeError, ensure_volume, location_of

from haybale_models.download import DownloadQueue
from haybale_models.keys import HF_VOLUME, MODELS_VOLUME
from haybale_models.pool import LoadedModels
from haybale_models.resolver import FetchSpec
from haybale_models.signals import ModelsChanged
from haybale_models.sources import builtin_sources
from haybale_models.store.index import ModelIndex
from haybale_models.store.records import FetchRecords

if TYPE_CHECKING:
    from haybale_models.needs import NeedsReport, NeedsWatcher

logger = logging.getLogger(__name__)


def hf_default_cache() -> Path:
    """Return Hugging Face's own default hub cache.

    Order: ``$HF_HUB_CACHE``, then ``$HF_HOME/hub``, then ``~/.cache/huggingface/hub``.
    """
    hub = os.environ.get("HF_HUB_CACHE")
    if hub:
        return Path(hub).expanduser()
    home = os.environ.get("HF_HOME")
    if home:
        return Path(home).expanduser() / "hub"
    return Path("~/.cache/huggingface/hub").expanduser()


@state(
    label="Models",
    description="Model volumes, file index, download queue and the pool of loaded models",
)
class ModelsState(AppState):
    """Owns the model volumes, the file index and the pool of loaded models."""

    def __init__(self) -> None:
        super().__init__()
        self.pool = LoadedModels()
        """Models loaded in memory, shared between nodes."""
        self.index = ModelIndex()
        """Index of the files in the models volume."""
        self.records = FetchRecords(library_storage_dir("haybale_models") / "fetched.json")
        """Files fetched into cache volumes, by volume and path inside it."""
        self.sources = builtin_sources(self.index, hf_cache=lambda: self.hf_cache, records=self.records)
        """Model sources: how each kind of address finds and fetches a file."""
        self.queue = DownloadQueue(self.index, self.sources, self._max_parallel, self.records)
        """The process-wide download queue."""
        self.queue.add_listener(self._on_models_changed)
        self.index.add_listener(self._on_models_changed)
        self.records.add_listener(self._on_models_changed)
        self._needs: NeedsWatcher | None = None

    @staticmethod
    def _max_parallel() -> int:
        from haybale_models.settings.models_settings import ModelsSettings

        try:
            return int(ModelsSettings().max_parallel_downloads)
        except Exception:
            logger.debug("max_parallel_downloads unreadable; using 2", exc_info=True)
            return 2

    def fetch(self, specs: list[FetchSpec], principal: str | None) -> list[str]:
        """Queue every spec's missing files; returns the job ids."""
        ids: list[str] = []
        for spec in specs:
            ids.extend(self.queue.enqueue_all(spec, principal))
        return ids

    def files_changed(self) -> None:
        """Report that files changed in a cache volume, which nothing here watches.

        Open graphs are checked again, so a node using a removed file learns it is gone.
        """
        self._on_models_changed()
        if self._needs is not None:
            self._needs.refresh()

    def needed_reports(self) -> dict[str, NeedsReport]:
        """Return the latest needs report of every open graph that misses models, by binding id."""
        return self._needs.latest_reports() if self._needs is not None else {}

    def _on_models_changed(self) -> None:
        """Publish ``ModelsChanged`` on the event loop; dropped while no loop runs.

        Called from download threads and under the index's locks, so it only schedules.
        """
        from nicegui import core

        loop = core.loop
        if loop is None or not loop.is_running():
            return
        loop.call_soon_threadsafe(self._signal_emit, ModelsChanged())

    def _scan(self) -> None:
        try:
            self.index.scan()
            self.index.hash_pending()
        except Exception:
            logger.exception("model scan failed")

    @property
    def catalog(self) -> CatalogRegistry:
        """The model catalog registry."""
        return get_catalog_registry()

    @property
    def hf_cache(self) -> Path | None:
        """Root of the Hugging Face cache volume, or ``None`` when the volume has a problem."""
        try:
            return location_of(HF_VOLUME)
        except VolumeError:
            return None

    def on_disable(self) -> None:
        """Stop the downloads and release every loaded model."""
        if self._needs is not None:
            self._needs.stop()
            self._needs = None
        self.queue.stop()
        self.pool.release_all()

    def on_enable(self) -> None:
        # Only the default location is created: ``ensure_volume`` never makes folders, and a
        # user-edited volume on an unmounted drive must still fail honestly. The HF cache is
        # Hugging Face's to create.
        default_models = library_storage_dir("haybale_models") / "models"
        default_models.mkdir(parents=True, exist_ok=True)
        ensure_volume(
            MODELS_VOLUME,
            label="Models",
            description="Model files downloaded or added on this machine",
            location=default_models,
        )
        ensure_volume(
            HF_VOLUME,
            label="Hugging Face cache",
            description="Shared Hugging Face download cache; haywire never deletes here",
            location=hf_default_cache(),
        )
        threading.Thread(target=self._scan, name="models-scan", daemon=True).start()
        self._start_needs()

    def _start_needs(self) -> None:
        """Watch the open graphs for missing models; skipped when no graph registry exists."""
        from haywire.core.di.context import get_library_state_container
        from haybale_graph_editor.states.graph_app_state import GraphAppState

        from haybale_models.needs import NeedsWatcher

        try:
            graphs = get_library_state_container().get(GraphAppState)
        except Exception:
            logger.debug("no library state container; needs-list off", exc_info=True)
            return
        if graphs is None:
            return
        if self._needs is not None:
            self._needs.stop()
        self._needs = NeedsWatcher(graphs, self)
        self._needs.start()
