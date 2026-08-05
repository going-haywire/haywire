"""`haywire share` — the two modes over SharePipeline."""

import subprocess
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest
import toml

from haywire_studio.packaging.share.pipeline.pipeline import SharePipeline
from haywire_studio.packaging.share.pipeline.steps import detect as steps_detect

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

    return patch.object(
        SharePipeline, "apply_docs", new=AsyncMock(return_value=DocsResult(coverage={}, written=[]))
    )


# ── --yes ────────────────────────────────────────────────────────────────────


def test_yes_runs_the_whole_pipeline(project: Path) -> None:
    from haywire_studio.packaging.share.cli import run_share_cli

    with (
        patch.object(steps_detect, "detect_share_drift", side_effect=_no_drift),
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
        patch.object(steps_detect, "detect_share_drift", side_effect=_no_drift),
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


def test_yes_declares_undeclared_imports_rather_than_refusing(project: Path) -> None:
    """Declaring an import the source actually uses is unambiguously correct.

    The old behaviour refused ANY drift, because both apply modes mutated and
    one removed declarations. Removals are now their own optional step, so the
    only thing left for --yes to do here is the safe, corrective one.
    """
    from haywire_studio.packaging.share import DepDrift
    from haywire_studio.packaging.share.cli import run_share_cli

    def _drifty(lib_dir: Path):
        return DepDrift(lib_dir=lib_dir, pyproject_missing=["toml"])

    with (
        patch.object(steps_detect, "detect_share_drift", side_effect=_drifty),
        _fake_docs(),
    ):
        code = run_share_cli(repo_root=project, yes=True, bump="patch", message=None)

    assert code == 0
    table = toml.loads((project / "barn" / "haybale-alpha" / "pyproject.toml").read_text())["project"]
    assert any(entry.startswith("toml") for entry in table.get("dependencies", []))


def test_yes_never_removes_declarations(project: Path) -> None:
    """Removals are lossy and stay interactive — --yes must not guess."""
    from haywire_studio.packaging.share import DepDrift
    from haywire_studio.packaging.share.cli import run_share_cli

    lib = project / "barn" / "haybale-alpha"
    (lib / "pyproject.toml").write_text(
        '[project]\nname = "haybale-alpha"\nversion = "0.3.1"\ndependencies = ["numpy>=1.0"]\n'
    )

    def _unused(lib_dir: Path):
        return DepDrift(lib_dir=lib_dir, unused_declarations=["numpy"])

    with (
        patch.object(steps_detect, "detect_share_drift", side_effect=_unused),
        _fake_docs(),
    ):
        run_share_cli(repo_root=project, yes=True, bump="patch", message=None)

    table = toml.loads((lib / "pyproject.toml").read_text())["project"]
    assert table["dependencies"] == ["numpy>=1.0"]


def test_yes_reports_a_tag_collision_without_mutating(project: Path, capsys) -> None:
    from haywire_studio.packaging.share.cli import run_share_cli

    subprocess.run(["git", "tag", "v0.3.2"], cwd=project, check=True, capture_output=True)

    with patch.object(steps_detect, "detect_share_drift", side_effect=_no_drift):
        code = run_share_cli(repo_root=project, yes=True, bump="patch", message=None)

    assert code != 0
    assert "v0.3.2" in capsys.readouterr().out
    path = project / "barn" / "haybale-alpha" / "pyproject.toml"
    assert toml.loads(path.read_text())["project"]["version"] == "0.3.1"


def test_yes_prints_the_share_url(project: Path, capsys) -> None:
    from haywire_studio.packaging.share.cli import run_share_cli

    with (
        patch.object(steps_detect, "detect_share_drift", side_effect=_no_drift),
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


# ── detect report ────────────────────────────────────────────────────────────


def test_detect_report_groups_by_finding_not_by_library(capsys) -> None:
    """Each explanation appears ONCE, with every instance listed under it.

    Grouping by library repeated the same paragraph per library and left the
    reader to work out which name was the subject and which the container.
    """
    from types import SimpleNamespace

    from haywire_studio.packaging.share.cli import _print_detect_report

    def _drift(name: str, **kwargs):
        fields: dict[str, list] = dict(
            pyproject_missing=[],
            decorator_missing=[],
            unused_declarations=[],
            pyproject_version_lag=[],
            unresolved=[],
        )
        fields.update(kwargs)
        return SimpleNamespace(lib_dir=Path(f"barn/{name}"), **fields)

    _print_detect_report(
        SimpleNamespace(
            libraries=[
                _drift("haybale-example", decorator_missing=["haybale_studio"]),
                _drift("haybale-marketplace", decorator_missing=["haybale_studio"]),
                _drift("haybale-studio", pyproject_missing=["haywire-studio"]),
            ]
        )
    )

    out = capsys.readouterr().out
    # One heading per finding, however many libraries it spans.
    assert out.count("Undeclared in @library(dependencies)") == 1
    # Both instances sit under it, each naming its own library.
    assert "haybale_studio  in haybale-example" in out
    assert "haybale_studio  in haybale-marketplace" in out
    # A different finding gets its own heading.
    assert "haywire-studio  in haybale-studio" in out


def test_detect_report_says_so_when_there_is_nothing(capsys) -> None:
    from types import SimpleNamespace

    from haywire_studio.packaging.share.cli import _print_detect_report

    _print_detect_report(SimpleNamespace(libraries=[]))

    assert "Nothing to report" in capsys.readouterr().out


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
