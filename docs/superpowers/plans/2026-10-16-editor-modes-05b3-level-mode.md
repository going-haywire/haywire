# Editor modes, slice 5b-3: level mode — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Level mode (`view` / `operate` / `edit`) becomes the one rule the graph editor checks. `view` pans and zooms on the document level only, `operate` adds Enter and operable card widgets, and selection, copy and the Properties editor's writable panels need `edit`. The browser canvas enforces the same mode as a second layer.

**Architecture:**
- **Server:** `allows(can_access, locked, required)` and the canvas manager's own `locked` flag go away. Every check asks the level's `EditRoute` for its mode, including canvas handler tiers (`@handles_event(access=LevelMode)`), command acceptance, the toolbar, the menus and the inspector polls. `EditState.active_locked` becomes `active_mode`.
- **Selection and levels:** selection events need `edit`. Locking the level on screen clears the selection. Entering a level needs `operate`, and so does the error-ledger reveal of an interior level. A reveal selects only in `edit`.
- **Properties:** the five graph inspectors poll false below `edit`, so the read-only renderings of rows, the propagation switch and the Ports panel are deleted.
- **Browser:** the canvas gets a `levelMode` prop in place of `locked`, with a `data-hw-level-mode` attribute on its root. A CSS gate removes pointer input from card content below `edit`, and in `operate` gives it back to the `data-hw-operable` elements. `BaseSkin.render_widget` stamps that attribute on every card widget.

**Tech Stack:** Python 3.12, NiceGUI/Vue 3 (`canvas.vue`), pytest (`uv run pytest`), Playwright browser tier, ruff, mypy.

**Spec:** [2026-10-16-edit-route.md](2026-10-16-edit-route.md): sections "Level mode", "What each level mode allows on the canvas" and "Two layers of enforcement"; sequence item 3 ("5b-3, level mode"); the traps "CSS pointer gating has to out-specify five layers" and "The error-ledger reveal opens interior levels"; "Open after 5b-2". Decisions are listed below.

## Global Constraints

- **Branch:** work on `feat/editor-modes-slice5b3` in worktree `.worktrees/editor-modes-slice5b3`, cut from `feat/editor-modes-slice1`. It merges into `feat/editor-modes-slice1` after the live check; nothing goes to master.
- **Breaking changes are allowed.** No compatibility shims: `allows`, `GraphCanvasManager.locked/allows/set_locked`, `GraphCanvasVue.set_locked` and `EditState.active_locked` are deleted, not aliased.
- **Level mode table** (spec, unchanged): `view` → `view`; `operate` → `operate`; `edit`/`admin` → `edit` when unlocked, `operate` when locked. The cap never raises a lower tier.
- **Per-mode canvas rules** (spec table): pan/zoom always; levels: `view` the document level only, `operate` Enter (double-click), `edit` everything; selection and copy need `edit`; card widgets need `operate` (every card widget is operable until 5b-4 adds `operable=False`); context menus, toolbar, structure edits, writable Properties panels and Undo/Redo need `edit`. Patch | Stage switching stays `view` (Q22).
- **Save, the haystack and agents use the principal's real tier**, not level mode. Nothing in this slice changes them.
- **The route stays the refusal that counts.** `pointer-events` does not stop keyboard focus. Every write still takes the edit route, which refuses below its `minimum`.
- **Not in this slice:** `FoldWidget`, the annotation text widget and `operable=False` (5b-4); haystack action tiers, including the run settings on the Execution tab, and access defaults (5b-5). A tier change of a live session also stays out: nothing publishes it today, so polls and open levels catch up at the next redraw, while the route refuses writes at once. Also out: undo restoring an edge's propagation to `None`, and a closing fence for a Farmhand tool run outside the MCP host (both deferred, see Decisions 8–9); Ctrl+S; and the undo-history panel.
- **Docs rules:** follow `.claude/rules/python-docs.md`. ADR, glossary, guide and insight edits land in Task 7, with the code.
- **Pre-edit baseline** (CLAUDE.md), before Task 1: `uv run ruff check packages/haywire-core/src barn/haybale-graph-editor barn/haybale-studio barn/haybale-haystack tests/graph_editor tests/ui` and the CLAUDE.md mypy command. It must be clean; if not, stop and ask.
- **Tests:** use the smallest tier while iterating (`uv run pytest <file>`). Commit before any full-suite run, because `tests/studio/test_docs/test_generate.py` reverts uncommitted edits under `barn/haybale-testing`. Use `-n 4`. Playwright tests carry `@pytest.mark.browser` (automatic under `tests/ui/harness/`).
- **Commit trailer:** end every commit message with `Co-Authored-By: Claude Opus 5.5 (1M context) <noreply@anthropic.com>`.

## Decisions (this plan's, against the spec)

1. **The route is the only source of a canvas's mode.** `GraphCanvasManager` reads `self.route.mode()` / `self.route.allows(...)`; it keeps no lock of its own. `refresh_mode()` replaces `set_locked(bool)` and pushes whatever the route says.
2. **`EditState.active_mode: LevelMode`** replaces `active_locked`. `_claim_session_state` writes it, so a lock toggle still publishes `ActiveGraphMoved` and the Properties editor re-polls (that redraw path exists today). Polls read the live route through `can_edit_graph(ctx)`, not the snapshot.
3. **Canvas handlers declare a `LevelMode`.** `@handles_event(..., access=LevelMode.X)`, default `EDIT`. `SelectionChangedEvent` and `UserCopySelectedEvent` drop their `VIEW` marker. `EnterGroupEvent` becomes `OPERATE`. `CanvasMountedEvent`, `NodesMeasuredEvent`, the two selection-bounds events, `EdgeClickedEvent` (logs only) and the context-menu events (which close an open menu, then check `EDIT`) stay `VIEW`.
4. **`EditorCommand.access` stays an `AccessTier`** (shared vocabulary; the wrapper checks the real tier). `GraphEditor.accepts_command` adds the level rule: `ToggleLock` and `ToggleStageView` always pass; every other command needs level mode `edit`. So Copy and Select All, `VIEW` in core, are refused on this editor below `edit`.
5. **All five Properties inspectors poll `can_edit_graph(ctx)`**: Graph, Node, Settings, Ports and Edge. The selection-based four would be empty below `edit` anyway, but the check keeps them closed if a selection survives some path. The information-only panels on those tabs (Graph info, Node info, status, errors, the edge diagnostics) disappear below `edit` too, as Q8 implies. The Execution tab is unaffected.
6. **A reveal selects only in level mode `edit`.** In `operate` it opens and shows the level and selects nothing. In `view` it shows the document tab only for a document-level graph and opens no interior level.
7. **Fold header stopgap.** The stacked skin's fold header row carries `data-hw-operable`, so a locked `edit` principal can still open folds until 5b-4 makes it a `FoldWidget`. Its write is still direct (no unsaved, no undo, ungated on the server): the known gap stays listed until 5b-4.
8. **Open after 5b-2, the stale toolbar after a remote undo: in.** `GraphEditor._on_graph_data_mutated` refreshes its own selection toolbar. A peer session's undo (`_do_undo` publishes `GraphDataMutated`) and a Farmhand undo (`ctx.broadcast(GraphDataMutated())`) both reach it. `_do_undo`/`_do_redo` drop their own refresh, since their publish reaches the same handler.
9. **Open after 5b-2, deferred:** undo restoring an edge's propagation to `None` (not a level-mode concern; parked for a later swinglet), and the closing fence for a Farmhand tool run outside the MCP host (no such caller exists). Both stay in the spec's "Open after 5b-2" list, marked deferred past 5b-3.

## Review Focus

1. **Locking with a node selected and the Node tab showing.** The selection clears in the session and on both canvases of the level, the toolbar hides, and Properties falls back to the Execution tab. Test: Task 2, `test_locking_the_level_on_screen_clears_the_selection`.
2. **A browser that has not received the new mode yet** (a stale `edit` canvas on an `operate` level) sends a selection change. The server refuses it and the session selection stays empty. Test: Task 2, `test_a_selection_change_is_refused_below_edit`.
3. **An error-ledger reveal of a node inside a Group, for a `view` session and for an `operate` session.** `view`: no interior level opens and nothing is selected. `operate`: the level opens and nothing is selected. Test: Task 3, `test_a_view_reveal_opens_no_interior_level` and `test_an_operate_reveal_opens_the_level_without_selecting`.
4. **A double-click on a Group card's number widget in `operate`.** The widget takes the input and the level is not entered; a double-click on the card's title enters. Test: Task 5, `test_operate_double_click_on_a_widget_does_not_enter` and the existing `test_double_click_enters_on_a_locked_level`.
5. **A locked level's stage canvas mounted for the first time.** The new canvas starts in `operate` in the browser, not in the Vue default. Test: Task 5, `test_a_canvas_pushes_its_mode_when_built`.

---

### Task 1: Level mode replaces `allows`

**Files:**
- Modify: `barn/haybale-graph-editor/haybale_graph_editor/access.py`; `.../editors/graph_canvas/event_handlers.py`; `.../editors/graph_canvas/graph_canvas_manager.py` (`allows` :93, `set_locked` :97, `locked` :159, dispatch :359); `.../handlers/context_menu.py` (ctor :890, check :926); `.../handlers/selection_toolbar.py` (ctor, `show_at` :121); the `@handles_event` markers in `handlers/selection.py`, `interaction.py`, `visual_layer.py`, `selection_toolbar.py`, `context_menu.py` (type change only: `AccessTier.VIEW` → `LevelMode.VIEW`; tier changes come in Tasks 2–3); `.../editors/graph_editor.py` (`_new_level` :337, `set_level_locked` :342, `_switch_view` :425, `_rekey_level` :593, `accepts_command` :757, `_claim_session_state` :947, `_mount_view` :1132, `_edit_allowed` :1452); `.../state/edit_state.py`; `barn/haybale-haystack/haybale_haystack/editors/haystack_editor.py:511`
- Test: `tests/graph_editor/test_access_rule.py`, `tests/graph_editor/test_canvas_event_gating.py`, `tests/graph_editor/test_graph_editor_commands.py`, `tests/graph_editor/test_graph_editor_lock.py`, `tests/graph_editor/test_graph_editor_views.py`; `tests/ui/harness/routes.py` (`_mount_graph_canvas` :557, lock pages :1629, :1682); every test fake carrying `active_locked=` (grep `tests/`)

**Interfaces:**
- Produces:
  - `haybale_graph_editor.access.level_mode(can_access: Callable[[AccessTier], bool], locked: bool) -> LevelMode`: same table, no longer built on `allows`.
  - `haybale_graph_editor.access.can_edit_graph(ctx: SessionContext) -> bool`: `route_for(ctx)` is not `None` and allows `LevelMode.EDIT`.
  - `allows(...)` is deleted.
  - `handles_event(*event_classes, access: LevelMode = LevelMode.EDIT)`; `handler_access(handler) -> LevelMode`.
  - `GraphCanvasManager.refresh_mode() -> None`: below `EDIT` it hides the toolbar and closes an open context menu, and it pushes the mode to the browser. In this task the push is still `canvas_vue.set_locked(mode is not LevelMode.EDIT)`; Task 5 swaps it. `locked`, `allows` and `set_locked` are gone; the dispatcher checks `self.route.allows(handler_access(handler))`.
  - `ContextMenuHandlers(..., allows: Callable[[LevelMode], bool])` and `SelectionToolbarProvider(..., allows: Callable[[LevelMode], bool])`; the manager passes `self.route.allows`.
  - `EditState.active_mode: LevelMode = signal_field(LevelMode.VIEW)` (docstring: the level mode of the level on screen, as last claimed); `active_locked` deleted. The haystack's "active graph removed" path sets it to `VIEW`.
  - `GraphEditor._level_mode() -> LevelMode`: the route mode of the level on screen; `VIEW` when no level is open.
  - `GraphEditor.accepts_command`: Decision 4.
  - `GraphEditor._edit_allowed()` returns `self._level_mode() is LevelMode.EDIT`.
  - Every former `canvas.set_locked(...)` call in `graph_editor.py` becomes `canvas.refresh_mode()`.
  - Test harness: `_HarnessLevel` (a dataclass with `mode: LevelMode = LevelMode.EDIT`) in `routes.py`; `_mount_graph_canvas(..., level: _HarnessLevel | None = None)` builds its route on `lambda: level.mode` (`None` means a fresh `_HarnessLevel()`, so every other page stays in `EDIT`). Lock pages set `level.mode = LevelMode.OPERATE`, then call `manager.refresh_mode()`; `?stale=true` sets the mode without the refresh.

- [ ] **Step 1: Write the tests:**
  - `test_access_rule.py`: drop the three `allows` tests; keep `test_level_mode_table`; add `test_can_edit_graph_follows_the_active_route` (`None` route → `False`; route in `OPERATE` → `False`; `EDIT` → `True`).
  - `test_canvas_event_gating.py`: `_manager(mode: LevelMode)` builds `manager.route = EditRoute(lambda: editor, lambda: mode)`; keep the existing cases, now parametrized by mode (unmarked handlers need `EDIT`; a refused drag end resyncs positions; a refused resize end resyncs size); `test_refresh_mode_below_edit_hides_toolbar_and_closes_menu`; `test_refresh_mode_in_edit_reopens_nothing`.
  - `test_graph_editor_commands.py`: `test_copy_and_select_all_are_refused_below_edit` (locked level, admin principal → `accepts_command(Copy)` and `(SelectAll)` false); `test_toggle_stage_view_passes_in_view` (a `VIEW` principal → true); `test_toggle_lock_always_passes`.
  - `test_graph_editor_lock.py`: `test_claim_publishes_the_level_mode` (lock the active level → `EditState.active_mode is OPERATE` and `ActiveGraphMoved` published; unlock → `EDIT`). Rewrite `test_claim_publishes_the_lock` into it.
- [ ] **Step 2: Run** the four files — they fail (`allows` still imported, no `refresh_mode`, no `active_mode`).
- [ ] **Step 3: Implement** the interfaces above. Replace `active_locked` in every test fake (`grep -rn active_locked tests/`) with `active_mode=LevelMode.EDIT` (or the mode the test means). Update `test_graph_editor_views.py` and `test_graph_editor_lock.py` fakes that spy on `set_locked` to spy on `refresh_mode`.
- [ ] **Step 4: Run** `uv run pytest tests/graph_editor tests/ui/graph_canvas tests/ui/panel tests/haystack -n 4` — all pass. Then `uv run pytest tests/ui/harness/test_canvas_lock.py tests/ui/harness/test_enter_by_double_click.py` — still pass. (`test_locked_canvas_still_selects_without_a_resize_gadget` changes in Task 2.)
- [ ] **Step 5: Commit** `refactor(graph-editor): level mode replaces the allows rule and the canvas lock flag`.

### Task 2: Selection needs `edit`; locking clears it

**Files:**
- Modify: `.../handlers/selection.py` (`process_selection_change` :81, `process_copy_selection` :132); `.../graph_canvas_manager.py` (`refresh_mode`); `.../editors/graph_editor.py` (`set_level_locked` :342, `_on_reveal_graph_instance` :672)
- Test: `tests/graph_editor/test_canvas_event_gating.py`, `tests/graph_editor/test_graph_editor_lock.py`, `tests/graph_editor/test_graph_editor_views.py`, the reveal tests (`grep -rln RevealGraphInstance tests/graph_editor tests/studio`)

**Interfaces:**
- Consumes: Task 1's `refresh_mode`, `_level_mode`, `handles_event(access=LevelMode)`.
- Produces:
  - `SelectionChangedEvent` and `UserCopySelectedEvent` handlers need `EDIT` (marker removed).
  - `refresh_mode()` below `EDIT` also calls `clear_selection()` (this canvas and its browser, no publish).
  - `set_level_locked(context, key, True)` on the level on screen calls `_clear_selection(context)` before it claims, so `SelectionMoved` is published once.
  - `_on_reveal_graph_instance` sets `active_node`/`active_edge` and publishes `SelectionMoved` only when the revealed level's `route.mode()` is `EDIT`. It still switches level and publishes `Reveal`.

- [ ] **Step 1: Write the tests:**
  - `test_a_selection_change_is_refused_below_edit` (Review Focus 2): `_manager(LevelMode.OPERATE)` with a real `SelectionHandlers`; dispatch `SelectionChangedEvent(["n1"], [], activeNodeId="n1")` → session `selected_nodes` empty, `active_node` `None`.
  - `test_copy_is_refused_below_edit`: same in `OPERATE` → `EditState.clipboard` unchanged.
  - `test_locking_the_level_on_screen_clears_the_selection` (Review Focus 1): editor with a selected node on the active level and both canvases mounted (patch and stage fakes); `set_level_locked(ctx, DOCUMENT_LEVEL, True)` → session `selected_nodes == set()`, `active_node is None`, `SelectionMoved` published once, `clear_selection` called on both canvases.
  - `test_locking_a_level_off_screen_leaves_the_session_selection`: lock a non-active level → session selection unchanged.
  - `test_unlocking_restores_no_selection`.
  - `test_an_edit_reveal_selects` (existing behaviour kept) and `test_an_operate_reveal_shows_without_selecting`: locked document level, reveal a node → `Reveal` published, `active_node is None`.
  - `tests/ui/harness/test_canvas_lock.py`: rename `test_locked_canvas_still_selects_without_a_resize_gadget` to `test_a_locked_canvas_selects_nothing` and assert the clicked card is not selected (that assertion passes only after Task 5's browser guard; mark it `xfail(strict=True, reason="browser guard lands in Task 5")` here, and drop the marker in Task 5).
- [ ] **Step 2: Run** — the new tests fail.
- [ ] **Step 3: Implement.**
- [ ] **Step 4: Run** the touched files and `tests/graph_editor -n 4` — pass.
- [ ] **Step 5: Commit** `feat(graph-editor): selection needs level mode edit; locking clears it`.

### Task 3: Enter needs `operate`; `view` sees the document level only

**Files:**
- Modify: `.../handlers/visual_layer.py` (`process_enter_group` :1093); `.../editors/graph_editor.py` (`descend_into` :1248, `_open_level_for_graph` :871, `_on_reveal_graph_instance` :672)
- Test: `tests/graph_editor/test_enter_by_navigation.py`, `tests/graph_editor/test_canvas_event_gating.py`, the reveal test file from Task 2

**Interfaces:**
- Consumes: Task 1's `_level_mode`.
- Produces:
  - `EnterGroupEvent` handler needs `OPERATE`.
  - `descend_into` returns `False` and opens nothing while `_level_mode() is LevelMode.VIEW`. Docstring `Returns:` gains that case.
  - `_open_level_for_graph` returns `None` and opens nothing while the document level's `route.mode()` is `VIEW`.
  - So `_on_subgraph_navigation` and the reveal inherit the refusal; the reveal's `Reveal` publish for a document-level graph still happens in `view`.

- [ ] **Step 1: Write the tests:**
  - `test_enter_group_needs_operate`: `_manager(VIEW)` refuses `EnterGroupEvent` (no `SubgraphNavigation` published); `_manager(OPERATE)` publishes it.
  - `test_a_view_session_cannot_descend`: `VIEW` principal, `descend_into(ctx, group_card_id)` → `False`, `_levels` holds only the document.
  - `test_an_operate_session_descends`: `OPERATE` principal → `True`; the new level's mode is `OPERATE`.
  - `test_subgraph_navigation_is_refused_in_view`: publish-path call `_on_subgraph_navigation` in `VIEW` → no level opened.
  - `test_a_view_reveal_opens_no_interior_level` (Review Focus 3): `VIEW` principal, reveal a node inside a Group → `_levels` holds only the document, `active_node is None`, no `Reveal` published.
  - `test_an_operate_reveal_opens_the_level_without_selecting` (Review Focus 3): `OPERATE` principal → the Group level is open and on screen, `active_node is None`.
  - `test_a_view_reveal_of_a_document_node_shows_the_tab`: `VIEW`, node at the document level → `Reveal` published, nothing selected.
- [ ] **Step 2: Run** — fail.
- [ ] **Step 3: Implement.**
- [ ] **Step 4: Run** the touched files and `tests/graph_editor tests/studio -n 4` — pass.
- [ ] **Step 5: Commit** `feat(graph-editor): entering a level needs operate; view stays on the document level`.

### Task 4: Writable Properties panels show only in `edit`

**Files:**
- Modify: `barn/haybale-graph-editor/haybale_graph_editor/surfaces/graph.py:22`, `surfaces/node.py:26,40`, `surfaces/ports.py:23`, `surfaces/edge.py:44`; `packages/haywire-core/src/haywire/ui/panel/render_utils.py` (`_route_allows` :688 and its uses :751, :872; `promotable` :776; docstring :90-98); `.../panels/properties/introspect/edge.py:197-198`; `.../panels/properties/introspect/node_ports.py:154, :188, :277-278` and docstrings :131-133, :179-180
- Test: new `tests/graph_editor/test_inspector_polls.py`; delete or rewrite `tests/ui/panel/test_render_settings_route.py::test_rows_render_disabled_when_refused`, `::test_reset_and_set_to_none_grey_while_refused`, `::test_promotion_needs_the_routes_editor`; `tests/ui/panel/test_ports_panel_reorder.py::test_the_sortable_is_disabled_on_a_locked_level`; `tests/graph_editor/test_port_pen.py::test_the_port_pen_refuses_below_edit`; `tests/graph_editor/test_structure_edits.py::test_the_propagation_switch_refuses_below_edit`

**Interfaces:**
- Consumes: Task 1's `can_edit_graph(ctx)`.
- Produces:
  - `GraphInspector.poll` = `can_edit_graph(ctx) and active_graph is not None`; Node, Settings, Ports and Edge inspectors add `can_edit_graph(ctx) and` to their existing condition.
  - Rows: Reset, Set to none and widget enablement follow `UiState` only; Promote/Demote is offered whenever `route is not None`. `route is None` keeps its meaning (a bag no graph document owns, written directly), and every write path keeps its route refusal.
  - The propagation switch, the Ports panel's widgets, its pen icon and its sortable are always enabled; their write-time guards (`_on_change` snap-back, `_open_editor`'s `can_apply`, `_on_reorder`'s editor check) stay.
  - The panels' `if route is None: return` early exits stay (type narrowing).

- [ ] **Step 1: Write the tests** in `test_inspector_polls.py`, with an `EditState` whose `active_graph`, `active_node` and `active_edge` are set and whose `active_route` mode is parametrized:
  - `test_graph_inspectors_hide_below_edit[view|operate]`: all five polls false.
  - `test_graph_inspectors_show_in_edit`: all five true.
  - `test_no_route_shows_no_graph_inspector`: `active_route=None` → all five false.
  - `test_the_execution_tab_stays_in_view`: `ExecutionInspector.poll` true in `VIEW`.
  - Rewrite the three `test_render_settings_route.py` cases into `test_a_refused_row_write_snaps_back` (row drawn, route in `OPERATE`, edit → value unchanged, row shows the model value), or delete where an existing write-refusal test (:209, :219, :244, :257, :445) already covers it. Delete the sortable, pen and switch "disabled" tests; their write-refusal siblings stay.
- [ ] **Step 2: Run** — the new tests fail.
- [ ] **Step 3: Implement.**
- [ ] **Step 4: Run** `tests/graph_editor tests/ui/panel tests/ui/panels tests/ui/widget -n 4` — pass.
- [ ] **Step 5: Commit** `feat(graph-editor): writable Properties panels show only in level mode edit`.

### Task 5: The browser layer

**Files:**
- Modify: `packages/haywire-core/src/haywire/ui/components/graph/canvas.py` (`set_locked` :174); `packages/haywire-core/src/haywire/ui/components/graph/canvas.vue` (contract index :127-137, prop :172, watcher :341, guards :693, :777, :1167, :1609, :2113, :2815, `handleDoubleClick` :1809, `_handleElementSelection` :2362, `_startBoxSelection` :2568, the context-menu replace-then-act selection :1917/:1940, root element :2-6, global style block :4392+); `packages/haywire-core/src/haywire/ui/skin/base.py` (`render_widget` :136); `barn/haybale-studio/haybale_studio/skins/stacked_skin.py:361-368`; `.../graph_canvas_manager.py` (`refresh_mode`, end of `__init__`); `.../editors/graph_editor.py` (`_mount_view` :1132); `tests/ui/harness/routes.py` (`/graph-enter` page :1645, new `/graph-level-mode` page)
- Test: `tests/graph_editor/test_canvas_event_gating.py`, `tests/graph_editor/test_graph_editor_lock.py`, `tests/ui/skin/test_fold_header.py`, a `render_widget` test (new `tests/ui/skin/test_operable_stamp.py`), `tests/ui/harness/test_canvas_lock.py`, `tests/ui/harness/test_enter_by_double_click.py`, new `tests/ui/harness/test_level_mode_gate.py`

**Interfaces:**
- Consumes: Task 1's `refresh_mode`, `_HarnessLevel`.
- Produces:
  - `GraphCanvasVue.set_level_mode(mode: LevelMode) -> None`: sets prop `levelMode` (`"view"`/`"operate"`/`"edit"`). `set_locked` is deleted.
  - `canvas.vue`: prop `levelMode: { type: String, default: 'view' }` (fails closed); computed `editing` (`levelMode === 'edit'`); root attribute `:data-hw-level-mode="levelMode"`.
    - Every former `this.locked` guard reads `!this.editing`, and the watcher on `levelMode` keeps today's `locked` watcher body for the edit → non-edit transition.
    - Selection guards: `_handleElementSelection`, `_startBoxSelection` and the context menu's replace-then-act selection return without selecting unless `editing`. A mousedown on a card below `edit` arms no drag state.
    - `handleDoubleClick` emits `EnterGroupEvent` only when `levelMode !== 'view'`.
  - CSS, in the global style block (out-specifies the five layers, including `.connection-pin`'s `!important`; spec trap):
    ```css
    .graph-canvas[data-hw-level-mode="view"] .ui-node-slot *,
    .graph-canvas[data-hw-level-mode="operate"] .ui-node-slot * { pointer-events: none !important; }
    .graph-canvas[data-hw-level-mode="operate"] .ui-node-slot [data-hw-operable],
    .graph-canvas[data-hw-level-mode="operate"] .ui-node-slot [data-hw-operable] * { pointer-events: auto !important; }
    ```
    The gate sits on `.ui-node-slot` descendants, not on `[data-node-id]`: pins carry `data-node-id` too, and the positioned card root and slot must keep pointer input, so a double-click on the card body still reaches `handleDoubleClick`.
  - `BaseSkin.render_widget` stamps `data-hw-operable` on the element it returns (every card widget; 5b-4 makes it conditional on `operable`).
  - The stacked skin's fold header row adds `data-hw-operable` to its props (Decision 7).
  - `GraphCanvasManager.refresh_mode` pushes `canvas_vue.set_level_mode(self.route.mode())`; `__init__` ends with `self.refresh_mode()`, so `_mount_view` drops its explicit call.
  - Harness: `/graph-enter` takes `mode: str = "edit"` in place of `locked`. New page `/graph-level-mode?mode=view|operate|edit` holds one Group card whose interface inlet shows a number widget (reuse the `/graph-enter` fixture builder), plus one stacked-skin node with a fold. Each page renders its card ids as `data-testid` labels and stamps `data-hw-synced` last.

- [ ] **Step 1: Write the tests:**
  - Unit: `test_a_canvas_pushes_its_mode_when_built` (Review Focus 5): construct a manager over a route in `OPERATE` → `canvas_vue.set_level_mode` called with `LevelMode.OPERATE` before any lock call. Also `test_refresh_mode_pushes_the_route_mode` (parametrized over the three modes). Replace the boolean assertions in `test_the_browser_canvas_is_read_only_wherever_edit_is_refused` and `test_an_operate_principal_mounts_a_read_only_canvas_on_an_unlocked_level` with the mode.
  - Unit: `test_render_widget_stamps_operable` (the returned element's `_props` has `data-hw-operable`); `test_fold_header_is_operable` in `test_fold_header.py`.
  - Browser, in `test_level_mode_gate.py`: probe with `page.evaluate` of `document.elementFromPoint(x, y)` at an element's box centre.
    - `test_view_card_content_takes_no_pointer_input`: at the number widget's centre the hit is not inside `.widget-container`.
    - `test_operate_widgets_take_pointer_input`: the hit is inside `[data-hw-operable]`.
    - `test_operate_card_text_takes_no_pointer_input`: at the card title's centre the hit is outside `.ui-node-slot *` (it is the slot or the card root).
    - `test_operate_fold_header_toggles`: a click on the fold header flips `data-hw-fold-open`.
    - `test_view_double_click_does_not_enter`: `enter-log` stays empty.
    - `test_operate_double_click_on_a_widget_does_not_enter` (Review Focus 4).
    - `test_edit_card_content_takes_pointer_input`: the hit is inside `.widget-container`.
  - `test_canvas_lock.py`: drop Task 2's `xfail`, so `test_a_locked_canvas_selects_nothing` passes; `test_double_click_enters_on_a_locked_level` uses `?mode=operate`.
- [ ] **Step 2: Run** the unit files and `uv run pytest tests/ui/harness/test_level_mode_gate.py tests/ui/harness/test_canvas_lock.py tests/ui/harness/test_enter_by_double_click.py` — the new ones fail.
- [ ] **Step 3: Implement.** Then grep `canvas.vue` for any remaining `locked` reference that means the canvas lock (the per-node `data-node-props-locked` / `_isNodeLocked` is a different thing and stays).
- [ ] **Step 4: Run** the files above, then `uv run pytest -m browser -n 4 -q` — all pass.
- [ ] **Step 5: Commit** `feat(canvas): the browser canvas follows the level mode; card content gated below edit`.

### Task 6: A remote undo refreshes the selection toolbar

**Files:**
- Modify: `.../editors/graph_editor.py` (`_on_graph_data_mutated` :625, `_do_undo` :1522, `_do_redo` :1531)
- Test: `tests/graph_editor/test_graph_editor_commands.py` (`test_undo_and_redo_refresh_the_selection_toolbar` :193, `test_refused_undo_does_not_refresh_the_toolbar` :206)

**Interfaces:**
- Produces: `_on_graph_data_mutated` ends with `self._refresh_toolbar()` (`SelectionToolbarProvider.refresh` already no-ops while hidden). `_do_undo`/`_do_redo` no longer call it themselves.

- [ ] **Step 1: Write the tests:**
  - `test_a_peer_undo_refreshes_this_sessions_toolbar`: two `GraphEditor`s over one document; editor B's toolbar provider is a spy; A calls `_do_undo` and the `GraphDataMutated` it publishes is delivered to B's `_on_graph_data_mutated` → B's `refresh` is called once.
  - `test_a_farmhand_undo_refreshes_the_toolbar`: `_on_graph_data_mutated(ctx, GraphDataMutated())` → `refresh` called.
  - Keep `test_refused_undo_does_not_refresh_the_toolbar` (a refused undo publishes nothing).
- [ ] **Step 2: Run** — the first two fail.
- [ ] **Step 3: Implement.**
- [ ] **Step 4: Run** `tests/graph_editor -n 4` — pass.
- [ ] **Step 5: Commit** `fix(graph-editor): any undo of the document refreshes every session's selection toolbar`.

### Task 7: Docs, insight and gate

**Files:**
- Modify: `docs/adr/0055-every-user-edit-takes-the-edit-route.md`, `docs/adr/0051-operate-tier-and-the-canvas-lock.md` (:20, :22-23, :25, Consequences), `docs/adr/0027-studio-authentication.md:38-49`, `docs/guides/security.md:482-500, :539-540`, `docs/reference/glossary.md` (:376-379, the selection entries), `docs/superpowers/plans/2026-10-16-edit-route.md` ("Open after 5b-2"), `CLAUDE.md` (Framework gotchas list)
- Create: `.insights/project_level_mode_pointer_gate.md`

- [ ] **Step 1: ADR 0055**, corrected in place (no history notes):
  - The level-mode bullet (:22): the mode callable is `level_mode` and every graph-editor check reads the route. That covers canvas handlers (`@handles_event(access=LevelMode)`), `accepts_command`, menus, toolbar, inspector polls and `EditState.active_mode`.
  - A new bullet: the browser layer (`levelMode` prop, `data-hw-level-mode`, the `.ui-node-slot` pointer gate, `data-hw-operable`).
  - Consequences :48 ("still draws controls disabled") becomes: Properties panels show only in `edit`, so rows have no read-only rendering.
- [ ] **Step 2: ADR 0051**, in place:
  - :20: `view` pans and zooms on the document level; `operate` adds Enter and the widgets on cards and the stage; selection, copy, menus, toolbar, Undo/Redo and the Properties editor's writable panels need `edit`.
  - :22-23: drop "effective tier" and the `allows` sentence; the cap is on the level mode (`level_mode`).
  - :25: handlers declare a `LevelMode`; describe the browser layer as the second layer.
  - Consequences: the fold toggle is clickable only from `operate` on (a stopgap until it is a widget); annotation text is editable only in `edit`; the fold write remains a known gap until 5b-4.
- [ ] **Step 3: ADR 0027 :38-49**, in place, and drop the "Amended by" note. A `view` principal changes nothing through the studio's surfaces: every user edit takes the edit route, which refuses below the level mode it needs, and the browser gates card content as a second layer. The tiers guard against accidents, not malice. Remaining gaps are in the security guide.
- [ ] **Step 4: security.md :482-500** tier descriptions per the spec table. Retire "effective tier" in favour of level mode. Enforcement paragraph: handlers declare a level mode, the browser gate, and the route. Known-gaps box: the fold toggle now needs `operate` in the browser but still writes directly; annotation text needs `edit` in the browser; the haystack list is unchanged (5b-5). Fix :539-540 if its wording no longer matches.
- [ ] **Step 5: Glossary.**
  - **Operate (tier)** (:376): values on operable widgets on cards and the stage, plus Enter.
  - **Enter** (:377): double-click needs `operate`, the context-menu row needs `edit`.
  - **Level mode** (:379): add "selection needs `edit`".
  - The **Selection axis** entry (grep): selection needs level mode `edit`; locking a level clears it.
  - New row **Operable widget**: a card widget that takes pointer input in level mode `operate` (`data-hw-operable`). Every card widget is operable until `operable=False` exists. Aliases to avoid: live widget, performance control.
- [ ] **Step 6: Spec** "Open after 5b-2": mark the toolbar item done in 5b-3 and the other two deferred past 5b-3 (Decision 9).
- [ ] **Step 7: Insight** `project_level_mode_pointer_gate.md`, the non-obvious parts of the gate:
  - It keys on `.ui-node-slot *`, because pins carry `data-node-id` and the card root must keep input for a double-click Enter.
  - It needs `!important` against `.connection-pin`.
  - `pointer-events` leaves keyboard focus alone, so the route is the refusal.
  - The Vue default for `levelMode` is `view`, and a manager pushes its mode at construction.
  - Add a one-line entry under "Framework gotchas" in `CLAUDE.md`.
- [ ] **Step 8: Gate.** `uv run ruff check . --extend-exclude .scratch`, `uv run ruff format --check .`, the CLAUDE.md mypy command, `uv run mkdocs build --strict`, `uv run python scripts/bake_docs.py`. Then commit and run `uv run pytest -m "not browser and not perf" -n 4 -q > /tmp/t.log 2>&1; echo "exit=$?"` and `uv run pytest -m browser -n 4 -q`. All green.
- [ ] **Step 9: Commit** `docs: level mode (ADR 0055, 0051, 0027, security guide, glossary)`.
- [ ] **Step 10: Live-check list** for the user (studio started from the worktree):
  1. `edit` principal, unlocked: select, copy, context menu, toolbar and Properties all work as before.
  2. Select a node, lock (`Mod+E`): the selection clears, the toolbar hides, and Properties shows only the Execution tab.
  3. Locked: a click or box drag on cards selects nothing; card widgets (sliders, numbers) still work; card titles and pins take no clicks; fold headers still toggle.
  4. Locked: double-click a Group card's title → enters; double-click its number widget → no entry.
  5. Locked: `Mod+C`, `Mod+A`, Delete and Undo do nothing; `Mod+Shift+E` still switches to the stage, and the stage canvas is locked too.
  6. `operate` principal: same as 3–5 on an unlocked level; the lock button is disabled.
  7. `view` principal: pan and zoom work; widgets, fold headers and annotation double-click do nothing; double-clicking a Group does not enter; Properties shows only the Execution tab.
  8. Error ledger: reveal an error inside a Group as `view` (stays on the document, nothing selected), as `operate` (enters the Group, nothing selected), and as `edit` (enters and selects).
  9. Two browser sessions: B selects a node and the toolbar is up; A changes that node's lock flag through the toolbar, then undoes. B's toolbar Lock icon follows.
