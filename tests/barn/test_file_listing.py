"""list_files: name patterns, case-insensitive, hidden names skipped, symlinks kept inside the root."""

import importlib
import logging
from pathlib import Path, PurePosixPath

import pytest

pytestmark = pytest.mark.unit


def list_files(root: Path, pattern: str, *, recursive: bool) -> list[PurePosixPath]:
    # Imported at call time: a barn module reload would leave a top-level import stale.
    return importlib.import_module("haybale_core.file_listing").list_files(
        root, pattern, recursive=recursive
    )


def _touch(root: Path, *names: str) -> None:
    for name in names:
        path = root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(b"x")


def _names(root: Path, pattern: str, recursive: bool = False) -> list[str]:
    return [str(p) for p in list_files(root, pattern, recursive=recursive)]


def test_patterns_union_sorted_deduped(tmp_path):
    _touch(tmp_path, "a.png", "b.JPG", "c.txt")
    assert _names(tmp_path, "*.png; *.jpg;*.png") == ["a.png", "b.JPG"]


def test_case_insensitive(tmp_path):
    _touch(tmp_path, "IMG.JPG")
    assert _names(tmp_path, "*.jpg") == ["IMG.JPG"]


def test_recursive_flag(tmp_path):
    _touch(tmp_path, "x/y/a.png")
    assert _names(tmp_path, "*.png") == []
    assert _names(tmp_path, "*.png", recursive=True) == ["x/y/a.png"]


def test_sorted_by_relative_path(tmp_path):
    _touch(tmp_path, "b.png", "a/z.png", "a.png")
    assert _names(tmp_path, "*", recursive=True) == ["a.png", "a/z.png", "b.png"]


def test_dot_names_skipped(tmp_path):
    _touch(tmp_path, "._IMG_0001.JPG", ".DS_Store", ".hidden/a.jpg", "IMG_0002.JPG")
    assert _names(tmp_path, "*.jpg", recursive=True) == ["IMG_0002.JPG"]
    assert _names(tmp_path, "*", recursive=True) == ["IMG_0002.JPG"]


def test_symlinked_folder_not_entered(tmp_path):
    _touch(tmp_path, "sub/a.png")
    (tmp_path / "link").symlink_to(tmp_path / "sub", target_is_directory=True)
    assert _names(tmp_path, "*.png", recursive=True) == ["sub/a.png"]


def test_outward_symlinked_file_skipped_with_warning(tmp_path, caplog):
    root = tmp_path / "root"
    outside = tmp_path / "outside"
    _touch(root, "in.png")
    _touch(outside, "o.png")
    (root / "out.png").symlink_to(outside / "o.png")
    (root / "inward.png").symlink_to(root / "in.png")

    with caplog.at_level(logging.WARNING):
        names = _names(root, "*.png")

    assert names == ["in.png", "inward.png"]
    warnings = [r for r in caplog.records if r.levelno == logging.WARNING]
    assert len(warnings) == 1
    assert "out.png" in warnings[0].getMessage()


def test_inward_symlinked_file_listed_below_a_symlinked_root(tmp_path):
    real = tmp_path / "real"
    _touch(real, "in.png")
    (real / "inward.png").symlink_to(real / "in.png")
    (tmp_path / "root").symlink_to(real)

    assert _names(tmp_path / "root", "*.png") == ["in.png", "inward.png"]


@pytest.mark.parametrize("pattern", ["a/*.png", "*.png;b\\*.png"])
def test_slash_in_pattern_raises(tmp_path, pattern):
    with pytest.raises(ValueError, match="contains"):
        list_files(tmp_path, pattern, recursive=False)


@pytest.mark.parametrize("pattern", ["", " ; ;"])
def test_empty_pattern_means_all(tmp_path, pattern):
    _touch(tmp_path, "a.png", "b.txt")
    assert _names(tmp_path, pattern) == ["a.png", "b.txt"]


def test_missing_root_raises(tmp_path):
    with pytest.raises(FileNotFoundError):
        list_files(tmp_path / "nope", "*", recursive=False)
