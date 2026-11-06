"""The HTTP route an assisted download's drop zone posts a file to."""

from __future__ import annotations

import asyncio
import secrets
from collections.abc import AsyncIterator, Callable
from dataclasses import dataclass
from urllib.parse import unquote

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from nicegui import app as nicegui_app
from starlette.requests import ClientDisconnect

from haywire.core.access.resolver import resolve_tier
from haywire.core.access.tier import AccessTier
from haywire.core.errors import report_failure

from haybale_models.download import DownloadQueue
from haybale_models.receive import ReceiveRefused, UploadReceiver
from haybale_models.sources import DownloadCancelled, SourceFailed

NAME_HEADER = "X-Hw-File-Name"
"""The request header holding the uploaded file's percent-encoded name."""

_MIN_WRITE = 1024 * 1024
_POLL_S = 0.25
_IDLE_TIMEOUT_S = 60.0


@dataclass(frozen=True)
class UploadRoute:
    """A mounted upload route: where to post, and how to take it down again."""

    url: str
    app: FastAPI

    def unmount(self) -> None:
        """Remove the route. Idempotent."""
        self.app.router.routes[:] = [
            route for route in self.app.router.routes if getattr(route, "path", None) != self.url
        ]


class _Stalled(Exception):
    """No bytes arrived for ``_IDLE_TIMEOUT_S``."""


async def _next_or_none(stream: AsyncIterator[bytes]) -> bytes | None:
    """Return the stream's next piece, or ``None`` at its end."""
    return await anext(stream, None)


async def _coalesced(receiver: UploadReceiver, request: Request) -> AsyncIterator[bytes]:
    """Yield the raw body in pieces of at least ``_MIN_WRITE`` bytes, the last one aside.

    Raises ``DownloadCancelled`` once the job is cancelled and ``_Stalled`` when the connection goes
    silent, as a connection that dies without closing raises nothing by itself.
    """
    stream = request.stream()
    pending = bytearray()
    while True:
        read = asyncio.ensure_future(_next_or_none(stream))
        waited = 0.0
        try:
            while not read.done():
                await asyncio.wait({read}, timeout=_POLL_S)
                waited += _POLL_S
                if receiver.cancelled:
                    raise DownloadCancelled(receiver.job_id)
                if not read.done() and waited >= _IDLE_TIMEOUT_S:
                    raise _Stalled()
        finally:
            if not read.done():
                read.cancel()
        chunk = read.result()
        if chunk is None:
            break
        pending += chunk
        if len(pending) >= _MIN_WRITE:
            yield bytes(pending)
            pending.clear()
    if pending:
        yield bytes(pending)


def _report(receiver: UploadReceiver, exc: Exception) -> JSONResponse:
    """Record an unexpected exception in the error ledger and end the upload's job."""
    report_failure(exc, operation="Receive a model upload", job=receiver.job_id)
    error = str(exc) or type(exc).__name__
    receiver.abort(error)
    return JSONResponse({"error": error}, status_code=422)


async def _receive(receiver: UploadReceiver, request: Request) -> JSONResponse:
    """Stream the request into *receiver*; every outcome leaves the upload's job ended."""
    try:
        async for chunk in _coalesced(receiver, request):
            await asyncio.to_thread(receiver.write, chunk)
        await asyncio.to_thread(receiver.finish)
    except ClientDisconnect:
        receiver.abort()
        return JSONResponse({"error": "the connection was lost"}, status_code=400)
    except asyncio.CancelledError:
        receiver.abort()
        raise
    except DownloadCancelled:
        receiver.abort()
        return JSONResponse({"error": "cancelled"}, status_code=409)
    except _Stalled:
        error = f"no data for {_IDLE_TIMEOUT_S:g} s: the upload stalled"
        receiver.abort(error)
        return JSONResponse({"error": error}, status_code=408)
    except (SourceFailed, OSError) as exc:
        receiver.abort(str(exc))
        return JSONResponse({"error": str(exc)}, status_code=422)
    except Exception as exc:  # A job must not stay running, whatever went wrong.
        return _report(receiver, exc)
    return JSONResponse({"ok": True})


def mount_upload_route(
    queue: DownloadQueue,
    job_id: str,
    principal: str | None,
    *,
    on_begin: Callable[[str], object] | None = None,
    on_refused: Callable[[str], object] | None = None,
    app: FastAPI = nicegui_app,
) -> UploadRoute:
    """Mount a route at an unguessable address that takes one file for the failed job *job_id*.

    The route takes the file as the raw request body, with its name in ``NAME_HEADER``. It answers
    403 when *principal* no longer holds ADMIN, 409 when the upload is refused or cancelled, 408 when
    the connection stays silent for a minute, 422 when the file is the wrong one (the body says what
    was expected), and 200 when the file is stored. It can be posted to again after a refusal. Unmount
    it when done.

    Args:
        queue: The queue that owns the jobs.
        job_id: A job for which ``DownloadQueue.assistable`` holds.
        principal: Who may post, as named at the time the route is mounted.
        on_begin: Called with the upload's own job id, before the body is read.
        on_refused: Called with the reason when a post gets no job (403, or 409 before it starts).
        app: The application to mount on.
    """
    url = f"/_haybale_models/upload/{secrets.token_urlsafe(32)}"

    async def upload(request: Request) -> JSONResponse:
        if not resolve_tier(principal).satisfies(AccessTier.ADMIN):
            if on_refused is not None:
                on_refused("This needs admin access.")
            return JSONResponse({"error": "this needs admin access"}, status_code=403)
        name = unquote(request.headers.get(NAME_HEADER, ""))
        try:
            receiver = queue.begin_receive(job_id, name, principal)
        except ReceiveRefused as exc:
            if on_refused is not None:
                on_refused(str(exc))
            return JSONResponse({"error": str(exc)}, status_code=409)
        if on_begin is not None:
            try:
                on_begin(receiver.job_id)
            except Exception as exc:
                return _report(receiver, exc)
        expected = next((j.size for j in queue.jobs() if j.id == receiver.job_id), None)
        length = request.headers.get("content-length", "")
        if expected is not None and length.isdigit() and int(length) != expected:
            error = f"size mismatch: got {length} bytes, expected {expected}"
            receiver.abort(error)
            return JSONResponse({"error": error}, status_code=422)
        return await _receive(receiver, request)

    app.add_api_route(url, upload, methods=["POST"], include_in_schema=False)
    return UploadRoute(url, app)
