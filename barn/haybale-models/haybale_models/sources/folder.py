"""Cache-folder model sources: a framework's own model cache, kept as a cache volume."""

from __future__ import annotations

import re
from collections.abc import Callable
from pathlib import Path, PurePosixPath
from typing import TYPE_CHECKING

from haywire.core.volumes import VolumeError, ensure_volume, location_of

from haybale_models.sources.base import FetchRequest, ModelSource, SourceFailed

if TYPE_CHECKING:
    from haybale_models.store.records import FetchRecords

# torch.hub's HASH_REGEX: the sha256 prefix a file name carries.
_HASH_REGEX = re.compile(r"-([a-f0-9]+)\.")


class FolderSource(ModelSource):
    """A framework's model cache folder, addressed as ``<name>://<path inside the cache>``.

    The cache volume exists only once it is needed: a lookup adopts an existing suggested
    folder, a first fetch creates a missing one. With *records*, a file fetched into the cache
    is known by the digest its fetch record keeps.
    """

    def __init__(
        self,
        *,
        name: str,
        label: str,
        locate: Callable[[], Path],
        description: str,
        records: FetchRecords | None = None,
    ) -> None:
        self.name = name
        self.prefixes = (name,)
        self.label = label
        self.volume = f"haybale-models:volume:{name}"
        self.volume_noun = f"{label} cache volume"
        self.place = f"{label} cache"
        self._locate = locate
        self._description = description
        self._records = records

    def suggested(self) -> Path:
        """Where the framework keeps its cache on this machine."""
        return self._locate().expanduser()

    def root(self) -> Path | None:
        try:
            return location_of(self.volume)
        except VolumeError:
            pass
        suggested = self.suggested()
        if suggested.is_dir():
            self.ensure()
            return suggested
        return None

    def ensure(self) -> None:
        """Add the cache volume (suggested location only) unless it already exists."""
        ensure_volume(
            self.volume,
            label=f"{self.label} cache",
            description=self._description,
            location=self.suggested(),
        )

    def prepare_root(self) -> Path:
        """Ensure the cache volume and return its folder.

        A missing folder is created only at the suggested location.

        Raises:
            SourceFailed: The volume was moved to a folder that does not exist.
            OSError: The folder cannot be created.
        """
        self.ensure()
        root = location_of(self.volume)
        if root.is_dir():
            return root
        if root.expanduser().resolve() != self.suggested().resolve():
            raise SourceFailed(f"{self.label} cache volume folder does not exist: {root}")
        root.mkdir(parents=True, exist_ok=True)
        return root

    def recorded_sha256(self, path: Path, size: int) -> str | None:
        if self._records is None:
            return None
        root = self.root()
        if root is None:
            return None
        try:
            relative = path.resolve().relative_to(root.resolve()).as_posix()
        except ValueError:
            return None
        for record in self._records.at(self.volume, relative):
            if record.sha256 and record.current(size):
                return record.sha256
        return None

    def parse(self, address: str) -> None:
        self.relative(address)

    def relative(self, address: str) -> str:
        """The path inside the cache; raises ``ValueError`` unless it is a plain relative path."""
        _, sep, rest = address.partition("://")
        if not sep or not rest or rest.startswith("/") or "\\" in rest or ":" in rest:
            raise ValueError(f"not a path inside the {self.label} cache: {address}")
        if any(part in ("", "..") for part in PurePosixPath(rest).parts) or rest.endswith("/"):
            raise ValueError(f"not a path inside the {self.label} cache: {address}")
        return rest

    def target(self, address: str) -> Path | None:
        """Return the file's place in the cache, or ``None`` without a volume or outside the cache."""
        relative = self.relative(address)
        root = self.root()
        if root is None:
            return None
        target = root / relative
        if not target.resolve().is_relative_to(root.resolve()):
            return None
        return target

    def find(self, address: str) -> Path | None:
        target = self.target(address)
        return target if target is not None and target.is_file() else None

    def fetch(self, request: FetchRequest) -> Path:
        raise SourceFailed(f"{self.name}:// is a cache, not a download address")


class TorchHubSource(FolderSource):
    """The torch hub checkpoint folder, whose file names carry a sha256 prefix."""

    def matches(self, path: Path, sha256: str) -> bool | None:
        found = _HASH_REGEX.findall(path.name)
        if not found:
            return None
        return sha256.startswith(found[-1])
