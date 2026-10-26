# Open follow-ups — backlog

What is still open after the editor-modes slices, the follow-up batches of 2026-10-20 to 2026-10-22, and the browser access layer (ADR 0060, 2026-10-24). Landed items have been removed; git history keeps them. ADRs 0051–0060 record the decisions.

This is a backlog, not an executable plan: each item names what is wrong, where, and a suggested first step. Pick one, settle it with the user, then write a plan for it.

Items carry stable IDs (`#N`; handoff notes cite them), so the numbering has gaps. Line references are from the date the item was added.

---

## 1. Features and UX gaps

- **#2** **No undo-history panel.** The two-session undo case (two sessions on one file) cannot be checked live without seeing the stack. Needs a design round: where the panel lives, what an entry shows (description, group, fence), whether it is per graph or per file history (Group interiors share their host's history, ADR 0059).
- **#3** **A Farmhand tool run outside the MCP host gets no closing fence.** No such caller exists yet; record it where a non-MCP caller is added.
- **#6** **Live reconfigure of a widget** (changing a widget's config while it is drawn) was left for a later design round.
- **#49** **Nested `data-hw-requires` stamps follow two rules.** Card CSS frees an element if *any* enclosing stamp allows the mode; `isGated` (`access_gate.vue`) reads only the *nearest* stamp; panels gate on any enclosing stamp that ranks too high. Nothing nests stamps today. Decide one nesting rule for both scopes, then add a nested fixture to `test_css_and_isGated_agree`.
- **#50** **A press on an `edit`-stamped widget inside a drag handle starts a node drag in `edit`.** `_isInteractiveWidgetElement` (`canvas.vue`) only counts `operate`-stamped elements as widgets; an `edit`-stamped or routeless widget in a widget node or Inset is not exempt. Pre-existing. First step: test `_levelModeSatisfies(closest('[data-hw-requires]')?.dataset.hwRequires)` instead.
- **#51** **The settings row menu greys by the session mode, not its own route's mode.** With two canvases (one locked, one not), selection-toolbar forms can be greyed wrongly or left live; the route still refuses the write. Decide whether a teleported row menu should carry its own route's mode.

## 2. Performance

- **#9** **Drawing large graphs.** The 512-node load went from 23 s to ~12 s (Firefox 52 s → 11 s) on 2026-10-20; the Vue full-tree render walk remains (`.insights/project_nicegui_component_vs_native_tag.md`). Handoff: `internals/handoff/draw_performance_regression_fix.md` — check whether its `_claim_session_state` regression is cleared by `_clear_selection` publishing only when something was selected.

## 3. Polish

- **#13** **Slice 5b-4 leftovers:** a `storage_key` collision in `widget_instances`; the guard misses `bag.x =`; a Group's mirrored ports drop `operable`; Farmhand's not-operable message; hard-coded 12 px padding.
- **#15** **Edit-instance polish** (`internals/handoff/edit-instance-followups.md` §3): `Editor.last_promotion_dropped_edges` is a last-call field (return it from `promote_to_macro` once a second caller needs it); optional notice in a second session whose placement level became a modified instance.
- **#54** **`properties_editor.py` imports private core helpers** `_accessible` and `_poll_surface`; make them public. `_offered_surfaces` runs up to three times per draw.
- **#55** **`_allows(USER_DRAG_START)` is checked twice per gesture** (`canvas.vue` `_startUnifiedDrag` and the drag-start emit): a mode rise mid-press emits a drag start with an empty node list (harmless). Gate the emit on `draggedElements.length > 0`.
- **#56** **`AppShell._on_roster_changed` borrows the keymap listener's client;** capture the client in `_mount_tier_watch` and drop the silent `listener is None` branch. `resolve_tier` is imported inside the function (tests patch it there).
- **#57** **AccessGate leaves `window.hwAccess` and `<html data-hw-session-mode>` behind on unmount** (harmless with one gate per page).
- **#58** **Small leftovers from the access layer:** the double `needed is None` check in `GraphCanvasManager._handle_canvas_event`; the route/node guard in `widget/factory.py` `_widget_model_for` duplicates `_write_for`'s; stale `Union[AccessTier, str]` annotations on the popped requirement in the three surface decorators; `AccessTier` import order in four inspector panel files; ADR 0055 still names the deleted `can_edit_graph` (add an amendment note).

## 4. Test gaps

- **#59** **No test hovers the greyed "Promote to" anchor** in the settings row menu to prove its flyout stays shut below `edit` (`tests/ui/harness/test_inspector_gate.py`); `test_writers_are_live_in_edit` runs `all()` over a settings list it never asserts non-empty.
- **#60** **`test_css_and_isGated_agree` masks elements whose `pointer-events` is already `none` in `edit`** without counting them; assert or log the count.
- **#61** **The surface-decorator tests only check the `TypeError` for a `LevelMode`,** not that a valid tier lands on `class_identity.requires` nor that an unknown name raises `ValueError` through the decorator; the panel test passes a class the raising `@panel(...)` never sees.
- **#62** **Test hygiene:** a 600 ms negative `wait_for_timeout` in `test_level_mode_gate.py`; `test_port_pen.py`'s fake `EditState` carries a `mode` stand-in; `test_graph_editor_session_claim.py` imports `_locked_editor` inside a function; the `required_mode` tests lack type annotations.

## 5. Deferred minors from the 2026-10-20 → 22 branches

- **#35** A Graph-node or Macro stand-in pasted while broken carries no Subgraph (the clipboard reads `wrapper.node.subgraph_key`); once fixed it would share its Subgraph with the original. Same pattern as an unknown-key Graph-node.

## 6. Other open handoffs

Each has its own note in `internals/handoff/`:

- **#40** `graph-loop-benchmark-drift.md` — `graph_loop` ~8% slower between June and September 2026, not attributed.
- **#41** `install-writeback-breaks-the-dev-repo.md` — a marketplace install over an editable install silently replaces it.
- **#42** `node-busy-highlight-from-is-executing.md` — a busy highlight while a worker runs (`NodeWrapper.is_executing` is never assigned).
- **#43** `popup-overlay-should-stop-capturing.md` — a `backdrop_click_close` Popup intercepts outside clicks.
- **#44** `startup-main-thread-block.md` — the browser main thread is blocked ~800 ms after a large load.

## 7. Found while working the backlog

- **#45** **A port or setting edit on a stand-in is lost at the next save,** silently — a stand-in saves its kept data and takes only props from the live card. Applies to the canvas and to Farmhand's `set_property`/`operate` alike. Decide: refuse such writes, write them into the kept data, or leave it to the STAND-IN note (`inspect_node`).
- **#46** **A hot reload in a graph without a history loses the user's setup silently** (a never-opened Group interior, mainly). Handoff: `internals/handoff/reload-without-history-loses-setup.md`. **On hold** until #47 has landed.
- **#47** **Errors on the main editing and running pathways do not reach the error ledger** systematically; convert to `HaywireException` at a short list of central boundaries (`Editor._apply`, validation loops, signal dispatch, a global UI hook, Farmhand runner, load/save). Needs a design round and an ADR. Handoff: `internals/handoff/haywire-exception-at-boundaries.md`.
- **#63** **`GraphAppState` is keyed `__system__:state:GraphAppState`,** not `haybale-graph-editor:…`: `haybale_graph_editor/__init__.py` imports it (line 21) before `Library` is defined, so `derive_library_identity` finds no `Library` yet. Any library importing a decorated component above its `Library` class has the same defect, silently. Fixing it changes a registry key; check `workspace_state.json` and other persisted state keys first.
