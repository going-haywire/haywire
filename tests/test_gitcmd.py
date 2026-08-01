"""Tests for the hardened git subprocess helpers."""

import subprocess
from pathlib import Path

import pytest

from haywire_studio.packaging.share.git import (
    HARDENED_ENV,
    GitResult,
    git,
    git_remote,
    run,
)

pytestmark = pytest.mark.unit


@pytest.fixture
def git_repo(tmp_path: Path) -> Path:
    """A real, initialised git repo with one commit."""
    repo = tmp_path / "repo"
    repo.mkdir()
    subprocess.run(["git", "init"], cwd=repo, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.email", "t@t.test"], cwd=repo, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.name", "T"], cwd=repo, check=True, capture_output=True)
    (repo / "a.txt").write_text("a\n")
    subprocess.run(["git", "add", "a.txt"], cwd=repo, check=True, capture_output=True)
    subprocess.run(["git", "commit", "-m", "init"], cwd=repo, check=True, capture_output=True)
    return repo


def test_git_success_returns_ok_and_stdout(git_repo: Path) -> None:
    result = git(["rev-parse", "--abbrev-ref", "HEAD"], cwd=git_repo)
    assert result.ok is True
    assert result.returncode == 0
    assert result.stdout.strip() in {"main", "master"}
    assert result.timed_out is False


def test_git_failure_returns_not_ok(git_repo: Path) -> None:
    result = git(["rev-parse", "--verify", "refs/tags/v9.9.9"], cwd=git_repo)
    assert result.ok is False
    assert result.returncode != 0


def test_git_missing_binary_is_reported_not_raised(tmp_path: Path, monkeypatch) -> None:
    """A missing git binary must come back as a GitResult, never a FileNotFoundError."""

    def _boom(*_a, **_kw):
        raise FileNotFoundError("git")

    monkeypatch.setattr(subprocess, "run", _boom)
    result = git(["--version"], cwd=tmp_path)
    assert result.ok is False
    assert "git" in result.stderr


def test_git_timeout_is_reported_not_raised(tmp_path: Path, monkeypatch) -> None:
    def _boom(*_a, **_kw):
        raise subprocess.TimeoutExpired(cmd="git", timeout=1.0)

    monkeypatch.setattr(subprocess, "run", _boom)
    result = git(["--version"], cwd=tmp_path, timeout=1.0)
    assert result.ok is False
    assert result.timed_out is True


def test_hardened_env_disables_every_prompt_path() -> None:
    assert HARDENED_ENV["GIT_TERMINAL_PROMPT"] == "0"
    assert HARDENED_ENV["GIT_ASKPASS"] == ""
    assert HARDENED_ENV["SSH_ASKPASS"] == ""
    assert HARDENED_ENV["GIT_CONFIG_NOSYSTEM"] == "1"


def test_git_remote_passes_hardened_env(tmp_path: Path, monkeypatch) -> None:
    seen: dict = {}

    def _capture(cmd, **kwargs):
        seen.update(kwargs)
        return subprocess.CompletedProcess(cmd, 0, "", "")

    monkeypatch.setattr(subprocess, "run", _capture)
    git_remote(["ls-remote", "origin"], cwd=tmp_path)
    env = seen["env"]
    assert env["GIT_TERMINAL_PROMPT"] == "0"
    assert env["GIT_ASKPASS"] == ""
    # The parent environment is preserved (PATH must survive or git isn't findable).
    assert "PATH" in env


def test_local_git_does_not_pass_hardened_env(tmp_path: Path, monkeypatch) -> None:
    """Local calls run with the ambient env — no need to fight the user's config."""
    seen: dict = {}

    def _capture(cmd, **kwargs):
        seen.update(kwargs)
        return subprocess.CompletedProcess(cmd, 0, "", "")

    monkeypatch.setattr(subprocess, "run", _capture)
    git(["status"], cwd=tmp_path)
    assert seen.get("env") is None


def test_git_result_is_frozen() -> None:
    result = GitResult(ok=True, stdout="", stderr="", returncode=0, timed_out=False)
    with pytest.raises(Exception):
        result.ok = False  # type: ignore[misc]


# ── run (generic, non-git) ───────────────────────────────────────────────────


def test_run_success_returns_ok_and_stdout(tmp_path: Path) -> None:
    result = run(["echo", "hello"], cwd=tmp_path, timeout=5.0)
    assert result.ok is True
    assert result.returncode == 0
    assert "hello" in result.stdout
    assert result.timed_out is False


def test_run_failure_returns_not_ok(tmp_path: Path) -> None:
    result = run(["python3", "-c", "import sys; sys.exit(3)"], cwd=tmp_path, timeout=5.0)
    assert result.ok is False
    assert result.returncode == 3


def test_run_missing_binary_is_reported_not_raised(tmp_path: Path, monkeypatch) -> None:
    """A missing binary must come back as a GitResult, never a FileNotFoundError."""

    def _boom(*_a, **_kw):
        raise FileNotFoundError("uv")

    monkeypatch.setattr(subprocess, "run", _boom)
    result = run(["uv", "lock"], cwd=tmp_path, timeout=5.0)
    assert result.ok is False
    assert result.returncode == 127
    assert "uv" in result.stderr


def test_run_timeout_is_reported_not_raised(tmp_path: Path, monkeypatch) -> None:
    def _boom(*_a, **_kw):
        raise subprocess.TimeoutExpired(cmd="uv lock", timeout=1.0)

    monkeypatch.setattr(subprocess, "run", _boom)
    result = run(["uv", "lock"], cwd=tmp_path, timeout=1.0)
    assert result.ok is False
    assert result.timed_out is True


def test_run_does_not_pass_hardened_env(tmp_path: Path, monkeypatch) -> None:
    """Like git(), run() is a purely local call — ambient env, no prompt-disabling overlay."""
    seen: dict = {}

    def _capture(cmd, **kwargs):
        seen.update(kwargs)
        return subprocess.CompletedProcess(cmd, 0, "", "")

    monkeypatch.setattr(subprocess, "run", _capture)
    run(["uv", "lock"], cwd=tmp_path, timeout=5.0)
    assert seen.get("env") is None
