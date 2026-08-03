"""The pre-write conflict check.

`uv sync --dry-run` output is noisy with PRE-EXISTING venv drift — a real run
reported "Would uninstall 33 packages" purely because the venv held packages
the lockfile didn't. So the check diffs against a baseline run and reports only
what OUR pin changes.
"""

from __future__ import annotations

import textwrap
from pathlib import Path
from unittest.mock import patch

import pytest

pytestmark = pytest.mark.unit


def _project(tmp_path: Path) -> Path:
    (tmp_path / "pyproject.toml").write_text(
        textwrap.dedent("""
            [project]
            name = "my-project"
            version = "0.1.0"
            dependencies = ["haywire-studio~=0.0.34"]
        """).lstrip()
    )
    return tmp_path


def test_preexisting_drift_is_not_reported_as_ours():
    from haywire.core.update.conflict import diff_resolutions

    baseline = " - haybale-visiongraph==0.0.5\n - opencv-python==4.9.0\n"
    proposed = " - haybale-visiongraph==0.0.5\n - opencv-python==4.9.0\n + haywire-core==0.0.35\n"

    assert diff_resolutions(baseline, proposed) == ["+ haywire-core==0.0.35"]


def test_identical_resolutions_diff_to_nothing():
    from haywire.core.update.conflict import diff_resolutions

    same = " - haybale-visiongraph==0.0.5\n"
    assert diff_resolutions(same, same) == []


def test_unsatisfiable_pin_is_reported_as_a_conflict(tmp_path):
    from haywire.core.update.conflict import check_pin_conflict

    root = _project(tmp_path)
    calls: list[str] = []

    def fake_sync(cwd):
        calls.append("run")
        if len(calls) == 1:
            return True, " - nothing\n"
        return False, "error: no solution found: haybale-foo requires haywire-core<0.0.35"

    with patch("haywire.core.update.conflict._uv_sync_dry_run", side_effect=fake_sync):
        result = check_pin_conflict(root, "0.0.35")

    assert not result.ok
    assert "no solution found" in result.message


def test_a_clean_resolution_never_promises_a_successful_launch(tmp_path):
    """Resolution is not installation: the real sync happens later inside
    `uv run`, unsupervised, after all our UI is gone."""
    from haywire.core.update.conflict import check_pin_conflict

    root = _project(tmp_path)

    with patch("haywire.core.update.conflict._uv_sync_dry_run", return_value=(True, " - x==1\n")):
        result = check_pin_conflict(root, "0.0.35")

    assert result.ok
    assert "No conflicts found" in result.message
    assert "will succeed" not in result.message


def test_the_original_pyproject_is_restored_after_the_check(tmp_path):
    """Write-resolve-restore: a temp-dir copy would resolve DIFFERENTLY —
    [tool.uv.sources] carries {workspace = true} and absolute dev paths — so
    the check runs against the real workspace and must put it back."""
    from haywire.core.update.conflict import check_pin_conflict

    root = _project(tmp_path)
    before = (root / "pyproject.toml").read_text()

    with patch("haywire.core.update.conflict._uv_sync_dry_run", return_value=(True, "")):
        check_pin_conflict(root, "0.0.35")

    assert (root / "pyproject.toml").read_text() == before


def test_the_original_is_restored_even_when_the_resolve_raises(tmp_path):
    from haywire.core.update.conflict import check_pin_conflict

    root = _project(tmp_path)
    before = (root / "pyproject.toml").read_text()

    with patch("haywire.core.update.conflict._uv_sync_dry_run", side_effect=OSError("uv is gone")):
        with pytest.raises(OSError, match="uv is gone"):
            check_pin_conflict(root, "0.0.35")

    assert (root / "pyproject.toml").read_text() == before
