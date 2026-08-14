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
def test_whitespace_padded_target_normalized_end_to_end(tmp_path):
    """Finding 3: a padded target name must not leak literal whitespace into
    the resulting directory/module name — the rename must use the trimmed
    name throughout, not the raw input."""
    ws = _workspace(tmp_path)
    ok, message = _run(ws, "hay-src", "  hay-dst  ")

    assert ok, message
    assert (ws / "barn" / "hay-dst").is_dir()
    assert (ws / "barn" / "hay-dst" / "hay_dst").is_dir()
    assert not (ws / "barn" / "  hay-dst  ").exists()
    toml_text = (ws / "barn" / "hay-dst" / "hay_dst" / "haybale.toml").read_text()
    assert 'name = "hay-dst"' in toml_text


@pytest.mark.unit
def test_python_outside_module_dir_does_not_crash(tmp_path):
    """Finding 1: a .py file under barn/<lib>/ but outside the module dir
    (tests/, conftest.py, ...) must not raise ValueError out of execute_plan."""
    ws = _workspace(tmp_path)
    tests_dir = ws / "barn" / "hay-src" / "tests"
    tests_dir.mkdir()
    (tests_dir / "test_x.py").write_text('from hay_src.types import X\nW = "hay-src:widget:Thing"\n')

    import subprocess as sp

    sp.run(["git", "add", "-A"], cwd=ws, check=True)
    sp.run(["git", "commit", "-qm", "add tests dir"], cwd=ws, check=True)

    ok, message = _run(ws, "hay-src", "hay-dst")

    assert ok, message
    text = (ws / "barn" / "hay-dst" / "tests" / "test_x.py").read_text()
    assert "from hay_dst.types import X" in text
    assert '"hay-dst:widget:Thing"' in text


@pytest.mark.unit
def test_graph_inside_library_dir_is_retargeted_and_patched(tmp_path):
    """Finding 2: a graph shipped inside barn/<lib>/<module>/ must be found
    at its NEW location after the phase-3 directory rename, not raise
    FileNotFoundError."""
    ws = _workspace(tmp_path)
    examples_dir = ws / "barn" / "hay-src" / "hay_src" / "examples"
    examples_dir.mkdir()
    (examples_dir / "demo.haywire").write_text(
        json.dumps({"graph_id": "demo", "nodes": {"n": {"registry_key": "hay-src:node:Demo"}}})
    )

    import subprocess as sp

    sp.run(["git", "add", "-A"], cwd=ws, check=True)
    sp.run(["git", "commit", "-qm", "add in-library graph"], cwd=ws, check=True)

    ok, message = _run(ws, "hay-src", "hay-dst")

    assert ok, message
    new_path = ws / "barn" / "hay-dst" / "hay_dst" / "examples" / "demo.haywire"
    assert new_path.is_file()
    data = json.loads(new_path.read_text())
    assert data["nodes"]["n"]["registry_key"] == "hay-dst:node:Demo"


@pytest.mark.unit
def test_missing_entry_points_section_fails_cleanly(tmp_path):
    """Finding 4: a pyproject.toml missing [project.entry-points."haywire.libraries"]
    must fail loud (KeyError, caught), not silently drop the write while
    reporting success."""
    from haywire_studio.packaging.rename.execute import execute_plan
    from haywire_studio.packaging.rename.planner import plan_rename

    ws = _workspace(tmp_path)
    (ws / "barn" / "hay-src" / "pyproject.toml").write_text('[project]\nname = "hay-src"\n')

    import subprocess as sp

    sp.run(["git", "add", "-A"], cwd=ws, check=True)
    sp.run(["git", "commit", "-qm", "strip entry-points"], cwd=ws, check=True)

    plan, _ = plan_rename("hay-src", "hay-dst", ws)
    assert plan.ok, plan.blockers

    with patch("haywire_studio.packaging.rename.execute.subprocess.run") as run:
        run.return_value.returncode = 0
        run.return_value.stdout = b""
        ok, message = execute_plan(plan, sink=lambda *_: None)

    assert not ok
    assert "library metadata" in message
    assert "Traceback" not in message


@pytest.mark.unit
def test_sibling_heap_linked_libraries_rewritten(tmp_path):
    """Finding 5: a SIBLING heap's linked_libraries entry naming the renamed
    library's old module must be rewritten too, not just the renamed
    library's own heap name/path."""
    ws = _workspace(tmp_path)

    dep = ws / "barn" / "hay-dep" / "hay_dep"
    dep.mkdir(parents=True)
    (dep / "haybale.toml").write_text('name = "hay-dep"\nversion = "0.1.0"\n')
    (ws / "barn" / "hay-dep" / "pyproject.toml").write_text('[project]\nname = "hay-dep"\n')

    marketplace_dir = ws / ".haywire"
    marketplace_dir.mkdir(exist_ok=True)
    (marketplace_dir / "marketplace.toml").write_text(
        '[[heaps]]\nname = "hay-src"\npath = "barn/hay-src"\n\n'
        '[[heaps]]\nname = "hay-dep"\npath = "barn/hay-dep"\n'
        'linked_libraries = ["hay_src"]\n'
    )

    import subprocess as sp

    sp.run(["git", "add", "-A"], cwd=ws, check=True)
    sp.run(["git", "commit", "-qm", "add dependent heap"], cwd=ws, check=True)

    ok, message = _run(ws, "hay-src", "hay-dst")
    assert ok, message

    text = (ws / ".haywire" / "marketplace.toml").read_text()
    import toml as toml_lib

    doc = toml_lib.loads(text)
    dep_heap = next(h for h in doc["heaps"] if h["name"] == "hay-dep")
    assert dep_heap["linked_libraries"] == ["hay_dst"]


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
