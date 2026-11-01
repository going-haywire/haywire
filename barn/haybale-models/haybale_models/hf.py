"""Hugging Face bridge: ``hf://`` URIs, offline cache lookup, download, cache listing.

Every call passes ``cache_dir=`` explicitly; no environment variable is ever set.
Only :func:`remote_sha256` and :func:`download` touch the network.
"""

from __future__ import annotations

import threading
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

import huggingface_hub

POLL_INTERVAL_S = 0.5
"""Seconds between progress polls of the ``.incomplete`` blob (tests may lower it)."""

_SCHEME = "hf://"


class DownloadCancelled(Exception):
    """Raised by :func:`download` when ``cancel`` was set; the partial blob is kept."""


@dataclass(frozen=True)
class HfUri:
    """A parsed ``hf://org/repo/path/in/repo[@rev]`` reference."""

    repo_id: str
    path: str
    revision: str = "main"


@dataclass(frozen=True)
class HfCachedFile:
    """One file in the Hugging Face cache."""

    repo_id: str
    revision: str
    path_in_repo: str
    size: int
    blob_path: Path


def parse_hf(uri: str) -> HfUri:
    """Parse ``hf://org/repo/path@rev``; ``@rev`` is optional (default ``main``)."""
    if not uri.startswith(_SCHEME):
        raise ValueError(f"not an hf:// URI: {uri!r}")
    body = uri[len(_SCHEME) :]
    revision = "main"
    if "@" in body:
        body, revision = body.rsplit("@", 1)
        if not revision:
            revision = "main"
    parts = [p for p in body.split("/") if p]
    if len(parts) < 3:
        raise ValueError(f"hf:// URI needs org/repo/path: {uri!r}")
    return HfUri("/".join(parts[:2]), "/".join(parts[2:]), revision)


def cached_path(uri: str, cache_dir: Path) -> Path | None:
    """Return the cached file for ``uri`` or ``None``. Offline; never downloads."""
    ref = parse_hf(uri)
    found = huggingface_hub.try_to_load_from_cache(
        ref.repo_id, ref.path, cache_dir=cache_dir, revision=ref.revision
    )
    return Path(found) if isinstance(found, str) else None


def remote_sha256(uri: str) -> tuple[str, int] | None:
    """Ask the Hub for ``(sha256, size)`` of an LFS file; ``None`` on any error or non-LFS file."""
    try:
        ref = parse_hf(uri)
        infos = huggingface_hub.HfApi().get_paths_info(ref.repo_id, [ref.path], revision=ref.revision)
        lfs = getattr(infos[0], "lfs", None) if infos else None
        if lfs is None:
            return None
        return str(lfs.sha256), int(lfs.size)
    except Exception:
        return None


def _incomplete_size(cache_dir: Path, repo_id: str) -> int:
    blobs = cache_dir / ("models--" + repo_id.replace("/", "--")) / "blobs"
    best = 0
    try:
        for f in blobs.glob("*.incomplete"):
            try:
                best = max(best, f.stat().st_size)
            except OSError:
                pass
    except OSError:
        pass
    return best


def download(
    uri: str,
    cache_dir: Path,
    expected_size: int | None,
    on_progress: Callable[[int, int | None], None],
    cancel: threading.Event,
) -> Path:
    """Download ``uri`` into the HF cache, polling the ``.incomplete`` blob for progress.

    Blocks the calling thread. If ``cancel`` is set the result is discarded and
    :class:`DownloadCancelled` is raised (HF keeps the ``.incomplete`` for resume).
    """
    ref = parse_hf(uri)
    stop = threading.Event()

    def poll() -> None:
        while not stop.wait(POLL_INTERVAL_S):
            if cancel.is_set():
                return
            seen = _incomplete_size(cache_dir, ref.repo_id)
            # A blob already at full size while the download runs is a preallocated file, not progress.
            known = seen > 0 and (expected_size is None or seen < expected_size)
            on_progress(seen if known else 0, expected_size)

    poller = threading.Thread(target=poll, name="hf-progress", daemon=True)
    poller.start()
    try:
        result = huggingface_hub.hf_hub_download(
            ref.repo_id, ref.path, cache_dir=cache_dir, revision=ref.revision
        )
    finally:
        stop.set()
        poller.join()
    if cancel.is_set():
        raise DownloadCancelled(uri)
    path = Path(result)
    size = path.stat().st_size if path.exists() else (expected_size or 0)
    on_progress(size, expected_size if expected_size is not None else size)
    return path


def list_cache(cache_dir: Path) -> list[HfCachedFile]:
    """Flatten the HF cache into one row per cached file; empty if the folder is missing."""
    if not cache_dir.is_dir():
        return []
    info = huggingface_hub.scan_cache_dir(cache_dir)
    rows: list[HfCachedFile] = []
    for repo in info.repos:
        if repo.repo_type != "model":
            continue
        for rev in repo.revisions:
            for f in rev.files:
                try:
                    rel = f.file_path.relative_to(rev.snapshot_path).as_posix()
                except ValueError:
                    rel = f.file_name
                rows.append(HfCachedFile(repo.repo_id, rev.commit_hash, rel, f.size_on_disk, f.blob_path))
    rows.sort(
        key=lambda r: (r.repo_id.lower(), r.repo_id, r.revision, r.path_in_repo.lower(), r.path_in_repo)
    )
    return rows
