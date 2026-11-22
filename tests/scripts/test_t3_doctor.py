"""The T3 slot's doctor.py against a stand-in T3 home and checkout."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

pytestmark = pytest.mark.unit

ROOT = Path(__file__).resolve().parents[2]
DOCTOR = ROOT / "plugins" / "haywire-dev" / "orchestrators" / "t3" / "doctor.py"
SETUP, FINISH, STUDIO = json.loads((ROOT / "t3.json").read_text())["scripts"]
IMPORTED_SETUP = {"id": "worktree-setup", **{k: v for k, v in SETUP.items() if k != "async"}}


def _settings(*scripts: dict, **extra) -> dict:
    return {
        "storageCleanup": {"worktreeOnMerge": True},
        "branchNamingMode": "semantic",
        "projectSettingsOverrides": {
            "other": {"defaultProjectScripts": [{"id": "x", "command": "make x"}]},
            "p1": {"defaultProjectScripts": list(scripts)},
        },
        **extra,
    }


@pytest.fixture
def t3(tmp_path):
    """A checkout holding the repository's t3.json, and T3's settings file in a T3 home."""
    repo, path = tmp_path / "repo", tmp_path / "t3home" / "userdata" / "settings.json"
    repo.mkdir()
    (repo / "t3.json").write_text((ROOT / "t3.json").read_text())
    path.parent.mkdir(parents=True)

    def run(*args: str, settings: dict | str | None = None) -> str:
        if settings is not None:
            path.write_text(settings if isinstance(settings, str) else json.dumps(settings, indent=2) + "\n")
        env = {"T3CODE_HOME": str(tmp_path / "t3home"), "PATH": "/usr/bin:/bin"}
        command = [sys.executable, str(DOCTOR), *args, "--repo", str(repo)]
        return subprocess.run(command, capture_output=True, text=True, env=env, check=False).stdout

    run.path = path  # type: ignore[attr-defined]
    return run


def _backups(path: Path) -> list[Path]:
    return list(path.parent.glob("settings.json.*.bak"))


def test_the_fix_backs_up_and_adds_only_the_missing_scripts_and_async(t3):
    before = _settings(IMPORTED_SETUP, {"id": "f", **FINISH})
    assert "lacks the t3.json script *Haywire studio*" in t3("--check", settings=before)
    assert "Fixed:" in t3("--fix")
    (backup,) = _backups(t3.path)
    assert json.loads(backup.read_text()) == before
    after = json.loads(t3.path.read_text())
    assert after["projectSettingsOverrides"]["p1"]["defaultProjectScripts"] == [
        {**IMPORTED_SETUP, "async": False},
        {"id": "f", **FINISH},
        {"id": "haywire-studio", **STUDIO},
    ]
    after["projectSettingsOverrides"]["p1"] = before["projectSettingsOverrides"]["p1"]
    assert after == before


def test_the_fix_is_idempotent(t3):
    t3("--fix", settings=_settings(IMPORTED_SETUP))
    fixed = t3.path.read_text()
    assert "Nothing to fix" in t3("--fix")
    assert t3.path.read_text() == fixed
    assert len(_backups(t3.path)) == 1


def test_cleanup_and_naming_are_left_to_the_user(t3):
    out = t3(
        "--fix", settings=_settings(SETUP, FINISH, STUDIO, branchNamingMode="static", storageCleanup={})
    )
    assert "Still to do by hand" in out
    assert "Branch naming" in out
    assert "Delete merged worktrees" in out
    assert _backups(t3.path) == []


def test_another_project_without_scripts_is_skipped(t3):
    settings = _settings(IMPORTED_SETUP)
    settings["projectSettingsOverrides"]["model-only"] = {"defaultModel": "x"}
    out = t3("--check", settings=settings)
    assert "*Worktree setup* lacks `async: false`" in out
    assert "could not check" not in out


def test_scripts_not_imported_point_to_the_import(t3):
    out = t3("--fix", settings=_settings())
    assert "the t3.json scripts are not imported" in out
    assert _backups(t3.path) == []


@pytest.mark.parametrize("settings", ["{not json", "[]", {"projectSettingsOverrides": []}])
def test_an_unknown_shape_is_left_untouched(t3, settings):
    out = t3("--fix", settings=settings)
    assert "could not check the T3 settings, see" in out
    assert _backups(t3.path) == []
