"""Offline resolver: a ``ModelRef`` plus a preference becomes local file(s).

No network call and no filesystem write happens here; files are found through the model
sources' offline ``find``.
"""

from __future__ import annotations

import hashlib
import logging
import os
import re
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from haybale_models.hf import matching_files
from haybale_models.matcher import Preference, candidates
from haybale_models.sources import ModelSource, SourceSet, prefix_of
from haybale_models.sources.base import blob_name
from haybale_models.store.index import ModelIndex
from haybale_models.value.model_ref import ModelRef

from haywire.core.catalog import CatalogEntry, CatalogRegistry, ModelFile, Resource

logger = logging.getLogger(__name__)

_HEX64 = re.compile(r"[0-9a-f]{64}")
_MISSING = "model missing — fetch it from Models"


@dataclass(frozen=True)
class FetchSpec:
    """What to fetch: a catalog variant, or a file reference's sources."""

    entry: CatalogEntry | None = None
    resource: Resource | None = None
    ref: ModelRef | None = None

    @property
    def identity(self) -> tuple[Any, ...]:
        """Key for deduplicating specs across consumers."""
        if self.entry is not None and self.resource is not None:
            return (self.entry.class_identity.registry_key, self.resource.variant_name())
        if self.ref is not None:
            return (self.ref.sha256 or self.ref.source,)
        return ()


class ModelMissing(Exception):
    """A reference has no local file. ``wanted`` is what the needs-list would fetch."""

    def __init__(self, ref: ModelRef, wanted: list[FetchSpec], reason: str = _MISSING) -> None:
        super().__init__(reason)
        self.ref = ref
        self.wanted = wanted
        self.reason = reason


@dataclass(frozen=True)
class ResolvedModel:
    """A reference resolved to local files.

    ``files`` maps a file's name inside the resource to its path (``""`` for a single
    file). ``sha256`` is honest: the single file's real digest, or for a bundle the
    digest of the sorted ``"path:sha"`` lines when every file has one; ``""`` when
    unknown. ``key`` is the pool key: the digest when known, else derived from the
    resolved path(s), so it is never empty and never collides across files.
    """

    files: dict[str, Path]
    sha256: str
    key: str
    size: int
    ref: ModelRef
    entry: CatalogEntry | None = None
    resource: Resource | None = None
    rank: int = 0
    better_unfetched: Resource | None = None

    @property
    def path(self) -> Path:
        """The single file, or the folder holding a bundle."""
        if "" in self.files:
            return self.files[""]
        parents = [str(p.parent) for p in self.files.values()]
        return Path(os.path.commonpath(parents)) if parents else Path()


def resolve(
    ref: ModelRef,
    preference: Preference,
    *,
    catalog: CatalogRegistry,
    index: ModelIndex,
    sources: SourceSet,
) -> ResolvedModel:
    """Resolve ``ref`` to local files, or raise :class:`ModelMissing`."""
    if ref.is_empty:
        raise ModelMissing(ref, [], "no model chosen")
    if ref.is_catalog:
        return _resolve_catalog(ref, preference, catalog, index, sources)
    return _resolve_file(ref, index, sources)


def _resolve_catalog(
    ref: ModelRef,
    preference: Preference,
    catalog: CatalogRegistry,
    index: ModelIndex,
    sources: SourceSet,
) -> ResolvedModel:
    key = ref.catalog or ""
    entry = catalog.entry(key)
    if entry is None:
        raise ModelMissing(ref, [], f"catalog entry {key} is not installed")
    ranked = candidates(entry.resources, preference)
    for rank, resource in ranked:
        located = locate_resource(resource, index, sources)
        if located is None:
            continue
        files, sha, key, size = located
        best = ranked[0][1]
        return ResolvedModel(
            files, sha, key, size, ref, entry, resource, rank, None if best is resource else best
        )
    wanted = [FetchSpec(entry=entry, resource=ranked[0][1])] if ranked else []
    raise ModelMissing(ref, wanted, _reason(index))


def names_whole_repo(urls: Iterable[str], sources: SourceSet) -> bool:
    """Whether any of *urls* is a folder address (a whole-repo address) of its model source."""
    for url in urls:
        source = sources.lookup(url)
        if source is not None and source.names_folder(url):
            return True
    return False


def _resolve_file(ref: ModelRef, index: ModelIndex, sources: SourceSet) -> ResolvedModel:
    if names_whole_repo(ref.urls, sources):
        raise ModelMissing(ref, [], "a whole-repo address belongs in a catalog entry")
    path = _locate_file(ref.sha256, ref.urls, index, sources, size=ref.size)
    if path is None:
        raise ModelMissing(ref, [FetchSpec(ref=ref)], _reason(index))
    sha = ref.sha256 or _digest_of(path, ref.urls, index) or ""
    return ResolvedModel({"": path}, sha, _pool_key(sha, path), _size_of(path), ref)


def _pool_key(sha: str, path: Path) -> str:
    return sha or f"path:{path.resolve()}"


def _reason(index: ModelIndex) -> str:
    return index.problem or _MISSING


def _known_digest(path: Path, index: ModelIndex) -> str | None:
    """The digest of *path* when already known without hashing: indexed, or an HF blob name."""
    known = index.sha256_at(path)
    if known:
        return known
    name = blob_name(path)
    return name if _HEX64.fullmatch(name) else None


def cache_of(resource: Resource, file: ModelFile) -> str | None:
    """The cache address of *file*: its own, else the resource's when the resource is a single file."""
    return file.cache or (None if resource.is_bundle else resource.cache)


def unserved_cache(resource: Resource, sources: SourceSet) -> str | None:
    """The prefix of the first file's ``cache`` that no cache source serves, else ``None``."""
    for mfile in resource.files:
        cache = cache_of(resource, mfile)
        if cache and sources.cache_source(cache) is None:
            return prefix_of(cache) or cache
    return None


def place_of(files: Iterable[Path], sources: SourceSet) -> str:
    """The status word of found *files*: the first non-``local`` place among them, else ``local``.

    A file no source holds counts as ``local``.
    """
    for path in files:
        held = sources.holding(path)
        if held is not None and held.place != "local":
            return held.place
    return "local"


def accepts(
    path: Path, sha256: str | None, source: ModelSource, index: ModelIndex, size: int | None = None
) -> bool:
    """Whether a file found by *source* may stand for the pinned *sha256* and the expected *size*.

    Never hashes. A file the model index has hashed is judged by its digest alone. Any other
    file is refused when its byte count differs from a known *size* or it cannot be stat'ed;
    its digest is then judged from the source's fetch record, else from the file name. An
    unpinned file of the right size is always accepted.
    """
    if not sha256 and size is None:
        return True
    indexed = index.sha256_at(path)
    if indexed and sha256:
        return indexed == sha256
    try:
        actual = path.stat().st_size
    except OSError:
        logger.warning("cannot read the size of %s; treated as not found", path, exc_info=True)
        return False
    if size is not None and actual != size:
        return False
    if not sha256:
        return True
    known = indexed or source.recorded_sha256(path, actual)
    if known:
        return known == sha256
    named = _known_digest(path, index)
    if named is not None and named != sha256:
        return False
    return source.matches(path, sha256) is not False


def find_accepted(
    address: str,
    sha256: str | None,
    index: ModelIndex,
    source: ModelSource | None,
    size: int | None = None,
) -> Path | None:
    """The file *source* has for *address*, if :func:`accepts` takes it for *sha256* and *size*. Offline."""
    if source is None:
        return None
    try:
        path = source.find(address)
    except ValueError:
        return None
    except Exception:
        logger.warning(
            "source %r failed to look up %s; treated as not found", source.name, address, exc_info=True
        )
        return None
    if path is None or not accepts(path, sha256, source, index, size):
        return None
    return path


def _locate_file(
    sha256: str | None,
    urls: tuple[str, ...],
    index: ModelIndex,
    sources: SourceSet,
    cache: str | None = None,
    size: int | None = None,
) -> Path | None:
    """Digest, then the cache, then each address; an address's file must not contradict its pin or *size*."""
    if sha256:
        found = index.by_sha256(sha256)
        if found is not None:
            return found
    if cache:
        path = find_accepted(cache, sha256, index, sources.cache_source(cache), size)
        if path is not None:
            return path
    for url in urls:
        path = find_accepted(url, sha256, index, sources.lookup(url), size)
        if path is not None:
            return path
    return None


def addresses_of(resource: Resource) -> tuple[str, ...]:
    """Every download address of every file of *resource*, in order."""
    found: list[str] = []
    for mfile in resource.files:
        found.extend(mfile.urls or (() if resource.is_bundle else resource.urls))
    return tuple(found)


def _folder_addresses(resource: Resource) -> tuple[str, ...]:
    """The addresses of a non-bundle *resource*; empty for a bundle."""
    if resource.is_bundle:
        return ()
    return resource.files[0].urls if resource.files and resource.files[0].urls else resource.urls


def files_of(files: dict[str, Path], resource: Resource) -> list[Path]:
    """The files a located resource stands for: a folder resource's files matching ``include``.

    For any other resource, the values of *files*.
    """
    folder = files.get("")
    if folder is not None and folder.is_dir():
        return matching_files(folder, resource.include)
    return list(files.values())


def folder_address(resource: Resource, sources: SourceSet) -> str | None:
    """The first address of a non-bundle *resource* when its source names a folder, else ``None``."""
    for address in _folder_addresses(resource)[:1]:
        source = sources.lookup(address)
        if source is not None and source.names_folder(address):
            return address
    return None


def find_folder_accepted(address: str, include: tuple[str, ...], source: ModelSource) -> Path | None:
    """The folder *source* has for *address* narrowed by *include*, else ``None``. Offline."""
    try:
        return source.find_folder(address, include)
    except ValueError:
        return None
    except Exception:
        logger.warning(
            "source %r failed to look up %s; treated as not found", source.name, address, exc_info=True
        )
        return None


def _tree_size(folder: Path, include: tuple[str, ...]) -> int:
    """Total bytes of the files under *folder* matching *include* (all when empty); unreadable count 0."""
    total = 0
    for path in matching_files(folder, include):
        try:
            total += path.stat().st_size
        except OSError:
            continue
    return total


def _locate_folder(resource: Resource, sources: SourceSet) -> tuple[dict[str, Path], str, str, int] | None:
    for address in _folder_addresses(resource):
        source = sources.lookup(address)
        if source is None or not source.names_folder(address):
            continue
        folder = find_folder_accepted(address, resource.include, source)
        if folder is not None:
            key = f"path:{folder.resolve()}|{','.join(resource.include)}"
            return {"": folder}, "", key, _tree_size(folder, resource.include)
    return None


def locate_resource(
    resource: Resource, index: ModelIndex, sources: SourceSet
) -> tuple[dict[str, Path], str, str, int] | None:
    """Return ``(files, digest, pool key, size)`` of *resource* if every file is on disk, else ``None``.

    Looks in the model index and then in each address's model source; a file whose size
    differs from its known size counts as missing. A folder resource (see :func:`folder_address`)
    resolves to ``{"": folder}`` with an empty digest. Offline.
    """
    if folder_address(resource, sources) is not None:
        return _locate_folder(resource, sources)
    files: dict[str, Path] = {}
    digests: dict[str, str] = {}
    keys: dict[str, str] = {}
    for mfile in resource.files:
        sha = mfile.sha256 or (None if resource.is_bundle else resource.sha256)
        urls = mfile.urls or (() if resource.is_bundle else resource.urls)
        size = mfile.size or (None if resource.is_bundle else resource.size)
        path = _locate_file(sha, urls, index, sources, cache_of(resource, mfile), size)
        if path is None:
            return None
        files[mfile.path] = path
        digests[mfile.path] = sha or _digest_of(path, urls, index) or ""
        keys[mfile.path] = _pool_key(digests[mfile.path], path)
    if not files:
        return None
    total = sum(_size_of(p) for p in files.values())
    if not resource.is_bundle:
        return files, digests[""], keys[""], total
    key_lines = "\n".join(f"{name}:{keys[name]}" for name in sorted(keys))
    key = hashlib.sha256(key_lines.encode("utf-8")).hexdigest()
    if not all(digests.values()):
        return files, "", key, total
    pool = "\n".join(f"{name}:{digests[name]}" for name in sorted(digests))
    return files, hashlib.sha256(pool.encode("utf-8")).hexdigest(), key, total


def _digest_of(path: Path, urls: tuple[str, ...], index: ModelIndex) -> str | None:
    """Best known digest of a located file without hashing it."""
    known = index.sha256_at(path)
    if known:
        return known
    for url in urls:
        record = index.by_source(url)
        if record is not None:
            return record.sha256
    # An HF blob is stored under its own sha256 for LFS files.
    name = blob_name(path)
    return name if _HEX64.fullmatch(name) else None


def _size_of(path: Path) -> int:
    try:
        return path.stat().st_size
    except OSError:
        return 0


__all__ = [
    "FetchSpec",
    "ModelFile",
    "ModelMissing",
    "ResolvedModel",
    "accepts",
    "files_of",
    "find_accepted",
    "folder_address",
    "place_of",
    "addresses_of",
    "cache_of",
    "resolve",
    "unserved_cache",
]
