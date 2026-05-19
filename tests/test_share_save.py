"""Tests for `haywire share --save` (aggregates all barn/* libraries into marketstall.toml)."""

from pathlib import Path

import pytest
import toml


@pytest.fixture
def repo_with_two_barn_libs(tmp_path: Path) -> Path:
    """Create a fake repo with two barn libraries under barn/."""
    repo = tmp_path / "fake-repo"
    repo.mkdir()
    (repo / ".git").mkdir()  # Marks it as a git root for share's detector.

    # Library A
    lib_a = repo / "barn" / "haybale-alpha"
    (lib_a / "haybale_alpha").mkdir(parents=True)
    (lib_a / "pyproject.toml").write_text(
        "[project]\n"
        'name = "haybale-alpha"\n'
        'version = "0.0.1"\n'
        'description = "Alpha library"\n'
        'keywords = ["alpha", "demo"]\n'
        'authors = [{name = "Alpha Author"}]\n'
    )
    (lib_a / "haybale_alpha" / "__init__.py").write_text(
        '@library(label="Alpha", id="alpha", dependencies=["haybale_beta"])\nclass Library: pass\n'
    )

    # Library B
    lib_b = repo / "barn" / "haybale-beta"
    (lib_b / "haybale_beta").mkdir(parents=True)
    (lib_b / "pyproject.toml").write_text(
        '[project]\nname = "haybale-beta"\nversion = "0.0.1"\ndescription = "Beta library"\n'
    )
    (lib_b / "haybale_beta" / "__init__.py").write_text(
        '@library(label="Beta", id="beta")\nclass Library: pass\n'
    )

    return repo


def test_share_save_writes_marketstall_at_repo_root(repo_with_two_barn_libs: Path) -> None:
    from haywire_studio.share import share_save_repo

    out_path = share_save_repo(repo_with_two_barn_libs)

    assert out_path == repo_with_two_barn_libs / "marketstall.toml"
    assert out_path.is_file()


def test_share_save_aggregates_all_barn_libraries(repo_with_two_barn_libs: Path) -> None:
    from haywire_studio.share import share_save_repo

    share_save_repo(repo_with_two_barn_libs)

    data = toml.loads((repo_with_two_barn_libs / "marketstall.toml").read_text())
    names = sorted(pkg["name"] for pkg in data["packages"])
    assert names == ["haybale-alpha", "haybale-beta"]


def test_share_save_each_entry_is_source_git(repo_with_two_barn_libs: Path) -> None:
    from haywire_studio.share import share_save_repo

    share_save_repo(repo_with_two_barn_libs)

    data = toml.loads((repo_with_two_barn_libs / "marketstall.toml").read_text())
    for pkg in data["packages"]:
        assert pkg["source"] == "git"


def test_share_save_skips_dirs_without_pyproject(tmp_path: Path) -> None:
    """A directory under barn/ that has no pyproject.toml must be silently skipped."""
    from haywire_studio.share import share_save_repo

    repo = tmp_path / "sparse-repo"
    (repo / ".git").mkdir(parents=True)
    (repo / "barn" / "haybale-alpha").mkdir(parents=True)
    (repo / "barn" / "haybale-alpha" / "pyproject.toml").write_text(
        '[project]\nname = "haybale-alpha"\nversion = "0.0.1"\ndescription = "a"\n'
    )
    (repo / "barn" / "not-a-library").mkdir(parents=True)
    # not-a-library has no pyproject.toml; share_save_repo must skip it.

    share_save_repo(repo)
    data = toml.loads((repo / "marketstall.toml").read_text())
    names = [pkg["name"] for pkg in data["packages"]]
    assert names == ["haybale-alpha"]


def test_share_save_raises_when_no_barn(tmp_path: Path) -> None:
    from haywire_studio.share import share_save_repo, NoBarnError

    repo = tmp_path / "no-barn-repo"
    repo.mkdir()
    (repo / ".git").mkdir()

    with pytest.raises(NoBarnError):
        share_save_repo(repo)
