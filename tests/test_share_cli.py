"""`haywire share` — the two modes over SharePipeline."""

import subprocess
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest
import toml

pytestmark = pytest.mark.unit


@pytest.fixture
def project(tmp_path: Path) -> Path:
    """Git repo, bare origin, one barn library at 0.3.1, one commit."""
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
    (lib / "haybale_alpha" / "__init__.py").write_text(
        '@library(label="Alpha", id="alpha")\nclass Library: pass\n'
    )
    subprocess.run(["git", "add", "-A"], cwd=repo, check=True, capture_output=True)
    subprocess.run(["git", "commit", "-m", "seed"], cwd=repo, check=True, capture_output=True)
    subprocess.run(["git", "push", "-u", "origin", "HEAD"], cwd=repo, check=True, capture_output=True)
    return repo


def _no_drift(lib_dir: Path):
    from haywire_studio.packaging.share import DepDrift

    return DepDrift(lib_dir=lib_dir)


def _fake_docs():
    """Patch apply_docs so no real library system boots in a unit test."""
    from haywire_studio.packaging.share.pipeline.results import DocsResult

    return patch(
        "haywire_studio.packaging.share.pipeline.pipeline.SharePipeline.apply_docs",
        new=AsyncMock(return_value=DocsResult(coverage={}, written=[])),
    )


# ── --yes ────────────────────────────────────────────────────────────────────


def test_yes_runs_the_whole_pipeline(project: Path) -> None:
    from haywire_studio.packaging.share.cli import run_share_cli

    with (
        patch(
            "haywire_studio.packaging.share.pipeline.steps.drift.detect_share_drift", side_effect=_no_drift
        ),
        _fake_docs(),
    ):
        code = run_share_cli(repo_root=project, yes=True, bump="patch", message=None)

    assert code == 0
    path = project / "barn" / "haybale-alpha" / "pyproject.toml"
    assert toml.loads(path.read_text())["project"]["version"] == "0.3.2"

    tags = subprocess.run(
        ["git", "tag", "--list"], cwd=project, capture_output=True, text=True, check=True
    ).stdout.split()
    assert "v0.3.2" in tags


def test_yes_uses_the_supplied_message(project: Path) -> None:
    from haywire_studio.packaging.share.cli import run_share_cli

    with (
        patch(
            "haywire_studio.packaging.share.pipeline.steps.drift.detect_share_drift", side_effect=_no_drift
        ),
        _fake_docs(),
    ):
        run_share_cli(
            repo_root=project,
            yes=True,
            bump="patch",
            message="release: 0.3.2",
        )

    subject = subprocess.run(
        ["git", "log", "-1", "--format=%s"], cwd=project, capture_output=True, text=True, check=True
    ).stdout.strip()
    assert subject == "release: 0.3.2"


def test_yes_without_bump_fails_fast(project: Path, capsys) -> None:
    """Non-interactive means every answer comes from a flag — guessing a version is not ours to do."""
    from haywire_studio.packaging.share.cli import run_share_cli

    code = run_share_cli(repo_root=project, yes=True, bump=None, message=None)

    assert code != 0
    assert "--bump" in capsys.readouterr().out


def test_yes_stops_on_unresolved_drift(project: Path, capsys) -> None:
    """Replace can destructively remove declared deps — never a non-interactive default."""
    from haywire_studio.packaging.share import DepDrift
    from haywire_studio.packaging.share.cli import run_share_cli

    def _drifty(lib_dir: Path):
        return DepDrift(lib_dir=lib_dir, pyproject_missing=["numpy"])

    with patch(
        "haywire_studio.packaging.share.pipeline.steps.drift.detect_share_drift", side_effect=_drifty
    ):
        code = run_share_cli(repo_root=project, yes=True, bump="patch", message=None)

    assert code != 0
    out = capsys.readouterr().out
    assert "drift" in out.lower()


def test_yes_reports_a_tag_collision_without_mutating(project: Path, capsys) -> None:
    from haywire_studio.packaging.share.cli import run_share_cli

    subprocess.run(["git", "tag", "v0.3.2"], cwd=project, check=True, capture_output=True)

    with patch(
        "haywire_studio.packaging.share.pipeline.steps.drift.detect_share_drift", side_effect=_no_drift
    ):
        code = run_share_cli(repo_root=project, yes=True, bump="patch", message=None)

    assert code != 0
    assert "v0.3.2" in capsys.readouterr().out
    path = project / "barn" / "haybale-alpha" / "pyproject.toml"
    assert toml.loads(path.read_text())["project"]["version"] == "0.3.1"


def test_yes_prints_the_share_url(project: Path, capsys) -> None:
    from haywire_studio.packaging.share.cli import run_share_cli

    with (
        patch(
            "haywire_studio.packaging.share.pipeline.steps.drift.detect_share_drift", side_effect=_no_drift
        ),
        _fake_docs(),
    ):
        run_share_cli(repo_root=project, yes=True, bump="patch", message=None)

    # The fixture's origin is a local path, so no host provider resolves and the
    # warning path is exercised instead of a URL. Either way the user is told.
    out = capsys.readouterr().out
    assert "marketstall.toml" in out


def test_precondition_failure_exits_before_any_write(tmp_path: Path) -> None:
    from haywire_studio.packaging.share.cli import run_share_cli

    repo = tmp_path / "noremote"
    lib = repo / "barn" / "haybale-alpha"
    lib.mkdir(parents=True)
    (lib / "pyproject.toml").write_text('[project]\nname = "haybale-alpha"\nversion = "0.1.0"\n')
    subprocess.run(["git", "init"], cwd=repo, check=True, capture_output=True)

    code = run_share_cli(repo_root=repo, yes=True, bump="patch", message=None)

    assert code != 0
    assert toml.loads((lib / "pyproject.toml").read_text())["project"]["version"] == "0.1.0"


# ── argparse surface ─────────────────────────────────────────────────────────


def test_share_help_lists_the_two_modes() -> None:
    result = subprocess.run(["uv", "run", "haywire", "share", "--help"], capture_output=True, text=True)
    assert "--yes" in result.stdout
    assert "--bump" in result.stdout


def test_removed_flags_are_gone() -> None:
    """--save, --strict/--fix, and --check were prior shapes; leaving them would
    imply behaviour the pipeline no longer has."""
    result = subprocess.run(["uv", "run", "haywire", "share", "--help"], capture_output=True, text=True)
    assert "--save" not in result.stdout
    assert "--strict" not in result.stdout
    assert "--check" not in result.stdout
