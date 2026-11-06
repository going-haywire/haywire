"""The process-wide download queue.

Jobs outlive sessions. The queue owns the jobs: it deduplicates them by target, hands
each address to the model source that serves its prefix, and tracks which volume paths a
job has claimed so two jobs never write one path. The sources do the fetching (the
built-in web source streams into ``<target>.part``, resumes with a ``Range`` request and
moves the file to its target once size and digest match; the ``hf`` source goes through
:func:`haybale_models.hf.download` into the Hugging Face cache). Progress, cancel and
the job's state and error come back through the queue.
"""

from __future__ import annotations

import hashlib
import itertools
import logging
import threading
import time
from collections.abc import Callable
from dataclasses import dataclass, field, replace
from pathlib import Path
from typing import Literal
from urllib.parse import urlsplit

import httpx

from haybale_models.keys import MODELS_VOLUME
from haybale_models.receive import ReceiveRefused, UploadReceiver
from haybale_models.resolver import (
    FetchSpec,
    accepts,
    cache_of,
    find_accepted,
    folder_address,
    locate_resource,
    names_whole_repo,
)
from haybale_models.sources import DownloadCancelled, FetchRequest, SourceFailed, SourceSet, prefix_of
from haybale_models.store.index import ModelIndex
from haybale_models.store.layout import safe_name, target_path
from haybale_models.store.records import FetchRecord, FetchRecords

from haywire.core.di.context import activity_tracker
from haywire.core.catalog import ModelFile
from haywire.core.errors import Refusal, report_failure
from haywire.core.volumes import VolumeError, location_of

logger = logging.getLogger(__name__)

_CHUNK = 1024 * 1024


def sha256_of(path: Path) -> str:
    """Return the sha256 hex of the file at *path*."""
    hasher = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(_CHUNK), b""):
            hasher.update(chunk)
    return hasher.hexdigest()


PROGRESS_THROTTLE_S = 0.25
"""Minimum seconds between two progress notifications of one job."""

JobState = Literal["queued", "running", "done", "failed", "cancelled"]
_Plan = tuple[str, "ModelFile | None", "str | None", "int | None", tuple[str, ...], tuple[str, ...]]
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
    include: tuple[str, ...] = ()
    """Glob patterns narrowing a whole-repo (folder) job; ``()`` for a file job."""
    cancellable: bool = True
    """Whether :meth:`DownloadQueue.cancel` can stop the job now: always while queued, and while
    running only when the model source fetching it stops on cancel."""
    via_browser: bool = False
    """The bytes arrive through an upload instead of a model source."""


@dataclass(frozen=True)
class _CachePlace:
    """Where a job's file goes in a cache volume."""

    volume: str
    root: Path
    relative: str
    target: Path
    address: str
    present: bool = False
    """The target already holds an acceptable file nobody recorded: nothing to fetch."""


@dataclass
class _Task:
    job: DownloadJob
    spec: FetchSpec
    file: ModelFile | None
    cancel: threading.Event = field(default_factory=threading.Event)
    thread: threading.Thread | None = None
    last_emit: float = 0.0
    claimed: set[Path] = field(default_factory=set)


class DownloadQueue:
    """Bounded-parallel downloads with dedup, cancel and listeners."""

    def __init__(
        self,
        index: ModelIndex,
        sources: SourceSet,
        max_parallel: Callable[[], int],
        records: FetchRecords | None = None,
    ) -> None:
        self._index = index
        self._records = records
        self._sources = sources
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
        for label, mfile, sha, size, sources, include in self._plan(spec):
            ids.append(self._add(spec, label, mfile, sha, size, sources, principal, include))
        self._pump()
        return ids

    def cancel(self, job_id: str) -> bool:
        """Cancel a queued job, or ask a running one to stop. Idempotent.

        Returns ``False`` when nothing was done: an unknown or finished job, or a running job
        whose model source cannot stop mid-transfer (``DownloadJob.cancellable``).
        """
        changed = False
        with self._lock:
            task = self._tasks.get(job_id)
            if task is None:
                return False
            if task.job.state == "queued":
                task.job.state = "cancelled"
                changed = True
            elif task.job.state == "running" and task.job.cancellable:
                task.cancel.set()
            else:
                return False
        if changed:
            self._notify()
        return True

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

    # -- upload --------------------------------------------------------------------

    def assistable(self, job_id: str) -> bool:
        """Whether a person can finish this job by handing over the file through their browser.

        True for a failed file job that nothing has replaced since, when something would find the
        stored file: a digest, a ``cache`` target, or an address the models index answers for.
        """
        with self._lock:
            task = self._tasks.get(job_id)
            if task is None or task.job.state != "failed":
                return False
            job = task.job
            resource = task.spec.resource
            if resource is not None and folder_address(resource, self._sources) is not None:
                return False
            if job.sha256 and self._index.by_sha256(job.sha256) is not None:
                return False
            tasks = list(self._tasks.values())
            newer = tasks[tasks.index(task) + 1 :]
            if any(t.job.state == "done" and self._same_file(t.job, job) for t in newer):
                return False
            if job.sha256:
                return True
            if resource is not None and task.file is not None and cache_of(resource, task.file):
                return True
            return self._indexed_address(job) is not None

    def begin_receive(self, job_id: str, filename: str, principal: str | None) -> UploadReceiver:
        """Start an upload standing in for the failed job *job_id*; it runs as a new job.

        The new job does not count against the parallel limit, and the failed job stays listed.

        Args:
            job_id: A job for which :meth:`assistable` holds.
            filename: The uploaded file's own name; used where the target is not fixed.
            principal: Who uploads, for the activity log.

        Raises:
            ReceiveRefused: The upload cannot start; the message says why.
        """
        with self._lock:
            if not self.assistable(job_id):
                raise ReceiveRefused("this file has no failed download to replace")
            old = self._tasks[job_id]
            if any(t.job.state in _ACTIVE and self._same_file(t.job, old.job) for t in self._tasks.values()):
                raise ReceiveRefused("a download of this file is running")
            new_id = f"dl-{next(self._ids)}"
            job = DownloadJob(
                new_id,
                old.job.label,
                old.job.sha256,
                old.job.size,
                old.job.sources,
                total_bytes=old.job.size,
                state="running",
                principal=principal,
                via_browser=True,
            )
            task = _Task(job, old.spec, old.file)
            place, target = self._upload_target(task, filename)
            token = None
            try:
                self._claim_upload(task, place, target)
                token = activity_tracker().start(
                    principal, "models.download", {"label": job.label, "source": "browser"}
                )
                receiver = UploadReceiver(
                    new_id,
                    target,
                    size=job.size,
                    sha256=job.sha256,
                    cancel=task.cancel,
                    on_progress=lambda d, t: self._progress(task, d, t),
                    place=lambda path, digest: (
                        path if place is not None else self._kept_apart(task, path, digest)
                    ),
                    record=lambda path, digest: self._record_upload(task, place, path, digest),
                    end=lambda state, error: self._end_upload(task, token, state, error),
                )
            except Exception as exc:
                self._writing -= task.claimed
                if not isinstance(exc, OSError):  # A disk refusing a file is no bug; the user gets told.
                    report_failure(exc, operation="Start a model upload", label=job.label)
                if token is not None:
                    activity_tracker().finish(token, ok=False, error=str(exc))
                raise ReceiveRefused(exc.message if isinstance(exc, Refusal) else str(exc)) from exc
            self._tasks[new_id] = task
        self._notify()
        return receiver

    def _upload_target(self, task: _Task, filename: str) -> tuple[_CachePlace | None, Path]:
        """Return the cache place, if any, and the path the upload is meant for."""
        try:
            place = self._cache_place(task)
        except Refusal as exc:
            raise ReceiveRefused(exc.message) from exc
        if place is not None:
            if place.present:
                raise ReceiveRefused("this file is already on this machine")
            return place, place.target
        try:
            root = location_of(MODELS_VOLUME)
            if not root.is_dir():
                raise ReceiveRefused(f"models volume folder does not exist: {root}")
            target = target_path(
                entry=task.spec.entry,
                resource=task.spec.resource,
                file=task.file,
                url=task.job.sources[0],
                sha256=task.job.sha256,
                root=root,
                existing_sha256=self._index.sha256_at,
                name=safe_name(filename),
            )
        except (VolumeError, ValueError, OSError) as exc:
            raise ReceiveRefused(str(exc)) from exc
        return None, target

    def _claim_upload(self, task: _Task, place: _CachePlace | None, target: Path) -> None:
        """Claim *target* under the same key a fetch into that place uses."""
        root = place.root if place is not None else location_of(MODELS_VOLUME)
        relative = target.resolve().relative_to(root.resolve())
        self._claim(task, Path(f"<{place.volume}>") / relative if place is not None else relative)

    def _kept_apart(self, task: _Task, path: Path, digest: str) -> Path:
        """Return where a file with *digest* goes when *path* may hold a different one.

        A declared bundle path stays, as the bundle's layout depends on it.
        """
        if task.file is not None and task.file.path:
            return path
        if not path.exists() or (self._index.sha256_at(path) or sha256_of(path)) == digest:
            return path
        return path.with_name(f"{path.stem}-{digest[:8]}{path.suffix}")

    def _record_upload(self, task: _Task, place: _CachePlace | None, path: Path, digest: str) -> None:
        if place is not None:
            self._record_cache_fetch(task, place, path, digest)
        else:
            job = task.job
            self._index.add(path, digest, source=self._indexed_address(job) or job.sources[0])
        with self._lock:
            task.job.target = path

    def _end_upload(self, task: _Task, token: int | None, state: JobState, error: str | None) -> None:
        with self._lock:
            self._writing -= task.claimed
            task.claimed.clear()
        if token is not None:
            try:
                activity_tracker().finish(
                    token, ok=state == "done", error=error or (state if state != "done" else None)
                )
            except Exception:
                logger.exception("activity tracker failed to finish %s", task.job.id)
        self._finish(task, state, error)

    def _indexed_address(self, job: DownloadJob) -> str | None:
        """The job's first address whose source finds files through the models index."""
        for address in job.sources:
            source = self._sources.lookup(address)
            if source is not None and source.indexed_addresses:
                return address
        return None

    @staticmethod
    def _same_file(a: DownloadJob, b: DownloadJob) -> bool:
        if a.sha256 or b.sha256:
            return a.sha256 == b.sha256
        return a.sources[:1] == b.sources[:1] and a.include == b.include

    # -- planning ------------------------------------------------------------------

    def _plan(self, spec: FetchSpec) -> list[_Plan]:
        """One ``(label, file, sha, size, sources, include)`` per file that is not already local.

        A folder resource (a whole-repo address) plans one entry, or none when its snapshot is on disk.
        """
        plan: list[_Plan] = []
        if spec.entry is not None and spec.resource is not None:
            resource = spec.resource
            if folder_address(resource, self._sources) is not None:
                if locate_resource(resource, self._index, self._sources) is None and resource.urls:
                    first = resource.files[0] if resource.files else None
                    plan.append(
                        (spec.entry.name, first, None, resource.size, resource.urls, resource.include)
                    )
                return plan
            bundle = resource.is_bundle
            label = spec.entry.name
            for mfile in resource.files:
                sha = mfile.sha256 or (None if bundle else resource.sha256)
                size = mfile.size or (None if bundle else resource.size)
                urls = mfile.urls or (() if bundle else resource.urls)
                if sha and self._index.by_sha256(sha) is not None:
                    continue
                cache = cache_of(resource, mfile)
                if cache and find_accepted(cache, sha, self._index, self._sources.cache_source(cache), size):
                    continue
                if urls:
                    plan.append((label, mfile, sha, size, urls, ()))
        elif spec.ref is not None and spec.ref.urls:
            ref = spec.ref
            if names_whole_repo(ref.urls, self._sources):
                return plan
            if not (ref.sha256 and self._index.by_sha256(ref.sha256) is not None):
                plan.append(
                    (
                        ref.label or Path(urlsplit(ref.urls[0]).path).name or ref.urls[0],
                        None,
                        ref.sha256,
                        ref.size,
                        ref.urls,
                        (),
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
        include: tuple[str, ...] = (),
    ) -> str:
        with self._lock:
            for task in self._tasks.values():
                job = task.job
                if job.state not in _ACTIVE:
                    continue
                if (sha is not None and job.sha256 == sha) or (
                    sha is None and job.sources[:1] == sources[:1] and job.include == include
                ):
                    return job.id
            job_id = f"dl-{next(self._ids)}"
            job = DownloadJob(
                job_id, label, sha, size, sources, total_bytes=size, principal=principal, include=include
            )
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
            running = sum(
                1 for t in self._tasks.values() if t.job.state == "running" and not t.job.via_browser
            )
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
        except DownloadCancelled:
            state, error = "cancelled", None
        except Refusal as exc:
            logger.info("download %s failed: %s", job.id, exc.message)
            error = exc.message
        except Exception as exc:
            report_failure(exc, operation="Download a model", label=job.label, source=job.sources[0])
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
        entry = task.spec.entry
        last_error = "no source"
        place = self._cache_place(task)
        resource = task.spec.resource
        is_folder = resource is not None and folder_address(resource, self._sources) is not None
        if place is not None and place.present:
            with self._lock:
                job.target = place.target
            return
        for position, address in enumerate(job.sources):
            if task.cancel.is_set():
                raise DownloadCancelled(address)
            source = self._sources.lookup(address)
            if source is None:
                prefix = prefix_of(address)
                last_error = f"source unavailable: {prefix}:// not provided ({address})"
                continue
            if is_folder and not source.names_folder(address):
                last_error = f"not a folder address ({address})"
                continue
            if place is not None:
                if not source.fills_target:
                    last_error = f"{source.name}:// cannot fill a cache ({address})"
                    continue
                root = place.root
            else:
                found_root = source.root()
                if found_root is None:
                    last_error = f"{source.volume_noun} unavailable: {source.root_problem()} ({address})"
                    continue
                root = found_root
            request = FetchRequest(
                address=address,
                root=root,
                sha256=job.sha256,
                size=job.size,
                entry=entry,
                resource=task.spec.resource,
                file=task.file,
                on_progress=lambda d, t: self._progress(task, d, t),
                cancel=task.cancel,
                claim=(
                    (lambda relative: self._claim(task, Path(f"<{place.volume}>") / relative))
                    if place is not None
                    else (lambda relative: self._claim(task, relative))
                ),
                fresh=position > 0,
                target=place.target if place is not None else None,
            )
            with self._lock:
                changed = job.cancellable != source.cancels_running
                job.cancellable = source.cancels_running
            if changed:
                self._notify()
            try:
                path = source.fetch(request)
            except (SourceFailed, httpx.HTTPError, httpx.InvalidURL, OSError) as exc:
                last_error = f"{exc} ({address})"
                continue
            if place is not None:
                self._record_cache_fetch(task, place, path, request.result_sha256 or job.sha256 or "")
            with self._lock:
                job.target = path
            return
        raise Refusal(last_error)

    def _record_cache_fetch(self, task: _Task, place: _CachePlace, path: Path, sha256: str) -> None:
        entry = task.spec.entry
        if self._records is None or entry is None:
            return
        try:
            self._records.add(
                FetchRecord(
                    place.volume,
                    place.relative,
                    sha256,
                    entry.class_identity.registry_key,
                    place.address,
                    path.stat().st_size,
                )
            )
        except OSError:
            logger.warning("could not record the fetch of %s", path, exc_info=True)

    def _cache_place(self, task: _Task) -> _CachePlace | None:
        """Prepare the task file's cache volume and return where the file goes; ``None`` without a cache.

        Raises ``Refusal`` when the cache cannot be written, or holds a file this
        queue did not fetch.
        """
        resource, mfile = task.spec.resource, task.file
        cache = cache_of(resource, mfile) if resource is not None and mfile is not None else None
        if cache is None:
            return None
        source = self._sources.cache_source(cache)
        if source is None:
            raise Refusal(f"source unavailable: {prefix_of(cache)}:// not provided")
        try:
            root = source.prepare_root()
            relative = source.relative(cache)
            target = source.target(cache)
        except (ValueError, SourceFailed) as exc:
            raise Refusal(str(exc)) from exc
        except Exception as exc:
            raise Refusal(f"{source.volume_noun} unavailable: {source.root_problem() or exc}") from exc
        if target is None:
            raise Refusal(f"not a path inside the {source.label} cache: {cache}")
        if target.is_file() and not self._recorded(source.volume, relative, target):
            if not accepts(target, task.job.sha256, source, self._index, task.job.size):
                raise Refusal(f"a different file already exists at {target}")
            return _CachePlace(source.volume, root, relative, target, cache, present=True)
        return _CachePlace(source.volume, root, relative, target, cache)

    def _recorded(self, volume: str, relative: str, path: Path) -> bool:
        """Whether a fetch record of the file at *path* still matches its size."""
        if self._records is None:
            return False
        try:
            size = path.stat().st_size
        except OSError:
            logger.warning("cannot read the size of %s; treated as unrecorded", path, exc_info=True)
            return False
        return any(r.current(size) for r in self._records.at(volume, relative))

    def _claim(self, task: _Task, relative: Path) -> None:
        with self._lock:
            if relative not in task.claimed:
                if relative in self._writing:
                    raise Refusal(f"another download is writing {relative.as_posix()}")
                self._writing.add(relative)
                task.claimed.add(relative)
