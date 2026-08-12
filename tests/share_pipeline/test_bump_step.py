"""Step 3 — lockstep bump, tag-collision pre-check, lockfile refresh."""

import subprocess
from pathlib import Path
from unittest.mock import patch

import pytest
import toml

from haywire.core.publishing.pipeline import TagCollisionError, VersionError
from haywire.core.publishing.pipeline.pipeline import SharePipeline
from haywire.core.publishing.pipeline.steps import version as steps_version

pytestmark = pytest.mark.unit


@pytest.fixture
def project(tmp_path: Path) -> Path:
    """Git repo, bare origin, two barn libraries at 0.3.1."""
    remote = tmp_path / "remote.git"
    remote.mkdir()
    subprocess.run(["git", "init", "--bare"], cwd=remote, check=True, capture_output=True)

    repo = tmp_path / "project"
    repo.mkdir()
    subprocess.run(["git", "init"], cwd=repo, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.email", "t@t.test"], cwd=repo, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.name", "T"], cwd=repo, check=True, capture_output=True)
    subprocess.run(
        ["git", "remote", "add", "origin", str(remote)], cwd=repo, check=True, capture_output=True
    )
    (repo / "pyproject.toml").write_text('[project]\nname = "ws"\nversion = "0.1.0"\n')
    for name in ("haybale-alpha", "haybale-beta"):
        lib = repo / "barn" / name
        lib.mkdir(parents=True)
        (lib / "pyproject.toml").write_text(f'[project]\nname = "{name}"\nversion = "0.3.1"\n')
    (repo / "seed.txt").write_text("seed\n")
    subprocess.run(["git", "add", "-A"], cwd=repo, check=True, capture_output=True)
    subprocess.run(["git", "commit", "-m", "seed"], cwd=repo, check=True, capture_output=True)
    return repo


def test_plan_version_reports_the_common_version(project: Path) -> None:
    plan = SharePipeline(project).plan_version()
    assert plan.common_version == "0.3.1"
    assert plan.suggestions["patch"] == "0.3.2"


def test_apply_bump_writes_every_barn_library(project: Path) -> None:
    pipeline = SharePipeline(project)
    result = pipeline.apply_bump("patch")

    assert result.version == "0.3.2"
    for name in ("haybale-alpha", "haybale-beta"):
        path = project / "barn" / name / "pyproject.toml"
        assert toml.loads(path.read_text())["project"]["version"] == "0.3.2"
        assert path in pipeline.written


def test_apply_bump_leaves_the_root_pyproject_alone(project: Path) -> None:
    root = project / "pyproject.toml"
    before = root.read_text()
    pipeline = SharePipeline(project)
    pipeline.apply_bump("minor")
    assert root.read_text() == before
    assert root not in pipeline.written


def test_apply_bump_accepts_an_explicit_version(project: Path) -> None:
    result = SharePipeline(project).apply_bump("2.0.0")
    assert result.version == "2.0.0"


def test_apply_bump_rejects_a_malformed_version(project: Path) -> None:
    with pytest.raises(VersionError):
        SharePipeline(project).apply_bump("2.0")


def test_apply_bump_records_the_version_on_the_pipeline(project: Path) -> None:
    pipeline = SharePipeline(project)
    assert pipeline.version is None
    pipeline.apply_bump("patch")
    assert pipeline.version == "0.3.2"


def test_local_tag_collision_is_caught_before_any_write(project: Path) -> None:
    subprocess.run(["git", "tag", "v0.3.2"], cwd=project, check=True, capture_output=True)
    pipeline = SharePipeline(project)

    with pytest.raises(TagCollisionError) as excinfo:
        pipeline.apply_bump("patch")

    assert excinfo.value.tag == "v0.3.2"
    assert excinfo.value.local is True
    # Nothing was written — the check runs before write_barn_versions.
    path = project / "barn" / "haybale-alpha" / "pyproject.toml"
    assert toml.loads(path.read_text())["project"]["version"] == "0.3.1"
    assert pipeline.written == []


def test_remote_tag_collision_is_caught(project: Path) -> None:
    from haywire.core.publishing import git as gitcmd

    def _ls_remote_tags(args, **_kw):
        if args[:2] == ["ls-remote", "--tags"]:
            return gitcmd.GitResult(
                ok=True,
                stdout="abc123\trefs/tags/v0.3.2\n",
                stderr="",
                returncode=0,
            )
        return gitcmd.GitResult(ok=True, stdout="", stderr="", returncode=0)

    with patch.object(steps_version, "git_remote", side_effect=_ls_remote_tags):
        with pytest.raises(TagCollisionError) as excinfo:
            SharePipeline(project).apply_bump("patch")

    assert excinfo.value.remote is True


def test_check_tag_available_passes_for_a_free_tag(project: Path) -> None:
    SharePipeline(project).check_tag_available("9.9.9")  # must not raise


def test_unreachable_remote_does_not_block_the_tag_check(project: Path) -> None:
    """A remote we can't query is step 1's problem. Here it must not become a
    false collision — that would block a legitimate publish."""
    from haywire.core.publishing import git as gitcmd

    def _unreachable(*_a, **_kw):
        return gitcmd.GitResult(ok=False, stdout="", stderr="could not read", returncode=128)

    with patch.object(steps_version, "git_remote", side_effect=_unreachable):
        SharePipeline(project).check_tag_available("0.3.2")  # must not raise


def test_lockfile_warning_is_carried_not_raised(project: Path) -> None:
    (project / "uv.lock").write_text("")

    with patch.object(steps_version, "refresh_lockfile", return_value=(False, "uv lock failed: boom")):
        result = SharePipeline(project).apply_bump("patch")

    assert result.lock_refreshed is False
    assert result.lock_warning is not None
    assert "boom" in result.lock_warning
    assert result.version == "0.3.2"  # the bump still stands


def test_refreshed_lockfile_joins_the_write_set(project: Path) -> None:
    (project / "uv.lock").write_text("")
    pipeline = SharePipeline(project)

    with patch.object(steps_version, "refresh_lockfile", return_value=(True, None)):
        result = pipeline.apply_bump("patch")

    assert result.lock_refreshed is True
    assert project / "uv.lock" in pipeline.written


def test_stale_lockfile_stays_out_of_the_write_set(project: Path) -> None:
    """A failed lock left the file untouched — staging it would commit nothing
    useful and muddy the commit preview."""
    (project / "uv.lock").write_text("")
    pipeline = SharePipeline(project)

    with patch.object(steps_version, "refresh_lockfile", return_value=(False, "uv lock failed")):
        pipeline.apply_bump("patch")

    assert project / "uv.lock" not in pipeline.written


def test_disagreeing_versions_reject_a_keyword_bump(tmp_path: Path) -> None:
    """No silent resolution — a 'first barn library' heuristic would
    downgrade the higher-versioned sibling."""
    repo = tmp_path / "mixed"
    subprocess.run(["git", "init", str(repo)], check=True, capture_output=True)
    for name, version in (("haybale-alpha", "0.3.1"), ("haybale-beta", "0.9.0")):
        lib = repo / "barn" / name
        lib.mkdir(parents=True)
        (lib / "pyproject.toml").write_text(f'[project]\nname = "{name}"\nversion = "{version}"\n')

    with pytest.raises(VersionError):
        SharePipeline(repo).apply_bump("patch")


def test_disagreeing_versions_accept_an_explicit_target(tmp_path: Path) -> None:
    repo = tmp_path / "mixed2"
    subprocess.run(["git", "init", str(repo)], check=True, capture_output=True)
    for name, version in (("haybale-alpha", "0.3.1"), ("haybale-beta", "0.9.0")):
        lib = repo / "barn" / name
        lib.mkdir(parents=True)
        (lib / "pyproject.toml").write_text(f'[project]\nname = "{name}"\nversion = "{version}"\n')

    result = SharePipeline(repo).apply_bump("1.0.0")
    assert result.version == "1.0.0"
    for name in ("haybale-alpha", "haybale-beta"):
        path = repo / "barn" / name / "pyproject.toml"
        assert toml.loads(path.read_text())["project"]["version"] == "1.0.0"
