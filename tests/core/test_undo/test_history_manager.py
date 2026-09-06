"""HistoryManager: merging, fence accounting, eviction and cleanup contracts.

The actions here are fakes — the manager's own bookkeeping is what is under
test, so a real graph would only add noise. Each fake records execute/undo/
cleanup calls so a test can assert on the sequence the manager produced.
"""

import time
from typing import Any, cast

import pytest

from haywire.core.undo.base_action import ActionBase
from haywire.core.undo.config import UndoConfig
from haywire.core.undo.history_manager import Fence, HistoryManager

pytestmark = pytest.mark.unit


class RecordingAction(ActionBase):
    """A fake action that logs every lifecycle call into a shared list."""

    def __init__(self, name: str, log: list, mergeable: bool = False):
        super().__init__(name)
        self.name = name
        self.log = log
        self.mergeable = mergeable
        self.cleaned = False

    def _execute_impl(self) -> None:
        self.log.append(("exec", self.name))

    def _undo_impl(self) -> None:
        self.log.append(("undo", self.name))

    def cleanup(self) -> None:
        self.cleaned = True
        self.log.append(("cleanup", self.name))

    def can_merge(self, other) -> bool:
        return self.mergeable and isinstance(other, RecordingAction) and other.mergeable

    def merge(self, other):
        if not self.can_merge(other):
            return None
        merged = RecordingAction(f"({self.name}+{other.name})", self.log, mergeable=True)
        merged.mark_executed()
        return merged


def _merging_config(**kw) -> UndoConfig:
    """Config with merging on and auto-grouping on (the studio's shape)."""
    params: dict[str, Any] = dict(max_actions=100, enable_auto_grouping=True, enable_action_merging=True)
    params.update(kw)
    return UndoConfig(**params)


def _plain_config(**kw) -> UndoConfig:
    """Config with grouping and merging off, so one action is one history item."""
    params: dict[str, Any] = dict(max_actions=100, enable_auto_grouping=False, enable_action_merging=False)
    params.update(kw)
    return UndoConfig(**params)


def _names(items) -> list[str]:
    """The ``name`` of each history/pending item.

    ``name`` is not on the ``IAction`` protocol — it belongs to the concrete
    actions these tests build — so cast rather than widen the protocol to
    suit a test.
    """
    return [cast(Any, item).name for item in items]


# ---------------------------------------------------------------------------
# Merging
# ---------------------------------------------------------------------------


def test_merging_happens_on_two_rapid_compatible_actions():
    """The merge window must be reachable from a cold manager.

    Regression: ``_last_merge_time`` started at 0.0 and was only ever written
    by a merge, so the window check ``(now - 0.0)*1000 > 100`` rejected every
    candidate and merging could never fire at all.
    """
    log: list = []
    h = HistoryManager(_merging_config())

    h.add_action(RecordingAction("a", log, mergeable=True))
    h.add_action(RecordingAction("b", log, mergeable=True))

    h._flush_pending_actions()
    assert _names(h.history) == ["(a+b)"]


def test_merged_action_can_be_undone():
    """A merged action stands for work already applied, so undo must reverse it.

    Regression: ``merge()`` returns a freshly constructed action whose
    ``_executed`` was False, so ``ActionBase.undo`` raised, ``undo()`` swallowed
    it and returned False without moving ``current_index`` — wedging the stack.
    """
    log: list = []
    h = HistoryManager(_merging_config())

    h.add_action(RecordingAction("a", log, mergeable=True))
    h.add_action(RecordingAction("b", log, mergeable=True))
    h._flush_pending_actions()

    assert h.undo() is True
    assert ("undo", "(a+b)") in log


def test_undo_stack_does_not_wedge_after_a_merge():
    """Every action below a merged one stays reachable."""
    log: list = []
    h = HistoryManager(_merging_config())

    h.add_action(RecordingAction("first", log))
    h.add_fence()
    h.add_action(RecordingAction("a", log, mergeable=True))
    h.add_action(RecordingAction("b", log, mergeable=True))
    h._flush_pending_actions()

    assert h.undo() is True  # the merged action
    assert h.undo() is True  # the action underneath it
    assert h.can_undo() is False
    assert [entry for entry in log if entry[0] == "undo"] == [
        ("undo", "(a+b)"),
        ("undo", "first"),
    ]


def test_merge_replaced_action_is_cleaned_up():
    """The action the merge superseded is discarded, so it must be cleaned up."""
    log: list = []
    h = HistoryManager(_merging_config())

    first = RecordingAction("a", log, mergeable=True)
    second = RecordingAction("b", log, mergeable=True)
    h.add_action(first)
    h.add_action(second)

    assert first.cleaned is True
    assert second.cleaned is True


def test_merge_does_not_fire_outside_the_time_window():
    """Two compatible actions far apart in time stay separate actions."""
    log: list = []
    h = HistoryManager(_merging_config(merge_time_window_ms=10))

    first = RecordingAction("a", log, mergeable=True)
    second = RecordingAction("b", log, mergeable=True)
    h.add_action(first)
    time.sleep(0.05)
    h.add_action(second)

    assert _names(h._pending_actions) == ["a", "b"]
    assert first.cleaned is False
    assert second.cleaned is False


def test_incompatible_actions_are_not_merged():
    log: list = []
    h = HistoryManager(_merging_config())

    h.add_action(RecordingAction("a", log, mergeable=False))
    h.add_action(RecordingAction("b", log, mergeable=False))

    assert _names(h._pending_actions) == ["a", "b"]


# ---------------------------------------------------------------------------
# History limits
# ---------------------------------------------------------------------------


def test_fences_do_not_count_against_max_actions():
    """The user's limit counts undoable actions, not the fences between them.

    Regression: the cap compared ``len(self.history)``, which includes fences.
    Canvas drags emit two fences per gesture, so real undo steps were evicted
    at a fraction of the configured limit.
    """
    log: list = []
    h = HistoryManager(_plain_config(max_actions=3))

    for i in range(3):
        h.add_action(RecordingAction(f"a{i}", log))
        h.add_fence()

    action_names = _names(i for i in h.history if not isinstance(i, Fence))
    assert action_names == ["a0", "a1", "a2"]
    assert [entry for entry in log if entry[0] == "cleanup"] == []


def test_actions_beyond_the_limit_are_evicted_and_cleaned_up():
    log: list = []
    h = HistoryManager(_plain_config(max_actions=2))

    actions = [RecordingAction(f"a{i}", log) for i in range(4)]
    for action in actions:
        h.add_action(action)

    assert _names(i for i in h.history if not isinstance(i, Fence)) == ["a2", "a3"]
    assert actions[0].cleaned is True
    assert actions[1].cleaned is True
    assert actions[2].cleaned is False
    assert actions[3].cleaned is False


def test_current_index_survives_eviction():
    """Eviction must leave current_index pointing at the same logical action."""
    log: list = []
    h = HistoryManager(_plain_config(max_actions=2))

    for i in range(4):
        h.add_action(RecordingAction(f"a{i}", log))

    assert h.undo() is True
    assert h.undo() is True
    assert h.can_undo() is False
    assert [entry for entry in log if entry[0] == "undo"] == [
        ("undo", "a3"),
        ("undo", "a2"),
    ]


def test_fences_alone_do_not_grow_history_without_bound():
    """A gesture that produces no action must not leave a fence behind forever.

    Regression: ``_maintain_history_limits`` ran only from ``add_action``, so
    fences accumulated unboundedly across empty click-drag gestures.
    """
    log: list = []
    h = HistoryManager(_plain_config(max_actions=3))

    h.add_action(RecordingAction("a", log))
    for _ in range(50):
        h.add_fence()

    assert len(h.history) < 10


# ---------------------------------------------------------------------------
# Redo-branch discard
# ---------------------------------------------------------------------------


def test_discarded_redo_branch_is_cleaned_up():
    log: list = []
    h = HistoryManager(_plain_config())

    keep = RecordingAction("keep", log)
    discarded = RecordingAction("discarded", log)
    h.add_action(keep)
    h.add_action(discarded)
    h.undo()

    h.add_action(RecordingAction("new", log))

    assert discarded.cleaned is True
    assert keep.cleaned is False


def test_clear_cleans_pending_and_history():
    log: list = []
    h = HistoryManager(_merging_config())

    flushed = RecordingAction("flushed", log)
    h.add_action(flushed)
    h.add_fence()
    pending = RecordingAction("pending", log)
    h.add_action(pending)

    h.clear()

    assert flushed.cleaned is True
    assert pending.cleaned is True
    assert h.history == []
    assert h.can_undo() is False
