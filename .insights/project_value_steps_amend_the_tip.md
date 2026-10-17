# Value edits amend the newest undo step; they cannot use the generic merge

Found while recording value edits (editor-modes 5b-2). A slider drag emits a
write per tick and must be ONE undo step.

## Why the generic merge fails

`HistoryManager`'s merge has a 100 ms window, looks at pending actions only,
and the grouping window flushes pending to the history 500 ms after a fence.
A drag longer than 500 ms therefore stops merging mid-gesture: later ticks start
new steps, and the user needs many Ctrl+Z to undo one drag.

## What value writes do instead

`HistoryManager.add_value_action(action, merge_owner, idle_s)` amends the run's
own step. `HistoryManager._amendable` holds the step `add_value_action` last
recorded or amended; `add_action`, `add_fence`, `undo`, `redo`, `clear` and the
step's eviction or redo-branch discard drop it. It is amended only while it is
still the pending tail, else the history tip (for a group, its last action), and
only when the merge key is non-None, equal, and the last write is within
`VALUE_EDIT_MERGE_IDLE_S` (3 s).

The amend adopts the newer value WITHOUT executing (see
`project_undo_merge_executed_state.md`). A no-op write adds nothing and keeps
the redo branch; resets never amend.

## Why the run is held, not inferred

The history's shape cannot say whether a run is open. After `undo()` then
`redo()` the redone step is the tip with nothing redoable — exactly what an open
run looks like — and redo re-executes the action, restamping `last_write`. A
step found by shape would let the next write amend the redone step, making the
value before it unreachable.

## Testing

Run undo tests with merging AND grouping on. A test that turns either off
passes while the bug (a long drag split into steps, or an undone or redone step amended)
is live.
