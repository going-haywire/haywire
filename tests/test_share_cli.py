"""`haywire share` — the single non-interactive mode over SharePipeline."""

from __future__ import annotations

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

    assert capsys.readouterr().out.strip()


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
    assert "STOP:" in out
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
    assert captured.err.strip()


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
    imply behaviour the pipeline no longer has.
    """
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
    assert "haybale-alpha" in capsys.readouterr().out
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


# ── --first-release in a project that already has names on PyPI ─────────────


@pytest.fixture
def mixed_project(pypi_project: Path) -> Path:
    """The pypi project plus a second library, haybale-beta, at the same version."""
    lib = pypi_project / "barn" / "haybale-beta"
    lib.mkdir(parents=True)
    (lib / "pyproject.toml").write_text('[project]\nname = "haybale-beta"\nversion = "0.3.1"\n')
    (lib / "haybale_beta").mkdir()
    (lib / "haybale_beta" / "__init__.py").write_text("")
    (lib / "haybale_beta" / "haybale.toml").write_text('name = "haybale-beta"\nversion = "0.3.1"\n')
    subprocess.run(["git", "add", "-A"], cwd=pypi_project, check=True, capture_output=True)
    subprocess.run(["git", "commit", "-m", "beta"], cwd=pypi_project, check=True, capture_output=True)
    subprocess.run(["git", "push"], cwd=pypi_project, check=True, capture_output=True)
    return pypi_project


def _pypi_names(monkeypatch: pytest.MonkeyPatch, answers: dict[str, bool | None]) -> None:
    """PyPI answers per distribution name; GitHub is the host."""
    from haywire.core.publishing import human_steps
    from haywire.core.publishing.pipeline.steps import preconditions

    monkeypatch.setattr(preconditions, "_pypi_name_is_registered", lambda name, **kw: answers[name])
    monkeypatch.setattr(human_steps, "github_owner_repo", lambda url: ("o", "r"))


def test_first_release_with_bump_creates_the_new_name_and_updates_the_existing(
    mixed_project: Path, monkeypatch: pytest.MonkeyPatch, capsys
) -> None:
    from haywire_studio.packaging.share_cli import run_share_cli

    _pypi_names(monkeypatch, {"haybale-alpha": True, "haybale-beta": False})
    with (
        patch.object(steps_detect, "detect_share_drift", side_effect=_no_drift),
        _fake_docs(),
    ):
        code = run_share_cli(repo_root=mixed_project, bump="patch", message=None, first_release=True)

    out = capsys.readouterr().out
    assert code == 0
    assert "creates on PyPI: haybale-beta" in out
    assert "adds a version to: haybale-alpha" in out
    assert _tags(mixed_project) == ["v0.3.2"]


def test_first_release_without_bump_is_refused_when_some_names_exist(
    mixed_project: Path, monkeypatch: pytest.MonkeyPatch, capsys
) -> None:
    from haywire_studio.packaging.share_cli import EXIT_REFUSED, run_share_cli

    _pypi_names(monkeypatch, {"haybale-alpha": True, "haybale-beta": False})
    code = run_share_cli(repo_root=mixed_project, bump=None, message=None, first_release=True)

    out = capsys.readouterr().out
    assert code == EXIT_REFUSED
    assert "needs a new version" in out
    assert "NEXT: uv run --frozen haywire share --first-release --bump patch" in out
    assert _tags(mixed_project) == []


def test_first_release_is_refused_when_no_name_is_new(
    mixed_project: Path, monkeypatch: pytest.MonkeyPatch, capsys
) -> None:
    from haywire_studio.packaging.share_cli import EXIT_REFUSED, run_share_cli

    _pypi_names(monkeypatch, {"haybale-alpha": True, "haybale-beta": True})
    code = run_share_cli(repo_root=mixed_project, bump="patch", message=None, first_release=True)

    assert code == EXIT_REFUSED
    out = capsys.readouterr().out
    assert "haybale-alpha" in out
    assert "haybale-beta" in out
    assert _tags(mixed_project) == []


def test_the_owner_checklist_lists_only_the_missing_names_and_asks_for_a_bump(
    mixed_project: Path, monkeypatch: pytest.MonkeyPatch, capsys
) -> None:
    from haywire_studio.packaging.share_cli import EXIT_HUMAN_NEEDED, run_share_cli

    _pypi_names(monkeypatch, {"haybale-alpha": True, "haybale-beta": False})
    code = run_share_cli(repo_root=mixed_project, bump="patch", message=None)

    out = capsys.readouterr().out
    assert code == EXIT_HUMAN_NEEDED
    assert "haybale-beta" in out
    assert "haybale-alpha" not in out.split("Give this to the owner")[1].split("THEN")[0]
    assert "THEN, once the owner confirms: uv run --frozen haywire share --first-release --bump patch" in out
    assert _tags(mixed_project) == []


# ── --pr: a release through a pull request ──────────────────────────────────


def _pr_run(project: Path, *, gh: str | None = None, gh_result=None, gh_calls: list | None = None):
    """A ``--pr`` run. *gh* is where ``shutil.which`` finds gh (None: not installed),
    *gh_result* what running it returns; *gh_calls* collects the command lines run.
    """
    from haywire.core.publishing.pipeline.steps import release_pr
    from haywire_studio.packaging.share_cli import run_share_cli

    with (
        patch.object(steps_detect, "detect_share_drift", side_effect=_no_drift),
        _fake_docs(),
        patch.object(release_pr.shutil, "which", return_value=gh),
        patch.object(release_pr, "run", return_value=gh_result) as gh_run,
    ):
        code = run_share_cli(repo_root=project, bump="patch", message=None, pr=True)
    if gh_calls is not None:
        gh_calls += [call.args[0] for call in gh_run.call_args_list]
    return code


def _git_out(repo: Path, *args: str) -> str:
    return subprocess.run(
        ["git", *args], cwd=repo, capture_output=True, text=True, check=True
    ).stdout.strip()


def test_pr_mode_pushes_only_the_release_branch(project: Path, capsys) -> None:
    default = _git_out(project, "rev-parse", "--abbrev-ref", "HEAD")
    before = _git_out(project, "rev-parse", "HEAD")

    assert _pr_run(project) == 0

    out = capsys.readouterr().out
    assert "STATE: RELEASE_BRANCH_PUSHED" in out
    assert _tags(project) == []
    assert _git_out(project, "rev-parse", "--abbrev-ref", "HEAD") == default
    assert _git_out(project, "rev-parse", "HEAD") == before
    assert _git_out(project, "status", "--porcelain") == ""
    heads = _git_out(project, "ls-remote", "--heads", "origin")
    assert "refs/heads/release/v0.3.2" in heads
    assert _git_out(project, "rev-parse", f"origin/{default}") == before
    release = _git_out(project, "show", "release/v0.3.2:barn/haybale-alpha/pyproject.toml")
    assert toml.loads(release)["project"]["version"] == "0.3.2"


def test_pr_mode_opens_the_pr_with_gh(project: Path, capsys) -> None:
    from haywire.core.publishing.git import GitResult

    url = "https://github.com/o/r/pull/7"
    calls: list = []
    assert (
        _pr_run(project, gh="/usr/bin/gh", gh_result=GitResult(True, f"{url}\n", "", 0), gh_calls=calls) == 0
    )

    out = capsys.readouterr().out
    assert f"PR: {url}" in out
    assert "STATE: RELEASE_PR_OPEN" in out
    [args] = calls
    default = _git_out(project, "rev-parse", "--abbrev-ref", "HEAD")
    assert args[:3] == ["gh", "pr", "create"]
    assert args[args.index("--head") + 1] == "release/v0.3.2"
    assert args[args.index("--base") + 1] == default
    assert args[args.index("--title") + 1] == "chore: share v0.3.2"


def test_pr_mode_without_gh_names_the_command_that_opens_the_pr(project: Path, capsys) -> None:
    assert _pr_run(project) == 0

    out = capsys.readouterr().out
    assert "gh) is not installed" in out
    assert "NEXT: gh pr create --base " in out
    assert "--head release/v0.3.2 --title 'chore: share v0.3.2'" in out
    assert "STATE: RELEASE_BRANCH_PUSHED" in out
    assert "RELEASE_PR_OPEN" not in out


def test_pr_mode_reports_why_gh_refused(project: Path, capsys) -> None:
    from haywire.core.publishing.git import GitResult

    refused = GitResult(False, "", "To get started with GitHub CLI, please run:  gh auth login\n", 4)
    assert _pr_run(project, gh="/usr/bin/gh", gh_result=refused) == 0

    out = capsys.readouterr().out
    assert "gh could not open the PR: To get started with GitHub CLI" in out
    assert "STATE: RELEASE_BRANCH_PUSHED" in out


def test_pr_mode_runs_from_a_worktree_at_the_default_tip(project: Path, capsys) -> None:
    """A task worktree cannot check out the default branch; a release PR doesn't need it."""
    from haywire.core.publishing.git import GitResult

    default = _git_out(project, "rev-parse", "--abbrev-ref", "HEAD")
    worktree = project.parent / "worktree"
    _git_out(project, "worktree", "add", str(worktree), "-b", "task/release")
    calls: list = []
    ok = GitResult(True, "https://github.com/o/r/pull/8\n", "", 0)

    assert _pr_run(worktree, gh="/usr/bin/gh", gh_result=ok, gh_calls=calls) == 0

    assert "STATE: RELEASE_PR_OPEN" in capsys.readouterr().out
    [args] = calls
    assert args[args.index("--base") + 1] == default
    assert "refs/heads/release/v0.3.2" in _git_out(project, "ls-remote", "--heads", "origin")
    assert _git_out(worktree, "rev-parse", "--abbrev-ref", "HEAD") == "task/release"


def test_pr_mode_refuses_a_branch_ahead_of_the_default_tip(project: Path, capsys) -> None:
    from haywire_studio.packaging.share_cli import EXIT_REFUSED

    _git_out(project, "switch", "-c", "task/ahead")
    (project / "extra.txt").write_text("unreviewed")
    _git_out(project, "add", "extra.txt")
    _git_out(project, "commit", "-m", "ahead")

    assert _pr_run(project) == EXIT_REFUSED

    out = capsys.readouterr().out
    assert "`task/ahead` is not at the latest" in out
    assert "refs/heads/release/" not in _git_out(project, "ls-remote", "--heads", "origin")


def test_a_direct_release_still_needs_the_default_branch(project: Path, capsys) -> None:
    from haywire_studio.packaging.share_cli import EXIT_REFUSED, run_share_cli

    _git_out(project, "switch", "-c", "task/direct")
    with patch.object(steps_detect, "detect_share_drift", side_effect=_no_drift), _fake_docs():
        code = run_share_cli(repo_root=project, bump="patch", message=None)

    assert code == EXIT_REFUSED
    assert "but the repository publishes from" in capsys.readouterr().out


def test_status_reports_the_open_release_pr(project: Path, capsys) -> None:
    from haywire_studio.packaging.share_cli import run_share_cli

    _pr_run(project)
    capsys.readouterr()

    assert run_share_cli(repo_root=project, bump=None, message=None, status=True) == 30
    out = capsys.readouterr().out
    assert "STATE: RELEASE_PR_OPEN" in out


def test_a_merged_release_pr_is_no_longer_open(project: Path, capsys) -> None:
    from haywire_studio.packaging.share_cli import run_share_cli

    _pr_run(project)
    _git_out(project, "merge", "--ff-only", "release/v0.3.2")
    _git_out(project, "push", "origin", "HEAD")
    capsys.readouterr()

    run_share_cli(repo_root=project, bump=None, message=None, status=True)

    assert "RELEASE_PR_OPEN" not in capsys.readouterr().out


def test_pr_mode_refuses_a_branch_that_already_exists_and_reverts(project: Path, capsys) -> None:
    from haywire_studio.packaging.share_cli import run_share_cli

    _git_out(project, "branch", "release/v0.3.2")

    with patch.object(steps_detect, "detect_share_drift", side_effect=_no_drift), _fake_docs():
        code = run_share_cli(repo_root=project, bump="patch", message=None, pr=True)

    assert code == 40
    assert "already exists locally" in capsys.readouterr().out
    assert _git_out(project, "status", "--porcelain") == ""


@pytest.mark.parametrize("other", [{"resume": True}, {"first_release": True}])
def test_pr_cannot_be_combined_with_resume_or_first_release(project: Path, other: dict) -> None:
    from haywire_studio.packaging.share_cli import run_share_cli

    assert run_share_cli(repo_root=project, bump="patch", message=None, pr=True, **other) == 64


def test_the_host_provides_the_link_that_opens_the_pr() -> None:
    from haywire.core.marketstall.host_providers.github import GitHubProvider
    from haywire.core.marketstall.host_providers.gitlab import GitLabProvider

    assert GitHubProvider().new_pull_request_url("o", "r", "master", "release/v1.0.0") == (
        "https://github.com/o/r/compare/master...release/v1.0.0?expand=1"
    )
    assert GitLabProvider().new_pull_request_url("o", "r", "main", "release/v1.0.0") == (
        "https://gitlab.com/o/r/-/merge_requests/new"
        "?merge_request[source_branch]=release/v1.0.0&merge_request[target_branch]=main"
    )


def test_pr_link_is_derived_from_origin(project: Path) -> None:
    from haywire.core.publishing.url import derive_pull_request_url

    _git_out(project, "remote", "set-url", "origin", "git@github.com:acme/libs.git")

    url, warning = derive_pull_request_url(project, head="release/v1.0.0", base="master")

    assert warning is None
    assert url == "https://github.com/acme/libs/compare/master...release/v1.0.0?expand=1"


# ── a merged release PR without its tag ─────────────────────────────────────


def _merge_release_pr(project: Path) -> None:
    """Run the PR mode, merge the branch (fast-forward) and publish the default branch, as a host would."""
    _git_out(project, "tag", "v0.3.1")
    _git_out(project, "push", "origin", "v0.3.1")
    (project / "barn" / "haybale-alpha" / "change.txt").write_text("a change worth releasing")
    _git_out(project, "add", "-A")
    _git_out(project, "commit", "-m", "feat: a change")
    _git_out(project, "push", "origin", "HEAD")
    _pr_run(project)
    _git_out(project, "merge", "--ff-only", "release/v0.3.2")
    _git_out(project, "push", "origin", "HEAD")


def test_status_reports_a_merged_release_without_its_tag(project: Path, capsys) -> None:
    from haywire_studio.packaging.share_cli import run_share_cli

    _merge_release_pr(project)
    capsys.readouterr()

    assert run_share_cli(repo_root=project, bump=None, message=None, status=True) == 20
    out = capsys.readouterr().out
    assert "STATE: RELEASE_MERGED" in out
    assert "NEXT: uv run --frozen haywire share --resume" in out


def test_resume_tags_the_merged_release_and_pushes_only_the_tag(project: Path, capsys) -> None:
    from haywire_studio.packaging.share_cli import run_share_cli

    _merge_release_pr(project)
    tip = _git_out(project, "rev-parse", "HEAD")
    capsys.readouterr()

    assert run_share_cli(repo_root=project, bump=None, message=None, resume=True) == 0

    assert _git_out(project, "rev-parse", "v0.3.2^{commit}") == tip
    assert "refs/tags/v0.3.2" in _git_out(project, "ls-remote", "--tags", "origin")
    assert "STATE: RELEASED" in capsys.readouterr().out


def test_resume_refuses_when_head_is_not_on_origin(project: Path, capsys) -> None:
    from haywire_studio.packaging.share_cli import run_share_cli

    _merge_release_pr(project)
    (project / "extra.txt").write_text("local only")
    _git_out(project, "add", "-A")
    _git_out(project, "commit", "-m", "local")
    capsys.readouterr()

    assert run_share_cli(repo_root=project, bump=None, message=None, resume=True) != 0

    assert _tags(project) == ["v0.3.1"]


def test_a_hand_edited_version_is_not_a_merged_release(project: Path) -> None:
    from haywire.core.publishing.pipeline.steps import release_state

    _git_out(project, "tag", "v0.3.1")
    path = project / "barn" / "haybale-alpha" / "pyproject.toml"
    path.write_text(path.read_text().replace("0.3.1", "0.4.0"))
    _git_out(project, "commit", "-am", "bump by hand")

    assert release_state.detect(project).kind is not release_state.ReleaseKind.MERGED_UNTAGGED
