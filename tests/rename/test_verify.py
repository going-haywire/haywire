"""haywire verify resolves keys without instantiating anything."""

from __future__ import annotations

import json

import pytest


def _graph(tmp_path, name, *keys):
    nodes = {
        f"n{i}": {
            "registry_key": key,
            "node_data": {"ports": {"a": {"kwargs": {"widget_key": key}}}},
        }
        for i, key in enumerate(keys)
    }
    path = tmp_path / name
    path.write_text(json.dumps({"graph_id": "g", "nodes": nodes}))
    return path


@pytest.mark.unit
def test_collect_keys_finds_every_key_at_any_depth():
    from haywire_studio.packaging.verify import collect_keys

    data = {
        "nodes": {
            "n": {
                "registry_key": "a:node:X",
                "node_data": {
                    "ports": {"p": {"kwargs": {"widget_key": "a:widget:W"}}},
                    "subgraph": {"nodes": {"m": {"registry_key": "b:node:Y"}}},
                },
            }
        },
        "edges": {"e": {"chain_adapter_keys": ["c:adapter:Z"]}},
    }

    assert collect_keys(data) == {
        "a:node:X": 1,
        "a:widget:W": 1,
        "b:node:Y": 1,
        "c:adapter:Z": 1,
    }


@pytest.mark.unit
def test_all_keys_resolve_reports_ok(tmp_path):
    from haywire_studio.packaging.verify import verify_graphs

    _graph(tmp_path, "g.haywire", "hay-x:node:Add")
    report = verify_graphs(tmp_path, resolver=lambda key: True)

    assert report.ok
    assert report.graphs_checked == 1
    assert report.unresolved_total == 0


@pytest.mark.unit
def test_unresolved_key_is_reported_per_graph(tmp_path):
    from haywire_studio.packaging.verify import verify_graphs

    _graph(tmp_path, "g.haywire", "hay-gone:node:Add")
    report = verify_graphs(tmp_path, resolver=lambda key: False)

    assert not report.ok
    assert report.unresolved_total == 2  # registry_key + widget_key
    assert report.graphs[0].unresolved["hay-gone:node:Add"] == 2


@pytest.mark.unit
def test_mixed_resolution_reports_only_the_missing(tmp_path):
    from haywire_studio.packaging.verify import verify_graphs

    _graph(tmp_path, "g.haywire", "hay-ok:node:A", "hay-gone:node:B")
    report = verify_graphs(tmp_path, resolver=lambda key: key.startswith("hay-ok"))

    assert not report.ok
    assert set(report.graphs[0].unresolved) == {"hay-gone:node:B"}


@pytest.mark.unit
def test_empty_workspace_is_ok(tmp_path):
    from haywire_studio.packaging.verify import verify_graphs

    report = verify_graphs(tmp_path, resolver=lambda key: True)
    assert report.ok
    assert report.graphs_checked == 0


@pytest.mark.unit
def test_cli_exit_code_reflects_resolution(tmp_path):
    from haywire_studio.packaging.verify import run_verify_cli

    _graph(tmp_path, "g.haywire", "hay-gone:node:Add")
    assert run_verify_cli(workspace_root=tmp_path, resolver=lambda key: False) != 0
    assert run_verify_cli(workspace_root=tmp_path, resolver=lambda key: True) == 0
