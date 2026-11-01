"""ModelIndex: digest index of the models volume."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from unittest.mock import patch

import pytest

from haybale_models.keys import MODELS_VOLUME
from haybale_models.store.index import ModelIndex

from haywire.core.volumes import VolumeStore, location_of


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def drop(path: Path, data: bytes) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)
    return path


def _root(store: VolumeStore) -> Path:
    return location_of(MODELS_VOLUME, store)


@pytest.fixture
def index(models_env: VolumeStore) -> ModelIndex:
    _root(models_env).mkdir(parents=True, exist_ok=True)
    return ModelIndex()


def test_rescan_picks_up_dropped_file(models_env: VolumeStore, index: ModelIndex) -> None:
    root = _root(models_env)
    drop(root / "mine" / "x.pth", b"abc")
    assert index.scan() == [root / "mine" / "x.pth"]
    assert index.pending() == {root / "mine" / "x.pth": 0.0}
    index.hash_pending()
    assert index.pending() == {}
    assert index.by_sha256(sha(b"abc")) == root / "mine" / "x.pth"
    assert index.sha256_at(root / "mine" / "x.pth") == sha(b"abc")


def test_moved_file_resolves_by_digest(models_env: VolumeStore, index: ModelIndex) -> None:
    root = _root(models_env)
    old = drop(root / "a" / "x.pth", b"abc")
    index.scan()
    index.hash_pending()
    index.add(old, sha(b"abc"), "https://example.com/x.pth")
    new = root / "b" / "x.pth"
    new.parent.mkdir()
    old.rename(new)
    index.scan()
    index.hash_pending()
    assert index.by_sha256(sha(b"abc")) == new
    rec = index.by_source("https://example.com/x.pth")
    assert rec is not None
    assert rec.relative == "b/x.pth"


def test_unchanged_file_is_not_rehashed(models_env: VolumeStore, index: ModelIndex) -> None:
    root = _root(models_env)
    drop(root / "x.pth", b"abc")
    index.scan()
    index.hash_pending()
    with patch("haybale_models.store.index.hashlib.sha256", wraps=hashlib.sha256) as spy:
        assert index.scan() == []
        index.hash_pending()
    assert spy.call_count == 0
    assert index.by_sha256(sha(b"abc")) == root / "x.pth"


def test_vanished_file_drops_out(models_env: VolumeStore, index: ModelIndex) -> None:
    root = _root(models_env)
    path = drop(root / "x.pth", b"abc")
    index.scan()
    index.hash_pending()
    path.unlink()
    index.scan()
    assert index.records() == []


def test_scan_on_missing_volume_is_empty_and_reports(tmp_path: Path) -> None:
    from haywire.core.volumes import get_volume_store, set_volume_store

    previous = get_volume_store()
    set_volume_store(VolumeStore(tmp_path / "v.toml"))
    try:
        index = ModelIndex()
        assert index.scan() == []
        assert index.problem
        assert not list(tmp_path.glob("**/.index.json"))
    finally:
        set_volume_store(previous)


def test_scan_on_absent_location_creates_nothing(models_env: VolumeStore, tmp_path: Path) -> None:
    index = ModelIndex()  # location tmp_path/models was never created
    assert index.scan() == []
    assert index.problem
    assert not (tmp_path / "models").exists()


def test_index_file_written_atomically_and_reloaded(models_env: VolumeStore, index: ModelIndex) -> None:
    root = _root(models_env)
    drop(root / "x.pth", b"abc")
    index.scan()
    index.hash_pending()
    data = json.loads((root / ".index.json").read_text())
    assert data["version"] == 1
    assert data["files"][0]["sha256"] == sha(b"abc")
    assert not (root / ".index.json.tmp").exists()
    fresh = ModelIndex()
    with patch("haybale_models.store.index.hashlib.sha256", wraps=hashlib.sha256) as spy:
        assert fresh.scan() == []
    assert spy.call_count == 0
    assert fresh.by_sha256(sha(b"abc")) == root / "x.pth"


def test_part_and_dot_files_skipped(models_env: VolumeStore, index: ModelIndex) -> None:
    root = _root(models_env)
    drop(root / "x.pth.part", b"1")
    drop(root / ".hidden", b"2")
    drop(root / ".cache" / "y.bin", b"3")
    ok = drop(root / "ok.bin", b"4")
    assert index.scan() == [ok]


def test_listeners_fire(models_env: VolumeStore, index: ModelIndex) -> None:
    root = _root(models_env)
    calls: list[int] = []
    cb = lambda: calls.append(1)  # noqa: E731
    index.add_listener(cb)
    drop(root / "x.pth", b"abc")
    index.scan()
    index.hash_pending()
    index.remove(sha(b"abc"))
    assert len(calls) == 3
    index.remove_listener(cb)
    index.scan()
    assert len(calls) == 3


def test_lookup_not_blocked_by_scan_walk(models_env: VolumeStore, index: ModelIndex) -> None:
    import os
    import threading

    real_walk = os.walk
    in_walk = threading.Event()
    release = threading.Event()

    def slow_walk(top: Path):  # type: ignore[no-untyped-def]
        in_walk.set()
        assert release.wait(5)
        yield from real_walk(top)

    drop(_root(models_env) / "a.bin", b"a")
    with patch("haybale_models.store.index.os.walk", slow_walk):
        scanner = threading.Thread(target=index.scan)
        scanner.start()
        assert in_walk.wait(5)
        result: list[object] = []
        looker = threading.Thread(target=lambda: result.append(index.by_sha256("x") or "none"))
        looker.start()
        looker.join(2)
        finished = not looker.is_alive()
        release.set()
        scanner.join(5)
    assert finished
    assert result == ["none"]


def test_concurrent_hash_pending_hashes_each_file_once(models_env: VolumeStore, index: ModelIndex) -> None:
    import threading

    drop(_root(models_env) / "a.bin", b"aaa")
    drop(_root(models_env) / "b.bin", b"bbb")
    index.scan()

    calls = 0
    real = hashlib.sha256
    first_in = threading.Event()
    release = threading.Event()

    def spy(*args: object, **kwargs: object):  # type: ignore[no-untyped-def]
        nonlocal calls
        calls += 1
        return real(*args, **kwargs)  # type: ignore[arg-type]

    def block(_p: Path, _d: int, _s: int) -> None:
        first_in.set()
        assert release.wait(5)

    with patch("haybale_models.store.index.hashlib.sha256", spy):
        t1 = threading.Thread(target=index.hash_pending, args=(block,))
        t1.start()
        assert first_in.wait(5)
        t2 = threading.Thread(target=index.hash_pending)
        t2.start()
        release.set()
        t1.join(5)
        t2.join(5)
    assert calls == 2
    assert len(index.records()) == 2


def _blocked_walk(in_walk, release):  # type: ignore[no-untyped-def]
    import os

    real_walk = os.walk

    def walk(top: Path):  # type: ignore[no-untyped-def]
        listing = list(real_walk(top))  # the volume is listed BEFORE the pause
        in_walk.set()
        assert release.wait(5)
        yield from listing

    return walk


def test_add_during_walk_is_kept(models_env: VolumeStore, index: ModelIndex) -> None:
    import threading

    in_walk, release = threading.Event(), threading.Event()
    with patch("haybale_models.store.index.os.walk", _blocked_walk(in_walk, release)):
        scanner = threading.Thread(target=index.scan)
        scanner.start()
        assert in_walk.wait(5)
        new = drop(_root(models_env) / "dl.bin", b"downloaded")  # renamed after the listing
        index.add(new, sha(b"downloaded"), "hf://x")
        release.set()
        scanner.join(5)
    assert index.by_sha256(sha(b"downloaded")) == new
    assert index.by_source("hf://x") is not None
    saved = json.loads((_root(models_env) / ".index.json").read_text())
    assert [f["relative"] for f in saved["files"]] == ["dl.bin"]


def test_remove_during_walk_is_not_resurrected(models_env: VolumeStore, index: ModelIndex) -> None:
    import threading

    drop(_root(models_env) / "a.bin", b"aaa")
    index.scan()
    index.hash_pending()
    in_walk, release = threading.Event(), threading.Event()
    with patch("haybale_models.store.index.os.walk", _blocked_walk(in_walk, release)):
        scanner = threading.Thread(target=index.scan)
        scanner.start()
        assert in_walk.wait(5)
        index.remove(sha(b"aaa"))
        release.set()
        scanner.join(5)
    assert index.by_sha256(sha(b"aaa")) is None
    assert list(index.pending()) == [_root(models_env) / "a.bin"]  # re-queued, not trusted


def test_overlapping_scans_keep_add(models_env: VolumeStore, index: ModelIndex) -> None:
    import threading

    in_walk, release = threading.Event(), threading.Event()
    with patch("haybale_models.store.index.os.walk", _blocked_walk(in_walk, release)):
        first = threading.Thread(target=index.scan)
        second = threading.Thread(target=index.scan)
        first.start()
        assert in_walk.wait(5)
        second.start()
        new = drop(_root(models_env) / "dl.bin", b"downloaded")
        index.add(new, sha(b"downloaded"), "hf://x")
        release.set()
        first.join(5)
        second.join(5)
    assert not first.is_alive()
    assert not second.is_alive()
    assert index.by_sha256(sha(b"downloaded")) == new
    saved = json.loads((_root(models_env) / ".index.json").read_text())
    assert [f["relative"] for f in saved["files"]] == ["dl.bin"]


@pytest.mark.parametrize("content", ["[]", "5", '{"files": 5}', "{"])
def test_malformed_index_file_is_rebuilt(models_env: VolumeStore, index: ModelIndex, content: str) -> None:
    root = _root(models_env)
    drop(root / "x.pth", b"abc")
    (root / ".index.json").write_text(content)
    index.scan()
    index.hash_pending()
    assert index.by_sha256(sha(b"abc")) == root / "x.pth"
