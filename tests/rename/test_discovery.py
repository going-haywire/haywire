"""Graphs are found by CONTENT, never by extension or location."""

from __future__ import annotations

import json

import pytest


def _graph_bytes(key: str = "haybale-foo:node:Add") -> str:
    return json.dumps({"graph_id": "g", "name": "G", "nodes": {"n": {"registry_key": key}}, "edges": {}})


@pytest.mark.unit
def test_finds_haywire_extension(tmp_path):
    from haywire_studio.packaging.rename.discovery import find_graph_files

    (tmp_path / "graphs").mkdir()
    (tmp_path / "graphs" / "a.haywire").write_text(_graph_bytes())

    assert [p.name for p in find_graph_files(tmp_path)] == ["a.haywire"]


@pytest.mark.unit
def test_finds_graph_with_unknown_future_extension(tmp_path):
    """Abstractions and graph-groups will use extensions not yet chosen."""
    from haywire_studio.packaging.rename.discovery import find_graph_files

    (tmp_path / "abstraction.hwabs").write_text(_graph_bytes())

    assert [p.name for p in find_graph_files(tmp_path)] == ["abstraction.hwabs"]


@pytest.mark.unit
def test_finds_graphs_outside_the_graphs_folder(tmp_path):
    from haywire_studio.packaging.rename.discovery import find_graph_files

    nested = tmp_path / "some" / "deep" / "place"
    nested.mkdir(parents=True)
    (nested / "b.haywire").write_text(_graph_bytes())

    assert [p.name for p in find_graph_files(tmp_path)] == ["b.haywire"]


@pytest.mark.unit
def test_ignores_non_graph_json(tmp_path):
    from haywire_studio.packaging.rename.discovery import find_graph_files

    (tmp_path / "package.json").write_text(json.dumps({"name": "x", "version": "1"}))
    (tmp_path / "tsconfig.json").write_text(json.dumps({"compilerOptions": {}}))

    assert find_graph_files(tmp_path) == []


@pytest.mark.unit
def test_prunes_heavy_directories(tmp_path):
    """A graph inside .venv or node_modules is not the project's graph."""
    from haywire_studio.packaging.rename.discovery import find_graph_files

    for skipped in (".venv", "node_modules", "__pycache__", ".git"):
        d = tmp_path / skipped
        d.mkdir()
        (d / "x.haywire").write_text(_graph_bytes())

    assert find_graph_files(tmp_path) == []


@pytest.mark.unit
def test_ignores_binary_and_unreadable_files(tmp_path):
    from haywire_studio.packaging.rename.discovery import find_graph_files

    (tmp_path / "image.png").write_bytes(b"\x89PNG\r\n\x1a\n\x00\x00")
    (tmp_path / "notes.txt").write_text("registry_key mentioned in prose")

    assert find_graph_files(tmp_path) == []


@pytest.mark.unit
def test_result_is_sorted_and_deduplicated(tmp_path):
    from haywire_studio.packaging.rename.discovery import find_graph_files

    (tmp_path / "b.haywire").write_text(_graph_bytes())
    (tmp_path / "a.haywire").write_text(_graph_bytes())

    assert [p.name for p in find_graph_files(tmp_path)] == ["a.haywire", "b.haywire"]
