"""Impact computation for the uninstall flow — pure, no registry or UI."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from haybale_marketplace.uninstall_impact import (
    UninstallImpact,
    find_graph_usage,
    find_pip_dependents,
)

pytestmark = pytest.mark.unit


def _graph(path: Path, *registry_keys: str) -> None:
    """Write a minimal .haywire document referencing *registry_keys*."""
    path.parent.mkdir(parents=True, exist_ok=True)
    nodes = {
        f"Node_{i}": {"node_id": f"Node_{i}", "registry_key": key, "position": {"x": 0, "y": 0}}
        for i, key in enumerate(registry_keys)
    }
    path.write_text(json.dumps({"graph_id": path.stem, "name": path.stem, "nodes": nodes, "edges": {}}))


def test_finds_graph_referencing_library(tmp_path: Path) -> None:
    _graph(tmp_path / "a.haywire", "visiongraph:node:WebCameraNode", "core:node:BeginPlayNode")

    usage = find_graph_usage(tmp_path, "visiongraph")

    assert [u.name for u in usage] == ["a.haywire"]
    assert usage[0].references == 1


def test_ignores_graphs_without_the_library(tmp_path: Path) -> None:
    _graph(tmp_path / "a.haywire", "core:node:BeginPlayNode")

    assert find_graph_usage(tmp_path, "visiongraph") == []


def test_counts_non_node_component_kinds(tmp_path: Path) -> None:
    """A library's footprint spans types, adapters and widgets, not just nodes.

    The prefix search is what makes this work — a nodes-only walk would report
    this graph as unaffected.
    """
    _graph(tmp_path / "a.haywire", "visiongraph:node:Cam", "visiongraph:type:Frame")
    path = tmp_path / "a.haywire"
    doc = json.loads(path.read_text())
    doc["nodes"]["Node_0"]["node_data"] = {"widget": "visiongraph:widget:Preview"}
    path.write_text(json.dumps(doc))

    usage = find_graph_usage(tmp_path, "visiongraph")

    assert usage[0].references == 3


def test_skips_venv_and_git(tmp_path: Path) -> None:
    """Installed libraries ship their own graphs; those are not the user's."""
    _graph(tmp_path / ".venv" / "pkg" / "bundled.haywire", "visiongraph:node:Cam")
    _graph(tmp_path / ".git" / "stash.haywire", "visiongraph:node:Cam")
    _graph(tmp_path / "mine.haywire", "visiongraph:node:Cam")

    usage = find_graph_usage(tmp_path, "visiongraph")

    assert [u.name for u in usage] == ["mine.haywire"]


def test_searches_nested_directories(tmp_path: Path) -> None:
    _graph(tmp_path / "deep" / "nested" / "b.haywire", "visiongraph:node:Cam")

    assert len(find_graph_usage(tmp_path, "visiongraph")) == 1


def test_sorted_by_descending_reference_count(tmp_path: Path) -> None:
    _graph(tmp_path / "few.haywire", "visiongraph:node:Cam")
    _graph(tmp_path / "many.haywire", "visiongraph:node:Cam", "visiongraph:node:Depth")

    usage = find_graph_usage(tmp_path, "visiongraph")

    assert [u.name for u in usage] == ["many.haywire", "few.haywire"]


def test_malformed_graph_still_reports(tmp_path: Path) -> None:
    """Text search, not JSON parse — a broken graph must not vanish."""
    (tmp_path / "broken.haywire").write_text('{"nodes": {"a": {"registry_key": "visiongraph:node:Cam"')

    usage = find_graph_usage(tmp_path, "visiongraph")

    assert [u.name for u in usage] == ["broken.haywire"]


def test_missing_root_is_empty_not_an_error(tmp_path: Path) -> None:
    assert find_graph_usage(tmp_path / "nope", "visiongraph") == []


def test_library_id_prefix_does_not_match_a_longer_id(tmp_path: Path) -> None:
    """`vision` must not match `visiongraph:` — the colon is the boundary."""
    _graph(tmp_path / "a.haywire", "visiongraph:node:Cam")

    assert find_graph_usage(tmp_path, "vision") == []


def test_pip_dependents_finds_requirers() -> None:
    """Something in this venv requires pytest; the walk must find it."""
    dependents = find_pip_dependents("pytest")

    assert dependents
    assert all(isinstance(d, str) for d in dependents)


def test_pip_dependents_normalizes_separators() -> None:
    """`-`, `_` and `.` are the same separator to pip."""
    assert find_pip_dependents("pytest_cov") == find_pip_dependents("pytest-cov")


def test_pip_dependents_excludes_self() -> None:
    assert "pytest" not in [d.lower() for d in find_pip_dependents("pytest")]


def test_pip_dependents_unknown_dist_is_empty() -> None:
    assert find_pip_dependents("definitely-not-installed-xyz") == []


def test_pip_dependents_empty_name_is_empty() -> None:
    assert find_pip_dependents("") == []


def test_impact_totals_and_editable_flag() -> None:
    impact = UninstallImpact(library_id="visiongraph", install_type="EDITABLE")
    assert impact.is_editable
    assert impact.total_references == 0
    assert not UninstallImpact(library_id="x", install_type="REGULAR").is_editable
