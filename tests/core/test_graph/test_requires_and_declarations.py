"""A saved graph names the libraries it needs and the declaration of each node class it holds."""

from __future__ import annotations

import pytest

from haywire.core.graph.base import BaseGraph
from haywire.core.graph.scheduler import SyncScheduler

from tests.conftest import make_node

pytestmark = pytest.mark.integration

_ADD = "haybale-testing:node:TestAddFloatNode"
_MISSING = "haybale-gone:node:Vanished"


def _graph(name: str = "g") -> BaseGraph:
    return BaseGraph(filestem=name, validation_scheduler=SyncScheduler())


def test_a_saved_graph_names_its_libraries(library_system):
    graph = _graph()
    wrapper = make_node(graph, _ADD)

    saved = graph.to_dict()

    assert saved["requires"] == {"haybale-testing": wrapper.node.library.version}


def test_a_saved_graph_holds_one_declaration_per_node_class(library_system):
    graph = _graph()
    first = make_node(graph, _ADD)
    make_node(graph, _ADD)

    saved = graph.to_dict()

    assert list(saved["declarations"]) == [_ADD]
    assert saved["declarations"][_ADD] == first.node.saved_declaration
    assert saved["declarations"][_ADD]["value_a"]["kwargs"]["port_type"] == "inlet"


def test_a_saved_node_carries_nothing_its_class_says(library_system):
    graph = _graph()
    wrapper = make_node(graph, _ADD, position=(120, 80))

    saved = graph.to_dict()["nodes"][wrapper.node_id]

    assert set(saved) == {"node_id", "registry_key", "node_data"}
    assert set(saved["node_data"]) == {"ports", "settings", "props", "store"}
    assert "props" not in saved["node_data"]["settings"]


def test_props_come_back_from_their_one_place(library_system):
    graph = _graph()
    wrapper = make_node(graph, _ADD, position=(120, 80))
    wrapper.node.props.label = "Mine"

    loaded = _graph("h")
    assert loaded.load_from_dict(graph.to_dict()) is True

    props = loaded.node_wrappers[wrapper.node_id].node.props
    assert props.get_position() == wrapper.node.props.get_position()
    assert props.label == "Mine"


def test_a_missing_class_keeps_the_entries_of_its_file(library_system):
    graph = _graph()
    wrapper = make_node(graph, _ADD)
    saved = graph.to_dict()
    node = saved["nodes"].pop(wrapper.node_id)
    node["registry_key"] = _MISSING
    saved["nodes"]["gone"] = {**node, "node_id": "gone"}
    saved["requires"] = {"haybale-gone": "1.2.3"}
    saved["declarations"] = {_MISSING: {"value_a": {"recipe": {"registry_key": "x"}, "kwargs": {}}}}

    loaded = _graph("h")
    assert loaded.load_from_dict(saved) is True
    assert loaded.node_wrappers["gone"].is_stand_in

    again = loaded.to_dict()
    assert again["requires"] == saved["requires"]
    assert again["declarations"] == saved["declarations"]
    assert again["nodes"]["gone"]["node_data"]["ports"] == node["node_data"]["ports"]
