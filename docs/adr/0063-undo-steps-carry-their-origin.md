---
name: undo-steps-carry-their-origin
description: Every undo step records who recorded it (a session or a Farmhand call), a history lists itself read-only and reports changes, and the History editor shows a file's whole history with that origin
status: accepted
see-also: ADR-0055, ADR-0059
level: framework
---

# Undo steps carry their origin

**Context.**

- One file has one undo history. Every session with the file open, every Farmhand call on it, and every Group or Macro interior inside it record on that one history (ADR 0059's "one history per file", `SubgraphContainer`).
- So Ctrl+Z in one session can undo another session's edit, or an edit inside an interior the user is not looking at. That case could not be checked live: the history kept no record of who made a step, and nothing showed the stack (backlog #2).
- A history exposed only the descriptions of the next undo and redo. Its list, grouping window and fences were private state.

**Decision.**

- **A step carries a `StepOrigin`** (principal, short session id, and `via`: `canvas`, `farmhand` or `system`). The history keeps it beside the step. A step merged into the pending one keeps the earlier step's origin; a value write that amends a step leaves the step's origin as it is.
- **An `Editor` credits what it records.** `Editor(origin=)` passes its origin with every step, undo and redo; `Editor.with_origin()` returns a sibling over the same graph and history. `EditRoute(origin=)` hands out a sibling credited to its origin, so a structure edit made through `route.editor()` is credited too, and `for_subgraph` keeps the origin. A session's level route carries `StepOrigin.of_session(principal, session_id)`; undo, redo and Edit Instance credit the session; Farmhand editor tools credit the calling principal.
- **A history lists itself.** `IHistoryManager.snapshot()` returns read-only `HistoryEntry` rows: steps, groups with per-child origins, fences, the redo branch, the steps still pending in the grouping window, and a step's merge key while it can still be amended. Building one changes nothing. `last_move()` names the latest undo or redo and who did it.
- **A history reports changes.** `add_listener()` registers a zero-argument hook that runs whenever a snapshot would list different rows. A merge into the pending step and an amend list no new row and run nothing, so a drag or a slider gesture reports on its fences only. `GraphAppState` listens to every registered file's history and publishes the cross-session, payload-free `GraphHistoryChanged` on the event loop.
- **The History editor shows it.** A read-only editor in the CONTEXT slot, at the edit tier, lists the active graph's file history, the whole file including interiors, with each step's origin and interior path.

**Considered.**

- *An ambient origin on the history,* set around each route call. A structure edit runs through `route.editor()` after the route has returned, outside any such scope.
- *Stamping the origin in each action's constructor.* Over forty construction sites, and an action does not know which session builds it.
- *Showing only the active graph's steps.* That hides why Ctrl+Z seemed to do nothing: it undid an edit in another interior.
- *Fixing the redraw through haystack's undo-availability signal.* Fences and some undos run no validation, so it would still miss changes.

**Consequences.**

- An edit made outside any session or Farmhand call (an editor built without an origin) shows as "unknown".
- A fence lasts only until the next step: recording a step ends the redo branch, and a fence past the undo marker is part of it. The editor shows at most a closing fence at the top.
- The editor does not jump to a step. Undoing several steps in one click, with a refusal partway through, needs a decision of its own.
- Undo and redo stay one file-wide history: the origin makes a cross-session undo visible, not prevented.
