"""Editor value verbs: recorded as value steps, merged per owner, no-ops add nothing."""

from __future__ import annotations

from collections.abc import Iterator
from typing import Any, cast

import pytest

from haywire.core.graph.base import BaseGraph
from haywire.core.graph.editor import Editor
from haywire.core.graph.scheduler import SyncScheduler
from haywire.core.graph.setting_owner import SettingOwner, setting_owner
from haywire.core.undo.config import UndoConfig
from haywire.core.undo.history_manager import HistoryManager

pytestmark = pytest.mark.integration

PORT_NODE_KEY = "haybale-example:node:MathOP"
SETTINGS_NODE_KEY = "haybale-testing:node:SettingsNode"


@pytest.fixture
def graph_and_editor(library_system) -> Iterator[tuple[BaseGraph, Editor]]:
    graph = BaseGraph("g", validation_scheduler=SyncScheduler())
    # Default merging and grouping on: the merge rules are what is under test.
    config = UndoConfig(enable_auto_grouping=True, enable_action_merging=True)
    yield graph, Editor(graph, library_system.get_node_factory(), undo_config=config)
    graph.cleanup()


def _history(editor: Editor) -> list[Any]:
    manager = cast(HistoryManager, editor.history_manager)
    manager._flush_pending_actions()
    return list(manager.history)


def _node(editor: Editor, key: str = PORT_NODE_KEY):
    wrapper = editor.create_wrapper(key)
    assert wrapper is not None
    editor.history_manager.clear()
    return wrapper


def test_a_recorded_write_is_one_undo_step(graph_and_editor):
    _, editor = graph_and_editor
    wrapper = _node(editor)
    port = wrapper.node.ports["value_a"]
    before = port.get_value()

    assert editor.set_property(wrapper.node_id, "value_a", before + 1) is True
    assert editor.undo() is True

    assert port.get_value() == before
    assert editor.can_undo() is False


def test_recorded_writes_with_one_owner_amend(graph_and_editor):
    _, editor = graph_and_editor
    wrapper = _node(editor)
    port = wrapper.node.ports["value_a"]
    before = port.get_value()
    route = object()

    for step in (1.0, 2.0, 3.0):
        assert editor.set_property(wrapper.node_id, "value_a", before + step, merge_owner=route) is True
    assert port.get_value() == before + 3.0

    assert editor.undo() is True
    assert port.get_value() == before
    assert editor.can_undo() is False


def test_an_unrecorded_no_op_adds_no_fence(graph_and_editor):
    _, editor = graph_and_editor
    wrapper = _node(editor)
    current = wrapper.node.ports["value_a"].data.get_own_value()
    before = len(_history(editor))

    assert editor.set_property(wrapper.node_id, "value_a", current, record=False) is True

    assert len(_history(editor)) == before


def test_an_unrecorded_change_still_fences(graph_and_editor):
    from haywire.core.undo.history_manager import Fence

    _, editor = graph_and_editor
    wrapper = _node(editor)
    current = wrapper.node.ports["value_a"].data.get_own_value()

    assert editor.set_property(wrapper.node_id, "value_a", current + 1, record=False) is True

    assert isinstance(_history(editor)[-1], Fence)
    assert editor.can_undo() is False


def test_a_recorded_no_op_adds_no_step(graph_and_editor):
    _, editor = graph_and_editor
    wrapper = _node(editor)
    current = wrapper.node.ports["value_a"].data.get_own_value()

    assert editor.set_property(wrapper.node_id, "value_a", current, record=True) is True

    assert editor.can_undo() is False


def _two_settings_owners(editor: Editor) -> list[SettingOwner]:
    owners = []
    for _ in range(2):
        wrapper = _node(editor, SETTINGS_NODE_KEY)
        owner = setting_owner(editor.graph, wrapper.node.example)
        assert owner is not None
        owners.append(owner)
    return owners


def test_set_settings_is_one_step_over_every_owner(graph_and_editor):
    graph, editor = graph_and_editor
    owners = _two_settings_owners(editor)
    bags: list[Any] = [o.resolve(graph) for o in owners]
    before = [b.persistent_value for b in bags]

    assert editor.set_settings(owners, "persistent_value", 9.5) is True
    assert [b.persistent_value for b in bags] == [9.5, 9.5]

    assert editor.undo() is True
    assert [b.persistent_value for b in bags] == before
    assert editor.can_undo() is False


def test_reset_settings_is_one_step(graph_and_editor):
    graph, editor = graph_and_editor
    owners = _two_settings_owners(editor)
    bags: list[Any] = [o.resolve(graph) for o in owners]
    assert editor.set_settings(owners, "persistent_value", 9.5, record=False) is True

    assert editor.reset_settings(owners, "persistent_value") is True
    assert [b.persistent_value for b in bags] != [9.5, 9.5]

    assert editor.undo() is True
    assert [b.persistent_value for b in bags] == [9.5, 9.5]
