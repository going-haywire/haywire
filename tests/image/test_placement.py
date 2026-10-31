"""Save-target placement: if_exists policy and atomic write."""

import importlib
import os
from pathlib import Path

import pytest

placement = importlib.import_module("haybale_image.io.placement")


def test_overwrite_returns_target(tmp_path: Path) -> None:
    target = tmp_path / "a.png"
    target.write_bytes(b"old")
    assert placement.claim_target(target, placement.IfExists.OVERWRITE) == target
    assert target.read_bytes() == b"old"  # no placeholder, untouched


def test_skip_existing_returns_none(tmp_path: Path) -> None:
    target = tmp_path / "a.png"
    target.write_bytes(b"old")
    assert placement.claim_target(target, placement.IfExists.SKIP) is None


def test_skip_missing_returns_target(tmp_path: Path) -> None:
    target = tmp_path / "a.png"
    assert placement.claim_target(target, placement.IfExists.SKIP) == target
    assert not target.exists()  # no placeholder


def test_unique_suffix_free_target_is_claimed(tmp_path: Path) -> None:
    target = tmp_path / "a.png"
    assert placement.claim_target(target, placement.IfExists.UNIQUE_SUFFIX) == target
    assert target.exists()
    assert target.stat().st_size == 0


def test_unique_suffix_picks_first_free(tmp_path: Path) -> None:
    (tmp_path / "a.png").write_bytes(b"x")
    (tmp_path / "a_1.png").write_bytes(b"x")
    got = placement.claim_target(tmp_path / "a.png", placement.IfExists.UNIQUE_SUFFIX)
    assert got == tmp_path / "a_2.png"


def test_unique_suffix_claims_atomically(tmp_path: Path) -> None:
    target = tmp_path / "a.png"
    first = placement.claim_target(target, placement.IfExists.UNIQUE_SUFFIX)
    second = placement.claim_target(target, placement.IfExists.UNIQUE_SUFFIX)
    assert first != second


def test_missing_folder_raises(tmp_path: Path) -> None:
    for mode in placement.IfExists:
        with pytest.raises(FileNotFoundError, match="Create Folder"):
            placement.claim_target(tmp_path / "nope" / "a.png", mode)


def test_atomic_write_replaces(tmp_path: Path) -> None:
    target = tmp_path / "a.png"
    target.write_bytes(b"old")
    placement.atomic_write(target, b"new")
    assert target.read_bytes() == b"new"
    assert [p.name for p in tmp_path.iterdir()] == ["a.png"]


def test_failed_write_leaves_no_file(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    target = placement.claim_target(tmp_path / "a.png", placement.IfExists.UNIQUE_SUFFIX)
    assert target is not None

    def boom(*_a: object, **_k: object) -> None:
        raise OSError("disk gone")

    monkeypatch.setattr(os, "replace", boom)
    with pytest.raises(OSError, match="disk gone"):
        placement.atomic_write(target, b"data")
    assert list(tmp_path.iterdir()) == []


def test_failed_write_keeps_existing_data(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    target = tmp_path / "a.png"
    target.write_bytes(b"old")
    monkeypatch.setattr(os, "replace", lambda *_a, **_k: (_ for _ in ()).throw(OSError("x")))
    with pytest.raises(OSError, match="x"):
        placement.atomic_write(target, b"new")
    assert [p.name for p in tmp_path.iterdir()] == ["a.png"]
    assert target.read_bytes() == b"old"
