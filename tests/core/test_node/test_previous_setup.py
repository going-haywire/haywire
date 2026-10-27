"""A node holds a previous setup inside its node data; the warning and ledger row follow it."""

from __future__ import annotations

from typing import Any

import pytest

from haywire.core.errors.ledger import ErrorLedger, get_error_ledger, set_error_ledger
from haywire.core.graph.base import BaseGraph
from haywire.core.graph.editor import Editor
from haywire.core.graph.scheduler import SyncScheduler
from haywire.core.node.previous_setup import report_previous_setup, strip_previous_setups

pytestmark = pytest.mark.integration


@pytest.fixture
def ledger():
    previous = get_error_ledger()
    fresh = ErrorLedger(max_entries=20)
    set_error_ledger(fresh)
    yield fresh
    set_error_ledger(previous)


def _print_key() -> str:
    from haybale_testing.nodes.testbed.print_node import TestPrintNode

    return TestPrintNode.class_identity.registry_key


def _printer(graph: BaseGraph, message: str) -> Any:
    wrapper: Any = graph.create_node_wrapper(_print_key(), position=(10.0, 10.0))
    graph._validation.force_immediate_validation()
    wrapper.node.ports["message"].set_value(message)
    return wrapper


def _graph_and_printer(message: str) -> tuple[BaseGraph, Any]:
    graph = BaseGraph("Held", validation_scheduler=SyncScheduler())
    return graph, _printer(graph, message)


def test_a_previous_setup_round_trips_through_node_data(graph_with_library_system):
    _graph, wrapper = _graph_and_printer("kept")
    old = wrapper.serialize()["node_data"]
    wrapper.set_previous_setup(old)
    data = wrapper.serialize()["node_data"]
    assert data["previous_setup"] == old
    assert [w.kind for w in wrapper.state.warnings] == ["previous_setup"]
    assert wrapper.state.warnings[0].message == (
        "Rebuilt from its changed code with default settings. The earlier settings were kept."
    )

    wrapper.build(data)
    assert wrapper.previous_setup == old
    assert [w.kind for w in wrapper.state.warnings] == ["previous_setup"]


def test_building_from_data_without_the_key_clears_it(graph_with_library_system):
    _graph, wrapper = _graph_and_printer("kept")
    wrapper.set_previous_setup(wrapper.serialize()["node_data"])
    data = wrapper.serialize()["node_data"]
    data.pop("previous_setup")
    wrapper.build(data)
    assert wrapper.previous_setup is None
    assert wrapper.state.warnings == []


def test_a_fresh_build_keeps_the_field(graph_with_library_system):
    _graph, wrapper = _graph_and_printer("kept")
    wrapper.set_previous_setup({"x": 1})
    wrapper.build()
    assert wrapper.previous_setup == {"x": 1}
    assert [w.kind for w in wrapper.state.warnings] == ["previous_setup"]


def test_strip_previous_setups_recurses_into_subgraphs():
    doc: dict[str, Any] = {
        "nodes": {"a": {"node_data": {"previous_setup": {}, "props": {}}}},
        "subgraphs": {"g": {"nodes": {"b": {"node_data": {"previous_setup": {}}}}, "subgraphs": {}}},
    }
    strip_previous_setups(doc)
    assert "previous_setup" not in doc["nodes"]["a"]["node_data"]
    assert "previous_setup" not in doc["subgraphs"]["g"]["nodes"]["b"]["node_data"]


def test_report_names_the_node_in_a_root_graph(graph_with_library_system, ledger):
    graph, wrapper = _graph_and_printer("kept")
    report_previous_setup(wrapper, operation="Load graph")
    (entry,) = ledger.query().entries
    assert entry.severity.value == "warning"
    assert (entry.operation, entry.graph_id, entry.node_id) == (
        "Load graph",
        graph.graph_id,
        wrapper.node_id,
    )
    assert entry.message == f"{wrapper.node.display_label} '{wrapper.node_id}' holds a previous setup"


def test_report_names_the_host_of_an_interior(graph_with_library_system, library_system, ledger):
    from haywire.barn.builtin.nodes.graph_node import GraphNode
    from haywire.barn.builtin.nodes.subgraph_io import SubgraphInputNode, SubgraphOutputNode

    graph = BaseGraph("Host", validation_scheduler=SyncScheduler())
    editor = Editor(graph, library_system.get_node_factory())
    printer = _printer(graph, "kept")
    host_id, _ = editor.collapse_to_group(
        [printer.node_id],
        GraphNode.class_identity.registry_key,
        SubgraphInputNode.class_identity.registry_key,
        SubgraphOutputNode.class_identity.registry_key,
    )
    assert host_id is not None
    host: Any = graph.get_node_wrapper(host_id)
    definition: Any = graph.get_subgraph(host.node.subgraph_key)
    interior = next(w for w in definition.node_wrappers.values() if w.registry_key == _print_key())

    report_previous_setup(interior, operation="Hot reload")
    (entry,) = ledger.query().entries
    assert (entry.graph_id, entry.node_id) == (definition.graph_id, interior.node_id)
    assert entry.message.endswith(f"kept its previous setup (inside '{host.node.display_label}')")
