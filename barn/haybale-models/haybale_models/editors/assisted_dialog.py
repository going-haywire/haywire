"""The dialog of an assisted download: where to get each failed file, and a drop zone to hand it over."""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from dataclasses import dataclass, field
from pathlib import PurePosixPath
from typing import TYPE_CHECKING

from haywire.ui import elements as hui
from haywire.ui.modals import confirm_modal
from nicegui import ui

from haybale_models.download import DownloadJob, DownloadQueue
from haybale_models.needs import format_size
from haybale_models.status import resource_status
from haybale_models.upload_route import NAME_HEADER, UploadRoute, mount_upload_route

if TYPE_CHECKING:
    from haybale_models.states.models_state import ModelsState

NO_DIGEST_NOTICE = "No digest in the catalog: this file can't be verified."
_ACTIVE = ("queued", "running")
_REFRESH_S = 0.25


def assisted_slots(queue: DownloadQueue, jobs: Iterable[DownloadJob]) -> list[DownloadJob]:
    """Return the *jobs* a person can finish through their browser, the newest one per file."""
    newest: dict[tuple[str | None, tuple[str, ...]], DownloadJob] = {}
    for job in jobs:
        if queue.assistable(job.id):
            newest[(job.sha256, job.sources)] = job
    return list(newest.values())


@dataclass
class _Slot:
    """One failed file in the dialog."""

    job: DownloadJob
    route: UploadRoute
    upload: ui.upload
    status: ui.label
    upload_id: str | None = None
    refusal: str | None = None
    settled: set[str] = field(default_factory=set)


def _links(models: ModelsState, job: DownloadJob) -> None:
    """Draw one link per address that has a web page."""
    with ui.row().classes("w-full items-center gap-2"):
        for address in job.sources:
            url = models.sources.page_url(address)
            if url is not None:
                host = address.partition("://")[2].partition("/")[0]
                ui.link(host or address, url, new_tab=True).mark("assisted-link").tooltip(address)


def _describe(job: DownloadJob) -> None:
    """Draw what identifies the file: its size and digest, or that it has no digest."""
    if job.size is not None:
        hui.hint(format_size(job.size))
    if job.sha256:
        hui.hint(f"sha256 {job.sha256}").classes("font-mono break-all")
    else:
        hui.hint(NO_DIGEST_NOTICE).mark("assisted-no-digest")


def _slot_text(slot: _Slot, by_id: dict[str, DownloadJob]) -> str:
    """Return the status line of *slot*."""
    if slot.refusal is not None:
        return slot.refusal
    job = by_id.get(slot.upload_id) if slot.upload_id is not None else None
    if job is None:
        return slot.job.error or ""
    if job.state == "done" and job.target is not None:
        return f"✓ stored as {PurePosixPath(job.target).name}"
    if job.state == "cancelled":
        return "cancelled"
    return resource_status(None, [job])


def _draw_slot(models: ModelsState, principal: str | None, job: DownloadJob) -> _Slot:
    """Draw the slot of the failed *job* and mount its upload route."""
    hui.subject(job.label).classes("w-full truncate")
    _describe(job)
    _links(models, job)
    route_ready: list[_Slot] = []

    def began(upload_id: str) -> None:
        route_ready[0].upload_id = upload_id
        route_ready[0].refusal = None

    def refused(reason: str) -> None:
        route_ready[0].refusal = reason

    route = mount_upload_route(models.queue, job.id, principal, on_begin=began, on_refused=refused)
    upload = ui.upload(auto_upload=True, max_files=1, label="Drop the file here").classes("w-full")
    upload._props["url"] = route.url
    upload.props("send-raw")
    upload.props(
        f""":headers="files => [{{name: '{NAME_HEADER}', value: encodeURIComponent(files[0].name)}}]" """
    )
    # A refused file stays listed in the uploader and would block the next drop.
    upload.on("failed", lambda: upload.run_method("reset"))
    upload.mark("assisted-upload")
    status = hui.hint(job.error or "").classes("break-words").mark("assisted-status")
    slot = _Slot(job, route, upload, status)
    route_ready.append(slot)
    return slot


def open_assisted_dialog(models: ModelsState, principal: str | None, jobs: Sequence[DownloadJob]) -> None:
    """Open the dialog offering each failed job in *jobs* a drop zone and its web pages.

    Parented to the page, so a redraw of the editor leaves a running upload alone. Closing the dialog
    stops its uploads, after a confirmation while one is running.

    Args:
        models: The models state, for its queue and model sources.
        principal: Who uploads; re-checked for admin access on every upload.
        jobs: Jobs from :func:`assisted_slots`.
    """
    client = ui.context.client
    slots: list[_Slot] = []

    def running() -> list[str]:
        ids = {j.id for j in models.queue.jobs() if j.state in _ACTIVE}
        return [s.upload_id for s in slots if s.upload_id in ids]

    def stop() -> None:
        for slot in slots:
            slot.route.unmount()
            if slot.upload_id is not None:
                models.queue.cancel(slot.upload_id)

    def close() -> None:
        active = bool(running())
        stop()
        if active:
            for slot in slots:
                slot.upload.run_method("abort")
        timer.cancel()
        dialog.delete()

    def ask_to_close() -> None:
        if running():
            confirm_modal(
                title="Stop the upload?",
                message="Closing this dialog stops the upload. The partly received file is deleted.",
                confirm_label="Stop upload",
                danger=True,
                on_confirm=close,
            )
        else:
            close()

    def refresh() -> None:
        by_id = {j.id: j for j in models.queue.jobs()}
        for slot in slots:
            slot.status.set_text(_slot_text(slot, by_id))
            job = by_id.get(slot.upload_id) if slot.upload_id is not None else None
            if job is not None and job.state == "done" and job.id not in slot.settled:
                slot.settled.add(job.id)
                slot.upload.set_visibility(False)

    with client.layout, ui.dialog().props("persistent") as dialog, hui.dialog_card("w-[560px]"):
        hui.heading("Download in browser")
        hui.hint("Get the file from one of these pages, then drop it here.")
        for job in jobs:
            with ui.column().classes("w-full gap-1 py-2").mark("assisted-slot"):
                slots.append(_draw_slot(models, principal, job))
        with hui.action_row().classes("mt-2"):
            ui.button("Close", on_click=ask_to_close).props("flat dense").mark("assisted-close")
        timer = ui.timer(_REFRESH_S, refresh)
    client.on_delete(stop)
    dialog.open()


__all__ = ["NO_DIGEST_NOTICE", "assisted_slots", "open_assisted_dialog"]
