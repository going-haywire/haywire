# tests/test_rename_cli.py
"""Tests for the haywire rename CLI (haywire_studio.packaging.rename)."""

from __future__ import annotations

import pytest


@pytest.mark.unit
def test_sanitize_name_rejects_path_separators():
    from haywire_studio.packaging.rename import sanitize_rename

    assert sanitize_rename("foo/bar") is None
    assert sanitize_rename("..") is None
    assert sanitize_rename("My Lib") == "my_lib"


@pytest.mark.unit
def test_patch_graphs_dry_run_only_touches_registry_keys(tmp_path):
    import json

    from haywire_studio.packaging.rename import patch_graph_references

    graphs = tmp_path / "graphs"
    graphs.mkdir()
    g = graphs / "g1.json"
    g.write_text(
        json.dumps(
            {
                "nodes": [{"type": "foo:node:adder"}],  # registry key — SHOULD change
                "meta": {"note": "see foo:bar in docs"},  # user value — must NOT change
            }
        )
    )

    changes = patch_graph_references(graphs, "foo", "bar", apply=False)

    # dry-run reports the one real key change, leaves the file untouched
    assert changes.files_changed == 1
    assert changes.replacements == 1
    on_disk = json.loads(g.read_text())
    assert on_disk["nodes"][0]["type"] == "foo:node:adder"  # unchanged (dry-run)
    assert on_disk["meta"]["note"] == "see foo:bar in docs"  # never a candidate


@pytest.mark.unit
def test_patch_graphs_apply_writes_and_backs_up(tmp_path):
    import json

    from haywire_studio.packaging.rename import patch_graph_references

    graphs = tmp_path / "graphs"
    graphs.mkdir()
    g = graphs / "g1.json"
    g.write_text(json.dumps({"nodes": [{"type": "foo:node:adder"}]}))

    patch_graph_references(graphs, "foo", "bar", apply=True)

    assert json.loads(g.read_text())["nodes"][0]["type"] == "bar:node:adder"
    assert (graphs / "g1.json.bak").exists()  # backup written


@pytest.mark.unit
def test_run_rename_cli_dry_run_does_not_write(tmp_path, capsys):
    import json
    from haywire_studio.packaging.rename import run_rename_cli

    # minimal workspace: graphs/ with one referencing graph
    (tmp_path / "graphs").mkdir()
    g = tmp_path / "graphs" / "g.json"
    g.write_text(json.dumps({"nodes": [{"type": "foo:node:x"}]}))

    # bundle: rename + patch, but dry-run (apply=False) skips package rename + writes
    code = run_rename_cli(
        old_library="haybale-foo",
        new_name="bar",
        workspace_root=tmp_path,
        apply=False,
    )

    assert code == 0
    # dry-run printed the plan and left the graph untouched
    assert json.loads(g.read_text())["nodes"][0]["type"] == "foo:node:x"
    out = capsys.readouterr().out
    assert "1 file" in out  # reports the would-be change
