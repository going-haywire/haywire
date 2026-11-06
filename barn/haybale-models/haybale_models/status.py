"""The status text of a catalog resource, shared by the Models editor and the Farmhand tools."""

from __future__ import annotations

from collections.abc import Sequence

from haybale_models.download import DownloadJob

__all__ = ["resource_status"]


def _percent(done: int, total: int | None) -> int:
    return min(100, int(100 * done / total)) if total else 0


def resource_status(
    place: str | None, matching: Sequence[DownloadJob], *, unavailable: str | None = None
) -> str:
    """Return the status text: the place of the files (``local``, ``HF cache``, ``Torch Hub cache``…).

    Otherwise ``queued``, ``downloading N %``, ``downloading…``, ``uploading N %`` or ``uploading…``.

    Otherwise ``failed: …`` or ``not downloaded``.

    Args:
        place: The ``ModelSource.place`` of the found files, or ``None`` when not found.
        matching: The download jobs that fetch a file of the resource.
        unavailable: The address prefix no model source serves (``SourceSet.unavailable``), if any;
            the status then reads ``source unavailable: <prefix>:// not provided``.
    """
    if place:
        return place
    if unavailable:
        return f"source unavailable: {unavailable}:// not provided"
    active = [j for j in matching if j.state in ("queued", "running")]
    if active:
        if all(j.state == "queued" for j in active):
            return "queued"
        done = sum(j.done_bytes for j in active)
        total = sum(j.total_bytes or j.size or 0 for j in active)
        if any(j.via_browser for j in active):
            return f"uploading {_percent(done, total)} %" if done > 0 else "uploading…"
        if done <= 0:
            return "downloading…"  # no byte count yet (queued behind a size probe, or a Xet transfer)
        return f"downloading {_percent(done, total)} %"
    if matching and matching[-1].state == "failed":
        return f"failed: {matching[-1].error or 'unknown error'}"
    return "not downloaded"
