"""Setting, port-order and propagation actions, and the ``Editor`` verbs that apply them."""

from __future__ import annotations

from collections.abc import Iterator
from typing import Any, cast

import pytest

from haywire.core.graph.base import BaseGraph
from haywire.core.graph.editor import Editor
from haywire.core.graph.properties import GraphProperties
from haywire.core.graph.scheduler import ThreadingTimerScheduler
from haywire.core.graph.setting_owner import SettingOwner, setting_owner
from haywire.core.graph.types import ChangeReason
from haywire.core.types import Propagation
from haywire.core.undo.config import UndoConfig
from haywire.core.undo.history_manager import Fence, HistoryManager

from tests.conftest import make_edge, make_node

pytestmark = pytest.mark.integration

_ADD = "haybale-testing:node:TestAddFloatNode"
_SETTINGS_NODE = "haybale-testing:node:SettingsNode"


@pytest.fixture
def held_graph(library_system) -> Iterator[BaseGraph]:
    """A graph whose debounce never fires on its own, so a test drains it explicitly."""
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


def _drain(graph: BaseGraph):
    return graph._validation.force_immediate_validation()


def _drain_graph_marks(graph: BaseGraph):
    """Run the batch the debounce would: ``force_immediate_validation`` skips a graph-only mark."""
    return graph._validation._validate_batch()


def _probe_key() -> str:
    from haybale_testing.nodes.testbed.visual_probe import VisualProbeNode

    return VisualProbeNode.class_identity.registry_key


def _styled_edge(graph):
    source = make_node(graph, _probe_key(), position=(0, 0))
    sink = make_node(graph, _probe_key(), position=(300, 0))
    edge = make_edge(graph, source.node_id, "note_out", sink.node_id, "note_in")
    graph.force_validation()
    return edge


def _settings_node(graph: BaseGraph):
    wrapper = make_node(graph, _SETTINGS_NODE)
    _drain(graph)
    return wrapper, setting_owner(graph, cast(Any, wrapper.node).example)


def test_owner_round_trips_for_node_graph_and_edge_bags(held_graph: BaseGraph):
    node = make_node(held_graph, _ADD)
    edge = _styled_edge(held_graph)
    assert edge.style is not None

    for bag in (node.node.props, held_graph.props, held_graph.meta, edge.style):
        owner = setting_owner(held_graph, bag)
        assert owner is not None
        assert owner.resolve(held_graph) is bag


def test_a_bag_no_document_saves_has_no_owner(held_graph: BaseGraph):
    assert setting_owner(held_graph, GraphProperties()) is None


def test_a_node_setting_write_marks_the_node(held_graph: BaseGraph, editor: Editor):
    wrapper, owner = _settings_node(held_graph)
    assert owner is not None

    assert editor.set_setting(owner, "persistent_value", 5.0) is True

    result = _drain(held_graph)
    assert result is not None
    assert result.nodes == {wrapper.node_id: ChangeReason.NODE_VALUE_CHANGED}


def test_a_graph_props_write_marks_the_graph(held_graph: BaseGraph, editor: Editor):
    _drain(held_graph)
    owner = SettingOwner(kind="graph", accessor="props")

    assert editor.set_setting(owner, "open_locked", not held_graph.props.open_locked) is True

    result = _drain_graph_marks(held_graph)
    assert result is not None
    assert result.graph is ChangeReason.GRAPH_CONTENT_CHANGED
    assert result.requires_save()


def test_a_meta_write_marks_the_graph(held_graph: BaseGraph, editor: Editor):
    _drain(held_graph)
    owner = SettingOwner(kind="graph", accessor="meta")

    assert editor.set_setting(owner, "label", "Renamed") is True

    result = _drain_graph_marks(held_graph)
    assert result is not None
    assert result.graph is ChangeReason.GRAPH_CONTENT_CHANGED
    assert result.requires_save()


def test_writing_what_is_stored_marks_nothing(held_graph: BaseGraph, editor: Editor):
    wrapper, owner = _settings_node(held_graph)
    assert owner is not None
    assert editor.set_setting(owner, "persistent_value", 5.0) is True
    _drain(held_graph)

    assert editor.set_setting(owner, "persistent_value", 5.0) is True

    assert _drain(held_graph) is None


def test_resetting_a_field_set_to_its_default_marks(held_graph: BaseGraph, editor: Editor):
    """Only the local override changes, not the value: the stored pair still differs."""
    wrapper, owner = _settings_node(held_graph)
    assert owner is not None
    bag = wrapper.node.example
    bag.persistent_value = 5.0
    bag.persistent_value = 1.0  # the default, now set locally
    assert bag._is_locally_set("persistent_value") is True
    _drain(held_graph)

    assert editor.reset_setting(owner, "persistent_value") is True

    assert bag._is_locally_set("persistent_value") is False
    assert bag.persistent_value == 1.0
    result = _drain(held_graph)
    assert result is not None
    assert result.nodes == {wrapper.node_id: ChangeReason.NODE_VALUE_CHANGED}


def test_undo_of_a_first_write_restores_unset(held_graph: BaseGraph, editor: Editor):
    wrapper, owner = _settings_node(held_graph)
    assert owner is not None
    bag = wrapper.node.example

    assert editor.set_setting(owner, "persistent_value", 5.0) is True
    assert editor.undo() is True

    assert bag._is_locally_set("persistent_value") is False
    assert bag.persistent_value == 1.0


def test_undo_of_a_reset_restores_the_local_value(held_graph: BaseGraph, editor: Editor):
    wrapper, owner = _settings_node(held_graph)
    assert owner is not None
    bag = wrapper.node.example
    bag.persistent_value = 5.0

    assert editor.reset_setting(owner, "persistent_value") is True
    assert bag._is_locally_set("persistent_value") is False

    assert editor.undo() is True
    assert bag._is_locally_set("persistent_value") is True
    assert bag.persistent_value == 5.0


def test_an_unknown_field_or_owner_is_refused(held_graph: BaseGraph, editor: Editor):
    _, owner = _settings_node(held_graph)
    assert owner is not None

    assert editor.set_setting(owner, "no_such_field", 1) is False
    assert (
        editor.set_setting(SettingOwner(kind="node", accessor="example", owner_id="gone"), "x", 1) is False
    )
    assert editor.can_undo() is False


def test_an_unrecorded_write_adds_no_step_and_a_fence(held_graph: BaseGraph, editor: Editor):
    wrapper, owner = _settings_node(held_graph)
    assert owner is not None

    assert editor.set_setting(owner, "persistent_value", 5.0, record=False) is True

    assert wrapper.node.example.persistent_value == 5.0
    assert editor.can_undo() is False
    history = cast(HistoryManager, editor.history_manager).history
    assert isinstance(history[-1], Fence)


def test_a_reorder_is_one_undo_step(held_graph: BaseGraph, editor: Editor):
    wrapper = make_node(held_graph, _ADD)
    ports = wrapper.node.ports
    inlets = sorted((pid for pid, p in ports.items() if p.is_inlet()), key=lambda pid: ports[pid].order)
    assert len(inlets) >= 2

    assert editor.reorder_ports(wrapper.node_id, list(reversed(inlets))) is True
    assert sorted(inlets, key=lambda pid: ports[pid].order) == list(reversed(inlets))

    assert editor.undo() is True
    assert sorted(inlets, key=lambda pid: ports[pid].order) == inlets


def test_a_propagation_change_is_one_undo_step(held_graph: BaseGraph, editor: Editor):
    a = make_node(held_graph, _ADD, position=(0, 0))
    b = make_node(held_graph, _ADD, position=(300, 0))
    edge = make_edge(held_graph, a.node_id, "result", b.node_id, "value_a")
    held_graph.force_validation()
    assert edge.propagation is Propagation.EAGER

    assert editor.set_edge_propagation(edge.edge_id, Propagation.LAZY) is True
    assert edge.propagation is Propagation.LAZY

    assert editor.undo() is True
    assert edge.propagation is Propagation.EAGER


def test_a_propagation_change_marks_the_graph_and_undo_marks_again(held_graph: BaseGraph, editor: Editor):
    a = make_node(held_graph, _ADD, position=(0, 0))
    b = make_node(held_graph, _ADD, position=(300, 0))
    edge = make_edge(held_graph, a.node_id, "result", b.node_id, "value_a")
    held_graph.force_validation()
    _drain_graph_marks(held_graph)

    assert editor.set_edge_propagation(edge.edge_id, Propagation.LAZY) is True
    result = _drain_graph_marks(held_graph)
    assert result is not None
    assert result.graph is ChangeReason.GRAPH_CONTENT_CHANGED
    assert result.requires_save()

    assert editor.undo() is True
    result = _drain_graph_marks(held_graph)
    assert result is not None
    assert result.graph is ChangeReason.GRAPH_CONTENT_CHANGED


def test_writing_the_same_propagation_marks_nothing(held_graph: BaseGraph, editor: Editor):
    a = make_node(held_graph, _ADD, position=(0, 0))
    b = make_node(held_graph, _ADD, position=(300, 0))
    edge = make_edge(held_graph, a.node_id, "result", b.node_id, "value_a")
    held_graph.force_validation()
    _drain_graph_marks(held_graph)

    assert editor.set_edge_propagation(edge.edge_id, Propagation.EAGER) is True

    result = _drain_graph_marks(held_graph)
    assert result is None or result.graph is None  # the edge redraws; the graph is not marked
