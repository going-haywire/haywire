"""Tests for the Hugging Face bridge (no network)."""

from __future__ import annotations

import hashlib
import os
import threading
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import huggingface_hub
import pytest

from tests.models.conftest import make_hf_snapshot
from haybale_models import hf
from haybale_models.hf import HfUri, parse_hf
from haybale_models.sources.base import blob_name


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


C = "a" * 40


def test_whole_repo_is_recognised() -> None:
    assert hf.is_whole_repo(f"hf://o/r@{C}")
    assert hf.is_whole_repo("hf://o/r@main")
    for uri in ("hf://o/r/w.bin@v1", "hf://o/r", f"https://o/r@{C}", f"hf://o/@{C}"):
        assert not hf.is_whole_repo(uri), uri


def test_parse_hf_repo_needs_a_commit() -> None:
    assert hf.parse_hf_repo(f"hf://o/r@{C}") == hf.HfRepoUri("o/r", C)
    with pytest.raises(ValueError, match="needs a commit"):
        hf.parse_hf_repo("hf://o/r@main")
    with pytest.raises(ValueError, match="needs a commit"):
        hf.parse_hf_repo(f"hf://o/r@{'A' * 40}")
    with pytest.raises(ValueError, match="needs a commit"):
        hf.parse_hf_repo("hf://o/r@")
    with pytest.raises(ValueError, match="whole-repo"):
        hf.parse_hf_repo("hf://o/r/w.bin@v1")


def test_snapshot_path_finds_a_complete_snapshot(tmp_path: Path) -> None:
    snap = make_hf_snapshot(tmp_path, "o/r", C, {"a.bin": b"1", "sub/b.bin": b"2"}, ["a.bin", "sub/b.bin"])
    assert hf.snapshot_path(f"hf://o/r@{C}", tmp_path, ()) == snap


def test_snapshot_path_refuses_an_incomplete_snapshot(tmp_path: Path) -> None:
    make_hf_snapshot(tmp_path, "o/r", C, {"a.bin": b"1"}, ["a.bin", "b.bin"])
    assert hf.snapshot_path(f"hf://o/r@{C}", tmp_path, ()) is None


def test_snapshot_path_honours_include(tmp_path: Path) -> None:
    snap = make_hf_snapshot(tmp_path, "o/r", C, {"a.safetensors": b"1"}, ["a.safetensors", "b.bin"])
    assert hf.snapshot_path(f"hf://o/r@{C}", tmp_path, ("*.safetensors",)) == snap
    assert hf.snapshot_path(f"hf://o/r@{C}", tmp_path, ()) is None


def test_snapshot_path_without_listing_is_missing(tmp_path: Path) -> None:
    make_hf_snapshot(tmp_path, "o/r", C, {"a.safetensors": b"1"}, None)
    assert hf.snapshot_path(f"hf://o/r@{C}", tmp_path, ()) is None
    assert hf.snapshot_path(f"hf://o/r@{C}", tmp_path, ("*.safetensors",)) is None


def test_snapshot_path_include_matching_nothing_is_missing(tmp_path: Path) -> None:
    make_hf_snapshot(tmp_path, "o/r", C, {"README.md": b"hi"}, ["README.md"])
    assert hf.snapshot_path(f"hf://o/r@{C}", tmp_path, ("*.safetensors",)) is None


def test_snapshot_path_never_downloads(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    def boom(*a: object, **k: object) -> None:
        raise AssertionError("network")

    monkeypatch.setattr(huggingface_hub, "hf_hub_download", boom)
    monkeypatch.setattr(huggingface_hub.HfApi, "repo_info", boom)
    assert hf.snapshot_path(f"hf://o/r@{C}", tmp_path, ()) is None
    assert hf.snapshot_path(f"hf://o/r@{C}", tmp_path, ("*.bin",)) is None


def test_download_snapshot_reports_progress(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    folder = make_hf_snapshot(tmp_path, "o/r", C, {"w.bin": b"x" * 10}, None)
    seen: dict[str, object] = {}

    def fake(repo_id: str, **kw: Any) -> str:
        seen.update(repo_id=repo_id, **kw)
        files = kw["tqdm_class"](desc="Fetching 1 files", total=1)  # the file-count bar is not reported
        files.update(1)
        bar = kw["tqdm_class"](name="huggingface_hub.snapshot_download", total=10, disable=True)
        bar.update(4)
        bar.update(6)
        return str(folder)

    monkeypatch.setattr(huggingface_hub, "snapshot_download", fake)
    progress: list[tuple[int, int | None]] = []
    out = hf.download_snapshot(
        f"hf://o/r@{C}", tmp_path, ("*.bin",), None, lambda d, t: progress.append((d, t)), threading.Event()
    )
    assert out == folder
    assert progress == [(4, 10), (10, 10)]
    assert {k: seen[k] for k in ("repo_id", "revision", "cache_dir", "allow_patterns")} == {
        "repo_id": "o/r",
        "revision": C,
        "cache_dir": tmp_path,
        "allow_patterns": ["*.bin"],
    }


def test_download_snapshot_reports_expected_size_without_a_total(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    folder = make_hf_snapshot(tmp_path, "o/r", C, {"w.bin": b"x"}, None)

    def fake(repo_id: str, **kw: Any) -> str:
        kw["tqdm_class"](name="huggingface_hub.snapshot_download", total=0, disable=True).update(3)
        return str(folder)

    monkeypatch.setattr(huggingface_hub, "snapshot_download", fake)
    progress: list[tuple[int, int | None]] = []
    hf.download_snapshot(
        f"hf://o/r@{C}", tmp_path, (), 99, lambda d, t: progress.append((d, t)), threading.Event()
    )
    assert progress == [(3, 99)]


def test_progress_hook_never_raises(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    # The hook may run inside hf_xet's download thread, where a raised exception is only printed.
    cancel = threading.Event()
    updated: list[int] = []

    def fake(repo_id: str, **kw: Any) -> str:
        cancel.set()
        kw["tqdm_class"](name="huggingface_hub.snapshot_download", total=10, disable=True).update(4)
        updated.append(4)
        return str(tmp_path)

    monkeypatch.setattr(huggingface_hub, "snapshot_download", fake)
    with pytest.raises(hf.DownloadCancelled):
        hf.download_snapshot(f"hf://o/r@{C}", tmp_path, (), None, lambda d, t: None, cancel)
    assert updated == [4]


def test_download_snapshot_cancel_after_return_raises(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    cancel = threading.Event()

    def fake(repo_id: str, **kw: Any) -> str:
        cancel.set()
        return str(tmp_path)

    monkeypatch.setattr(huggingface_hub, "snapshot_download", fake)
    with pytest.raises(hf.DownloadCancelled):
        hf.download_snapshot(f"hf://o/r@{C}", tmp_path, (), None, lambda d, t: None, cancel)


def test_download_snapshot_no_match_names_the_patterns(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    # huggingface_hub 2.4 only logs "No files matched" and returns the (absent) snapshot folder.
    def fake(repo_id: str, **kw: Any) -> str:
        return str(tmp_path / "models--o--r" / "snapshots" / C)

    monkeypatch.setattr(huggingface_hub, "snapshot_download", fake)
    with pytest.raises(ValueError, match=r"matches include \['\*\.gguf'\]"):
        hf.download_snapshot(
            f"hf://o/r@{C}", tmp_path, ("*.gguf",), None, lambda d, t: None, threading.Event()
        )


D = "d" * 40


def test_hf_remove_deletes_link_and_blob(tmp_path: Path) -> None:
    snap = make_hf_snapshot(tmp_path, "o/r", C, {"a.bin": b"weights", "b.json": b"{}"}, None, linked=True)
    blob = (snap / "a.bin").resolve()
    hf.remove_cached_file(snap / "a.bin", tmp_path)
    assert not (snap / "a.bin").is_symlink()
    assert not (snap / "a.bin").exists()
    assert not blob.exists()
    assert (snap / "b.json").read_bytes() == b"{}"


def test_hf_remove_prunes_empty_folders_inside_the_snapshot(tmp_path: Path) -> None:
    snap = make_hf_snapshot(tmp_path, "o/r", C, {"unet/a.bin": b"w"}, None, linked=True)
    hf.remove_cached_file(snap / "unet" / "a.bin", tmp_path)
    assert not (snap / "unet").exists()
    assert snap.is_dir()


def test_hf_remove_keeps_a_blob_another_snapshot_links_to(tmp_path: Path) -> None:
    first = make_hf_snapshot(tmp_path, "o/r", C, {"a.bin": b"shared"}, None, linked=True)
    second = make_hf_snapshot(tmp_path, "o/r", D, {"a.bin": b"shared"}, None, linked=True)
    hf.remove_cached_file(first / "a.bin", tmp_path)
    assert not (first / "a.bin").exists()
    assert (second / "a.bin").read_bytes() == b"shared"


def test_hf_remove_refuses_a_path_outside_the_snapshots(tmp_path: Path) -> None:
    snap = make_hf_snapshot(tmp_path, "o/r", C, {"a.bin": b"w"}, None, linked=True)
    blob = (snap / "a.bin").resolve()
    outside = tmp_path.parent / f"{tmp_path.name}-outside.bin"
    outside.write_bytes(b"x")
    for path in (outside, blob):
        with pytest.raises(ValueError, match="not a file of a cached snapshot"):
            hf.remove_cached_file(path, tmp_path)
    assert outside.exists()
    assert blob.exists()


SHARED_DATA = b"shared-weights"
SHARED_SHA = hashlib.sha256(SHARED_DATA).hexdigest()
SHARED_COMMIT = "a" * 40


def _store_files(root: Path) -> list[Path]:
    payloads = (p for p in (root / "blobs").rglob("*") if p.is_file())
    return [p for p in payloads if len(p.name) == 64]


def test_a_shared_store_file_keeps_its_digest_in_the_repo_link(tmp_path: Path) -> None:
    snap = make_hf_snapshot(
        tmp_path, "org/repo", SHARED_COMMIT, {"a.bin": SHARED_DATA}, None, linked=True, shared=True
    )
    assert (snap / "a.bin").resolve().name != SHARED_SHA
    assert blob_name(snap / "a.bin") == SHARED_SHA


def test_remove_deletes_the_repo_link_and_the_shared_file(tmp_path: Path) -> None:
    snap = make_hf_snapshot(
        tmp_path, "org/repo", SHARED_COMMIT, {"a.bin": SHARED_DATA}, None, linked=True, shared=True
    )
    assert _store_files(tmp_path)
    hf.remove_cached_file(snap / "a.bin", tmp_path)
    assert not (snap / "a.bin").is_symlink()
    assert not list((tmp_path / "models--org--repo" / "blobs").iterdir())
    assert not _store_files(tmp_path)


def test_remove_keeps_a_shared_file_another_repo_links_to(tmp_path: Path) -> None:
    snap = make_hf_snapshot(
        tmp_path, "org/repo", SHARED_COMMIT, {"a.bin": SHARED_DATA}, None, linked=True, shared=True
    )
    other = make_hf_snapshot(
        tmp_path, "org/other", SHARED_COMMIT, {"a.bin": SHARED_DATA}, None, linked=True, shared=True
    )
    hf.remove_cached_file(snap / "a.bin", tmp_path)
    assert (other / "a.bin").read_bytes() == SHARED_DATA
    assert _store_files(tmp_path)


def test_remove_keeps_a_link_another_snapshot_of_the_repo_uses(tmp_path: Path) -> None:
    snap = make_hf_snapshot(
        tmp_path, "org/repo", SHARED_COMMIT, {"a.bin": SHARED_DATA}, None, linked=True, shared=True
    )
    second = tmp_path / "models--org--repo" / "snapshots" / ("b" * 40)
    second.mkdir()
    (second / "a.bin").symlink_to(os.readlink(snap / "a.bin"))
    hf.remove_cached_file(snap / "a.bin", tmp_path)
    assert (second / "a.bin").read_bytes() == SHARED_DATA
