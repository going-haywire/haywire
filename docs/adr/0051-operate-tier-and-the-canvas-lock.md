---
name: operate-tier-and-the-canvas-lock
description: A fourth access tier, operate, may change values on shown widgets only; a per-session, per-level lock caps the effective tier at operate and never raises it; writes are gated where they land
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

- **Four tiers: `view` < `operate` < `edit` < `admin`.** Wire value `operate`. `view` pans, zooms, selects, copies, enters levels and reads panels. `operate` additionally changes values on widgets shown on node cards, and nothing else: no context menus, selection toolbar, paste, cut, delete, duplicate, Undo/Redo, Properties writes or unlock.
- **The lock is a per-session, per-level cap.** A level is a document or an entered Group. The lock is never saved and does not affect other sessions. `ToggleLock` (`Mod+E`, access `edit`) and the header lock button toggle it; unlocking needs the real `edit` tier. `GraphProperties.open_locked` (default off) locks a level when it first opens in a session.
- **The cap lowers and never raises.** A locked level makes the session's effective tier `min(real tier, operate)` for that level, so a `view` session stays `view`. The rule is `allows(can_access, locked, required)` in the graph editor's `access.py`.
- **Operate means values on shown widgets.** There is no per-port tier. A widget whose `on_change` reshapes its node (`rejig()`) stays operable: ghost pins make the reshape reversible, since edges on a removed pin reattach when a port with that id returns. An author who wants a widget out of operators' reach hides it on the card (`ShowWidgetStrategy.NEVER`); it then lives only in the Properties panel, which needs `edit`.
- **Save uses the real tier.** Saving needs the principal's real `edit` tier and ignores the lock, in the graph editor header and in the haystack editor's entry Save and Save-as. Locking protects the canvas; it is not a statement about persistence.
- **Enforcement is at the write.** Canvas events declare a tier (`@handles_event(..., access=...)`, default `edit`), and a refused drag or resize snaps back. Context menus and the selection toolbar do not open below effective `edit` and close when a level locks. `BaseEditor.accepts_command` lets an editor refuse a command the wrapper's tier check allowed. A `WriteGate` on widgets, `bind()` bindings and settings rows is asked when the write lands: card widgets need `operate`; Properties settings rows, Ports-panel widgets, port reorder, the port edit dialog and the edge propagation switch need `edit`. A disabled-looking control is only the look.
- **Value edits mark the graph unsaved** when the stored value actually changes, without reassembling a running graph. A Group interior forwards non-structural changes without restarting its host or redrawing its card.
- **Agents.** `graph_editor_operate` (access `operate`) writes a value to a port whose widget is shown, not linked and accepting its own value. It is not undo-recorded. The lock does not apply to agents.

**Considered options.**

- *A per-port `access=` on port specs.* Not built. Noted as the escape hatch if hiding a widget on the card (`NEVER`) proves insufficient.
- *Lock stored on the graph and shared.* Rejected: it would lock every session viewing the graph, and a saved lock is a second thing to forget. Only the default (`open_locked`) is saved.
- *Save following the lock.* Rejected: a locked editor still needs to persist work, and a value change that marks the graph unsaved must not leave the person who holds `edit` unable to save it.
- *Gating only by hiding controls.* Rejected: a hidden or disabled control does not stop an event already in flight. The write itself asks.
- *Letting a lock raise a lower tier.* Rejected: the lock is a protection, never a grant.

**Consequences.**

- These are UI roles against accidents, not a sandbox (ADR 0027): a principal who can edit a graph holds the authority of the studio process.
- Known gaps, recorded in the [security guide](../guides/security.md): the stacked-skin fold disclosure on a card is still clickable at `view`; the haystack entry menu's Rename and Remove, and haystack run settings, are not tier-gated.
- A widget whose handler reshapes its node is operable. Authors who do not want that hide it with `NEVER`.
- A new write path must ask the write gate or declare a tier on its event; nothing gates it by default except canvas events (default `edit`).
- Because the cap is per level, entering a Group opens a level with its own lock.
