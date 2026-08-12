---
name: NiceGUI slot/client resolution — async tasks, and slots deleted mid-handler
description: How NiceGUI's slot stack works with asyncio tasks (the three safe async patterns), plus the sibling trap where a handler's own redraw deletes the slot it's running in — same underlying client-resolution mechanism, two different triggers
type: feedback
---

NiceGUI resolves "the current client" through a **slot stack kept per asyncio
task** (`Slot.stacks: Dict[int, List[Slot]]`) — not `ContextVar`, not thread-local.
Anything that calls `ui.notify()`, creates new elements, or otherwise touches
`context.slot.parent.client` only works if the *current task's* stack still has
a live slot on top. Two independent ways that breaks, below.

## 1. A new asyncio task starts with an empty stack

`asyncio.ensure_future()` / `background_tasks.create()` hand the coroutine a
**new task**, which starts with an empty slot stack — copying context doesn't
help, context vars are not used here at all.

**1a. `ui.notify()` or anything that discovers the client via the slot stack**

Must run inside NiceGUI's `handle_event` wrapper. Fix: return the coroutine
from the handler (don't schedule it) — NiceGUI detects the returned
`Awaitable` and wraps it with `with parent_slot:` before scheduling.

```python
# CORRECT
on_click=lambda e, ...: self._my_async_method(...)

# WRONG — new task has empty slot stack, ui.notify() will crash
on_click=lambda e, ...: asyncio.ensure_future(self._my_async_method(...))
```

**1b. Creating new UI in a background task**

Safe if you enter the container first: `with self._my_container:` pushes its
slot onto the current task's stack.

**1c. Modifying existing elements** (`.text=`, `.value=`, `.props()`, `.set_visibility()`)

Always safe from any background task — no slot context needed.

## 2. A handler's own redraw deletes the slot it's still running in

A click handler attached to an element **inside a container that the same
handler causes to be cleared/rebuilt** runs in a slot that gets deleted
mid-flight. Any subsequent slot-context call (`ui.notify()`, creating UI,
etc.) raises `RuntimeError: The parent element this slot belongs to has been
deleted.` — same failure family as case 1, different trigger (no new task
involved; the *original* task's slot is gone).

Concrete incident: the Haystack sidebar's per-row **Save** icon.
`_on_entry_save` called `hs.save_graph(entry)`, which marks the entry clean
and fires `GraphDataMutated`. `@redraw_on(GraphDataMutated, …)` rebuilds the
editor, and `_render_list` calls `self._list_container.clear()` — deleting the
very row the handler is running inside. Control returns to the handler's
`ui.notify(...)`, which resolves its client via `context.slot.parent.client` →
parent row gone → crash. (The graph editor's own save button worked because it
lives in `panel_header`, not inside the cleared list.)

**Fix:** capture the client **before** the mutation and run the post-mutation
UI calls under `with client:` — the client's own auto-index slot survives the
row teardown:

```python
client = ui.context.client          # before the redraw-triggering mutation
success = hs.save_graph(entry)      # fires GraphDataMutated → redraw → row deleted
with client:                        # client slot survives; row slot does not
    ui.notify("Saved", type="positive")
```

Same pattern already used in `ui_node.py` and `library_overview_editor.py`.
Applies to any row/list action handler that both (a) mutates state in a way
that triggers `@redraw_on` of its own container and (b) emits UI afterward.
Handlers that notify from a *dialog* callback (`confirm_modal`, save-as,
rename) are unaffected — the dialog is a separate, still-live slot.

### Deferred-timer variant: a `ui.timer` can outlive the slot it was created in

Same root cause (a slot deleted by a redraw), a third trigger. A
`ui.timer(delay, …, once=True)` created during a draw is parented to the
*ambient draw slot*. If that container is cleared/rebuilt within `delay`, the
timer fires after its parent slot is gone and NiceGUI's `Timer._run_once` →
`_get_context()` → `parent_slot` raises **`RuntimeError: The parent slot of
the element has been deleted.`** — a background-task traceback through
`timer.py:_run_once`, not a handler crash.

Concrete incident: selecting a node set `ctx.active_component`; the studio
**component source editor** redrew to follow it, built a `ui.codemirror`, and
`attach_code_intelligence()` scheduled `ui.timer(0.1, …, once=True)` in that
draw slot. The tail of the selection event sequence (`selectionBounds`)
triggered a second redraw inside the 0.1s window, clearing the slot → the
timer fired orphaned → crash. Intermittent because it's a race against the
delay.

**The `with client:` fix does NOT apply here** — the problem isn't resolving a
client for `ui.notify`, it's the timer object itself being parented to a
doomed slot. Two fixes, combined:

1. **Re-parent the timer to a stable element** that shares the lifecycle you
   actually want — e.g. the editor element it acts on. When the host slot is
   cleared, the timer is torn down *with* that element instead of firing into
   a dead parent:

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

See `attach_code_intelligence` in
`packages/haywire-core/src/haywire/ui/extends/codemirror/code_intelligence.py`.

**Why:** Prior incidents where `asyncio.ensure_future()` crashed `ui.notify()`
with an empty slot stack, and separately where a handler-triggered redraw
deleted its own slot before `ui.notify()` ran.

**How to apply:** Async event handlers / background-task UI code → return the
coroutine, don't schedule it (case 1). Row/list handlers that redraw their own
container and then emit UI → capture `client = ui.context.client` before the
mutation, `with client:` after (case 2). Deferred timers created during a draw
that may be invoked from a container that redraws on selection/state change →
re-parent the timer to a stable element, guard the body on
`has_socket_connection` — the fix belongs in the helper, not each caller.
