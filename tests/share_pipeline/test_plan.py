"""plan() — the read-only verifier behind `haywire share --check`."""

import subprocess
from pathlib import Path
from unittest.mock import patch

import pytest

from haywire_studio.share_pipeline.pipeline import SharePipeline

pytestmark = pytest.mark.unit


@pytest.fixture
def project(tmp_path: Path) -> Path:
    remote = tmp_path / "remote.git"
    remote.mkdir()
    subprocess.run(["git", "init", "--bare"], cwd=remote, check=True, capture_output=True)

    repo = tmp_path / "project"
    repo.mkdir()
    for args in (
        ["init"],
        ["config", "user.email", "t@t.test"],
        ["config", "user.name", "T"],
        ["remote", "add", "origin", str(remote)],
    ):
        subprocess.run(["git", *args], cwd=repo, check=True, capture_output=True)

    lib = repo / "barn" / "haybale-alpha"
    (lib / "haybale_alpha").mkdir(parents=True)
    (lib / "pyproject.toml").write_text('[project]\nname = "haybale-alpha"\nversion = "0.3.1"\n')
    subprocess.run(["git", "add", "-A"], cwd=repo, check=True, capture_output=True)
    subprocess.run(["git", "commit", "-m", "seed"], cwd=repo, check=True, capture_output=True)
    return repo


def _no_drift(lib_dir: Path):
    from haywire_studio.share import DepDrift

    return DepDrift(lib_dir=lib_dir)


@pytest.mark.anyio
async def test_plan_mutates_nothing(project: Path) -> None:
    """--check is a PR gate: it writes nothing, commits nothing, pushes nothing."""
    before = subprocess.run(
        ["git", "status", "--porcelain"], cwd=project, capture_output=True, text=True, check=True
    ).stdout
    head_before = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=project, capture_output=True, text=True, check=True
    ).stdout

    with patch("haywire_studio.share_pipeline.pipeline.detect_share_drift", side_effect=_no_drift):
        await SharePipeline(project).plan()

    after = subprocess.run(
        ["git", "status", "--porcelain"], cwd=project, capture_output=True, text=True, check=True
    ).stdout
    head_after = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=project, capture_output=True, text=True, check=True
    ).stdout
    assert after == before
    assert head_after == head_before


@pytest.mark.anyio
async def test_plan_reports_preconditions_and_versions(project: Path) -> None:
    with patch("haywire_studio.share_pipeline.pipeline.detect_share_drift", side_effect=_no_drift):
        plan = await SharePipeline(project).plan()

    assert plan.preconditions.ok is True
    assert plan.versions.common_version == "0.3.1"


@pytest.mark.anyio
async def test_plan_flags_a_missing_marketstall_as_stale(project: Path) -> None:
    with patch("haywire_studio.share_pipeline.pipeline.detect_share_drift", side_effect=_no_drift):
        plan = await SharePipeline(project).plan()

    assert plan.stale_marketstall is True
    assert plan.is_clean is False


@pytest.mark.anyio
async def test_plan_is_clean_when_the_marketstall_matches(project: Path) -> None:
    from haywire_studio.share import write_marketstall

    write_marketstall(project, update_readme=False)
    subprocess.run(["git", "add", "-A"], cwd=project, check=True, capture_output=True)
    subprocess.run(["git", "commit", "-m", "feed"], cwd=project, check=True, capture_output=True)

    pipeline = SharePipeline(project)
    with (
        patch("haywire_studio.share_pipeline.pipeline.detect_share_drift", side_effect=_no_drift),
        patch.object(SharePipeline, "_stale_docs", return_value=[]),
    ):
        plan = await pipeline.plan()

    assert plan.stale_marketstall is False
    assert plan.is_clean is True


@pytest.mark.anyio
async def test_plan_flags_drift(project: Path) -> None:
    from haywire_studio.share import DepDrift

    def _drifty(lib_dir: Path):
        return DepDrift(lib_dir=lib_dir, pyproject_missing=["numpy"])

    with patch("haywire_studio.share_pipeline.pipeline.detect_share_drift", side_effect=_drifty):
        plan = await SharePipeline(project).plan()

    assert plan.drift.needs_decision is True
    assert plan.is_clean is False


def test_marketstall_is_stale_when_content_differs(project: Path) -> None:
    (project / "marketstall.toml").write_text("# stale hand-edit\n[[haybales]]\nname = 'gone'\n")
    assert SharePipeline(project).marketstall_is_stale() is True


def test_marketstall_is_not_stale_when_it_matches(project: Path) -> None:
    from haywire_studio.share import write_marketstall

    write_marketstall(project, update_readme=False)
    assert SharePipeline(project).marketstall_is_stale() is False


def test_marketstall_stale_check_leaves_the_file_untouched(project: Path) -> None:
    from haywire_studio.share import write_marketstall

    write_marketstall(project, update_readme=False)
    before = (project / "marketstall.toml").read_text()
    SharePipeline(project).marketstall_is_stale()
    assert (project / "marketstall.toml").read_text() == before


@pytest.mark.anyio
async def test_plan_skips_the_rest_when_preconditions_fail(tmp_path: Path) -> None:
    """No point diffing docs for a repo that cannot be published at all."""
    repo = tmp_path / "broken"
    repo.mkdir()
    subprocess.run(["git", "init"], cwd=repo, check=True, capture_output=True)

    plan = await SharePipeline(repo).plan()

    assert plan.preconditions.ok is False
    assert plan.stale_docs == []
    assert plan.is_clean is False
