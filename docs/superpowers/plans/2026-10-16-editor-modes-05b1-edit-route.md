# Editor modes, slice 5b-1: the edit route — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Every user edit of a value, a setting or a bypassed structure verb reaches `Editor` through one per-session, per-level `EditRoute`, which refuses edits below the level mode and marks unsaved the document that saves the value; the write-gate classes are deleted.

**Architecture:**
- **Core** gains `LevelMode`, value actions and verbs on `Editor`, and `EditRoute`.
- **Widgets** write through their model. `WidgetFactory` builds that model over the route the host hands it, and a skin passes its card's route on.
- **The graph editor** builds one route per level and session, and hands it to the canvas, the card widgets, the Ports panel and the Properties forms.
- **Value undo stays off in this slice.** The route's value writes are `record=False`; 5b-2 turns recording on.

**Tech Stack:** Python 3.12, NiceGUI/Vue 3, pytest (`uv run pytest`), ruff, mypy.

**Spec:** [2026-10-16-edit-route.md](2026-10-16-edit-route.md), sequence item 1 ("5b-1, the edit route"), plus decisions Q21–Q23.

## Global Constraints

- **Branch:** work on `feat/editor-modes-slice5b1` in worktree `.worktrees/editor-modes-slice5b1`, cut from `feat/editor-modes-slice1`. It merges into `feat/editor-modes-slice1` after the live check; nothing goes to master.
- **Breaking changes are allowed.** Remove replaced APIs in this slice; no compatibility shims survive Task 9.
- **Level mode:** `view < operate < edit`. Wire values `"view"`, `"operate"`, `"edit"`. In 5b-1 it is derived from today's rule: `edit` when `allows(can_access, locked, EDIT)`, `operate` when it allows `OPERATE`, else `view`.
- **Every route write names its `minimum: LevelMode` explicitly.** Card and stage widgets pass `OPERATE`; the Ports panel and Properties forms pass `EDIT`.
- **Value writes are not recorded in 5b-1** (`record=False`). An unrecorded write adds an undo fence afterwards.
- **Unsaved rule:** a write marks unsaved only when what the field stores changed (`(is_locally_set, value)` for a setting, the own value for a port).
  - A node bag or port write calls `NodeWrapper.mark_value_edited()`.
  - A graph or edge bag write calls `graph._validation.mark_graph_dirty(ChangeReason.GRAPH_CONTENT_CHANGED)`.
  - A placement interior stays unmarked through the existing `GraphNode._forwards_content_changes`.
- **A bag no document saves** (`setting_owner(...)` returns `None`, e.g. a multi-selection's neutral form) is written directly after the mode check, and marks nothing.
- **Docs rules:** follow `.claude/rules/python-docs.md`. Glossary and ADR edits land in Task 9, with the code, none earlier (memory `feedback_glossary_adr_after_landing`).
- **Pre-edit baseline** (CLAUDE.md), before Task 1: `uv run ruff check packages/haywire-core/src barn/haybale-graph-editor barn/haybale-haystack` and the CLAUDE.md mypy command. It must be clean; if not, stop and ask.
- **Tests:** run the smallest tier while iterating (`uv run pytest <file>`). Commit before any full-suite run, because `tests/studio/test_docs/test_generate.py` reverts uncommitted edits under `barn/haybale-testing`. Use `-n 4`.
- **Commit trailer:** end every commit message with `Co-Authored-By: Claude Opus 5.5 (1M context) <noreply@anthropic.com>`.

## Decisions this plan adds to the spec

1. **`minimum` instead of `operable=`.** The host states its surface's minimum. 5b-4's `operable=False` will raise it to `EDIT`.
2. **The routed model is the existing `SettingWidgetModel`** (cell for reads, a write callable). Its write now returns `bool`, and no new class is added. The spec's sketch called it `RoutedModel`.
3. **`render_settings(..., route=...)` is a required keyword.** `route=None` means a bag outside any graph document, written directly (haystack's run settings). Every caller has to decide.
4. **Farmhand edit-tier tools keep calling `Editor` verbs**, so they are recorded as today. Only `graph_editor_operate` writes through a route (`OPERATE`).
5. **Undoing a setting write restores *unset*** when the field had no local value. This is part of the new action's correctness, so it lands here rather than in 5b-2.
6. **The route reads its `Editor` through a callable, like its mode.**
   `GraphEditor._ensure_document_level` swaps a level's container in place
   ([graph_editor.py:276-278](../../../barn/haybale-graph-editor/haybale_graph_editor/editors/graph_editor.py#L276-L278)),
   so a route holding a fixed `Editor` would go stale. The spec's sketch passed
   the editor itself.

## Review Focus

1. **A promoted setting's widget on a card.** The write lands through its setting, so it saves and Reset enables, not raw into the shared cell. Test: Task 4, `test_a_promoted_port_widget_writes_its_setting`.
2. **Two sessions on one graph, one of them locked.** Each route reads its own level's lock. Test: Task 5, `test_each_session_reads_its_own_lock`.
3. **A Ports-panel row drawn before the level locks.** Its next write is refused and the view snaps back. Test: Task 5, `test_a_ports_panel_row_drawn_before_the_lock_refuses`.
4. **A placement's interior value edit.** The value changes and the host graph stays saved and unreassembled. Test: Task 6, `test_an_interior_value_is_still_live` (rewritten).
5. **A settings value the field's validator rejects.** The row shows the error, and nothing is written or marked. Test: Task 6, `test_a_rejected_value_shows_the_error_and_marks_nothing`.

---

### Task 1: `LevelMode` and the level-mode rule

**Files:**
- Create: `packages/haywire-core/src/haywire/core/access/level_mode.py`; export `LevelMode` from `haywire/core/access/__init__.py`
- Modify: `barn/haybale-graph-editor/haybale_graph_editor/access.py` (add `level_mode`)
- Test: `tests/core/test_access/test_level_mode.py` (new), `tests/graph_editor/test_access_rule.py`

**Interfaces:**
- Produces:
  - `LevelMode(StrEnum)`: `VIEW = "view"`, `OPERATE = "operate"`, `EDIT = "edit"`, with `rank: int` (0/1/2) and `satisfies(self, required: LevelMode) -> bool`. Same shape as `AccessTier`.
  - `level_mode(can_access: Callable[[AccessTier], bool], locked: bool) -> LevelMode` in the graph editor's `access.py`.

- [ ] **Step 0: Baseline.** Run the two commands from Global Constraints. Expect no errors.
- [ ] **Step 1: Write the tests.**
  - `test_level_mode.py`:
    - `test_wire_values`: `LevelMode.OPERATE == "operate"`.
    - `test_ranks_order`: `VIEW.rank < OPERATE.rank < EDIT.rank`.
    - `test_satisfies_matrix`, parametrized over all 9 pairs: true exactly when `mode.rank >= required.rank`.
  - `test_access_rule.py`: `test_level_mode_table`, parametrized as `(tier, locked) -> mode`:

    | tier | locked=False | locked=True |
    | --- | --- | --- |
    | VIEW | VIEW | VIEW |
    | OPERATE | OPERATE | OPERATE |
    | EDIT | EDIT | OPERATE |
    | ADMIN | EDIT | OPERATE |

    Use `tier.satisfies` as `can_access`, as the file's other tests do.
- [ ] **Step 2: Run** `uv run pytest tests/core/test_access/test_level_mode.py tests/graph_editor/test_access_rule.py`. Expect FAIL (import error).
- [ ] **Step 3: Implement.** `level_mode` asks `allows(...)` for `EDIT`, then for `OPERATE`.
- [ ] **Step 4: Run** the same command. Expect PASS.
- [ ] **Step 5: Commit** `feat(access): level mode, the per-level mode a session edits in`.

### Task 2: Value actions and `Editor` verbs

**Files:**
- Create: `packages/haywire-core/src/haywire/core/graph/setting_owner.py`
- Modify: `packages/haywire-core/src/haywire/core/undo/actions/graph_actions.py`:
  - add `value_changed`, `SetSettingAction`, `ResetSettingAction`, `ReorderPortsAction` and `SetEdgePropagationAction`;
  - change `SetPropertyAction` (:1080-1166) to mark only on change.
- Modify: `packages/haywire-core/src/haywire/core/graph/editor.py` (`set_property` gains `record`; new verbs)
- Modify: `packages/haywire-core/src/haywire/ui/widget/write_gate.py`: delete its `value_changed` body and import it from `graph_actions` (the module goes away in Task 9).
- Modify: the `SetPropertyAction` docstring. Drop "the one deliberate new core mutation surface mandated by the Farmhand spec": it is now the value action every port write takes, through the edit route or an edit-tier tool.
- Test: `tests/core/test_undo/test_value_actions.py` (new), `tests/core/test_undo/test_set_property_action.py`

**Interfaces:**
- Produces:
  - `value_changed(before: Any, after: Any) -> bool` in `haywire.core.undo.actions.graph_actions`, moved verbatim.
  - `SettingOwner`, a frozen dataclass: `kind: Literal["node", "graph", "edge"]`, `accessor: str`, `owner_id: str | None = None`.
    - `accessor` is the node's bag accessor, `"props"`/`"meta"`, or `"style"`.
    - `resolve(self, graph: BaseGraph) -> Settings | None`.
  - `setting_owner(graph: BaseGraph, bag: Settings) -> SettingOwner | None`. It matches by identity:
    - a node bag: `bag._node` is a node of `graph` and `bag_accessor(node, bag)` finds it;
    - `graph.props` / `graph.meta`;
    - an edge bag: `bag._edge` is an edge of `graph` whose `style is bag`.

    Anything else is `None`.
  - `SetSettingAction(graph, owner: SettingOwner, name: str, value: Any)` and `ResetSettingAction(graph, owner, name)`:
    - Execute records `(was_set, old)` = `(bag._is_locally_set(name), getattr(bag, name))`, then writes (`setattr` or `bag._reset(name)`).
    - It marks per Global Constraints only when that pair changed.
    - Undo: if `was_set`, `setattr(bag, name, old)`, else `bag._reset(name)`; marks the same way.
    - Raises `ValueError` when the owner does not resolve or the bag has no field `name`.
  - `ReorderPortsAction(graph, node_id: str, ordered_ids: list[str])`:
    - Execute records the previous order of those ids (sorted by `DataPort.order`), then calls `node.reorder_ports(ordered_ids)`.
    - Undo calls `node.reorder_ports(previous)`.
  - `SetEdgePropagationAction(graph, edge_id: str, propagation: Propagation)`:
    - Execute records the old `wrapper.propagation`, sets the new one and calls `wrapper.redraw()`.
    - Undo restores and redraws. A refusal from the setter's `ValueError` propagates.
  - On `Editor`:
    - `set_property(node_id, name, value, prefer_setting=False, *, record: bool = True) -> bool`;
    - `set_setting(owner: SettingOwner, name: str, value: Any, *, record: bool = True) -> bool`;
    - `reset_setting(owner: SettingOwner, name: str, *, record: bool = True) -> bool`;
    - `reorder_ports(node_id: str, ordered_ids: list[str]) -> bool`;
    - `set_edge_propagation(edge_id: str, propagation: Propagation) -> bool`.
    - All of them go through one private `_apply(action, record: bool) -> bool`:
      - `record=True`: `history_manager.add_action(action)`.
      - `record=False`: `action.execute()`, then `history_manager.add_fence()`, and `True`.
      - An exception is logged and gives `False`.

- [ ] **Step 1: Write the tests.** Use a held graph (`ThreadingTimerScheduler`, `validation_delay_ms=60_000`, as in `tests/graph_editor/test_write_gates.py::held_graph`) and drain it with `force_immediate_validation()`.
  - `test_value_actions.py`:
    - `test_owner_round_trips_for_node_graph_and_edge_bags`: `setting_owner(graph, bag).resolve(graph) is bag` for a node's `props`, `graph.props`, `graph.meta` and a styled edge's `style`. Copy `_styled_edge` from `tests/ui/panels/test_selection_forms.py`.
    - `test_a_bag_no_document_saves_has_no_owner`: a standalone `GraphProperties()` gives `None`.
    - `test_a_node_setting_write_marks_the_node`: `result.nodes == {node_id: NODE_VALUE_CHANGED}`.
    - `test_a_graph_props_write_marks_the_graph`: `result.graph is GRAPH_CONTENT_CHANGED` and `result.requires_save()`.
    - `test_a_meta_write_marks_the_graph`: same, for `graph.meta.label`.
    - `test_writing_what_is_stored_marks_nothing`: on a locally set field, the result is `None`.
    - `test_setting_an_unset_field_to_its_default_marks`: `_is_locally_set` flips, so it marks.
    - `test_undo_of_a_first_write_restores_unset`: after `editor.set_setting(...)` then `editor.undo()`, `bag._is_locally_set(name) is False`.
    - `test_undo_of_a_reset_restores_the_local_value`.
    - `test_an_unrecorded_write_adds_no_step_and_a_fence`: `record=False` writes; `editor.can_undo() is False`; `isinstance(editor.history_manager.history[-1], Fence)`.
    - `test_a_reorder_is_one_undo_step`: `reorder_ports` then `undo()` restores the original id order.
    - `test_a_propagation_change_is_one_undo_step`: `set_edge_propagation(eid, Propagation.LAZY)` then `undo()` gives `EAGER` again.
  - `test_set_property_action.py`: add `test_setting_the_current_value_marks_nothing` (port and setting), and `test_record_false_leaves_no_undo_step`.
- [ ] **Step 2: Run** both files. Expect FAIL.
- [ ] **Step 3: Implement** as listed under Interfaces. `setting_owner` lives in core; `bag_accessor` is in `haywire.core.node.promotion`.
- [ ] **Step 4: Run** both files, then `uv run pytest tests/core/test_undo/ tests/farmhand/ -n 4`. Expect PASS. Farmhand's `set_property` now marks only on change.
- [ ] **Step 5: Commit** `feat(undo): setting, port-order and propagation actions; value writes mark only on change`.

### Task 3: `EditRoute`

**Files:**
- Create: `packages/haywire-core/src/haywire/core/graph/edit_route.py`
- Test: `tests/core/test_graph/test_edit_route.py` (new)

**Interfaces:**
- Consumes: `LevelMode` (Task 1); `Editor.set_property/set_setting/reset_setting`, `setting_owner` (Task 2).
- Produces: `EditRoute(editor: Callable[[], Editor], mode: Callable[[], LevelMode])`, where both callables are read at each call, with:
  - `graph` (property) → `BaseGraph`, the current editor's graph;
  - `mode() -> LevelMode`;
  - `allows(minimum: LevelMode) -> bool`;
  - `editor() -> Editor | None`: the editor only when the mode is `EDIT`;
  - `set_port(node_id: str, port_id: str, value: Any, *, minimum: LevelMode) -> bool`: `editor.set_property(..., record=False)`;
  - `set_setting(bag: Settings, name: str, value: Any, *, minimum: LevelMode) -> bool`;
  - `reset_setting(bag: Settings, name: str, *, minimum: LevelMode) -> bool`.
  - Every write returns `False` and changes nothing when `allows(minimum)` is false.
  - A bag with no owner is written directly and returns `True`.
  - The mode is read at each call. The class docstring carries the Sketch example from the spec.

- [ ] **Step 1: Write the tests** in `test_edit_route.py`, with a real `Editor` over a held graph and a node from `haybale_testing`'s `TestAddFloatNode`. Build the route as `EditRoute(lambda: editor, lambda: mode)` with a mutable `mode`.
  - `test_the_editor_is_read_at_each_call`: swap the object the first callable returns; the next write lands on the new editor's graph.
  - `test_the_editor_is_handed_out_only_in_edit`: parametrized over the three modes.
  - `test_a_write_below_its_minimum_changes_nothing`: `OPERATE` mode, `set_setting(..., minimum=EDIT)` is `False`, and the value is unchanged.
  - `test_set_port_writes_marks_and_records_nothing`: value set, `NODE_VALUE_CHANGED`, `editor.can_undo() is False`.
  - `test_the_mode_is_read_at_each_write`: flip `mode` between two calls; the second call is refused.
  - `test_a_bag_no_document_saves_is_written_directly`.
  - `test_a_port_without_an_own_value_is_refused`: an `ADD` slot gives `False`. Find a node with one through `tests/conftest.py`'s `make_node` users of `ADD[`.
- [ ] **Step 2: Run.** Expect FAIL.
- [ ] **Step 3: Implement.**
- [ ] **Step 4: Run.** Expect PASS.
- [ ] **Step 5: Commit** `feat(graph): EditRoute, the one way a user edit reaches the Editor`.

### Task 4: Widgets write through their model; the factory and skins carry the route

**Files:**
- Modify: `packages/haywire-core/src/haywire/ui/panel/setting_widget_model.py`: `on_edit: Callable[[Any], bool | None]`; `set_value` returns `bool`, which is `False` only when `on_edit` returned `False`.
- Modify: `packages/haywire-core/src/haywire/core/types/widget_model.py`: the protocol's `set_value` returns `bool | None`, with `False` meaning refused. Document that in the docstring.
- Modify: `packages/haywire-core/src/haywire/ui/widget/base.py:74-87`: `set_value` shows the model again when `accepts_write()` is false or the model returns `False`. The `write_gate` check stays until Task 9.
- Modify: `packages/haywire-core/src/haywire/ui/widget/binding.py:159-259`:
  - `_sync_to_model` calls `sync_to_view()` when the model returns `False`.
  - A nested `source_property` builds `copy.deepcopy` of the container, sets the path on the copy and calls `self._element.set_value(copy)`. `_update_nested_property` is deleted.
- Modify: `packages/haywire-core/src/haywire/barn/builtin/widgets/optional_widget.py:40-48`: `_ElementModel.set_value` returns the outer model's result.
- Modify: `packages/haywire-core/src/haywire/ui/widget/factory.py`:
  - `render_widget(registry_key, port, node_id, *, route: EditRoute | None = None, minimum: LevelMode = LevelMode.EDIT)`.
  - `_widget_model_for(port, route, minimum)`:
    - A model that is not a `DataPort` is returned as given (the port dialog's `PortDefaultWidgetModel`).
    - A `DataPort` gets a `SettingWidgetModel(port.id, port.widget_config, port.data, write)`:
      - `write` is `route.set_setting(bag, descriptor._attr_name, v, minimum=minimum)` for a promoted port, using `_resolve_promoted`;
      - otherwise `route.set_port(port._node.node_id, port.id, v, minimum=minimum)`;
      - with no route, it writes as today: the port's `set_value`, or `setattr` on the setting of a promoted port. Task 5 makes this read-only once every host passes a route, so this commit changes no behaviour.
- Modify: `packages/haywire-core/src/haywire/ui/widget/factory_interface.py`: same signature.
- Modify: `packages/haywire-core/src/haywire/ui/skin/base.py:59-149`:
  - `_render(wrapper, *, on_stage=False, route: EditRoute | None = None)` holds the route per node id for the render, beside `_nodeids_widget_instances`, and clears it after.
  - `render_widget` passes `route=` that node's route and `minimum=LevelMode.OPERATE`.
- Modify: `packages/haywire-core/src/haywire/ui/skin/factory.py:74`: `render(..., route: EditRoute | None = None)` forwards it, including on the error-skin path.
- Test: `tests/ui/widget/test_routed_widgets.py` (new)

**Interfaces:**
- Consumes: `EditRoute`, `LevelMode` (Tasks 1, 3).
- Produces:
  - `WidgetFactory.render_widget(..., *, route, minimum)`;
  - `SkinFactory.render(..., route=)`;
  - `BaseSkin._render(..., route=)`;
  - `SettingWidgetModel.set_value(...) -> bool`.
- Note for test fixes: a widget's `self.port` is now the routed model, not the `DataPort`. Compare `widget.port.data is port.data`, not `widget.port is port`.

- [ ] **Step 1: Write the tests** in `test_routed_widgets.py`. Get the factories from `library_system.injector`.
  - `test_a_port_widget_writes_through_its_route`: a real `EditRoute` in `EDIT` mode; the value is set and the node marked.
  - `test_a_route_below_the_minimum_refuses_and_snaps_back`: route `VIEW`, minimum `OPERATE`.
  - `test_a_promoted_port_widget_writes_its_setting`: use the `make_node_with_setting` fixture; after the write, `bag._is_locally_set(name)` is true. This is a Review Focus item.
  - `test_a_model_the_host_built_is_used_as_given`: a `PortDefaultWidgetModel` is the widget's `port`.
  - `test_a_nested_binding_writes_a_new_value_through_the_model`: a stub model whose `set_value` records. `bind(to="x")` sends a new instance with `x` changed, and the original instance is untouched.
  - `test_an_optional_inner_edit_goes_through_the_outer_model`: an outer model returning `False` leaves the inner widget showing the model.
  - `test_a_skin_hands_its_card_widgets_the_route`: `SkinFactory.render(key, wrapper, route=stub)`, then a card widget's `set_value` calls `stub.set_port(..., minimum=LevelMode.OPERATE)`.
- [ ] **Step 2: Run.** Expect FAIL.
- [ ] **Step 3: Implement** as listed under Files.
- [ ] **Step 4: Run** `uv run pytest tests/ui/widget/ tests/ui/skin/ tests/ui/panel/ -n 4`. Expect PASS; fix `widget.port is port` assertions as noted.
- [ ] **Step 5: Commit** `feat(ui): widgets write through a model the host routes; skins pass the card's route`.

### Task 5: Levels own routes; the canvas, cards and Ports panel use them

**Files:**
- Modify: `barn/haybale-graph-editor/haybale_graph_editor/editors/graph_editor.py`:
  - `_Level` (:146-173) gains `route: EditRoute = field(init=False, repr=False)`.
  - `_new_level` (:314-330) becomes an instance method `_new_level(self, context, key, container)`. It sets `level.route = EditRoute(lambda: level.container.editor, lambda: level_mode(context.can_access, level.locked))`, so the route follows `_ensure_document_level`'s in-place container swap.
    - Production callers: :276 (`_ensure_document_level`), :306 (`_open_level`), :537 (`_repoint_level`), and the example in `protocols.py:97`.
    - Test callers: `tests/graph_editor/test_graph_editor_placement_levels.py:65,74,84`, `tests/graph_editor/test_graph_editor_views.py:76,454` and `tests/ui/harness/routes.py:1496`.
  - `_build_canvas` (:1119) takes `route: EditRoute` instead of `entry`, and `_mount_view` passes `level.route`.
    - Test callers: `test_graph_editor_views.py:471,490`, `test_graph_editor_session_claim.py:276` and `test_graph_editor_placement_levels.py:520`.
  - `_claim_session_state` (:929-962) compares and sets `edit_state.active_route`.
- Modify: `barn/haybale-graph-editor/haybale_graph_editor/state/edit_state.py`: `active_route: Optional["EditRoute"] = signal_field(None)`.
- Modify: `barn/haybale-graph-editor/haybale_graph_editor/state/graph_app_state.py:91`: `editor_for` is replaced by `route_for(context) -> EditRoute | None`, which returns `EditState.active_route`. `_host_history` goes if unused.
- Modify: `editors/graph_canvas/graph_canvas_manager.py:124-190`: `GraphCanvasManager(route: EditRoute, ...)` replaces `editor`; `self.graph = route.graph`. Its handlers are built with `route`.
- Modify: `editors/graph_canvas/handlers/interaction.py`, `selection.py` and `visual_layer.py`:
  - Each takes `route` instead of `editor`.
  - A verb call becomes `editor = self.route.editor()`, with `if editor is None: return` (or the handler's own refusal value).
  - Graph reads use `self.graph` / `self.route.graph`, never the editor. The `EnterGroupEvent` handler (view tier) must not need an editor.
  - `VisualLayerHandlers` drops `allows`, and passes `self.route` to `UINode`.
- Modify: `editors/graph_canvas/ui_node.py`: `UINode(container, wrapper, factory, route: EditRoute, channel=PATCH)` replaces `allows`. `factory.render(..., route=self._route)`. `_apply_write_gates` is deleted.
- Modify: `packages/haywire-core/src/haywire/ui/widget/factory.py`: a `DataPort` widget rendered with no route, or whose port has no `_node`, is now read-only (`lambda _v: False`). Every host passes a route from this task on.
- Modify: `panels/properties/introspect/node_ports.py`:
  - widgets: `render_widget(..., route=route_for(context), minimum=LevelMode.EDIT)`, drawn enabled when `route is not None and route.allows(LevelMode.EDIT)`. The `write_gate` assignment is deleted.
  - port pen (:197-212): `editor = route.editor()`.
- Modify: `editors/graph_canvas/handlers/context_menu.py:775-781` and `barn/haybale-haystack/haybale_haystack/panels/graph/menu/macro.py:209-214`: `route_for(...)`, then `.editor()`. In macro.py this also replaces the `session_allows(ctx)(AccessTier.EDIT)` check: the refusal "Updating a macro needs edit access" shows when there is no editor.
- Modify: `barn/haybale-haystack/haybale_haystack/editors/haystack_editor.py:508-510`: also clear `active_route`.
- Test: `tests/graph_editor/test_graph_editor_lock.py`, `tests/graph_editor/test_level_routes.py` (new), and the handler tests that set or pass `editor`.
  - Those handler tests are: `tests/ui/test_canvas_handlers/` (`test_interaction_handlers.py`, `test_resize_commit.py`, `test_selection_handlers.py`, `test_visual_layer_auto_wire.py`, `test_stage_visual_layer.py`) and `tests/graph_editor/` (`test_stage_creation.py`, `test_locked_node_delete_skip.py`, `test_stage_parity.py`).
  - Add `edit_route(editor, mode=LevelMode.EDIT) -> EditRoute` to `tests/conftest.py` for them (`EditRoute(lambda: editor, lambda: mode)`).

**Interfaces:**
- Consumes: `EditRoute` (Task 3), `level_mode` (Task 1), `render_widget(..., route, minimum)` and `SkinFactory.render(..., route)` (Task 4).
- Produces:
  - `_Level.route`;
  - `EditState.active_route`;
  - `route_for(context: SessionContext) -> EditRoute | None` in `haybale_graph_editor.state.graph_app_state`;
  - `GraphCanvasManager(route=...)`;
  - `UINode(..., route, ...)`.

- [ ] **Step 1: Write the tests.**
  - In `test_graph_editor_lock.py`, using `_locked_editor`, add `active_route=None` to its `EditState` stand-in:
    - `test_a_level_route_follows_the_lock`: an `EDIT` principal's document route is `EDIT`; after `set_level_locked(..., True)` it is `OPERATE` and `route.editor() is None`.
    - `test_each_session_reads_its_own_lock`: two `GraphEditor`s over one document, only one locked; their document routes report `OPERATE` and `EDIT`. This is a Review Focus item.
    - `test_claiming_publishes_the_active_route`: after the claim, `EditState.active_route is editor._levels[DOCUMENT_LEVEL].route`.
  - In `tests/ui/widget/test_routed_widgets.py`: `test_a_port_widget_without_a_route_is_read_only`: the own value is unchanged after `set_value`, and the view shows the model.
  - In `test_level_routes.py`, with a held graph and a real `UINode`:
    - `test_a_card_widget_writes_for_operate_and_refuses_view`: replaces `test_card_widgets_get_an_operate_gate` and `test_a_rendered_card_refuses_a_view_principals_write`, with the same assertions, built with routes.
    - `test_a_ports_panel_widget_needs_edit`: a locked `ADMIN` route refuses; an `EDIT` route writes and marks `NODE_VALUE_CHANGED`.
    - `test_a_ports_panel_row_drawn_before_the_lock_refuses`: render with an `EDIT` route, flip its mode to `OPERATE`, write; the value is unchanged and the view shows the model. This is a Review Focus item.
    - `test_structure_handlers_do_nothing_without_an_editor`: `InteractionHandlers(edit_route(editor, LevelMode.VIEW)).process_drag_update(...)` moves no node.
- [ ] **Step 2: Run** `uv run pytest tests/graph_editor/test_graph_editor_lock.py tests/graph_editor/test_level_routes.py`. Expect FAIL.
- [ ] **Step 3: Implement** as listed under Files. Then update the handler tests to build handlers with `edit_route(editor)`.
- [ ] **Step 4: Run** `uv run pytest tests/graph_editor/ tests/ui/test_canvas_handlers/ tests/haystack/ -n 4`, then `uv run pytest -m browser -n 4 -k "graph or canvas or node"`. Expect PASS.
- [ ] **Step 5: Commit** `feat(graph-editor): each level's route reaches the canvas, its cards and the Ports panel`.

### Task 6: Settings rows write through the route

**Files:**
- Modify: `packages/haywire-core/src/haywire/ui/panel/render_utils.py`:
  - `render_settings(ctx, obj, *, categories=None, route: EditRoute | None)`: `route` is required, and `editor` and `gate` are removed. Its docstring states what `route=None` means.
  - `_render_reactive_field_row` (:566-910):
    - A row is editable when its UI state is `NORMAL` and `route is None or route.allows(LevelMode.EDIT)`.
    - Edit, Reset and Set to none write through `route.set_setting` / `route.reset_setting` with `minimum=LevelMode.EDIT`, or directly when `route is None`. A refusal shows the model again.
    - Promote and Demote call `route.editor()` and do nothing when it is `None`; their entries grey then. They are offered only when `route is not None` and the bag has a node. The direct `promote_setting` / `demote_setting` fallbacks are deleted.
  - `_bag_on_edit(obj, attr_name, error_container, route, on_refused)`: validate, then write through the route; error chrome as today. `_written_if_changed` is deleted.
- Modify: `barn/haybale-graph-editor/haybale_graph_editor/panels/_selection_forms.py`:
  - Forms render with `route=route_for(ctx)`.
  - `fan_out_to(neutral, bags, route)` writes each real bag through `route.set_setting` / `route.reset_setting` (`minimum=LevelMode.EDIT`).
  - `_EachNodeWriteGate` and `_form_gate` are deleted.
- Modify: the `render_settings` callers:
  - `panels/properties/introspect/node.py:91-92`, `panels/properties/setting/node.py:73-79`, `panels/properties/setting/graph.py:51`, `panels/properties/setting/metadata.py:60` and `panels/properties/introspect/edge.py:130` pass `route=route_for(ctx)`;
  - `barn/haybale-haystack/haybale_haystack/panels/properties/introspect/graph_run_settings_panel.py:61` passes `route=None`.
- Modify: `barn/haybale-graph-editor/haybale_graph_editor/access.py`: delete `NodeWriteGate`, `GraphWriteGate` and `session_allows`; update the module docstring. `allows`, `can_edit_graph` and `level_mode` stay.
- Test: `tests/ui/panel/test_render_settings_route.py` (new; replaces `test_render_settings_gate.py`, which is deleted), `tests/ui/panels/test_selection_forms.py`, `tests/core/test_macro/test_macro_node.py:274-300`, the other `render_settings(` callers in tests (add `route=None`).

**Interfaces:**
- Consumes: `EditRoute`, `route_for` (Tasks 3, 5).
- Produces: `render_settings(..., route: EditRoute | None)` and `fan_out_to(neutral, bags, route)`.

- [ ] **Step 1: Write the tests.**
  - `test_render_settings_route.py`: port the tests of `test_render_settings_gate.py` to an `EditRoute` whose mode the test flips, keeping each test's assertions. Add:
    - `test_a_rows_edit_marks_the_node`: `NODE_VALUE_CHANGED`.
    - `test_a_graph_props_row_marks_the_graph_unsaved`: `GRAPH_CONTENT_CHANGED`.
    - `test_a_rejected_value_shows_the_error_and_marks_nothing`: a field with a `validator=`; the row's error container holds `data-error`, the value is unchanged and the validation result is `None`. This is a Review Focus item.
    - `test_without_a_route_rows_write_the_bag_directly`.
    - `test_promotion_needs_the_routes_editor`: an `OPERATE` route; `_promote` adds no port.
  - `test_selection_forms.py`: update the `fan_out_to` tests to pass a route. Add:
    - `test_a_neutral_change_marks_every_node`;
    - `test_a_refused_neutral_change_reaches_no_bag`: an `OPERATE` route; the neutral write is refused and the real bags are unchanged.
  - `test_macro_node.py::test_an_interior_value_is_still_live`: replace both gates with `EditRoute(lambda: interior_editor, lambda: LevelMode.OPERATE)`, where `interior_editor = Editor(<the placement's definition>, MagicMock())`:
    - `route.set_port(interior.node_id, "value_a", 2.5, minimum=LevelMode.OPERATE) is True`;
    - the same write with `minimum=LevelMode.EDIT` is refused;
    - the value is 2.5, and the host sees no save or reassembly.

    This is a Review Focus item.
- [ ] **Step 2: Run** the three files. Expect FAIL.
- [ ] **Step 3: Implement** as listed under Files.
- [ ] **Step 4: Run** `uv run pytest tests/ui/panel/ tests/ui/panels/ tests/graph_editor/ tests/core/test_macro/ tests/haystack/ -n 4`. Expect PASS.
- [ ] **Step 5: Commit** `feat(ui): settings rows and forms write through the edit route; graph props and metadata mark unsaved`.

### Task 7: Structure edits that bypassed `Editor`

**Files:**
- Modify: `barn/haybale-graph-editor/haybale_graph_editor/panels/properties/introspect/node_ports.py:295-324`: `_on_reorder` gets `editor = route_for(context).editor()` (refusing when there is none) and calls `editor.reorder_ports(node.node_id, list(sibling_ids))`.
- Modify: `editors/graph_canvas/handlers/context_menu.py:520-535`: `toggle_edge_propagation` calls `editor.set_edge_propagation(edge_id, wrapper.propagation.toggled())`, with the editor from `route_for(self._context)`, and returns the edge's mode afterwards.
- Modify: `panels/properties/introspect/edge.py:170-192`: the switch's `_on_change` writes through `route.editor().set_edge_propagation(...)`, and shows the model's value when there is no editor. Enabled when `route.allows(LevelMode.EDIT)`.
- Modify: `docs/guides/ports.md:218`: reordering is one undo step.
- Test: `tests/graph_editor/test_structure_edits.py` (new). It takes over the reorder and propagation tests of `tests/graph_editor/test_write_gates.py` (:265-391), which are deleted from there.

**Interfaces:**
- Consumes: `Editor.reorder_ports`, `Editor.set_edge_propagation` (Task 2), `route_for` (Task 5).

- [ ] **Step 1: Write the tests.**
  - `test_a_port_reorder_is_one_undo_step`: drop through `_on_reorder` with an `EDIT` route, then `editor.undo()`; the original order is back.
  - `test_reordering_ports_refuses_on_a_locked_level`: an `OPERATE` route; the order is unchanged.
  - `test_a_propagation_toggle_is_one_undo_step`: through the context-menu handler, then `undo()`.
  - `test_the_propagation_switch_refuses_below_edit`: parametrized over a `VIEW` route and a locked `ADMIN` route.
  - `test_the_propagation_switch_writes_for_edit`.
- [ ] **Step 2: Run.** Expect FAIL.
- [ ] **Step 3: Implement.**
- [ ] **Step 4: Run** `uv run pytest tests/graph_editor/ tests/ui/panels/ -n 4`. Expect PASS.
- [ ] **Step 5: Commit** `feat(graph-editor): port reorder and edge propagation are undoable Editor actions`.

### Task 8: Farmhand writes

**Files:**
- Modify: `barn/haybale-graph-editor/haybale_graph_editor/farmhands/editor_tools.py`:
  - `GraphEditorOperateTool` (:1054-1104): keeps its `not_operable` check and read-back. It writes with `EditRoute(lambda: editor, lambda: LevelMode.OPERATE).set_port(node_id, port_id, value, minimum=LevelMode.OPERATE)`. The direct `port.set_value`, `mark_value_edited` and `value_changed` go.
  - Promote tool (:1120-1146): `ctx.fence(editor)`, then `editor.promote_setting(node_id, accessor, field, port_type)`. `False` raises `not_promotable`, with a message naming the three causes (unknown field, already promoted, direction not allowed) and a `help` pointing to `graph_editor_inspect_node`.
  - Demote tool (:1149-1167): `ctx.fence(editor)`, then `editor.remove_port(node_id, port_id)`. `False` raises `FarmhandError("demote_failed", ...)`.
  - Their `description`/`instructions` drop "NOT undo-routed" and say one undo step.
  - `GraphEditorSetMetadataTool` (:1225-1290): `ctx.fence(editor)`, then for each field `editor.set_setting(SettingOwner("graph", "meta"), field, value)`. The comment about no undo goes, and the description says one undo step that marks the graph unsaved.
- Test: `tests/farmhand/test_graph_editor_tools.py`

**Interfaces:**
- Consumes: `EditRoute` (Task 3); `SettingOwner`, `Editor.set_setting` (Task 2).

- [ ] **Step 1: Write the tests.**
  - `test_operate_marks_unsaved_and_records_nothing`: the entry is unsaved and `editor.can_undo() is False`.
  - `test_promote_is_one_undo_step` and `test_demote_is_one_undo_step`: the port appears or vanishes, and `undo()` reverses it.
  - `test_set_metadata_marks_unsaved_and_undoes`: one `undo()` restores every field the call set.
- [ ] **Step 2: Run** `uv run pytest tests/farmhand/test_graph_editor_tools.py`. Expect FAIL.
- [ ] **Step 3: Implement.**
- [ ] **Step 4: Run** `uv run pytest tests/farmhand/ -n 4`. Expect PASS.
- [ ] **Step 5: Commit** `feat(farmhand): tool writes take the edit route; promote, demote and metadata are undoable`.

### Task 9: Delete the write gates; docs, glossary and ADR

**Files:**
- Delete:
  - `packages/haywire-core/src/haywire/ui/widget/write_gate.py`;
  - `BaseWidget.write_gate` and its check in `accepts_write`;
  - the `owner.write_gate.written()` call in `binding.py`;
  - `_OuterGate` and its assignment in `optional_widget.py`.
- Delete tests:
  - `tests/ui/widget/test_write_gate.py`: move `test_a_linked_port_refuses_even_when_the_gate_allows` into `test_routed_widgets.py` as `test_a_linked_port_refuses_through_a_route_that_allows`.
  - `tests/ui/widget/test_optional_widget.py::TestWriteGate`.
  - `tests/graph_editor/test_write_gates.py`: move the port-pen tests (:400-510) unchanged into `tests/graph_editor/test_port_pen.py`; everything else is covered by Tasks 5–7.
- Create: `docs/adr/0055-every-user-edit-takes-the-edit-route.md`, with front matter like ADR 0051 and `see-also: ADR-0051, ADR-0027`.
  - **Context:** the gap from the spec.
  - **Decision:** what this slice built:
    - the route and its `minimum`;
    - level mode;
    - routed widget models;
    - `render_settings(route=)`;
    - structure verbs through `route.editor()`;
    - the unsaved rule by mechanism;
    - value writes unrecorded for now.
  - **Considered options:** a gate per write path (what it replaces), a route that mirrors every `Editor` verb, a protocol in core with the class in the library, and a check of who is writing at the cell.
  - **Consequences.**
- Modify: `docs/adr/0051-operate-tier-and-the-canvas-lock.md`. Correct these in place, with no history notes:
  - :25: enforcement is the edit route, not a write gate;
  - :26: value edits mark unsaved on every surface, graph props and metadata included;
  - :42: a new write path takes the edit route.
- Modify: `docs/guides/security.md`:
  - :76: list `view`, `operate`, `edit` and `admin`, and replace "full operator" with "can run arbitrary code";
  - :492: enforcement is the edit route, which refuses an edit the level mode does not allow.
- Modify: `docs/reference/glossary.md`:
  - remove **Write gate** and **Effective tier**;
  - add **User edit**, **Edit route** and **Level mode** (aliases to avoid: effective tier, mode (bare), canvas mode);
  - change **graph metadata** to say a metadata edit marks the graph unsaved.
- Modify: `docs/components/widgets/widget-canon.md`:
  - a widget sees a `WidgetModel` (`id`, `widget_config`, `data`, `get_value`, `set_value`);
  - its writes go through the host's route;
  - a refused write shows the model again;
  - a widget rendered with no route is read-only.
- Sweep: `grep -rn -E "write_gate|WriteGate|NodeWriteGate|GraphWriteGate|editor_for|session_allows" docs packages barn` must print nothing. Then run `uv run python scripts/bake_docs.py`.
- Test: the suites below.

- [ ] **Step 1: Delete** the code and tests listed above, and move the two kept tests.
- [ ] **Step 2: Run** `uv run pytest tests/ui/ tests/graph_editor/ tests/core/ -n 4`. Expect PASS.
- [ ] **Step 3: Write the ADR and docs.** Run the sweep; expect no output. Run `uv run mkdocs build --strict` and `uv run pytest tests/ -k "bake or docs" -n 4`. Expect PASS.
- [ ] **Step 4: Commit** `docs: the edit route (ADR 0055); remove the write gates`.

### Task 10: Full gate and live check

- [ ] **Step 1:** `uv run ruff check . && uv run ruff format --check .`
- [ ] **Step 2:** the CLAUDE.md mypy command.
- [ ] **Step 3:** `uv run pytest -m "not browser and not perf" -n 4 -q > /tmp/t.log 2>&1; echo "exit=$?"`. Expect `exit=0`.
- [ ] **Step 4:** `uv run pytest -m browser -n 4`. Expect PASS.
- [ ] **Step 5: Measure the per-write cost.** On the 512-node graph used by `internals/handoff/draw_performance_regression_fix.md`, time 1,000 `route.set_port` calls against 1,000 `port.set_value` calls on one node. Report both numbers in the handoff; no threshold.
- [ ] **Step 6: Live check in the studio** (hand to the user):
  1. Unlocked: dragging a slider marks the graph unsaved; Ctrl+Z does not undo it yet (5b-2).
  2. Locked: the slider works; Properties rows are disabled and refuse.
  3. A `view` login: the slider snaps back.
  4. Editing graph props or metadata marks the graph unsaved (new).
  5. Reordering ports in the Ports panel, then Ctrl+Z, restores the order (new).
  6. Toggling an edge's propagation, then Ctrl+Z, restores the mode (new).
  7. A multi-node form edit reaches every node and marks the graph unsaved.
  8. A slider inside a Group of a running graph: the host turns unsaved and keeps running.
  9. A slider inside a macro placement: the host stays saved.
  10. A promoted setting's card widget: the edit saves, and Reset enables in Properties.
