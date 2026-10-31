"""Server side of the image viewer.

- ``StreamingBackend``: an MJPEG route fed from a one-frame queue, for images that
  change many times a second.
- ``StillBackend``: a route that encodes the latest image to PNG when the browser
  asks for it, for large images that change rarely.
- ``ImageViewer``: the NiceGUI element that shows either route.

The backends are plain objects, not elements: their routes outlive a card redraw
until ``cleanup()`` removes them. Every route sits behind the studio's login gate.
"""

from __future__ import annotations

import asyncio
import logging
import uuid
from functools import partial
from queue import Empty, Full, Queue
from typing import Any, Optional

import cv2
import numpy as np
from fastapi import Request, Response
from fastapi.responses import StreamingResponse
from nicegui import app
from nicegui.element import Element

from haybale_image.value import ChannelOrder, ImageValue, Layout, convert_layout

logger = logging.getLogger(__name__)


def _remove_route(endpoint: str) -> None:
    app.routes[:] = [r for r in app.routes if getattr(r, "path", None) != endpoint]


class StreamingBackend:
    """Server-side MJPEG pipeline: a route, a frame queue and the task that feeds viewers.

    ``stream()`` encodes an image to JPEG and queues it. While no viewer has opened
    the route, ``stream()`` does nothing; with ``block_on_full`` off a full queue
    drops its oldest frame, so a slow viewer always gets the latest one.

    Args:
        endpoint: HTTP path of the stream; ``None`` makes a unique ``/stream/<id>``.
        quality: JPEG quality, 0 to 100.
        frame_queue_size: Frames buffered between the producer and the viewers.
        block_on_full: Wait up to 0.1 s for room in a full queue instead of
            dropping its oldest frame.

    Example::

        backend = StreamingBackend(quality=85)
        backend.stream(image)      # from any thread; JPEG-encodes once a viewer is open
        backend.cleanup()          # removes the route
    """

    def __init__(
        self,
        endpoint: str | None = None,
        quality: int = 80,
        frame_queue_size: int = 1,
        block_on_full: bool = False,
    ) -> None:
        if endpoint is None:
            endpoint = f"/stream/{uuid.uuid4().hex[:8]}"

        self.endpoint = endpoint
        self.quality = quality
        self.frame_queue_size = frame_queue_size
        self.block_on_full = block_on_full

        self.latest_frame: bytes | None = None
        self.frame_id: int = 0
        self.cond: asyncio.Condition = asyncio.Condition()

        self._thread_queue: Queue[bytes] = Queue(maxsize=self.frame_queue_size)
        self._queue_reader_task: Optional[asyncio.Task] = None
        self._is_running = False

        self._register_endpoint()

    def _ensure_queue_reader(self) -> None:
        """Start the queue reader task if it is not running.

        Raises:
            RuntimeError: No event loop runs in this thread.
        """
        if self._queue_reader_task is None or self._queue_reader_task.done():
            loop = asyncio.get_running_loop()  # raises before a coroutine is made that nobody awaits
            self._is_running = True
            self._queue_reader_task = loop.create_task(self._queue_reader_loop())

    async def _queue_reader_loop(self) -> None:
        """Move frames from the thread queue to ``latest_frame`` and wake the viewers."""

        def get_with_timeout() -> bytes | None:
            try:
                return self._thread_queue.get(block=True, timeout=0.1)
            except Empty:
                return None

        try:
            while self._is_running:
                try:
                    data = await asyncio.to_thread(get_with_timeout)
                    if not self._is_running:
                        break
                    if data is None:
                        await asyncio.sleep(0.01)
                        continue
                    async with self.cond:
                        self.latest_frame = data
                        self.frame_id += 1
                        self.cond.notify_all()
                except asyncio.CancelledError:
                    break
                except Exception:
                    logger.debug("stream queue reader error", exc_info=True)
                    if not self._is_running:
                        break
                    await asyncio.sleep(0.01)
        finally:
            self._is_running = False

    def stream(self, img: ImageValue) -> None:
        """Encode ``img`` as JPEG and queue it for the viewers.

        Does nothing for an empty image or while no viewer has opened the route.
        RGBA images lose their alpha. Safe to call from any thread.
        """
        if img.is_empty:
            return
        if not self._is_running:
            try:
                self._ensure_queue_reader()
            except RuntimeError:
                return  # a worker thread: the route starts the reader when a viewer connects
        try:
            if img.layout is Layout.RGBA:
                img = convert_layout(img, Layout.RGB)
            ok, buf = cv2.imencode(
                ".jpg",
                img.array(np.uint8, ChannelOrder.BGR),
                [cv2.IMWRITE_JPEG_QUALITY, self.quality],
            )
            if not ok:
                return
            data = buf.tobytes()
            if self.block_on_full:
                try:
                    self._thread_queue.put(data, timeout=0.1)
                except Full:
                    pass
            else:
                try:
                    self._thread_queue.put_nowait(data)
                except Full:
                    try:
                        self._thread_queue.get_nowait()
                        self._thread_queue.put_nowait(data)
                    except (Empty, Full):
                        pass
        except Exception:
            if self._is_running:
                logger.warning("stream error", exc_info=True)

    def _has_frame_after(self, seen: int) -> bool:
        return self.frame_id > seen

    def _register_endpoint(self) -> None:
        @app.get(self.endpoint)
        async def mjpeg_endpoint(request: Request) -> StreamingResponse:
            self._ensure_queue_reader()

            async def generator() -> Any:
                last_id = 0
                try:
                    while True:
                        if await request.is_disconnected():
                            break
                        try:
                            async with self.cond:
                                await asyncio.wait_for(
                                    self.cond.wait_for(partial(self._has_frame_after, last_id)),
                                    timeout=5.0,
                                )
                                last_id = self.frame_id
                                frame = self.latest_frame
                        except asyncio.TimeoutError:
                            continue
                        if not frame:
                            continue
                        yield (
                            b"--frame\r\n"
                            b"Content-Type: image/jpeg\r\n"
                            b"Content-Length: " + str(len(frame)).encode() + b"\r\n\r\n" + frame + b"\r\n"
                        )
                except asyncio.CancelledError:
                    return
                except Exception:
                    logger.warning("stream client error", exc_info=True)

            return StreamingResponse(generator(), media_type="multipart/x-mixed-replace; boundary=frame")

    def cleanup(self) -> None:
        """Stop the reader task, drop queued frames and remove the route."""
        self._is_running = False
        if self._queue_reader_task and not self._queue_reader_task.done():
            self._queue_reader_task.cancel()
        while True:
            try:
                self._thread_queue.get_nowait()
            except Empty:
                break
        _remove_route(self.endpoint)


class StillBackend:
    """A route serving the latest shown image as PNG, encoded when the browser asks.

    ``show()`` only keeps a reference to the image, so showing an image costs
    nothing until a viewer fetches it. The PNG is 8-bit and keeps alpha. The
    route answers 204 while no image, or an empty one, is shown, and its
    responses are never cached: viewers fetch ``<endpoint>?v=<version>``.

    Args:
        endpoint: HTTP path of the image; ``None`` makes a unique ``/still/<id>``.

    Example::

        backend = StillBackend()
        version = backend.show(image)   # from any thread; no encoding
        src = f"{backend.endpoint}?v={version}"
        backend.cleanup()               # removes the route
    """

    def __init__(self, endpoint: str | None = None) -> None:
        if endpoint is None:
            endpoint = f"/still/{uuid.uuid4().hex[:8]}"
        self.endpoint = endpoint
        self.version = 0
        self._image: ImageValue | None = None

        # A sync handler: FastAPI runs it in its thread pool, so a large encode never blocks the loop.
        @app.get(self.endpoint)
        def still_endpoint() -> Response:
            return self.response()

    def show(self, img: ImageValue) -> int:
        """Keep ``img`` as the image the route serves; return the new version number."""
        self._image = img  # one assignment: a request encodes either the old or the new image
        self.version += 1
        return self.version

    def response(self) -> Response:
        """Return the route's response: the shown image as PNG, or 204 when there is none."""
        img = self._image
        if img is None or img.is_empty:
            return Response(status_code=204, headers={"Cache-Control": "no-store"})
        ok, buf = cv2.imencode(
            ".png",
            img.array(np.uint8, ChannelOrder.BGR),
            [cv2.IMWRITE_PNG_COMPRESSION, 1],  # a preview: fast over small
        )
        if not ok:
            return Response(status_code=500, headers={"Cache-Control": "no-store"})
        return Response(buf.tobytes(), media_type="image/png", headers={"Cache-Control": "no-store"})

    def cleanup(self) -> None:
        """Drop the image and remove the route."""
        self._image = None
        _remove_route(self.endpoint)


class ImageViewer(Element, component="image_viewer.js"):
    """An ``<img>`` showing a ``StreamingBackend`` stream or a ``StillBackend`` image.

    Args:
        backend: The route to show; its type picks the mode.
    """

    def __init__(self, backend: StreamingBackend | StillBackend) -> None:
        super().__init__()
        self._props["endpoint"] = backend.endpoint
        self._props["mode"] = "still" if isinstance(backend, StillBackend) else "stream"
        self._props["version"] = 0

    def set_version(self, version: int) -> None:
        """Make the viewer fetch the still image ``version``; 0 shows no image."""
        self._props["version"] = version
        self.update()
