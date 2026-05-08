---
name: NiceGUI async and slot context rules
description: How NiceGUI's slot stack works with asyncio tasks, and the three patterns for safe async UI
type: feedback
---

NiceGUI stores the slot stack **per asyncio task ID** (`Slot.stacks: Dict[int, List[Slot]]`).
New tasks from `asyncio.ensure_future()` / `background_tasks.create()` always start with an empty slot stack — context vars are NOT used, copying context doesn't help.

## Three cases

**1. `ui.notify()` or any function that discovers the client via slot stack**

Must run inside NiceGUI's `handle_event` wrapper. Fix: return the coroutine from `on_click` lambda (don't schedule it). NiceGUI detects the returned `Awaitable` and wraps it with `with parent_slot:` before scheduling.

```python
# CORRECT
on_click=lambda e, ...: self._my_async_method(...)

# WRONG — new task has empty slot stack, ui.notify() will crash
on_click=lambda e, ...: asyncio.ensure_future(self._my_async_method(...))
```

**2. Creating new UI in a background task**

Safe if you enter the container first: `with self._my_container:` pushes its slot onto the current task's stack.

**3. Modifying existing elements** (`.text=`, `.value=`, `.props()`, `.set_visibility()`)

Always safe from any background task — no slot context needed.

**Why:** Prior incidents where `asyncio.ensure_future()` caused `ui.notify()` to crash with empty slot stack.
**How to apply:** Any time writing async event handlers or background task UI code, use pattern 1 (return coroutine, don't schedule).
