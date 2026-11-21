"""The T3 slot's doctor.py against a stand-in T3 home and checkout."""

import json
import sqlite3
import subprocess
import sys
from pathlib import Path

import pytest

pytestmark = pytest.mark.unit

ROOT = Path(__file__).resolve().parents[2]
DOCTOR = ROOT / "plugins" / "haywire-dev" / "orchestrators" / "t3" / "doctor.py"
T3_JSON = json.loads((ROOT / "t3.json").read_text())
SETUP, FINISH, STUDIO = T3_JSON["scripts"]


def _imported(script: dict, sid: str) -> dict:
    """``script`` as T3's import writes it: with an id, without ``async``."""
    return {"id": sid, **{k: v for k, v in script.items() if k != "async"}}


def _settings(scripts: list[dict] | None, **extra) -> dict:
    overrides: dict = {"other": {"defaultProjectScripts": [{"id": "x", "command": "make x"}]}}
    if scripts is not None:
        overrides["p1"] = {"defaultProjectScripts": scripts}
    settings = {
        "projectSettingsFolded": True,
        "storageCleanup": {"worktreeOnMerge": True},
        "branchNamingMode": "semantic",
        "idleCompaction": {"enabled": True},
        "projectSettingsOverrides": overrides,
    }
    return {**settings, **extra}


@pytest.fixture
def t3(tmp_path):
    """A checkout holding the repository's t3.json and a T3 home; ``write`` puts its settings file."""

    class T3:
        repo = tmp_path / "repo"
        home = tmp_path / "t3home"
        path = home / "userdata" / "settings.json"

        def write(self, settings: dict | str) -> None:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            self.path.write_text(
                settings if isinstance(settings, str) else json.dumps(settings, indent=2) + "\n"
            )

        def read(self) -> dict:
            return json.loads(self.path.read_text())

        def run(self, *args: str) -> subprocess.CompletedProcess:
            return subprocess.run(
                [sys.executable, str(DOCTOR), *args, "--repo", str(self.repo)],
                capture_output=True,
                text=True,
                env={"T3CODE_HOME": str(self.home), "PATH": "/usr/bin:/bin"},
                check=False,
            )

        def backups(self) -> list[Path]:
            return sorted(self.path.parent.glob("settings.json.*.bak"))

    T3.repo.mkdir()
    (T3.repo / "t3.json").write_text(json.dumps(T3_JSON))
    return T3()


def test_a_complete_setup_needs_nothing(t3):
    t3.write(_settings([{"id": "worktree-setup", **SETUP}, _imported(FINISH, "f"), _imported(STUDIO, "s")]))
    result = t3.run("--check")
    assert result.returncode == 0
    assert "complete" in result.stdout
    before = t3.path.read_text()
    assert "Nothing to fix" in t3.run("--fix").stdout
    assert t3.path.read_text() == before
    assert t3.backups() == []


def test_the_check_names_each_script_gap(t3):
    t3.write(_settings([_imported(SETUP, "worktree-setup"), _imported(FINISH, "f")]))
    result = t3.run("--check")
    assert result.returncode == 1
    assert "*Worktree setup* lacks `async: false`" in result.stdout
    assert "lacks the t3.json script *Haywire studio*" in result.stdout
    assert "*Finish merged task*" not in result.stdout


def test_the_fix_backs_up_and_changes_only_the_scripts(t3):
    t3.write(_settings([_imported(SETUP, "worktree-setup"), _imported(FINISH, "f")]))
    before = t3.read()
    result = t3.run("--fix")
    assert result.returncode == 0, result.stderr
    assert "fixed: *Worktree setup* lacks `async: false`" in result.stdout
    (backup,) = t3.backups()
    assert json.loads(backup.read_text()) == before
    after = t3.read()
    scripts = after["projectSettingsOverrides"]["p1"]["defaultProjectScripts"]
    assert scripts[0] == {"id": "worktree-setup", **SETUP}
    assert scripts[1] == _imported(FINISH, "f")
    assert scripts[2] == {"id": "haywire-studio", **STUDIO}
    after["projectSettingsOverrides"]["p1"] = before["projectSettingsOverrides"]["p1"]
    assert after == before


def test_the_fix_is_idempotent(t3):
    t3.write(_settings([_imported(SETUP, "worktree-setup")]))
    t3.run("--fix")
    fixed = t3.path.read_text()
    second = t3.run("--fix")
    assert "Nothing to fix" in second.stdout
    assert t3.path.read_text() == fixed
    assert len(t3.backups()) == 1
    assert t3.run("--check").returncode == 0


def test_a_changed_command_is_brought_in_line_with_t3_json(t3):
    t3.write(_settings([{"id": "worktree-setup", **SETUP}, {**_imported(FINISH, "f"), "command": "old"}]))
    assert "*Finish merged task* differs from t3.json in `command`" in t3.run("--check").stdout
    t3.run("--fix")
    assert (
        t3.read()["projectSettingsOverrides"]["p1"]["defaultProjectScripts"][1]["command"]
        == FINISH["command"]
    )


def test_cleanup_and_naming_are_left_to_the_user(t3):
    t3.write(_settings([{"id": "worktree-setup", **SETUP}], branchNamingMode="static", storageCleanup={}))
    result = t3.run("--fix")
    assert "Still to do by hand" in result.stdout
    assert "Branch naming → semantic" in result.stdout
    assert "Delete merged worktrees" in result.stdout
    after = t3.read()
    assert after["branchNamingMode"] == "static"
    assert after["storageCleanup"] == {}


@pytest.mark.parametrize(
    "settings",
    [
        "{not json",
        "[]",
        _settings([_imported(SETUP, "worktree-setup")], projectSettingsFolded=False),
        _settings([_imported(SETUP, "worktree-setup")], projectSettingsOverrides=[]),
    ],
)
def test_an_unknown_shape_is_left_untouched(t3, settings):
    t3.write(settings)
    before = t3.path.read_text()
    result = t3.run("--fix")
    assert t3.path.read_text() == before
    assert t3.backups() == []
    assert "orchestrators/t3.md#setup" in result.stdout


def test_scripts_not_imported_point_to_the_import(t3):
    t3.write(_settings(None))
    result = t3.run("--check")
    assert "the t3.json scripts are not imported" in result.stdout
    assert "Import from t3.json" in result.stdout
    t3.run("--fix")
    assert t3.backups() == []


def test_two_projects_alike_are_not_guessed(t3):
    settings = _settings([_imported(SETUP, "a")])
    settings["projectSettingsOverrides"]["p2"] = {"defaultProjectScripts": [_imported(SETUP, "b")]}
    t3.write(settings)
    assert "could not tell which T3 project" in t3.run("--check").stdout
    t3.run("--fix")
    assert t3.backups() == []


def _state(t3, root: Path, pid: str = "p1") -> None:
    db = t3.home / "userdata" / "statev2.sqlite"
    with sqlite3.connect(db) as con:
        con.execute(
            "CREATE TABLE projection_projects (project_id TEXT, workspace_root TEXT, deleted_at TEXT)"
        )
        con.execute("INSERT INTO projection_projects VALUES (?, ?, NULL)", (pid, str(root)))
    con.close()


def test_the_project_is_found_by_its_folder_in_t3_state(t3):
    settings = _settings([_imported(SETUP, "a")])
    settings["projectSettingsOverrides"]["p2"] = {"defaultProjectScripts": [_imported(SETUP, "b")]}
    t3.write(settings)
    _state(t3, t3.repo, "p2")
    t3.run("--fix")
    after = t3.read()["projectSettingsOverrides"]
    assert after["p2"]["defaultProjectScripts"][0] == {"id": "b", **SETUP}
    assert after["p1"]["defaultProjectScripts"] == [_imported(SETUP, "a")]


def test_a_folder_t3_does_not_know_is_named(t3, tmp_path):
    t3.write(_settings([_imported(SETUP, "worktree-setup")]))
    _state(t3, tmp_path / "elsewhere")
    assert "is not a T3 project" in t3.run("--check").stdout


def test_without_a_t3_json_only_the_settings_are_checked(t3):
    (t3.repo / "t3.json").unlink()
    t3.write(_settings(None, branchNamingMode="static"))
    result = t3.run("--check")
    assert "t3.json scripts" not in result.stdout
    assert "Branch naming" in result.stdout
