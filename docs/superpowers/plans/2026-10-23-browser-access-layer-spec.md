# Design Spec: Consistent browser access layer

**Status:** approved 2026-10-23 (design round on `internals/handoff/level-mode-press-filter.md`). Unbuilt.
Supersedes the press-filter proposal in that handoff.

**What it does:** the browser's access decisions are derived from the same rules the server uses
(the edit route and the canvas handler table), enforced by one core component for canvases and
panels, for pointer, keyboard and gestures; a tier change reloads the pages it affects.

## Why

The server side is sound (ADR 0055: one `EditRoute`, one `level_mode`). The browser layer re-derives
the same rules by hand in several places:

- **S1** The route rule "required mode = `minimum` if operable, else `EDIT`" is written inline twice
  (`edit_route.py:102`, `_minimum_for` at `:167`) and re-derived a third time by the stamping funnel
  (`skin/base.py:196,252`), which also stamps `data-hw-operable` when the card has no route
  (server: read-only).
- **S2** `data-hw-readable` is hand-stamped (`pin_render.py:146`, `node_skin.py:821,856`).
- **S3** Keyboard is not gated: Tab reaches a gated input, a typed edit snaps back.
- **S4** Panels project no level mode at all; every panel write is optimistic and snaps back.
  `NodePortsPanel` reorder below edit leaves DOM and model diverged (SortableJS moves the row first).
- **S5** Canvas gesture rules are scattered `editing` / `levelMode === 'view'` checks that hand-copy
  the server's `@handles_event(access=)` table (`graph_canvas_manager.py:396`).
- **S6** A tier change notifies nothing but the keymap and Farmhand: panel visibility, open editor
  bindings, canvas `levelMode` and `active_mode` stay stale.

The press-filter proposal was dropped: it trades the CSS gate's fail-closed-by-construction for an
enumerated event list, and tooltips in `view` (its one user-visible gain) are not a priority.

## Decisions

| # | Decision |
|---|---|
| Q1 | (moot) Press filter not built; CSS gate stays. |
| Q2 | Inset gate stays CSS in `canvas.vue` (it retargets presses to the host card; not an access gate). |
| Q3 | Cursor rule only; no hover neutralizing. |
| Q4 | `required_mode(minimum, operable) -> LevelMode` free function in `haywire.core.access`. |
| Q5 | One attribute `data-hw-requires="view\|operate\|edit"` replaces `data-hw-readable` / `data-hw-operable`; helper `stamp_requires(el, mode)`. |
| Q6 | Canvas gets `{event_type: mode}` from the handler map; `_allows(eventType)`; unknown type → console error + refused in every mode; test that every gesture event type has an entry. |
| Q6b | `@handles_event(access=)` mandatory (`TypeError` at decoration); `handler_access` on an undeclared handler refuses and logs. `required_access`: an invalid `access` value raises at decoration time; missing identity / identity without `access` keep the `VIEW` fallback (ADR 0027 amendment). |
| Q7 | One document-level capture `focusin` listener blurs a gated target; shares the gate definition with the CSS. |
| Q8 | Panels use the same mechanism. |
| Q9 | Session mode on `<html data-hw-session-mode>`; applies under `[data-hw-mode-scope="session"]` (the `PropertiesEditor` content column). Canvases keep their own root `data-hw-level-mode`. |
| Q10 | Panels: positive marking (only stamped writers gated). Cards: negative (unmarked = `edit`, fails closed). |
| Q11 | "Active level mode of this session" becomes a core per-session signal field, `SessionContext.level_mode` (core has no `SessionState` of its own; `SessionContext` holds core's per-session fields such as `keymap`); moves from `EditState.active_mode`; the shell mounts the stamp element. |
| Q12 | On `RosterChanged`, each shell whose principal's resolved tier changed notifies and reloads its page. |
| Q13 | Gated panel writers greyed with the `DISABLED_STYLE` look (design guide §2.11); cards not greyed. |

## Changes

**Core — rules (`haywire.core.access`)**
- `required_mode(minimum, operable)`; `EditRoute` uses it at both sites.
- `required_access`: invalid `access` value raises at decoration time.
- `@handles_event(..., access=)` mandatory; all undeclared handlers get an explicit `access=LevelMode.EDIT`.

**Core — session mode**
- New core `SessionState` field for the session's active level mode. `EditState.active_mode` moves
  there. Writers: `GraphEditor._claim_session_state` (`graph_editor.py:1001`), haystack reset
  (`haystack_editor.py:537`).

**Core — stamping**
- `stamp_requires(el, mode)`.
- `WidgetFactory.render_widget` (`ui/widget/factory.py:142`) stamps `required_mode(minimum, operable)`
  when a route exists, nothing without one. `BaseSkin.render_widget` / `render_setting_widget` stop
  stamping. One stamping site for card and panel widgets.
- Hand stamps: `pin_render` tooltip pin and `node_skin` badges (`view`); `NodePortsPanel` pen and
  reorder handle, edge propagation switch (`edit`).

**Core — browser enforcement**
- Shell-mounted Vue component (working name `AccessGate`): writes `<html data-hw-session-mode>` from
  its session-mode prop, owns the global gate CSS, owns the `focusin` listener. CSS and `focusin`
  share one JS definition of "is gated":
  - canvas: `.ui-node-slot` content, scope = nearest canvas root `data-hw-level-mode`, negative;
  - panels: under `[data-hw-mode-scope="session"]`, scope = `<html>` session mode, positive, greyed.
- The level gate CSS moves out of `canvas.vue` into `AccessGate`.

**Canvas gestures (`canvas.vue`)**
- Gesture map pushed by `GraphCanvasManager` at construction; `_allows(eventType)` replaces the checks
  in drag, resize, edge, reconnect, paste, Enter and context menu; `keepsPress` reads `data-hw-requires`.

**Tier change**
- Shell: on `RosterChanged` compare resolved tier before/after; changed → notify + reload. The keymap's
  own `RosterChanged` subscription goes. Farmhand host keeps its own.

## Not in scope

- Tooltips on gated triggers in `view` (#5 part 1): known limitation, documented in skin-canon.
- Per-widget messages on a mode change.
- Context menu / selection toolbar (already hidden below `edit`).
- The route stays the refusal that counts.

## Tests

- Unit: `required_mode`; `@handles_event` without `access` raises; `required_access` invalid value raises.
- Every gesture event type the canvas emits has a handler-map entry.
- Harness (`tests/ui/harness/test_level_mode_gate.py` + suites probing `elementFromPoint`: `test_inset.py`,
  `test_stacking.py`, `test_graph_swinglet_connect.py`, `test_edge_appearance.py`, `test_edge_drag_cost.py`):
  attributes renamed; keyboard focus refused in `view` on canvas and panel; panel writer gated and
  greyed, level-free settings free; `NodePortsPanel` reorder blocked; unknown gesture logs and is refused.
- A tier change reloads only the affected session.

## Docs (land with the code)

- New ADR superseding ADR 0055's "The browser layer" paragraph; ADR 0027 amendment (`required_access`).
- Glossary: `data-hw-requires`, session mode.
- Rewrite `.insights/project_level_mode_pointer_gate.md` and its CLAUDE.md entry; skin-canon
  "Pointer input below level mode `edit`"; `canvas.vue` contract block.
- Close `internals/handoff/level-mode-press-filter.md` as superseded.

## Open questions (verify while planning)

1. Does every browser gesture map 1:1 onto one handler event type?
2. Does `RosterCache` notice security-document edits made outside the app (CLI)? If not, no reload.
3. How the shell mounts `AccessGate` and how the session-mode prop reaches it.
4. Can a canvas render widgets without a route?
