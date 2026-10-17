"""``HistoryManager.add_value_action``: value writes amend the newest step within a merge run.

Runs with ``UndoConfig()`` defaults (merging and grouping on).
"""

from __future__ import annotations

from collections.abc import Iterator
from typing import Any, cast

import pytest

from haywire.core.graph.base import BaseGraph
from haywire.core.graph.scheduler import ThreadingTimerScheduler
from haywire.core.graph.setting_owner import SettingOwner, setting_owner
from haywire.core.undo.actions.graph_actions import ResetSettingAction, SetSettingAction
from haywire.core.undo.config import UndoConfig
from haywire.core.undo.history_manager import ActionGroup, HistoryManager
from haywire.core.undo.interfaces import IAction

from tests.conftest import make_node

pytestmark = pytest.mark.integration

_SETTINGS_NODE = "haybale-testing:node:SettingsNode"
_FIELD = "persistent_value"


class _PlainAction(IAction):
    """An action with no value-edit attributes, as a pending tail or history tip may be."""

    description = "plain"

    def execute(self) -> None:
        pass

    def undo(self) -> None:
        pass


@pytest.fixture
def held_graph(library_system) -> Iterator[BaseGraph]:
    graph = BaseGraph(
        filestem="g", validation_scheduler=ThreadingTimerScheduler(), validation_delay_ms=60_000
    )
    yield graph
    graph._validation.clear()
    graph.cleanup()


@pytest.fixture
def setup(held_graph: BaseGraph):
    wrapper = make_node(held_graph, _SETTINGS_NODE)
    held_graph._validation.force_immediate_validation()
    owner = setting_owner(held_graph, cast(Any, wrapper.node).example)
    assert owner is not None
    bag = cast(Any, wrapper.node).example
    bag.persistent_value = 2.0
    history = HistoryManager(UndoConfig())
    return held_graph, owner, bag, history, object()


def _write(
    history: HistoryManager, graph: BaseGraph, owner: SettingOwner, value: float, token, field=_FIELD
):
    return history.add_value_action(SetSettingAction(graph, owner, field, value), token)


def _steps(history: HistoryManager) -> int:
    history._flush_pending_actions()
    return sum(1 for i in history.history if type(i).__name__ != "Fence")


def test_same_key_amends_into_one_step(setup):
    graph, owner, bag, history, token = setup
    for value in (5.0, 8.0, 9.0):
        assert _write(history, graph, owner, value, token) is True
    assert bag.persistent_value == 9.0

    assert history.undo() is True
    assert bag.persistent_value == 2.0
    assert history.can_undo() is False


def test_a_run_amends_the_history_tip_after_the_pending_flush(setup):
    graph, owner, bag, history, token = setup
    _write(history, graph, owner, 5.0, token)
    history._flush_pending_actions()
    assert not history._pending_actions
    _write(history, graph, owner, 8.0, token)

    assert _steps(history) == 1
    history.undo()
    assert bag.persistent_value == 2.0


def test_another_field_starts_a_new_step(setup):
    graph, owner, bag, history, token = setup
    _write(history, graph, owner, 5.0, token)
    history._flush_pending_actions()
    _write(history, graph, owner, 6.0, token, field="intensity")

    assert _steps(history) == 2


def test_another_owner_object_starts_a_new_step(setup):
    graph, owner, bag, history, token = setup
    _write(history, graph, owner, 5.0, token)
    history._flush_pending_actions()
    _write(history, graph, owner, 8.0, object())

    assert _steps(history) == 2


def test_idle_gap_starts_a_new_step(setup):
    graph, owner, bag, history, token = setup
    _write(history, graph, owner, 5.0, token)
    history._flush_pending_actions()
    tip = cast(Any, history.history[-1])
    tip.last_write -= 4.0
    _write(history, graph, owner, 8.0, token)

    assert _steps(history) == 2


def test_a_fence_ends_the_run(setup):
    graph, owner, bag, history, token = setup
    _write(history, graph, owner, 5.0, token)
    history.add_fence()
    _write(history, graph, owner, 8.0, token)

    assert _steps(history) == 2


def test_a_write_after_undo_starts_a_new_step(setup):
    graph, owner, bag, history, token = setup
    _write(history, graph, owner, 5.0, token)
    history.undo()
    assert history.can_redo()
    _write(history, graph, owner, 7.0, token)

    assert history.can_redo() is False
    assert _steps(history) == 1
    assert bag.persistent_value == 7.0
    history.undo()
    assert bag.persistent_value == 2.0


def test_a_no_op_keeps_the_redo_branch(setup):
    graph, owner, bag, history, token = setup
    _write(history, graph, owner, 5.0, token)
    history.undo()
    before = list(history.history)

    assert _write(history, graph, owner, 2.0, token) is True
    assert history.can_redo() is True
    assert history.history == before


def test_a_none_owner_never_amends(setup):
    graph, owner, bag, history, token = setup
    _write(history, graph, owner, 5.0, None)
    _write(history, graph, owner, 8.0, None)

    history._flush_pending_actions()
    group = history.history[-1]
    assert isinstance(group, ActionGroup)
    assert len(group.actions) == 2
    history.undo()
    assert bag.persistent_value == 2.0


def test_resets_never_amend(setup):
    graph, owner, bag, history, token = setup
    _write(history, graph, owner, 5.0, token)
    history.add_value_action(ResetSettingAction(graph, owner, _FIELD), token)
    _write(history, graph, owner, 6.0, token)

    assert len(history._pending_actions) == 3


def test_amend_into_a_flushed_group_tail(setup):
    graph, owner, bag, history, token = setup
    history._pending_actions.append(_PlainAction())
    _write(history, graph, owner, 5.0, token)
    history._flush_pending_actions()
    group = history.history[-1]
    assert isinstance(group, ActionGroup)
    _write(history, graph, owner, 8.0, token)

    assert len(group.actions) == 2
    assert _steps(history) == 1
    history.undo()
    assert bag.persistent_value == 2.0


def test_a_write_after_redo_starts_a_new_step(setup):
    graph, owner, bag, history, token = setup
    _write(history, graph, owner, 5.0, token)
    history.undo()
    history.redo()
    assert bag.persistent_value == 5.0
    _write(history, graph, owner, 8.0, token)

    assert _steps(history) == 2
    history.undo()
    assert bag.persistent_value == 5.0
    history.undo()
    assert bag.persistent_value == 2.0
