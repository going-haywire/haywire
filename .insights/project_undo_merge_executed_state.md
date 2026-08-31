# Undo: a merged action carries execution state, and merging was dead code

Found 2026-08-31 while auditing `haywire.core.undo`. Four coupled defects; all
silent, none covered by a test (there was no `HistoryManager` test file at all —
`tests/core/test_undo/` only covered individual actions).

## The wedge: `merge()` returns an unexecuted action

`HistoryManager._merge_with_last_action` puts `last.merge(other)` into
`_pending_actions[-1]`. Every `merge()` builds a **fresh** action, so
`_executed` is `False` — but the object represents work already applied to the
graph.

`ActionBase.undo()` raises on `not self._executed`; `HistoryManager.undo()`
catches it, logs, returns `False`, and **does not move `current_index`**. The
result is a permanently wedged stack: Ctrl+Z silently does nothing for the rest
of the session, every action below the merged one is unreachable, and
`can_undo()` keeps returning `True` so the UI still offers undo.

The fix is `ActionBase.mark_executed()`, called by `merge()` implementations.
Do **not** fix it by executing the merged action instead: `MoveNodesAction.merge`
sums the deltas (`self.deltaX + other.deltaX`), so re-executing double-applies
the movement. A merged action is *already done* by construction.

**If you add a mergeable action, its `merge()` must call `mark_executed()` on
what it returns.** Nothing enforces this — the failure is silent and arbitrarily
far from the cause.

## Merging never fired at all, hiding the above

`_last_merge_time` starts at `0.0` and was written *only* inside
`_merge_with_last_action`. The window check `(now - 0.0) * 1000 >
merge_time_window_ms` therefore rejected every candidate forever — merging could
not bootstrap, so `enable_action_merging=True` was a no-op. `_should_merge_action`
additionally required a non-empty `self.history`, blocking merges for the whole
first group of a session (nothing is flushed yet).

Consequence for archaeology: this masked the wedge. Fixing the timestamp alone
would have shipped the wedge to users on the first two-node drag.

## Fences were counted against `max_actions`

`_maintain_history_limits` compared `len(self.history)` to `max_actions`, but
history holds `Fence` entries too. Canvas drags emit **two fences per gesture**
(`interaction.py` drag start/end), so real undo steps were evicted at a fraction
of the user's configured limit. The cap counts undoable items only.

## Fences grew without bound

`_maintain_history_limits` ran only from `add_action`; `add_fence` appends
directly. A gesture producing no action (a click that starts and ends a drag)
left a fence behind permanently — 50 empty gestures meant 50 history entries.
`_trim_trailing_fences()` now collapses consecutive tail fences.

## Related

Cleanup contract is otherwise sound: `_cleanup_item` covers eviction, redo-branch
discard and `clear()`, actions only ever hold wrappers that are *out* of the
graph (`RemoveElementsAction._undo_impl` clears its three dicts after re-adding),
and `NodeWrapper.cleanup()` is idempotent via `_cleaned_up`. The one hole was the
merge path dropping both operands without `cleanup()` — harmless while only
move actions merged (they hold no wrappers) but a leak for any future mergeable
action that stashes one.
