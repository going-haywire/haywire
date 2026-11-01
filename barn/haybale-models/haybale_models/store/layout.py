"""Where a downloaded model file lands under the models volume root, and which volume holds a file."""

from collections.abc import Callable
from pathlib import Path, PurePosixPath
from urllib.parse import unquote, urlsplit

from haybale_models.keys import HF_VOLUME, MODELS_VOLUME

from haywire.core.models import CatalogEntry, ModelFile, Resource
from haywire.core.volumes import VolumeError, VolumePath, location_of

_FALLBACK_NAME = "model.bin"


def _basename(url: str) -> str:
    """Last path segment of a URL: query stripped, percent-decoding applied."""
    name = PurePosixPath(unquote(urlsplit(url).path)).name
    if name in ("", ".", "..") or "\\" in name or "\0" in name:
        return _FALLBACK_NAME
    return name


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
) -> Path:
    """The path a download of ``url`` is stored at.

    - catalog single file: ``<root>/<library>/<entry stem>/<basename>``
    - catalog bundle: ``<root>/<library>/<entry stem>/<variant>/<file.path>``
    - pasted URL: ``<root>/downloads/<host>/<basename>``

    When the target exists and ``existing_sha256`` reports a different digest than
    ``sha256``, ``-<sha8>`` is inserted before the suffix so both files coexist.

    A basename that is empty, ``.`` or ``..`` becomes ``model.bin``. A bundle file path
    with an absolute, backslash or ``..`` segment raises ``ValueError``.
    """
    if entry is not None:
        base = root / entry.library.name / entry.path.stem
        if resource is not None and file is not None and file.path:
            path = base / resource.variant_name() / _checked_bundle_path(file.path)
        else:
            path = base / _basename(url)
    else:
        path = root / "downloads" / (urlsplit(url).hostname or "unknown") / _basename(url)

    if sha256 and path.exists() and existing_sha256 is not None:
        indexed = existing_sha256(path)
        if indexed is not None and indexed != sha256:
            path = path.with_name(f"{path.stem}-{sha256[:8]}{path.suffix}")
    return path


def volume_path_of(path: Path) -> VolumePath | None:
    """Return ``path`` as a path inside the models or the HF cache volume, or ``None`` if in neither.

    An HF snapshot file keeps its own name: the unresolved path is tried before the
    resolved one (a snapshot file is a link to its blob).
    """
    for volume in (MODELS_VOLUME, HF_VOLUME):
        try:
            root = location_of(volume)
        except VolumeError:
            continue
        for candidate, base in ((path, root), (path.resolve(), root.resolve())):
            try:
                relative = candidate.relative_to(base).as_posix()
            except ValueError:
                continue
            return VolumePath(volume, "" if relative == "." else relative)
    return None
