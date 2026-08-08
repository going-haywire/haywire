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


@pytest.fixture
def renamable_workspace(tmp_path):
    """A minimal workspace holding one ruff-formatted (double-quoted) library.

    Enough of the shape `rename_library` walks: barn/<lib>/<module>/__init__.py,
    the library's pyproject, and the project's. No marketplace.toml — that path
    is optional — and `uv sync` is stubbed by the caller.
    """
    lib_dir = tmp_path / "barn" / "haybale-old"
    pkg_dir = lib_dir / "haybale_old"
    pkg_dir.mkdir(parents=True)
    (pkg_dir / "__init__.py").write_text(
        '"""Local haybale library for the old project."""\n'
        "\n"
        "from haywire.core.library.base import BaseLibrary\n"
        "from haywire.core.library.decorator import library\n"
        "\n"
        "\n"
        "@library(\n"
        '    label="Old Label",\n'
        '    id="old",\n'
        "    linked_libraries=[],\n"
        "    file_watcher=True,\n"
        ")\n"
        "class Library(BaseLibrary):\n"
        "    pass\n"
    )
    (lib_dir / "pyproject.toml").write_text(
        '[project]\nname = "haybale-old"\nversion = "0.1.0"\ndescription = "old"\n\n'
        '[project.entry-points."haywire.libraries"]\nold = "haybale_old:Library"\n\n'
        '[tool.hatch.build.targets.wheel]\npackages = ["haybale_old"]\n'
    )
    (tmp_path / "pyproject.toml").write_text(
        '[project]\nname = "proj"\ndependencies = ["haybale-old"]\n\n'
        "[tool.uv.sources]\nhaybale-old = { workspace = true }\n"
    )
    return tmp_path


def _rename(workspace, monkeypatch):
    """Drive rename_library with `uv sync` stubbed out, returning the new __init__."""
    import subprocess as sp

    from haywire_studio.packaging import rename as rename_mod

    monkeypatch.setattr(
        rename_mod.subprocess,
        "run",
        lambda *a, **kw: sp.CompletedProcess(a[0] if a else [], 0, b""),
    )
    ok, msg = rename_mod.rename_library("haybale-old", "new-name", workspace, sink=lambda _m: None)
    assert ok, msg
    return (workspace / "barn" / "haybale-new-name" / "haybale_new_name" / "__init__.py").read_text()


@pytest.mark.unit
def test_rename_rewrites_a_double_quoted_label(renamable_workspace, monkeypatch):
    """Regression: rename used single-quote-only regexes, so every rewrite
    silently no-opped against ruff-formatted source — the same defect fixed in
    update_library_identity, missed because rename.py is a separate file."""
    result = _rename(renamable_workspace, monkeypatch)

    assert 'label="New Name"' in result
    assert "Old Label" not in result


@pytest.mark.unit
def test_rename_does_not_write_removed_fields(renamable_workspace, monkeypatch):
    """version, description, url, author, author_url and tags are no longer
    decorator fields — rename must not reintroduce them."""
    result = _rename(renamable_workspace, monkeypatch)

    for gone in ("version=", "description=", "url=", "author=", "author_url=", "tags="):
        assert gone not in result, gone


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
