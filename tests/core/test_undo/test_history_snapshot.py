"""History read API (``snapshot()``, step origins, ``last_move()``, listeners) and origin-stamped editors.

The actions are fakes: the manager's bookkeeping is under test, so a real graph would only add noise.
"""

from types import SimpleNamespace
from typing import Any, cast

import pytest

from haywire.core.access import LevelMode
from haywire.core.graph.edit_route import EditRoute
from haywire.core.graph.editor import Editor
from haywire.core.undo.base_action import ActionBase
from haywire.core.undo.config import UndoConfig
from haywire.core.undo.history_manager import HistoryManager
from haywire.core.undo.no_op_history_manager import NoOpHistoryManager
from haywire.core.undo.origin import StepOrigin

pytestmark = pytest.mark.unit

ALICE = StepOrigin("alice", "a1", "canvas")
BOB = StepOrigin("bob", "b2", "canvas")


class _Step(ActionBase):
    """A fake step on ``graph``; merges with another mergeable step when ``mergeable``."""

    def __init__(self, name: str, graph: Any = None, mergeable: bool = False):
        super().__init__(name)
        self.graph = graph
        self.mergeable = mergeable

    def _execute_impl(self) -> None:
        pass

    def _undo_impl(self) -> None:
        pass

    def can_merge(self, other) -> bool:
        return self.mergeable and isinstance(other, _Step) and other.mergeable

    def merge(self, other):
        merged = _Step(f"{self.description}+{other.description}", self.graph, mergeable=True)
        merged.mark_executed()
        return merged


class _Composite(ActionBase):
    """A fake step with no graph of its own, holding sub-actions that have one."""

    def __init__(self, actions: list):
        super().__init__("composite")
        self.actions = actions

    def _execute_impl(self) -> None:
        pass

    def _undo_impl(self) -> None:
        pass


def _plain() -> HistoryManager:
    return HistoryManager(UndoConfig(enable_auto_grouping=False, enable_action_merging=False))


def _kinds(history: HistoryManager) -> list[tuple[str, str]]:
    return [(row.kind, row.description) for row in history.snapshot()]


# ---------------------------------------------------------------------------
# StepOrigin
# ---------------------------------------------------------------------------


def test_origin_label_names_principal_and_session():
    assert ALICE.label == "alice · a1"
    assert StepOrigin(None, None, "farmhand").label == "Farmhand"
    assert StepOrigin("carol", None, "farmhand").label == "Farmhand · carol"
    assert StepOrigin(None, None, "system").label == "System"


# ---------------------------------------------------------------------------
# snapshot()
# ---------------------------------------------------------------------------


def test_snapshot_lists_steps_oldest_first_with_their_origin():
    history = _plain()
    history.add_action(_Step("one"), origin=ALICE)
    history.add_action(_Step("two"), origin=BOB)
    history.add_action(_Step("three"))
    history.add_fence()

    rows = history.snapshot()

    assert [(r.kind, r.description) for r in rows] == [
        ("step", "one"),
        ("step", "two"),
        ("step", "three"),
        ("fence", ""),
    ]
    assert [r.origin for r in rows] == [ALICE, BOB, None, None]
    assert rows[0].action_type == "_Step"
    assert rows[3].undone is False


def test_a_fence_lasts_only_until_the_next_step():
    history = _plain()
    history.add_action(_Step("one"))
    history.add_fence()
    history.add_action(_Step("two"))

    assert _kinds(history) == [("step", "one"), ("step", "two")]


def test_snapshot_marks_the_redo_branch_undone():
    history = _plain()
    history.add_action(_Step("one"))
    history.add_action(_Step("two"))
    history.undo()

    assert [(r.description, r.undone) for r in history.snapshot()] == [("one", False), ("two", True)]


def test_snapshot_lists_pending_steps_last_and_changes_nothing():
    history = HistoryManager(
        UndoConfig(enable_auto_grouping=True, enable_action_merging=False, grouping_time_window_ms=60_000)
    )
    history.add_fence()
    history.add_action(_Step("one"), origin=ALICE)
    history.add_action(_Step("two"), origin=BOB)

    rows = history.snapshot()

    assert [(r.description, r.pending) for r in rows if r.kind == "step"] == [("one", True), ("two", True)]
    assert len(history._pending_actions) == 2


def test_a_flushed_group_lists_its_children_with_their_own_origins():
    history = HistoryManager(
        UndoConfig(enable_auto_grouping=True, enable_action_merging=False, grouping_time_window_ms=60_000)
    )
    history.add_fence()
    history.add_action(_Step("one"), origin=ALICE)
    history.add_action(_Step("two"), origin=BOB)
    history.add_fence()

    assert [row.kind for row in history.snapshot()] == ["group", "fence"]
    group = history.snapshot()[0]

    assert group.kind == "group"
    assert group.description == "Group of 2 actions"
    assert group.origin == ALICE
    assert [(c.description, c.origin) for c in group.children] == [("one", ALICE), ("two", BOB)]


def test_a_merged_step_keeps_the_earlier_steps_origin():
    # Merging rewrites only the pending tail, so grouping holds the steps pending.
    history = HistoryManager(
        UndoConfig(enable_auto_grouping=True, enable_action_merging=True, grouping_time_window_ms=60_000)
    )
    history.add_fence()
    history.add_action(_Step("a", mergeable=True), origin=ALICE)
    calls: list[int] = []
    history.add_listener(lambda: calls.append(1))
    history.add_action(_Step("b", mergeable=True), origin=BOB)

    steps = [r for r in history.snapshot() if r.kind == "step"]

    assert [(r.description, r.origin) for r in steps] == [("a+b", ALICE)]
    assert len(history._origins) == 1
    assert calls == []  # a merge lists no new row


def test_snapshot_names_the_graph_a_step_mutates_including_through_sub_actions():
    graph = object()
    history = _plain()
    history.add_action(_Step("own", graph=graph))
    history.add_action(_Composite([_Step("inner", graph=graph)]))
    history.add_action(_Step("none"))

    assert [r.graph for r in history.snapshot()] == [graph, graph, None]


def test_snapshot_shows_the_merge_key_only_while_the_step_can_be_amended():
    history = _plain()
    step = _Step("value")
    cast(Any, step).changed = True
    cast(Any, step).value_key = lambda: ("node", "x")
    cast(Any, step).last_write = 0.0
    owner = object()
    history.add_value_action(step, owner)

    assert history.snapshot()[0].merge_key == (("node", "x"), owner)

    history.add_fence()
    assert history.snapshot()[0].merge_key is None


def test_dropped_steps_leave_no_origin_behind():
    history = _plain()
    history.add_action(_Step("one"), origin=ALICE)
    history.add_action(_Step("two"), origin=BOB)
    history.undo()
    history.add_action(_Step("three"), origin=ALICE)  # ends the redo branch

    assert len(history._origins) == 2
    history.clear()
    assert history._origins == {}
    assert history.snapshot() == []


def test_eviction_drops_the_evicted_steps_origin():
    history = HistoryManager(
        UndoConfig(max_actions=1, enable_auto_grouping=False, enable_action_merging=False)
    )
    history.add_action(_Step("one"), origin=ALICE)
    history.add_action(_Step("two"), origin=BOB)

    assert [r.origin for r in history.snapshot()] == [BOB]
    assert len(history._origins) == 1


# ---------------------------------------------------------------------------
# last_move()
# ---------------------------------------------------------------------------


def test_last_move_names_who_undid_and_redid():
    history = _plain()
    history.add_action(_Step("one"), origin=ALICE)
    assert history.last_move() is None

    history.undo(origin=BOB)
    move = history.last_move()
    assert move is not None
    assert (move.direction, move.origin) == ("undo", BOB)

    history.redo(origin=ALICE)
    move = history.last_move()
    assert move is not None
    assert (move.direction, move.origin) == ("redo", ALICE)

    history.clear()
    assert history.last_move() is None


def test_a_failed_undo_is_no_move():
    history = _plain()
    assert history.undo(origin=BOB) is False
    assert history.last_move() is None


# ---------------------------------------------------------------------------
# Listeners
# ---------------------------------------------------------------------------


def test_listener_fires_on_every_change_snapshot_would_show():
    history = _plain()
    calls: list[int] = []
    listener = lambda: calls.append(1)  # noqa: E731
    history.add_listener(listener)
    history.add_listener(listener)  # added once

    history.add_action(_Step("one"))
    history.add_fence()
    history.undo()
    history.redo()
    history.record_executed(_Step("two"))
    history.clear()
    assert len(calls) == 6

    history.remove_listener(listener)
    history.remove_listener(listener)  # ignored
    history.add_action(_Step("three"))
    assert len(calls) == 6


def test_listener_does_not_fire_on_an_amend_or_an_unchanged_write():
    history = _plain()
    owner = object()

    def value_step(changed: bool = True) -> _Step:
        step = _Step("value")
        cast(Any, step).changed = changed
        cast(Any, step).value_key = lambda: ("node", "x")
        cast(Any, step).last_write = 1e18  # always within the idle window
        cast(Any, step).amend_from = lambda newer: None
        return step

    history.add_value_action(value_step(), owner)
    calls: list[int] = []
    history.add_listener(lambda: calls.append(1))

    history.add_value_action(value_step(), owner)
    history.add_value_action(value_step(changed=False), owner)

    assert calls == []
    assert len(history.snapshot()) == 1


def test_a_raising_listener_does_not_stop_the_others():
    history = _plain()
    calls: list[int] = []

    def broken() -> None:
        raise RuntimeError("listener")

    history.add_listener(broken)
    history.add_listener(lambda: calls.append(1))
    assert history.add_action(_Step("one")) is True
    assert calls == [1]


def test_the_no_op_history_reads_empty():
    history = NoOpHistoryManager()
    history.add_listener(lambda: None)
    history.remove_listener(lambda: None)
    assert history.snapshot() == []
    assert history.last_move() is None


# ---------------------------------------------------------------------------
# Editor.with_origin and EditRoute(origin=)
# ---------------------------------------------------------------------------


def _editor() -> Editor:
    graph = cast(Any, SimpleNamespace(graph_id="g1"))
    return Editor(
        graph, cast(Any, None), UndoConfig(enable_auto_grouping=False, enable_action_merging=False)
    )


def test_with_origin_shares_graph_and_history_and_credits_its_steps():
    editor = _editor()
    mine = editor.with_origin(ALICE)

    assert mine is not editor
    assert mine.origin == ALICE
    assert editor.origin is None
    assert mine.graph is editor.graph
    assert mine.history_manager is editor.history_manager
    assert editor.with_origin(None) is editor
    assert mine.with_origin(ALICE) is mine
    # A sibling leaves the history's error context alone.
    assert cast(HistoryManager, editor.history_manager).error_context == {"graph_id": "g1"}

    assert mine._apply(_Step("one"), record=True)
    mine.undo()
    history = cast(HistoryManager, editor.history_manager)
    assert history.snapshot()[0].origin == ALICE
    move = history.last_move()
    assert move is not None
    assert move.origin == ALICE


def test_a_route_with_an_origin_hands_out_a_stamped_editor_that_follows_the_level():
    level = SimpleNamespace(editor=_editor())
    route = EditRoute(lambda: level.editor, lambda: LevelMode.EDIT, origin=BOB)

    stamped = route.editor()
    assert stamped is not None
    assert stamped.origin == BOB
    assert route.editor() is stamped

    level.editor = _editor()
    swapped = route.editor()
    assert swapped is not None
    assert swapped is not stamped
    assert swapped.graph is level.editor.graph
    assert swapped.origin == BOB


def test_a_route_without_an_origin_hands_out_the_level_editor_itself():
    level = SimpleNamespace(editor=_editor())
    route = EditRoute(lambda: level.editor, lambda: LevelMode.EDIT)
    assert route.editor() is level.editor


def test_a_subgraph_route_keeps_the_hosts_origin():
    level = SimpleNamespace(editor=_editor())
    route = EditRoute(lambda: level.editor, lambda: LevelMode.EDIT, origin=ALICE)
    definition = cast(Any, SimpleNamespace(graph_id="inner"))

    inner = route.for_subgraph(definition).editor()

    assert inner is not None
    assert inner.origin == ALICE
    assert inner.graph is definition
    assert inner.history_manager is level.editor.history_manager
