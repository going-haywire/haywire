# Editor modes, slice 4: Position — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** a node's position has one home, its props (`posX`/`posY`). The saved file's `"position"` key is dropped. A **layout channel** names the props fields a canvas reads and writes, so slice 5's stage can reuse the move and resize machinery.

**Architecture:**
- **One source.**
  - `NodeWrapper` loses `_initial_position` and its `position` constructor argument.
  - Every reader of a serialized node's position reads `node_data.props.values.posX/posY`, through one helper.
  - Callers that hold `node_data` write the position into it.
  - A rebuild (hot reload or reset) carries over the old instance's `posX`/`posY`, and nothing else.
- **The layout channel** is a small frozen dataclass of props field names, with one constant in this slice: `PATCH`.
  - Server-side code on the move and resize path takes it as a parameter defaulting to `PATCH`: the move actions, `BaseGraph.move_node`, `NodeWrapper.move`, the canvas-size check, the resize handler, the visual layer and `UINode`.
  - A `GraphCanvasManager` owns one channel.
  - `NODE_MOVED` carries no channel: each canvas re-reads its own fields.
  - The JS canvas is untouched, because positions and sizes reach it as values.

**Tech Stack:** Python 3.12, NiceGUI/Vue 3, pytest (`uv run pytest`), ruff, mypy.

**Spec:** [2026-10-12-editor-modes.md](2026-10-12-editor-modes.md), section "Node position", and Sequence item 4. The decisions below were taken with the user on 2026-10-14. They refine the spec and bind where they differ.

## Decisions (2026-10-14)

1. **(Q1)** The `position` argument is removed from `NodeWrapper`. A caller that builds a node from `node_data` writes `posX`/`posY` into that data.
   - **Controller ruling:** building with non-empty `node_data` takes the *restore* path (`_initialize_from_dict`), and an empty one runs `init()` (`NodeWrapper.build` → `_initialize`, `node_wrapper.py:~339`). A fresh node therefore cannot carry its position in `node_data` without skipping `init()`.
   - `BaseGraph.create_node_wrapper` and `AddNodeAction` keep an optional, keyword-only `position: tuple[float, float] | None = None`. When given, it is written to the built node's props after `build` and before `add_node_wrapper`. Nothing stores it.
   - Callers with `node_data` (load, instantiate, paste, expand, collapse, detach, Save new Macro) put the position in `node_data` and pass no `position`.
   - `Editor.create_wrapper` keeps its `(3750, 3750)` default.
2. **(Q2)** A rebuild with no `node_info` carries over the old instance's `posX`/`posY` only. Width, height and `size_adapt` reset as they do today.
3. **(Q3)** The layout channel is built now, with `PATCH` only.
4. **(Q4, for slice 5, not built here)** Stacking order exists in both views, each with its own field (`z` for the patch, `stage_z` for the stage). The verbs are Bring to Front, Send to Back, Forward and Backward. It lands in slice 5 as a channel field. Record it in the spec (Task 6).

## Global Constraints

- `LayoutChannel` lives in `packages/haywire-core/src/haywire/core/node/layout.py`. `PATCH = LayoutChannel(name="patch", x="posX", y="posY", width="width", height="height", size_adapt="size_adapt")`.
- A serialized node's position is `node["node_data"]["props"]["values"][channel.x / channel.y]`. **A missing value means `0.0`**, because settings serialize sparsely and a value equal to its default is omitted. Verify the path against `Settings` serialization in Task 1.
- An old file's `"position"` key is ignored: no upgrader and no `format_version` bump. A node with no `posX`/`posY` in its props loads at `(0, 0)`, where today's fallback is `(100, 100)`.
- The clipboard keeps `CLIPBOARD_FORMAT_VERSION = 2`. Its bounding box is read from props.
- The Farmhand `move_nodes` tool and every JS event stay unchanged.
- `canvas_width`/`canvas_height` describe the patch. The canvas-size check takes a channel, but where the stage's extent is stored is slice 5's decision.
- **Docs:** follow `.claude/rules/python-docs.md`. The ADR and glossary land in Task 6.
- **Commit trailer:** `Co-Authored-By: Claude Opus 5.5 (1M context) <noreply@anthropic.com>`.

## Review Focus

1. **A node at exactly `(0, 0)`** round-trips through save/load, copy/paste and collapse/expand, even though sparse serialization omits `posX`/`posY` (Tasks 2 and 3).
2. **A position written through `set_property`** (the Properties panel or Farmhand) survives save, load and a rebuild. This is the spec's trap "position lives in two places" (Task 3).
3. **Hot reload and reset** keep a node where it is (Task 3).
4. **A file whose `"position"` disagrees with its props** loads at the props position (Task 3).
5. **Drag, resize from the top-left, and a locked canvas's snap-back** behave as before. The existing tests and the live check cover this (Task 5).

---

### Task 1: The layout module

**Files:**
- Create: `packages/haywire-core/src/haywire/core/node/layout.py`
- Modify: `packages/haywire-core/src/haywire/core/node/properties.py`, `set_position`/`get_position` (~:174-181)
- Test: create `tests/core/test_node/test_layout_channel.py`

**Interfaces — produces:**
- `@dataclass(frozen=True) class LayoutChannel` with fields `name: str, x: str, y: str, width: str, height: str, size_adapt: str`.
- `PATCH: LayoutChannel`, as in Global Constraints.
- `position_of(node: Mapping[str, Any], channel: LayoutChannel = PATCH) -> tuple[float, float]`: reads a serialized wrapper dict, the shape `NodeWrapper.serialize` returns. A missing `node_data`, `props`, `values` or field reads as `0.0`.
- `with_position(node_data: Mapping[str, Any] | None, x: float, y: float, channel: LayoutChannel = PATCH) -> dict[str, Any]`: returns a copy of `node_data` with the props values set. It never mutates its argument.
- `NodeProperties.set_position(pos, channel=PATCH)` and `get_position(channel=PATCH)` read and write through the channel's field names.

- [ ] **Step 1: Tests.**
  - `test_position_of_reads_props_values`
  - `test_position_of_reads_a_missing_field_as_zero`: a node whose `values` lacks `posX` → `(0.0, y)`. A node with no `node_data` → `(0.0, 0.0)`.
  - `test_with_position_copies`: the original dict is unchanged, and the result has `props.values.posX/posY`. Its other `props.values` and `store` are kept.
  - `test_a_channel_names_the_fields`: `SWAPPED = LayoutChannel("swapped", x="posY", y="posX", width="height", height="width", size_adapt="size_adapt")`. `props.set_position((1.0, 2.0), SWAPPED)` gives `posY == 1.0` and `posX == 2.0`.
  - `test_position_of_matches_a_real_serialization`: build a node, set its position, serialize it. `position_of` returns the set position, for both `(0, 0)` and `(120.5, 40.0)`.
- [ ] **Step 2: Run** `uv run pytest tests/core/test_node/test_layout_channel.py -q`. Expect FAIL.
- [ ] **Step 3: Implement.**
- [ ] **Step 4: Run** the same file, then `uv run pytest tests/core/test_node/ -n 4 -q`. Expect PASS.
- [ ] **Step 5: Commit** `feat(node): a layout channel names the props fields a canvas lays out with`.

### Task 2: Serialized-position readers move to props

The `"position"` key is still written in this task, so every step stays green. Only the readers change.

**Files:**
- Modify:
  - `packages/haywire-core/src/haywire/core/graph/clipboard.py` ~:56-58: the bounding box via `position_of`.
  - `packages/haywire-core/src/haywire/core/undo/actions/graph_actions.py`:
    - `PasteClipboardAction` ~:634-663: offset from `position_of`. Keep forcing props to the paste point with `with_position`, and stop passing `position=`.
    - Collapse interior ~:1294 and Expand ~:1772: drop the `position` read and argument, since `node_data` already carries props.
    - Detach ~:1953 and Save new Macro ~:2096: read the card's position from `card.node.props.get_position()`, and pass it into the new card's `node_data` with `with_position`, not `position=`.
    - The collapse card ~:1640: `with_position(node_data, *_centroid(nodes))`.
    - `_boundary_positions` ~:2180 and `_centroid` ~:2195: use `position_of`.
    - The collapse boundary nodes ~:1326 and `SplitEdgeWithRerouteAction` ~:800 are fresh nodes and keep `position=`.
  - `packages/haywire-core/src/haywire/core/graph/subgraph.py` `instantiate` ~:207: drop the `position` read and argument.
  - `barn/haybale-graph-editor/haybale_graph_editor/editors/graph_canvas/handlers/selection.py` ~:216 (duplicate's bounding box), if it reads `"position"`.
- Test: `tests/core/test_undo/test_paste_action.py`, `tests/core/test_graph/test_clipboard_payload.py`, `tests/core/test_undo/test_collapse_expand.py`, `tests/core/test_macro/test_detach_placement.py`.

**Interfaces — consumes:** `position_of` and `with_position` (Task 1).

- [ ] **Step 1: Tests.**
  - `test_paste_of_a_node_at_the_origin_lands_at_the_paste_point`: copy a node at `(0, 0)` with a second node at `(300, 200)`, paste at `(1000, 1000)` → `(1000, 1000)` and `(1300, 1200)`.
  - `test_clipboard_bounding_box_reads_props`: a payload whose nodes carry props values but no `"position"` key gives the correct `bounding_box`.
  - `test_expand_keeps_interior_positions_including_the_origin`: collapse then expand a selection holding a node at `(0, 0)`. Every node is back at its position.
  - `test_detach_keeps_the_card_position`: check it still passes once the `"position"` read is gone.
  - Update the hand-built `"position"` dicts in `test_paste_action.py` and `test_clipboard_payload.py`, and in `tests/ui/test_canvas_handlers/test_selection_handlers.py` and `tests/libraries/test_clipboard_reactive.py` if they feed a reader changed here, to carry `node_data.props.values`.
- [ ] **Step 2: Run** the touched test files. The new tests FAIL.
- [ ] **Step 3: Implement.** Afterwards, grep `packages/` and `barn/` for `get("position")` and `["position"]`. Only `NodeWrapper.serialize` and the graph loader may remain; Task 3 removes both.
- [ ] **Step 4: Run** `uv run pytest tests/core/ tests/ui/test_canvas_handlers/ tests/libraries/ -n 4 -q`. Expect PASS.
- [ ] **Step 5: Commit** `refactor(graph): read a serialized node's position from its props`.

### Task 3: One source — drop `_initial_position` and the file key

**Files:**
- Modify:
  - `packages/haywire-core/src/haywire/core/node/node_wrapper.py`:
    - `__init__` ~:128-167: remove `position` and `_initial_position`.
    - `_instantiate` ~:300-315: on a rebuild, read the old instance's `props.get_position()` before `_cleanup()` and set it on the new instance. A first build sets nothing.
    - `move` ~:572: write props only.
    - `serialize` ~:712: no `"position"` key.
  - `packages/haywire-core/src/haywire/core/graph/base.py`:
    - `create_node_wrapper` ~:409: the signature becomes `(self, registry_key, node_data=None, node_id=None, *, position: tuple[float, float] | None = None)`. Write `position` after `build`, before `add_node_wrapper`.
    - The loader ~:1022: no `position`.
    - The comment at ~:138 about calling `estimate_canvas_size` after load: check it, and fix it if wrong.
  - `graph_actions.py` `AddNodeAction` ~:38-90: `position: tuple[float, float] | None = None`, keyword-only, passed through.
  - The callers of `create_node_wrapper`/`AddNodeAction` that pass `position` positionally or rely on the old `(3750, 3750)` default:
    - `packages/haywire-core/src/haywire/core/graph/utils/graph_to_python.py` ~:84-86 (the generated code);
    - `barn/haybale-core/haybale_core/nodes/events/shutdown.py` ~:45 (a docstring example; regenerate that library's docs if it changes);
    - `barn/haybale-studio/haybale_studio/farmhands/catalog.py:265` and `authoring.py:369`;
    - `packages/haywire-studio/src/haywire_studio/packaging/docs/extract.py:125`;
    - `benchmarks/cases.py:80,146`;
    - `.scratch/pan-perf/make_edge_graph.py:56`, which reads the file key;
    - `tests/conftest.py:549` and `tests/ui/harness/routes.py`.

    Grep `create_node_wrapper(` and `AddNodeAction(` across the repo, including `tests/`, `benchmarks/` and `.scratch/`.
- Test: new `tests/core/test_node/test_position_single_source.py`; fix `tests/core/graph/test_load_degradation.py` (its poison was `"position" = 12345`; poison a field the loader still reads); update the `"position"` fixtures in `tests/core/test_macro/` (6 files) and `tests/studio/test_docs/test_extract.py`.

**Interfaces — consumes:** `PATCH` and `get_position` (Task 1). After Task 2, nothing reads the file key.

- [ ] **Step 1: Tests**, in `test_position_single_source.py`:
  - `test_serialize_writes_no_position_key`
  - `test_a_node_at_the_origin_round_trips`: `to_dict` → a fresh graph `load_from_dict` → `(0.0, 0.0)`.
  - `test_a_position_set_through_set_property_survives_save_and_load`: `editor.set_property(node_id, "posX", 640.0)` → `to_dict` → load → `posX == 640.0`.
  - `test_a_rebuild_keeps_the_position_only`: move the node to `(640, 320)` and set a manual `width`, then `request_node_reset(node_id)` and flush validation. The position is `(640, 320)`, and `width` is back at its default.
  - `test_a_hot_reload_keeps_the_position`: deliver `NODE_HOT_RELOADED` the way `node_wrapper.py:~548` receives it → the position is kept.
  - `test_props_win_over_a_stale_file_position`: a file node with `"position": [5, 5]` and props `(700, 80)` loads at `(700, 80)`.
  - `test_a_file_node_without_props_position_loads_at_the_origin`
  - `test_create_node_wrapper_writes_the_given_position_and_runs_init`: a fresh node with `position=(10, 20)` has that position, and its `init()` ran. Use a test node that records `init`.
- [ ] **Step 2: Run** the new file. Expect FAIL.
- [ ] **Step 3: Implement.** Afterwards, `grep -rn "_initial_position\|\"position\"" packages barn` should show only unrelated uses. These stay:
  - the keymap event payload: `ui/app/shell.py` ~:1228-1239 and `keymap_listener.py`;
  - the corner settings of `minimap.py` and `debug_overlay.py`;
  - the `position` fields of `SyncNodePositionEvent`, `NodeCreateRequestEvent` and the context-menu events;
  - `ui.notify(position=...)`.
- [ ] **Step 4: Run** `uv run pytest tests/core/ tests/studio/ tests/graph_editor/ tests/haystack/ -n 4 -q`. Expect PASS.
- [ ] **Step 5: Commit** `feat(graph): props are a node's only position; files no longer save "position"`.

### Task 4: The channel through the graph core

**Files:**
- Modify:
  - `node_wrapper.py` `move(new_x, new_y, channel: LayoutChannel = PATCH)`.
  - `base.py`:
    - `move_node(node_id, new_x, new_y, channel: LayoutChannel = PATCH) -> bool`;
    - `_check_canvas_size(channel: LayoutChannel = PATCH) -> bool`, which reads `getattr(props, channel.x/y)`;
    - `move_node` passes its channel to both.
  - `graph_actions.py`:
    - `MoveNodesToAction(graph, positions, channel: LayoutChannel = PATCH, description=None)` captures the originals through the channel.
    - `MoveNodesAction(...)` gains the same parameter and threads it to `move_node`; `can_merge` is False across channels.
  - `packages/haywire-core/src/haywire/core/graph/editor.py`: `move_nodes_to(positions, channel: LayoutChannel = PATCH)` and `move_nodes(nodes, deltaX, deltaY, channel: LayoutChannel = PATCH)`.
  - `packages/haywire-core/src/haywire/core/graph/types.py`: the `NODE_MOVED` docstring says the node moved in some channel, and that a canvas re-reads its own.
- Test: `tests/core/test_graph/test_layout_channel_moves.py` (new), using `SWAPPED` from Task 1 (define it in the test module).

**Interfaces — produces:** the signatures above. Task 5 calls `editor.move_nodes_to(positions, channel)`.

- [ ] **Step 1: Tests.**
  - `test_move_node_writes_the_channel_fields`: `graph.move_node(id, 10, 20, SWAPPED)` → `posY == 10` and `posX == 20`.
  - `test_move_nodes_to_undo_restores_the_channel_fields`: through `Editor.move_nodes_to(..., SWAPPED)`, then undo.
  - `test_move_nodes_actions_do_not_merge_across_channels`
  - `test_canvas_size_reads_the_channel`: a node with `posY = 9000` and `posX = 0`. Checked with `PATCH`, the height grows. Checked with `SWAPPED`, the width grows.
- [ ] **Step 2: Run.** Expect FAIL.
- [ ] **Step 3: Implement.**
- [ ] **Step 4: Run** `uv run pytest tests/core/ -n 4 -q`. Expect PASS.
- [ ] **Step 5: Commit** `feat(graph): moves and the canvas-size check take a layout channel`.

### Task 5: The channel through the canvas

**Files:**
- Modify, under `barn/haybale-graph-editor/haybale_graph_editor/editors/graph_canvas/`:
  - `graph_canvas_manager.py` `__init__` ~:112: `channel: LayoutChannel = PATCH`, stored as `self.channel` and passed to the handlers below.
  - `handlers/interaction.py`:
    - `InteractionHandlers(editor, session, channel=PATCH)`;
    - `process_drag_update` → `move_nodes_to(event.positions, self.channel)`;
    - `process_resize_end` writes `channel.size_adapt/width/height` through `set_property`, and its move goes through the channel.
  - `handlers/visual_layer.py`: `VisualLayerHandlers(..., channel=PATCH)`. Every layout read and write goes through the channel:
    - `on_validated` ~:152 and :166;
    - the chunked sync ~:303;
    - `resync_positions` ~:583;
    - `resync_size` ~:594;
    - `process_nodes_measured` ~:763-766;
    - the clone at ~:1005;
    - the `UINode` construction ~:528.
  - `ui_node.py`: `UINode(..., channel=PATCH)`. The slot-field subscription ~:276 and `_apply_slot_style` ~:412-420 use the channel's size fields. `node_theme` and `color_override` are not layout fields and stay as they are.
  - `barn/haybale-graph-editor/haybale_graph_editor/editors/graph_editor.py` ~:1021: no change needed (it uses the default). Leave a call site that passes `channel=PATCH` explicitly only if that matches how `_mount_level` passes its other arguments.
- Test: `tests/ui/test_canvas_handlers/test_interaction_handlers.py`, `test_resize_commit.py`, `test_visual_layer_handlers.py`, `tests/graph_editor/test_canvas_event_gating.py`.

**Interfaces — consumes:** Task 4's `move_nodes_to(positions, channel)`; `PATCH` and `LayoutChannel` (Task 1).

- [ ] **Step 1: Tests**, with `SWAPPED`:
  - `test_drag_update_moves_through_the_canvas_channel`: `move_nodes_to` is called with `(positions, SWAPPED)`.
  - `test_resize_writes_the_channel_size_fields`: the `set_property` calls name `"height"` for width, `"width"` for height, and `"size_adapt"`.
  - `test_node_moved_reads_the_canvas_channel`: `on_validated` with `NODE_MOVED` sends `update_node_position` the `(posY, posX)` pair.
  - `test_resync_positions_and_size_use_the_channel`
  - The existing `PATCH` tests stay unchanged and pass.
- [ ] **Step 2: Run** the four files. Expect FAIL.
- [ ] **Step 3: Implement.** Afterwards, grep the `graph_canvas/` directory for `props.posX`, `props.posY`, `props.width`, `props.height` and `props.size_adapt`. None remain outside the channel helpers.
- [ ] **Step 4: Run** `uv run pytest tests/ui/ tests/graph_editor/ -n 4 -q` and `uv run pytest -m browser -n 4 -q`. Expect PASS.
- [ ] **Step 5: Commit** `feat(graph-editor): a canvas lays nodes out through its layout channel`.

### Task 6: Docs

**Files:**
- Create: `docs/adr/0053-position-lives-in-props.md`. It records:
  - props are the single source;
  - the `"position"` key is dropped with no upgrader, why, and the `(0, 0)` consequence;
  - the `create_node_wrapper`/`AddNodeAction` `position` keyword and why it remains (the init-vs-restore split);
  - a rebuild carries over the position only;
  - the layout channel (`PATCH` now, `STAGE` in slice 5);
  - `NODE_MOVED` carries no channel.

  Match the format of `docs/adr/0052-instance-edit-by-detach-with-origin.md`.
- Modify:
  - `docs/reference/glossary.md`: add **Layout channel**. Where the glossary describes node position, say it lives in props `posX`/`posY`.
  - `packages/haywire-core/src/haywire/core/node/properties.py`, the stale comments:
    - ~:41-43: "fires on every drag tick" → drag positions are sent once, at drag end;
    - ~:140: "not shown in settings panels" → the node Properties panel shows them.
  - `docs/components/nodes/node-canon.md` ~:125, if its position sentence is now wrong.
  - The spec, `docs/superpowers/plans/2026-10-12-editor-modes.md`:
    - under "Traps", mark "Position lives in two places until slice 4" resolved by slice 4;
    - add a slice-5 trap: "`canvas_width/height` are the patch's; decide where the stage's extent lives before `move_node` runs with `STAGE`";
    - under "Stage", add Decision Q4 (z per view, the four verbs).
- Run:
  - `uv run haywire docs barn/haybale-graph-editor`, `uv run haywire docs barn/haybale-core` and `uv run haywire docs barn/haybale-studio`; commit whatever regenerates;
  - `uv run python scripts/bake_docs.py`;
  - `uv run mkdocs build --strict`.
- [ ] **Step 1: Edit the docs.**
- [ ] **Step 2: Commit first** (the docs test resets `barn/haybale-testing`). Then run the commands above and `uv run pytest tests/ -k "bake or docs" -n 4 -q`. Expect PASS.
- [ ] **Step 3: Commit** `docs: position lives in props; the layout channel (ADR 0053)`.

### Task 7: Full gate

- [ ] **Step 1:** `uv run ruff check . && uv run ruff format --check .`
- [ ] **Step 2:** the mypy command from CLAUDE.md.
- [ ] **Step 3:** `uv run pytest -m "not browser and not perf" -n 4 -q > <scratch>/t.log 2>&1; echo "exit=$?"`. Expect `exit=0`.
- [ ] **Step 4:** `uv run pytest -m browser -n 4 -q`. Expect PASS.
- [ ] **Step 5:** `uv run haywire` should load every tracked `.haywire` file under `graphs/` without errors, and each node should sit where it did. Spot-check by comparing each node's `posX`/`posY` before and after a load→save round trip, in a script run over `git ls-files '*.haywire' '*.hwm'`.
