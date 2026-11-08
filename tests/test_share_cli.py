"""`haywire share` — the single non-interactive mode over SharePipeline."""

import subprocess
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest
import toml

from haywire.core.publishing.pipeline.pipeline import SharePipeline
from haywire.core.publishing.pipeline.steps import detect as steps_detect

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
    from haywire.core.publishing import DepDrift

    return DepDrift(lib_dir=lib_dir)


def _fake_docs():
    """Patch apply_docs so no real library system boots in a unit test."""
    from haywire.core.publishing.pipeline.results import DocsResult

    return patch.object(
        SharePipeline, "apply_docs", new=AsyncMock(return_value=DocsResult(coverage={}, written=[]))
    )


# ── --yes ────────────────────────────────────────────────────────────────────


def test_yes_runs_the_whole_pipeline(project: Path) -> None:
    from haywire_studio.packaging.share_cli import run_share_cli

    with (
        patch.object(steps_detect, "detect_share_drift", side_effect=_no_drift),
        _fake_docs(),
    ):
        code = run_share_cli(repo_root=project, bump="patch", message=None)

    assert code == 0
    path = project / "barn" / "haybale-alpha" / "pyproject.toml"
    assert toml.loads(path.read_text())["project"]["version"] == "0.3.2"

    tags = subprocess.run(
        ["git", "tag", "--list"], cwd=project, capture_output=True, text=True, check=True
    ).stdout.split()
    assert "v0.3.2" in tags


def test_yes_uses_the_supplied_message(project: Path) -> None:
    from haywire_studio.packaging.share_cli import run_share_cli

    with (
        patch.object(steps_detect, "detect_share_drift", side_effect=_no_drift),
        _fake_docs(),
    ):
        run_share_cli(
            repo_root=project,
            bump="patch",
            message="release: 0.3.2",
        )

    subject = subprocess.run(
        ["git", "log", "-1", "--format=%s"], cwd=project, capture_output=True, text=True, check=True
    ).stdout.strip()
    assert subject == "release: 0.3.2"


def test_yes_without_bump_fails_fast(project: Path, capsys) -> None:
    """Non-interactive means every answer comes from a flag — guessing a version is not ours to do."""
    from haywire_studio.packaging.share_cli import run_share_cli

    code = run_share_cli(repo_root=project, bump=None, message=None)

    assert code != 0
    assert "--bump" in capsys.readouterr().out


def test_yes_declares_undeclared_imports_rather_than_refusing(project: Path) -> None:
    """Declaring an import the source actually uses is unambiguously correct.

    The old behaviour refused ANY drift, because both apply modes mutated and
    one removed declarations. Removals are now their own optional step, so the
    only thing left for --yes to do here is the safe, corrective one.
    """
    from haywire.core.publishing import DepDrift
    from haywire_studio.packaging.share_cli import run_share_cli

    def _drifty(lib_dir: Path):
        return DepDrift(lib_dir=lib_dir, pyproject_missing=["toml"])

    with (
        patch.object(steps_detect, "detect_share_drift", side_effect=_drifty),
        _fake_docs(),
    ):
        code = run_share_cli(repo_root=project, bump="patch", message=None)

    assert code == 0
    table = toml.loads((project / "barn" / "haybale-alpha" / "pyproject.toml").read_text())["project"]
    assert any(entry.startswith("toml") for entry in table.get("dependencies", []))


def test_yes_never_removes_declarations(project: Path) -> None:
    """Removals are lossy and stay interactive — --yes must not guess."""
    from haywire.core.publishing import DepDrift
    from haywire_studio.packaging.share_cli import run_share_cli

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
        run_share_cli(repo_root=project, bump="patch", message=None)

    table = toml.loads((lib / "pyproject.toml").read_text())["project"]
    assert table["dependencies"] == ["numpy>=1.0"]


def test_yes_reports_a_tag_collision_without_mutating(project: Path, capsys) -> None:
    from haywire_studio.packaging.share_cli import run_share_cli

    subprocess.run(["git", "tag", "v0.3.2"], cwd=project, check=True, capture_output=True)

    with patch.object(steps_detect, "detect_share_drift", side_effect=_no_drift):
        code = run_share_cli(repo_root=project, bump="patch", message=None)

    assert code != 0
    assert "v0.3.2" in capsys.readouterr().out
    path = project / "barn" / "haybale-alpha" / "pyproject.toml"
    assert toml.loads(path.read_text())["project"]["version"] == "0.3.1"


def test_yes_prints_the_share_url(project: Path, capsys) -> None:
    from haywire_studio.packaging.share_cli import run_share_cli

    with (
        patch.object(steps_detect, "detect_share_drift", side_effect=_no_drift),
        _fake_docs(),
    ):
        run_share_cli(repo_root=project, bump="patch", message=None)

    # The fixture's origin is a local path, so no host provider resolves and the
    # warning path is exercised instead of a URL. Either way the user is told.
    out = capsys.readouterr().out
    assert "marketstall.toml" in out


def test_precondition_failure_exits_before_any_write(tmp_path: Path) -> None:
    from haywire_studio.packaging.share_cli import run_share_cli

    repo = tmp_path / "noremote"
    lib = repo / "barn" / "haybale-alpha"
    lib.mkdir(parents=True)
    (lib / "pyproject.toml").write_text('[project]\nname = "haybale-alpha"\nversion = "0.1.0"\n')
    subprocess.run(["git", "init"], cwd=repo, check=True, capture_output=True)

    code = run_share_cli(repo_root=repo, bump="patch", message=None)

    assert code != 0
    assert toml.loads((lib / "pyproject.toml").read_text())["project"]["version"] == "0.1.0"


# ── detect report ────────────────────────────────────────────────────────────


def test_findings_name_the_library_on_every_line(project: Path, capsys) -> None:
    """Each line stands alone.

    The CLI does not group by finding kind the way the Share editor does: the
    editor has room and controls to attach, and a second copy of that
    vocabulary here is exactly what made the old interactive mode diverge from
    the wizard it was supposed to mirror.
    """
    from haywire.core.publishing.pipeline import DepDrift, DriftReport, SharePipeline
    from haywire_studio.packaging.share_cli import _print_findings

    report = DriftReport(
        drifted=[DepDrift(lib_dir=Path("barn/haybale-studio"), pyproject_missing=["haywire-studio"])],
        findings_only=[DepDrift(lib_dir=Path("barn/haybale-example"), unused_declarations=["requests"])],
    )
    with patch.object(SharePipeline, "check_drift", return_value=report):
        _print_findings(SharePipeline(project))

    out = capsys.readouterr().out
    assert "haybale-studio: haywire-studio imported but not declared" in out
    assert "haybale-example: requests declared but not imported" in out


def test_findings_say_so_when_there_is_nothing(project: Path, capsys) -> None:
    from haywire.core.publishing.pipeline import DriftReport, SharePipeline
    from haywire_studio.packaging.share_cli import _print_findings

    with patch.object(SharePipeline, "check_drift", return_value=DriftReport(drifted=[], findings_only=[])):
        _print_findings(SharePipeline(project))

    assert "Nothing to report" in capsys.readouterr().out


# ── idempotency, --status, --resume ─────────────────────────────────────────


def _release(project: Path) -> None:
    from haywire_studio.packaging.share_cli import run_share_cli

    with (
        patch.object(steps_detect, "detect_share_drift", side_effect=_no_drift),
        _fake_docs(),
    ):
        assert run_share_cli(repo_root=project, bump="patch", message=None) == 0


def _tags(project: Path) -> list[str]:
    return subprocess.run(
        ["git", "tag", "--list"], cwd=project, capture_output=True, text=True, check=True
    ).stdout.split()


def test_second_share_of_the_same_change_is_refused(project: Path, capsys) -> None:
    from haywire_studio.packaging.share_cli import run_share_cli

    _release(project)
    with (
        patch.object(steps_detect, "detect_share_drift", side_effect=_no_drift),
        _fake_docs(),
    ):
        code = run_share_cli(repo_root=project, bump="patch", message=None)

    assert code != 0
    assert "Already released" in capsys.readouterr().out
    assert _tags(project) == ["v0.3.2"]


def test_status_reports_ready_then_released(project: Path, capsys) -> None:
    from haywire_studio.packaging.share_cli import run_share_cli

    assert run_share_cli(repo_root=project, bump=None, message=None, status=True) == 0
    out = capsys.readouterr().out
    assert "STATE: READY" in out
    assert "NEXT: " in out

    _release(project)
    capsys.readouterr()
    assert run_share_cli(repo_root=project, bump=None, message=None, status=True) == 10
    assert "STATE: RELEASED" in capsys.readouterr().out


def test_status_writes_nothing(project: Path) -> None:
    from haywire_studio.packaging.share_cli import run_share_cli

    run_share_cli(repo_root=project, bump=None, message=None, status=True)
    porcelain = subprocess.run(["git", "status", "--porcelain"], cwd=project, capture_output=True, text=True)
    assert porcelain.stdout == ""
    assert _tags(project) == []


def test_resume_finishes_a_release_whose_push_failed(project: Path, capsys) -> None:
    from haywire.core.publishing.pipeline.errors import PushError
    from haywire_studio.packaging.share_cli import run_share_cli

    failing_push = AsyncMock(side_effect=PushError(stderr="boom", manual_command="git push"))
    with (
        patch.object(steps_detect, "detect_share_drift", side_effect=_no_drift),
        _fake_docs(),
        patch.object(SharePipeline, "apply_push", new=failing_push),
    ):
        assert run_share_cli(repo_root=project, bump="patch", message=None) == 50
    assert _tags(project) == ["v0.3.2"]

    capsys.readouterr()
    assert run_share_cli(repo_root=project, bump=None, message=None, status=True) == 20
    out = capsys.readouterr().out
    assert "STATE: UNPUSHED" in out
    assert "NEXT: uv run --frozen haywire share --resume" in out

    assert run_share_cli(repo_root=project, bump=None, message=None, resume=True) == 0
    remote_tags = subprocess.run(
        ["git", "ls-remote", "--tags", "origin"], cwd=project, capture_output=True, text=True
    ).stdout
    assert "refs/tags/v0.3.2" in remote_tags
    assert _tags(project) == ["v0.3.2"]


# ── exit codes and --json ───────────────────────────────────────────────────


def test_missing_bump_is_a_usage_error(project: Path) -> None:
    from haywire_studio.packaging.share_cli import EXIT_USAGE, run_share_cli

    assert run_share_cli(repo_root=project, bump=None, message=None) == EXIT_USAGE


def test_a_fixable_refusal_exits_20_and_names_the_next_step(project: Path, capsys) -> None:
    from haywire_studio.packaging.share_cli import EXIT_REFUSED, run_share_cli

    (project / "stray.txt").write_text("x")
    assert run_share_cli(repo_root=project, bump="patch", message=None) == EXIT_REFUSED
    out = capsys.readouterr().out
    assert "NEXT: " in out
    assert "STATE: BLOCKED" in out


def test_a_human_only_refusal_exits_30_with_a_stop_line(project: Path, capsys) -> None:
    from haywire_studio.packaging.share_cli import EXIT_HUMAN_NEEDED, run_share_cli

    subprocess.run(["git", "remote", "remove", "origin"], cwd=project, check=True, capture_output=True)
    assert run_share_cli(repo_root=project, bump="patch", message=None) == EXIT_HUMAN_NEEDED
    out = capsys.readouterr().out
    assert "STOP: human needed" in out
    assert "STATE: NEEDS_HUMAN" in out


def test_a_step_failure_before_the_commit_exits_40_and_reverts(project: Path, capsys) -> None:
    from haywire.core.publishing.pipeline.errors import MarketstallError
    from haywire_studio.packaging.share_cli import EXIT_FAILED_REVERTED, run_share_cli

    with (
        patch.object(steps_detect, "detect_share_drift", side_effect=_no_drift),
        _fake_docs(),
        patch.object(SharePipeline, "apply_marketstall", side_effect=MarketstallError("boom")),
    ):
        code = run_share_cli(repo_root=project, bump="patch", message=None)

    assert code == EXIT_FAILED_REVERTED
    path = project / "barn" / "haybale-alpha" / "pyproject.toml"
    assert toml.loads(path.read_text())["project"]["version"] == "0.3.1"
    assert _tags(project) == []
    assert "Reverted" in capsys.readouterr().out


def test_json_prints_one_object_on_stdout_and_prose_on_stderr(project: Path, capsys) -> None:
    import json

    from haywire_studio.packaging.share_cli import run_share_cli

    code = run_share_cli(repo_root=project, bump=None, message=None, status=True, json_output=True)

    captured = capsys.readouterr()
    payload = json.loads(captured.out)
    assert code == 0
    assert payload["schema"] == 1
    assert (payload["state"], payload["exit_code"], payload["ok"]) == ("READY", 0, True)
    assert payload["next"]["command"].endswith("share --bump patch")
    assert "Ready to release" in captured.err


def test_json_describes_a_refusal(project: Path, capsys) -> None:
    import json

    from haywire_studio.packaging.share_cli import run_share_cli

    _release(project)
    capsys.readouterr()
    run_share_cli(repo_root=project, bump="patch", message=None, json_output=True)

    payload = json.loads(capsys.readouterr().out)
    assert (payload["state"], payload["exit_code"], payload["ok"]) == ("RELEASED", 10, True)
    assert payload["failure"]["code"] == "already_released"


# ── argparse surface ─────────────────────────────────────────────────────────


def test_share_help_lists_the_one_mode() -> None:
    result = subprocess.run(["uv", "run", "haywire", "share", "--help"], capture_output=True, text=True)
    assert "--bump" in result.stdout
    assert "--dry-run" in result.stdout
    # --yes named the wrong thing (the run authors a release; it does not
    # "assume yes") and switched on a prompt mode that no longer exists.
    assert "--yes" not in result.stdout


def test_removed_flags_are_gone() -> None:
    """--save, --strict/--fix, and --check were prior shapes; leaving them would
    imply behaviour the pipeline no longer has."""
    result = subprocess.run(["uv", "run", "haywire", "share", "--help"], capture_output=True, text=True)
    assert "--save" not in result.stdout
    assert "--strict" not in result.stdout
    assert "--check" not in result.stdout


# ── --first-release ─────────────────────────────────────────────────────────


@pytest.fixture
def pypi_project(project: Path) -> Path:
    """The project, declaring distribute = pypi, committed and pushed."""
    (project / "pyproject.toml").write_text('[tool.haywire.marketstall]\ndistribute = "pypi"\n')
    subprocess.run(["git", "add", "-A"], cwd=project, check=True, capture_output=True)
    subprocess.run(["git", "commit", "-m", "pypi"], cwd=project, check=True, capture_output=True)
    subprocess.run(["git", "push"], cwd=project, check=True, capture_output=True)
    return project


def _pypi(monkeypatch: pytest.MonkeyPatch, answer: bool | None, *, github: bool = True) -> None:
    from haywire.core.publishing import human_steps
    from haywire.core.publishing.pipeline.steps import preconditions

    monkeypatch.setattr(preconditions, "_pypi_name_is_registered", lambda name, **kw: answer)
    if github:
        monkeypatch.setattr(human_steps, "github_owner_repo", lambda url: ("o", "r"))


def test_a_missing_pypi_name_stops_for_the_owner_and_names_the_next_command(
    pypi_project: Path, monkeypatch: pytest.MonkeyPatch, capsys
) -> None:
    from haywire_studio.packaging.share_cli import EXIT_HUMAN_NEEDED, run_share_cli

    _pypi(monkeypatch, False)
    code = run_share_cli(repo_root=pypi_project, bump="patch", message=None)

    out = capsys.readouterr().out
    assert code == EXIT_HUMAN_NEEDED
    assert "Register a PyPI pending publisher" in out
    assert "THEN, once the owner confirms: uv run --frozen haywire share --first-release" in out
    assert _tags(pypi_project) == []


def test_first_release_tags_the_declared_version_without_bumping(
    pypi_project: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from haywire_studio.packaging.share_cli import run_share_cli

    _pypi(monkeypatch, False)
    with (
        patch.object(steps_detect, "detect_share_drift", side_effect=_no_drift),
        _fake_docs(),
    ):
        code = run_share_cli(repo_root=pypi_project, bump=None, message=None, first_release=True)

    assert code == 0
    assert _tags(pypi_project) == ["v0.3.1"]
    path = pypi_project / "barn" / "haybale-alpha" / "pyproject.toml"
    assert toml.loads(path.read_text())["project"]["version"] == "0.3.1"
    assert (
        "refs/tags/v0.3.1"
        in subprocess.run(
            ["git", "ls-remote", "--tags", "origin"], cwd=pypi_project, capture_output=True, text=True
        ).stdout
    )


def test_first_release_with_bump_composes(pypi_project: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from haywire_studio.packaging.share_cli import run_share_cli

    _pypi(monkeypatch, False)
    with (
        patch.object(steps_detect, "detect_share_drift", side_effect=_no_drift),
        _fake_docs(),
    ):
        assert run_share_cli(repo_root=pypi_project, bump="patch", message=None, first_release=True) == 0
    assert _tags(pypi_project) == ["v0.3.2"]


def test_first_release_refuses_a_name_that_exists(
    pypi_project: Path, monkeypatch: pytest.MonkeyPatch, capsys
) -> None:
    from haywire_studio.packaging.share_cli import EXIT_REFUSED, run_share_cli

    _pypi(monkeypatch, True)
    code = run_share_cli(repo_root=pypi_project, bump=None, message=None, first_release=True)

    assert code == EXIT_REFUSED
    assert "already exist on PyPI" in capsys.readouterr().out
    assert _tags(pypi_project) == []


def test_first_release_refuses_when_pypi_cannot_confirm(
    pypi_project: Path, monkeypatch: pytest.MonkeyPatch, capsys
) -> None:
    from haywire_studio.packaging.share_cli import EXIT_REFUSED, run_share_cli

    _pypi(monkeypatch, None)
    code = run_share_cli(repo_root=pypi_project, bump=None, message=None, first_release=True)

    assert code == EXIT_REFUSED
    assert "NEXT: uv run --frozen haywire share --first-release" in capsys.readouterr().out


def test_first_release_stops_on_a_non_github_host(
    pypi_project: Path, monkeypatch: pytest.MonkeyPatch, capsys
) -> None:
    from haywire_studio.packaging.share_cli import EXIT_HUMAN_NEEDED, run_share_cli

    _pypi(monkeypatch, False, github=False)
    code = run_share_cli(repo_root=pypi_project, bump=None, message=None, first_release=True)

    assert code == EXIT_HUMAN_NEEDED
    assert "github.com only" in capsys.readouterr().out


def test_first_release_needs_a_new_version_when_the_current_one_is_tagged(
    pypi_project: Path, monkeypatch: pytest.MonkeyPatch, capsys
) -> None:
    from haywire_studio.packaging.share_cli import EXIT_REFUSED, run_share_cli

    subprocess.run(["git", "tag", "v0.3.1"], cwd=pypi_project, check=True, capture_output=True)
    subprocess.run(["git", "push", "origin", "refs/tags/v0.3.1"], cwd=pypi_project, check=True)
    (pypi_project / "barn" / "haybale-alpha" / "mod.py").write_text("x = 1\n")
    subprocess.run(["git", "add", "-A"], cwd=pypi_project, check=True, capture_output=True)
    subprocess.run(["git", "commit", "-m", "more"], cwd=pypi_project, check=True, capture_output=True)
    subprocess.run(["git", "push"], cwd=pypi_project, check=True, capture_output=True)
    _pypi(monkeypatch, False)
    code = run_share_cli(repo_root=pypi_project, bump=None, message=None, first_release=True)

    assert code == EXIT_REFUSED
    assert "--first-release --bump patch" in capsys.readouterr().out


def test_first_release_is_refused_for_a_git_project(
    project: Path, monkeypatch: pytest.MonkeyPatch, capsys
) -> None:
    from haywire_studio.packaging.share_cli import EXIT_REFUSED, run_share_cli

    _pypi(monkeypatch, False)
    code = run_share_cli(repo_root=project, bump=None, message=None, first_release=True)

    assert code == EXIT_REFUSED
    assert 'distribute = "pypi"' in capsys.readouterr().out
