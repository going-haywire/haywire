"""Offline resolver: a ``ModelRef`` plus a preference becomes local file(s).

No network call and no filesystem write happens here; the Hugging Face cache is read
through ``try_to_load_from_cache`` only.
"""

from __future__ import annotations

import hashlib
import os
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from haybale_models.hf import cached_path
from haybale_models.matcher import Preference, candidates
from haybale_models.store.index import ModelIndex
from haybale_models.value.model_ref import ModelRef

from haywire.core.models import CatalogEntry, ModelCatalogRegistry, ModelFile, Resource

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
    catalog: ModelCatalogRegistry,
    index: ModelIndex,
    hf_cache: Path | None,
) -> ResolvedModel:
    """Resolve ``ref`` to local files, or raise :class:`ModelMissing`."""
    if ref.is_empty:
        raise ModelMissing(ref, [], "no model chosen")
    if ref.is_catalog:
        return _resolve_catalog(ref, preference, catalog, index, hf_cache)
    return _resolve_file(ref, index, hf_cache)


def _resolve_catalog(
    ref: ModelRef,
    preference: Preference,
    catalog: ModelCatalogRegistry,
    index: ModelIndex,
    hf_cache: Path | None,
) -> ResolvedModel:
    key = ref.catalog or ""
    entry = catalog.entry(key)
    if entry is None:
        raise ModelMissing(ref, [], f"catalog entry {key} is not installed")
    ranked = candidates(entry.resources, preference)
    for rank, resource in ranked:
        located = locate_resource(resource, index, hf_cache)
        if located is None:
            continue
        files, sha, key, size = located
        best = ranked[0][1]
        return ResolvedModel(
            files, sha, key, size, ref, entry, resource, rank, None if best is resource else best
        )
    wanted = [FetchSpec(entry=entry, resource=ranked[0][1])] if ranked else []
    raise ModelMissing(ref, wanted, _reason(index))


def _resolve_file(ref: ModelRef, index: ModelIndex, hf_cache: Path | None) -> ResolvedModel:
    path = _locate_file(ref.sha256, ref.urls, index, hf_cache)
    if path is None:
        raise ModelMissing(ref, [FetchSpec(ref=ref)], _reason(index))
    sha = ref.sha256 or _digest_of(path, ref.urls, index) or ""
    return ResolvedModel({"": path}, sha, _pool_key(sha, path), _size_of(path), ref)


def _pool_key(sha: str, path: Path) -> str:
    return sha or f"path:{path.resolve()}"


def _reason(index: ModelIndex) -> str:
    return index.problem or _MISSING


def _locate_file(
    sha256: str | None, urls: tuple[str, ...], index: ModelIndex, hf_cache: Path | None
) -> Path | None:
    """Digest first, then the HF cache, then (only when unpinned) the source URI."""
    if sha256:
        found = index.by_sha256(sha256)
        if found is not None:
            return found
    if hf_cache is not None:
        for url in urls:
            if url.startswith("hf://"):
                try:
                    cached = cached_path(url, hf_cache)
                except ValueError:
                    continue
                if cached is not None:
                    return cached
    if not sha256:
        for url in urls:
            record = index.by_source(url)
            if record is not None:
                located = index.by_sha256(record.sha256)
                if located is not None:
                    return located
    return None


def locate_resource(
    resource: Resource, index: ModelIndex, hf_cache: Path | None
) -> tuple[dict[str, Path], str, str, int] | None:
    """Return ``(files, digest, pool key, size)`` of *resource* if every file is on disk, else ``None``.

    Looks in the model index and, when *hf_cache* is given, the Hugging Face cache. Offline.
    """
    files: dict[str, Path] = {}
    digests: dict[str, str] = {}
    keys: dict[str, str] = {}
    for mfile in resource.files:
        sha = mfile.sha256 or (None if resource.is_bundle else resource.sha256)
        urls = mfile.urls or (() if resource.is_bundle else resource.urls)
        path = _locate_file(sha, urls, index, hf_cache)
        if path is None:
            return None
        files[mfile.path] = path
        digests[mfile.path] = sha or _digest_of(path, urls, index) or ""
        keys[mfile.path] = _pool_key(digests[mfile.path], path)
    if not files:
        return None
    size = sum(_size_of(p) for p in files.values())
    if not resource.is_bundle:
        return files, digests[""], keys[""], size
    key_lines = "\n".join(f"{name}:{keys[name]}" for name in sorted(keys))
    key = hashlib.sha256(key_lines.encode("utf-8")).hexdigest()
    if not all(digests.values()):
        return files, "", key, size
    pool = "\n".join(f"{name}:{digests[name]}" for name in sorted(digests))
    return files, hashlib.sha256(pool.encode("utf-8")).hexdigest(), key, size


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
    name = path.resolve().name
    return name if _HEX64.fullmatch(name) else None


def _size_of(path: Path) -> int:
    try:
        return path.stat().st_size
    except OSError:
        return 0


__all__ = ["FetchSpec", "ModelFile", "ModelMissing", "ResolvedModel", "resolve"]
