"""Value steps: change reporting, merge keys and amending, on a held graph with no ``HistoryManager``."""

from __future__ import annotations

from collections.abc import Iterator
from typing import Any, cast

import pytest

from haywire.core.graph.base import BaseGraph
from haywire.core.graph.scheduler import ThreadingTimerScheduler
from haywire.core.graph.setting_owner import SettingOwner, setting_owner
from haywire.core.graph.types import ChangeReason
from haywire.core.undo.actions.graph_actions import (
    VALUE_EDIT_MERGE_IDLE_S,
    ResetSettingAction,
    ResetSettingsAction,
    SetPropertyAction,
    SetSettingAction,
    SetSettingsAction,
)

from tests.conftest import make_node

pytestmark = pytest.mark.integration

_SETTINGS_NODE = "haybale-testing:node:SettingsNode"
_PORT_NODE = "haybale-example:node:MathOP"
_FIELD = "persistent_value"


@pytest.fixture
def held_graph(library_system) -> Iterator[BaseGraph]:
    """A graph whose debounce never fires on its own, so a test drains it explicitly."""
    graph = BaseGraph(
        filestem="g", validation_scheduler=ThreadingTimerScheduler(), validation_delay_ms=60_000
    )
    yield graph
    graph._validation.clear()
    graph.cleanup()


def _settings_node(graph: BaseGraph):
    wrapper = make_node(graph, _SETTINGS_NODE)
    graph._validation.force_immediate_validation()
    owner = setting_owner(graph, cast(Any, wrapper.node).example)
    assert owner is not None
    return wrapper, owner


def test_the_idle_window_is_three_seconds():
    assert VALUE_EDIT_MERGE_IDLE_S == 3.0


def test_a_write_reports_change(held_graph: BaseGraph):
    _, owner = _settings_node(held_graph)

    first = SetSettingAction(held_graph, owner, _FIELD, 5.0)
    first.execute()
    assert first.changed is True

    same = SetSettingAction(held_graph, owner, _FIELD, 5.0)
    same.execute()
    assert same.changed is False

    same.undo()
    assert same.changed is False
    first.undo()
    assert first.changed is True


def test_a_port_write_reports_change(held_graph: BaseGraph):
    wrapper = make_node(held_graph, _PORT_NODE)
    port_id = next(pid for pid, p in wrapper.node.ports.items() if p.is_inlet())
    held_graph._validation.force_immediate_validation()

    first = SetPropertyAction(held_graph, wrapper.node_id, port_id, 42.0)
    first.execute()
    assert first.changed is True

    same = SetPropertyAction(held_graph, wrapper.node_id, port_id, 42.0)
    same.execute()
    assert same.changed is False


def test_amend_keeps_the_first_old_value(held_graph: BaseGraph):
    wrapper, owner = _settings_node(held_graph)
    bag = wrapper.node.example
    bag.persistent_value = 2.0

    a = SetSettingAction(held_graph, owner, _FIELD, 5.0)
    a.execute()
    b = SetSettingAction(held_graph, owner, _FIELD, 8.0)
    b.execute()
    a.amend_from(b)
    assert bag.persistent_value == 8.0  # amending writes nothing

    a.undo()
    assert bag.persistent_value == 2.0
    a.execute()
    assert bag.persistent_value == 8.0


def test_amend_takes_the_newer_last_write(held_graph: BaseGraph):
    _, owner = _settings_node(held_graph)
    a = SetSettingAction(held_graph, owner, _FIELD, 5.0)
    a.execute()
    b = SetSettingAction(held_graph, owner, _FIELD, 8.0)
    b.execute()
    assert b.last_write >= a.last_write > 0.0

    a.amend_from(b)

    assert a.last_write == b.last_write


def test_amend_across_merge_keys_is_refused(held_graph: BaseGraph):
    _, owner = _settings_node(held_graph)
    a = SetSettingAction(held_graph, owner, _FIELD, 5.0)
    b = SetSettingAction(held_graph, owner, _FIELD, 8.0)
    a.merge_key = "one"
    b.merge_key = "two"

    with pytest.raises(ValueError, match="another run"):
        a.amend_from(b)


def test_amend_restores_unset_on_undo(held_graph: BaseGraph):
    wrapper, owner = _settings_node(held_graph)
    bag = wrapper.node.example
    assert bag._is_locally_set(_FIELD) is False

    a = SetSettingAction(held_graph, owner, _FIELD, 5.0)
    a.execute()
    b = SetSettingAction(held_graph, owner, _FIELD, 8.0)
    b.execute()
    a.amend_from(b)
    a.undo()

    assert bag._is_locally_set(_FIELD) is False


def test_amend_a_port_write(held_graph: BaseGraph):
    wrapper = make_node(held_graph, _PORT_NODE)
    port_id = next(pid for pid, p in wrapper.node.ports.items() if p.is_inlet())
    before = wrapper.node.ports[port_id].data.get_own_value()

    a = SetPropertyAction(held_graph, wrapper.node_id, port_id, 3.0)
    a.execute()
    b = SetPropertyAction(held_graph, wrapper.node_id, port_id, 9.0)
    b.execute()
    a.amend_from(b)

    a.undo()
    assert wrapper.node.ports[port_id].data.get_own_value() == before
    a.execute()
    assert wrapper.node.ports[port_id].data.get_own_value() == 9.0


def test_value_keys(held_graph: BaseGraph):
    wrapper, owner = _settings_node(held_graph)
    other = SettingOwner(kind="graph", accessor="meta")

    assert SetPropertyAction(held_graph, "n1", "x", 1).value_key() == ("port", "n1", "x")
    assert SetSettingAction(held_graph, owner, _FIELD, 1).value_key() == ("setting", owner, _FIELD)
    assert SetSettingsAction(held_graph, [owner, other], _FIELD, 1).value_key() == (
        "settings",
        frozenset({owner, other}),
        _FIELD,
    )
    assert ResetSettingAction(held_graph, owner, _FIELD).value_key() is None
    assert ResetSettingsAction(held_graph, [owner], _FIELD).value_key() is None
    assert (
        SetSettingAction(held_graph, owner, _FIELD, 1).value_key()
        == SetSettingAction(held_graph, owner, _FIELD, 2).value_key()
    )


def _three_nodes(graph: BaseGraph):
    nodes = [_settings_node(graph) for _ in range(3)]
    nodes[0][0].node.example.persistent_value = 2.0
    nodes[1][0].node.example.persistent_value = 4.0
    # nodes[2] stays unset
    graph._validation.force_immediate_validation()
    return nodes


def test_a_form_step_writes_every_bag_and_undoes_each(held_graph: BaseGraph):
    nodes = _three_nodes(held_graph)
    owners = [owner for _, owner in nodes]

    step = SetSettingsAction(held_graph, owners, _FIELD, 7.0)
    step.execute()
    assert step.changed is True
    assert [w.node.example.persistent_value for w, _ in nodes] == [7.0, 7.0, 7.0]
    result = held_graph._validation.force_immediate_validation()
    assert result is not None
    assert result.nodes == {w.node_id: ChangeReason.NODE_VALUE_CHANGED for w, _ in nodes}

    step.undo()
    assert [w.node.example.persistent_value for w, _ in nodes[:2]] == [2.0, 4.0]
    assert nodes[2][0].node.example._is_locally_set(_FIELD) is False
    assert step.changed is True


def test_a_form_step_amends_every_child(held_graph: BaseGraph):
    nodes = _three_nodes(held_graph)
    owners = [owner for _, owner in nodes]

    a = SetSettingsAction(held_graph, owners, _FIELD, 7.0)
    a.execute()
    b = SetSettingsAction(held_graph, owners, _FIELD, 9.0)
    b.execute()
    a.amend_from(b)

    a.undo()
    assert [w.node.example.persistent_value for w, _ in nodes[:2]] == [2.0, 4.0]
    assert nodes[2][0].node.example._is_locally_set(_FIELD) is False
    a.execute()
    assert [w.node.example.persistent_value for w, _ in nodes] == [9.0, 9.0, 9.0]


def test_a_form_reset_undoes_each_bag(held_graph: BaseGraph):
    nodes = _three_nodes(held_graph)
    owners = [owner for _, owner in nodes]

    step = ResetSettingsAction(held_graph, owners, _FIELD)
    step.execute()
    assert step.changed is True
    assert all(not w.node.example._is_locally_set(_FIELD) for w, _ in nodes)

    step.undo()
    assert [w.node.example.persistent_value for w, _ in nodes[:2]] == [2.0, 4.0]
    assert nodes[2][0].node.example._is_locally_set(_FIELD) is False
