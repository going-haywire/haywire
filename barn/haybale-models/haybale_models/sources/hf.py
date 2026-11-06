"""The built-in ``hf://`` model source: downloads into the Hugging Face cache volume."""

from __future__ import annotations

import hashlib
from collections.abc import Callable
from pathlib import Path

from haybale_models import hf
from haybale_models.keys import HF_VOLUME
from haybale_models.sources.base import FetchRequest, ModelSource, SourceFailed, blob_name

_CHUNK = 1024 * 1024


def _sha256_of(path: Path) -> str:
    hasher = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(_CHUNK), b""):
            hasher.update(chunk)
    return hasher.hexdigest()


class HfSource(ModelSource):
    """Hugging Face Hub files, kept in HF's own cache layout."""

    name = "hf"
    prefixes = ("hf",)
    label = "Hugging Face"
    volume = HF_VOLUME
    volume_noun = "Hugging Face cache volume"
    place = "HF cache"

    def __init__(self, cache: Callable[[], Path | None]) -> None:
        self._cache = cache

    def root(self) -> Path | None:
        return self._cache()

    def root_problem(self) -> str | None:
        if self._cache() is not None:
            return None
        return super().root_problem() or "location unknown"

    def parse(self, address: str) -> None:
        if hf.is_whole_repo(address):
            hf.parse_hf_repo(address)
        else:
            hf.parse_hf(address)

    def page_url(self, address: str) -> str | None:
        """Return the file's page on huggingface.co; ``None`` for a whole-repo or malformed address."""
        if hf.is_whole_repo(address):
            return None
        try:
            uri = hf.parse_hf(address)
        except ValueError:
            return None
        return f"https://huggingface.co/{uri.repo_id}/blob/{uri.revision}/{uri.path}"

    def names_folder(self, address: str) -> bool:
        return hf.is_whole_repo(address)

    def find_folder(self, address: str, include: tuple[str, ...]) -> Path | None:
        root = self.root()
        if root is None or not root.exists():
            return None
        return hf.snapshot_path(address, root, include)

    def find(self, address: str) -> Path | None:
        if hf.is_whole_repo(address):
            return self.find_folder(address, ())
        root = self.root()
        if root is None or not root.exists():
            return None
        return hf.cached_path(address, root)

    def remove(self, path: Path) -> None:
        """Delete one snapshot file, and its blob when no other snapshot links to it.

        See ``haybale_models.hf.remove_cached_file``.
        """
        root = self.root()
        if root is None:
            raise ValueError(f"{self.volume_noun} unavailable: {self.root_problem()}")
        hf.remove_cached_file(path, root)

    def fetch(self, request: FetchRequest) -> Path:
        if hf.is_whole_repo(request.address):
            return self._fetch_folder(request)
        path = hf.download(request.address, request.root, request.size, request.on_progress, request.cancel)
        if request.sha256 and blob_name(path) != request.sha256:
            if _sha256_of(path) != request.sha256:
                raise SourceFailed(f"digest mismatch for {request.address}")
        name = blob_name(path)
        request.result_sha256 = request.sha256 or (name if len(name) == 64 and name.isalnum() else None)
        return path

    def _fetch_folder(self, request: FetchRequest) -> Path:
        include = request.resource.include if request.resource else ()
        try:
            hf.parse_hf_repo(request.address)
            folder = hf.download_snapshot(
                request.address, request.root, include, request.size, request.on_progress, request.cancel
            )
        except ValueError as exc:
            raise SourceFailed(str(exc)) from exc
        if self.find_folder(request.address, include) is None:
            raise SourceFailed(f"incomplete snapshot of {request.address}")
        return folder
