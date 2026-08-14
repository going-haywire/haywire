"""Clean-tree gate and the write-access probe."""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest


def _git_repo(tmp_path: Path) -> Path:
    subprocess.run(["git", "init", "-q"], cwd=tmp_path, check=True)
    subprocess.run(["git", "config", "user.email", "t@t.t"], cwd=tmp_path, check=True)
    subprocess.run(["git", "config", "user.name", "t"], cwd=tmp_path, check=True)
    (tmp_path / "seed.txt").write_text("seed")
    subprocess.run(["git", "add", "-A"], cwd=tmp_path, check=True)
    subprocess.run(["git", "commit", "-qm", "seed"], cwd=tmp_path, check=True)
    return tmp_path


@pytest.mark.unit
def test_clean_tree_passes(tmp_path):
    from haywire_studio.packaging.rename.checks import check_clean_tree

    assert check_clean_tree(_git_repo(tmp_path)) == []


@pytest.mark.unit
def test_dirty_tree_blocks_and_names_the_fix(tmp_path):
    """No --allow-dirty exists, so the message must carry the commands."""
    from haywire_studio.packaging.rename.checks import check_clean_tree

    repo = _git_repo(tmp_path)
    (repo / "seed.txt").write_text("modified")

    blockers = check_clean_tree(repo)
    assert blockers
    assert "seed.txt" in blockers[0].message
    assert "git commit" in blockers[0].remedy
    assert "git stash" in blockers[0].remedy


@pytest.mark.unit
def test_untracked_file_also_blocks(tmp_path):
    from haywire_studio.packaging.rename.checks import check_clean_tree

    repo = _git_repo(tmp_path)
    (repo / "new.txt").write_text("untracked")
    assert check_clean_tree(repo)


@pytest.mark.unit
def test_non_repo_blocks_with_init_hint(tmp_path):
    from haywire_studio.packaging.rename.checks import check_clean_tree

    blockers = check_clean_tree(tmp_path)
    assert blockers
    assert "git init" in blockers[0].remedy


@pytest.mark.unit
def test_write_access_passes_on_writable_paths(tmp_path):
    from haywire_studio.packaging.rename.checks import check_write_access

    f = tmp_path / "a.json"
    f.write_text("{}")
    assert check_write_access([f], [tmp_path / "sub"]) == []


@pytest.mark.unit
def test_write_access_checks_PARENT_for_dir_renames(tmp_path):
    """Renaming a directory needs write on its PARENT, not on itself."""
    from haywire_studio.packaging.rename.checks import check_write_access

    parent = tmp_path / "locked"
    parent.mkdir()
    target = parent / "lib"
    target.mkdir()
    parent.chmod(0o500)  # r-x: target is writable, its parent is not
    try:
        assert check_write_access([], [target]), "must inspect the parent, not the target"
    finally:
        parent.chmod(0o700)
