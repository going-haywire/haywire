"""Tests for the barn repo-shape queries (leaf module, no haywire_studio deps)."""

import subprocess
from pathlib import Path

import pytest

from haywire_studio.share.barn import barn_library_dirs, current_ref

pytestmark = pytest.mark.unit


def _git(repo: Path, *args: str) -> subprocess.CompletedProcess:
    return subprocess.run(["git", *args], cwd=repo, check=True, capture_output=True, text=True)


def _init_repo(repo: Path) -> None:
    repo.mkdir(parents=True, exist_ok=True)
    _git(repo, "init", "-q")
    _git(repo, "config", "user.email", "t@t.test")
    _git(repo, "config", "user.name", "T")


def test_returns_empty_list_when_barn_directory_absent(tmp_path: Path) -> None:
    assert barn_library_dirs(tmp_path) == []


def test_finds_directories_with_pyproject_toml(tmp_path: Path) -> None:
    barn = tmp_path / "barn"
    for name in ("haybale-b", "haybale-a"):
        lib = barn / name
        lib.mkdir(parents=True)
        (lib / "pyproject.toml").write_text("[project]\nname = 'x'\n")

    result = barn_library_dirs(tmp_path)

    assert result == sorted(result)
    assert result == [barn / "haybale-a", barn / "haybale-b"]


def test_ignores_directory_literally_named_pyproject_toml(tmp_path: Path) -> None:
    """A directory named pyproject.toml passes .exists() but is not a manifest.

    This is the predicate distinction the plan calls out: .is_file() correctly
    excludes it, while the old .exists()-based scan in share.py would not.
    """
    barn = tmp_path / "barn"
    lib = barn / "haybale-weird"
    lib.mkdir(parents=True)
    (lib / "pyproject.toml").mkdir()  # a directory, not a file

    assert barn_library_dirs(tmp_path) == []


def test_ignores_barn_entries_without_pyproject(tmp_path: Path) -> None:
    barn = tmp_path / "barn"
    no_manifest = barn / "not-a-library"
    no_manifest.mkdir(parents=True)
    (no_manifest / "README.md").write_text("hello\n")

    assert barn_library_dirs(tmp_path) == []


def test_ignores_files_directly_under_barn(tmp_path: Path) -> None:
    barn = tmp_path / "barn"
    barn.mkdir(parents=True)
    (barn / "stray_file.txt").write_text("not a library\n")

    assert barn_library_dirs(tmp_path) == []


def test_sorted_order_guarantee(tmp_path: Path) -> None:
    barn = tmp_path / "barn"
    names = ["zeta", "alpha", "mid", "beta"]
    for name in names:
        lib = barn / name
        lib.mkdir(parents=True)
        (lib / "pyproject.toml").write_text("[project]\nname = 'x'\n")

    result = barn_library_dirs(tmp_path)

    assert [p.name for p in result] == sorted(names)


# ── current_ref ──────────────────────────────────────────────────────────────


def test_current_ref_reports_a_normal_branch(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    _init_repo(repo)
    (repo / "f.txt").write_text("x\n")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-q", "-m", "seed")
    _git(repo, "checkout", "-q", "-b", "feature-x")

    assert current_ref(repo) == "feature-x"


def test_current_ref_returns_none_on_genuine_detached_head(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    _init_repo(repo)
    (repo / "f.txt").write_text("x\n")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-q", "-m", "seed")
    sha = _git(repo, "rev-parse", "HEAD").stdout.strip()
    _git(repo, "checkout", "-q", sha)  # real detachment, not a branch checkout

    assert current_ref(repo) is None


def test_current_ref_reports_the_real_name_for_an_unborn_branch(tmp_path: Path) -> None:
    """A fresh repo before its first commit: `rev-parse --abbrev-ref HEAD`
    prints the literal string "HEAD" here too, but `symbolic-ref -q HEAD`
    still succeeds and names the real branch — current_ref must use that,
    not the rev-parse string, or it would misreport a brand-new project as
    detached.
    """
    repo = tmp_path / "repo"
    _init_repo(repo)

    ref = current_ref(repo)

    assert ref is not None
    assert ref != "HEAD"


def test_current_ref_never_returns_the_literal_head_string(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    _init_repo(repo)
    (repo / "f.txt").write_text("x\n")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-q", "-m", "seed")
    sha = _git(repo, "rev-parse", "HEAD").stdout.strip()
    _git(repo, "checkout", "-q", sha)

    assert current_ref(repo) != "HEAD"


def test_current_ref_returns_none_when_not_a_git_repo(tmp_path: Path) -> None:
    assert current_ref(tmp_path) is None
