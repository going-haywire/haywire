"""
Custom Streaming Viewer Component for Haywire Widgets

Based on duit's OpencvViewer but adapted to work within widget lifecycle
without requiring app.on_startup decorator.
"""

import asyncio
import uuid
from queue import Queue, Full
from typing import Optional

import numpy as np
from fastapi import Request
from fastapi.responses import StreamingResponse
from nicegui import app
from nicegui.element import Element


class StreamingViewer(Element, component="opencv_viewer.js"):
    """
    NiceGUI component for MJPEG streaming of numpy image arrays.

    Adapted from duit's OpencvViewer to work within Haywire's widget system
    by managing the background task lifecycle explicitly instead of using
    app.on_startup decorator.

    :param endpoint: HTTP endpoint for the MJPEG stream (default: random id is generated).
    :param quality: JPEG compression quality (0-100, higher is better quality, default: 80).
    :param frame_queue_size: Maximum number of frames to buffer (default: 1).
    :param block_on_full: If True, block the producer when the queue is full;
                          if False, drop the oldest frame when full (default: False).
    """

    def __init__(
        self,
        endpoint: str | None = None,
        quality: int = 80,
        frame_queue_size: int = 1,
        block_on_full: bool = False,
    ):
        super().__init__()

        # Generate a new random endpoint for this component
        if endpoint is None:
            endpoint_id = uuid.uuid4().hex[:8]
            endpoint = f"/stream/{endpoint_id}"

        self._props["endpoint"] = endpoint
        self.endpoint = endpoint
        self.quality = quality
        self.frame_queue_size = frame_queue_size
        self.block_on_full = block_on_full

        # Shared state for latest frame broadcast
        self.latest_frame: bytes | None = None
        self.frame_id: int = 0
        self.cond: asyncio.Condition = asyncio.Condition()

        # Thread-safe queue holding JPEG bytes
        self._thread_queue: Queue[bytes] = Queue(maxsize=self.frame_queue_size)

        # Background task handle
        self._queue_reader_task: Optional[asyncio.Task] = None
        self._is_running = False

        # Register the HTTP endpoint
        self._register_endpoint()

    def _ensure_queue_reader(self) -> None:
        """Ensure the background queue reader task is running.

        Called lazily from the endpoint handler or stream(), not from __init__,
        because __init__ may run before the event loop is started.
        """
        if self._queue_reader_task is None or self._queue_reader_task.done():
            self._is_running = True
            self._queue_reader_task = asyncio.create_task(self._queue_reader_loop())

    async def _queue_reader_loop(self) -> None:
        """Background task: pull from thread queue, update shared frame, notify viewers"""
        from queue import Empty

        try:
            while self._is_running:
                try:

                    def get_with_timeout():
                        try:
                            return self._thread_queue.get(block=True, timeout=0.1)
                        except Empty:
                            return None

                    data = await asyncio.to_thread(get_with_timeout)

                    if data is None:
                        if not self._is_running:
                            break
                        await asyncio.sleep(0.01)
                        continue

                    if not self._is_running:
                        break

                    async with self.cond:
                        self.latest_frame = data
                        self.frame_id += 1
                        self.cond.notify_all()

                except asyncio.CancelledError:
                    break
                except Exception:
                    if not self._is_running:
                        break
                    await asyncio.sleep(0.01)

        except asyncio.CancelledError:
            pass
        except Exception:
            pass
        finally:
            self._is_running = False

    def stream(self, frame: np.ndarray) -> None:
        """
        Push an OpenCV BGR frame into the streaming pipeline.

        :param frame: OpenCV image (BGR numpy array) to encode and enqueue.
        """
        # Lazily start the queue reader if needed
        if not self._is_running:
            try:
                self._ensure_queue_reader()
            except RuntimeError:
                pass  # No event loop in this thread - endpoint handler will start it

        import cv2

        try:
            success, buf = cv2.imencode(".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, self.quality])
            if not success:
                return
            data = buf.tobytes()

            if not self._is_running:
                return

            if self.block_on_full:
                try:
                    self._thread_queue.put(data, timeout=0.1)
                except Exception:
                    pass
            else:
                try:
                    self._thread_queue.put_nowait(data)
                except Full:
                    try:
                        _ = self._thread_queue.get_nowait()
                        self._thread_queue.put_nowait(data)
                    except Exception:
                        pass

        except Exception as e:
            if self._is_running:
                print(f"[StreamingViewer] Stream error: {e}")

    def _register_endpoint(self) -> None:
        """Register the HTTP endpoint for MJPEG streaming"""

        @app.get(self.endpoint)
        async def mjpeg_endpoint(request: Request):
            """HTTP endpoint that streams multipart MJPEG to clients"""
            self._ensure_queue_reader()
            boundary = "--frame"

            async def generator():
                """Async generator yielding JPEG frames to each connected client"""
                last_id = 0

                try:
                    while True:
                        if await request.is_disconnected():
                            break

                        # Wait for a newer frame than we've sent
                        try:
                            async with self.cond:
                                await asyncio.wait_for(
                                    self.cond.wait_for(lambda: self.frame_id > last_id), timeout=5.0
                                )
                                last_id = self.frame_id
                                frame = self.latest_frame
                        except asyncio.TimeoutError:
                            continue

                        if not frame:
                            continue

                        yield (
                            boundary.encode() + b"\r\n"
                            b"Content-Type: image/jpeg\r\n"
                            b"Content-Length: " + str(len(frame)).encode() + b"\r\n\r\n" + frame + b"\r\n"
                        )

                except asyncio.CancelledError:
                    return
                except Exception as e:
                    print(f"[StreamingViewer] Client stream error: {e}")

            return StreamingResponse(generator(), media_type="multipart/x-mixed-replace; boundary=frame")

    def cleanup(self) -> None:
        """Clean up resources when widget is destroyed."""
        self._is_running = False

        if self._queue_reader_task and not self._queue_reader_task.done():
            self._queue_reader_task.cancel()

        try:
            while not self._thread_queue.empty():
                try:
                    self._thread_queue.get_nowait()
                except Exception:
                    break
        except Exception:
            pass

    def __del__(self):
        """Ensure cleanup on deletion"""
        try:
            self.cleanup()
        except Exception:
            pass
