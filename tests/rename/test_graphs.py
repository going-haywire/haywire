"""Recursive, name-based registry-key rewriting."""

from __future__ import annotations

from typing import Any

import pytest


@pytest.mark.unit
def test_rewrites_keys_at_real_nesting_depth():
    """Real graphs carry keys inside ports, three levels down."""
    from haywire_studio.packaging.rename.graphs import patch_graph_tree

    data: dict[str, Any] = {
        "nodes": {
            "n1": {
                "registry_key": "haybale-foo:node:Add",
                "node_data": {
                    "identity": {"registry_key": "haybale-foo:node:Add"},
                    "ports": {
                        "a": {
                            "kwargs": {
                                "registry_key": "haybale-foo:type:FLOAT",
                                "widget_key": "haybale-foo:widget:NumberWidget",
                            },
                            "recipe": {"registry_key": "haybale-foo:type:FLOAT"},
                        }
                    },
                },
            }
        }
    }

    count, _ = patch_graph_tree(data, "haybale-foo", "hay-bar")

    node = data["nodes"]["n1"]
    port = node["node_data"]["ports"]["a"]
    assert node["registry_key"] == "hay-bar:node:Add"
    assert node["node_data"]["identity"]["registry_key"] == "hay-bar:node:Add"
    assert port["kwargs"]["registry_key"] == "hay-bar:type:FLOAT"
    assert port["kwargs"]["widget_key"] == "hay-bar:widget:NumberWidget"
    assert port["recipe"]["registry_key"] == "hay-bar:type:FLOAT"
    assert count == 5


@pytest.mark.unit
def test_rewrites_graphs_nested_inside_nodes():
    """Graph-groups will nest a whole graph inside a node. Depth is unbounded."""
    from haywire_studio.packaging.rename.graphs import patch_graph_tree

    data: dict[str, Any] = {
        "nodes": {
            "outer": {
                "registry_key": "haybale-foo:node:Group",
                "node_data": {
                    "subgraph": {
                        "nodes": {
                            "inner": {
                                "registry_key": "haybale-foo:node:Add",
                                "node_data": {
                                    "subgraph": {
                                        "nodes": {"deepest": {"registry_key": "haybale-foo:node:Sub"}}
                                    }
                                },
                            }
                        }
                    }
                },
            }
        }
    }

    count, _ = patch_graph_tree(data, "haybale-foo", "hay-bar")

    outer = data["nodes"]["outer"]
    inner = outer["node_data"]["subgraph"]["nodes"]["inner"]
    deepest = inner["node_data"]["subgraph"]["nodes"]["deepest"]
    assert outer["registry_key"] == "hay-bar:node:Group"
    assert inner["registry_key"] == "hay-bar:node:Add"
    assert deepest["registry_key"] == "hay-bar:node:Sub"
    assert count == 3


@pytest.mark.unit
def test_rewrites_chain_adapter_key_lists():
    from haywire_studio.packaging.rename.graphs import patch_graph_tree

    data: dict[str, Any] = {
        "edges": {"e": {"chain_adapter_keys": ["haybale-foo:adapter:X", "other:adapter:Y"]}}
    }
    count, _ = patch_graph_tree(data, "haybale-foo", "hay-bar")

    assert data["edges"]["e"]["chain_adapter_keys"] == ["hay-bar:adapter:X", "other:adapter:Y"]
    assert count == 1


@pytest.mark.unit
def test_rewrites_library_name_only_under_node_data():
    from haywire_studio.packaging.rename.graphs import patch_graph_tree

    data: dict[str, Any] = {
        "name": "haybale-foo",  # the GRAPH's name — must NOT change
        "nodes": {"n": {"node_data": {"library": {"name": "haybale-foo"}}}},
    }
    patch_graph_tree(data, "haybale-foo", "hay-bar")

    assert data["name"] == "haybale-foo"
    assert data["nodes"]["n"]["node_data"]["library"]["name"] == "hay-bar"


@pytest.mark.unit
def test_never_rewrites_user_prose():
    from haywire_studio.packaging.rename.graphs import patch_graph_tree

    data: dict[str, Any] = {"nodes": {"n": {"node_data": {"props": {"note": "uses haybale-foo a lot"}}}}}
    count, _ = patch_graph_tree(data, "haybale-foo", "hay-bar")

    assert count == 0
    assert data["nodes"]["n"]["node_data"]["props"]["note"] == "uses haybale-foo a lot"


@pytest.mark.unit
def test_prefix_match_is_colon_scoped():
    """haybale-foo must not match haybale-foobar."""
    from haywire_studio.packaging.rename.graphs import patch_graph_tree

    data: dict[str, Any] = {"nodes": {"n": {"registry_key": "haybale-foobar:node:Add"}}}
    count, _ = patch_graph_tree(data, "haybale-foo", "hay-bar")

    assert count == 0


@pytest.mark.unit
def test_non_key_value_in_a_key_field_is_left_alone():
    """Grammar guard: a key field holding something that is not a key."""
    from haywire_studio.packaging.rename.graphs import patch_graph_tree

    data: dict[str, Any] = {"nodes": {"n": {"registry_key": "haybale-foo: see the docs"}}}
    count, _ = patch_graph_tree(data, "haybale-foo", "hay-bar")

    assert count == 0


@pytest.mark.unit
def test_drift_scan_reports_unpatched_occurrences():
    from haywire_studio.packaging.rename.graphs import patch_graph_tree

    data: dict[str, Any] = {
        "name": "haybale-foo",
        "nodes": {"n": {"node_data": {"props": {"note": "haybale-foo"}}}},
    }
    _, leftovers = patch_graph_tree(data, "haybale-foo", "hay-bar")

    assert len(leftovers) == 2


@pytest.mark.unit
def test_is_registry_key_grammar():
    from haywire_studio.packaging.rename.graphs import is_registry_key

    assert is_registry_key("haybale-core:type:FLOAT")
    assert is_registry_key("haywire-core:widget:NumberWidget")
    assert is_registry_key("haybale-studio:theme:node:Dark")  # 4-part variant
    assert not is_registry_key("haybale-foo: see the docs")
    assert not is_registry_key("just-a-name")
    assert not is_registry_key("")
