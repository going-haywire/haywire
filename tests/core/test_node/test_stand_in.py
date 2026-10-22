"""An error node stands in for a node that cannot be built, and keeps that node's data.

Two causes: the node's class is unknown (a library is missing), or its
constructor raises (a broken edit, reloaded). Either way the graph stays
editable, and a save writes the original node back, so the real node returns
with its values once its class works again.
"""

from __future__ import annotations

import copy

import pytest

from haywire.barn.builtin.nodes.error_node import ErrorNode
from haywire.core.graph.base import BaseGraph
from haywire.core.graph.scheduler import SyncScheduler
from haywire.core.node.layout import position_of

pytestmark = pytest.mark.integration

_UNKNOWN = "haybale-testing:node:NoSuchNode"


def _print_key() -> str:
    from haybale_testing.nodes.testbed.print_node import TestPrintNode

    return TestPrintNode.class_identity.registry_key


def _load(data: dict) -> BaseGraph:
    graph = BaseGraph(filestem="Reloaded", validation_scheduler=SyncScheduler())
    graph.load_from_dict(data)
    return graph


def _reset(graph: BaseGraph, node_id: str) -> None:
    graph.request_node_reset(node_id)
    graph._validation.force_immediate_validation()


def _saved(graph: BaseGraph, node_id: str) -> dict:
    return graph.to_dict()["nodes"][node_id]


def _two_nodes(graph: BaseGraph):
    broken = graph.create_node_wrapper(_print_key(), position=(300.0, 40.0))
    healthy = graph.create_node_wrapper(_print_key(), position=(10.0, 10.0))
    return broken, healthy


def test_a_constructor_failure_stands_in_an_error_node(graph_with_library_system, construction_fails):
    construction_fails(1)

    wrapper = graph_with_library_system.create_node_wrapper(_print_key(), position=(5.0, 6.0))

    assert isinstance(wrapper.node, ErrorNode)
    assert wrapper.is_stand_in
    assert wrapper.state.error_instantiate is not None
    assert wrapper.registry_key == _print_key()
    assert wrapper.node.props.get_position() == (5.0, 6.0)


def test_the_graph_stays_editable_around_a_stand_in(graph_with_library_system, construction_fails):
    broken, healthy = _two_nodes(graph_with_library_system)
    data = graph_with_library_system.to_dict()
    construction_fails(1)  # the first node built on load
    graph = _load(data)
    assert graph.node_wrappers[broken.node_id].is_stand_in

    added = graph.create_node_wrapper(_print_key(), position=(900.0, 900.0))
    assert added is not None
    graph.move_node(healthy.node_id, 50.0, 60.0)
    graph.move_node(broken.node_id, 70.0, 80.0)
    graph.remove_node_wrapper(graph.node_wrappers[added.node_id])

    assert graph.node_wrappers[healthy.node_id].node.props.get_position() == (50.0, 60.0)
    assert graph.node_wrappers[broken.node_id].node.props.get_position() == (70.0, 80.0)


def test_a_stand_in_saves_its_original_node_data(graph_with_library_system, construction_fails):
    broken, _ = _two_nodes(graph_with_library_system)
    data = graph_with_library_system.to_dict()
    original = copy.deepcopy(data["nodes"][broken.node_id]["node_data"])

    construction_fails(1)
    once = _load(data).to_dict()
    construction_fails(1)
    twice = _load(once).to_dict()

    assert once["nodes"][broken.node_id]["node_data"] == original
    assert twice["nodes"][broken.node_id]["node_data"] == original


def test_a_moved_stand_in_saves_its_new_position(graph_with_library_system, construction_fails):
    broken, _ = _two_nodes(graph_with_library_system)
    data = graph_with_library_system.to_dict()
    original = data["nodes"][broken.node_id]["node_data"]
    construction_fails(1)
    graph = _load(data)

    graph.move_node(broken.node_id, 640.0, 320.0)
    saved = _saved(graph, broken.node_id)

    assert position_of(saved) == (640.0, 320.0)
    for key in ("ports", "identity", "library", "store"):
        assert saved["node_data"][key] == original[key]


def test_an_unknown_class_keeps_its_settings_and_identity(graph_with_library_system):
    from haybale_testing.nodes.testbed.settings_node import SettingsNode

    wrapper = graph_with_library_system.create_node_wrapper(
        SettingsNode.class_identity.registry_key, position=(1.0, 2.0)
    )
    data = graph_with_library_system.to_dict()
    original = copy.deepcopy(data["nodes"][wrapper.node_id]["node_data"])
    assert set(original["settings"]) - {"props"}, "the test node declares its own settings bag"
    data["nodes"][wrapper.node_id]["registry_key"] = _UNKNOWN

    graph = _load(data)
    saved = _saved(graph, wrapper.node_id)

    assert graph.node_wrappers[wrapper.node_id].is_stand_in
    assert saved["registry_key"] == _UNKNOWN
    assert saved["node_data"] == original


def test_a_stand_in_keeps_its_own_copy_of_the_loaded_data(graph_with_library_system, construction_fails):
    broken, _ = _two_nodes(graph_with_library_system)
    data = graph_with_library_system.to_dict()
    original = copy.deepcopy(data["nodes"][broken.node_id]["node_data"])
    construction_fails(1)
    graph = _load(data)

    data["nodes"][broken.node_id]["node_data"]["ports"].clear()

    assert _saved(graph, broken.node_id)["node_data"] == original


def test_an_unknown_class_keeps_its_own_copy_of_the_loaded_data(graph_with_library_system):
    wrapper = graph_with_library_system.create_node_wrapper(_print_key(), position=(1.0, 2.0))
    data = graph_with_library_system.to_dict()
    original = copy.deepcopy(data["nodes"][wrapper.node_id]["node_data"])
    data["nodes"][wrapper.node_id]["registry_key"] = _UNKNOWN
    graph = _load(data)

    data["nodes"][wrapper.node_id]["node_data"]["ports"].clear()

    assert _saved(graph, wrapper.node_id)["node_data"] == original


def test_a_failed_rebuild_keeps_the_values_for_the_fix(graph_with_library_system, construction_fails):
    from haybale_testing.nodes.testbed.print_node import TestPrintNode

    graph = graph_with_library_system
    wrapper = graph.create_node_wrapper(_print_key(), position=(10.0, 10.0))
    wrapper.node.ports["message"].set_value("kept")
    wrapper.move(640.0, 320.0)

    construction_fails(1)
    _reset(graph, wrapper.node_id)
    assert wrapper.is_stand_in
    assert "message" in wrapper.node.ports

    _reset(graph, wrapper.node_id)

    assert isinstance(wrapper.node, TestPrintNode)
    assert not wrapper.is_stand_in
    assert wrapper._stand_in_data is None
    assert wrapper.node.ports["message"].get_value() == "kept"
    assert wrapper.node.props.get_position() == (640.0, 320.0)


def _loaded_with_a_stand_in(graph_with_library_system, construction_fails):
    broken, _ = _two_nodes(graph_with_library_system)
    data = graph_with_library_system.to_dict()
    original = copy.deepcopy(data["nodes"][broken.node_id]["node_data"])
    construction_fails(1)
    return _load(data), broken.node_id, original


def test_undoing_the_delete_of_a_stand_in_restores_its_data(
    graph_with_library_system, library_system, construction_fails
):
    from haywire.core.graph.editor import Editor

    graph, node_id, original = _loaded_with_a_stand_in(graph_with_library_system, construction_fails)
    editor = Editor(graph, library_system.get_node_factory())
    assert editor.remove_elements([node_id], [])
    assert node_id not in graph.node_wrappers

    construction_fails(1)  # the class is still broken when the delete is undone
    editor.undo()

    assert graph.node_wrappers[node_id].is_stand_in
    assert _saved(graph, node_id)["node_data"] == original


def test_a_pasted_stand_in_carries_the_original_data(
    graph_with_library_system, library_system, construction_fails
):
    from haywire.core.graph.clipboard import build_clipboard_payload
    from haywire.core.graph.editor import Editor

    graph, node_id, original = _loaded_with_a_stand_in(graph_with_library_system, construction_fails)
    editor = Editor(graph, library_system.get_node_factory())
    payload = build_clipboard_payload(graph, [node_id], [], "session")

    construction_fails(1)
    pasted = editor.paste_clipboard(payload, 500.0, 500.0)

    assert pasted is not None
    new_id = pasted[0][0]
    saved = _saved(graph, new_id)["node_data"]
    assert graph.node_wrappers[new_id].is_stand_in
    for key in ("ports", "identity", "library", "store"):
        assert saved[key] == original[key]


def test_a_node_that_cannot_serialize_still_rebuilds(graph_with_library_system, monkeypatch):
    """A stand-in's data is captured before every rebuild; a failed capture must not stop one."""
    from haybale_testing.nodes.testbed.print_node import TestPrintNode

    graph = graph_with_library_system
    wrapper = graph.create_node_wrapper(_print_key(), position=(10.0, 10.0))
    old = wrapper.node

    def broken_to_dict(self, include_data=True):
        raise RuntimeError("cannot serialize")

    monkeypatch.setattr(TestPrintNode, "_to_dict", broken_to_dict)
    _reset(graph, wrapper.node_id)

    assert wrapper.node is not old
    assert isinstance(wrapper.node, TestPrintNode)
