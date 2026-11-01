"""The status text of a catalog resource, shared by the Models editor and the Farmhand tools."""

from __future__ import annotations

from collections.abc import Sequence

from haybale_models.download import DownloadJob

__all__ = ["resource_status"]


def _percent(done: int, total: int | None) -> int:
    return min(100, int(100 * done / total)) if total else 0


def resource_status(local: bool, in_hf: bool, matching: Sequence[DownloadJob]) -> str:
    """Return the status text: ``local``, ``HF cache``, ``queued``, ``downloading N %`` or ``downloading…``.

    Otherwise ``failed: …`` or ``not downloaded``.

    Args:
        local: Every file of the resource is in the models volume.
        in_hf: Every file is found, in the Hugging Face cache.
        matching: The download jobs that fetch a file of the resource.
    """
    if local:
        return "local"
    if in_hf:
        return "HF cache"
    active = [j for j in matching if j.state in ("queued", "running")]
    if active:
        if all(j.state == "queued" for j in active):
            return "queued"
        done = sum(j.done_bytes for j in active)
        total = sum(j.total_bytes or j.size or 0 for j in active)
        if done <= 0:
            return "downloading…"  # no byte count yet (queued behind a size probe, or a Xet transfer)
        return f"downloading {_percent(done, total)} %"
    if matching and matching[-1].state == "failed":
        return f"failed: {matching[-1].error or 'unknown error'}"
    return "not downloaded"
