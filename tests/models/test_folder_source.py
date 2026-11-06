"""Folder model sources: cache volumes on first need, path-safe addresses, torch hub names."""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest

from haywire.core.volumes import VolumeStore, get_volume_store, set_volume_store

from haybale_models.sources import FolderSource, TorchHubSource


@pytest.fixture
def store(tmp_path: Path) -> Iterator[VolumeStore]:
    previous = get_volume_store()
    s = VolumeStore(tmp_path / "volumes.toml")
    set_volume_store(s)
    yield s
    set_volume_store(previous)


def make(tmp_path: Path, cls: type[FolderSource] = FolderSource) -> FolderSource:
    return cls(name="x", label="X", locate=lambda: tmp_path / "cache", description="X models")


def test_find_is_the_file_under_the_root(store, tmp_path) -> None:
    source = make(tmp_path)
    (tmp_path / "cache" / "sub").mkdir(parents=True)
    (tmp_path / "cache" / "sub" / "w.pth").write_bytes(b"1")
    assert source.find("x://sub/w.pth") == tmp_path / "cache" / "sub" / "w.pth"
    assert source.find("x://sub/missing.pth") is None


@pytest.mark.parametrize("address", ["x://../w", "x:///w", "x://a\\b", "x://", "x://a/../b"])
def test_parse_refuses_escaping_paths(address) -> None:
    with pytest.raises(ValueError, match="not a path inside"):
        FolderSource(name="x", label="X", locate=lambda: Path("/c"), description="").parse(address)


def test_no_volume_until_needed(store, tmp_path) -> None:
    source = make(tmp_path)
    assert source.root() is None
    assert source.find("x://w.pth") is None
    assert store.entry(source.volume) is None


def test_existing_suggested_folder_becomes_the_volume(store, tmp_path) -> None:
    source = make(tmp_path)
    (tmp_path / "cache").mkdir()
    assert source.root() == tmp_path / "cache"
    entry = store.entry(source.volume)
    assert entry is not None
    assert entry.suggested == tmp_path / "cache"


def test_prepare_root_creates_the_folder(store, tmp_path) -> None:
    source = make(tmp_path)
    root = source.prepare_root()
    assert root == tmp_path / "cache"
    assert root.is_dir()
    assert store.entry(source.volume) is not None


def test_torchhub_matches_by_name_prefix(tmp_path) -> None:
    s = make(tmp_path, TorchHubSource)
    assert s.matches(Path("resnet18-f37072fd.pth"), "f37072fd" + "0" * 56) is True
    assert s.matches(Path("resnet18-f37072fd.pth"), "aaaaaaaa" + "0" * 56) is False
    assert s.matches(Path("resnet18.pth"), "f37072fd" + "0" * 56) is None


@pytest.mark.parametrize("address", ["torchhub://C:/x/w.pth", "x://a:b"])
def test_parse_refuses_colons(address) -> None:
    with pytest.raises(ValueError, match="not a path inside"):
        FolderSource(name="x", label="X", locate=lambda: Path("/c"), description="").parse(address)


def test_symlink_escaping_the_root_is_not_found(store, tmp_path) -> None:
    source = make(tmp_path)
    cache = tmp_path / "cache"
    cache.mkdir()
    outside = tmp_path / "outside.pth"
    outside.write_bytes(b"1")
    try:
        (cache / "link.pth").symlink_to(outside)
    except (OSError, NotImplementedError):
        pytest.skip("symlinks unavailable on this platform")
    assert source.find("x://link.pth") is None


def test_folder_remove_prunes_empty_folders(store, tmp_path) -> None:
    source = make(tmp_path)
    (tmp_path / "cache" / "sub").mkdir(parents=True)
    (tmp_path / "cache" / "keep.pth").write_bytes(b"k")
    (tmp_path / "cache" / "sub" / "w.pth").write_bytes(b"1")
    source.remove(tmp_path / "cache" / "sub" / "w.pth")
    assert not (tmp_path / "cache" / "sub").exists()
    assert (tmp_path / "cache" / "keep.pth").exists()


def test_folder_remove_refuses_a_path_outside_the_cache(store, tmp_path) -> None:
    source = make(tmp_path)
    (tmp_path / "cache").mkdir()
    outside = tmp_path / "outside.pth"
    outside.write_bytes(b"1")
    (tmp_path / "cache" / "link.pth").symlink_to(outside)
    with pytest.raises(ValueError, match="outside"):
        source.remove(outside)
    with pytest.raises(ValueError, match="outside"):
        source.remove(tmp_path / "cache" / "link.pth")
    assert outside.exists()
