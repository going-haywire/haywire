"""Five fail-fast phases; identity fields only."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

import pytest

from tests.rename.test_planner import _workspace  # noqa: F401


def _run(ws: Path, old: str, new: str):
    from haywire_studio.packaging.rename.execute import execute_plan
    from haywire_studio.packaging.rename.planner import plan_rename

    plan, _ = plan_rename(old, new, ws)
    assert plan.ok, plan.blockers
    with patch("haywire_studio.packaging.rename.execute.subprocess.run") as run:
        run.return_value.returncode = 0
        run.return_value.stdout = b""
        return execute_plan(plan, sink=lambda *_: None)


@pytest.mark.unit
def test_renames_both_directories(tmp_path):
    ws = _workspace(tmp_path)
    ok, _ = _run(ws, "hay-src", "hay-dst")

    assert ok
    assert (ws / "barn" / "hay-dst" / "hay_dst").is_dir()
    assert not (ws / "barn" / "hay-src").exists()


@pytest.mark.unit
def test_preserves_descriptive_metadata(tmp_path):
    """Rename changes identity, not description."""
    ws = _workspace(tmp_path)
    _run(ws, "hay-src", "hay-dst")

    toml = (ws / "barn" / "hay-dst" / "hay_dst" / "haybale.toml").read_text()
    assert 'name = "hay-dst"' in toml
    assert 'label = "Src"' in toml
    assert 'tags = ["a"]' in toml


@pytest.mark.unit
def test_patches_graph_keys_outside_graphs_folder(tmp_path):
    ws = _workspace(tmp_path)
    _run(ws, "hay-src", "hay-dst")

    data = json.loads((ws / "flows" / "g.haywire").read_text())
    node = data["nodes"]["n"]
    assert node["registry_key"] == "hay-dst:node:Add"
    assert node["node_data"]["ports"]["a"]["kwargs"]["widget_key"] == "hay-dst:widget:W"


@pytest.mark.unit
def test_writes_no_bak_files(tmp_path):
    """Git is the rollback; .bak files would trip the next clean-tree gate."""
    ws = _workspace(tmp_path)
    _run(ws, "hay-src", "hay-dst")

    assert list(ws.glob("**/*.bak")) == []


@pytest.mark.unit
def test_rewrites_imports_and_key_literals(tmp_path):
    ws = _workspace(tmp_path)
    _run(ws, "hay-src", "hay-dst")

    text = (ws / "barn" / "hay-dst" / "hay_dst" / "use.py").read_text()
    assert "from hay_dst.types import X" in text
    assert '"hay-dst:widget:Thing"' in text


@pytest.mark.unit
def test_updates_project_pyproject(tmp_path):
    ws = _workspace(tmp_path)
    _run(ws, "hay-src", "hay-dst")

    text = (ws / "pyproject.toml").read_text()
    assert "hay-dst" in text
    assert '"hay-src"' not in text


@pytest.mark.unit
def test_uv_sync_failure_reports_source_rename_succeeded(tmp_path):
    """Phase 5 runs last, so its failure is an env problem, not a rename one."""
    from haywire_studio.packaging.rename.execute import execute_plan
    from haywire_studio.packaging.rename.planner import plan_rename

    ws = _workspace(tmp_path)
    plan, _ = plan_rename("hay-src", "hay-dst", ws)

    with patch("haywire_studio.packaging.rename.execute.subprocess.run") as run:
        run.return_value.returncode = 1
        run.return_value.stdout = b"resolution failed"
        ok, message = execute_plan(plan, sink=lambda *_: None)

    assert not ok
    assert "uv sync" in message
    assert "git checkout" not in message  # do not discard good work


@pytest.mark.unit
def test_malformed_toml_returns_failure_not_exception(tmp_path):
    """A malformed haybale.toml must fail cleanly, not raise out of execute_plan."""
    from haywire_studio.packaging.rename.execute import execute_plan
    from haywire_studio.packaging.rename.planner import plan_rename

    ws = _workspace(tmp_path)
    plan, _ = plan_rename("hay-src", "hay-dst", ws)
    assert plan.ok, plan.blockers

    # Phase 2 edits the library's own haybale.toml first (already renamed by
    # phase 1's directory move) — corrupt it so read_toml raises TomlDecodeError.
    haybale_toml = ws / "barn" / "hay-src" / "hay_src" / "haybale.toml"
    haybale_toml.write_text("not [ valid toml")

    with patch("haywire_studio.packaging.rename.execute.subprocess.run") as run:
        run.return_value.returncode = 0
        run.return_value.stdout = b""
        ok, message = execute_plan(plan, sink=lambda *_: None)

    assert not ok
    assert "library metadata" in message
    assert "Traceback" not in message


@pytest.mark.unit
def test_missing_uv_binary_returns_failure_not_exception(tmp_path):
    """If `uv` itself can't be invoked, phase 5 must fail cleanly, not raise."""
    from haywire_studio.packaging.rename.execute import execute_plan
    from haywire_studio.packaging.rename.planner import plan_rename

    ws = _workspace(tmp_path)
    plan, _ = plan_rename("hay-src", "hay-dst", ws)

    with patch(
        "haywire_studio.packaging.rename.execute.subprocess.run",
        side_effect=FileNotFoundError("uv"),
    ):
        ok, message = execute_plan(plan, sink=lambda *_: None)

    assert not ok
    assert "completed" in message
    assert "hay-dst" in message
    assert "git checkout" not in message  # do not discard good work
