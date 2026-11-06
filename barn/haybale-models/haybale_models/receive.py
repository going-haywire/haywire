"""Receiving a model file through an upload: the bytes come from outside, the checks stay the same."""

from __future__ import annotations

import hashlib
import threading
from collections.abc import Callable
from pathlib import Path
from typing import BinaryIO, Literal

from haywire.core.errors import Refusal

from haybale_models.sources import DownloadCancelled, SourceFailed
from haybale_models.sources.base import finish_part


class ReceiveRefused(Refusal):
    """The upload cannot start; the message says why, in words for the user."""


class UploadReceiver:
    """One file arriving through an upload, written to ``<target>.part`` and checked at the end.

    Calls come one at a time: :meth:`write` for each chunk, then :meth:`finish`, or :meth:`abort` at
    any point. Get one from ``DownloadQueue.begin_receive``.

    Example::

        receiver = queue.begin_receive(failed_job_id, "w.pth", principal)
        try:
            for chunk in chunks:
                receiver.write(chunk)
            path = receiver.finish()
        except DownloadCancelled:
            receiver.abort()  # the job ends cancelled
        except SourceFailed:
            pass  # the job already ended failed, with what was expected
    """

    def __init__(
        self,
        job_id: str,
        target: Path,
        *,
        size: int | None,
        sha256: str | None,
        cancel: threading.Event,
        on_progress: Callable[[int, int | None], None],
        place: Callable[[Path, str], Path],
        record: Callable[[Path, str], None],
        end: Callable[[Literal["done", "failed", "cancelled"], str | None], None],
    ) -> None:
        """Open the ``.part`` file.

        Args:
            job_id: The id of the job this upload runs as.
            target: Where the file is meant to end up.
            size: The expected size in bytes, or ``None`` when unknown.
            sha256: The expected sha256 hex, or ``None`` when unknown.
            cancel: Once set, the next :meth:`write` raises ``DownloadCancelled``.
            on_progress: Called with the bytes received and the expected total.
            place: Given *target* and the computed digest, returns the final path.
            record: Called with the final path and digest, after the file is in place.
            end: Called once with the job's final state and error.

        Raises:
            OSError: The ``.part`` file cannot be created.
        """
        self.job_id = job_id
        self._target = target
        self._part = target.with_name(target.name + ".part")
        self._size = size
        self._sha256 = sha256
        self._cancel = cancel
        self._on_progress = on_progress
        self._place = place
        self._record = record
        self._end = end
        self._hasher = hashlib.sha256()
        self._done = 0
        self._ended = False
        target.parent.mkdir(parents=True, exist_ok=True)
        self._out: BinaryIO | None = self._part.open("wb")

    @property
    def cancelled(self) -> bool:
        """Whether the job was asked to stop. Call :meth:`abort`."""
        return self._cancel.is_set()

    def write(self, chunk: bytes) -> None:
        """Append *chunk*.

        Raises:
            DownloadCancelled: The job was cancelled. Call :meth:`abort`.
            SourceFailed: More bytes than expected arrived; the job has ended failed.
            OSError: The disk refused them; the job has ended failed.
        """
        if self._cancel.is_set():
            raise DownloadCancelled(self.job_id)
        if self._size is not None and self._done + len(chunk) > self._size:
            error = SourceFailed(f"size mismatch: got over {self._size} bytes, expected {self._size}")
            self.abort(str(error))
            raise error
        assert self._out is not None
        try:
            self._out.write(chunk)
        except OSError as exc:
            self.abort(str(exc))
            raise
        self._hasher.update(chunk)
        self._done += len(chunk)
        self._on_progress(self._done, self._size)

    def finish(self) -> Path:
        """Check the file, move it into place and record it; returns its final path.

        Raises:
            SourceFailed: Size or digest differ; the job has ended failed, with what was expected.
            OSError: The file could not be moved; the job has ended failed.
        """
        digest = self._hasher.hexdigest()
        try:
            self._close()
            path = self._place(self._target, digest)
            path.parent.mkdir(parents=True, exist_ok=True)
            finish_part(self._part, path, digest=digest, size=self._size, sha256=self._sha256)
            self._record(path, digest)
        except (SourceFailed, OSError) as exc:
            self.abort(str(exc))
            raise
        self._ended = True
        self._end("done", None)
        return path

    def abort(self, error: str | None = None) -> None:
        """Delete the ``.part`` file and end the job: cancelled, or failed with *error*. Idempotent."""
        if self._ended:
            return
        self._ended = True
        try:
            self._close()
        except OSError:
            pass  # A failing flush changes nothing: the file is being thrown away.
        self._part.unlink(missing_ok=True)
        self._end("failed" if error else "cancelled", error)

    def _close(self) -> None:
        out, self._out = self._out, None
        if out is not None:
            out.close()
