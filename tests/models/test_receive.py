"""An upload as a download job: checks, records, refusals and which failed jobs offer it."""

from __future__ import annotations

import hashlib
import shutil
from collections.abc import Iterator
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from haywire.core.catalog import ModelFile, Resource
from haywire.core.farmhand.activity import activity_tracker
from haywire.core.volumes import VolumeStore

from tests.models.test_download import DATA, SHA, Env, spec, wait_until

from haybale_models.receive import ReceiveRefused
from haybale_models.resolver import FetchSpec, locate_resource
from haybale_models.sources import DownloadCancelled, SourceFailed
from haybale_models.status import resource_status
from haybale_models.store.records import FetchRecords


@pytest.fixture
def env(models_env: VolumeStore, tmp_path: Path) -> Iterator[Env]:
    (tmp_path / "models").mkdir(exist_ok=True)
    e = Env(tmp_path)
    activity_tracker().clear()
    yield e
    e.queue.stop()
    activity_tracker().clear()


def failed(env: Env, server: Any, the_spec: FetchSpec | None = None, *, sha: str | None = SHA) -> str:
    """Return the id of a job that failed on an address answering 404."""
    job = env.run(the_spec or spec(server.status("/gone", 404), sha=sha))
    assert job.state == "failed"
    return job.id


def entry(name: str = "model") -> Any:
    return SimpleNamespace(
        library=SimpleNamespace(name="lib"),
        path=Path(f"cat/{name}.json"),
        name=name,
        class_identity=SimpleNamespace(registry_key=f"lib:{name}"),
    )


def single(url: str, *, sha: str | None = SHA, cache: str | None = None) -> Resource:
    file = ModelFile("", sha, len(DATA), (url,), cache=cache)
    return Resource(platform="pytorch", type="pth", size=len(DATA), sha256=sha, urls=(url,), files=(file,))


def test_upload_with_digest_lands_like_a_download(env, http_server):
    old = failed(env, http_server)
    receiver = env.queue.begin_receive(old, "w.pth", "tester")
    job = env.job(receiver.job_id)
    assert job.state == "running"
    assert job.via_browser
    assert job.cancellable
    receiver.write(DATA[:100])
    receiver.write(DATA[100:])
    path = receiver.finish()
    job = env.job(receiver.job_id)
    assert job.state == "done", job.error
    assert job.target == path
    assert path.read_bytes() == DATA
    assert env.index.by_sha256(SHA) == path
    assert job.done_bytes == len(DATA)
    records = [r for r in activity_tracker().recent() if r.tool == "models.download"]
    assert "browser" in str(records[0].arguments)
    assert records[0].ok is True


def test_the_failed_job_stays_listed(env, http_server):
    old = failed(env, http_server)
    receiver = env.queue.begin_receive(old, "w.pth", "tester")
    assert env.job(old).state == "failed"
    receiver.abort()


def test_wrong_digest_refused_with_expected_text(env, http_server):
    old = failed(env, http_server)
    receiver = env.queue.begin_receive(old, "w.pth", "tester")
    receiver.write(b"not the model")
    with pytest.raises(SourceFailed):
        receiver.finish()
    job = env.job(receiver.job_id)
    assert job.state == "failed"
    assert job.error is not None
    assert SHA in job.error
    assert hashlib.sha256(b"not the model").hexdigest() in job.error
    assert job.target is None
    assert not list((env.tmp / "models").rglob("*.part"))
    assert not list((env.tmp / "models").rglob("w.pth"))


def test_over_expected_size_stops_at_the_write(env, http_server):
    the_spec = spec(http_server.status("/gone", 404), size=10)
    receiver = env.queue.begin_receive(failed(env, http_server, the_spec), "w.pth", "tester")
    receiver.write(b"12345")
    with pytest.raises(SourceFailed, match="expected 10"):
        receiver.write(b"123456")
    assert env.job(receiver.job_id).state == "failed"
    assert not list((env.tmp / "models").rglob("*.part"))


def test_a_refused_upload_can_be_followed_by_the_right_file(env, http_server):
    old = failed(env, http_server)
    wrong = env.queue.begin_receive(old, "w.pth", "tester")
    wrong.write(b"nope")
    with pytest.raises(SourceFailed):
        wrong.finish()
    right = env.queue.begin_receive(old, "w.pth", "tester")
    right.write(DATA)
    assert right.finish().read_bytes() == DATA


def test_cache_target_gets_a_fetch_record(models_env, tmp_path, http_server, monkeypatch):
    from haybale_models.download import DownloadQueue
    from haybale_models.sources import builtin_sources
    from haybale_models.store.index import ModelIndex

    (tmp_path / "models").mkdir(exist_ok=True)
    monkeypatch.setenv("TORCH_HOME", str(tmp_path / "torch"))
    index = ModelIndex()
    records = FetchRecords(tmp_path / "fetched.json")
    queue = DownloadQueue(
        index, builtin_sources(index, hf_cache=lambda: None, records=records), lambda: 2, records=records
    )
    url = http_server.status("/gone", 404)
    file = ModelFile("", SHA, len(DATA), (url,), cache="torchhub://w.pth")
    resource = Resource(
        platform="pytorch", type="pth", size=len(DATA), sha256=SHA, urls=(url,), files=(file,)
    )
    job_id = queue.enqueue(FetchSpec(entry=entry(), resource=resource), "tester")
    wait_until(lambda: next(j for j in queue.jobs() if j.id == job_id).state == "failed")
    try:
        receiver = queue.begin_receive(job_id, "ignored.pth", "tester")
        receiver.write(DATA)
        path = receiver.finish()
        assert path.name == "w.pth"
        assert path.is_relative_to(tmp_path / "torch")
        assert index.by_sha256(SHA) is None
        assert records.all()
    finally:
        queue.stop()


def test_hf_with_digest_lands_in_models_volume_and_resolves(env):
    url = "hf://org/repo/w.pth@" + "a" * 40
    resource = single(url)
    env.hf_dir = None  # the Hugging Face cache cannot serve it
    job = env.run(FetchSpec(entry=entry(), resource=resource))
    assert job.state == "failed"
    receiver = env.queue.begin_receive(job.id, "w.pth", "tester")
    receiver.write(DATA)
    path = receiver.finish()
    assert path.is_relative_to(env.tmp / "models")
    found = locate_resource(resource, env.index, env.queue._sources)
    assert found is not None
    assert path in found[0].values()


def test_no_digest_resolves_through_first_address(env, http_server):
    url = http_server.status("/gone", 404)
    old = failed(env, http_server, spec(url, sha=None))
    receiver = env.queue.begin_receive(old, "w.pth", "tester")
    receiver.write(DATA)
    path = receiver.finish()
    record = env.index.by_source(url)
    assert record is not None
    assert record.sha256 == SHA
    assert env.queue._sources.lookup(url).find(url) == path


def test_no_digest_name_taken_keeps_both(env, http_server):
    url = http_server.status("/gone", 404)
    first = env.queue.begin_receive(failed(env, http_server, spec(url, sha=None)), "model.pth", "t")
    first.write(b"first file")
    first_path = first.finish()
    second = env.queue.begin_receive(failed(env, http_server, spec(url, sha=None)), "model.pth", "t")
    second.write(DATA)
    second_path = second.finish()
    assert second_path != first_path
    assert second_path.name == f"model-{SHA[:8]}.pth"
    assert first_path.read_bytes() == b"first file"
    assert second_path.read_bytes() == DATA
    assert env.index.by_sha256(SHA) == second_path


def test_same_file_again_replaces_itself(env, http_server):
    url = http_server.status("/gone", 404)
    first = env.queue.begin_receive(failed(env, http_server, spec(url, sha=None)), "model.pth", "t")
    first.write(DATA)
    first_path = first.finish()
    second = env.queue.begin_receive(failed(env, http_server, spec(url, sha=None)), "model.pth", "t")
    second.write(DATA)
    assert second.finish() == first_path


def test_mega_link_stored_under_uploaded_name(env):
    url = "https://127.0.0.1:9/file/Bc0SmIyK#key"
    job = env.run(FetchSpec(entry=entry("compact"), resource=single(url)))
    assert job.state == "failed"
    receiver = env.queue.begin_receive(job.id, "2x-Compact-Pretrain.pth", "tester")
    receiver.write(DATA)
    assert receiver.finish() == env.tmp / "models" / "lib" / "compact" / "2x-Compact-Pretrain.pth"


def test_abort_cancels_and_removes_part(env, http_server):
    old = failed(env, http_server)
    receiver = env.queue.begin_receive(old, "w.pth", "tester")
    receiver.write(DATA[:10])
    receiver.abort()
    receiver.abort()
    assert env.job(receiver.job_id).state == "cancelled"
    assert not list((env.tmp / "models").rglob("*.part"))
    again = env.queue.begin_receive(old, "w.pth", "tester")  # the claim was released
    again.abort()


def test_abort_with_a_reason_fails_the_job(env, http_server):
    receiver = env.queue.begin_receive(failed(env, http_server), "w.pth", "tester")
    receiver.abort("size mismatch: got 1 bytes, expected 2")
    job = env.job(receiver.job_id)
    assert job.state == "failed"
    assert job.error == "size mismatch: got 1 bytes, expected 2"


def test_cancel_from_row_stops_the_next_write(env, http_server):
    receiver = env.queue.begin_receive(failed(env, http_server), "w.pth", "tester")
    assert env.queue.cancel(receiver.job_id) is True
    with pytest.raises(DownloadCancelled):
        receiver.write(DATA)
    receiver.abort()
    assert env.job(receiver.job_id).state == "cancelled"
    assert not list((env.tmp / "models").rglob("*.part"))


def test_an_active_upload_refuses_a_second_and_dedups_a_download(env, http_server):
    the_spec = spec(http_server.status("/gone", 404))
    old = failed(env, http_server, the_spec)
    receiver = env.queue.begin_receive(old, "w.pth", "tester")
    with pytest.raises(ReceiveRefused, match="running"):
        env.queue.begin_receive(old, "w.pth", "tester")
    assert env.queue.enqueue(the_spec, "tester") == receiver.job_id
    receiver.abort()


def test_upload_ignores_max_parallel(env, http_server):
    env.parallel = 1
    receiver = env.queue.begin_receive(failed(env, http_server), "w.pth", "tester")
    job = env.run(spec(http_server.file("/other", b"other"), sha=None))
    assert job.state == "done", job.error
    receiver.abort()


def test_unavailable_models_volume_refuses(env, http_server, monkeypatch):
    from haywire.core.volumes import VolumeError

    old = failed(env, http_server)

    def unavailable(_key: str) -> Path:
        raise VolumeError("models volume is offline")

    monkeypatch.setattr("haybale_models.download.location_of", unavailable)
    with pytest.raises(ReceiveRefused, match="offline"):
        env.queue.begin_receive(old, "w.pth", "tester")


@pytest.mark.parametrize(
    ("address", "sha", "expected"),
    [
        ("{gone}", SHA, True),
        ("{gone}", None, True),
        ("hf://org/repo/w.pth@" + "a" * 40, SHA, True),
        ("hf://org/repo/w.pth@" + "a" * 40, None, False),
    ],
)
def test_assistable_rules_for_addresses(env, http_server, address, sha, expected):
    env.hf_dir = None
    url = address.format(gone=http_server.status("/gone", 404))
    job = env.run(spec(url, sha=sha))
    assert job.state == "failed"
    assert env.queue.assistable(job.id) is expected


def test_a_running_or_done_job_is_not_assistable(env, http_server):
    done = env.run(spec(http_server.file("/w.pth", DATA)))
    assert env.queue.assistable(done.id) is False
    assert env.queue.assistable("dl-unknown") is False
    receiver = env.queue.begin_receive(failed(env, http_server, sha="a" * 64), "w.pth", "t")
    assert env.queue.assistable(receiver.job_id) is False
    receiver.abort()


def test_a_whole_repo_job_is_not_assistable(env):
    env.hf_dir = None
    url = "hf://org/repo@" + "a" * 40
    resource = Resource(
        platform="pytorch", type="pth", size=None, sha256=None, urls=(url,), files=(), include=("*.bin",)
    )
    job = env.run(FetchSpec(entry=entry(), resource=resource))
    assert job.state == "failed"
    assert env.queue.assistable(job.id) is False


def test_a_cache_target_without_digest_is_assistable(env):
    url = "hf://org/repo/w.pth@" + "a" * 40
    file = ModelFile("", None, None, (url,), cache="torchhub://w.pth")
    resource = Resource(platform="pytorch", type="pth", size=None, sha256=None, urls=(url,), files=(file,))
    env.hf_dir = None
    job = env.run(FetchSpec(entry=entry(), resource=resource))
    assert job.state == "failed"
    assert env.queue.assistable(job.id) is True


def test_retried_file_is_not_assistable_after_success(env, http_server):
    gone = http_server.status("/flaky", 404)
    the_spec = spec(gone)
    old = failed(env, http_server, the_spec)
    assert env.queue.assistable(old) is True
    http_server.file("/flaky", DATA)
    assert env.run(the_spec).state == "done"
    assert env.queue.assistable(old) is False


def test_refused_for_a_job_that_is_not_assistable(env, http_server):
    done = env.run(spec(http_server.file("/w.pth", DATA)))
    with pytest.raises(ReceiveRefused):
        env.queue.begin_receive(done.id, "w.pth", "tester")


def test_status_reads_uploading(env, http_server):
    the_spec = spec(http_server.status("/gone", 404), size=len(DATA))
    receiver = env.queue.begin_receive(failed(env, http_server, the_spec), "w.pth", "tester")
    assert resource_status(None, [env.job(receiver.job_id)]) == "uploading…"
    receiver.write(DATA[: len(DATA) // 2])
    assert resource_status(None, [env.job(receiver.job_id)]) == "uploading 50 %"
    receiver.abort()


def test_an_error_flushing_at_finish_ends_the_job(env, http_server):
    receiver = env.queue.begin_receive(failed(env, http_server), "w.pth", "tester")
    receiver.write(DATA)

    class Failing:
        def close(self) -> None:
            raise OSError("no space left on device")

    receiver._out.close()
    receiver._out = Failing()  # type: ignore[assignment]
    with pytest.raises(OSError, match="no space"):
        receiver.finish()
    job = env.job(receiver.job_id)
    assert job.state == "failed"
    assert "no space" in (job.error or "")
    assert not list((env.tmp / "models").rglob("*.part"))


def test_a_missing_models_folder_is_refused_not_recreated(env, http_server):
    old = failed(env, http_server)
    shutil.rmtree(env.tmp / "models")
    with pytest.raises(ReceiveRefused, match="does not exist"):
        env.queue.begin_receive(old, "w.pth", "tester")
    assert not (env.tmp / "models").exists()


def test_a_name_the_disk_rejects_is_refused_and_releases_the_claim(env, http_server):
    old = failed(env, http_server)
    with pytest.raises(ReceiveRefused):
        env.queue.begin_receive(old, "n" * 300 + ".pth", "tester")
    assert env.queue._writing == set()
    assert not [j for j in env.queue.jobs() if j.via_browser]


def test_a_failure_after_the_claim_releases_it(env, http_server, monkeypatch):
    old = failed(env, http_server)

    class Broken:
        def start(self, *args: Any, **kwargs: Any) -> int:
            raise ValueError("tracker is broken")

    monkeypatch.setattr("haybale_models.download.activity_tracker", lambda: Broken())
    with pytest.raises(ReceiveRefused, match="tracker is broken"):
        env.queue.begin_receive(old, "w.pth", "tester")
    assert env.queue._writing == set()


def test_a_refused_upload_stays_out_of_the_ledger(env, http_server, error_ledger):
    receiver = env.queue.begin_receive(failed(env, http_server), "w.pth", "tester")
    receiver.write(b"wrong")
    with pytest.raises(SourceFailed):
        receiver.finish()
    with pytest.raises(ReceiveRefused):
        env.queue.begin_receive("dl-unknown", "w.pth", "tester")
    assert error_ledger.current_seq == 0


def test_a_bug_starting_an_upload_reaches_the_ledger(env, http_server, error_ledger, monkeypatch):
    old = failed(env, http_server)

    class Broken:
        def start(self, *args: Any, **kwargs: Any) -> int:
            raise ValueError("tracker is broken")

    monkeypatch.setattr("haybale_models.download.activity_tracker", lambda: Broken())
    with pytest.raises(ReceiveRefused, match="tracker is broken"):
        env.queue.begin_receive(old, "w.pth", "tester")
    assert error_ledger.current_seq == 1


def test_a_name_the_disk_rejects_stays_out_of_the_ledger(env, http_server, error_ledger):
    with pytest.raises(ReceiveRefused):
        env.queue.begin_receive(failed(env, http_server), "n" * 300 + ".pth", "tester")
    assert error_ledger.current_seq == 0
