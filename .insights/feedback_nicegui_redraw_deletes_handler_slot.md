---
name: NiceGUI redraw-during-handler deletes the row slot — capture the client first
description: A click handler that mutates state then redraws its own container deletes its slot mid-flight; ui.notify() then crashes
type: feedback
---

A click handler attached to an element **inside a container that the same
handler causes to be cleared/rebuilt** runs in a slot that gets deleted
mid-flight. Any subsequent slot-context API call (`ui.notify()`, creating UI,
etc.) raises `RuntimeError: The parent element this slot belongs to has been
deleted.`

Concrete incident: the Haystack sidebar's per-row **Save** icon. `_on_entry_save`
called `hs.save_graph(entry)`, which marks the entry clean and fires
`GraphDataMutated`. `@redraw_on(GraphDataMutated, …)` rebuilds the editor, and
`_render_list` calls `self._list_container.clear()` — deleting the very row the
handler is running inside. Control returns to the handler's `ui.notify(...)`,
which resolves its client via `context.slot.parent.client` → parent row gone →
crash. The graph editor's own save button worked because it lives in
`panel_header`, which is not inside the cleared list.

**Why:** `ui.notify()` (and friends) discover the client through the *current
task's* slot stack: `context.slot.parent.client`. A redraw triggered earlier in
the same handler deletes that parent before the notify runs.

**What works:** capture the client **before** the mutation and run the
post-mutation UI calls under `with client:` — the client's own auto-index slot
survives the row teardown.

```python
client = ui.context.client          # before the redraw-triggering mutation
success = hs.save_graph(entry)      # fires GraphDataMutated → redraw → row deleted
with client:                        # client slot survives; row slot does not
    ui.notify("Saved", type="positive")
```

This is the same `with client:` pattern already used in
`ui_node.py` and `library_overview_editor.py`.

**How to apply:** Any row/list action handler that both (a) mutates state in a
way that triggers `@redraw_on` of its own container and (b) emits UI afterward
(`ui.notify`, new elements). Note: handlers that notify from a *dialog* callback
(`confirm_modal`, save-as, rename) are unaffected — the dialog is a separate,
still-live slot. Related: [[feedback_nicegui_async.md]] (the async/empty-slot
variant of the same client-resolution problem).

---

## Deferred-timer variant: a `ui.timer` can outlive the slot it was created in

Same root cause (a slot deleted by a redraw), different trigger. A
`ui.timer(delay, …, once=True)` created during a draw is parented to the
*ambient draw slot*. If that container is cleared/rebuilt within `delay`, the
timer fires after its parent slot is gone and NiceGUI's `Timer._run_once` →
`_get_context()` → `parent_slot` raises **`RuntimeError: The parent slot of the
element has been deleted.`** — a background-task traceback through
`timer.py:_run_once`, not a handler crash.

Concrete incident: selecting a node set `ctx.active_component`; the studio
**component source editor** redrew to follow it, built a `ui.codemirror`, and
`attach_code_intelligence()` scheduled `ui.timer(0.1, …, once=True)` in that
draw slot. The tail of the selection event sequence (`selectionBounds`)
triggered a second redraw inside the 0.1s window, clearing the slot → the timer
fired orphaned → crash. Intermittent because it's a race against the delay.

**The `with client:` fix does NOT apply here** — the problem isn't resolving a
client for `ui.notify`, it's the timer object itself being parented to a doomed
slot. Two fixes, combined:

1. **Re-parent the timer to a stable element** that shares the lifecycle you
   actually want — e.g. the editor element it acts on. When the host slot is
   cleared, the timer is torn down *with* that element instead of firing into a
   dead parent:

   ```python
   with editor:                       # not the ambient draw slot
       ui.timer(0.1, _inject, once=True)
   ```

2. **Guard the body** so a client that disconnected before the tick is a quiet
   no-op (the element may be gone even when correctly parented):

   ```python
   def _inject():
       if not editor.client.has_socket_connection:
           return
       ui.run_javascript(js)
   ```

   (`element.client` is never `None`; check `has_socket_connection`, not the
   client itself.)

**How to apply:** any helper that defers work via `ui.timer(..., once=True)`
during a draw and may be invoked from a container that redraws on selection /
state change. The fix belongs in the *helper*, not each caller. See
`attach_code_intelligence` in
`packages/haywire-core/src/haywire/ui/extends/codemirror/code_intelligence.py`.
