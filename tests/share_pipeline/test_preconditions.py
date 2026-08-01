"""Step 1 — the combined precondition gate."""

import subprocess
from pathlib import Path

import pytest

from haywire_studio.share_pipeline import PreconditionsError
from haywire_studio.share_pipeline.pipeline import SharePipeline

pytestmark = pytest.mark.unit


def _init_repo(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)
    subprocess.run(["git", "init"], cwd=path, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.email", "t@t.test"], cwd=path, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.name", "T"], cwd=path, check=True, capture_output=True)


def _add_lib(repo: Path, name: str = "haybale-alpha") -> Path:
    lib = repo / "barn" / name
    (lib / name.replace("-", "_")).mkdir(parents=True)
    (lib / "pyproject.toml").write_text(f'[project]\nname = "{name}"\nversion = "0.1.0"\n')
    return lib


@pytest.fixture
def bare_remote(tmp_path: Path) -> Path:
    """A local bare repo usable as `origin` — makes ls-remote real without a network."""
    remote = tmp_path / "remote.git"
    remote.mkdir()
    subprocess.run(["git", "init", "--bare"], cwd=remote, check=True, capture_output=True)
    return remote


@pytest.fixture
def project(tmp_path: Path, bare_remote: Path) -> Path:
    """A shareable project: git repo, one barn library, origin pointing at a real bare repo."""
    repo = tmp_path / "project"
    _init_repo(repo)
    _add_lib(repo)
    subprocess.run(
        ["git", "remote", "add", "origin", str(bare_remote)],
        cwd=repo,
        check=True,
        capture_output=True,
    )
    return repo


def test_healthy_project_passes(project: Path) -> None:
    report = SharePipeline(project).check_preconditions()
    assert report.ok is True
    assert report.failures == []
    assert report.remote_url is not None
    assert [p.name for p in report.barn_libraries] == ["haybale-alpha"]


def test_missing_barn_directory_fails(tmp_path: Path, bare_remote: Path) -> None:
    repo = tmp_path / "nobarn"
    _init_repo(repo)
    subprocess.run(
        ["git", "remote", "add", "origin", str(bare_remote)], cwd=repo, check=True, capture_output=True
    )
    report = SharePipeline(repo).check_preconditions()
    assert report.ok is False
    assert any("barn" in f for f in report.failures)


def test_barn_with_no_library_fails(tmp_path: Path, bare_remote: Path) -> None:
    repo = tmp_path / "emptybarn"
    _init_repo(repo)
    (repo / "barn").mkdir()
    subprocess.run(
        ["git", "remote", "add", "origin", str(bare_remote)], cwd=repo, check=True, capture_output=True
    )
    report = SharePipeline(repo).check_preconditions()
    assert report.ok is False
    assert any("pyproject.toml" in f for f in report.failures)


def test_missing_origin_fails_with_setup_instructions(tmp_path: Path) -> None:
    repo = tmp_path / "noremote"
    _init_repo(repo)
    _add_lib(repo)
    report = SharePipeline(repo).check_preconditions()
    assert report.ok is False
    assert any("remote add origin" in f for f in report.failures)
    assert report.remote_url is None


def test_unreachable_remote_fails(tmp_path: Path) -> None:
    """ls-remote exercises the exact credential path push uses, so auth
    failures surface here rather than after a commit and tag exist."""
    repo = tmp_path / "badremote"
    _init_repo(repo)
    _add_lib(repo)
    subprocess.run(
        ["git", "remote", "add", "origin", str(tmp_path / "does-not-exist.git")],
        cwd=repo,
        check=True,
        capture_output=True,
    )
    report = SharePipeline(repo).check_preconditions()
    assert report.ok is False
    assert any("origin" in f for f in report.failures)


def test_every_failure_is_reported_together(tmp_path: Path) -> None:
    """No barn AND no remote must both appear — fixing one shouldn't reveal the other."""
    repo = tmp_path / "broken"
    _init_repo(repo)
    report = SharePipeline(repo).check_preconditions()
    assert len(report.failures) >= 2
    assert any("barn" in f for f in report.failures)
    assert any("origin" in f for f in report.failures)


def test_missing_git_binary_reports_install_instructions(project: Path, monkeypatch) -> None:
    from haywire_studio.share_pipeline import gitcmd

    def _no_git(*_a, **_kw):
        raise FileNotFoundError("git")

    monkeypatch.setattr(gitcmd.subprocess, "run", _no_git)
    report = SharePipeline(project).check_preconditions()
    assert report.ok is False
    assert any("git-scm.com" in f for f in report.failures)


def test_require_preconditions_raises_with_all_failures(tmp_path: Path) -> None:
    repo = tmp_path / "broken2"
    _init_repo(repo)
    with pytest.raises(PreconditionsError) as excinfo:
        SharePipeline(repo).require_preconditions()
    assert len(excinfo.value.failures) >= 2


def test_require_preconditions_returns_report_when_ok(project: Path) -> None:
    report = SharePipeline(project).require_preconditions()
    assert report.ok is True


def test_successful_check_records_remote_url_on_the_pipeline(project: Path) -> None:
    pipeline = SharePipeline(project)
    assert pipeline.remote_url is None
    pipeline.check_preconditions()
    assert pipeline.remote_url is not None


def test_pipeline_starts_with_an_empty_write_set(project: Path) -> None:
    assert SharePipeline(project).written == []
