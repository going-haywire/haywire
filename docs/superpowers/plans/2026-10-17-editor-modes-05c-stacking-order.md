# Editor modes, slice 5c: stacking order — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Each view of a level has a saved stacking order: overlapping cards paint by it. The node menu offers Bring to Front, Bring Forward, Send Backward and Send to Back, and new nodes land on top.

**Architecture:** Stacking order is a layout-channel field: `z` for the patch, `stage_z` for the stage, both on `NodeProperties` and named by `LayoutChannel.z`. A view's order is its member nodes sorted by `(z, graph order)`. One pure function turns a verb into the new order and writes `z = rank` only where the rank changed, as one undoable `Editor` action through the edit route. A card shows its z the way it shows its size: `UINode` watches the field and restyles its container with no redraw. The patch keeps its hover/selected lift; the stage does not.

**Tech Stack:** Python 3.12, NiceGUI/Vue 3 (`canvas.vue`), pytest, Playwright browser tier.

**Spec:** [2026-10-12-editor-modes.md](2026-10-12-editor-modes.md) "Stacking order (Decision Q4, 2026-10-14)" and Sequence 5c, plus the user's 5c decisions of 2026-10-17 (below).

## Global Constraints

- **Branch:** `feat/editor-modes-slice5c` in `.worktrees/editor-modes-slice5c`, cut from `feat/editor-modes-slice1` (`861b2cd8`). It merges into slice1 after the user's live check. Nothing goes to master until slice 6 lands.
- **Q1 (b):** in the patch view a hovered, selected or dragged card lifts above all others, as today. In the stage view hover, selection and drag never change paint order (drag amended by the user at the live check, 2026-10-18).
- **Q2 (c):** the four verbs live only in an "Arrange" submenu of the selection menu: no keyboard shortcuts and no toolbar button. The toolbar's ⋯ shows the same selection menu, so the submenu appears there too.
- **Q3 (a):** Forward/Backward move one step in the view's total order. They do not look at whether cards overlap.
- **Q4 (a):** annotations are ordinary nodes here.
- **Saved files:** a `z`/`stage_z` of `0` is the default and is not written, so an untouched graph saves byte-identical.
- **Tests and docs:** use the smallest test tier while iterating, then the full gates at the end. Docs follow `.claude/rules/python-docs.md`, and glossary/ADR edits land with the code (Task 5).

## Decisions

1. **Fields.** `NodeProperties.z = setting[INT](0, label="Stacking order", description="Paint order in the patch view; higher draws on top.", order=55, category="layout")` and `stage_z = setting[INT](0, label="Stage stacking order", description="Paint order in the stage view; higher draws on top.", order=105, category="stage")`. `LayoutChannel` gains a required `z: str` after `size_adapt`; `PATCH.z = "z"`, `STAGE.z = "stage_z"`.
2. **Order.** `stacking_order(graph, channel)` returns the channel's members (`channel.includes(props)`) sorted by `(getattr(props, channel.z), index in graph.node_wrappers)`, bottom first. In the browser equal z-indexes resolve by DOM order, which is mount order, so a fresh mount matches graph order.
3. **Verbs.** `Restack` is a `str` enum: `FRONT="front"`, `BACK="back"`, `FORWARD="forward"`, `BACKWARD="backward"`. Node ids that are unknown or not in the channel are ignored.
   - FRONT/BACK: a stable partition that puts the selected nodes last/first, keeping their relative order.
   - FORWARD: walk the order from top to bottom, and swap each selected node with the node above it when that node is unselected.
   - BACKWARD: the mirror image.
   - The result is `z = index` for every node whose z differs. An empty result records nothing.
4. **Action.** `RestackNodesAction(graph, z_by_node: dict[str, int], channel)` captures the old values at construction. Execute and undo write the channel's z field and call `wrapper.mark_value_edited()` on each node they change. It is one step and not mergeable. `Editor.restack_nodes(node_ids, how, channel=PATCH) -> bool` returns `False` for an empty result or a failure.
5. **No new `ChangeReason`.** This deviates from the 5c proposal: z rides the restyle path the size fields use. The canvas updates through `UINode`'s field subscription, so a Properties-panel or Farmhand `set_property` write of `z` also repaints. Unsaved comes from `mark_value_edited` (`NODE_VALUE_CHANGED` + `GRAPH_CONTENT_CHANGED`, already forwarded from an interior without reassembly).
6. **New nodes on top.** `top_z(graph, channel, exclude=())` returns the max z of the channel's members not in `exclude`, plus 1, or `0` when there are none.
   - `AddNodeAction` gets the keyword `on_top: bool = True`. On first execution only, it sets the new node's z in every channel of `CHANNELS` that includes it to `top_z(graph, channel, exclude={node_id})`. Redo re-adds the same wrapper, so its z is kept.
   - `PasteClipboardAction` passes `on_top=False` and writes z into each child's `node_data` at construction, per channel. The pasted members of that channel, as placed, are sorted by `(source z, payload order)` and get `top_z(graph, channel) + i`.
   - `SetStageMembershipAction`'s add path writes `stage_z = top_z(graph, STAGE) + i` in the same patch order as its spots, and captures/restores `stage_z`.
   - A Reset drops z to 0, as it drops every stage field (slice 4, Q2b).
7. **Render.**
   - Server side: `UINode._apply_stacking()` writes `container.style(f"z-index: {z}")` from `channel.z`. It runs at construction, on a change of that field, and in `_rebind_props`. `VisualLayerHandlers` stops writing `z-index: 100` (in `add_node_visual` and `update_node_position`).
   - Browser side: `canvas.vue` stops writing `style.zIndex` at drag start (`'1000'`) and drag end (`'100'`), because `.dragging-node` already lifts.
8. **Canvas ladder.** Node z-indexes are unbounded ranks, so every lift above them rises:
   - `--hw-z-canvas-selected: 1000000`
   - `--hw-z-canvas-hover: 1000001`
   - `--hw-z-canvas-gadget: 1000002`
   - `.hw-edge-handles` `z-index: 1000003`
   - The marquee (999) is unchanged: it sits outside `#node-container`, whose stacking context (z 2) holds every card.
9. **Stage drops hover/selected lift.**
   - `GraphCanvasVue(..., stage: bool = False)` stamps `data-hw-stage` on its root when true. `GraphCanvasManager._setup_canvas` passes `stage=self.channel.stage`.
   - In `canvas.vue`, the `z-index` declarations leave `[data-node-id]:hover` and `[data-node-id].node-selected`. They move to `.graph-canvas:not([data-hw-stage]) [data-node-id]:hover` and `.graph-canvas:not([data-hw-stage]) [data-node-id].node-selected` (same values, `!important`), in the same style block as the rules they came from.
   - `.dragging-node` keeps its lift in both views.
10. **Menu.**
    - A new surface `SelectionArrangeMenu` (`id = "selection-arrange"`, `provides = SelectionActions`, no `poll`).
    - A hosting panel `ArrangeSelectionMenuPanel` on `SelectionMenu`: `label="Arrange"`, `icon=hui.icon.arrange`, `order=17`, `access=AccessTier.EDIT`, `hosts=(SelectionArrangeMenu,)`. Its poll is true when the selection holds a node of the active graph, and `draw_disabled` draws a greyed row.
    - Four leaves on `SelectionArrangeMenu` (`access=EDIT`, same poll):

      | Leaf panel | Label | Icon | Order |
      |---|---|---|---|
      | `BringToFrontMenuPanel` | "Bring to Front" | `bring_to_front` | 10 |
      | `BringForwardMenuPanel` | "Bring Forward" | `bring_forward` | 20 |
      | `SendBackwardMenuPanel` | "Send Backward" | `send_backward` | 30 |
      | `SendToBackMenuPanel` | "Send to Back" | `send_to_back` | 40 |

      Each calls `self.actions.restack_selection(Restack.…)`.
    - New icons in `ui/elements/icons.py`: `arrange="layers"`, `bring_to_front="flip_to_front"`, `bring_forward="arrow_upward"`, `send_backward="arrow_downward"`, `send_to_back="flip_to_back"`.
    - `SelectionActions.restack_selection(how: Restack) -> None`. `SessionContextMenuProvider` emits `RestackEvent(node_ids=list(selected_nodes), how=how.value)`, and `SelectionToolbarProvider` delegates to it.
    - `RestackEvent` is registered as `@graph_event("restackNodes", category="user", description="Change the stacking order of the selected nodes")` with fields `node_ids: List[str]` and `how: str`.
    - `VisualLayerHandlers.process_restack` (default access, edit) calls `editor.restack_nodes(event.node_ids, Restack(event.how), self.channel)`. A no-op is silent.

## Review Focus

1. An untouched legacy graph (every z 0) opens stacked in graph order as before and saves with no `z`/`stage_z` key; the first Bring to Front writes z only to nodes whose rank changed. Test: Task 1 `test_an_untouched_graph_saves_no_stacking_fields`, `test_bring_to_front_writes_only_changed_ranks`.
2. On stage, hovering the exposed edge of a back card does not lift it over the card in front; in the patch it does. Test: Task 3 browser `test_hover_lifts_a_back_card_in_the_patch_only`.
3. A drag on stage ends with the card at its own stacking order, not at a leftover inline value. Test: Task 3 browser `test_a_stage_drag_keeps_the_stacking_order`.
4. A verb that changes nothing (Forward on the top card) adds no undo step; a real one is one step that marks the graph unsaved and undoes every z it wrote. Test: Task 1 `test_forward_at_the_top_records_nothing`, `test_a_restack_is_one_undo_step_and_marks_unsaved`.
5. Pasting overlapping on-stage nodes keeps their relative order and lands them above everything already there. Test: Task 2 `test_paste_lands_on_top_keeping_relative_order`.

---

### Task 1: Core — fields, order, verbs, action

**Files:**
- Create: `packages/haywire-core/src/haywire/core/graph/stacking.py`
- Modify: `packages/haywire-core/src/haywire/core/node/properties.py` (after `size_adapt`, after `stage_size_adapt`), `.../core/node/layout.py` (`LayoutChannel`, `PATCH`, `STAGE`), `.../core/undo/actions/graph_actions.py` (new `RestackNodesAction` after `SetStageMembershipAction`), `.../core/graph/editor.py` (`restack_nodes` after `remove_from_stage`)
- Test: `tests/core/test_graph/test_stacking.py` (integration; helpers `_key`, `_editor`, `_collect`, `_node` as in `tests/core/test_graph/test_stage_graph.py`)

**Interfaces:**
- Produces: `Restack` (enum); `stacking_order(graph: BaseGraph, channel: LayoutChannel) -> list[str]`; `restacked(graph: BaseGraph, node_ids: Iterable[str], how: Restack, channel: LayoutChannel) -> dict[str, int]`; `top_z(graph: BaseGraph, channel: LayoutChannel, exclude: Collection[str] = ()) -> int`, all in `haywire.core.graph.stacking`; `LayoutChannel.z`; `RestackNodesAction(graph, z_by_node, channel)`; `Editor.restack_nodes(node_ids: list[str], how: Restack, channel: LayoutChannel = PATCH) -> bool`.

- [ ] **Step 1: Write the failing tests** (four nodes `a, b, c, d` made in that order, all z 0, unless stated):
  - `test_channels_name_their_stacking_field`: `PATCH.z == "z"`, `STAGE.z == "stage_z"`.
  - `test_an_untouched_graph_saves_no_stacking_fields`: `"z"` and `"stage_z"` are not in `wrapper.serialize()["node_data"]["props"]["values"]`.
  - `test_stacking_order_sorts_by_z_then_graph_order`: with `c.z = 5`, the order is `[a, b, d, c]`.
  - `test_stage_order_holds_only_on_stage_nodes`: with only `b, d` on stage, `stacking_order(graph, STAGE) == [b, d]`.
  - `test_bring_to_front_writes_only_changed_ranks`: `restack_nodes([a, c], FRONT)` gives order `[b, d, a, c]`, `d.z == 1`, `a.z == 2`, `c.z == 3`, and `b` is still not locally set (`not b.props._is_locally_set("z")`).
  - `test_send_to_back_keeps_the_selections_order`: `restack_nodes([d, b], BACK)` gives `[b, d, a, c]`.
  - `test_forward_steps_one_node`: `[a]` gives `[b, a, c, d]`; then `[a, b]` from the fresh order `[a, b, c, d]` gives `[c, a, b, d]`.
  - `test_backward_steps_one_node`: `[d]` gives `[a, b, d, c]`.
  - `test_forward_at_the_top_records_nothing`: `restack_nodes([d], FORWARD) is False` and `not editor.history_manager.can_undo()`.
  - `test_unknown_and_off_channel_ids_are_ignored`: `restack_nodes(["missing", a], FRONT, STAGE)` with `a` off stage returns `False`.
  - `test_a_restack_is_one_undo_step_and_marks_unsaved`: after FRONT on `[a]`, `any(r.requires_save() for r in results)`. One `undo()` restores `[a, b, c, d]` with every z 0, and `redo()` restores the order.
  - `test_a_stage_restack_writes_stage_z_only`: patch z untouched.
- [ ] **Step 2:** Run `uv run pytest tests/core/test_graph/test_stacking.py -q`. Expected: FAIL (import error).
- [ ] **Step 3:** Implement Decisions 1–5. `restacked` builds the new order list per Decision 3 and diffs `index` against the current z. The FORWARD walk runs from `len-2` down to `0` and swaps `order[i]`/`order[i+1]` when `order[i]` is selected and `order[i+1]` is not. BACKWARD runs from `1` up and swaps `order[i]`/`order[i-1]` symmetrically. Write the module docstring and the `Restack`/function docstrings with examples.
- [ ] **Step 4:** Run the tests again, plus `tests/core/test_graph/test_stage_graph.py`, `tests/core/test_node/`, `tests/core/test_undo/`. Expected: PASS. `LayoutChannel` is frozen with a new required field, so grep for every `LayoutChannel(` construction in `packages/`, `barn/` and `tests/` and add `z=`.
- [ ] **Step 5:** Commit `feat(core): stacking order — z/stage_z, the four verbs, one undo step`.

### Task 2: Core — new nodes land on top

**Files:**
- Modify: `graph_actions.py` (`AddNodeAction.__init__`/`_execute_impl`, `PasteClipboardAction.__init__` steps 3+, `SetStageMembershipAction`), `core/node/layout.py` (add `with_z(node_data, z, channel=PATCH) -> dict` beside `with_position`, same copy semantics)
- Test: `tests/core/test_graph/test_stacking.py` (append)

**Interfaces:**
- Consumes: `top_z`, `stacking_order`, `LayoutChannel.z` (Task 1).
- Produces: `AddNodeAction(..., on_top: bool = True)`; `with_z`.

- [ ] **Step 1: Write the failing tests:**
  - `test_a_created_node_lands_on_top`: after FRONT on `[a]` (so `a.z == 3`), `editor.create_wrapper(_key(), (0, 0))` gives z `4`, and the new node is `stacking_order(graph, PATCH)[-1]`. On a fresh graph of all-zero nodes, a new node gets z `1`.
  - `test_a_node_made_in_the_stage_view_lands_on_top_in_both_views`: `create_wrapper(_key(), STAGE.to_canvas(40, 40), STAGE)` makes the node last in both orders.
  - `test_redo_of_a_create_keeps_its_z`.
  - `test_paste_lands_on_top_keeping_relative_order`: two on-stage nodes with `stage_z` 2 (`p`) and 1 (`q`) are copied with `build_clipboard_payload(graph, [p, q], [], "s")` and pasted in the stage view. Both copies sit above every existing stage node, the copy of `p` above the copy of `q`, and the same holds for patch `z`.
  - `test_add_to_stage_lands_on_top_of_the_stage`: the added node's `stage_z` equals the old stage max + 1, and undo restores its previous `stage_z`.
- [ ] **Step 2:** Run. Expected: FAIL.
- [ ] **Step 3:** Implement Decision 6.
- [ ] **Step 4:** Run the tests, plus `tests/core/test_graph/`, `tests/graph_editor/test_stage_creation.py`, `tests/core/test_undo/`. Expected: PASS.
- [ ] **Step 5:** Commit `feat(core): new, pasted and staged nodes land on top`.

### Task 3: Canvas — paint by stacking order

**Files:**
- Modify: `barn/haybale-graph-editor/haybale_graph_editor/editors/graph_canvas/ui_node.py` (`_subscribe_slot_fields`, `_unsubscribe_slot_fields`, `_rebind_props`, new `_apply_stacking`/`_on_stacking_change`, `__init__`), `.../graph_canvas/handlers/visual_layer.py:642` and `:689`, `.../graph_canvas/graph_canvas_manager.py:346`, `packages/haywire-core/src/haywire/ui/components/graph/canvas.py` (`GraphCanvasVue.__init__`), `.../components/graph/canvas.vue` (ladder vars ~:4237, drag writes :2241/:2291, hover/selected rules ~:4370–4395, `.hw-edge-handles` ~:4556, the attribute index at the top of `<script>` gains `data-hw-stage`), `tests/ui/harness/routes.py` (new route)
- Test: `tests/graph_editor/test_ui_node_stacking.py` (integration, `card` fixture as in `test_ui_node_resubscribe.py`), `tests/ui/test_canvas_handlers/test_stage_visual_layer.py` (append), `tests/ui/harness/test_stacking.py` (browser)

**Interfaces:**
- Consumes: `LayoutChannel.z` (Task 1).
- Produces: `GraphCanvasVue(..., stage: bool = False)`; harness route `/graph-stack?channel=patch|stage`. The route mounts two on-stage nodes, `back` (z/stage_z 0) and `front` (z/stage_z 1), placed so `front` covers `back`'s lower-right quarter in both views. It stamps `#stack-ids` with `data-back` and `data-front`.

- [ ] **Step 1: Write the failing tests:**
  - `test_the_container_carries_the_nodes_z`: `ui_node.container._style["z-index"] == "0"`; after `node.props.z = 7`, it is `"7"` and `ui_node.current_ui_card` is the same object (no redraw).
  - `test_a_stage_card_reads_stage_z` (`channel=STAGE`).
  - `test_stacking_follows_the_node_across_a_rebuild` (parametrized reset/hot_reload, as `test_slot_restyle_follows_the_node_across_a_rebuild`).
  - `test_a_move_leaves_the_z_index_alone`: after `update_node_position`, the container style string has no `z-index: 100`.
  - `test_a_stage_canvas_is_marked`: `GraphCanvasVue(stage=True)._props["data-hw-stage"]` is truthy, and the attribute is absent by default.
  - Browser, using `document.elementFromPoint` at the overlap centre and checking `closest('[data-node-id]')`:
    - `test_the_higher_card_paints_on_top` (both channels): it is `front`.
    - `test_hover_lifts_a_back_card_in_the_patch_only`: hover `back`'s exposed upper-left, then probe the overlap. The result is `back` in the patch and `front` on stage.
    - `test_a_stage_drag_keeps_the_stacking_order`: drag `back` 10 px, release, move the mouse off both cards, and the probe gives `front`.
- [ ] **Step 2:** Run `uv run pytest tests/graph_editor/test_ui_node_stacking.py tests/ui/test_canvas_handlers/test_stage_visual_layer.py -q` and `uv run pytest tests/ui/harness/test_stacking.py -m browser`. Expected: FAIL.
- [ ] **Step 3:** Implement Decisions 7–9 and the harness route (pattern: `_build_stage_graph` + `/graph-stage` in `routes.py`). Update the canvas-ladder comment above the vars to say node z-indexes are stacking ranks and every lift sits above them.
- [ ] **Step 4:** Run the same commands, plus `uv run pytest tests/ui/harness/test_stage_origin.py tests/ui/harness/test_graph_views.py -m browser` and `tests/graph_editor/test_ui_node_resubscribe.py`. Expected: PASS.
- [ ] **Step 5:** Commit `feat(graph-editor): cards paint by stacking order; the stage never lifts on hover or select`.

### Task 4: Arrange submenu

**Files:**
- Create: `barn/haybale-graph-editor/haybale_graph_editor/panels/graph/menu/selection/arrange.py`
- Modify: `.../surfaces/selection.py` (`SelectionActions.restack_selection`, new `SelectionArrangeMenu`), `.../surfaces/__init__.py` (export), `.../editors/graph_canvas/handlers/context_menu.py` (`SessionContextMenuProvider.restack_selection` after `remove_from_stage`), `.../handlers/selection_toolbar.py` (delegate after `remove_from_stage`), `.../handlers/visual_layer.py` (`process_restack` after `process_remove_from_stage`), `packages/haywire-core/src/haywire/ui/components/graph/event_definitions.py` (`RestackEvent` after `RemoveFromStageEvent`), `.../ui/elements/icons.py` (Decision 10 icons beside `stage_add`), the panel package `__init__` that imports `stage.py`'s panels (import `arrange` the same way), `tests/studio/test_component_access_classification.py` (`EDIT_PANELS` gains the five panels)
- Regenerate: `packages/haywire-core/src/haywire/ui/components/graph/generated/graph_events.js` with `uv run python ./scripts/generate_vue_events.py`
- Test: `tests/graph_editor/test_arrange_submenu.py` (pattern: `tests/graph_editor/test_rebuild_submenu.py`), `tests/ui/test_canvas_handlers/test_stage_visual_layer.py` (append)

**Interfaces:**
- Consumes: `Restack`, `Editor.restack_nodes` (Task 1).
- Produces: `SelectionActions.restack_selection(how: Restack) -> None`; `RestackEvent(node_ids: List[str], how: str)`.

- [ ] **Step 1: Write the failing tests:**
  - `test_arrange_row_hosts_the_four_verbs_and_stays_live`: the labels include "Arrange" and the four leaf labels; the flyout row is not `hw-disabled`; there are 5 `hw-menu-row`s.
  - `test_arrange_row_greys_without_a_selection`.
  - `test_each_leaf_calls_restack_with_its_verb`: clicking each leaf leaves `("restack_selection", (Restack.X,))` in `stub.calls`.
  - `test_a_restack_event_reaches_the_editor_on_the_canvas_channel`: a `STAGE` layer whose route editor is a `MagicMock` gets `restack_nodes(["a"], Restack.FORWARD, STAGE)`.
  - `test_restack_selection_emits_a_restack_event` for the context-menu provider: `how == "front"` and the ids are the selected ones.
  - The classification test fails until the five panels are listed.
- [ ] **Step 2:** Run the new files plus `tests/studio/test_component_access_classification.py`. Expected: FAIL.
- [ ] **Step 3:** Implement Decision 10 and regenerate `graph_events.js`.
- [ ] **Step 4:** Run the same tests, plus `tests/graph_editor/test_selection_toolbar_provider.py`, `tests/ui/test_canvas_handlers/`, `tests/graph_editor/test_rebuild_submenu.py`. Expected: PASS.
- [ ] **Step 5:** Commit `feat(graph-editor): Arrange submenu — Bring to Front, Forward, Backward, Send to Back`.

### Task 5: Docs, then the gates

**Files:** `docs/reference/glossary.md`, `docs/adr/0054-the-stage-view.md`, `docs/reference/design-guide.md` (§2.9 canvas ladder), `docs/superpowers/plans/2026-10-12-editor-modes.md` (Sequence 5c links this plan)

- [ ] **Step 1:** Make the doc edits:
  - Glossary: add a **Stacking order** row after **Layout channel**. It defines the per-view order `(z, graph order)`, says the stage drops hover/selected lift, describes the four verbs and new nodes on top, and lists as aliases to avoid "z-order (fine in code)" and "layer".
  - Glossary **Layout channel** row: add `z` to the field list.
  - Glossary **Canvas ladder** row: node z-indexes are stacking ranks and every lift sits above them.
  - ADR 0054: add a section "Stacking order (slice 5c)" with Decisions 1, 3, 5, 6, 8 and 9 in two paragraphs.
  - Design guide §2.9: the canvas-ladder text gets the new values and the rule "node z-index is the stacking rank; never write a z-index on a card from JS".
- [ ] **Step 2:** Run the gates:
  - `uv run ruff check .` and `uv run ruff format --check .`
  - the full mypy command from CLAUDE.md
  - `uv run pytest -m "not browser and not perf" -n 4 -q > /tmp/t.log 2>&1; echo "exit=$?"`
  - `uv run pytest -m browser -n 4 -q > /tmp/b.log 2>&1; echo "exit=$?"`

  Expected: all exit 0.
- [ ] **Step 3:** Commit `docs: stacking order — glossary, ADR 0054, canvas ladder`.

### Live check (user, studio started from the worktree)

1. Open an existing graph. Cards stack as before, and saving without edits leaves the file unchanged (`git diff`).
2. Overlap two cards in the patch. Right-click the back one → Arrange → Bring to Front: it paints on top. Undo restores the old order. The file shows unsaved.
3. Overlap three cards. Bring Forward and Send Backward move one step each, and Bring Forward on the top card does nothing (no undo step).
4. Patch: hovering or selecting a back card lifts it. Stage: hovering or selecting a back card does not, while dragging it does, and on release it returns to its order.
5. Create a node and paste a copied pair onto overlapping cards, in both views: they land on top, and the pair keeps its order.
6. Add to Stage onto an overlapping spot: the added card is on top on stage.
7. Locked level and view/operate login: the Arrange row is absent.
