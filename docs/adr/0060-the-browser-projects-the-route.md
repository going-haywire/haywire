---
name: the-browser-projects-the-route
description: The browser gates input from what the server declares, not from its own rules - one data-hw-requires stamp derived from the route's required_mode, gesture mode requirements taken from the handler table, one AccessGate owning the gate for canvases and panels
status: accepted
see-also: ADR-0055, ADR-0051, ADR-0027
supersedes: ADR-0055 (section "The browser layer")
level: framework
---

# The browser projects the route

**Context.**

- ADR 0055 gave the browser a second layer against accidents: `canvas.vue` owned a CSS gate and its own gesture checks, with two markers (`data-hw-readable`, `data-hw-operable`). Those rules restated, in JavaScript and CSS, what the server's `EditRoute` already decides. Panels had no gate at all.
- A rule stated twice drifts. A canvas handler's mode requirement was optional and the gestures `canvas.vue` checked were its own list, a widget stamped by a skin could disagree with the route's `minimum`/`operable` rule, and `EditState.active_mode` lived in a graph-editor state object although every surface needs it.

**Decision.**

- **One rule, one function.** `required_mode(minimum, operable)` (`haywire.core.access`) is the mode a write needs; `EditRoute` uses it at both sites and the stamp derives from it.
- **One stamp.** `data-hw-requires="view|operate|edit"` replaces `data-hw-readable` and `data-hw-operable`, with no alias period. `stamp_requires(el, mode=LevelMode.EDIT)` (`haywire/ui/access_stamp.py`) sets it, and always writes the attribute. Card widgets are stamped by `WidgetFactory.render_widget` from `model.requires`; panel settings widgets by `render_utils._resolve_widget_instance`. That is two call sites and one rule. A routeless widget is unstamped: on a card that means `edit` (fails closed), in a panel free. Pins and badges stamp `view`; the Ports panel pen, reorder handle and the edge propagation switch take the `edit` default.
- **Cards gate negatively, panels positively.** Inside `.ui-node-slot` unmarked content counts as `edit`. Under `[data-hw-mode-scope="session"]` (the Properties editor content column) only stamped writers are gated, and a gated one is greyed (`opacity: 0.5`, `pointer-events: none`, design guide 2.11). Cards are not greyed.
- **Inspector tabs show in every mode, read-only below edit.** The Graph, Node, Settings, Ports and Edge tabs of the Properties editor poll only for their subject (active graph, node or edge), not the level mode, so a locked canvas or a viewer keeps them, errors and warnings included. Their writers are greyed by the panel gate; read-only rows stay live. `PropertiesEditor` and every panel on those five surfaces declare `requires=AccessTier.VIEW`; the editor's other tabs (Application, Execution, Canvas & Nodes, Debug) hold unstamped global settings, so their panels keep the `edit` default. A tab none of whose panels the principal's access right reaches is not offered, neither in the tab strip nor as the default tab, so a viewer opens Properties onto the first inspector tab whose subject exists. Only the access requirement decides this: a tab whose surface polls false stays in place greyed, and one whose panels all poll false shows its empty state. A teleported popup sits outside the scope column, so a dialog that writes is gated at its opener (the Ports pen), and a popup that holds writers carries `data-hw-mode-scope="session"` itself: the settings row menu does when it has a route, with Promote to, Demote, Reset and Set to none stamped `edit` and the Developer submenu left live.
- **`AccessGate`** (`haywire/ui/components/access_gate/`), mounted by the shell, owns the gate CSS (moved out of `canvas.vue`), writes `<html data-hw-session-mode>`, blurs a gated target on capture `focusin` (and a focused card input when a canvas mode drop gates it), and exposes `window.hwAccess.isGated`. Canvases keep their own root `data-hw-level-mode`. Mode changes stay O(1): one attribute, never per-widget messages.
- **Session level mode** is `SessionContext.level_mode`, a core signal field (default `view`), replacing `EditState.active_mode`. Writers: `GraphEditor._claim_session_state` and the haystack close reset.
- **Gestures come from the handler table.** `GraphCanvasManager` pushes `{event_type: mode}` (`GraphCanvasVue.set_gesture_requires`, prop `gestureRequires`); `canvas.vue` `_allows(eventType)` replaces its own checks, and names each event type by its generated constant (`_allows(GraphEvents.UserInteractions.USER_DRAG_START)`), never a string literal; a test resolves every constant through `generated/graph_events.js` and fails on a literal. An unknown type logs `console.error` and is refused in every mode. A canvas built without a manager must call `set_gesture_requires` itself.
- **A mode requirement defaults to `edit`.** `@handles_event(*classes, requires: LevelMode = LevelMode.EDIT)`; only a lowered requirement is written (`requires=LevelMode.VIEW` for selection, `OPERATE` for Enter). `handler_requires(handler)` returns the declared mode, and `EDIT` for a handler without the marker, so the manager pushes an entry for every handler. The context-menu handler takes the `edit` default; its inner gate is gone, since below `edit` the menu cannot be open.
- **Decorators validate.** `coerce_requirement` (`haywire.core.access`) rejects a `LevelMode` (`TypeError`) or unknown name (`ValueError`) on `@panel`, `@editor` and `@farmhand` (ADR 0027 amendment).
- **A tier change reloads the page.** When a `RosterChanged` changes the resolved tier of a shell's principal, the shell notifies "Your access changed - reloading" and reloads; the keymap's own subscription is gone.
- **A parity test stands in for a generated stylesheet.** The CSS and `isGated` are two expressions of one rule; `test_css_and_isGated_agree` fails when they diverge. Generating one from the other was considered too heavy for two selectors.

**Considered.**

- *Keep the gate in `canvas.vue` and add a second one for panels.* Two copies of the rule.
- *A press filter instead of `pointer-events`* (handoff `level-mode-press-filter`). Superseded: `pointer-events` is the one mechanism; tooltips on gated triggers stay inert in `view` (see Consequences).
- *A new `SessionState` for the mode.* Core has none; `SessionContext` already holds core's per-session fields.

**Consequences.**

- Known gap: the CSS exempts an element if any ancestor stamp is exempt, while `isGated` reads the nearest stamp. They differ only for a gated stamp nested inside an exempt one; none exists today.
- Known limitation: tooltips on gated triggers stay inert in `view`, because `pointer-events: none` also removes hover; they are documented in skin-canon.
- Known gap: a number widget briefly enters its edit state on focus before the blur in `view`; nothing is written.
- Known limitation: a teleported settings row menu greys its writers by the session mode, the active editor's level mode, not by its own route's mode. They differ only for a selection toolbar on a canvas that is not the active one with a different lock (two canvases of one graph); the route still refuses the write (follow-up #51).
- Out-of-app limitation: edits to the security document made outside the app publish no `RosterChanged`, so no page reloads (the roster cache picks them up lazily). This closes follow-up #5 part 1 as a known limitation.
- The gate stays a second layer, not access control; the route is the refusal that counts (ADR 0055).

**Amendment (one name for every requirement).**

- Two axes, each with a "has" and a "requires" side: the access right against the access requirement (`AccessTier`, ADR 0027), and the level mode against the mode requirement (`LevelMode`). Every requirement defaults to `edit`; only a lowered or raised one is written down.
- The mode requirement defaults to `edit`. This supersedes the decision that it is mandatory: a handler without `requires=` needed a declaration, and was refused and logged without one; it now needs `edit`. The keyword was `access=`, the helper `handler_access()` and the marker `_handles_event_access`.
- One keyword, `requires=`, on `@panel`, `@editor`, `@farmhand` (tier) and `@handles_event` (mode), and `requires` on an `EditorCommand`. The renames: `access=` and the identity field `access` to `requires`, `required_access()` to `required_tier()`, `coerce_access()` to `coerce_requirement()`, `handler_access()` to `handler_requires()`, `set_gesture_access()` / prop `gestureAccess` to `set_gesture_requires()` / `gestureRequires`, and `EditorCommand.access` to `EditorCommand.requires`. No alias.
- `stamp_requires` defaults its mode to `edit`.
- `canvas.vue` names each gesture by its generated `GraphEvents.UserInteractions` constant instead of a string literal.
- The Properties editor hides a tab none of whose panels the principal's access right reaches; it showed it empty.

**Amendment (nested stamps tighten).**

- Where stamps nest, the strictest one around an element decides: an inner stamp can only tighten, never loosen, the one it sits in. The card CSS, `isGated`, the canvas's press check and the Inset rule all read it so; the panel rule already did. An unknown value counts as `edit` on a card and gates nothing in a panel. This closes the known gap above (follow-up #49).
- On a card the nearer of a stamp and a `.drag-handle` decides whether a press stays with the element or drags the card, so a widget can hand a part of itself back to the card (`NoteTextWidget`'s shown text, follow-up #50).
