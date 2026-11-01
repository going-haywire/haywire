"""Fixtures for haybale-models tests."""

from __future__ import annotations

import threading
import time
from collections.abc import Iterator
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any

import pytest

from haywire.core.volumes import VolumeStore, get_volume_store, set_volume_store


@pytest.fixture(autouse=True)
def _models_storage_dir(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Path:
    """Keep ``ModelsState.on_enable`` out of the real ``~/.haywire/db/haybale_models/``.

    Redirects the home directory rather than patching ``library_storage_dir``: the library
    system fixtures import ``haybale_models`` afresh, which rebinds the patched name.
    """
    home = tmp_path / "home"
    monkeypatch.setenv("HOME", str(home))
    storage = home / ".haywire" / "db" / "haybale_models"
    storage.mkdir(parents=True)
    return storage


@pytest.fixture
def models_env(tmp_path: Path) -> Iterator[VolumeStore]:
    """A temp VolumeStore with both model volumes pointed at tmp_path subfolders."""
    from haybale_models.keys import HF_VOLUME, MODELS_VOLUME

    previous = get_volume_store()
    store = VolumeStore(tmp_path / "models-volumes.toml")
    set_volume_store(store)
    store.ensure(MODELS_VOLUME, label="Models", description="", location=tmp_path / "models")
    store.ensure(HF_VOLUME, label="Hugging Face cache", description="", location=tmp_path / "hf")
    yield store
    set_volume_store(previous)


class FakeServer:
    """A local HTTP server for download tests: files with optional Range support, HTML pages, delays."""

    def __init__(self) -> None:
        self.routes: dict[str, dict[str, Any]] = {}
        self.sent: dict[str, int] = {}
        self.ranges: dict[str, list[str]] = {}
        self.release = threading.Event()
        self._active = 0
        self.max_active = 0
        self._lock = threading.Lock()
        outer = self

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *args: Any) -> None:
                pass

            def do_GET(self) -> None:
                outer._serve(self)

        self.httpd = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self.base = f"http://127.0.0.1:{self.httpd.server_address[1]}"
        self.thread = threading.Thread(
            target=lambda: self.httpd.serve_forever(poll_interval=0.01), daemon=True
        )
        self.thread.start()

    def file(
        self,
        path: str,
        data: bytes,
        *,
        ranges: bool = True,
        delay: float = 0.0,
        hold_half: bool = False,
        die_half: bool = False,
    ) -> str:
        """Serve ``data`` at ``path``; ``hold_half`` stalls after half the body until ``release`` is set.

        ``die_half`` closes the connection after half the body (a mid-stream failure).
        """
        self.routes[path] = {
            "data": data,
            "ranges": ranges,
            "delay": delay,
            "hold": hold_half,
            "die": die_half,
        }
        return self.base + path

    def html(self, path: str) -> str:
        """Serve a 200 ``text/html`` page (a download interstitial) at ``path``."""
        self.routes[path] = {"data": b"<html>please log in</html>", "html": True}
        return self.base + path

    def status(self, path: str, code: int) -> str:
        self.routes[path] = {"status": code}
        return self.base + path

    def _serve(self, h: BaseHTTPRequestHandler) -> None:
        route = self.routes.get(h.path)
        if route is None:
            h.send_error(404)
            return
        if "status" in route:
            h.send_error(route["status"])
            return
        with self._lock:
            self._active += 1
            self.max_active = max(self.max_active, self._active)
        try:
            data: bytes = route["data"]
            if route.get("delay"):
                time.sleep(route["delay"])
            start, status = 0, 200
            header = h.headers.get("Range")
            if header:
                self.ranges.setdefault(h.path, []).append(header)
            if header and route.get("ranges", False):
                start = int(header.split("=")[1].split("-")[0])
                status = 206
            body = data[start:]
            h.send_response(status)
            h.send_header("Content-Type", "text/html" if route.get("html") else "application/octet-stream")
            h.send_header("Content-Length", str(len(body)))
            h.end_headers()
            half = len(body) // 2 if route.get("hold") or route.get("die") else len(body)
            h.wfile.write(body[:half])
            h.wfile.flush()
            if half < len(body) and not route.get("die"):
                self.release.wait(5)
                h.wfile.write(body[half:])
            with self._lock:
                self.sent[h.path] = self.sent.get(h.path, 0) + len(body)
        except (BrokenPipeError, ConnectionResetError):
            pass
        finally:
            with self._lock:
                self._active -= 1

    def close(self) -> None:
        self.release.set()
        self.httpd.shutdown()
        self.httpd.server_close()


@pytest.fixture
def http_server() -> Iterator[FakeServer]:
    server = FakeServer()
    yield server
    server.close()
