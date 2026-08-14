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
    count, leftovers = patch_graph_tree(data, "haybale-foo", "hay-bar")

    assert count == 0
    # A key-shaped field _rewrite declines to touch is still a real
    # occurrence of `old` — it must surface as drift, not vanish silently
    # just because it lives in a KEY_FIELDS-named field.
    assert leftovers == ["nodes.n.registry_key"]


@pytest.mark.unit
def test_non_key_value_in_a_key_field_is_left_alone():
    """Grammar guard: a key field holding something that is not a key."""
    from haywire_studio.packaging.rename.graphs import patch_graph_tree

    data: dict[str, Any] = {"nodes": {"n": {"registry_key": "haybale-foo: see the docs"}}}
    count, leftovers = patch_graph_tree(data, "haybale-foo", "hay-bar")

    assert count == 0
    assert leftovers == ["nodes.n.registry_key"]


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
def test_module_name_field_reported_as_drift():
    """Finding 6: library.module_name carries the UNDERSCORE module form,
    distinct from the hyphenated distribution name the walker rewrites. It
    is not rewritten (write-only telemetry, not read back on load), but the
    drift scan must still report it as an unrecognized occurrence when
    old_module is supplied — otherwise the safety net silently misses a
    known-stale field."""
    from haywire_studio.packaging.rename.graphs import patch_graph_tree

    data: dict[str, Any] = {
        "nodes": {
            "n": {
                "node_data": {
                    "library": {"name": "haybale-foo", "module_name": "haybale_foo"},
                }
            }
        }
    }

    count, leftovers = patch_graph_tree(data, "haybale-foo", "hay-bar", old_module="haybale_foo")

    # library.name IS rewritten (position-scoped rule); module_name is not.
    assert data["nodes"]["n"]["node_data"]["library"]["name"] == "hay-bar"
    assert data["nodes"]["n"]["node_data"]["library"]["module_name"] == "haybale_foo"
    assert count == 1
    assert any("module_name" in path for path in leftovers)


@pytest.mark.unit
def test_module_name_drift_not_reported_without_old_module():
    """Without old_module, drift scanning is unchanged (searches only the
    distribution name) — proves the widening is additive, not a behavior
    change for existing callers."""
    from haywire_studio.packaging.rename.graphs import patch_graph_tree

    data: dict[str, Any] = {"nodes": {"n": {"node_data": {"library": {"module_name": "haybale_foo"}}}}}

    _, leftovers = patch_graph_tree(data, "haybale-foo", "hay-bar")

    assert leftovers == []


@pytest.mark.unit
def test_rewritten_field_is_not_reported_as_drift_when_new_contains_old():
    """A rename target that extends the old name as a prefix (e.g.
    haybale-testing -> haybale-testing2) makes every correctly-rewritten
    value still contain the old needle as a substring of its NEW value.
    Scanning the post-mutation tree for drift double-reports those fields
    as unpatched even though they were rewritten correctly — the drift scan
    must run against a pre-mutation snapshot."""
    from haywire_studio.packaging.rename.graphs import patch_graph_tree

    data: dict[str, Any] = {
        "nodes": {
            "n": {
                "registry_key": "haybale-testing:node:X",
                "node_data": {
                    "identity": {"registry_key": "haybale-testing:node:X"},
                    "library": {"name": "haybale-testing"},
                },
            }
        }
    }

    count, leftovers = patch_graph_tree(data, "haybale-testing", "haybale-testing2")

    node = data["nodes"]["n"]
    assert node["registry_key"] == "haybale-testing2:node:X"
    assert node["node_data"]["identity"]["registry_key"] == "haybale-testing2:node:X"
    assert node["node_data"]["library"]["name"] == "haybale-testing2"
    assert count == 3
    assert leftovers == []


@pytest.mark.unit
def test_is_registry_key_grammar():
    from haywire_studio.packaging.rename.graphs import is_registry_key

    assert is_registry_key("haybale-core:type:FLOAT")
    assert is_registry_key("haywire-core:widget:NumberWidget")
    assert is_registry_key("haybale-studio:theme:node:Dark")  # 4-part variant
    assert not is_registry_key("haybale-foo: see the docs")
    assert not is_registry_key("just-a-name")
    assert not is_registry_key("")
