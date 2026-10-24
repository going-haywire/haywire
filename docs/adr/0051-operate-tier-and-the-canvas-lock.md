---
name: operate-tier-and-the-canvas-lock
description: A fourth access tier, operate, may change values on shown widgets only; a per-session, per-level lock caps the level mode at operate and never raises it; writes are gated where they land
status: accepted
see-also: ADR-0027, ADR-0050
level: ui
---

# The operate tier and the canvas lock

**Context.**

- ADR 0027 gave the studio three tiers. For the graph canvas that left two choices: a principal could change nothing, or could restructure the graph. A live show needs a third: turning knobs on a running graph without being able to delete the node behind them.
- Editors also want to protect structure from themselves. Moving a node by accident mid-performance is the realistic failure, and it applies to a principal who holds `edit`.
- The graph and its editor are shared across sessions, so a protection that lives on the graph would lock everyone.
- The canvas menus and gestures were not tier-gated (ADR 0050 recorded the gap).

**Decision.**

- **Four tiers: `view` < `operate` < `edit` < `admin`.** Wire value `operate`. `view` pans and zooms on the document level and selects a haystack entry; the Properties editor needs `edit`. The read-only affordances on cards (the diagnostics badge and its menu, the comment, pin tooltips) work in every level mode. `operate` adds Enter (Groups and macro placements), the widgets on node cards and the stage, and Start and Stop in the haystack. Selection works in every level mode (it changes no document); copy, context menus, the selection toolbar, the resize gadget, paste, cut, delete, duplicate, Undo/Redo, the Properties editor's writable panels and unlock need `edit`.
- **The lock is a per-session, per-level cap.** A level is a document, an entered Group or an entered macro placement; a level inside a placement is always locked (ADR 0038). The lock is never saved and does not affect other sessions. `ToggleLock` (`Mod+E`, requires `edit`) and the header lock button toggle it; unlocking needs the real `edit` tier. `GraphProperties.open_locked` (default off) locks a level when it first opens in a session.
- **The cap lowers and never raises.** A locked level makes the session's level mode `min(real tier, operate)` for that level, so a `view` session stays `view`. The rule is `level_mode(can_access, locked)` in the graph editor's `access.py`; locking a level keeps its selection.
- **Operate means values on shown, operable widgets.** There is no per-port tier; a port or a settings field may only declare `operable=False`, a boolean, which makes its writes need `edit` even from a card (ADR 0055). A widget whose `on_change` reshapes its node (`rejig()`) stays operable: ghost pins make the reshape reversible, since edges on a removed pin reattach when a port with that id returns. An author who wants a widget out of operators' reach hides it on the card (`ShowWidgetStrategy.NEVER`); it then lives only in the Properties panel, which needs `edit`.
- **Save uses the real tier.** Saving needs the principal's real `edit` tier and ignores the lock, in the graph editor header and in the haystack editor's entry Save and Save-as and its header Save and Save As. Locking protects the canvas; it is not a statement about persistence.
- **Enforcement is at the write, in two layers.** First, the server: canvas events carry a mode requirement (`@handles_event(..., requires=LevelMode.X)`, `edit` by default, ADR 0060), and a refused drag or resize snaps back. `GraphEditor.accepts_command` lets the editor refuse a command the wrapper's tier check allowed: every command but `ToggleLock` and `ToggleStageView` needs level mode `edit`. Context menus and the selection toolbar do not open below `edit` and close when a level locks. User edits take the edit route (ADR 0055), which refuses an edit the session's level mode does not allow when it lands: card and stage widgets need `operate`; Properties settings rows, Ports-panel widgets, port reorder, the port edit dialog and the edge propagation switch need `edit`. Second, the browser projects the route (ADR 0060, which replaced the `data-hw-readable` / `data-hw-operable` markers with `data-hw-requires`). The route is the refusal that counts; the browser gate is a second layer against accidents, and it is not access control: `pointer-events` does not stop keyboard focus.
- **Value edits mark the graph unsaved** on every surface that writes through the edit route, graph props and graph metadata included (a promoted port's widget-visibility choice is the exception, see ADR 0055), when the stored value actually changes, without reassembling a running graph. The first one on a saved graph announces the change with `GraphUnsavedChanged`, which only unsaved markers follow, so no panel is rebuilt while it is typed in. A Group interior forwards non-structural changes without restarting its host or redrawing its card.
- **Agents.** `graph_editor_operate` (requires `operate`) writes a value to a port whose widget is shown, not linked and accepting its own value. It is not undo-recorded. The lock does not apply to agents.

**Considered options.**

- *A per-port `requires=` tier on port specs.* Rejected: a tier there could name `view` or `admin` by mistake. The boolean `operable=False` covers the one case that needed it, the annotation's text.
- *Lock stored on the graph and shared.* Rejected: it would lock every session viewing the graph, and a saved lock is a second thing to forget. Only the default (`open_locked`) is saved.
- *Save following the lock.* Rejected: a locked editor still needs to persist work, and a value change that marks the graph unsaved must not leave the person who holds `edit` unable to save it.
- *Gating only by hiding controls.* Rejected: a hidden or disabled control does not stop an event already in flight. The write itself asks.
- *Letting a lock raise a lower tier.* Rejected: the lock is a protection, never a grant.

**Consequences.**

- These are UI roles against accidents, not a sandbox (ADR 0027): a principal who can edit a graph holds the authority of the studio process.
- A fold opens and closes from `operate` on, and an annotation's text is editable only in `edit` (it declares `operable=False`). Both are widgets writing through the edit route, so the server checks them, and both mark the graph unsaved.
- The haystack editor follows the same ladder: selecting an entry needs `view`, Start and Stop need `operate`, everything else needs `edit`. A control below its tier is not drawn.
- A widget whose handler reshapes its node is operable. Authors who do not want that hide it with `NEVER`.
- A new write path takes the edit route (ADR 0055) or declares a tier on its event; nothing gates it by default except canvas events (default `edit`).
- Because the cap is per level, entering a Group opens a level with its own lock.

## Amendment (ADR 0060)

The Properties editor requires `view`, not `edit`. Its inspector tabs show in every level mode and their writers are greyed below `edit`; the edit route still refuses the write. See [ADR 0060](0060-the-browser-projects-the-route.md).
