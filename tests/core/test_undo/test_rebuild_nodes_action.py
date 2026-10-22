"""Reset is one undoable step: the node is rebuilt fresh, and Undo puts it back exactly."""

from __future__ import annotations

from typing import Any

import pytest

from haywire.core.graph.base import BaseGraph
from haywire.core.graph.editor import Editor
from haywire.core.types.enums import PortType
from haywire.core.undo.actions.graph_actions import RebuildNodesAction
from haywire.core.undo.base_action import ActionBase
from haywire.core.undo.config import UndoConfig
from haywire.core.undo.history_manager import HistoryManager

from tests.conftest import make_edge

pytestmark = [pytest.mark.integration]


def _settings_key() -> str:
    from haybale_testing.nodes.testbed.settings_node import SettingsNode

    return SettingsNode.class_identity.registry_key


def _print_key() -> str:
    from haybale_testing.nodes.testbed.print_node import TestPrintNode

    return TestPrintNode.class_identity.registry_key


@pytest.fixture
def editor(graph_with_library_system: BaseGraph, library_system) -> Editor:
    # Grouping off: each step is in the history at once, so its name can be read.
    return Editor(
        graph_with_library_system,
        library_system.get_node_factory(),
        undo_config=UndoConfig(enable_auto_grouping=False),
    )


def _configured(editor: Editor) -> tuple[Any, Any]:
    graph = editor.graph
    settings: Any = graph.create_node_wrapper(_settings_key(), position=(10.0, 10.0))
    settings.node.example.example_int = 7
    assert editor.promote_setting(settings.node_id, "example", "example_int", PortType.INLET)
    printer: Any = graph.create_node_wrapper(_print_key(), position=(300.0, 10.0))
    printer.node.ports["message"].set_value("kept")
    graph._validation.force_immediate_validation()
    return settings, printer


class _Counting(ActionBase):
    def __init__(self) -> None:
        super().__init__(description="counting")
        self.executed = 0
        self.undone = 0

    def _execute_impl(self) -> None:
        self.executed += 1

    def _undo_impl(self) -> None:
        self.undone += 1


def test_record_executed_adds_an_undoable_step_without_running_it():
    history = HistoryManager(UndoConfig(enable_auto_grouping=False))
    action = _Counting()

    history.record_executed(action)

    assert action.executed == 0
    assert history.can_undo()
    assert history.undo()
    assert action.undone == 1
    assert history.redo()
    assert action.executed == 1


def test_a_reset_is_one_undoable_step(editor):
    settings, printer = _configured(editor)

    assert editor.reset_nodes([settings.node_id, printer.node_id])
    editor.graph._validation.force_immediate_validation()

    assert settings.node.example.example_int == 3
    assert "example.example_int" not in settings.node.ports
    assert printer.node.ports["message"].get_value() == "Hello, World!"
    assert editor.history_manager.get_undo_description() == "Reset 2 nodes"

    assert editor.undo()
    editor.graph._validation.force_immediate_validation()

    assert settings.node.example.example_int == 7
    assert settings.node.example._is_promoted("example_int")
    assert "example.example_int" in settings.node.ports
    assert printer.node.ports["message"].get_value() == "kept"

    assert editor.redo()
    editor.graph._validation.force_immediate_validation()

    assert settings.node.example.example_int == 3
    assert printer.node.ports["message"].get_value() == "Hello, World!"


def test_undoing_a_reset_brings_an_edge_on_a_promoted_port_back_to_life(editor):
    graph = editor.graph
    settings, _ = _configured(editor)
    assert editor.promote_setting(settings.node_id, "example", "example_float", PortType.INLET)
    source = graph.create_node_wrapper("haybale-testing:node:TestAddFloatNode", position=(10.0, 400.0))
    graph._validation.force_immediate_validation()
    edge = make_edge(graph, source.node_id, "result", settings.node_id, "example.example_float")
    graph._validation.force_immediate_validation()
    assert edge.is_valid()

    editor.reset_nodes([settings.node_id])
    graph._validation.force_immediate_validation()
    assert not graph.edge_wrappers[edge.edge_id].is_valid()

    editor.undo()
    graph._validation.force_immediate_validation()

    assert graph.edge_wrappers[edge.edge_id].is_valid()


def test_rebuild_with_data_restores_exactly(editor):
    graph = editor.graph
    _, printer = _configured(editor)
    data = printer.serialize()["node_data"]
    printer.node.ports["message"].set_value("changed")

    graph.request_node_rebuild(printer.node_id, data)
    graph._validation.force_immediate_validation()

    assert printer.serialize()["node_data"] == data


def test_undo_of_a_rebuild_whose_node_is_gone_fails_cleanly(editor):
    graph = editor.graph
    _, printer = _configured(editor)
    action = RebuildNodesAction.capture(graph, [printer.node_id], "Reset Print")
    editor.history_manager.record_executed(action)

    graph.remove_node_wrapper(printer)

    assert editor.undo() is False
    assert editor.history_manager.can_redo() is False
