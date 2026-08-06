"""Tests for reverting the working tree after a mid-pipeline failure."""

import subprocess
from pathlib import Path

import pytest

from haywire.core.publishing.pipeline.pipeline import SharePipeline
from haywire.core.publishing.pipeline.steps.rollback import revert_working_tree

pytestmark = pytest.mark.unit


def _init_repo(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)
    subprocess.run(["git", "init"], cwd=path, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.email", "t@t.test"], cwd=path, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.name", "T"], cwd=path, check=True, capture_output=True)


def _commit(repo: Path, message: str = "init") -> None:
    subprocess.run(["git", "add", "-A"], cwd=repo, check=True, capture_output=True)
    subprocess.run(["git", "commit", "-m", message], cwd=repo, check=True, capture_output=True)


def test_revert_discards_a_modified_tracked_file(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    _init_repo(repo)
    tracked = repo / "tracked.txt"
    tracked.write_text("original")
    _commit(repo)

    tracked.write_text("modified by a failed pipeline run")
    revert_working_tree(SharePipeline(repo))

    assert tracked.read_text() == "original"


def test_revert_removes_a_newly_created_untracked_file(tmp_path: Path) -> None:
    repo = tmp_path / "repo2"
    _init_repo(repo)
    (repo / "seed.txt").write_text("seed")
    _commit(repo)

    new_file = repo / "written_by_docs_step.md"
    new_file.write_text("generated during a failed run")
    revert_working_tree(SharePipeline(repo))

    assert not new_file.exists()


def test_revert_leaves_committed_history_untouched(tmp_path: Path) -> None:
    repo = tmp_path / "repo3"
    _init_repo(repo)
    (repo / "a.txt").write_text("a")
    _commit(repo, "first")

    (repo / "b.txt").write_text("uncommitted during a failed run")
    revert_working_tree(SharePipeline(repo))

    log = subprocess.run(
        ["git", "log", "--oneline"], cwd=repo, check=True, capture_output=True, text=True
    ).stdout
    assert "first" in log
    assert len(log.strip().splitlines()) == 1
