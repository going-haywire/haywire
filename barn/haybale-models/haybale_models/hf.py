"""Hugging Face bridge: ``hf://`` URIs, offline cache lookup, download, cache listing.

Two address forms: a per-file ``hf://org/repo/path[@rev]`` (:func:`parse_hf`, :func:`cached_path`,
:func:`download`) and a whole-repo address ``hf://org/repo@<commit>`` (:func:`parse_hf_repo`,
:func:`snapshot_path`, :func:`download_snapshot`), optionally narrowed by ``include`` patterns.

Every call passes ``cache_dir=`` explicitly; no environment variable is ever set.
Only :func:`remote_sha256`, :func:`download` and :func:`download_snapshot` touch the network.
"""

from __future__ import annotations

import os
import re
import threading
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

import huggingface_hub
import huggingface_hub.utils
from haybale_models.sources.base import DownloadCancelled
from huggingface_hub._tree_cache import read_tree_cache
from huggingface_hub.errors import LocalEntryNotFoundError
from huggingface_hub.file_download import repo_folder_name
from huggingface_hub.utils import _shared_blobs

POLL_INTERVAL_S = 0.5
"""Seconds between progress polls of the ``.incomplete`` blob (tests may lower it)."""

_SCHEME = "hf://"
_COMMIT = re.compile(r"[0-9a-f]{40}")
_BYTES_BAR = "huggingface_hub.snapshot_download"


@dataclass(frozen=True)
class HfUri:
    """A parsed ``hf://org/repo/path/in/repo[@rev]`` reference."""

    repo_id: str
    path: str
    revision: str = "main"


@dataclass(frozen=True)
class HfRepoUri:
    """A parsed whole-repo address ``hf://org/repo@<commit>``.

    Example::

        parse_hf_repo("hf://org/repo@" + "a" * 40)  # HfRepoUri("org/repo", "aaa...a")
    """

    repo_id: str
    commit: str
    """The 40-character lower-case hex commit."""


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


def is_whole_repo(uri: str) -> bool:
    """Return whether ``uri`` has the whole-repo form ``hf://org/repo@<rev>``.

    Only the shape is checked: ``hf://o/r@main`` is whole-repo here and refused by
    :func:`parse_hf_repo`.
    """
    if not uri.startswith(_SCHEME) or "@" not in uri:
        return False
    body = uri[len(_SCHEME) :].rsplit("@", 1)[0]
    parts = body.split("/")
    return len(parts) == 2 and all(parts)


def parse_hf_repo(uri: str) -> HfRepoUri:
    """Parse a whole-repo address ``hf://org/repo@<commit>``.

    Raises:
        ValueError: ``uri`` is not a whole-repo address, or its revision is not a
            40-character lower-case hex commit (a branch or tag).
    """
    if not is_whole_repo(uri):
        raise ValueError(f"not a whole-repo hf:// address (hf://org/repo@<commit>): {uri!r}")
    repo_id, rev = uri[len(_SCHEME) :].rsplit("@", 1)
    if not _COMMIT.fullmatch(rev):
        raise ValueError(
            f"a whole-repo hf:// address needs a commit (40 hex characters), not a branch: {uri}"
        )
    return HfRepoUri(repo_id, rev)


def matching_files(folder: Path, include: tuple[str, ...]) -> list[Path]:
    """The files under ``folder`` that match ``include`` (all when empty), by ``huggingface_hub`` rules.

    A pattern ending in ``/`` matches a folder's whole subtree, as in ``allow_patterns``.
    """
    if not folder.is_dir():
        return []
    rel = [p.relative_to(folder).as_posix() for p in folder.rglob("*") if p.is_file()]
    if not include:
        return [folder / r for r in rel]
    kept = huggingface_hub.utils.filter_repo_objects(rel, allow_patterns=list(include))
    return [folder / r for r in kept]


def remove_cached_file(path: Path, cache_dir: Path) -> None:
    """Delete one file of a cached snapshot, and its blob when no other snapshot of the repo links to it.

    Folders the file leaves empty inside its snapshot are removed; the snapshot folder itself,
    ``refs/`` and the cached tree listing stay.

    Args:
        path: The file's path inside ``<cache_dir>/models--<org>--<repo>/snapshots/<commit>/``.

    Raises:
        ValueError: *path* is not a file of a cached snapshot under *cache_dir*.
        OSError: A file could not be deleted.
    """
    base = cache_dir.absolute()
    try:
        parts = path.absolute().relative_to(base).parts
    except ValueError:
        parts = ()
    if len(parts) < 4 or not parts[0].startswith("models--") or parts[1] != "snapshots" or ".." in parts:
        raise ValueError(f"{path} is not a file of a cached snapshot in {cache_dir}")
    repo = base / parts[0]
    snapshot = repo / "snapshots" / parts[2]
    blob = _first_link_target(path)
    path.unlink(missing_ok=True)
    if blob is not None and blob.parent == repo / "blobs" and not _still_linked(repo, blob):
        # Read before the link goes: the shared store is found through it.
        shared = _shared_blobs.shared_blob_target(blob, base)
        blob.unlink(missing_ok=True)
        if shared is not None:
            _shared_blobs.sweep_shared_blob(shared, cache_dir=base)
    parent = path.parent
    while parent != snapshot and parent.is_relative_to(snapshot):
        try:
            parent.rmdir()  # only when empty
        except OSError:
            break
        parent = parent.parent


def _first_link_target(path: Path) -> Path | None:
    """Return where the link at *path* points, not following any further link; ``None`` if no link."""
    if not path.is_symlink():
        return None
    return Path(os.path.normpath(path.absolute().parent / os.readlink(path)))


def _still_linked(repo: Path, blob: Path) -> bool:
    """Whether a link under the repo's snapshots points at the repo blob *blob*."""
    return any(_first_link_target(p) == blob for p in (repo / "snapshots").rglob("*"))


def _has_match(folder: Path, include: tuple[str, ...]) -> bool:
    """Whether a file under ``folder`` matches one of the ``include`` patterns."""
    return bool(matching_files(folder, include))


def snapshot_path(uri: str, cache_dir: Path, include: tuple[str, ...]) -> Path | None:
    """Return the cached snapshot folder of a whole-repo address, or ``None``. Offline; never downloads.

    Args:
        uri: A whole-repo address ``hf://org/repo@<commit>``.
        include: ``fnmatch`` patterns of the repo files wanted; empty means the whole repo.

    Returns:
        The snapshot folder, or ``None`` when it is missing, when there is no cached tree
        listing for the commit (per-file downloads and other tools leave none), when the
        listing shows a wanted file missing, or when no file in the folder matches ``include``.

    Raises:
        ValueError: ``uri`` is not a whole-repo address with a commit (see :func:`parse_hf_repo`).
    """
    ref = parse_hf_repo(uri)
    storage = Path(cache_dir) / repo_folder_name(repo_id=ref.repo_id, repo_type="model")
    if read_tree_cache(str(storage), ref.commit) is None:
        return None
    try:
        found = huggingface_hub.snapshot_download(
            ref.repo_id,
            revision=ref.commit,
            cache_dir=cache_dir,
            allow_patterns=list(include) or None,
            local_files_only=True,
        )
    except (LocalEntryNotFoundError, ValueError):
        return None
    folder = Path(found)
    if not _has_match(folder, include):
        return None
    return folder


def download_snapshot(
    uri: str,
    cache_dir: Path,
    include: tuple[str, ...],
    expected_size: int | None,
    on_progress: Callable[[int, int | None], None],
    cancel: threading.Event,
) -> Path:
    """Download a whole-repo address into the HF cache and return its snapshot folder.

    Blocks the calling thread. Files already in the cache are not downloaded again.

    Args:
        uri: A whole-repo address ``hf://org/repo@<commit>``.
        include: ``fnmatch`` patterns of the repo files wanted; empty means the whole repo.
        expected_size: Total bytes to report while the download has no total of its own;
            ``None`` if unknown.
        on_progress: Called from download threads with ``(bytes done, total bytes or None)``.
        cancel: Checked once the download returns: when set, the result is discarded (the
            files stay in the cache). The transfer itself cannot be stopped.

    Raises:
        DownloadCancelled: ``cancel`` was set when the download returned.
        ValueError: ``uri`` is not a whole-repo address with a commit, or no file of the
            repo matches ``include``.
    """
    ref = parse_hf_repo(uri)
    lock = threading.Lock()

    class _Progress(huggingface_hub.utils.tqdm):  # type: ignore[misc]
        """Reports the snapshot's bytes bar to ``on_progress``."""

        def __init__(self, *args: object, **kwargs: object) -> None:
            self._hw_reported = kwargs.get("name") == _BYTES_BAR
            self._hw_done = 0
            super().__init__(*args, **kwargs)

        def update(self, n: float | None = 1) -> bool | None:
            # Never raises: hf_xet calls this from its Rust download thread, which only prints an
            # exception and keeps downloading.
            if self._hw_reported:
                # Counted here because a disabled tqdm's ``update`` does nothing.
                with lock:
                    self._hw_done += int(n or 0)
                    done = max(0, self._hw_done)
                on_progress(done, self.total or expected_size)
            return super().update(n)  # type: ignore[no-any-return]

    try:
        result = huggingface_hub.snapshot_download(
            ref.repo_id,
            revision=ref.commit,
            cache_dir=cache_dir,
            allow_patterns=list(include) or None,
            tqdm_class=_Progress,
        )
    except Exception:
        if cancel.is_set():
            raise DownloadCancelled(uri) from None
        raise
    if cancel.is_set():
        raise DownloadCancelled(uri)
    folder = Path(result)
    # huggingface_hub only logs a warning when no repo file matches the patterns.
    if not _has_match(folder, include):
        raise ValueError(f"no file of {ref.repo_id}@{ref.commit} matches include {list(include)}")
    return folder


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
