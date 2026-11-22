"""Model sources: how each kind of address finds and fetches a model file.

The set is fixed: haybale-models' built-ins (``https``, ``hf``) and the cache sources, keyed by address
prefix. A library that keeps its models somewhere else manages those files itself.
"""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import TYPE_CHECKING

from haybale_models.sources.base import DownloadCancelled, FetchRequest, ModelSource, SourceFailed
from haybale_models.sources.folder import FolderSource, TorchHubSource
from haybale_models.sources.registry import SourceSet, prefix_of

if TYPE_CHECKING:
    from haybale_models.store.index import ModelIndex
    from haybale_models.store.records import FetchRecords


def builtin_sources(
    index: ModelIndex, *, hf_cache: Callable[[], Path | None], records: FetchRecords | None = None
) -> SourceSet:
    """A :class:`SourceSet` holding the built-in HTTPS, Hugging Face and cache sources.

    *records* are the files fetched into the cache volumes; see ``FolderSource``.
    """
    # Imported here: ``haybale_models.hf`` imports this package, so a top-level import would cycle.
    from haybale_models.sources.hf import HfSource
    from haybale_models.sources.https import HttpsSource

    from haybale_models.sources.caches import cache_sources

    return SourceSet([HttpsSource(index), HfSource(hf_cache), *cache_sources(records)])


__all__ = [
    "builtin_sources",
    "DownloadCancelled",
    "FetchRequest",
    "FolderSource",
    "ModelSource",
    "SourceFailed",
    "SourceSet",
    "TorchHubSource",
    "prefix_of",
]
