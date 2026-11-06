"""``SourceSet``: which model source serves which address prefix."""

from __future__ import annotations

from collections.abc import Iterable, Sequence

from pathlib import Path

from haywire.core.volumes import VolumeError, location_of

from haybale_models.sources.base import ModelSource
from haybale_models.sources.folder import FolderSource


def prefix_of(address: str) -> str | None:
    """Lower-cased text before ``://``; ``None`` without one."""
    head, sep, _ = address.partition("://")
    return head.lower() if sep else None


class SourceSet:
    """The built-in model sources, looked up by address prefix."""

    def __init__(self, sources: Sequence[ModelSource]) -> None:
        self._sources = tuple(sources)
        # Prefixes are case-insensitive; the source objects keep their own spelling.
        self._by_prefix: dict[str, ModelSource] = {}
        for source in self._sources:
            for prefix in source.prefixes:
                self._by_prefix.setdefault(prefix.lower(), source)

    def lookup(self, address: str) -> ModelSource | None:
        """The source serving *address*'s prefix, else ``None``."""
        prefix = prefix_of(address)
        return None if prefix is None else self._by_prefix.get(prefix)

    def page_url(self, address: str) -> str | None:
        """The web page where a person can get the file at *address*; ``None`` when there is none."""
        source = self.lookup(address)
        return None if source is None else source.page_url(address)

    def cache_source(self, address: str) -> FolderSource | None:
        """The folder source serving *address*'s prefix, else ``None``; only a folder can serve a cache."""
        source = self.lookup(address)
        return source if isinstance(source, FolderSource) else None

    def holding(self, path: Path) -> ModelSource | None:
        """The source whose volume contains *path*, else ``None``; never ensures a volume.

        When volumes nest, the deepest root wins. For each root the unresolved path is tried before
        the resolved one (an HF snapshot file is a link to its blob). A source whose volume is
        undefined holds nothing.
        """
        resolved = path.resolve()
        best: ModelSource | None = None
        best_depth = -1
        for source in self._sources:
            try:
                root = location_of(source.volume)
            except VolumeError:
                continue
            for candidate, base in ((path, root), (resolved, root.resolve())):
                if candidate.is_relative_to(base):
                    if len(base.parts) > best_depth:
                        best, best_depth = source, len(base.parts)
                    break
        return best

    def builtin_prefixes(self) -> tuple[str, ...]:
        return tuple(self._by_prefix)

    def primary_prefixes(self) -> tuple[str, ...]:
        """The first prefix of each source, lower-cased, in order."""
        return tuple(s.prefixes[0].lower() for s in self._sources if s.prefixes)

    def download_prefixes(self) -> tuple[str, ...]:
        """Every prefix of each source that can download, lower-cased, in source order.

        Cache folder sources are left out: their addresses name files already in a cache.
        """
        return tuple(p.lower() for s in self._sources if not isinstance(s, FolderSource) for p in s.prefixes)

    def primary_download_prefixes(self) -> tuple[str, ...]:
        """The first prefix of each source that can download, lower-cased, in order."""
        return tuple(
            s.prefixes[0].lower() for s in self._sources if s.prefixes and not isinstance(s, FolderSource)
        )

    def unavailable(self, addresses: Iterable[str]) -> str | None:
        """The first prefix when no address has a source, else ``None``."""
        first: str | None = None
        for address in addresses:
            if self.lookup(address) is not None:
                return None
            if first is None:
                first = prefix_of(address)
        return first
