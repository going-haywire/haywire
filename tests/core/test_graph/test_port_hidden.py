"""Hiding a port's row on its node card: undoable, saved, and an edge keeps its pin."""

from __future__ import annotations

from typing import Any

import pytest

from haywire.core.graph.base import BaseGraph
from haywire.core.graph.editor import Editor
from haywire.core.graph.scheduler import ThreadingTimerScheduler
from haywire.core.graph.types import ChangeReason
from haywire.core.undo.config import UndoConfig

from tests.conftest import make_edge, make_node

pytestmark = pytest.mark.integration

_ADD = "haybale-testing:node:TestAddFloatNode"
#: Its progress bar is a promoted setting (a card row).
_FOR_EACH_FILE = "haybale-core:node:ForEachFileNode"


@pytest.fixture
def held_graph(library_system):
    graph = BaseGraph(
        filestem="g", validation_scheduler=ThreadingTimerScheduler(), validation_delay_ms=60_000
    )
    yield graph
    graph._validation.clear()
    graph.cleanup()


@pytest.fixture
def editor(held_graph: BaseGraph, library_system) -> Editor:
    config = UndoConfig(enable_auto_grouping=False, enable_action_merging=False)
    return Editor(held_graph, library_system.get_node_factory(), undo_config=config)


def test_a_hidden_port_leaves_the_card(held_graph: BaseGraph, editor: Editor):
    node = make_node(held_graph, _ADD).node
    assert editor.set_port_hidden(node.node_id, "value_a", True) is True
    assert "value_a" not in {p.id for p in node.get_visible_ports()}
    assert node.get_hidden_connected_ports(is_inlet=False) == []


def test_hiding_is_one_undo_step_and_marks_the_layout(held_graph: BaseGraph, editor: Editor):
    wrapper = make_node(held_graph, _ADD)
    held_graph._validation.force_immediate_validation()

    editor.set_port_hidden(wrapper.node_id, "value_a", True)
    result = held_graph._validation.force_immediate_validation()
    assert result is not None
    assert result.nodes == {wrapper.node_id: ChangeReason.NODE_LAYOUT_CHANGED}

    editor.undo()
    assert wrapper.node.ports["value_a"].hidden is False
    editor.redo()
    assert wrapper.node.ports["value_a"].hidden is True


def test_a_hidden_linked_port_keeps_its_pin_near_the_title(held_graph: BaseGraph, editor: Editor):
    source = make_node(held_graph, _ADD)
    sink = make_node(held_graph, _ADD)
    make_edge(held_graph, source.node_id, "result", sink.node_id, "value_a")

    editor.set_port_hidden(sink.node_id, "value_a", True)

    assert [p.id for p in sink.node.get_hidden_connected_ports(is_inlet=False)] == ["value_a"]


def test_the_choice_is_saved_with_the_node(held_graph: BaseGraph, editor: Editor):
    wrapper = make_node(held_graph, _ADD)
    editor.set_port_hidden(wrapper.node_id, "value_a", True)
    data: Any = wrapper.node._serialize_ports(include_data=True)

    other = make_node(held_graph, _ADD)
    other.node._deserialize_ports(data)

    assert other.node.ports["value_a"].hidden is True


def test_unchanged_unknown_and_promoted_ports_are_refused(held_graph: BaseGraph, editor: Editor):
    node = make_node(held_graph, _ADD).node
    loop = make_node(held_graph, _FOR_EACH_FILE).node

    assert editor.set_port_hidden(node.node_id, "value_a", False) is False
    assert editor.set_port_hidden(node.node_id, "nope", True) is False
    assert editor.set_port_hidden(loop.node_id, "progress.main", True) is False
    assert loop.ports["progress.main"].hidden is False
    assert editor.can_undo() is False
