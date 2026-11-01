"""The download queue: verify, mirrors, resume, limits, cancel, refusals, activity."""

from __future__ import annotations

import hashlib
import threading
import time
from collections.abc import Callable, Iterator
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from haywire.core.farmhand.activity import activity_tracker
from haywire.core.catalog import ModelFile, Resource
from haywire.core.volumes import VolumeStore

from haybale_models import hf
from haybale_models.download import DownloadJob, DownloadQueue
from haybale_models.resolver import FetchSpec
from haybale_models.store.index import ModelIndex
from haybale_models.value.model_ref import ModelRef

DATA = bytes(range(256)) * 400  # ~100 kB
SHA = hashlib.sha256(DATA).hexdigest()


class Env:
    def __init__(self, tmp: Path) -> None:
        self.tmp = tmp
        self.index = ModelIndex()
        self.parallel = 2
        self.hf_dir: Path | None = tmp / "hf"
        self.queue = DownloadQueue(self.index, lambda: self.hf_dir, lambda: self.parallel)

    def wait(self, job_id: str, timeout: float = 4.0) -> DownloadJob:
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            job = self.job(job_id)
            if job.state not in ("queued", "running"):
                return job
            time.sleep(0.01)
        raise AssertionError(f"job {job_id} still {self.job(job_id).state}")

    def job(self, job_id: str) -> DownloadJob:
        return next(j for j in self.queue.jobs() if j.id == job_id)

    def run(self, spec: FetchSpec) -> DownloadJob:
        return self.wait(self.queue.enqueue(spec, "tester"))


@pytest.fixture
def env(models_env: VolumeStore, tmp_path: Path) -> Iterator[Env]:
    (tmp_path / "models").mkdir(exist_ok=True)
    e = Env(tmp_path)
    activity_tracker().clear()
    yield e
    e.queue.stop()
    activity_tracker().clear()


def spec(*urls: str, sha: str | None = SHA, size: int | None = None) -> FetchSpec:
    return FetchSpec(ref=ModelRef(urls=urls, sha256=sha, size=size, label="demo"))


def wait_until(cond: Callable[[], bool], timeout: float = 3.0) -> None:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if cond():
            return
        time.sleep(0.01)
    raise AssertionError("condition not reached")


def test_downloads_verifies_and_indexes(env, http_server):
    url = http_server.file("/w.pth", DATA)
    job = env.run(spec(url, size=len(DATA)))
    assert job.state == "done", job.error
    assert job.target is not None
    assert job.target == env.tmp / "models" / "downloads" / "127.0.0.1" / "w.pth"
    assert job.target.read_bytes() == DATA
    assert env.index.by_sha256(SHA) == job.target
    record = env.index.by_source(url)
    assert record is not None
    assert record.sha256 == SHA
    assert job.done_bytes == len(DATA)


def test_unpinned_download_indexes_computed_digest(env, http_server):
    job = env.run(spec(http_server.file("/u.bin", DATA), sha=None))
    assert job.state == "done", job.error
    assert env.index.by_sha256(SHA) == job.target


def test_html_response_falls_through_to_next_mirror(env, http_server):
    job = env.run(spec(http_server.html("/a"), http_server.file("/b", DATA)))
    assert job.state == "done", job.error
    assert job.target is not None
    assert job.target.read_bytes() == DATA
    assert not list((env.tmp / "models").rglob("*.part"))


def test_http_error_falls_through(env, http_server):
    job = env.run(spec(http_server.status("/gone", 404), http_server.file("/b", DATA)))
    assert job.state == "done", job.error


def test_digest_mismatch_fails_over_then_fails(env, http_server):
    bad = http_server.file("/bad", b"not the model")
    job = env.run(spec(bad, http_server.file("/good", DATA)))
    assert job.state == "done", job.error
    assert job.target is not None
    assert job.target.read_bytes() == DATA

    job = env.run(spec(bad, http_server.file("/bad2", b"also wrong"), sha="f" * 64))
    assert job.state == "failed"
    assert job.error is not None
    assert "digest mismatch" in job.error
    assert "/bad2" in job.error
    assert job.target is None
    assert not list((env.tmp / "models").rglob("*.part"))


def test_size_mismatch_is_a_mirror_failure(env, http_server):
    job = env.run(spec(http_server.file("/s", DATA), sha=None, size=len(DATA) + 1))
    assert job.state == "failed"
    assert job.error is not None
    assert "size mismatch" in job.error


def _seed_part(env: Env, url_path: str, data: bytes) -> Path:
    part = env.tmp / "models" / "downloads" / "127.0.0.1" / (Path(url_path).name + ".part")
    part.parent.mkdir(parents=True)
    part.write_bytes(data)
    return part


def test_resume_appends_with_range(env, http_server):
    half = len(DATA) // 2
    _seed_part(env, "/r.pth", DATA[:half])
    job = env.run(spec(http_server.file("/r.pth", DATA)))
    assert job.state == "done", job.error
    assert http_server.ranges["/r.pth"] == [f"bytes={half}-"]
    assert http_server.sent["/r.pth"] == len(DATA) - half
    assert job.target is not None
    assert job.target.read_bytes() == DATA


def test_server_without_range_restarts(env, http_server):
    half = len(DATA) // 2
    _seed_part(env, "/n.pth", DATA[:half])
    job = env.run(spec(http_server.file("/n.pth", DATA, ranges=False)))
    assert job.state == "done", job.error
    assert http_server.sent["/n.pth"] == len(DATA)
    assert job.target is not None
    assert job.target.read_bytes() == DATA


def test_parallel_limit_respected(env, http_server):
    env.parallel = 2
    ids = [
        env.queue.enqueue(spec(http_server.file(f"/p{i}", DATA, delay=0.3), sha=None), None)
        for i in range(4)
    ]
    peak = 0
    deadline = time.monotonic() + 4
    while time.monotonic() < deadline:
        states = [j.state for j in env.queue.jobs()]
        peak = max(peak, states.count("running"))
        if all(s == "done" for s in states):
            break
        time.sleep(0.01)
    assert [env.job(i).state for i in ids] == ["done"] * 4
    assert peak == 2
    assert http_server.max_active <= 2


def test_duplicate_enqueue_returns_same_job(env, http_server):
    url = http_server.file("/d", DATA, delay=0.2)
    first = env.queue.enqueue(spec(url), None)
    assert env.queue.enqueue(spec("http://elsewhere/x", sha="a" * 64), None) != first  # other sha: no dup
    assert env.queue.enqueue(spec("http://other/y", sha=SHA), None) == first  # same sha, other source: dup
    unpinned = env.queue.enqueue(spec(url, sha=None), None)
    assert env.queue.enqueue(spec(url, "http://m/z", sha=None), None) == unpinned  # same first source
    env.wait(first)


def test_finished_job_is_not_a_duplicate(env, http_server):
    url = http_server.file("/f", DATA)
    first = env.run(spec(url, sha=None))
    assert first.state == "done"
    # the file is not in the index under a pinned digest here, so a re-enqueue makes a new job
    second = env.queue.enqueue(spec(url, sha=None), None)
    assert second != first.id
    env.wait(second)


def test_already_local_file_is_not_fetched(env, http_server):
    url = http_server.file("/l", DATA)
    assert env.run(spec(url)).state == "done"
    assert env.queue.enqueue(spec(url), None) == ""


def test_cancel_removes_part(env, http_server):
    job_id = env.queue.enqueue(spec(http_server.file("/c", DATA, hold_half=True)), None)
    wait_until(lambda: env.job(job_id).done_bytes > 0)
    env.queue.cancel(job_id)
    http_server.release.set()
    job = env.wait(job_id)
    assert job.state == "cancelled"
    assert not list((env.tmp / "models").rglob("*.part"))
    assert env.index.by_sha256(SHA) is None


def test_cancel_queued_job(env, http_server):
    env.parallel = 1
    running = env.queue.enqueue(spec(http_server.file("/q1", DATA, hold_half=True), sha=None), None)
    queued = env.queue.enqueue(spec(http_server.file("/q2", DATA), sha=None), None)
    wait_until(lambda: env.job(running).done_bytes > 0)
    assert env.job(queued).state == "queued"
    env.queue.cancel(queued)
    assert env.job(queued).state == "cancelled"
    http_server.release.set()
    assert env.wait(running).state == "done"
    assert env.job(queued).state == "cancelled"


def test_download_refuses_missing_volume(env, http_server):
    (env.tmp / "models").rmdir()
    job = env.run(spec(http_server.file("/v", DATA)))
    assert job.state == "failed"
    assert job.error is not None
    assert "does not exist" in job.error
    assert http_server.sent == {}


def test_download_refuses_undefined_volume(env, http_server, monkeypatch):
    from haywire.core.volumes import VolumeUndefinedError

    def boom(key: str, store: Any = None) -> Path:
        raise VolumeUndefinedError(key)

    monkeypatch.setattr("haybale_models.download.location_of", boom)
    job = env.run(spec(http_server.file("/v2", DATA)))
    assert job.state == "failed"
    assert job.error is not None
    assert "models volume unavailable" in job.error
    assert http_server.sent == {}


def test_activity_record_per_job(env, http_server):
    ok = env.run(spec(http_server.file("/ok", DATA)))
    bad = env.run(spec(http_server.file("/bad", b"x"), sha="e" * 64))
    assert (ok.state, bad.state) == ("done", "failed")
    records = [r for r in activity_tracker().recent() if r.tool == "models.download"]
    assert len(records) == 2
    by_ok = {r.ok: r for r in records}
    assert "demo" in by_ok[True].arguments
    assert "/ok" in by_ok[True].arguments
    assert "digest mismatch" in (by_ok[False].error or "")
    assert all(r.principal == "tester" for r in records)


def test_listeners_fire_and_progress_is_throttled(env, http_server):
    calls: list[int] = []
    env.queue.add_listener(lambda: calls.append(1))
    env.run(spec(http_server.file("/t", DATA)))
    assert len(calls) >= 3  # queued, running, done
    assert len(calls) < 10  # ~100 kB is one chunk: progress never floods


def test_catalog_bundle_downloads_one_job_per_missing_file(env, http_server):
    files = tuple(
        ModelFile(path, hashlib.sha256(body).hexdigest(), len(body), (http_server.file(f"/{path}", body),))
        for path, body in (("a.bin", b"alpha"), ("sub/b.bin", b"beta"))
    )
    resource = Resource("pytorch", "pth", None, None, (), files)
    entry = SimpleNamespace(
        name="My Model", library=SimpleNamespace(name="lib"), path=Path("cat/my-model.json")
    )
    fetch = FetchSpec(entry=entry, resource=resource)  # type: ignore[arg-type]
    ids = env.queue.enqueue_all(fetch, None)
    assert len(ids) == 2
    jobs = [env.wait(i) for i in ids]
    assert [j.state for j in jobs] == ["done", "done"]
    base = env.tmp / "models" / "lib" / "my-model" / "pytorch-pth"
    assert (base / "a.bin").read_bytes() == b"alpha"
    assert (base / "sub" / "b.bin").read_bytes() == b"beta"
    assert env.queue.enqueue_all(fetch, None) == []  # nothing missing any more


def test_bundle_path_traversal_fails_job(env, http_server):
    evil = ModelFile("../../escape.bin", None, None, (http_server.file("/e", b"evil"),))
    resource = Resource("pytorch", "pth", None, None, (), (evil, ModelFile("ok.bin", None, None, ())))
    entry = SimpleNamespace(name="Evil", library=SimpleNamespace(name="lib"), path=Path("cat/evil.json"))
    job = env.run(FetchSpec(entry=entry, resource=resource))  # type: ignore[arg-type]
    assert job.state == "failed"
    assert job.error is not None
    assert "unsafe bundle file path" in job.error
    assert not (env.tmp / "escape.bin").exists()


def test_target_outside_volume_root_is_refused(env, http_server, monkeypatch):
    outside = env.tmp / "elsewhere" / "w.bin"
    monkeypatch.setattr("haybale_models.download.target_path", lambda **kw: outside)
    job = env.run(spec(http_server.file("/o", DATA)))
    assert job.state == "failed"
    assert job.error is not None
    assert "outside the models volume" in job.error
    assert not outside.exists()
    assert not outside.parent.exists()
    assert http_server.sent == {}


def test_symlink_escape_is_refused(env, http_server):
    outside = env.tmp / "outside"
    outside.mkdir()
    link = env.tmp / "models" / "downloads"
    link.symlink_to(outside, target_is_directory=True)
    job = env.run(spec(http_server.file("/s", DATA)))
    assert job.state == "failed"
    assert job.error is not None
    assert "outside the models volume" in job.error
    assert list(outside.iterdir()) == []


def test_hf_source_downloads_through_hf_and_verifies(env, monkeypatch):
    blob = env.tmp / "hf" / "blobs" / SHA
    blob.parent.mkdir(parents=True)
    blob.write_bytes(DATA)
    seen: dict[str, Any] = {}

    def fake(uri, cache_dir, expected_size, on_progress, cancel):
        seen.update(uri=uri, cache=cache_dir)
        on_progress(len(DATA), expected_size)
        return blob

    monkeypatch.setattr(hf, "download", fake)
    job = env.run(spec("hf://org/repo/w.safetensors"))
    assert job.state == "done", job.error
    assert seen == {"uri": "hf://org/repo/w.safetensors", "cache": env.tmp / "hf"}
    assert job.target == blob
    assert env.index.by_sha256(SHA) is None  # hf never lands in the models index


def test_hf_digest_mismatch_fails(env, monkeypatch):
    other = env.tmp / "hf" / "snap" / "w.bin"
    other.parent.mkdir(parents=True)
    other.write_bytes(b"different")
    monkeypatch.setattr(hf, "download", lambda *a, **k: other)
    job = env.run(spec("hf://org/repo/w.bin"))
    assert job.state == "failed"
    assert "digest mismatch" in (job.error or "")


def test_hf_without_cache_volume_fails(env, monkeypatch):
    env.hf_dir = None
    job = env.run(spec("hf://org/repo/w.bin"))
    assert job.state == "failed"
    assert "cache volume unavailable" in (job.error or "")


def test_hf_cancel_marks_cancelled(env, monkeypatch):
    started = threading.Event()

    def fake(uri, cache_dir, expected_size, on_progress, cancel):
        started.set()
        cancel.wait(3)
        raise hf.DownloadCancelled(uri)

    monkeypatch.setattr(hf, "download", fake)
    job_id = env.queue.enqueue(spec("hf://org/repo/w.bin"), None)
    assert started.wait(2)
    env.queue.cancel(job_id)
    assert env.wait(job_id).state == "cancelled"


def test_mirror_switch_discards_the_partial_file(env, http_server):
    other = bytes(reversed(DATA))  # same length, different bytes: stitching would corrupt
    a = http_server.file("/a/m.bin", DATA, die_half=True)
    b = http_server.file("/b/m.bin", other)
    job = env.run(spec(a, b, sha=None))
    assert job.state == "done", job.error
    assert job.target is not None
    assert job.target.read_bytes() == other
    assert "/b/m.bin" not in http_server.ranges
    assert not job.target.with_name("m.bin.part").exists()


def test_two_jobs_cannot_write_the_same_target(env, http_server):
    env.parallel = 2
    one = http_server.file("/a/m.bin", DATA, hold_half=True)
    two = http_server.file("/b/m.bin", bytes(reversed(DATA)))
    first = env.queue.enqueue(spec(one, sha=None), None)
    wait_until(lambda: env.job(first).done_bytes > 0)
    second = env.queue.enqueue(spec(two, sha=None), None)
    failed = env.wait(second)
    assert failed.state == "failed"
    assert failed.error == "another download is writing downloads/127.0.0.1/m.bin"
    http_server.release.set()
    done = env.wait(first)
    assert done.state == "done", done.error
    assert done.target is not None
    assert done.target.read_bytes() == DATA


def test_raising_tracker_fails_the_job(env, http_server, monkeypatch):
    class Broken:
        def start(self, *args: Any, **kwargs: Any) -> Any:
            raise RuntimeError("tracker down")

    monkeypatch.setattr("haybale_models.download.activity_tracker", lambda: Broken())
    job = env.run(spec(http_server.file("/t", DATA)))
    assert job.state == "failed"
    assert job.error == "tracker down"
