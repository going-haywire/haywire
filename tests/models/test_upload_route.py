"""The upload route: the tier check, the file's name, refusals, a lost connection."""

from __future__ import annotations

import asyncio
import threading
from collections.abc import Iterator, MutableMapping
from pathlib import Path
from typing import Any
from urllib.parse import quote

import pytest
from fastapi import FastAPI
from starlette.testclient import TestClient

from haywire.core.access import AccessTier, access_resolver, set_access_resolver
from haywire.core.farmhand.activity import activity_tracker
from haywire.core.volumes import VolumeStore

from tests.models.test_download import DATA, SHA, Env, spec, wait_until

from haybale_models.upload_route import NAME_HEADER, mount_upload_route


@pytest.fixture
def env(models_env: VolumeStore, tmp_path: Path) -> Iterator[Env]:
    (tmp_path / "models").mkdir(exist_ok=True)
    e = Env(tmp_path)
    activity_tracker().clear()
    yield e
    e.queue.stop()
    activity_tracker().clear()


@pytest.fixture(autouse=True)
def _everyone_is_admin() -> Iterator[None]:
    """Start from no resolver, whatever an earlier test in this process installed."""
    previous = access_resolver()
    set_access_resolver(None)
    yield
    set_access_resolver(previous)


@pytest.fixture
def app() -> FastAPI:
    return FastAPI()


def failed(env: Env, server, *, sha: str | None = SHA, size: int | None = None) -> str:
    job = env.run(spec(server.status("/gone", 404), sha=sha, size=size))
    assert job.state == "failed"
    return job.id


def post(app: FastAPI, url: str, body: bytes, name: str = "w.pth", **headers: str):
    return TestClient(app).post(url, content=body, headers={NAME_HEADER: quote(name), **headers})


def upload_job(env: Env):
    return next(j for j in reversed(env.queue.jobs()) if j.via_browser)


def test_post_stores_the_file(env, http_server, app):
    route = mount_upload_route(env.queue, failed(env, http_server), "tester", app=app)
    response = post(app, route.url, DATA)
    assert response.status_code == 200, response.text
    assert env.index.by_sha256(SHA) == env.tmp / "models" / "downloads" / "127.0.0.1" / "w.pth"


def test_on_begin_gets_the_upload_job_id(env, http_server, app):
    seen: list[str] = []
    route = mount_upload_route(env.queue, failed(env, http_server), "tester", on_begin=seen.append, app=app)
    post(app, route.url, DATA)
    assert seen == [upload_job(env).id]


def test_percent_encoded_name_is_decoded_and_safe(env, http_server, app):
    route = mount_upload_route(env.queue, failed(env, http_server), "tester", app=app)
    response = post(app, route.url, DATA, name="../../mère #1.pth")
    assert response.status_code == 200, response.text
    assert env.index.by_sha256(SHA) == env.tmp / "models" / "downloads" / "127.0.0.1" / "mère #1.pth"


def test_a_missing_name_header_falls_back(env, http_server, app):
    route = mount_upload_route(env.queue, failed(env, http_server), "tester", app=app)
    response = TestClient(app).post(route.url, content=DATA)
    assert response.status_code == 200, response.text
    assert env.index.by_sha256(SHA).name == "model.bin"


def test_demoted_principal_gets_403_and_writes_nothing(env, http_server, app):
    route = mount_upload_route(env.queue, failed(env, http_server), "tester", app=app)
    set_access_resolver(lambda _name: AccessTier.VIEW)
    response = post(app, route.url, DATA)
    assert response.status_code == 403
    assert not list((env.tmp / "models").rglob("w.pth*"))
    assert not [j for j in env.queue.jobs() if j.via_browser]


def test_running_upload_gets_409(env, http_server, app):
    old = failed(env, http_server)
    route = mount_upload_route(env.queue, old, "tester", app=app)
    receiver = env.queue.begin_receive(old, "w.pth", "tester")
    response = post(app, route.url, DATA)
    assert response.status_code == 409
    assert "running" in response.json()["error"]
    receiver.abort()


def test_content_length_mismatch_is_refused_before_reading(env, http_server, app):
    route = mount_upload_route(env.queue, failed(env, http_server, size=len(DATA)), "tester", app=app)
    response = post(app, route.url, b"short")
    assert response.status_code == 422
    job = upload_job(env)
    assert job.state == "failed"
    assert f"got 5 bytes, expected {len(DATA)}" in (job.error or "")
    assert job.done_bytes == 0
    assert not list((env.tmp / "models").rglob("*.part"))


def test_wrong_digest_is_422_with_expected_text(env, http_server, app):
    route = mount_upload_route(env.queue, failed(env, http_server), "tester", app=app)
    response = post(app, route.url, b"not the model")
    assert response.status_code == 422
    assert SHA in response.json()["error"]
    assert upload_job(env).state == "failed"


def test_a_cancelled_job_gets_409(env, http_server, app):
    route = mount_upload_route(
        env.queue, failed(env, http_server), "tester", on_begin=env.queue.cancel, app=app
    )
    response = post(app, route.url, DATA)
    assert response.status_code == 409
    assert upload_job(env).state == "cancelled"
    assert not list((env.tmp / "models").rglob("*.part"))


def _call(app: FastAPI, url: str, messages: list[dict]) -> list[dict]:
    """Run the route with the given ASGI receive messages; returns what it sent."""
    sent: list[dict] = []
    queue = list(messages)

    async def receive() -> dict:
        return queue.pop(0)

    async def send(message: MutableMapping[str, Any]) -> None:
        sent.append(dict(message))

    scope = {
        "type": "http",
        "asgi": {"version": "3.0"},
        "http_version": "1.1",
        "method": "POST",
        "scheme": "http",
        "path": url,
        "raw_path": url.encode(),
        "root_path": "",
        "query_string": b"",
        "headers": [(NAME_HEADER.lower().encode(), b"w.pth")],
        "client": ("127.0.0.1", 1),
        "server": ("127.0.0.1", 80),
        "app": app,
    }
    asyncio.run(app(scope, receive, send))
    return sent


def test_client_disconnect_aborts(env, http_server, app):
    route = mount_upload_route(env.queue, failed(env, http_server), "tester", app=app)
    _call(
        app,
        route.url,
        [
            {"type": "http.request", "body": DATA[:10], "more_body": True},
            {"type": "http.disconnect"},
        ],
    )
    assert upload_job(env).state == "cancelled"
    assert not list((env.tmp / "models").rglob("*.part"))


def test_a_large_body_is_written_as_it_arrives(env, http_server, app):
    data = b"x" * (3 * 1024 * 1024)
    route = mount_upload_route(env.queue, failed(env, http_server, sha=None), "tester", app=app)
    messages: list[dict] = [
        {"type": "http.request", "body": data[i : i + 64 * 1024], "more_body": True}
        for i in range(0, len(data), 64 * 1024)
    ]
    messages.append({"type": "http.request", "body": b"", "more_body": False})
    _call(app, route.url, messages)
    wait_until(lambda: upload_job(env).state == "done")
    assert upload_job(env).done_bytes == len(data)


def test_unmount_removes_the_route(env, http_server, app):
    route = mount_upload_route(env.queue, failed(env, http_server), "tester", app=app)
    route.unmount()
    route.unmount()
    assert post(app, route.url, DATA).status_code == 404


def test_token_is_not_guessable_and_per_mount(env, http_server, app):
    job = failed(env, http_server)
    a = mount_upload_route(env.queue, job, "tester", app=app)
    b = mount_upload_route(env.queue, job, "tester", app=app)
    assert a.url != b.url
    assert a.url.startswith("/_haybale_models/upload/")
    assert len(a.url.rsplit("/", 1)[-1]) >= 32


def test_an_unexpected_error_while_reading_ends_the_job(env, http_server, app, monkeypatch):
    def broken(self: Any, chunk: bytes) -> None:
        raise ValueError("unexpected")

    monkeypatch.setattr("haybale_models.receive.UploadReceiver.write", broken)
    route = mount_upload_route(env.queue, failed(env, http_server), "tester", app=app)
    response = post(app, route.url, DATA)
    assert response.status_code == 422
    job = upload_job(env)
    assert job.state == "failed"
    assert "unexpected" in (job.error or "")
    assert not list((env.tmp / "models").rglob("*.part"))


def test_an_error_in_on_begin_ends_the_job(env, http_server, app):
    def boom(_job_id: str) -> None:
        raise RuntimeError("listener is broken")

    route = mount_upload_route(env.queue, failed(env, http_server), "tester", on_begin=boom, app=app)
    response = post(app, route.url, DATA)
    assert response.status_code == 422
    assert upload_job(env).state == "failed"


def _stalled_call(app: FastAPI, url: str, first: bytes = b"") -> list[dict]:
    """Run the route on a connection that goes silent without a disconnect."""
    sent: list[dict] = []
    gave_first = False

    async def receive() -> dict:
        nonlocal gave_first
        if not gave_first:
            gave_first = True
            return {"type": "http.request", "body": first, "more_body": True}
        await asyncio.Event().wait()
        raise AssertionError("unreachable")

    async def send(message: MutableMapping[str, Any]) -> None:
        sent.append(dict(message))

    scope = {
        "type": "http",
        "asgi": {"version": "3.0"},
        "http_version": "1.1",
        "method": "POST",
        "scheme": "http",
        "path": url,
        "raw_path": url.encode(),
        "root_path": "",
        "query_string": b"",
        "headers": [(NAME_HEADER.lower().encode(), b"w.pth")],
        "client": ("127.0.0.1", 1),
        "server": ("127.0.0.1", 80),
        "app": app,
    }

    async def bounded() -> None:
        await asyncio.wait_for(app(scope, receive, send), timeout=5)

    asyncio.run(bounded())
    return sent


def test_cancel_stops_a_stalled_connection(env, http_server, app, monkeypatch):
    monkeypatch.setattr("haybale_models.upload_route._POLL_S", 0.01)
    route = mount_upload_route(env.queue, failed(env, http_server), "tester", app=app)
    threading.Timer(0.1, lambda: env.queue.cancel(upload_job(env).id)).start()
    _stalled_call(app, route.url, DATA[:10])
    assert upload_job(env).state == "cancelled"
    assert not list((env.tmp / "models").rglob("*.part"))


def test_a_silent_connection_times_out(env, http_server, app, monkeypatch):
    monkeypatch.setattr("haybale_models.upload_route._POLL_S", 0.01)
    monkeypatch.setattr("haybale_models.upload_route._IDLE_TIMEOUT_S", 0.05)
    route = mount_upload_route(env.queue, failed(env, http_server), "tester", app=app)
    _stalled_call(app, route.url, DATA[:10])
    job = upload_job(env)
    assert job.state == "failed"
    assert "no data" in (job.error or "")
    assert not list((env.tmp / "models").rglob("*.part"))


def test_a_wrong_file_stays_out_of_the_ledger(env, http_server, app, error_ledger):
    route = mount_upload_route(env.queue, failed(env, http_server), "tester", app=app)
    assert post(app, route.url, b"not the model").status_code == 422
    assert error_ledger.current_seq == 0


def test_a_bug_while_reading_reaches_the_ledger(env, http_server, app, error_ledger, monkeypatch):
    def broken(self: Any, chunk: bytes) -> None:
        raise ValueError("unexpected")

    monkeypatch.setattr("haybale_models.receive.UploadReceiver.write", broken)
    route = mount_upload_route(env.queue, failed(env, http_server), "tester", app=app)
    post(app, route.url, DATA)
    assert error_ledger.current_seq == 1
    assert upload_job(env).state == "failed"


def test_a_bug_in_on_begin_reaches_the_ledger(env, http_server, app, error_ledger):
    def boom(_job_id: str) -> None:
        raise RuntimeError("listener is broken")

    route = mount_upload_route(env.queue, failed(env, http_server), "tester", on_begin=boom, app=app)
    post(app, route.url, DATA)
    assert error_ledger.current_seq == 1
