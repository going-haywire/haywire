"""The process-wide download queue.

Jobs outlive sessions. HTTPS downloads stream into ``<target>.part`` (resumed with a
``Range`` request), are hashed while streaming and move to their target only once size
and digest match. ``hf://`` sources go through :func:`haybale_models.hf.download` into
the Hugging Face cache. This module is the only writer into the models volume.
"""

from __future__ import annotations

import hashlib
import itertools
import logging
import os
import threading
import time
from collections.abc import Callable
from dataclasses import dataclass, field, replace
from pathlib import Path
from typing import Literal
from urllib.parse import urlsplit

import httpx

from haybale_models import hf
from haybale_models.keys import MODELS_VOLUME
from haybale_models.resolver import FetchSpec
from haybale_models.store.index import ModelIndex
from haybale_models.store.layout import target_path

from haywire.core.di.context import activity_tracker
from haywire.core.catalog import ModelFile
from haywire.core.volumes import VolumeError, location_of

logger = logging.getLogger(__name__)

PROGRESS_THROTTLE_S = 0.25
"""Minimum seconds between two progress notifications of one job."""

_CHUNK = 1024 * 1024

JobState = Literal["queued", "running", "done", "failed", "cancelled"]
_Plan = tuple[str, "ModelFile | None", "str | None", "int | None", tuple[str, ...]]
_ACTIVE: tuple[JobState, ...] = ("queued", "running")


@dataclass
class DownloadJob:
    """One file being fetched. Snapshots are handed out by :meth:`DownloadQueue.jobs`."""

    id: str
    label: str
    sha256: str | None
    size: int | None
    sources: tuple[str, ...]
    target: Path | None = None
    state: JobState = "queued"
    done_bytes: int = 0
    total_bytes: int | None = None
    error: str | None = None
    principal: str | None = None


@dataclass
class _Task:
    job: DownloadJob
    spec: FetchSpec
    file: ModelFile | None
    cancel: threading.Event = field(default_factory=threading.Event)
    thread: threading.Thread | None = None
    last_emit: float = 0.0
    claimed: set[Path] = field(default_factory=set)
    part: Path | None = None


class _MirrorFailed(Exception):
    """This source cannot serve the file; the next one is tried."""


class _RestartFresh(Exception):
    """The server rejected the resume range; start over without ``Range``."""


class DownloadQueue:
    """Bounded-parallel downloads with dedup, cancel and listeners."""

    def __init__(
        self,
        index: ModelIndex,
        hf_cache: Callable[[], Path | None],
        max_parallel: Callable[[], int],
    ) -> None:
        self._index = index
        self._hf_cache = hf_cache
        self._max_parallel = max_parallel
        self._lock = threading.RLock()
        self._tasks: dict[str, _Task] = {}
        self._writing: set[Path] = set()
        self._ids = itertools.count(1)
        self._listeners: list[Callable[[], None]] = []

    # -- listeners ---------------------------------------------------------------

    def add_listener(self, cb: Callable[[], None]) -> None:
        """Call ``cb()`` on state changes at once and on progress at most every 0.25 s per job."""
        with self._lock:
            self._listeners.append(cb)

    def remove_listener(self, cb: Callable[[], None]) -> None:
        with self._lock:
            if cb in self._listeners:
                self._listeners.remove(cb)

    def _notify(self) -> None:
        with self._lock:
            listeners = list(self._listeners)
        for cb in listeners:
            try:
                cb()
            except Exception:
                logger.exception("download queue listener failed")

    # -- public API ----------------------------------------------------------------

    def enqueue(self, spec: FetchSpec, principal: str | None) -> str:
        """Queue ``spec``; returns the id of its first job, or ``""`` when nothing is missing."""
        ids = self.enqueue_all(spec, principal)
        return ids[0] if ids else ""

    def enqueue_all(self, spec: FetchSpec, principal: str | None) -> list[str]:
        """Queue one job per missing file of ``spec``; returns their ids (existing ids on dedup)."""
        ids: list[str] = []
        for label, mfile, sha, size, sources in self._plan(spec):
            ids.append(self._add(spec, label, mfile, sha, size, sources, principal))
        self._pump()
        return ids

    def cancel(self, job_id: str) -> None:
        """Cancel a queued or running job. Idempotent."""
        changed = False
        with self._lock:
            task = self._tasks.get(job_id)
            if task is None:
                return
            if task.job.state == "queued":
                task.job.state = "cancelled"
                changed = True
            elif task.job.state == "running":
                task.cancel.set()
        if changed:
            self._notify()

    def jobs(self) -> list[DownloadJob]:
        """Snapshots of every job, oldest first."""
        with self._lock:
            return [replace(t.job) for t in self._tasks.values()]

    def stop(self) -> None:
        """Cancel every job and wait (briefly) for the running ones."""
        with self._lock:
            tasks = list(self._tasks.values())
            for task in tasks:
                if task.job.state == "queued":
                    task.job.state = "cancelled"
                elif task.job.state == "running":
                    task.cancel.set()
        for task in tasks:
            if task.thread is not None:
                task.thread.join(timeout=5)
        self._notify()

    # -- planning ------------------------------------------------------------------

    def _plan(
        self, spec: FetchSpec
    ) -> list[tuple[str, ModelFile | None, str | None, int | None, tuple[str, ...]]]:
        """One ``(label, file, sha, size, sources)`` per file that is not already local."""
        plan: list[tuple[str, ModelFile | None, str | None, int | None, tuple[str, ...]]] = []
        if spec.entry is not None and spec.resource is not None:
            resource = spec.resource
            bundle = resource.is_bundle
            label = spec.entry.name
            for mfile in resource.files:
                sha = mfile.sha256 or (None if bundle else resource.sha256)
                size = mfile.size or (None if bundle else resource.size)
                urls = mfile.urls or (() if bundle else resource.urls)
                if sha and self._index.by_sha256(sha) is not None:
                    continue
                if urls:
                    plan.append((label, mfile, sha, size, urls))
        elif spec.ref is not None and spec.ref.urls:
            ref = spec.ref
            if not (ref.sha256 and self._index.by_sha256(ref.sha256) is not None):
                plan.append(
                    (
                        ref.label or Path(urlsplit(ref.urls[0]).path).name or ref.urls[0],
                        None,
                        ref.sha256,
                        ref.size,
                        ref.urls,
                    )
                )
        return plan

    def _add(
        self,
        spec: FetchSpec,
        label: str,
        mfile: ModelFile | None,
        sha: str | None,
        size: int | None,
        sources: tuple[str, ...],
        principal: str | None,
    ) -> str:
        with self._lock:
            for task in self._tasks.values():
                job = task.job
                if job.state not in _ACTIVE:
                    continue
                if (sha is not None and job.sha256 == sha) or (
                    sha is None and job.sources[:1] == sources[:1]
                ):
                    return job.id
            job_id = f"dl-{next(self._ids)}"
            job = DownloadJob(job_id, label, sha, size, sources, total_bytes=size, principal=principal)
            self._tasks[job_id] = _Task(job, spec, mfile)
        self._notify()
        return job_id

    # -- scheduling ----------------------------------------------------------------

    def _pump(self) -> None:
        """Start queued jobs while fewer than ``max_parallel`` run."""
        try:
            limit = max(1, int(self._max_parallel()))
        except Exception:
            limit = 2
        started: list[_Task] = []
        with self._lock:
            running = sum(1 for t in self._tasks.values() if t.job.state == "running")
            for task in self._tasks.values():
                if running >= limit:
                    break
                if task.job.state != "queued":
                    continue
                task.job.state = "running"
                running += 1
                task.thread = threading.Thread(
                    target=self._run, args=(task,), name=f"model-download-{task.job.id}", daemon=True
                )
                started.append(task)
        for task in started:
            assert task.thread is not None
            task.thread.start()
        if started:
            self._notify()

    def _progress(self, task: _Task, done: int, total: int | None) -> None:
        now = time.monotonic()
        with self._lock:
            task.job.done_bytes = done
            if total is not None:
                task.job.total_bytes = total
            if now - task.last_emit < PROGRESS_THROTTLE_S:
                return
            task.last_emit = now
        self._notify()

    def _finish(self, task: _Task, state: JobState, error: str | None = None) -> None:
        with self._lock:
            task.job.state = state
            task.job.error = error
        self._notify()
        self._pump()

    # -- worker --------------------------------------------------------------------

    def _run(self, task: _Task) -> None:
        job = task.job
        token = None
        state: JobState = "failed"
        error: str | None = None
        try:
            token = activity_tracker().start(
                job.principal, "models.download", {"label": job.label, "source": job.sources[0]}
            )
            self._download(task)
            state = "done"
        except hf.DownloadCancelled:
            state, error = "cancelled", None
        except Exception as exc:
            logger.info("download %s failed: %s", job.id, exc)
            error = str(exc) or type(exc).__name__
        with self._lock:
            self._writing -= task.claimed
            task.claimed.clear()
        if token is not None:
            try:
                activity_tracker().finish(
                    token, ok=state == "done", error=error or (state if state != "done" else None)
                )
            except Exception:
                logger.exception("activity tracker failed to finish %s", job.id)
        self._finish(task, state, error)

    def _download(self, task: _Task) -> None:
        job = task.job
        needs_volume = any(not s.startswith("hf://") for s in job.sources)
        root: Path | None = None
        if needs_volume:
            try:
                root = location_of(MODELS_VOLUME)
            except VolumeError as exc:
                raise RuntimeError(f"models volume unavailable: {exc}") from exc
            if not root.is_dir():
                raise RuntimeError(f"models volume folder does not exist: {root}")
        last_error = "no source"
        for url in job.sources:
            if task.cancel.is_set():
                raise hf.DownloadCancelled(url)
            # A new mirror never continues another mirror's bytes.
            if task.part is not None:
                task.part.unlink(missing_ok=True)
                task.part = None
            try:
                if url.startswith("hf://"):
                    self._download_hf(task, url)
                else:
                    assert root is not None
                    self._download_http(task, url, root)
                return
            except (_MirrorFailed, httpx.HTTPError, httpx.InvalidURL, OSError) as exc:
                last_error = f"{url}: {exc}"
        raise RuntimeError(last_error)

    def _download_hf(self, task: _Task, url: str) -> None:
        job = task.job
        cache = self._hf_cache()
        if cache is None:
            raise _MirrorFailed("Hugging Face cache volume unavailable")
        path = hf.download(url, cache, job.size, lambda d, t: self._progress(task, d, t), task.cancel)
        if job.sha256 and path.resolve().name != job.sha256:
            digest = _sha256_of(path)
            if digest != job.sha256:
                raise _MirrorFailed(f"digest mismatch for {url}")
        with self._lock:
            job.target = path

    def _download_http(self, task: _Task, url: str, root: Path) -> None:
        job = task.job
        target = target_path(
            entry=task.spec.entry,
            resource=task.spec.resource,
            file=task.file,
            url=url,
            sha256=job.sha256,
            root=root,
            existing_sha256=self._index.sha256_at,
        )
        if not target.resolve().is_relative_to(root.resolve()):
            raise ValueError(f"target {target} is outside the models volume")
        target.parent.mkdir(parents=True, exist_ok=True)
        part = target.with_name(target.name + ".part")
        relative = target.resolve().relative_to(root.resolve())
        with self._lock:
            if relative not in task.claimed:
                if relative in self._writing:
                    raise RuntimeError(f"another download is writing {relative.as_posix()}")
                self._writing.add(relative)
                task.claimed.add(relative)
        task.part = part
        try:
            try:
                digest = self._stream(task, url, part, resume=True)
            except _RestartFresh:
                part.unlink(missing_ok=True)
                digest = self._stream(task, url, part, resume=False)
        except hf.DownloadCancelled:
            part.unlink(missing_ok=True)
            raise
        size = part.stat().st_size
        if job.size is not None and size != job.size:
            part.unlink(missing_ok=True)
            raise _MirrorFailed(f"size mismatch: got {size} bytes, expected {job.size}")
        if job.sha256 and digest != job.sha256:
            part.unlink(missing_ok=True)
            raise _MirrorFailed("digest mismatch")
        os.replace(part, target)
        self._index.add(target, digest, source=url)
        with self._lock:
            job.target = target

    def _stream(self, task: _Task, url: str, part: Path, *, resume: bool) -> str:
        """Fetch ``url`` into ``part`` (resuming it when possible); returns the sha256 hex."""
        part_size = part.stat().st_size if resume and part.exists() else 0
        headers = {"Accept-Encoding": "identity"}  # Range offsets count raw bytes
        if part_size:
            headers["Range"] = f"bytes={part_size}-"
        with httpx.stream("GET", url, headers=headers, follow_redirects=True, timeout=30) as response:
            if response.status_code == 416 and part_size:
                raise _RestartFresh()
            if response.status_code >= 400:
                raise _MirrorFailed(f"HTTP {response.status_code}")
            if response.headers.get("content-type", "").lower().startswith("text/html"):
                raise _MirrorFailed("got an HTML page instead of the file")
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
                    if task.cancel.is_set():
                        raise hf.DownloadCancelled(url)
                    out.write(chunk)
                    hasher.update(chunk)
                    done += len(chunk)
                    self._progress(task, done, task.job.size or total)
            self._progress(task, done, task.job.size or total or done)
            return hasher.hexdigest()


def _sha256_of(path: Path) -> str:
    hasher = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(_CHUNK), b""):
            hasher.update(chunk)
    return hasher.hexdigest()
