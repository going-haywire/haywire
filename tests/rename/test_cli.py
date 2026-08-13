"""Exit codes, dry-run safety, and the two confirmation gates."""

from __future__ import annotations

import json
from unittest.mock import patch

import pytest

from tests.rename.test_planner import _workspace  # noqa: F401


@pytest.mark.unit
def test_dry_run_changes_nothing_and_exits_zero(tmp_path, capsys):
    from haywire_studio.packaging.rename import run_rename_cli

    ws = _workspace(tmp_path)
    code = run_rename_cli(old_library="hay-src", new_name="hay-dst", workspace_root=ws, apply=False)

    assert code == 0
    assert (ws / "barn" / "hay-src").is_dir()
    data = json.loads((ws / "flows" / "g.haywire").read_text())
    assert data["nodes"]["n"]["registry_key"] == "hay-src:node:Add"
    assert "--apply" in capsys.readouterr().out


@pytest.mark.unit
def test_dry_run_of_invalid_rename_exits_nonzero(tmp_path):
    """The old code exited 0 on a bogus dry run; validation now runs first."""
    from haywire_studio.packaging.rename import run_rename_cli

    ws = _workspace(tmp_path)
    code = run_rename_cli(old_library="hay-nonexistent", new_name="hay-dst", workspace_root=ws, apply=False)
    assert code != 0


@pytest.mark.unit
def test_apply_declined_at_confirm_changes_nothing(tmp_path):
    from haywire_studio.packaging.rename import run_rename_cli

    ws = _workspace(tmp_path)
    with patch("builtins.input", return_value="n"):
        code = run_rename_cli(old_library="hay-src", new_name="hay-dst", workspace_root=ws, apply=True)

    assert code != 0
    assert (ws / "barn" / "hay-src").is_dir()


@pytest.mark.unit
def test_unconventional_name_asks_twice(tmp_path):
    """One prompt for the prefix, one to proceed."""
    from haywire_studio.packaging.rename import run_rename_cli

    ws = _workspace(tmp_path)
    with patch("builtins.input", side_effect=["y", "y"]) as prompt:
        with patch("haywire_studio.packaging.rename.execute.subprocess.run") as run:
            run.return_value.returncode = 0
            run.return_value.stdout = b""
            run_rename_cli(old_library="hay-src", new_name="forecast", workspace_root=ws, apply=True)

    assert prompt.call_count == 2


@pytest.mark.unit
def test_assume_yes_skips_prompts(tmp_path):
    from haywire_studio.packaging.rename import run_rename_cli

    ws = _workspace(tmp_path)
    with patch("builtins.input", side_effect=AssertionError("must not prompt")):
        with patch("haywire_studio.packaging.rename.execute.subprocess.run") as run:
            run.return_value.returncode = 0
            run.return_value.stdout = b""
            code = run_rename_cli(
                old_library="hay-src",
                new_name="hay-dst",
                workspace_root=ws,
                apply=True,
                assume_yes=True,
            )

    assert code == 0
    assert (ws / "barn" / "hay-dst").is_dir()


@pytest.mark.unit
def test_blocked_apply_exits_nonzero_without_prompting(tmp_path):
    from haywire_studio.packaging.rename import run_rename_cli

    ws = _workspace(tmp_path)
    (ws / "dirt.txt").write_text("x")

    with patch("builtins.input", side_effect=AssertionError("must not prompt")):
        code = run_rename_cli(old_library="hay-src", new_name="hay-dst", workspace_root=ws, apply=True)
    assert code != 0


@pytest.mark.unit
def test_success_suggests_verify(tmp_path, capsys):
    from haywire_studio.packaging.rename import run_rename_cli

    ws = _workspace(tmp_path)
    with patch("haywire_studio.packaging.rename.execute.subprocess.run") as run:
        run.return_value.returncode = 0
        run.return_value.stdout = b""
        run_rename_cli(
            old_library="hay-src",
            new_name="hay-dst",
            workspace_root=ws,
            apply=True,
            assume_yes=True,
        )

    assert "haywire verify" in capsys.readouterr().out
