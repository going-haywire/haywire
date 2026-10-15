# Editor modes, slice 5a: Stage core — Implementation Plan

> Superseded in part by 2026-10-15-editor-modes-05a2-stage-is-a-display.md (Decisions 1 and 6).

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** a node can be put on a graph's **stage**. Each open level gets a **Patch | Stage** switch, and stage view shows only the on-stage nodes. They sit at their own stage rect, drawn by a frameless stage face, and connected only by on-stage wires. Unlocked, stage view lets the user arrange the nodes and nothing more.

**Architecture:**
- **The stage is a second layout channel.** `STAGE` names the `stage_*` props fields, plus three new channel facts:
  - which nodes it includes (`member="on_stage"`);
  - where its origin sits on the canvas (`origin=200.0`);
  - that it draws stage faces and only on-stage edges (`stage=True`).
- A `GraphCanvasManager(channel=STAGE)` is the stage view. Its visual layer filters nodes and edges, translates positions by the origin, and asks the skin for `render_stage()`.
- **One level, two keep-alive panels** (Decision Q2c).
  - Each level holds a canvas per view in an inner `ui.tab_panels(...).props("keep-alive")`.
  - The stage canvas mounts on the first switch to it, and after that both stay mounted. Switching back is instant, the way graph tabs are.
  - A deactivated panel's DOM is detached, so page-global pin uuids never collide. Task 6 proves this in a browser.
- **Arrange only.** In stage view, an EDIT-tier canvas gesture, editor command or menu row runs only if it is on the stage allow-list (Decision Q7a). Delete stays a normal delete.

**Tech Stack:** Python 3.12, NiceGUI/Vue 3 (`canvas.vue`), pytest (`uv run pytest`), Playwright browser tier, ruff, mypy.

**Spec:** [2026-10-12-editor-modes.md](2026-10-12-editor-modes.md), sections "Two switches per open level" and "Stage", and Sequence item 5. The decisions below were taken with the user on 2026-10-14. They refine the spec and bind where they differ.

## Decisions (2026-10-14)

1. **(Q1)** Slice 5 ships as four plans: **5a** stage core (this plan), **5b** stage content (on-stage connector editing, the Annotation stage face, annotation text editing, Add Annotation), **5c** stacking order (`z`/`stage_z` and the four verbs), **5d** control nodes. Each merges into `feat/editor-modes-slice1` when it lands.
2. **(Q2c)** Patch and Stage are two keep-alive panels per level. The stage canvas mounts lazily, both stay mounted, and switching clears the selection.
3. **(Q3a)** `stage_x`/`stage_y` are relative to the stage origin.
   - The origin is fixed and cannot be edited: it is stage `(0, 0)`. `STAGE.origin` is only the canvas margin it is drawn at.
   - Positions are translated only at the visual layer (outbound) and the interaction handler (inbound).
   - **(Q3b, b)** An L-shaped corner bracket marks the origin. It has two short lines, one running right and one running down from the origin, and replaces the spec's grey band.
   - **(Q3c, a)** Drags stop at the origin, so nothing sits above or left of it.
4. **(Q4a)** `BaseGraph` keeps one canvas extent per channel. `ValidationResult` carries extents per channel name, and each canvas applies only its own.
5. **(Q5a)** `on_stage` is a bool props field in a new `"stage"` category. A write to it raises `ChangeReason.NODE_STAGE_CHANGED`. The stage canvas mounts or unmounts the node on that reason, and the patch canvas ignores it.
6. **(Q6a)** `WireType.on_stage: ClassVar[bool] = False`, set to `True` on `AnnotationWire`. `DataPort.on_stage` and `EdgeWrapper.on_stage` derive it the way `wire_key` and `carries_values` do. There is no `@wire` decorator.
7. **(Q7a, corrected by the user)** Stage view runs an EDIT-tier gesture, command or row only if it is on the stage allow-list. **Delete is not remapped**: in stage view it deletes the node from the graph, exactly as in patch view. Remove from Stage is its own verb.
8. **(Q8a)** The Patch | Stage switch sits in the editor header next to the lock button. The level bar stays hidden while only one level is open.

## Controller rulings (planning)

- **R1, Add to Stage placement.** Every added node goes at `x = STAGE_MARGIN`, `y = (max of stage_y + stage_height over the nodes already on stage) + STAGE_MARGIN`, or `y = STAGE_MARGIN` on an empty stage. `STAGE_MARGIN = 40.0`. Several nodes added at once stack downward in patch order (patch `posY`, then `posX`), each below the previous one at the margin. `stage_size_adapt` is set to `"auto"`.
- **R2, Remove from Stage keeps the stage rect.** It sets `on_stage = False` only. Add to Stage always re-places the node by R1, as the spec says.
- **R3, default stage face.** `BaseSkin.render_stage` draws, in port order and in one column:
  - every port with `widget_key is not None and should_show_widget()`, through `BaseSkin.render_widget`;
  - a pin for every port whose `on_stage` is true, through `pin_render.render_pin` with `card_padding=0`.

  The card has no frame and no lanes, and carries the classes `node-card drag-handle hw-stage-face` with a transparent background. It never inherits fold or collapse state.
- **R4, the empty stage viewport.** A stage canvas with no nodes centres on `(STAGE.origin + 400, STAGE.origin + 300)`, so the origin corner is in view.
- **R5, edges.** A stage canvas registers an edge only when `edge.on_stage` is true and both end nodes are included. It applies the same filter at every place it counts or iterates edges.

## Global Constraints

- `layout.py`:
  - `STAGE = LayoutChannel(name="stage", x="stage_x", y="stage_y", width="stage_width", height="stage_height", size_adapt="stage_size_adapt", member="on_stage", origin=200.0, stage=True)`.
  - `PATCH` gains `member=None, origin=0.0, stage=False` by default and is otherwise unchanged.
  - `CHANNELS = (PATCH, STAGE)`.
- `NodeProperties`, in `category="stage"`, kept together:
  - `on_stage = setting[BOOL](False)`
  - `stage_x`/`stage_y` = `setting[FLOAT](0.0)`
  - `stage_width`/`stage_height` = `setting[INT](200)`
  - `stage_size_adapt` = `setting[CHOICES]("auto")`, with the same options as `size_adapt`

  None of them goes in `REDRAW_FIELDS`.
- `GraphProperties.open_view = setting[CHOICES]("patch", options {"patch": "Patch", "stage": "Stage"}, category="behaviour", order=20)`, next to `open_locked`.
- `ToggleStageView`: `command_id="toggle_stage_view"`, `label="Patch / Stage"`, `default_keys=("Mod+Alt+E",)`, `access=AccessTier.VIEW`.
- A file without stage fields loads with every node off stage. There is no `format_version` bump.
- `NODE_STAGE_CHANGED` is save-relevant: it is not `is_visual_only()`, and it does not require graph reassembly.
- The JS canvas changes only by two props, `originX`/`originY` (default 0, meaning no marker and the existing clamp at 0).
  - When either is non-zero, the canvas draws the origin marker in its background layer: an L-shaped corner bracket at `(originX, originY)`, with arms 24 px long running right and down, stroked in the grid colour at a stronger opacity.
  - Drags clamp at `(originX, originY)`.
  - No JS event changes.
- The Farmhand tools are unchanged: `graph_editor_set_property` already writes every stage field.
- **Docs:** follow `.claude/rules/python-docs.md`. The ADR and glossary land in Task 7.
- **Commit trailer:** `Co-Authored-By: Claude Opus 5.5 (1M context) <noreply@anthropic.com>`.

## Review Focus

1. **Switching views never re-renders the patch.** The same `UINode` objects survive a Patch → Stage → Patch round trip. Edges in both views draw at their own pins, even for a node shown in both (Task 6, browser).
2. **Changes while a view is hidden.** A node added to, removed from, moved on, or deleted from the stage while the stage panel is hidden appears correctly when the stage is shown. The same holds for the patch while the stage is shown (Tasks 4 and 6).
3. **A node at stage `(0, 0)`** sits exactly at the origin corner and round-trips through save and load, although sparse serialization omits zero values (Tasks 1 and 4).
4. **Arrange only.** In unlocked stage view at EDIT:
   - paste, duplicate, cut, node creation, edge creation and the patch context-menu rows are refused;
   - move, resize, select, copy, Remove from Stage, Delete and Undo/Redo work.

   Locked stage view lets OPERATE change shown widgets only (Tasks 5 and 6).
5. **Two canvases per level.** The lock, the session claim, a pointer gesture's claim, re-keying and pruning a level all act on the visible canvas or on both, never on a stale one (Task 6).

---

### Task 1: The stage model

**Files:**
- Modify:
  - `packages/haywire-core/src/haywire/core/node/layout.py`
  - `packages/haywire-core/src/haywire/core/node/properties.py`
  - `packages/haywire-core/src/haywire/core/graph/properties.py`
  - `packages/haywire-core/src/haywire/core/types/wire.py`
  - `packages/haywire-core/src/haywire/barn/builtin/types/annotation.py`
  - `packages/haywire-core/src/haywire/core/types/port.py`
  - `packages/haywire-core/src/haywire/core/edge/edge_wrapper.py`
- Test: create `tests/core/test_node/test_stage_model.py`.

**Interfaces — produces:**
- `LayoutChannel` gains `member: str | None = None`, `origin: float = 0.0` and `stage: bool = False`, plus:
  - `includes(props) -> bool`: true when `member is None`, else `bool(getattr(props, member))`;
  - `to_canvas(x, y) -> tuple[float, float]`: adds `origin` to both;
  - `from_canvas(x, y) -> tuple[float, float]`: subtracts `origin` from both.
- `STAGE` and `CHANNELS`, as in Global Constraints.
- The `NodeProperties` stage fields and `GraphProperties.open_view`.
- `WireType.on_stage` (False), `AnnotationWire.on_stage = True`, `DataPort.on_stage -> bool` and `EdgeWrapper.on_stage -> bool`.

- [ ] **Step 1: Tests.**
  - `test_stage_channel_names_the_stage_fields`: `props.set_position((10.0, 20.0), STAGE)` sets `stage_x == 10.0` and `stage_y == 20.0`, and leaves `posX`/`posY` alone.
  - `test_patch_includes_every_node_and_stage_only_on_stage_nodes`.
  - `test_origin_translation`: `STAGE.to_canvas(0, 0) == (200.0, 200.0)`, `STAGE.from_canvas(200, 260) == (0.0, 60.0)`, and `PATCH.to_canvas(5, 6) == (5.0, 6.0)`.
  - `test_stage_fields_round_trip_including_the_origin`: a node with `on_stage=True` at stage `(0, 0)` keeps `on_stage` and its stage position through `to_dict` → `load_from_dict`.
  - `test_a_file_without_stage_fields_loads_off_stage`.
  - `test_annotation_wire_is_on_stage_and_exec_is_not`: `DataPort.on_stage` on an `ANNOTATION` swinglet and on an EXEC port. An edge between two annotation swinglets is `on_stage`.
  - `test_open_view_defaults_to_patch`.
- [ ] **Step 2: Run** `uv run pytest tests/core/test_node/test_stage_model.py -q`. Expect FAIL.
- [ ] **Step 3: Implement.** Keep the `"stage"` fields together, because the settings panel re-opens a category that another one interrupts. Import `CHOICES` in `graph/properties.py`.
- [ ] **Step 4: Run** the file, then `uv run pytest tests/core/ -n 4 -q`. Expect PASS.
- [ ] **Step 5: Commit** `feat(node): the stage channel, its props fields and on-stage wires`.

### Task 2: Graph core — extents per channel, the stage-change reason, Add/Remove

**Files:**
- Modify:
  - `packages/haywire-core/src/haywire/core/graph/base.py`
  - `packages/haywire-core/src/haywire/core/graph/types.py`
  - `packages/haywire-core/src/haywire/core/graph/validation.py`
  - `packages/haywire-core/src/haywire/core/node/node_wrapper.py`
  - `packages/haywire-core/src/haywire/core/undo/actions/graph_actions.py`
  - `packages/haywire-core/src/haywire/core/graph/editor.py`
  - every reader of `ValidationResult.canvas_size`: grep `canvas_size` across `packages/`, `barn/` and `tests/`; there are 14 constructor hits.
- Test: create `tests/core/test_graph/test_stage_graph.py`.

**Interfaces — produces:**
- `BaseGraph.canvas_extent(channel) -> tuple[int, int]`. `canvas_width` and `canvas_height` stay, as the PATCH extent.
- `_check_canvas_size(channel=None)` measures only the nodes `channel.includes()`, and adds `channel.origin`. Add, remove, load and `NODE_STAGE_CHANGED` check every channel in `CHANNELS`. The changed-flag becomes a set of channel names.
- `ValidationResult.canvas_sizes: dict[str, tuple[int, int]]` replaces `canvas_size`. Only changed channels are present.
- `ChangeReason.NODE_STAGE_CHANGED`. The wrapper subscribes `props.on_stage` in `build()`, next to `_subscribe_props_redraw`, and marks the node dirty with it. Its priority sits at the redraw level. It is neither `requires_redraw()` nor `is_visual_only()`.
- `next_stage_spot(graph, count) -> list[tuple[float, float]]`, by R1, in `layout.py` or a new `core/graph/stage.py`. Pick one and say which in your report.
- `SetStageMembershipAction(graph, node_ids, on_stage, description=None)`: undoable, capturing each node's `on_stage`, `stage_x`, `stage_y` and `stage_size_adapt`. Adding places the nodes by R1. Removing changes only `on_stage` (R2).
- `Editor.add_to_stage(node_ids) -> bool` and `Editor.remove_from_stage(node_ids) -> bool`. Each skips nodes that are already in the target state, and returns False when nothing changes.

- [ ] **Step 1: Tests.**
  - `test_stage_extent_measures_only_on_stage_nodes_plus_the_origin`: an off-stage node at stage `(9000, 9000)` does not grow the stage extent. An on-stage node at stage `(4500, 0)` grows the width.
  - `test_patch_extent_is_unchanged_by_stage_moves`: `move_node(id, 9000, 9000, STAGE)` leaves `canvas_width` as it was.
  - `test_validation_result_carries_extents_per_channel`.
  - `test_on_stage_write_raises_node_stage_changed`: through `editor.set_property(id, "on_stage", True)` and through `props.on_stage = True`. The graph is marked unsaved, and no reassembly is requested.
  - `test_add_to_stage_places_by_the_margin_rule`: an empty stage puts the first node at `(40, 40)`. A second call puts the next node 40 below the first one's `stage_y + stage_height`. Several nodes stack in patch order.
  - `test_add_and_remove_are_one_undo_step_each`: undo restores `on_stage` and the stage rect, and redo re-applies them.
  - `test_remove_from_stage_keeps_the_stage_rect`.
- [ ] **Step 2: Run.** Expect FAIL.
- [ ] **Step 3: Implement.** Before changing `ValidationResult`, grep every `canvas_size` reader and constructor, and update them all.
- [ ] **Step 4: Run** `uv run pytest tests/core/ tests/graph_editor/ tests/ui/ -n 4 -q`. Expect PASS.
- [ ] **Step 5: Commit** `feat(graph): canvas extents per channel, the stage-change reason, Add/Remove from Stage`.

### Task 3: The stage face

**Files:**
- Modify:
  - `packages/haywire-core/src/haywire/ui/skin/base.py`
  - `packages/haywire-core/src/haywire/ui/skin/factory.py`
  - `barn/haybale-graph-editor/haybale_graph_editor/editors/graph_canvas/ui_node.py`
- Test: create `tests/ui/skin/test_stage_face.py`.

**Interfaces — produces:**
- `BaseSkin.render_stage(main_card: ui.card, wrapper: NodeWrapper) -> None`: the default face by R3. It is overridable.
- `BaseSkin._render_stage(wrapper) -> UINodeCard`, which mirrors `_render` and registers widgets the same way.
- `SkinFactory.render(key, wrapper, *, stage: bool = False, _is_error_render=False)`. With `stage=True` it calls `_render_stage`, and it keeps the same error-skin fallback.
- `UINode._render` passes `stage=self.channel.stage`.

- [ ] **Step 1: Tests.**
  - `test_default_face_draws_shown_widgets_and_on_stage_pins_only`: a node with an inlet widget (NOT_LINKED, unlinked), an outlet without a widget, an EXEC pin and an ANNOTATION swinglet. The face holds the inlet widget and one pin (the annotation one). It has no lane grid and no EXEC pin.
  - `test_a_skin_that_overrides_only_render_gets_the_default_face`: `StackedNodeSkin`.
  - `test_stage_widgets_are_registered_so_write_gates_apply`: the stage card's `widget_instances` holds the widget.
  - `test_the_face_has_no_frame`: the card has `hw-stage-face` and `node-card`, and no theme background.
- [ ] **Step 2: Run.** Expect FAIL.
- [ ] **Step 3: Implement.** Reuse `render_widget`, `render_pin` and `resolve_layout_direction`. Take a pin's side and its `data-pin-dir-x/y` from one `LayoutDirection` (see `.insights/project_layout_direction_pin_contract.md`). Seat the pins in a `position: relative` container.
- [ ] **Step 4: Run** `uv run pytest tests/ui/ -n 4 -q`. Expect PASS.
- [ ] **Step 5: Commit** `feat(skin): render_stage draws a node's stage face`.

### Task 4: The stage canvas

**Files:**
- Modify:
  - `barn/haybale-graph-editor/haybale_graph_editor/editors/graph_canvas/handlers/visual_layer.py`
  - `barn/haybale-graph-editor/haybale_graph_editor/editors/graph_canvas/handlers/interaction.py`
  - `barn/haybale-graph-editor/haybale_graph_editor/editors/graph_canvas/graph_canvas_manager.py`
  - `packages/haywire-core/src/haywire/ui/components/graph/canvas.vue` and its Python element (`canvas.py`): the `originX`/`originY` props.
- Test:
  - `tests/ui/test_canvas_handlers/test_stage_visual_layer.py` (new);
  - a browser test under `tests/ui/harness/` for the origin marker and the clamp.

**Interfaces:**
- Consumes `STAGE`, `includes`, `to_canvas`/`from_canvas` (Task 1); `canvas_sizes` and `NODE_STAGE_CHANGED` (Task 2); `render_stage` via `UINode` (Task 3).
- Produces: `GraphCanvasManager(..., channel=STAGE)` is a working stage view. `VisualLayerHandlers.included_node_count() -> int` and `included_edge_count() -> int` are for `_build_canvas` (Task 6).

- [ ] **Step 1: Tests.** Use `channel=STAGE` unless a test says otherwise.
  - `test_only_on_stage_nodes_mount`, covering both `sync_with_graph` and the chunked sync.
  - `test_only_on_stage_edges_between_mounted_nodes_register`, covering `on_validated`, `resync_edges` and `add_edge_visual`. Check the edge count `_await_client_drawn` waits for.
  - `test_stage_change_mounts_and_unmounts`: `NODE_STAGE_CHANGED` to True mounts the node and its eligible edges. To False, it unmounts the node and drops its edges. A patch canvas ignores the reason.
  - `test_positions_are_translated_by_the_origin`:
    - a node at stage `(0, 0)` mounts at canvas `(200, 200)`;
    - a drag update to canvas `(260, 300)` calls `move_nodes_to({id: (60.0, 100.0)}, STAGE)`;
    - `resync_positions` sends `(260, 300)` back.
  - `test_each_canvas_applies_only_its_own_extent`.
  - `test_the_patch_canvas_is_unchanged`: the existing PATCH tests pass.
  - Browser:
    - a stage canvas with origin 200 shows the corner-bracket marker at canvas `(200, 200)`;
    - a patch canvas (origin 0) shows no marker;
    - dragging a stage node up and left stops with its top-left corner at the origin.
- [ ] **Step 2: Run.** Expect FAIL.
- [ ] **Step 3: Implement.**
  - Put the node filter at `add_node_visual`'s callers, and the edge filter in `_register_edge_visual`, per R5.
  - Pass the canvas origin to the Vue element.
  - Afterwards, grep `visual_layer.py` for `graph.node_wrappers` and `graph.edge_wrappers`. Each hit is filtered or commented with why it needn't be.
- [ ] **Step 4: Run** `uv run pytest tests/ui/ tests/graph_editor/ -n 4 -q`, then `uv run pytest -m browser -n 4 -q`. Expect PASS.
- [ ] **Step 5: Commit** `feat(graph-editor): a stage canvas shows the on-stage nodes at their stage rect`.

### Task 5: Arrange only — stage gating and the stage menus

**Files:**
- Modify:
  - `barn/haybale-graph-editor/haybale_graph_editor/editors/graph_canvas/event_handlers.py`: `handles_event`
  - `graph_canvas_manager.py`: `_handle_canvas_event`
  - `handlers/context_menu.py` and `handlers/selection_toolbar.py`: pick the surface by view
  - `barn/haybale-graph-editor/haybale_graph_editor/surfaces/selection.py`: a `StageSelectionMenu` surface, and `SelectionActions` gains `add_to_stage`/`remove_from_stage`
  - `barn/haybale-graph-editor/haybale_graph_editor/panels/graph/menu/selection/`: an Add to Stage row and a Remove from Stage row in `SelectionMenu`, and the stage rows in a new module
  - every `@handles_event` site that needs `stage=True`
- Test: `tests/graph_editor/test_stage_gating.py` (new).

**Interfaces:**
- Consumes `Editor.add_to_stage`/`remove_from_stage` (Task 2), and the `STAGE` canvas (Task 4).
- Produces:
  - `handles_event(*events, access=AccessTier.EDIT, stage: bool | None = None)`. `None` resolves to True for `access` VIEW or OPERATE, and to False for EDIT or ADMIN. `stage_allowed(handler) -> bool` reads the resolved value.
  - In a stage canvas, `_handle_canvas_event` refuses a handler whose `stage_allowed` is False. It snaps back as a refused drag or resize does today.
  - `StageSelectionMenu`, with the rows Remove from Stage, Copy and Delete. In stage view, `ContextMenuHandlers` and the toolbar's ⋯ host it in place of `SelectionMenu`. The background (graph) context menu opens nothing in stage view.
  - In patch view, `SelectionMenu` shows Add to Stage when the selection holds an off-stage node, and Remove from Stage when it holds an on-stage one. Both need EDIT.

- [ ] **Step 1: Tests.**
  - `test_stage_flag_defaults_by_tier`.
  - `test_stage_canvas_runs_only_allowed_edit_handlers`. At EDIT, in stage view:
    - drag, resize, selection change, element removal (Delete) and Remove from Stage run;
    - paste, duplicate, node creation, edge creation and reconnect are refused, and a refused drag snaps back.
  - `test_patch_canvas_ignores_the_stage_flag`.
  - `test_stage_view_opens_the_stage_selection_menu_and_no_background_menu`.
  - `test_add_to_stage_row_shows_for_off_stage_nodes_in_patch_view`, and the matching Remove row.
  - `test_delete_in_stage_view_deletes_the_node`: the node is gone from the graph, and undo brings it back (Decision 7).
- [ ] **Step 2: Run.** Expect FAIL.
- [ ] **Step 3: Implement.** Mark the stage gestures `stage=True`: drag update, resize end, selection change, element removal, Remove from Stage, and the size-measurement and mount events if any of them are EDIT. Leave everything else at the default. List every EDIT handler and its stage flag in your report.
- [ ] **Step 4: Run** `uv run pytest tests/graph_editor/ tests/ui/ -n 4 -q`. Expect PASS.
- [ ] **Step 5: Commit** `feat(graph-editor): stage view only arranges; Add to Stage and Remove from Stage`.

### Task 6: Two views per level — the switch, `ToggleStageView`, `open_view`

**Files:**
- Modify:
  - `barn/haybale-graph-editor/haybale_graph_editor/editors/graph_editor.py`: `_Level`, `_new_level`, `_mount_level`, `_build_canvas`, `_teardown_canvas`/`_teardown_level`, `_repoint_level`, `_switch_level`, `_claim_session_state`, `accepts_command`, the header, and the lock-button update;
  - `barn/haybale-graph-editor/haybale_graph_editor/state/edit_state.py`, if the active view must be mirrored there like `active_locked`;
  - `packages/haywire-core/src/haywire/core/signals/vocabulary.py`, `__all__`, and `core/signals/__init__.py`.
- Test:
  - `tests/graph_editor/test_graph_editor_views.py` (new);
  - a browser test under `tests/ui/harness/`.

**Interfaces:**
- Consumes everything above.
- Produces:
  - `_Level.view: str` (`"patch"` | `"stage"`) and `_Level.canvases: dict[str, GraphCanvasManager]`. `_Level.canvas_manager` becomes a read-only property returning `canvases.get(view)`, so its 30 existing call sites keep working. Audit each one: does it mean the visible canvas, or every canvas?
  - `GraphEditor._switch_view(context, level_key, view) -> None`. It:
    - mounts the view's canvas if absent, into the level's inner keep-alive panels;
    - selects that panel and clears the selection;
    - pushes the lock to the canvas;
    - claims the session for the editor;
    - refreshes the header switch.
  - `ToggleStageView`, as in Global Constraints, handled by `@react_on(ToggleStageView)` on the active level.
  - `_new_level` reads `open_view` alongside `open_locked`. An `open_view="stage"` level mounts the stage canvas first, and the patch canvas only on the first switch.
  - In stage view, `accepts_command` refuses an EDIT-tier command unless it is in `_STAGE_COMMANDS = {Delete, Copy, SelectAll, Undo, Redo, Save, ToggleLock, ToggleStageView}`. Check the exact class names in `vocabulary.py`.

- [ ] **Step 1: Tests.**
  - `test_first_switch_mounts_the_stage_and_later_switches_reuse_both`: after Patch → Stage → Patch, both canvases exist and the patch's `UINode` objects are the same instances.
  - `test_switch_clears_the_selection`.
  - `test_lock_applies_to_both_canvases`: lock in patch view, switch, and the stage canvas is locked too.
  - `test_toggle_stage_view_works_at_view_tier_and_on_a_locked_level`.
  - `test_open_view_stage_opens_on_the_stage_and_mounts_the_patch_lazily`.
  - `test_stage_view_refuses_paste_and_allows_delete_and_undo`, through `accepts_command`.
  - `test_teardown_and_repoint_handle_both_canvases`: both are cleaned up. A re-pointed level keeps its view and both viewports.
  - `test_pointer_gesture_on_the_stage_canvas_claims_the_session`, against slice 2's `POINTER_GESTURE_EVENTS` path.
  - Browser:
    - put two connected annotation nodes on stage, and switch Patch → Stage → Patch → Stage;
    - each time, every drawn edge's path starts and ends within 4 px of its own view's pins (`.scratch/edgecheck.js` shows how to measure);
    - after switching back, the patch cards are the same DOM elements (stamp one with a marker attribute before the switch).
- [ ] **Step 2: Run.** Expect FAIL.
- [ ] **Step 3: Implement.** Follow the design guide for the header switch (`docs/reference/design-guide.md`). Check that `Mod+Alt+E` is not in `RESERVED_COMBOS`.
- [ ] **Step 4: Run** `uv run pytest tests/graph_editor/ tests/ui/ -n 4 -q`, then `uv run pytest -m browser -n 4 -q`. Expect PASS.
- [ ] **Step 5: Commit** `feat(graph-editor): a level shows its patch or its stage, switched in the header`.

### Task 7: Docs

**Files:**
- Create `docs/adr/0054-the-stage-view.md`, matching `docs/adr/0053-position-lives-in-props.md`. It records:
  - the stage as a second layout channel, with membership, origin and stage face;
  - stage coordinates relative to a fixed origin;
  - extents per channel;
  - two keep-alive views per level, and why: no re-render on switch, and detached DOM keeps pin uuids unique;
  - the arrange-only allow-list, with Delete not remapped;
  - `on_stage` and `NODE_STAGE_CHANGED`;
  - on-stage wires as a `WireType` class attribute.
- Modify:
  - `docs/reference/glossary.md`: patch view, stage view, stage, on stage, stage rect, stage origin, on-stage wire, open-in default. Update **Layout channel** for `STAGE`.
  - `docs/components/skins/skin-canon.md`: `render_stage` and the default face.
  - The wire docs page that lists `WireType` attributes: `on_stage`.
  - `docs/guides/security.md`: stage view's arrange-only rule next to the lock.
  - The spec, `docs/superpowers/plans/2026-10-12-editor-modes.md`:
    - under "Stage", replace "Delete on a node means Remove from Stage" with Decision 7;
    - under "Stage origin", replace "stage view greys the area left of and above it" with Decision 3 (the corner-bracket marker, and drags stopping at the origin);
    - record Q2c (two keep-alive views per level) under "Two switches per open level", and Q8a (the switch sits in the header);
    - mark the trap "`canvas_width`/`canvas_height` are the patch's" resolved by 5a;
    - list 5a–5d under Sequence item 5.
- Run:
  - `uv run haywire docs barn/haybale-graph-editor`, `uv run haywire docs barn/haybale-core` and `uv run haywire docs barn/haybale-studio`;
  - `uv run python scripts/bake_docs.py`;
  - `uv run mkdocs build --strict`.
- [ ] **Step 1: Edit the docs.**
- [ ] **Step 2: Commit first** (the docs test resets `barn/haybale-testing`). Then run the commands above and `uv run pytest tests/ -k "bake or docs" -n 4 -q`. Expect PASS.
- [ ] **Step 3: Commit** `docs: the stage view (ADR 0054)`.

### Task 8: Full gate

- [ ] **Step 1:** `uv run ruff check . && uv run ruff format --check .`
- [ ] **Step 2:** the mypy command from CLAUDE.md.
- [ ] **Step 3:** `uv run pytest -m "not browser and not perf" -n 4 -q > <scratch>/t.log 2>&1; echo "exit=$?"`. Expect `exit=0`.
- [ ] **Step 4:** `uv run pytest -m browser -n 4 -q`. Expect PASS.
- [ ] **Step 5:** Round-trip every tracked `.haywire`/`.hwm` file (load, then `to_dict`). Every node stays off stage, and its patch position is unchanged.
