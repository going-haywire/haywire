"""The model-source shape: how one kind of address finds and fetches a model file."""

from __future__ import annotations

import os
import threading
from abc import ABC, abstractmethod
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from haywire.core.catalog import CatalogEntry, ModelFile, Resource
from haywire.core.volumes import VolumeError, location_of


class SourceFailed(Exception):
    """This address cannot serve the file; the next address is tried."""


class DownloadCancelled(Exception):
    """Raised by a fetch when ``cancel`` was set; the partial data is kept."""


@dataclass
class FetchRequest:
    """Everything a source needs to fetch one address into a volume root."""

    address: str
    root: Path
    sha256: str | None
    size: int | None
    entry: CatalogEntry | None
    resource: Resource | None
    file: ModelFile | None
    on_progress: Callable[[int, int | None], None]
    cancel: threading.Event
    claim: Callable[[Path], None]
    """Claims a path relative to ``root`` for writing; raises ``Refusal`` if another job writes it."""
    fresh: bool
    """True when an earlier address of this job was tried: never continue its bytes."""
    target: Path | None = None
    """When set, the absolute path (inside ``root``) to write; skips the source's layout and the index."""
    result_sha256: str | None = None
    """Set by the source after a successful fetch: the verified sha256 of what it wrote."""


def blob_name(path: Path) -> str:
    """Return the name a cached file is stored under: its first link's target, else its own.

    In the Hugging Face cache that link's name is the file's sha256 for LFS files, whatever the
    final file is called: the cache-wide shared store names its files by Xet hash.
    """
    return Path(os.readlink(path)).name if path.is_symlink() else path.name


def finish_part(part: Path, target: Path, *, digest: str, size: int | None, sha256: str | None) -> None:
    """Check a fully written ``.part`` file against what was expected and move it to *target*.

    Args:
        part: The written file.
        target: Where it ends up; an existing file is replaced.
        digest: The sha256 hex of what was written.
        size: The expected size in bytes, or ``None`` when unknown.
        sha256: The expected sha256 hex, or ``None`` when unknown.

    Raises:
        SourceFailed: Size or digest differ; *part* is deleted and the message says what was expected.
    """
    written = part.stat().st_size
    if size is not None and written != size:
        part.unlink(missing_ok=True)
        raise SourceFailed(f"size mismatch: got {written} bytes, expected {size}")
    if sha256 and digest != sha256:
        part.unlink(missing_ok=True)
        raise SourceFailed(f"digest mismatch: got {digest}, expected {sha256}")
    os.replace(part, target)


class ModelSource(ABC):
    """One kind of address (``https://``, ``hf://``, ...), with its volume.

    A subclass sets these class (or instance) attributes:

    - ``name``: the source's short identifier.
    - ``prefixes``: the address prefixes it serves, without ``://``. Prefixes are
      matched case-insensitively.
    - ``label``: the human-readable name shown to users.
    - ``volume``: a volume key that :func:`haywire.core.volumes.location_of` resolves.
    - ``volume_noun``: how errors name that volume (``"models volume"``).
    - ``place``: the status word for a file in this source's volume (``"local"``).
    """

    name: str
    prefixes: tuple[str, ...]
    label: str
    volume: str
    volume_noun: str
    place: str
    fills_target: bool = False
    """Whether :meth:`fetch` can write to ``FetchRequest.target`` (a framework cache file)."""
    cancels_running: bool = False
    """Whether :meth:`fetch` stops promptly once ``FetchRequest.cancel`` is set."""
    indexed_addresses: bool = False
    """Whether :meth:`find` looks addresses up in the models index, so a file recorded there under an
    address is found through it."""

    def root(self) -> Path | None:
        """The volume root, or ``None`` when the volume is unavailable."""
        try:
            return location_of(self.volume)
        except VolumeError:
            return None

    def root_problem(self) -> str | None:
        """The volume problem text, or ``None`` when the volume is available."""
        try:
            location_of(self.volume)
        except VolumeError as exc:
            return str(exc)
        return None

    def parse(self, address: str) -> None:
        """Raise ``ValueError`` when ``address`` is malformed. Default: accept all."""
        return None

    def page_url(self, address: str) -> str | None:
        """The web page where a person can get the file at ``address``; ``None`` when there is none."""
        return None

    def names_folder(self, address: str) -> bool:
        """Whether ``address`` names a folder of files rather than one file. Default: ``False``."""
        return False

    def find_folder(self, address: str, include: tuple[str, ...]) -> Path | None:
        """Offline lookup of an already-present folder; never hashes.

        ``include`` limits which files the folder must hold. Returns ``None`` when it is
        not found (the default). May raise ``ValueError`` for a malformed address.
        """
        return None

    def matches(self, path: Path, sha256: str) -> bool | None:
        """Whether ``path`` is the file with ``sha256``, judged offline from its name.

        Never hashes. ``None`` means unknown (the default).
        """
        return None

    def recorded_sha256(self, path: Path, size: int) -> str | None:
        """The digest a fetch record keeps for ``path`` while the file still has *size* bytes.

        Never hashes. ``None`` means no such record (the default).
        """
        return None

    def remove(self, path: Path) -> None:
        """Delete one file of this source's volume and the folders it leaves empty, up to the root.

        Raises:
            ValueError: The volume is unavailable, or *path* (or what it links to) lies outside it.
            OSError: The file could not be deleted.
        """
        root = self.root()
        if root is None:
            raise ValueError(f"{self.volume_noun} unavailable: {self.root_problem()}")
        base = root.resolve()
        if path.resolve() == base or not path.resolve().is_relative_to(base):
            raise ValueError(f"{path} is outside the {self.volume_noun}")
        if not path.absolute().is_relative_to(root.absolute()) and not path.is_relative_to(base):
            raise ValueError(f"{path} is outside the {self.volume_noun}")
        path.unlink(missing_ok=True)
        parent = path.parent
        while parent.resolve() != base and parent.resolve().is_relative_to(base):
            try:
                parent.rmdir()  # only when empty
            except OSError:
                break
            parent = parent.parent

    @abstractmethod
    def find(self, address: str) -> Path | None:
        """Offline lookup of an already-present file; never hashes a cache.

        Returns ``None`` when the file is not found. May raise ``ValueError`` only for a
        malformed address; the resolver then treats it as not found.
        """

    @abstractmethod
    def fetch(self, request: FetchRequest) -> Path:
        """Fetch ``request.address``; raise :class:`SourceFailed` to try the next address.

        Call ``request.claim(...)`` with each path (relative to ``request.root``) before
        writing it. Raise :class:`DownloadCancelled` when ``request.cancel`` is set; partial
        data is kept.
        """
