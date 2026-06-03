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
