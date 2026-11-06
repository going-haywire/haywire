"""The built-in ``https://`` / ``http://`` model source: streams into the models volume."""

from __future__ import annotations

import hashlib
from collections.abc import Callable
from pathlib import Path

import httpx

from haybale_models.keys import MODELS_VOLUME
from haybale_models.sources.base import (
    DownloadCancelled,
    FetchRequest,
    ModelSource,
    SourceFailed,
    finish_part,
)
from haybale_models.store.index import ModelIndex
from haybale_models.store.layout import target_path

_CHUNK = 1024 * 1024


class _RestartFresh(Exception):
    """The server rejected the resume range; start over without ``Range``."""


class HttpsSource(ModelSource):
    """Web downloads: ``.part`` resume, size and digest check, then recorded in the index."""

    name = "https"
    prefixes = ("https", "http")
    label = "Web"
    volume = MODELS_VOLUME
    volume_noun = "models volume"
    place = "local"
    fills_target = True
    cancels_running = True
    indexed_addresses = True

    def __init__(self, index: ModelIndex, root: Callable[[], Path | None] | None = None) -> None:
        self._index = index
        self._root = root

    def root(self) -> Path | None:
        return self._root() if self._root is not None else super().root()

    def page_url(self, address: str) -> str | None:
        """Return ``address`` itself: it is a web address."""
        return address

    def find(self, address: str) -> Path | None:
        record = self._index.by_source(address)
        if record is None:
            return None
        return self._index.by_sha256(record.sha256)

    def fetch(self, request: FetchRequest) -> Path:
        root = request.root
        if not root.is_dir():
            raise SourceFailed(f"models volume folder does not exist: {root}")
        url = request.address
        target = request.target or target_path(
            entry=request.entry,
            resource=request.resource,
            file=request.file,
            url=url,
            sha256=request.sha256,
            root=root,
            existing_sha256=self._index.sha256_at,
        )
        if not target.resolve().is_relative_to(root.resolve()):
            raise ValueError(f"target {target} is outside the models volume")
        target.parent.mkdir(parents=True, exist_ok=True)
        part = target.with_name(target.name + ".part")
        request.claim(target.resolve().relative_to(root.resolve()))
        if request.fresh:
            # A new mirror never continues another mirror's bytes.
            part.unlink(missing_ok=True)
        try:
            try:
                digest = self._stream(request, part, resume=True)
            except _RestartFresh:
                part.unlink(missing_ok=True)
                digest = self._stream(request, part, resume=False)
        except DownloadCancelled:
            part.unlink(missing_ok=True)
            raise
        finish_part(part, target, digest=digest, size=request.size, sha256=request.sha256)
        request.result_sha256 = digest
        if request.target is None:
            self._index.add(target, digest, source=url)
        return target

    def _stream(self, request: FetchRequest, part: Path, *, resume: bool) -> str:
        """Fetch the address into ``part`` (resuming it when possible); returns the sha256 hex."""
        url = request.address
        part_size = part.stat().st_size if resume and part.exists() else 0
        headers = {"Accept-Encoding": "identity"}  # Range offsets count raw bytes
        if part_size:
            headers["Range"] = f"bytes={part_size}-"
        with httpx.stream("GET", url, headers=headers, follow_redirects=True, timeout=30) as response:
            if response.status_code == 416 and part_size:
                raise _RestartFresh()
            if response.status_code >= 400:
                raise SourceFailed(f"HTTP {response.status_code}")
            if response.headers.get("content-type", "").lower().startswith("text/html"):
                raise SourceFailed("got an HTML page instead of the file")
            hasher = hashlib.sha256()
            length = response.headers.get("content-length")
            if response.status_code == 206 and part_size:
                done = part_size
                with part.open("rb") as existing:
                    for chunk in iter(lambda: existing.read(_CHUNK), b""):
                        hasher.update(chunk)
                mode = "ab"
                total = part_size + int(length) if length and length.isdigit() else None
            else:
                done = 0  # 200: the server ignored Range (or there was nothing to resume)
                mode = "wb"
                total = int(length) if length and length.isdigit() else None
            with part.open(mode) as out:
                for chunk in response.iter_bytes():
                    if request.cancel.is_set():
                        raise DownloadCancelled(url)
                    out.write(chunk)
                    hasher.update(chunk)
                    done += len(chunk)
                    request.on_progress(done, request.size or total)
            request.on_progress(done, request.size or total or done)
            return hasher.hexdigest()
