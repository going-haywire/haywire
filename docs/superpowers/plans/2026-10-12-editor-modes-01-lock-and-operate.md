# Editor modes, slice 1: lock and the operate tier — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add an `OPERATE` access tier and a per-session, per-level canvas lock that caps the effective tier at OPERATE. Gate every graph mutation path by that effective tier, and make user value edits mark the graph unsaved.

**Architecture:**
- **One rule.** `allows(can_access, locked, required)` in the graph-editor library: the real tier satisfies `required`, and if the level is locked, OPERATE does too. Every gate calls it.
- **Gate points:**
  - the canvas event dispatcher (each handler declares a tier, default EDIT);
  - the context-menu and selection-toolbar openers;
  - a new `BaseEditor.accepts_command` hook that the editor wrapper consults;
  - a `WriteGate` that widgets, `bind()` bindings and settings rows check at the moment of the write.
- **Value edits mark the graph unsaved** through a new non-reassembly `ChangeReason`. A Graph-node forwards its interior's non-structural changes without restarting a running graph or redrawing its card.

**Tech Stack:** Python 3.12, NiceGUI/Vue 3, pytest (`uv run pytest`), ruff, mypy.

**Spec:** [2026-10-12-editor-modes.md](2026-10-12-editor-modes.md), sections "Two switches per open level" and "Tiers"; build-sequence item 1.

## Global Constraints

- **Tier ladder:** `view < operate < edit < admin`. The wire value is `"operate"`. Ranks are VIEW 0, OPERATE 1, EDIT 2, ADMIN 3.
- **OPERATE may only change values on widgets shown on node cards.** No context menus, no selection toolbar, no paste/cut/delete/duplicate, no Reset/Revalidate, no Properties writes, no Undo/Redo, no unlock.
- **VIEW** may pan, zoom, select, copy, enter levels and read panels. It may not change values.
- **The lock** belongs to the session and the level. It is never saved and never seen by another session.
- **The lock caps and never raises:** `effective = min(real tier, OPERATE)` while locked.
- **Unlocking needs the real EDIT tier. Save needs the real EDIT tier and ignores the lock. Undo/Redo are capped.**
- **The Properties editor (settings rows, Ports-panel widgets) is read-only below effective EDIT.**
- **Every rule is enforced where the write lands.** `BaseWidget.set_enabled()` only changes the look.
- **Key bindings:** `ToggleLock` is `Mod+E`, `access = EDIT`.
- **Graph default:** `GraphProperties.open_locked: BOOL = False`, applied when a level first opens in a session.
- **Farmhand:** `graph_editor_operate`, `access = OPERATE`.
- **Docs rules:** follow `.claude/rules/python-docs.md`. Glossary and ADR edits land in Task 8 with the code; none earlier.
- **Commit trailer:** end every commit message with `Co-Authored-By: Claude Opus 5.5 (1M context) <noreply@anthropic.com>`.

## Review Focus

1. **A stale page or a gesture in flight.** A `UserDragEnd` or `UserResizeEnd` arriving for a locked level is refused, and the moved nodes snap back to their model positions. Test in Task 3.
2. **Lock toggled while a Properties panel is open.** A row rendered before the lock refuses the write when it lands, and the view shows the model's value again. Test in Task 6.
3. **Keys in a locked canvas.** Undo, Delete and Paste do nothing, while `Mod+E` still unlocks for an EDIT principal. Test in Task 4.
4. **A slider moved inside a Group interior while the host graph runs.** The host is marked unsaved, execution is not restarted, and the Group card is not redrawn. Test in Task 5.
5. **A VIEW principal.** Card widgets refuse writes (VIEW < OPERATE), the lock toggle is disabled, and Save is refused. Tests in Tasks 4 and 6.

**Known residual, not gated in this slice:** the StackedNodeSkin fold disclosure writes its port directly from the skin, which has no session (`stacked_skin.py:378-387`). It stays clickable for VIEW. Record it in the slice-5 plan, where skins gain a render context.

---

### Task 1: The OPERATE tier

**Files:**
- Modify: `packages/haywire-core/src/haywire/core/access/tier.py` (enum, `_RANKS`, module docstring "three" → "four")
- Modify: `packages/haywire-studio/src/haywire_studio/cli/user.py:121` (pad `tier.value` to 7)
- Test: `tests/core/test_access/test_tier.py`, `tests/farmhand/test_tool_tiers.py`

**Interfaces:**
- Produces: `AccessTier.OPERATE` (`"operate"`), ranks 0/1/2/3.

- [ ] **Step 1: Extend the tier tests.** In `test_tier.py`:
  - Add `OPERATE` to the wire-value check (`AccessTier.OPERATE == "operate"`).
  - Change the rank assertion to `VIEW.rank < OPERATE.rank < EDIT.rank < ADMIN.rank`.
  - Extend the parametrized `satisfies` matrix to all 16 pairs. In particular, `OPERATE.satisfies(VIEW)` is True and `OPERATE.satisfies(EDIT)` is False.
  - Fix the "three-tier" docstring.
- [ ] **Step 2: Run** `uv run pytest tests/core/test_access/test_tier.py`. Expect FAIL (`AttributeError: OPERATE`).
- [ ] **Step 3: Add `OPERATE = "operate"` between VIEW and EDIT, and renumber `_RANKS`.** The CLI choices and the roster `ui.select` derive from the enum, so they need no edit.
- [ ] **Step 4: Run** `uv run pytest tests/core/test_access/ tests/test_user_cli.py tests/studio/test_roster_editor.py tests/auth/`. Expect PASS.
- [ ] **Step 5: Commit** `feat(access): add the operate tier between view and edit`.

### Task 2: The lock: rule, level state, and the graph default

**Files:**
- Create: `barn/haybale-graph-editor/haybale_graph_editor/access.py`
- Modify: `barn/haybale-graph-editor/haybale_graph_editor/state/edit_state.py` (add `active_locked: bool = False`)
- Modify: `barn/haybale-graph-editor/haybale_graph_editor/editors/graph_editor.py`:
  - `_Level` (:94-103) gains `locked: bool = False`;
  - `_open_level` (:221-235);
  - `_claim_session_state` (:540-562);
  - new `set_level_locked`.
- Modify: `barn/haybale-graph-editor/haybale_graph_editor/editors/graph_canvas/graph_canvas_manager.py` (`locked` attribute, `allows()`)
- Modify: `packages/haywire-core/src/haywire/core/graph/properties.py` (`open_locked`)
- Test: `tests/graph_editor/test_graph_editor_lock.py` (new), `tests/graph_editor/test_access_rule.py` (new)

**Interfaces:**
- Produces:
  - `access.allows(can_access: Callable[[AccessTier], bool], locked: bool, required: AccessTier) -> bool`;
  - `access.can_edit_graph(ctx: SessionContext) -> bool`, which is `allows(ctx.can_access, ctx.data[EditState].active_locked, EDIT)`;
  - `GraphCanvasManager.locked: bool`;
  - `GraphCanvasManager.allows(required: AccessTier) -> bool`;
  - `GraphCanvasManager.set_locked(locked: bool) -> None` (also pushes the Vue prop; Task 3 adds the prop);
  - `GraphEditor.set_level_locked(context, key: str, locked: bool) -> bool` (False when refused).

- [ ] **Step 1: Write the rule tests** in `test_access_rule.py`. Use the `_ctx(tier)` mock style of `tests/ui/panel/test_panel_access.py`.
  - `test_unlocked_follows_the_real_tier`: `allows(edit.can_access, False, EDIT)` is True; `allows(view.can_access, False, OPERATE)` is False.
  - `test_locked_caps_at_operate`: `allows(admin.can_access, True, EDIT)` is False; `allows(admin.can_access, True, OPERATE)` is True.
  - `test_lock_never_raises`: `allows(view.can_access, True, OPERATE)` is False.
- [ ] **Step 2: Write the level tests** in `test_graph_editor_lock.py`, using `_editor()` from `tests/graph_editor/test_graph_editor_levels.py`. For `context.can_access`, use a real `SessionContext` with `set_access_resolver`, as in `tests/core/test_session/test_context_access.py`.
  - `test_a_document_opens_with_the_graph_default`: the graph's `props.open_locked = True` gives `editor._levels[DOCUMENT_LEVEL].locked is True`.
  - `test_locking_is_per_level`: lock the document level, descend into a Group; the Group level is unlocked.
  - `test_unlock_needs_real_edit`: an OPERATE principal's `set_level_locked(ctx, key, False)` returns False and the level stays locked; an EDIT principal's returns True.
  - `test_claim_publishes_the_lock`: `set_level_locked` on the active level sets `context.data[EditState].active_locked` and publishes `ActiveGraphMoved`.
- [ ] **Step 3: Run** both files. Expect FAIL (import errors).
- [ ] **Step 4: Implement.**
  - `allows` is two conditions: `can_access(required)`, and if `locked`, `AccessTier.OPERATE.satisfies(required)`.
  - `open_locked = setting[BOOL](False, label="Open locked", category="behaviour")`, following the existing `GraphProperties` field style. A new category is fine if none fits.
  - `_open_level` reads the level graph's `props.open_locked` once.
  - `_claim_session_state` also compares and sets `active_locked`, so a lock change on the same graph is not short-circuited.
  - `set_level_locked`:
    - refuses unlocking unless `context.can_edit()` (the real tier);
    - sets `_Level.locked` and `canvas_manager.set_locked`;
    - re-claims session state when the level is active.
- [ ] **Step 5: Run** both files and `tests/graph_editor/`. Expect PASS.
- [ ] **Step 6: Commit** `feat(graph-editor): per-level canvas lock capping the effective tier at operate`.

### Task 3: Gate the canvas: events, menus, toolbar, and the Vue gestures

**Files:**
- Modify: `barn/haybale-graph-editor/haybale_graph_editor/editors/graph_canvas/event_handlers.py` (`handles_event(..., access=AccessTier.EDIT)` stamps `_handles_event_access`)
- Modify: `graph_canvas_manager.py:237-252` (`_handle_canvas_event` checks `self.allows(...)`)
- Modify: handler files in `editors/graph_canvas/handlers/`. Declare `access=AccessTier.VIEW` on:
  - SelectionChanged, UserCopySelected, EdgeClicked, the five ContextMenu* events, SelectionBounds, SelectionBoundsHide, CanvasMounted, NodesMeasured, EnterGroup.

  Every other event keeps the default EDIT.
- Modify: `handlers/context_menu.py:856` (`process_context_menu` returns without opening when `not manager.allows(EDIT)`)
- Modify: `handlers/selection_toolbar.py:322` (same gate; hide the toolbar)
- Modify: `handlers/visual_layer.py` (new `resync_positions(node_ids: Iterable[str]) -> None`, which calls `update_node_position` with the model's `props.posX/posY`)
- Modify: `packages/haywire-core/src/haywire/ui/components/graph/canvas.py` (`set_locked(locked: bool)` sets `self._props["locked"]` and calls `update()`)
- Modify: `packages/haywire-core/src/haywire/ui/components/graph/canvas.vue`:
  - prop `locked: { type: Boolean, default: false }`;
  - while locked, return early from node-drag start (`_startUnifiedDrag`), the resize grip (`onResizeGripDown`), pin edge drag (`_enterActiveEdge`), reconnect, and paste event creation;
  - selection, marquee, context-menu and copy stay live;
  - document the prop in the attribute and prop index at the top of the file.
- Test: `tests/graph_editor/test_canvas_event_gating.py` (new); one browser test in `tests/ui/harness/` (marked `browser`)

**Interfaces:**
- Consumes: `GraphCanvasManager.allows`, `set_locked` (Task 2).
- Produces: `handles_event(*event_classes, access: AccessTier = AccessTier.EDIT)`; `VisualLayerHandlers.resync_positions(node_ids)`.

- [ ] **Step 1: Write the dispatcher tests.** Build a manager with a stub handler map.
  - `test_unmarked_handlers_need_edit`: locked, a default-EDIT handler is not called.
  - `test_view_handlers_run_while_locked`: a `SelectionChanged` handler is called while locked.
  - `test_refused_drag_end_resyncs_positions`: a refused `UserDragEnd` calls `resync_positions` with the event's node ids.
  - `test_refused_resize_end_resyncs_positions`: a refused `UserResizeEnd` calls `resync_positions` with the event's node ids.
  - `test_no_menu_below_edit`: `process_context_menu` with a locked manager calls no `provider.on_*_context`.
  - `test_no_toolbar_below_edit`: same for `process_selection_bounds`.
- [ ] **Step 2: Run.** Expect FAIL.
- [ ] **Step 3: Implement the Python side.** On refusal, `_handle_canvas_event` resyncs positions for `UserDragEnd` and `UserResizeEnd`, and logs every other refusal at debug.
- [ ] **Step 4: Implement the Vue prop and early returns.**
- [ ] **Step 5: Write the browser test** `test_locked_canvas_blocks_drag`. Lock the level, drag a node 100px, and assert its `left` style and `props.posX` are unchanged. Use `goto_ready`; see `tests/ui/harness/`.
- [ ] **Step 6: Run** `uv run pytest tests/graph_editor/ -n 4`, then `uv run pytest -m browser -n 4 -k locked`. Expect PASS.
- [ ] **Step 7: Commit** `feat(graph-editor): gate canvas events, menus and toolbar by effective tier`.

### Task 4: Commands, the lock toggle and the header buttons

**Files:**
- Modify: `packages/haywire-core/src/haywire/ui/editor/base.py`: add `accepts_command(self, context: SessionContext, command: EditorCommand) -> bool`, which returns True by default.
- Modify: `packages/haywire-core/src/haywire/ui/editor/wrapper.py:438-443`: `_dispatch` also returns when `not instance.accepts_command(self._session.context, event)`.
- Modify: `packages/haywire-core/src/haywire/core/signals/vocabulary.py`: add `ToggleLock` (`command_id = "toggle_lock"`, `label = "Lock / Unlock"`, `default_keys = ("Mod+E",)`, `access` left at the default EDIT); add it to `__all__`.
- Modify: `graph_editor.py`:
  - `accepts_command`: `ToggleLock` always passes, since the wrapper already checked the real tier; any other command passes `allows(context.can_access, active_level.locked, type(command).access)`.
  - `@react_on(ToggleLock) _on_toggle_lock`, which calls `set_level_locked(context, self._active_level, not locked)`.
  - Header (:613-622): a lock `hui.icon_action` beside the breadcrumb (`lock` / `lock_open`, `command=ToggleLock`), disabled when `not context.can_edit()`.
  - `_update_undo_redo_buttons` (:937-942) also disables Undo/Redo when `not self._canvas_manager.allows(EDIT)`.
  - `_do_undo` / `_do_redo` return without acting when refused.
  - `_save_graph` returns with a `ui.notify` refusal when `not context.can_edit()` (the real tier).
- Test: `tests/graph_editor/test_graph_editor_commands.py`, `tests/core/signals/test_editor_command.py`, `tests/ui/test_editor_command_delivery.py`

**Interfaces:**
- Consumes: `access.allows`, `GraphEditor.set_level_locked` (Task 2).
- Produces: `ToggleLock`; `BaseEditor.accepts_command`.

- [ ] **Step 1: Write the tests.**
  - `test_toggle_lock_identity` in `test_editor_command.py`: id, label, `("Mod+E",)`, `access is AccessTier.EDIT`.
  - `test_dispatch_asks_the_editor` in `test_editor_command_delivery.py`: an instance whose `accepts_command` returns False never receives the command.
  - In `test_graph_editor_commands.py`:
    - `test_locked_level_refuses_undo_delete_paste`: with the active level locked and an ADMIN principal, `accepts_command` is False for `Undo`, `Delete`, `Paste` and True for `Copy`, `SelectAll`, `ToggleLock`.
    - `test_toggle_lock_unlocks_for_edit`.
    - `test_save_ignores_the_lock`: locked level, EDIT principal; `_save_graph` saves.
    - `test_save_refused_below_edit`: an OPERATE principal's `_save_graph` does not call `entry.save`.
- [ ] **Step 2: Run.** Expect FAIL.
- [ ] **Step 3: Implement** as listed under Files.
- [ ] **Step 4: Run** `uv run pytest tests/graph_editor/ tests/core/signals/ tests/ui/test_editor_command_delivery.py tests/ui/keymap/`. Expect PASS.
- [ ] **Step 5: Commit** `feat(graph-editor): ToggleLock command, lock toggle, capped undo/redo, real-tier save`.

### Task 5: User value edits mark the graph unsaved

**Files:**
- Modify: `packages/haywire-core/src/haywire/core/graph/types.py`:
  - add `NODE_VALUE_CHANGED = "node_value_changed"` and `GRAPH_CONTENT_CHANGED = "graph_content_changed"`. Neither is visual-only, and neither is in `requires_graph_reassembly()`.
  - add `ValidationResult.requires_reassembly() -> bool`: any node, edge or graph reason for which `requires_graph_reassembly()` is true.
- Modify: `packages/haywire-core/src/haywire/core/node/node_wrapper.py`: `mark_value_edited(self) -> None`. It marks `NODE_VALUE_CHANGED` on the node's graph and does nothing while the node is unregistered, like `mark_as_structuraly_dirty`.
- Modify: `packages/haywire-core/src/haywire/core/undo/actions/graph_actions.py:962-972`: `SetPropertyAction.execute` and `undo` call `mark_value_edited()`.
- Modify: `packages/haywire-core/src/haywire/barn/builtin/nodes/graph_node.py:122-127`: when `result.requires_save()`, then
  - if `result.requires_reassembly()`: redraw and forward `GRAPH_REQUIRE_REASSEMBLY`, as today;
  - otherwise forward `GRAPH_CONTENT_CHANGED` with no redraw.
- Check: the validation pass and `VisualLayerHandlers.on_validated` treat the two new reasons as no-ops (no rebuild, no redraw). Add a branch only if one is not.
- Test: `tests/core/test_graph/test_value_change_reason.py` (new), `tests/core/test_graph/` Group interior test (extend the nearest existing `GraphNode` forwarding test)

**Interfaces:**
- Produces: `ChangeReason.NODE_VALUE_CHANGED`, `ChangeReason.GRAPH_CONTENT_CHANGED`, `ValidationResult.requires_reassembly()`, `NodeWrapper.mark_value_edited()`.

- [ ] **Step 1: Write the tests.**
  - `test_value_change_requires_save_not_reassembly`: after `mark_value_edited()`, the forced validation result (`force_immediate_validation()`) has `requires_save()` True and `requires_reassembly()` False.
  - `test_set_property_marks_unsaved`: `editor.set_property(node_id, "x", 3)` yields a result with `NODE_VALUE_CHANGED` for that node.
  - `test_interior_value_edit_forwards_content_changed`: a Group whose interior node calls `mark_value_edited()`. The host's result carries `GRAPH_CONTENT_CHANGED`, not `GRAPH_REQUIRE_REASSEMBLY`, and the card's `wrapper.redraw` is not called (patch it).
  - `test_interior_structure_edit_still_reassembles`: adding a node inside the interior still forwards `GRAPH_REQUIRE_REASSEMBLY` and redraws.
  - `test_running_host_not_restarted_by_value_edit`: build a `HaystackState` entry the way `tests/haystack/` builds one, and set `is_executing`. After an interior `mark_value_edited()`, `stop_execution` is not called and `entry.unsaved` is True.
- [ ] **Step 2: Run.** Expect FAIL.
- [ ] **Step 3: Implement.**
- [ ] **Step 4: Run** `uv run pytest tests/core/test_graph/ tests/haystack/ tests/graph_editor/`. Expect PASS.
- [ ] **Step 5: Commit** `fix(graph): user value edits mark the graph unsaved without reassembly`.

### Task 6: The write gate: widgets, bindings and settings rows

**Files:**
- Create: `packages/haywire-core/src/haywire/ui/widget/write_gate.py`. It holds a `Protocol` `WriteGate` with `allows(self) -> bool` and `written(self) -> None`.
- Modify: `packages/haywire-core/src/haywire/ui/widget/base.py`:
  - `write_gate: Optional[WriteGate] = None`;
  - `accepts_write(self) -> bool`, which combines the existing linked/own-value condition with `write_gate.allows()`;
  - `set_value` uses `accepts_write()` and calls `write_gate.written()` after a write;
  - `bind()` passes `self` to the `PropertyBinding` it creates.
- Modify: `packages/haywire-core/src/haywire/ui/widget/binding.py:152-169`: `_sync_to_model` uses the owner's `accepts_write()` (falling back to today's condition when it has no owner) and calls `written()` after the write.
- Modify: `packages/haywire-core/src/haywire/ui/panel/render_utils.py`: `render_settings(..., gate: Optional[WriteGate] = None)` is threaded to `_render_reactive_field_row`.
  - Rows render disabled when `gate and not gate.allows()`.
  - `_bag_on_edit`, `_on_reset_click`, `_set_to_none` and promote/demote refuse when the gate refuses at call time, re-syncing the row.
  - `written()` is called after an accepted write.
- Create: in `haybale_graph_editor/access.py`, `NodeWriteGate(required: AccessTier, allows_fn: Callable[[AccessTier], bool], wrapper: NodeWrapper)`. `allows()` returns `allows_fn(required)`; `written()` calls `wrapper.mark_value_edited()`. Also `GraphWriteGate`, where `written()` does nothing, because graph props and metadata do not mark the file dirty by design and edge style has `EDGE_STYLE_CHANGED`.
- Modify: `barn/haybale-graph-editor/haybale_graph_editor/editors/graph_canvas/ui_node.py:204`: after `factory.render(...)`, set `widget.write_gate = NodeWriteGate(OPERATE, manager.allows, wrapper)` on every instance in `current_ui_card.widget_instances`. `UINode` receives `allows_fn` from `VisualLayerHandlers`, which receives it from the manager.
- Modify: `panels/properties/introspect/node_ports.py:192` and `:304`. Ports-panel widgets get `NodeWriteGate(EDIT, lambda r: allows(ctx.can_access, ctx.data[EditState].active_locked, r), wrapper)`. `_on_reorder` refuses when `not can_edit_graph(context)`.
- Modify: the graph-editor panels that call `render_settings` (node properties, node settings, graph properties and metadata, edge style; find them with `grep -rn "render_settings(" barn/haybale-graph-editor`). Pass the matching gate at EDIT.
- Test: `tests/ui/widget/test_write_gate.py` (new), `tests/ui/panel/test_render_settings_gate.py` (new)

**Interfaces:**
- Consumes: `NodeWrapper.mark_value_edited` (Task 5), `access.allows` / `can_edit_graph` (Task 2), `GraphCanvasManager.allows` (Task 2).
- Produces: `WriteGate`, `BaseWidget.write_gate`, `BaseWidget.accepts_write()`, `render_settings(..., gate=...)`, `NodeWriteGate`, `GraphWriteGate`.

- [ ] **Step 1: Write the widget tests.** Mirror `tests/ui/widget/test_linked_widget_writes.py`, with a stub gate whose `allows` result can be toggled and which counts `written` calls.
  - `test_a_refused_gate_snaps_the_view_back`: via `_bindings[0]._sync_to_model(9.0)`, the own value is unchanged and the view shows the model value.
  - `test_a_refused_gate_blocks_set_value`.
  - `test_an_accepted_write_calls_written_once`.
  - `test_no_gate_behaves_as_today`.
- [ ] **Step 2: Write the settings tests.**
  - `test_rows_render_disabled_when_refused`.
  - `test_a_stale_row_refuses_at_write_time`: render with the gate allowing, flip it to refuse, call the row's `on_edit`; the bag value is unchanged.
  - `test_written_called_after_edit`.
- [ ] **Step 3: Write the graph-editor tests.**
  - `test_card_widgets_get_an_operate_gate`: a VIEW principal's card widget refuses; an OPERATE principal's accepts and marks `NODE_VALUE_CHANGED`.
  - `test_ports_panel_widgets_need_edit`: on a locked level, an ADMIN principal's Ports-panel widget refuses.
- [ ] **Step 4: Run.** Expect FAIL.
- [ ] **Step 5: Implement.**
- [ ] **Step 6: Run** `uv run pytest tests/ui/widget/ tests/ui/panel/ tests/graph_editor/ -n 4`. Expect PASS.
- [ ] **Step 7: Commit** `feat(ui): write gate on widgets, bindings and settings rows; enforce effective tier at the write`.

### Task 7: `graph_editor_operate`

**Files:**
- Modify: `barn/haybale-graph-editor/haybale_graph_editor/farmhands/editor_tools.py`: add `GraphEditorOperateTool`, `registry_id="operate"`, `annotations=_MUTATING`, `access=AccessTier.OPERATE`.
  - `run(self, ctx, binding_id: str, node_id: str, port_id: str, value: Any = None) -> dict`
  - Raise `FarmhandError("not_operable", ...)` unless the port exists, `port.widget_key` is set, `port.should_show_widget()` is true and `port.data.accepts_own_value()`. The `help` points to `graph_editor_inspect_node`.
  - Then `port.set_value(value)`, `wrapper.mark_value_edited()`, the same read-back check and `set_rejected` error as `GraphEditorSetPropertyTool`, `ctx.broadcast(GraphDataMutated())`, and a summary. Not undo-recorded, like a widget edit.
- Modify: `tests/farmhand/test_tool_tiers.py`: add an `OPERATE_TOOLS` set containing `operate`.
- Test: `tests/farmhand/test_graph_editor_tools.py`, `tests/farmhand/test_farmhand_access.py`

**Interfaces:**
- Consumes: `AccessTier.OPERATE` (Task 1), `NodeWrapper.mark_value_edited` (Task 5).

- [ ] **Step 1: Write the tests.**
  - `test_operate_writes_a_shown_widget`: the value is read back and the graph entry is unsaved.
  - `test_operate_refuses_a_hidden_widget`: a port with `ShowWidgetStrategy.NEVER` raises `not_operable`.
  - `test_operate_refuses_a_linked_inlet`.
  - `test_operate_listed_for_operate_not_view`: `tools_for_tier(..., OPERATE)` contains it and `VIEW` does not.
- [ ] **Step 2: Run.** Expect FAIL.
- [ ] **Step 3: Implement.**
- [ ] **Step 4: Run** `uv run pytest tests/farmhand/ -n 4`. Expect PASS.
- [ ] **Step 5: Commit** `feat(farmhand): graph_editor_operate for operate-tier agents`.

### Task 8: Docs, glossary, ADR

**Files:**
- Create: `docs/adr/0051-operate-tier-and-the-canvas-lock.md`. Use the front-matter and section shape of ADR 0050. It covers:
  - the four-tier ladder;
  - the lock as a per-session, per-level cap that never raises;
  - why OPERATE is "values on shown widgets": ghost pins make value-driven rejig reversible, authors hide with `NEVER`, and the noted per-port `access=` escape hatch;
  - why Save uses the real tier;
  - enforcement at the write (`WriteGate`).
  - `see-also: ADR-0027, ADR-0050`.
- Modify: `docs/adr/0027-studio-authentication.md`: add a one-line amendment note pointing to 0051 at :38-41 and :125-126.
- Modify: `docs/guides/security.md`:
  - :454-458 becomes `--tier {view,operate,edit,admin}`;
  - replace the :482-488 "Known gap" warning with a short section on what each tier and the lock allow;
  - :523 becomes "view/operate/edit/admin".
- Modify: `docs/reference/glossary.md`: add **Lock**, **Operate (tier)**, **Effective tier** and **Write gate** as rows in the existing table style (term | definition | avoid).
- Modify: `docs/guides/signals.md:433` and `docs/components/panels/panel-canon.md:129`: name the four tiers.
- Run: `uv run python scripts/bake_docs.py` to refresh `_baked_docs`.

- [ ] **Step 1: Write the ADR and edit the docs.**
- [ ] **Step 2: Bake and run** `uv run pytest tests/ -k "bake or docs" -n 4` and `uv run mkdocs build --strict`. Expect PASS.
- [ ] **Step 3: Commit** `docs: operate tier and canvas lock (ADR 0051)`.

### Task 9: Full gate

- [ ] **Step 1:** `uv run ruff check . && uv run ruff format --check .`
- [ ] **Step 2:** the CLAUDE.md mypy command (all package roots plus `tests/`).
- [ ] **Step 3:** `uv run pytest -m "not browser and not perf" -n 4 -q > /tmp/t.log 2>&1; echo "exit=$?"`. Expect `exit=0`.
- [ ] **Step 4:** `uv run pytest -m browser -n 4`. Expect PASS.
- [ ] **Step 5: Live check in the studio.**
  - `Mod+E` toggles the lock in Chrome. On Windows/Linux, confirm the address bar does not take it.
  - A locked level blocks drag, connect, menus and Undo, while card widgets still work.
  - An OPERATE login sees the lock disabled and can move sliders only.
