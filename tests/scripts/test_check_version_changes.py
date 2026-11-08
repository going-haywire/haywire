"""scripts/check_version_changes.py: only a release PR may change a package version."""

import subprocess
from pathlib import Path

import pytest

from scripts import check_version_changes

pytestmark = pytest.mark.unit


def _load():
    return check_version_changes


def _git(repo: Path, *args: str) -> None:
    subprocess.run(["git", *args], cwd=repo, check=True, capture_output=True)


@pytest.fixture
def repo(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """A repo whose `origin/master` ref is the base and whose HEAD is a feature branch."""
    for args in (
        ("init", "-b", "master"),
        ("config", "user.email", "t@t.test"),
        ("config", "user.name", "T"),
    ):
        _git(tmp_path, *args)
    (tmp_path / "pkg-a").mkdir()
    (tmp_path / "pkg-a" / "pyproject.toml").write_text('[project]\nname = "a"\nversion = "0.1.0"\n')
    (tmp_path / "pkg-a" / "other.txt").write_text("x\n")
    _git(tmp_path, "add", "-A")
    _git(tmp_path, "commit", "-m", "base")
    _git(tmp_path, "update-ref", "refs/remotes/origin/master", "HEAD")
    _git(tmp_path, "switch", "-c", "feature")
    monkeypatch.chdir(tmp_path)
    return tmp_path


def _commit(repo: Path, message: str = "change") -> None:
    _git(repo, "add", "-A")
    _git(repo, "commit", "-m", message)


def test_a_feature_without_version_changes_passes(repo: Path) -> None:
    (repo / "pkg-a" / "other.txt").write_text("y\n")
    _commit(repo)
    assert _load().changed_version_files("origin/master") == []


def test_a_changed_version_is_reported(repo: Path) -> None:
    (repo / "pkg-a" / "pyproject.toml").write_text('[project]\nname = "a"\nversion = "0.1.1"\n')
    _commit(repo)
    assert _load().changed_version_files("origin/master") == ["pkg-a/pyproject.toml"]


def test_a_new_package_may_declare_its_first_version(repo: Path) -> None:
    (repo / "pkg-b").mkdir()
    (repo / "pkg-b" / "pyproject.toml").write_text('[project]\nname = "b"\nversion = "0.0.1"\n')
    _commit(repo)
    assert _load().changed_version_files("origin/master") == []


def test_a_changed_dependency_pin_is_not_a_version_change(repo: Path) -> None:
    (repo / "pkg-a" / "pyproject.toml").write_text(
        '[project]\nname = "a"\nversion = "0.1.0"\ndependencies = ["haywire-core>=0.3.0"]\n'
    )
    _commit(repo)
    assert _load().changed_version_files("origin/master") == []


def test_main_fails_a_feature_pr_and_passes_a_release_pr(
    repo: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    (repo / "pkg-a" / "pyproject.toml").write_text('[project]\nname = "a"\nversion = "0.1.1"\n')
    _commit(repo)
    module = _load()
    monkeypatch.setenv("GITHUB_BASE_REF", "master")

    monkeypatch.setenv("PR_TITLE", "feat: something")
    assert module.main() == 1

    monkeypatch.setenv("PR_TITLE", "chore: release v0.1.1")
    assert module.main() == 0
