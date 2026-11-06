"""Fetch records: round trip, unreadable file, relocated volume."""

from __future__ import annotations

import hashlib
import logging
import shutil
import threading
import time
from pathlib import Path
from types import SimpleNamespace
from typing import cast

from haybale_models.download import DownloadQueue
from haybale_models.sources import SourceSet
from haybale_models.sources.folder import TorchHubSource
from haybale_models.sources.https import HttpsSource
from haybale_models.store.index import ModelIndex
from haybale_models.store.records import FetchRecord, FetchRecords
from haybale_models.resolver import FetchSpec

from haywire.core.catalog import CatalogEntry, ModelFile, Resource
from haywire.core.volumes import VolumeStore, location_of

VOLUME = "haybale-models:volume:torchhub"


def record(relative: str = "w.pth", entry_key: str = "lib:catalog:demo") -> FetchRecord:
    return FetchRecord(VOLUME, relative, "a" * 64, entry_key, f"torchhub://{relative}")


def test_records_round_trip(tmp_path: Path) -> None:
    path = tmp_path / "sub" / "fetched.json"
    records = FetchRecords(path)
    assert records.at(VOLUME, "w.pth") == []
    one, two = record("w.pth"), record("v.pth", "lib:catalog:other")
    records.add(one)
    records.add(two)
    assert records.at(VOLUME, "w.pth") == [one]
    assert records.for_entry("lib:catalog:other") == [two]
    reloaded = FetchRecords(path)
    assert reloaded.at(VOLUME, "v.pth") == [two]
    reloaded.remove(VOLUME, "w.pth")
    assert FetchRecords(path).at(VOLUME, "w.pth") == []
    assert not list(tmp_path.rglob("*.tmp"))


def test_adding_the_same_file_replaces_its_record(tmp_path: Path) -> None:
    records = FetchRecords(tmp_path / "f.json")
    records.add(record(entry_key="a"))
    records.add(record(entry_key="b"))
    assert [r.entry_key for r in records.at(VOLUME, "w.pth")] == ["b"]


def test_unreadable_file_reads_empty(tmp_path: Path, caplog) -> None:
    path = tmp_path / "f.json"
    path.write_text("{not json")
    with caplog.at_level(logging.WARNING):
        records = FetchRecords(path)
    assert records.at(VOLUME, "w.pth") == []
    assert "unreadable" in caplog.text
    records.add(record())
    assert FetchRecords(path).at(VOLUME, "w.pth") == [record()]


def test_concurrent_adds_all_land(tmp_path: Path) -> None:
    records = FetchRecords(tmp_path / "f.json")
    threads = [threading.Thread(target=records.add, args=(record(f"{n}.pth"),)) for n in range(20)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert len(FetchRecords(tmp_path / "f.json").for_entry("lib:catalog:demo")) == 20


def test_records_follow_a_relocated_volume(models_env: VolumeStore, tmp_path: Path, http_server) -> None:
    data = b"weights" * 100
    sha = hashlib.sha256(data).hexdigest()
    index = ModelIndex()
    source = TorchHubSource(
        name="torchhub", label="Torch Hub", locate=lambda: tmp_path / "torch", description=""
    )
    sources = SourceSet([HttpsSource(index), source])
    records = FetchRecords(tmp_path / "fetched.json")
    queue = DownloadQueue(index, sources, lambda: 2, records)
    (tmp_path / "models").mkdir(exist_ok=True)
    key = "lib:catalog:demo"
    entry = cast(
        CatalogEntry,
        SimpleNamespace(class_identity=SimpleNamespace(registry_key=key), name="demo"),
    )
    url = http_server.file("/w.pth", data)
    resource = Resource(
        "pytorch", "pth", None, sha, (url,), (ModelFile("", sha, None, (url,)),), cache="torchhub://w.pth"
    )
    job_id = queue.enqueue(FetchSpec(entry=entry, resource=resource), "tester")
    deadline = time.monotonic() + 4
    while time.monotonic() < deadline and any(j.state in ("queued", "running") for j in queue.jobs()):
        time.sleep(0.01)
    assert [j.state for j in queue.jobs() if j.id == job_id] == ["done"]
    old_root = location_of(VOLUME, models_env)
    assert source.find("torchhub://w.pth") == old_root / "w.pth"

    new_root = tmp_path / "moved"
    shutil.move(str(old_root), new_root)
    models_env.update(VOLUME, location=new_root)

    assert source.find("torchhub://w.pth") == new_root / "w.pth"
    found = records.at(VOLUME, "w.pth")
    assert len(found) == 1
    assert found[0].entry_key == key
    assert (new_root / found[0].relative).read_bytes() == data
    queue.stop()


def test_listeners_fire_on_add_and_on_a_real_remove_only(tmp_path: Path) -> None:
    records = FetchRecords(tmp_path / "f.json")
    calls: list[int] = []

    def cb() -> None:
        calls.append(1)

    records.add_listener(cb)
    records.add(record())
    assert len(calls) == 1
    records.remove(VOLUME, "unknown.pth")
    assert len(calls) == 1
    records.remove(VOLUME, "w.pth")
    assert len(calls) == 2
    records.remove_listener(cb)
    records.add(record())
    assert len(calls) == 2


def test_a_failed_save_on_remove_still_notifies(tmp_path: Path, monkeypatch) -> None:
    import pytest

    records = FetchRecords(tmp_path / "f.json")
    records.add(record())
    calls: list[int] = []
    records.add_listener(lambda: calls.append(1))

    def broken() -> None:
        raise OSError("read-only")

    monkeypatch.setattr(records, "_save", broken)
    with pytest.raises(OSError, match="read-only"):
        records.remove(VOLUME, "w.pth")
    assert calls == [1]
    assert records.at(VOLUME, "w.pth") == []


def test_a_record_without_size_reads_as_unknown(tmp_path: Path) -> None:
    path = tmp_path / "f.json"
    path.write_text(
        '{"records": [{"volume": "%s", "relative": "w.pth", '
        '"sha256": "", "entry_key": "k", "address": "a"}]}' % VOLUME
    )
    found = FetchRecords(path).at(VOLUME, "w.pth")
    assert len(found) == 1
    assert found[0].size is None
    assert found[0].current(123)
    assert not FetchRecord(VOLUME, "w.pth", "", "k", "a", 5).current(6)
