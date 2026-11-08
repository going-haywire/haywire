"""A second `share` of the same change is refused; an interrupted one is resumable."""

import subprocess
from pathlib import Path

import pytest

from haywire.core.publishing.pipeline.pipeline import SharePipeline
from haywire.core.publishing.pipeline.steps import release_state
from haywire.core.publishing.pipeline.steps.release_state import ReleaseKind

pytestmark = pytest.mark.unit


def _git(repo: Path, *args: str) -> str:
    return subprocess.run(
        ["git", *args], cwd=repo, check=True, capture_output=True, text=True
    ).stdout.strip()


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    remote = tmp_path / "remote.git"
    remote.mkdir()
    _git(remote, "init", "--bare")
    root = tmp_path / "project"
    root.mkdir()
    for args in (
        ("init", "-b", "main"),
        ("config", "user.email", "t@t.test"),
        ("config", "user.name", "T"),
        ("remote", "add", "origin", str(remote)),
    ):
        _git(root, *args)
    lib = root / "barn" / "haybale-alpha"
    lib.mkdir(parents=True)
    (lib / "pyproject.toml").write_text('[project]\nname = "haybale-alpha"\nversion = "0.0.9"\n')
    (root / "pyproject.toml").write_text('[project]\nname = "p"\n')
    _git(root, "add", "-A")
    _git(root, "commit", "-m", "seed")
    _git(root, "push", "-u", "origin", "main")
    return root


def _release_commit(repo: Path, tag: str = "v0.1.0", *, push: bool, do_tag: bool = True) -> None:
    (repo / "barn" / "haybale-alpha" / "pyproject.toml").write_text(
        f'[project]\nname = "haybale-alpha"\nversion = "{tag[1:]}"\n'
    )
    _git(repo, "add", "-A")
    _git(repo, "commit", "-m", f"chore: share {tag}")
    if do_tag:
        _git(repo, "tag", tag)
    if push:
        _git(repo, "push", "origin", "main", tag)


def test_untagged_checkout_is_not_blocked(repo: Path) -> None:
    assert release_state.detect(repo).kind is ReleaseKind.NONE


def test_head_tagged_and_on_origin_is_released(repo: Path) -> None:
    _release_commit(repo, push=True)
    state = release_state.detect(repo)
    assert (state.kind, state.tag) == (ReleaseKind.RELEASED, "v0.1.0")


def test_head_tagged_but_not_on_origin_is_unpushed(repo: Path) -> None:
    _release_commit(repo, push=False)
    assert release_state.detect(repo).kind is ReleaseKind.UNPUSHED


def test_commit_without_tag_is_unpushed_via_marker(repo: Path) -> None:
    _release_commit(repo, push=False, do_tag=False)
    sha = _git(repo, "rev-parse", "HEAD")
    release_state.write_marker(repo, tag="v0.1.0", sha=sha, phase="committed")
    state = release_state.detect(repo)
    assert (state.kind, state.needs_tag) == (ReleaseKind.UNPUSHED, True)


def test_marker_for_another_commit_is_stale(repo: Path) -> None:
    release_state.write_marker(repo, tag="v0.1.0", sha="deadbeef", phase="committed")
    assert release_state.detect(repo).kind is ReleaseKind.STALE_MARKER


def test_nothing_changed_since_the_tag(repo: Path) -> None:
    _release_commit(repo, push=True)
    (repo / "README.md").write_text("docs only")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-m", "docs")
    assert release_state.detect(repo).kind is ReleaseKind.NOTHING_NEW


def test_change_under_barn_since_the_tag_allows_a_release(repo: Path) -> None:
    _release_commit(repo, push=True)
    (repo / "barn" / "haybale-alpha" / "mod.py").write_text("x = 1\n")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-m", "feat")
    assert release_state.detect(repo).kind is ReleaseKind.NONE


def test_preconditions_refuse_a_second_release(repo: Path) -> None:
    _release_commit(repo, push=True)
    report = SharePipeline(repo).check_preconditions()
    assert [f.code for f in report.failures] == ["already_released"]
    assert "DONE" in report.failures[0].remedy


def test_preconditions_point_unpushed_at_resume(repo: Path) -> None:
    _release_commit(repo, push=False)
    failure = SharePipeline(repo).check_preconditions().failures[0]
    assert failure.code == "unpushed_release"
    assert "share --resume" in failure.remedy


@pytest.mark.anyio
async def test_resume_tags_and_pushes_without_bumping(repo: Path) -> None:
    _release_commit(repo, push=False, do_tag=False)
    sha = _git(repo, "rev-parse", "HEAD")
    release_state.write_marker(repo, tag="v0.1.0", sha=sha, phase="committed")

    result = await SharePipeline(repo).resume_release()

    assert result.tag == "v0.1.0"
    assert "v0.1.0" in _git(repo, "ls-remote", "--tags", "origin")
    assert _git(repo, "rev-parse", "HEAD") == sha  # no new commit
    assert release_state.read_marker(repo) is None
    assert release_state.detect(repo).kind is ReleaseKind.RELEASED


@pytest.mark.anyio
async def test_resume_refuses_when_nothing_is_half_done(repo: Path) -> None:
    from haywire.core.publishing.pipeline.errors import PipelineStateError

    with pytest.raises(PipelineStateError):
        await SharePipeline(repo).resume_release()
