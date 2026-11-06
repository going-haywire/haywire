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

from tests.models.conftest import make_hf_snapshot

from haybale_models import hf
from haybale_models.download import DownloadJob, DownloadQueue
from haybale_models.resolver import FetchSpec
from haybale_models.sources import builtin_sources
from haybale_models.store.index import ModelIndex
from haybale_models.value.model_ref import ModelRef

DATA = bytes(range(256)) * 400  # ~100 kB
SHA = hashlib.sha256(DATA).hexdigest()
BAD_NAME = "w-aaaaaaaa.pth"
"""A torch hub name whose hash prefix contradicts ``SHA``."""


class Env:
    def __init__(self, tmp: Path) -> None:
        self.tmp = tmp
        self.index = ModelIndex()
        self.parallel = 2
        self.hf_dir: Path | None = tmp / "hf"
        self.queue = DownloadQueue(
            self.index, builtin_sources(self.index, hf_cache=lambda: self.hf_dir), lambda: self.parallel
        )

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

    monkeypatch.setattr("haybale_models.sources.base.location_of", boom)
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
    monkeypatch.setattr("haybale_models.sources.https.target_path", lambda **kw: outside)
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


def test_hf_volume_problem_falls_through_to_https(env, http_server):
    env.hf_dir = None
    job = env.run(spec("hf://o/r/w.pth", http_server.file("/w.pth", DATA)))
    assert job.state == "done", job.error
    assert job.target is not None
    assert job.target.is_relative_to(env.tmp / "models")


def test_running_hf_job_is_not_cancellable(env, monkeypatch):
    started, release = threading.Event(), threading.Event()
    blob = env.tmp / "hf" / "blobs" / "w.bin"

    def fake(uri, cache_dir, expected_size, on_progress, cancel):
        started.set()
        release.wait(3)
        blob.parent.mkdir(parents=True, exist_ok=True)
        blob.write_bytes(DATA)
        return blob

    monkeypatch.setattr(hf, "download", fake)
    job_id = env.queue.enqueue(spec("hf://org/repo/w.bin", sha=None), None)
    assert started.wait(2)
    assert env.job(job_id).cancellable is False
    assert env.queue.cancel(job_id) is False
    assert env.job(job_id).state == "running"
    release.set()
    assert env.wait(job_id).state == "done"


def test_running_https_job_is_cancellable(env, http_server):
    job_id = env.queue.enqueue(spec(http_server.file("/k", DATA, hold_half=True)), None)
    wait_until(lambda: env.job(job_id).done_bytes > 0)
    assert env.job(job_id).cancellable is True
    assert env.queue.cancel(job_id) is True
    http_server.release.set()
    assert env.wait(job_id).state == "cancelled"


def test_cancellable_follows_the_running_address(env, http_server, monkeypatch):
    def fail(uri, cache_dir, expected_size, on_progress, cancel):
        raise OSError("hub down")

    monkeypatch.setattr(hf, "download", fail)
    url = http_server.file("/f", DATA, hold_half=True)
    job_id = env.queue.enqueue(spec("hf://org/repo/w.bin", url), None)
    wait_until(lambda: env.job(job_id).done_bytes > 0)
    assert env.job(job_id).cancellable is True
    http_server.release.set()
    assert env.wait(job_id).state == "done"


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


def test_fetch_writes_to_request_target_and_skips_the_index(env, http_server):
    from haybale_models.sources.base import FetchRequest
    from haybale_models.sources.https import HttpsSource

    url = http_server.file("/t.pth", DATA)
    root = env.tmp / "models"
    target = root / "elsewhere" / "t.pth"
    claimed: list[Path] = []
    request = FetchRequest(
        address=url,
        root=root,
        sha256=SHA,
        size=len(DATA),
        entry=None,
        resource=None,
        file=None,
        on_progress=lambda d, t: None,
        cancel=threading.Event(),
        claim=claimed.append,
        fresh=False,
        target=target,
    )
    assert HttpsSource(env.index).fetch(request) == target
    assert target.read_bytes() == DATA
    assert claimed == [Path("elsewhere/t.pth")]
    assert env.index.by_sha256(SHA) is None


def _cache_queue(env: Env, records: Any) -> DownloadQueue:
    from haybale_models.sources import SourceSet
    from haybale_models.sources.folder import TorchHubSource
    from haybale_models.sources.https import HttpsSource

    sources = SourceSet(
        [
            HttpsSource(env.index),
            TorchHubSource(
                name="torchhub", label="Torch Hub", locate=lambda: env.tmp / "torch", description=""
            ),
        ]
    )
    return DownloadQueue(env.index, sources, lambda: 2, records)


def _cache_spec(url: str, sha: str | None = SHA, name: str = "w.pth") -> FetchSpec:
    entry = SimpleNamespace(class_identity=SimpleNamespace(registry_key="lib:catalog:demo"), name="demo")
    resource = Resource(
        "pytorch", "pth", None, sha, (url,), (ModelFile("", sha, None, (url,)),), cache=f"torchhub://{name}"
    )
    return FetchSpec(entry=entry, resource=resource)  # type: ignore[arg-type]


def _run_on(queue: DownloadQueue, spec_: FetchSpec) -> DownloadJob:
    job_id = queue.enqueue(spec_, "tester")
    wait_until(lambda: all(j.state not in ("queued", "running") for j in queue.jobs()))
    return next(j for j in queue.jobs() if j.id == job_id)


def test_cache_file_is_fetched_into_the_cache_and_recorded(env, http_server):
    from haybale_models.store.records import FetchRecords

    records = FetchRecords(env.tmp / "fetched.json")
    queue = _cache_queue(env, records)
    try:
        job = _run_on(queue, _cache_spec(http_server.file("/w.pth", DATA)))
        assert job.state == "done", job.error
        assert (env.tmp / "torch" / "w.pth").read_bytes() == DATA
        assert job.target == env.tmp / "torch" / "w.pth"
        assert env.index.by_sha256(SHA) is None
        found = records.at("haybale-models:volume:torchhub", "w.pth")
        assert found[0].entry_key == "lib:catalog:demo"
        assert found[0].sha256 == SHA
    finally:
        queue.stop()


def test_present_cache_file_is_not_queued(env, http_server):
    from haybale_models.store.records import FetchRecords

    (env.tmp / "torch").mkdir()
    (env.tmp / "torch" / "w.pth").write_bytes(DATA)
    queue = _cache_queue(env, FetchRecords(env.tmp / "fetched.json"))
    try:
        assert queue.enqueue(_cache_spec(http_server.file("/w.pth", DATA)), "tester") == ""
        assert http_server.sent == {}
    finally:
        queue.stop()


def test_unrecorded_file_in_the_cache_is_never_overwritten(env, http_server):
    from haybale_models.store.records import FetchRecords

    (env.tmp / "torch").mkdir()
    (env.tmp / "torch" / BAD_NAME).write_bytes(b"someone else's file")
    records = FetchRecords(env.tmp / "fetched.json")
    queue = _cache_queue(env, records)
    try:
        job = _run_on(queue, _cache_spec(http_server.file("/w.pth", DATA), name=BAD_NAME))
        assert job.state == "failed"
        assert job.error == f"a different file already exists at {env.tmp / 'torch' / BAD_NAME}"
        assert (env.tmp / "torch" / BAD_NAME).read_bytes() == b"someone else's file"
        assert http_server.sent == {}
    finally:
        queue.stop()


def test_recorded_file_in_the_cache_may_be_replaced(env, http_server):
    from haybale_models.store.records import FetchRecord, FetchRecords

    (env.tmp / "torch").mkdir()
    (env.tmp / "torch" / BAD_NAME).write_bytes(b"stale")
    records = FetchRecords(env.tmp / "fetched.json")
    records.add(
        FetchRecord(
            "haybale-models:volume:torchhub",
            BAD_NAME,
            "0" * 64,
            "lib:catalog:demo",
            f"torchhub://{BAD_NAME}",
        )
    )
    queue = _cache_queue(env, records)
    try:
        job = _run_on(queue, _cache_spec(http_server.file("/w.pth", DATA), name=BAD_NAME))
        assert job.state == "done", job.error
        assert (env.tmp / "torch" / BAD_NAME).read_bytes() == DATA
    finally:
        queue.stop()


def test_unusable_cache_volume_fails_the_job(env, http_server):
    from haybale_models.store.records import FetchRecords

    (env.tmp / "torch").write_text("a file where the cache folder should be")
    queue = _cache_queue(env, FetchRecords(env.tmp / "fetched.json"))
    try:
        job = _run_on(queue, _cache_spec(http_server.file("/w.pth", DATA)))
        assert job.state == "failed"
        assert job.error is not None
        assert job.error.startswith("Torch Hub cache volume unavailable: ")
    finally:
        queue.stop()


def test_cache_source_that_raises_does_not_break_enqueue(env, http_server, monkeypatch):
    from haybale_models.sources.folder import TorchHubSource
    from haybale_models.store.records import FetchRecords

    def boom(self, address):
        raise OSError("disk gone")

    monkeypatch.setattr(TorchHubSource, "find", boom)
    queue = _cache_queue(env, FetchRecords(env.tmp / "fetched.json"))
    try:
        job = _run_on(queue, _cache_spec(http_server.file("/w.pth", DATA)))
        assert job.state in ("done", "failed")
    finally:
        queue.stop()


def test_unrecorded_unpinned_cache_file_completes_without_fetching(env, http_server, monkeypatch):
    from haybale_models import download
    from haybale_models.store.records import FetchRecords

    (env.tmp / "torch").mkdir()
    (env.tmp / "torch" / "w.pth").write_bytes(b"whatever")
    records = FetchRecords(env.tmp / "fetched.json")
    queue = _cache_queue(env, records)
    # the file appears after planning: planning saw nothing
    monkeypatch.setattr(download, "find_accepted", lambda *a, **k: None)
    try:
        job = _run_on(queue, _cache_spec(http_server.file("/w.pth", DATA), sha=None))
        assert job.state == "done", job.error
        assert job.target == env.tmp / "torch" / "w.pth"
        assert (env.tmp / "torch" / "w.pth").read_bytes() == b"whatever"
        assert http_server.sent == {}
        assert records.at("haybale-models:volume:torchhub", "w.pth") == []
    finally:
        queue.stop()


def test_source_that_cannot_fill_a_cache_falls_through_to_next_mirror(env, http_server):
    from haybale_models.sources import SourceSet
    from haybale_models.sources.folder import TorchHubSource
    from haybale_models.sources.https import HttpsSource
    from haybale_models.store.records import FetchRecords

    class Plain(HttpsSource):
        name = "plain"
        prefixes = ("plain",)  # type: ignore[assignment]
        fills_target = False

    sources = SourceSet(
        [
            Plain(env.index),
            HttpsSource(env.index),
            TorchHubSource(
                name="torchhub", label="Torch Hub", locate=lambda: env.tmp / "torch", description=""
            ),
        ]
    )
    queue = DownloadQueue(env.index, sources, lambda: 2, FetchRecords(env.tmp / "fetched.json"))
    try:
        spec_ = _cache_spec("plain://x/w.pth")
        url = http_server.file("/w.pth", DATA)
        mfile = ModelFile("", SHA, None, ("plain://x/w.pth", url))
        spec_ = FetchSpec(
            entry=spec_.entry,
            resource=Resource("pytorch", "pth", None, SHA, mfile.urls, (mfile,), cache="torchhub://w.pth"),
        )
        job = _run_on(queue, spec_)
        assert job.state == "done", job.error
        assert (env.tmp / "torch" / "w.pth").read_bytes() == DATA
    finally:
        queue.stop()


def test_source_that_cannot_fill_a_cache_fails_alone(env, http_server):
    from haybale_models.sources import SourceSet
    from haybale_models.sources.folder import TorchHubSource
    from haybale_models.sources.https import HttpsSource
    from haybale_models.store.records import FetchRecords

    class Plain(HttpsSource):
        name = "plain"
        prefixes = ("plain",)  # type: ignore[assignment]
        fills_target = False

    sources = SourceSet(
        [
            Plain(env.index),
            TorchHubSource(
                name="torchhub", label="Torch Hub", locate=lambda: env.tmp / "torch", description=""
            ),
        ]
    )
    queue = DownloadQueue(env.index, sources, lambda: 2, FetchRecords(env.tmp / "fetched.json"))
    try:
        job = _run_on(queue, _cache_spec("plain://x/w.pth"))
        assert job.state == "failed"
        assert job.error == "plain:// cannot fill a cache (plain://x/w.pth)"
    finally:
        queue.stop()


def test_failing_record_write_keeps_the_job_done(env, http_server, caplog):
    from haybale_models.store.records import FetchRecords

    class Broken(FetchRecords):
        def add(self, record):
            raise OSError("read-only")

    queue = _cache_queue(env, Broken(env.tmp / "fetched.json"))
    try:
        with caplog.at_level("WARNING"):
            job = _run_on(queue, _cache_spec(http_server.file("/w.pth", DATA)))
        assert job.state == "done", job.error
        assert (env.tmp / "torch" / "w.pth").read_bytes() == DATA
        assert any(r.levelname == "WARNING" for r in caplog.records)
    finally:
        queue.stop()


def test_unrecorded_cache_file_of_the_wrong_size_is_never_overwritten(env, http_server):
    from haybale_models.store.records import FetchRecords

    (env.tmp / "torch").mkdir()
    (env.tmp / "torch" / "w.pth").write_bytes(b"short")
    queue = _cache_queue(env, FetchRecords(env.tmp / "fetched.json"))
    url = http_server.file("/w.pth", DATA)
    mfile = ModelFile("", None, len(DATA), (url,))
    spec_ = FetchSpec(
        entry=_cache_spec(url).entry,
        resource=Resource("pytorch", "pth", len(DATA), None, (url,), (mfile,), cache="torchhub://w.pth"),
    )
    try:
        job = _run_on(queue, spec_)
        assert job.state == "failed"
        assert job.error == f"a different file already exists at {env.tmp / 'torch' / 'w.pth'}"
        assert (env.tmp / "torch" / "w.pth").read_bytes() == b"short"
        assert http_server.sent == {}
    finally:
        queue.stop()


def test_stale_record_does_not_license_an_overwrite(env, http_server):
    from haybale_models.store.records import FetchRecord, FetchRecords

    (env.tmp / "torch").mkdir()
    (env.tmp / "torch" / BAD_NAME).write_bytes(b"replaced by someone else")
    records = FetchRecords(env.tmp / "fetched.json")
    records.add(
        FetchRecord(
            "haybale-models:volume:torchhub", BAD_NAME, SHA, "lib:catalog:demo", f"torchhub://{BAD_NAME}", 3
        )
    )
    queue = _cache_queue(env, records)
    try:
        job = _run_on(queue, _cache_spec(http_server.file("/w.pth", DATA), name=BAD_NAME))
        assert job.state == "failed"
        assert job.error == f"a different file already exists at {env.tmp / 'torch' / BAD_NAME}"
    finally:
        queue.stop()


def test_fetch_records_the_file_size(env, http_server):
    from haybale_models.store.records import FetchRecords

    records = FetchRecords(env.tmp / "fetched.json")
    queue = _cache_queue(env, records)
    try:
        job = _run_on(queue, _cache_spec(http_server.file("/w.pth", DATA)))
        assert job.state == "done", job.error
        assert records.at("haybale-models:volume:torchhub", "w.pth")[0].size == len(DATA)
    finally:
        queue.stop()


def test_relocated_cache_volume_with_a_missing_folder_fails_the_job(env, http_server, models_env):
    from haybale_models.store.records import FetchRecords

    queue = _cache_queue(env, FetchRecords(env.tmp / "fetched.json"))
    from haybale_models.sources.folder import FolderSource

    source = queue._sources.lookup("torchhub://w.pth")
    assert isinstance(source, FolderSource)
    source.ensure()
    moved = env.tmp / "moved" / "torch"
    models_env.update(source.volume, location=moved)
    try:
        job = _run_on(queue, _cache_spec(http_server.file("/w.pth", DATA)))
        assert job.state == "failed"
        assert job.error == f"Torch Hub cache volume folder does not exist: {moved}"
        assert not (env.tmp / "moved").exists()
        assert not (env.tmp / "torch").exists()
        assert http_server.sent == {}
    finally:
        queue.stop()


C = "a" * 40


def whole_spec(include: tuple[str, ...] = (), urls: tuple[str, ...] = (f"hf://org/repo@{C}",)) -> FetchSpec:
    entry = SimpleNamespace(class_identity=SimpleNamespace(registry_key="lib:catalog:demo"), name="demo")
    resource = Resource(
        "diffusers", "dir", None, None, urls, (ModelFile("", None, None, urls),), include=include
    )
    return FetchSpec(entry=entry, resource=resource)  # type: ignore[arg-type]


def test_whole_repo_fetch_downloads_the_snapshot(env, monkeypatch):
    seen: dict[str, Any] = {}

    def fake(uri, cache_dir, include, expected_size, on_progress, cancel):
        # the snapshot appears only when fetched: a present one is not queued at all
        seen.update(uri=uri, include=include)
        seen["snapshot"] = make_hf_snapshot(
            env.tmp / "hf", "org/repo", C, {"a.safetensors": b"1"}, ["a.safetensors"]
        )
        return seen["snapshot"]

    monkeypatch.setattr(hf, "download_snapshot", fake)
    job = env.run(whole_spec(include=("*.safetensors",)))
    assert job.state == "done", job.error
    assert job.target == seen["snapshot"]
    assert seen["include"] == ("*.safetensors",)


def test_whole_repo_with_a_branch_fails_the_fetch(env, monkeypatch):
    def boom(*a, **k):
        raise AssertionError("must not download")

    monkeypatch.setattr(hf, "download_snapshot", boom)
    job = env.run(whole_spec(urls=("hf://org/repo@main",)))
    assert job.state == "failed"
    assert "needs a commit" in (job.error or "")


def test_include_matching_nothing_fails_the_fetch(env, monkeypatch):
    def fake(*a, **k):
        raise ValueError(f"no file of org/repo@{C} matches include ['*.gguf']")

    monkeypatch.setattr(hf, "download_snapshot", fake)
    job = env.run(whole_spec(include=("*.gguf",)))
    assert job.state == "failed"
    assert "matches include" in (job.error or "")


def test_whole_repo_fetch_that_leaves_a_partial_snapshot_fails(env, monkeypatch):
    snapshot = make_hf_snapshot(env.tmp / "hf", "org/repo", C, {"a.bin": b"1"}, ["a.bin", "missing.bin"])
    monkeypatch.setattr(hf, "download_snapshot", lambda *a, **k: snapshot)
    job = env.run(whole_spec())
    assert job.state == "failed"
    assert "incomplete snapshot" in (job.error or "")


def test_running_whole_repo_job_is_not_cancellable(env, monkeypatch):
    started, release = threading.Event(), threading.Event()

    def fake(uri, cache_dir, include, expected_size, on_progress, cancel):
        started.set()
        release.wait(3)
        return make_hf_snapshot(cache_dir, "org/repo", C, {"a.bin": b"1"}, ["a.bin"])

    monkeypatch.setattr(hf, "download_snapshot", fake)
    job_id = env.queue.enqueue(whole_spec(), None)
    assert started.wait(2)
    assert env.queue.cancel(job_id) is False
    release.set()
    assert env.wait(job_id).state == "done"


def test_present_snapshot_is_not_queued(env, monkeypatch):
    make_hf_snapshot(env.hf_dir, "org/repo", C, {"a.bin": b"1"}, ["a.bin"])
    monkeypatch.setattr(hf, "download_snapshot", lambda *a, **k: pytest.fail("must not download"))
    assert env.queue.enqueue_all(whole_spec(), None) == []


def test_same_repo_different_include_are_two_jobs(env, monkeypatch):
    release = threading.Event()
    monkeypatch.setattr(hf, "download_snapshot", lambda *a, **k: release.wait(3) and Path("/nonexistent"))
    first = env.queue.enqueue(whole_spec(include=("*.onnx",)), None)
    second = env.queue.enqueue(whole_spec(include=("*.safetensors",)), None)
    release.set()
    assert first
    assert second
    assert first != second


def test_same_whole_repo_spec_dedups(env, monkeypatch):
    release = threading.Event()
    monkeypatch.setattr(hf, "download_snapshot", lambda *a, **k: release.wait(3) and Path("/nonexistent"))
    first = env.queue.enqueue(whole_spec(include=("*.onnx",)), None)
    second = env.queue.enqueue(whole_spec(include=("*.onnx",)), None)
    release.set()
    assert first == second


def test_folder_resource_skips_a_file_mirror(env, monkeypatch, http_server):
    def boom(*a, **k):
        raise ValueError("snapshot failed")

    monkeypatch.setattr(hf, "download_snapshot", boom)
    mirror = http_server.file("/w.bin", DATA)
    job = env.run(whole_spec(urls=(f"hf://org/repo@{C}", mirror)))
    assert job.state == "failed"
    assert "not a folder address" in (job.error or "")
    assert not list((env.tmp / "models").rglob("w.bin"))


def test_file_ref_with_whole_repo_address_is_not_queued(env, monkeypatch):
    monkeypatch.setattr(hf, "download_snapshot", lambda *a, **k: pytest.fail("must not download"))
    assert env.queue.enqueue_all(spec(f"hf://org/repo@{C}", sha=None), None) == []


def test_a_failed_job_reads_reason_first_then_address(env, http_server):
    url = http_server.status("/gone", 404)
    job = env.run(spec(url))
    assert job.error == f"HTTP 404 ({url})"


def test_an_unserved_address_reads_reason_first(env):
    job = env.run(spec("nope://x"))
    assert job.error == "source unavailable: nope:// not provided (nope://x)"


def test_expected_download_failures_stay_out_of_the_ledger(env, http_server, error_ledger):
    env.run(spec(http_server.status("/gone", 404)))
    env.run(spec(http_server.html("/page")))
    env.run(spec(http_server.file("/bad", b"wrong")))
    env.run(spec("nope://x"))
    assert error_ledger.current_seq == 0


def test_a_bug_in_a_fetch_reaches_the_ledger_and_fails_the_job(env, http_server, error_ledger, monkeypatch):
    def broken(self: Any, request: Any) -> Path:
        raise TypeError("a bug")

    monkeypatch.setattr("haybale_models.sources.https.HttpsSource.fetch", broken)
    job = env.run(spec(http_server.file("/w.pth", DATA)))
    assert job.state == "failed"
    assert "a bug" in (job.error or "")
    assert error_ledger.current_seq == 1
