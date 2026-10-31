"""Viewer backends: the MJPEG stream's encode and drop-1 queue, the lazily encoded still route."""

import asyncio
import importlib
from typing import Any

import numpy as np
import pytest
from nicegui import app

pytestmark = pytest.mark.unit


def _backend_mod() -> Any:
    return importlib.import_module("haybale_image.viewer.backend")


def _image(layout: str = "rgb") -> Any:
    value_mod = importlib.import_module("haybale_image.value")
    channels = {"rgb": 3, "rgba": 4}[layout]
    return value_mod.ImageValue.from_array(np.full((8, 12, channels), 128, np.uint8))


def _empty() -> Any:
    value_mod = importlib.import_module("haybale_image.value")
    return value_mod.ImageValue.empty(value_mod.Layout.RGB)


def _route_paths() -> set[str | None]:
    return {getattr(r, "path", None) for r in app.routes}


def _still_route(backend: Any) -> Any:
    return next(r for r in app.routes if getattr(r, "path", None) == backend.endpoint)


@pytest.fixture
def imencode_calls(monkeypatch):
    """Count ``cv2.imencode`` calls made by the backend module."""
    cv2 = _backend_mod().cv2
    real = cv2.imencode
    calls: list[str] = []

    def counting(ext: str, *args: Any, **kwargs: Any) -> Any:
        calls.append(ext)
        return real(ext, *args, **kwargs)

    monkeypatch.setattr(cv2, "imencode", counting)
    return calls


def test_stream_skips_empty(imencode_calls):
    backend = _backend_mod().StreamingBackend()
    try:

        async def go() -> None:
            backend.stream(_empty())

        asyncio.run(go())
        assert imencode_calls == []
        assert backend._thread_queue.empty()
    finally:
        backend.cleanup()


def test_stream_without_viewer_loop_encodes_nothing(imencode_calls):
    backend = _backend_mod().StreamingBackend()
    try:
        backend.stream(_image())  # a worker thread: no event loop, no viewer
        assert imencode_calls == []
    finally:
        backend.cleanup()


def _solid(color: tuple[int, ...]) -> Any:
    value_mod = importlib.import_module("haybale_image.value")
    return value_mod.ImageValue.from_array(np.full((8, 12, len(color)), color, np.uint8))


def _drain(backend: Any) -> list[bytes]:
    queued = []
    while not backend._thread_queue.empty():
        queued.append(backend._thread_queue.get_nowait())
    return queued


def _decode(data: bytes) -> Any:
    cv2 = _backend_mod().cv2
    return cv2.imdecode(np.frombuffer(data, np.uint8), cv2.IMREAD_UNCHANGED)


def test_stream_drop1_keeps_latest(imencode_calls):
    backend = _backend_mod().StreamingBackend()
    try:

        async def go() -> list[bytes]:
            backend.stream(_solid((30, 30, 30)))  # gray, dropped by the second frame
            backend.stream(_solid((255, 0, 0, 255)))  # RGBA red: the frame that must survive
            queued = _drain(backend)
            backend.cleanup()
            return queued

        queued = asyncio.run(go())
        assert imencode_calls == [".jpg", ".jpg"]
        assert len(queued) == 1
        assert queued[0][:2] == b"\xff\xd8"  # JPEG SOI
        decoded = _decode(queued[0])
        assert decoded.shape[2] == 3
        b, g, r = (float(decoded[..., i].mean()) for i in range(3))
        assert r > 200  # the second (red) frame, not the gray one
        assert g < 60
        assert b < 60
    finally:
        backend.cleanup()


def test_stream_rgba_encodes_three_channels():
    backend = _backend_mod().StreamingBackend()
    try:

        async def go() -> list[bytes]:
            backend.stream(_solid((0, 255, 0, 128)))
            queued = _drain(backend)
            backend.cleanup()
            return queued

        queued = asyncio.run(go())
        assert len(queued) == 1
        assert _decode(queued[0]).shape[2] == 3
    finally:
        backend.cleanup()


def test_still_encodes_only_on_request(imencode_calls):
    backend = _backend_mod().StillBackend()
    try:
        img = _image("rgba")
        versions = [backend.show(img) for _ in range(100)]
        assert versions == list(range(1, 101))
        assert imencode_calls == []

        response = _still_route(backend).endpoint()
        assert imencode_calls == [".png"]
        assert response.status_code == 200
        assert response.media_type == "image/png"
        assert response.headers["cache-control"] == "no-store"
        assert response.body[:8] == b"\x89PNG\r\n\x1a\n"

        import cv2

        decoded = cv2.imdecode(np.frombuffer(response.body, np.uint8), cv2.IMREAD_UNCHANGED)
        assert decoded is not None
        assert decoded.shape == (8, 12, 4)  # alpha kept
        assert decoded.dtype == np.uint8
    finally:
        backend.cleanup()


def test_still_without_image_is_204(imencode_calls):
    backend = _backend_mod().StillBackend()
    try:
        response = _still_route(backend).endpoint()
        assert response.status_code == 204
        assert response.headers["cache-control"] == "no-store"
        backend.show(_empty())
        assert _still_route(backend).endpoint().status_code == 204
        assert imencode_calls == []
    finally:
        backend.cleanup()


def test_cleanup_removes_routes():
    mod = _backend_mod()
    stream, still = mod.StreamingBackend(), mod.StillBackend()
    assert {stream.endpoint, still.endpoint} <= _route_paths()
    stream.cleanup()
    still.cleanup()
    assert not {stream.endpoint, still.endpoint} & _route_paths()
