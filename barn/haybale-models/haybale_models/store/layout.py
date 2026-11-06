"""Where a downloaded model file lands under the models volume root, and which volume holds a file."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path, PurePosixPath
from urllib.parse import unquote, urlsplit

from typing import TYPE_CHECKING

from haybale_models.keys import HF_VOLUME, MODELS_VOLUME

from haywire.core.catalog import CatalogEntry, ModelFile, Resource
from haywire.core.volumes import VolumeError, VolumePath, location_of

if TYPE_CHECKING:
    from haybale_models.sources.registry import SourceSet

_FALLBACK_NAME = "model.bin"


def _basename(url: str) -> str:
    """Last path segment of a URL: query stripped, percent-decoding applied."""
    name = PurePosixPath(unquote(urlsplit(url).path)).name
    if name in ("", ".", "..") or "\\" in name or "\0" in name:
        return _FALLBACK_NAME
    return name


def safe_name(name: str) -> str:
    """Return *name*'s last path segment; an empty, ``.``, ``..`` or NUL one becomes ``model.bin``."""
    last = name.replace("\\", "/").rsplit("/", 1)[-1]
    if last in ("", ".", "..") or "\0" in last:
        return _FALLBACK_NAME
    return last


def _checked_bundle_path(path: str) -> str:
    """Return a bundle file path, or raise ``ValueError`` if it could leave its folder."""
    if path.startswith("/") or "\\" in path or "\0" in path:
        raise ValueError(f"unsafe bundle file path: {path!r}")
    if any(part in ("..", "") for part in path.split("/")):
        raise ValueError(f"unsafe bundle file path: {path!r}")
    return path


def target_path(
    *,
    entry: CatalogEntry | None,
    resource: Resource | None,
    file: ModelFile | None,
    url: str,
    sha256: str | None,
    root: Path,
    existing_sha256: Callable[[Path], str | None] | None = None,
    name: str | None = None,
) -> Path:
    """The path a download of ``url`` is stored at.

    - catalog single file: ``<root>/<library>/<entry stem>/<basename>``
    - catalog bundle: ``<root>/<library>/<entry stem>/<variant>/<file.path>``
    - pasted URL: ``<root>/downloads/<host>/<basename>``

    When the target exists and ``existing_sha256`` reports a different digest than
    ``sha256``, ``-<sha8>`` is inserted before the suffix so both files coexist.

    A basename that is empty, ``.`` or ``..`` becomes ``model.bin``. A bundle file path
    with an absolute, backslash or ``..`` segment raises ``ValueError``.

    *name*, when given, replaces the basename of ``url`` (see :func:`safe_name`); a bundle file
    keeps its declared path.
    """
    basename = _basename(url) if name is None else safe_name(name)
    if entry is not None:
        base = root / entry.library.name / entry.path.stem
        if resource is not None and file is not None and file.path:
            path = base / resource.variant_name() / _checked_bundle_path(file.path)
        else:
            path = base / basename
    else:
        path = root / "downloads" / (urlsplit(url).hostname or "unknown") / basename

    if sha256 and path.exists() and existing_sha256 is not None:
        indexed = existing_sha256(path)
        if indexed is not None and indexed != sha256:
            path = path.with_name(f"{path.stem}-{sha256[:8]}{path.suffix}")
    return path


def _relative_in(volume: str, path: Path) -> VolumePath | None:
    try:
        root = location_of(volume)
    except VolumeError:
        return None
    for candidate, base in ((path, root), (path.resolve(), root.resolve())):
        try:
            relative = candidate.relative_to(base).as_posix()
        except ValueError:
            continue
        return VolumePath(volume, "" if relative == "." else relative)
    return None


def volume_path_of(path: Path, sources: SourceSet | None = None) -> VolumePath | None:
    """Return ``path`` as a path inside a model volume, or ``None`` if in none.

    Without *sources* the volumes are the models and the HF cache; with them, every source's
    volume (models, HF, cache volumes). An HF snapshot file keeps its own name: the unresolved
    path is tried before the resolved one (a snapshot file is a link to its blob).
    """
    if sources is not None:
        held = sources.holding(path)
        return None if held is None else _relative_in(held.volume, path)
    for volume in (MODELS_VOLUME, HF_VOLUME):
        found = _relative_in(volume, path)
        if found is not None:
            return found
    return None
