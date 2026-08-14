"""plan_rename composes every check into one read-only plan."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest


def _workspace(tmp_path: Path) -> Path:
    """A clean git workspace: one library, one graph outside graphs/."""
    lib = tmp_path / "barn" / "hay-src" / "hay_src"
    lib.mkdir(parents=True)
    (lib / "haybale.toml").write_text('name = "hay-src"\nversion = "0.1.0"\nlabel = "Src"\ntags = ["a"]\n')
    (lib / "__init__.py").write_text("")
    (lib / "use.py").write_text('from hay_src.types import X\nW = "hay-src:widget:Thing"\n')
    (tmp_path / "barn" / "hay-src" / "pyproject.toml").write_text(
        '[project]\nname = "hay-src"\n\n'
        '[project.entry-points."haywire.libraries"]\nsrc = "hay_src:Library"\n\n'
        '[tool.hatch.build.targets.wheel]\npackages = ["hay_src"]\n'
    )
    (tmp_path / "pyproject.toml").write_text(
        '[project]\nname = "proj"\ndependencies = ["hay-src"]\n\n'
        "[tool.uv.sources]\nhay-src = { workspace = true }\n"
    )
    # deliberately NOT under graphs/ and NOT a .json extension
    nested = tmp_path / "flows"
    nested.mkdir()
    (nested / "g.haywire").write_text(
        json.dumps(
            {
                "graph_id": "g",
                "nodes": {
                    "n": {
                        "registry_key": "hay-src:node:Add",
                        "node_data": {"ports": {"a": {"kwargs": {"widget_key": "hay-src:widget:W"}}}},
                    }
                },
            }
        )
    )

    subprocess.run(["git", "init", "-q"], cwd=tmp_path, check=True)
    subprocess.run(["git", "config", "user.email", "t@t.t"], cwd=tmp_path, check=True)
    subprocess.run(["git", "config", "user.name", "t"], cwd=tmp_path, check=True)
    subprocess.run(["git", "add", "-A"], cwd=tmp_path, check=True)
    subprocess.run(["git", "commit", "-qm", "seed"], cwd=tmp_path, check=True)
    return tmp_path


@pytest.mark.unit
def test_plan_is_read_only(tmp_path):
    """The preflight promises to change nothing — including temp files."""
    from haywire_studio.packaging.rename.planner import plan_rename

    ws = _workspace(tmp_path)
    plan_rename("hay-src", "hay-dst", ws)

    status = subprocess.run(["git", "status", "--porcelain"], cwd=ws, capture_output=True, text=True).stdout
    assert status == ""


@pytest.mark.unit
def test_plan_finds_graph_outside_graphs_folder(tmp_path):
    from haywire_studio.packaging.rename.planner import plan_rename

    ws = _workspace(tmp_path)
    plan, _ = plan_rename("hay-src", "hay-dst", ws)

    assert plan.ok, plan.blockers
    assert len(plan.graph_changes) == 1
    assert plan.graph_changes[0].count == 2  # registry_key + widget_key


@pytest.mark.unit
def test_plan_enumerates_every_change_kind(tmp_path):
    from haywire_studio.packaging.rename.planner import plan_rename

    ws = _workspace(tmp_path)
    plan, _ = plan_rename("hay-src", "hay-dst", ws)

    assert plan.old_module == "hay_src"
    assert plan.new_module == "hay_dst"
    assert plan.python_changes
    assert plan.toml_changes


@pytest.mark.unit
def test_dirty_tree_blocks_the_plan(tmp_path):
    from haywire_studio.packaging.rename.planner import plan_rename

    ws = _workspace(tmp_path)
    (ws / "dirt.txt").write_text("x")

    assert not plan_rename("hay-src", "hay-dst", ws)[0].ok


@pytest.mark.unit
def test_missing_source_library_blocks(tmp_path):
    from haywire_studio.packaging.rename.planner import plan_rename

    ws = _workspace(tmp_path)
    plan, _ = plan_rename("hay-nope", "hay-dst", ws)

    assert not plan.ok
    assert any("does not exist" in b.message for b in plan.blockers)


@pytest.mark.unit
def test_unconventional_target_flags_confirm(tmp_path):
    from haywire_studio.packaging.rename.planner import plan_rename

    ws = _workspace(tmp_path)
    assert plan_rename("hay-src", "forecast", ws)[1]


@pytest.mark.unit
def test_storage_dir_warning_is_emitted(tmp_path, monkeypatch):
    """Persisted data does not follow the rename — the user must be told."""
    from haywire_studio.packaging.rename import planner

    ws = _workspace(tmp_path)
    fake_home = tmp_path / "home"
    (fake_home / ".haywire" / "db" / "hay_src").mkdir(parents=True)
    monkeypatch.setattr(planner.Path, "home", classmethod(lambda cls: fake_home))

    plan, _ = planner.plan_rename("hay-src", "hay-dst", ws)
    assert any("hay_src" in w.message for w in plan.warnings)
