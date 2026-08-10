"""Lockstep version reading, arithmetic, and writing."""

import subprocess
from pathlib import Path

import pytest
import toml

from haywire.core.publishing.pipeline import VersionError
from haywire.core.publishing.pipeline.versions import (
    next_version,
    plan_versions,
    read_barn_versions,
    refresh_lockfile,
    write_barn_versions,
)

pytestmark = pytest.mark.unit


def _make_lib(repo: Path, name: str, version: str) -> Path:
    lib = repo / "barn" / name
    lib.mkdir(parents=True)
    (lib / "pyproject.toml").write_text(
        f'[project]\nname = "{name}"\nversion = "{version}"\ndescription = "d"\n'
    )
    return lib


@pytest.fixture
def repo_agreeing(tmp_path: Path) -> Path:
    """Two barn libraries at the same version, root workspace at 0.1.0."""
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / "pyproject.toml").write_text('[project]\nname = "ws"\nversion = "0.1.0"\n')
    _make_lib(repo, "haybale-alpha", "0.3.1")
    _make_lib(repo, "haybale-beta", "0.3.1")
    return repo


@pytest.fixture
def repo_disagreeing(tmp_path: Path) -> Path:
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / "pyproject.toml").write_text('[project]\nname = "ws"\nversion = "0.1.0"\n')
    _make_lib(repo, "haybale-alpha", "0.3.1")
    _make_lib(repo, "haybale-beta", "0.9.0")
    return repo


# ── next_version ─────────────────────────────────────────────────────────────


@pytest.mark.parametrize(
    ("spec", "current", "expected"),
    [
        ("patch", "0.0.4", "0.0.5"),
        ("minor", "0.0.4", "0.1.0"),
        ("major", "0.0.4", "1.0.0"),
        ("minor", "2.9.9", "2.10.0"),
        ("major", "9.9.9", "10.0.0"),
        ("3.4.5", "1.2.3", "3.4.5"),
        ("3.4.5", None, "3.4.5"),
    ],
)
def test_next_version(spec: str, current: str | None, expected: str) -> None:
    assert next_version(spec, current) == expected


@pytest.mark.parametrize("spec", ["major", "minor", "patch"])
def test_keyword_without_parsable_current_raises(spec: str) -> None:
    with pytest.raises(VersionError):
        next_version(spec, None)
    with pytest.raises(VersionError):
        next_version(spec, "not-a-version")


def test_malformed_explicit_version_raises() -> None:
    with pytest.raises(VersionError):
        next_version("1.2", None)
    with pytest.raises(VersionError):
        next_version("banana", None)


# ── read_barn_versions ───────────────────────────────────────────────────────


def test_read_barn_versions_excludes_the_root_pyproject(repo_agreeing: Path) -> None:
    versions = read_barn_versions(repo_agreeing)
    assert [v.name for v in versions] == ["haybale-alpha", "haybale-beta"]
    assert all(v.lib_dir.parent.name == "barn" for v in versions)


def test_read_barn_versions_skips_dirs_without_pyproject(repo_agreeing: Path) -> None:
    (repo_agreeing / "barn" / "not-a-library").mkdir()
    assert len(read_barn_versions(repo_agreeing)) == 2


def test_read_barn_versions_reports_none_for_unversioned(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    lib = repo / "barn" / "haybale-x"
    lib.mkdir(parents=True)
    (lib / "pyproject.toml").write_text('[project]\nname = "haybale-x"\n')
    assert read_barn_versions(repo)[0].version is None


def test_read_barn_versions_reports_none_for_invalid_os_declaration(tmp_path: Path) -> None:
    """An invalid `os` value causes version to be None, just as if the manifest
    were malformed — the reader refuses to report a version it cannot vouch
    for."""
    repo = tmp_path / "repo"
    lib = repo / "barn" / "haybale-y"
    module = lib / "haybale_y"
    module.mkdir(parents=True)
    (module / "__init__.py").write_text("")
    (module / "haybale.toml").write_text('name = "haybale-y"\nid = "y"\nos = ["freebsd"]\n')
    (lib / "pyproject.toml").write_text('[project]\nname = "haybale-y"\nversion = "0.5.0"\n')
    assert read_barn_versions(repo)[0].version is None


# ── plan_versions ────────────────────────────────────────────────────────────


def test_plan_versions_offers_suggestions_when_all_agree(repo_agreeing: Path) -> None:
    plan = plan_versions(repo_agreeing)
    assert plan.versions_agree is True
    assert plan.common_version == "0.3.1"
    assert plan.suggestions == {"patch": "0.3.2", "minor": "0.4.0", "major": "1.0.0"}


def test_plan_versions_offers_no_suggestions_when_they_disagree(repo_disagreeing: Path) -> None:
    """A silent resolution would downgrade the higher-versioned sibling (ADR 0023)."""
    plan = plan_versions(repo_disagreeing)
    assert plan.versions_agree is False
    assert plan.common_version is None
    assert plan.suggestions == {}
    assert {v.version for v in plan.current} == {"0.3.1", "0.9.0"}


# ── write_barn_versions ──────────────────────────────────────────────────────


def test_write_barn_versions_writes_every_library(repo_disagreeing: Path) -> None:
    written = write_barn_versions(repo_disagreeing, "1.0.0")
    assert len(written) == 2
    for path in written:
        assert toml.loads(path.read_text())["project"]["version"] == "1.0.0"


def test_write_barn_versions_leaves_the_root_pyproject_untouched(repo_agreeing: Path) -> None:
    """The workspace root sits at a fixed version and depends on the library
    unversioned — nothing reads it, and bumping it is what the old
    bump_version() got wrong."""
    root = repo_agreeing / "pyproject.toml"
    before = root.read_text()
    written = write_barn_versions(repo_agreeing, "0.4.0")
    assert root not in written
    assert root.read_text() == before


def test_write_barn_versions_preserves_all_other_fields(repo_agreeing: Path) -> None:
    lib = repo_agreeing / "barn" / "haybale-alpha" / "pyproject.toml"
    write_barn_versions(repo_agreeing, "0.4.0")
    data = toml.loads(lib.read_text())
    assert data["project"]["name"] == "haybale-alpha"
    assert data["project"]["description"] == "d"


def test_write_barn_versions_returns_sorted_paths(repo_agreeing: Path) -> None:
    written = write_barn_versions(repo_agreeing, "0.4.0")
    assert written == sorted(written)


# ── refresh_lockfile ─────────────────────────────────────────────────────────


def test_refresh_lockfile_noop_without_a_lockfile(repo_agreeing: Path) -> None:
    refreshed, warning = refresh_lockfile(repo_agreeing)
    assert refreshed is False
    assert warning is None


def test_refresh_lockfile_warns_but_never_raises(repo_agreeing: Path, monkeypatch) -> None:
    """uv lock failing is a warning, not a blocker — matches bump_version's posture."""
    (repo_agreeing / "uv.lock").write_text("")

    def _fail(*_a, **_kw):
        return subprocess.CompletedProcess(["uv", "lock"], 1, "", "resolution impossible")

    monkeypatch.setattr(subprocess, "run", _fail)
    refreshed, warning = refresh_lockfile(repo_agreeing)
    assert refreshed is False
    assert warning == "uv lock failed (uv.lock left stale): resolution impossible"


def test_refresh_lockfile_reports_success(repo_agreeing: Path, monkeypatch) -> None:
    (repo_agreeing / "uv.lock").write_text("")

    def _ok(*_a, **_kw):
        return subprocess.CompletedProcess(["uv", "lock"], 0, "", "")

    monkeypatch.setattr(subprocess, "run", _ok)
    refreshed, warning = refresh_lockfile(repo_agreeing)
    assert refreshed is True
    assert warning is None


def test_refresh_lockfile_warns_when_uv_not_found(repo_agreeing: Path, monkeypatch) -> None:
    (repo_agreeing / "uv.lock").write_text("")

    def _boom(*_a, **_kw):
        raise FileNotFoundError("uv")

    monkeypatch.setattr(subprocess, "run", _boom)
    refreshed, warning = refresh_lockfile(repo_agreeing)
    assert refreshed is False
    assert warning == "uv not found on PATH — uv.lock left stale."


def test_refresh_lockfile_warns_on_timeout(repo_agreeing: Path, monkeypatch) -> None:
    (repo_agreeing / "uv.lock").write_text("")

    def _boom(*_a, **_kw):
        raise subprocess.TimeoutExpired(cmd="uv lock", timeout=300.0)

    monkeypatch.setattr(subprocess, "run", _boom)
    refreshed, warning = refresh_lockfile(repo_agreeing, timeout=300.0)
    assert refreshed is False
    assert warning == "uv lock timed out after 300s — uv.lock left stale."


def test_refresh_lockfile_warns_but_never_raises_on_permission_error(
    repo_agreeing: Path, monkeypatch
) -> None:
    """A sibling OSError (e.g. PermissionError on the uv binary) must not propagate —
    this is the gap fixed by routing through gitcmd's broad except OSError handling."""
    (repo_agreeing / "uv.lock").write_text("")

    def _boom(*_a, **_kw):
        raise PermissionError("uv")

    monkeypatch.setattr(subprocess, "run", _boom)
    refreshed, warning = refresh_lockfile(repo_agreeing)
    assert refreshed is False
    assert warning is not None
    assert "uv" in warning
