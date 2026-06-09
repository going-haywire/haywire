"""Tests for npm-style `haywire share --bump major|minor|patch` version arithmetic."""

import subprocess
from pathlib import Path

import pytest
import toml

from haywire_studio import share
from haywire_studio.share import _compute_next_version, bump_version


@pytest.mark.parametrize(
    ("spec", "current", "expected"),
    [
        ("patch", "0.0.4", "0.0.5"),
        ("minor", "0.0.4", "0.1.0"),
        ("major", "0.0.4", "1.0.0"),
        ("patch", "1.2.3", "1.2.4"),
        ("minor", "1.2.3", "1.3.0"),
        ("major", "1.2.3", "2.0.0"),
        # minor/major reset lower segments to zero.
        ("minor", "2.9.9", "2.10.0"),
        ("major", "9.9.9", "10.0.0"),
        # Explicit versions pass straight through unchanged.
        ("3.4.5", "1.2.3", "3.4.5"),
        ("3.4.5", None, "3.4.5"),
    ],
)
def test_compute_next_version(spec: str, current: str | None, expected: str) -> None:
    assert _compute_next_version(spec, current) == expected


@pytest.mark.parametrize("spec", ["major", "minor", "patch"])
def test_keyword_needs_current_version(spec: str) -> None:
    """A keyword bump with no parsable current version returns None (caller errors)."""
    assert _compute_next_version(spec, None) is None
    assert _compute_next_version(spec, "not-a-version") is None


@pytest.fixture
def repo_at_version(tmp_path: Path) -> Path:
    """A minimal repo with a root + one barn library, both at 0.1.2."""
    repo = tmp_path / "repo"
    (repo / ".git").mkdir(parents=True)  # marks the git root for share's detector
    (repo / "pyproject.toml").write_text('[project]\nname = "workspace"\nversion = "0.1.2"\n')
    lib = repo / "barn" / "haybale-alpha"
    lib.mkdir(parents=True)
    (lib / "pyproject.toml").write_text('[project]\nname = "haybale-alpha"\nversion = "0.1.2"\n')
    return repo


def _version_of(pyproject: Path) -> str:
    return str(toml.loads(pyproject.read_text())["project"]["version"])


def test_bump_keyword_writes_resolved_version(repo_at_version: Path) -> None:
    """`--bump minor` on 0.1.2 rewrites every pyproject to 0.2.0."""
    bump_version("minor", repo_at_version)

    assert _version_of(repo_at_version / "pyproject.toml") == "0.2.0"
    assert _version_of(repo_at_version / "barn" / "haybale-alpha" / "pyproject.toml") == "0.2.0"


def test_bump_explicit_still_works(repo_at_version: Path) -> None:
    """An explicit X.Y.Z is written verbatim, keeping the pre-existing behavior."""
    bump_version("5.6.7", repo_at_version)

    assert _version_of(repo_at_version / "pyproject.toml") == "5.6.7"
    assert _version_of(repo_at_version / "barn" / "haybale-alpha" / "pyproject.toml") == "5.6.7"


def _spy_subprocess(monkeypatch: pytest.MonkeyPatch) -> list[list[str]]:
    """Record every argv passed to subprocess.run; intercept `uv lock` (no real
    resolve) but let git commands run normally against the temp repo."""
    calls: list[list[str]] = []
    real_run = subprocess.run

    def fake_run(argv, *args, **kwargs):  # type: ignore[no-untyped-def]
        calls.append(list(argv))
        if argv[:2] == ["uv", "lock"]:
            return subprocess.CompletedProcess(argv, 0, stdout="", stderr="")
        return real_run(argv, *args, **kwargs)

    monkeypatch.setattr(share.subprocess, "run", fake_run)
    return calls


def test_bump_runs_uv_lock_and_stages_it_when_lockfile_present(
    repo_at_version: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """With a uv.lock present, the bump runs `uv lock` and stages the lockfile."""
    (repo_at_version / "uv.lock").write_text("# placeholder lock\n")
    calls = _spy_subprocess(monkeypatch)

    bump_version("patch", repo_at_version)

    assert ["uv", "lock"] in calls, "expected `uv lock` to run when a lockfile exists"
    staged_lock = any(c[:2] == ["git", "add"] and c[-1].endswith("uv.lock") for c in calls)
    assert staged_lock, "expected uv.lock to be staged into the bump commit"


def test_bump_skips_uv_lock_when_no_lockfile(repo_at_version: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """No uv.lock → no `uv lock` call (the step is guarded on the file's presence)."""
    assert not (repo_at_version / "uv.lock").exists()
    calls = _spy_subprocess(monkeypatch)

    bump_version("patch", repo_at_version)

    assert ["uv", "lock"] not in calls
