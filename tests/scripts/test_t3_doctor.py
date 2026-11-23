"""The T3 slot's doctor.py against a stand-in T3 home."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

pytestmark = pytest.mark.unit

ROOT = Path(__file__).resolve().parents[2]
DOCTOR = ROOT / "dev" / "orchestrators" / "t3" / "doctor.py"
COMPLETE = {"storageCleanup": {"worktreeOnMerge": True}, "branchNamingMode": "semantic"}


@pytest.fixture
def t3(tmp_path):
    """The doctor's ``--check`` against T3's settings file in a T3 home."""
    path = tmp_path / "t3home" / "userdata" / "settings.json"
    path.parent.mkdir(parents=True)

    def run(settings: dict | str) -> subprocess.CompletedProcess:
        text = settings if isinstance(settings, str) else json.dumps(settings, indent=2) + "\n"
        path.write_text(text)
        env = {"T3CODE_HOME": str(tmp_path / "t3home"), "PATH": "/usr/bin:/bin"}
        command = [sys.executable, str(DOCTOR), "--check", "--repo", str(tmp_path)]
        result = subprocess.run(command, capture_output=True, text=True, env=env, check=False)
        assert path.read_text() == text
        return result

    return run


def test_a_complete_setup_lacks_nothing(t3):
    result = t3(COMPLETE)
    assert result.stdout.strip() == "Nothing is missing in the T3 setup."
    assert result.returncode == 0


def test_project_scripts_are_not_checked(t3):
    assert t3({**COMPLETE, "projectSettingsOverrides": {}}).returncode == 0


@pytest.mark.parametrize(
    ("change", "named"),
    [
        ({"storageCleanup": {}}, "Delete merged worktrees"),
        ({"storageCleanup": {"worktreeOnMerge": True, "worktreeKeepWhen": "never"}}, "Uncommitted changes"),
        ({"branchNamingMode": "static"}, "Branch naming"),
    ],
)
def test_each_wrong_setting_is_named(t3, change, named):
    result = t3({**COMPLETE, **change})
    assert named in result.stdout
    assert result.returncode == 1


@pytest.mark.parametrize("settings", ["{not json", "[]"])
def test_an_unknown_shape_is_reported_and_left_untouched(t3, settings):
    assert "could not check the T3 settings, see" in t3(settings).stdout
