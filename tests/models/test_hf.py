"""Tests for the Hugging Face bridge (no network)."""

from __future__ import annotations

import threading
from pathlib import Path
from types import SimpleNamespace

import huggingface_hub
import pytest

from haybale_models import hf
from haybale_models.hf import HfUri, parse_hf


def test_parse_with_and_without_revision() -> None:
    assert parse_hf("hf://org/repo/sub/m.safetensors@v1") == HfUri("org/repo", "sub/m.safetensors", "v1")
    assert parse_hf("hf://org/repo/m.bin") == HfUri("org/repo", "m.bin", "main")


def test_parse_too_few_segments() -> None:
    with pytest.raises(ValueError, match="org/repo/path"):
        parse_hf("hf://org/repo")
    with pytest.raises(ValueError, match="not an hf"):
        parse_hf("https://x/y/z")


def test_cached_path_never_downloads(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    def boom(*a: object, **k: object) -> None:
        raise AssertionError("network")

    seen: dict[str, object] = {}

    def fake(repo: str, name: str, cache_dir: Path, revision: str) -> str:
        seen.update(repo=repo, name=name, cache_dir=cache_dir, revision=revision)
        return "/c/file"

    monkeypatch.setattr(huggingface_hub, "hf_hub_download", boom)
    monkeypatch.setattr(huggingface_hub, "try_to_load_from_cache", fake)
    assert hf.cached_path("hf://o/r/a/b.bin@v2", tmp_path) == Path("/c/file")
    assert seen == {"repo": "o/r", "name": "a/b.bin", "cache_dir": tmp_path, "revision": "v2"}
    monkeypatch.setattr(huggingface_hub, "try_to_load_from_cache", lambda *a, **k: None)
    assert hf.cached_path("hf://o/r/a.bin", tmp_path) is None
    monkeypatch.setattr(huggingface_hub, "try_to_load_from_cache", lambda *a, **k: object())
    assert hf.cached_path("hf://o/r/a.bin", tmp_path) is None


def test_remote_sha(monkeypatch: pytest.MonkeyPatch) -> None:
    lfs = SimpleNamespace(sha256="ab" * 32, size=42)

    class Api:
        def get_paths_info(self, repo: str, paths: list[str], revision: str) -> list[object]:
            return [SimpleNamespace(lfs=lfs)]

    monkeypatch.setattr(huggingface_hub, "HfApi", Api)
    assert hf.remote_sha256("hf://o/r/a.bin") == ("ab" * 32, 42)

    class Plain(Api):
        def get_paths_info(self, repo: str, paths: list[str], revision: str) -> list[object]:
            return [SimpleNamespace(lfs=None)]

    monkeypatch.setattr(huggingface_hub, "HfApi", Plain)
    assert hf.remote_sha256("hf://o/r/a.bin") is None


def test_remote_sha_none_on_error(monkeypatch: pytest.MonkeyPatch) -> None:
    class Api:
        def get_paths_info(self, *a: object, **k: object) -> None:
            raise OSError("offline")

    monkeypatch.setattr(huggingface_hub, "HfApi", Api)
    assert hf.remote_sha256("hf://o/r/a.bin") is None


def test_download_reports_progress_from_incomplete_file(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setattr(hf, "POLL_INTERVAL_S", 0.01)
    blobs = tmp_path / "models--o--r" / "blobs"
    blobs.mkdir(parents=True)
    final = tmp_path / "final.bin"
    seen: list[tuple[int, int | None]] = []
    got_progress = threading.Event()

    def on_progress(done: int, total: int | None) -> None:
        seen.append((done, total))
        if done == 7:
            got_progress.set()

    def fake_dl(repo: str, name: str, cache_dir: Path, revision: str) -> str:
        (blobs / "abc.incomplete").write_bytes(b"x" * 7)
        assert got_progress.wait(5)
        final.write_bytes(b"y" * 10)
        return str(final)

    monkeypatch.setattr(huggingface_hub, "hf_hub_download", fake_dl)
    out = hf.download("hf://o/r/a.bin", tmp_path, 10, on_progress, threading.Event())
    assert out == final
    assert (7, 10) in seen
    assert seen[-1] == (10, 10)
    assert not any(t.name == "hf-progress" for t in threading.enumerate())


def test_preallocated_incomplete_blob_reports_unknown_progress(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setattr(hf, "POLL_INTERVAL_S", 0.01)
    blobs = tmp_path / "models--o--r" / "blobs"
    blobs.mkdir(parents=True)
    final = tmp_path / "final.bin"
    seen: list[int] = []
    polled = threading.Event()

    def on_progress(done: int, total: int | None) -> None:
        seen.append(done)
        polled.set()

    def fake_dl(*a: object, **k: object) -> str:
        (blobs / "abc.x.incomplete").write_bytes(b"x" * 10)  # sparse file at full size
        assert polled.wait(5)
        final.write_bytes(b"y" * 10)
        return str(final)

    monkeypatch.setattr(huggingface_hub, "hf_hub_download", fake_dl)
    hf.download("hf://o/r/a.bin", tmp_path, 10, on_progress, threading.Event())
    assert seen[0] == 0


def test_download_cancel_discards_result(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    cancel = threading.Event()
    final = tmp_path / "f.bin"

    def fake_dl(*a: object, **k: object) -> str:
        cancel.set()
        final.write_bytes(b"z")
        return str(final)

    monkeypatch.setattr(huggingface_hub, "hf_hub_download", fake_dl)
    with pytest.raises(hf.DownloadCancelled):
        hf.download("hf://o/r/a.bin", tmp_path, None, lambda d, t: None, cancel)


def test_list_cache_missing_folder_is_empty(tmp_path: Path) -> None:
    assert hf.list_cache(tmp_path / "nope") == []


def test_list_cache_flattens_real_layout(tmp_path: Path) -> None:
    repo = tmp_path / "models--org--repo"
    (repo / "blobs").mkdir(parents=True)
    (repo / "refs").mkdir()
    snap = repo / "snapshots" / "abc123" / "sub"
    snap.mkdir(parents=True)
    blob = repo / "blobs" / "deadbeef"
    blob.write_bytes(b"12345")
    (snap / "m.bin").symlink_to(blob)
    (repo / "refs" / "main").write_text("abc123")
    rows = hf.list_cache(tmp_path)
    assert len(rows) == 1
    r = rows[0]
    assert (r.repo_id, r.revision, r.path_in_repo, r.size) == ("org/repo", "abc123", "sub/m.bin", 5)
    assert r.blob_path.name == "deadbeef"
