# Session Lifetime and Large-Graph Load Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** A websocket drop no longer destroys a studio session. Opening a large graph shows it filling in batch by batch, inside the viewport, and loads faster.

**Architecture:** Session teardown moves from NiceGUI's `app.on_disconnect`, which runs on every websocket drop, to `app.on_delete`, which runs once the client is discarded. The chunked load does four things:
- mounts a fixed batch of nodes per yield;
- holds every edge back until the nodes are mounted, then sends them once;
- fits the viewport at the start to a bounding box the server computes from saved positions;
- shows its progress over an undimmed canvas.

The selection clear that runs while a graph opens publishes `SelectionMoved` only when something was actually selected.

**Tech Stack:** Python 3.12, NiceGUI 3.13.0 (Vue 3, Quasar), pytest + anyio, Playwright harness `.scratch/draw-perf/`.

**Spec:** this conversation's rulings, 2026-10-20 (no separate spec file).
- **Item 1, session teardown on every websocket drop:** Q1–Q4 are still waiting for the user's confirmation. The recommended options are Q1 (a), Q2 (a), Q3 (a) now and (b) in Task 7, and Q4.
- **Drawing:** D1 (a), D2 (a), D3 (a), D4 (a), D5 (a). These are confirmed.

## Global Constraints

- Work on branch `fix/session-lifetime-and-large-graph-load`, created off `master` (`b7cbee64`).
- Tests use only files under `tests/` or `barn/haybale-testing`. They never use repo `graphs/` files.
- Docstrings and comments follow `.claude/rules/python-docs.md`: present tense, no history, no "NOT X".
- Pick the smallest pytest tier for each task. The gate is run once, at the end: `uv run pytest -m "not browser and not perf" -n 4` and `uv run pytest -m browser -n 4`.
- The perf metric is the 512-node graph `graphs/10x512n_5x448e.haywire`, timed with `.scratch/draw-perf/bis.sh <sha>`.
  - Metric A runs from the click to all nodes and edges drawn.
  - The baseline is about 22 s at `83a65e8f`. Task 0 re-measures it on `b7cbee64`.
  - This is a manual harness, not a test, so reading `graphs/` here is allowed.
- Constants (D3): `CHUNKED_LOAD_BATCH = 25` (nodes per yield) and `_FIT_CARD_SIZE = (200.0, 100.0)`. The second matches `pan.vue`'s fallback card size.

## Review Focus

1. **A page reload must not leave two live sessions forever.** The old session dies 60 s later through `on_delete`. Task 1's test drives `on_client_deleted` directly.
2. **An edge added or removed during a chunked load must still end up correct.** The final pass reads the graph's current edges. Task 3 tests both an add and a remove made while the load is mounting.
3. **A canvas re-mount (`CanvasMountedEvent`) during a load must not resend the edges early.** After the load it must still resend them. Task 3 covers both.
4. **The first fit on a hidden canvas (0×0) must do nothing.** Otherwise the canvas is misplaced, the way `centerOn` guards against. Task 5 adds the same guard to `fitToRect`.
5. **A load cancelled mid-batch leaves no edges sent and no "mounting" flag stuck.** Task 3 adds a test that the flag clears on cancellation.

---

### Task 0: Baseline

**Files:** none modified, except the commit of the already-done fixture move.

- [ ] **Step 1:** Create the branch: `git switch -c fix/session-lifetime-and-large-graph-load`.
- [ ] **Step 2:** Commit the prehydration fixture move. It is already in the working tree: `tests/core/test_graph/fixtures/prehydration/*` and `tests/core/test_graph/test_prehydration.py`.
  `git commit -m "test(prehydration): freeze the format fixtures under tests/"`.
  Do not stage the user's own changes to `graphs/`, `haystacks/`, `docs/components/nodes/node-canon.md` or `.claude/settings.local.json`.
- [ ] **Step 3:** Run the lint baseline on the files the plan touches:
  `uv run ruff check packages/haywire-studio/src/haywire_studio/app.py barn/haybale-graph-editor/haybale_graph_editor/editors packages/haywire-core/src/haywire/ui/components/zoom`.
  Then run `uv run mypy` on the same paths. Expected: clean. If not, stop and raise it with the user.
- [ ] **Step 4:** Run `.scratch/draw-perf/bis.sh b7cbee64` and record metric A in the ledger. Stop any studio on port 8191 first.

### Task 1: The session ends when the client is deleted (item 1)

**Blocked until the user confirms Q1–Q4.** The tasks after this one do not depend on it.

**Files:**
- Modify: `packages/haywire-studio/src/haywire_studio/app.py:59-72` and `:142-164`
- Modify: `tests/studio/test_app/test_disconnect_flow.py` (rename to `test_client_lifecycle.py`)
- Modify: `tests/core/test_session/test_session.py:5`, `packages/haywire-core/src/haywire/core/session/session.py:82`, `tests/ui/harness/routes.py:494,513` (stub renamed)
- Modify: `.insights/feedback_nicegui_async.md`, adding one paragraph. Extend the matching line in `CLAUDE.md`'s trap list by one clause.

**Interfaces:**
- Produces: `HaywireApp.on_client_deleted(client) -> None`, which replaces `on_disconnect`. Also `HaywireApp._register_lifecycle() -> None`, which `__init__` calls. It registers `app.on_delete(self.on_client_deleted)`, `app.on_shutdown(self.on_app_shutdown)` and `app.on_startup(self._wire_store_broadcasts)`, and no `on_disconnect`.

- [ ] **Step 1: Write the failing tests.** In `test_client_lifecycle.py`:
  - Keep the four existing tests, retargeted to `on_client_deleted`, same assertions: cleanup comes before `remove_session`; with no shell, the session is still removed; an unmapped client is a no-op; nothing happens during shutdown.
  - Add `test_the_session_is_bound_to_client_deletion`: patch `haywire_studio.app.app` with a `MagicMock` and call `HaywireApp._register_lifecycle(app_under_test)`. Assert `fake.on_delete.assert_called_once_with(app_under_test.on_client_deleted)` and `fake.on_disconnect.assert_not_called()`.
  - Add `test_deletion_broadcasts_presence`: after `on_client_deleted`, assert `signal_dispatcher.broadcast` was called once with a `PresenceChanged` instance.
- [ ] **Step 2:** Run `uv run pytest tests/studio/test_app/test_client_lifecycle.py -v`. Expected: FAIL, because `on_client_deleted` and `_register_lifecycle` don't exist.
- [ ] **Step 3: Implement.** Rename `on_disconnect` to `on_client_deleted`; the body is unchanged. Add `_register_lifecycle` and call it from `__init__` in place of the three `app.on_*` lines.
  - Docstring: "Tear down the shell and session of a discarded page: a tab closed or reloaded, and not reconnected within ``reconnect_timeout``."
  - Comment: `# on_delete, not on_disconnect: NiceGUI runs disconnect handlers on every websocket drop, also one the page reconnects from.`
  - Update the `_client_to_session` comment (`:59-61`) and the comment at `:319`.
- [ ] **Step 4:** Update the stale references:
  - the docstring at `session.py:82`;
  - `test_session.py:5`;
  - the harness stub `on_disconnect` → `on_client_deleted` and its docstring at `routes.py:494`. Nothing reads `app_state.on_disconnect`; confirm with `grep -rn "\.on_disconnect\b" packages barn tests`.
- [ ] **Step 5:** Write the insight. Add one paragraph to `.insights/feedback_nicegui_async.md`: `app.on_disconnect` and `client.on_disconnect` run on every websocket drop, and the client survives a drop. A page's teardown belongs on `on_delete`, which runs after `reconnect_timeout` with no reconnect. In the `CLAUDE.md` trap list, extend that file's existing entry with "; page/session teardown belongs on `on_delete` — `on_disconnect` fires on every ws drop". Do not add a new entry.
- [ ] **Step 6:** Run `uv run pytest tests/studio/test_app/ tests/core/test_session/ -q`. Expected: PASS.
- [ ] **Step 7:** Commit: `fix(studio): a websocket drop no longer ends the session`.

### Task 2: Clearing an empty selection publishes nothing (D5)

**Files:**
- Modify: `barn/haybale-graph-editor/haybale_graph_editor/editors/graph_editor.py:462-470` (`_clear_selection`)
- Test: `tests/graph_editor/test_graph_editor_levels.py` (new class `TestClearSelection`)

**Interfaces:** the `_clear_selection(context)` signature is unchanged.

- [ ] **Step 1: Write the failing tests.**
  - `test_clearing_an_empty_selection_publishes_nothing`: a context with a fresh `EditState()` (no active node or edge, empty sets, `context.active_component = None`). Call `GraphEditor._clear_selection(context)` and assert `context.session.publish` was not called.
  - `test_clearing_a_selection_publishes_once`: the same, with `selected_nodes = {"n1"}`. Assert exactly one `SelectionMoved` was published and `selected_nodes == set()`.
  - `test_an_active_component_alone_counts_as_a_selection`: `context.active_component = object()`. Assert one publish.
- [ ] **Step 2:** Run `uv run pytest tests/graph_editor/test_graph_editor_levels.py -k ClearSelection -v`. Expected: the first test FAILS.
- [ ] **Step 3: Implement.** In `_clear_selection`, publish only when at least one of these was set before the reset: `active_node`, `active_edge`, a non-empty `selected_nodes` or `selected_edges`, or `context.active_component`. The fields are still reset either way.
- [ ] **Step 4:** Run `uv run pytest tests/graph_editor/ -q`. Expected: PASS. The level and placement-level tests from `edd6ee50` must stay green, because they pin that a locked-level selection does not survive a switch.
- [ ] **Step 5:** Commit: `perf(graph-editor): clearing an empty selection publishes nothing`.
- [ ] **Step 6: Measure.** Run `.scratch/draw-perf/bis.sh <this sha>` and record metric A against Task 0. If it does not move, add a temporary counter of `SelectionMoved` publishes during one load (handoff step 1) and record the count. Do not try a second fix without asking the user. Then mark `internals/handoff/draw_performance_regression_fix.md` `status: done`, or say in the handoff what the count showed.

### Task 3: Edges wait for the nodes (D2)

**Files:**
- Modify: `barn/haybale-graph-editor/haybale_graph_editor/editors/graph_canvas/handlers/visual_layer.py`: `__init__`, `on_validated` (`:231-249`), `resync_edges` (`:362-375`), `sync_with_graph_chunked` (`:377-455`)
- Modify: `packages/haywire-core/src/haywire/ui/components/graph/canvas.vue:3170-3176` (the `console.error` on missing pins)
- Modify: `barn/haybale-graph-editor/haybale_graph_editor/editors/graph_canvas/graph_load_modal.py`, module docstring lines 4-8
- Test: `tests/ui/test_canvas_handlers/test_visual_layer_chunked_sync.py`

**Interfaces:**
- Produces: `VisualLayerHandlers.mounting: bool`, True only while `sync_with_graph_chunked` is mounting nodes. While it is True, `on_validated` registers no added edges and `resync_edges` sends nothing.

- [ ] **Step 1: Write the failing tests.**
  - Replace `TestTheValidationTimerBeatsTheLoop` with `TestEdgesWaitForTheNodes`:
    - `test_a_validation_pass_during_the_mount_sends_no_edges`: set `handler.mounting = True`, call `on_validated(handler._full_add_result(include_nodes=False))` with 2 edges, and assert no `SyncAllEdgesEvent` and `handler.edge_states == {}`.
    - `test_a_canvas_mount_during_the_load_sends_no_edges`: with `mounting = True`, `process_canvas_mounted(CanvasMountedEvent())` emits no `SyncAllEdgesEvent`.
    - `test_the_load_sends_every_edge_once_after_the_last_node`:
      - use `on_progress` to record the emit count while mounting;
      - assert that no `SyncAllEdgesEvent` was emitted before the last node;
      - assert exactly one batch with all 4 edges afterwards.
    - `test_an_edge_added_mid_load_is_in_the_final_batch` and `test_an_edge_removed_mid_load_is_not_sent`: mutate `graph.edge_wrappers` from `on_progress` at node 2.
    - `test_mounting_clears_after_success_and_after_cancellation`: reuse the cancellation pattern from `test_cancellation_stops_the_load`.
  - Keep `TestCanvasMounted` as it is. It runs with `mounting` False.
- [ ] **Step 2:** Run `uv run pytest tests/ui/test_canvas_handlers/test_visual_layer_chunked_sync.py -v`. Expected: the new tests FAIL.
- [ ] **Step 3: Implement.**
  - `self.mounting = False` in `__init__`.
  - In `sync_with_graph_chunked`, set it True before the loop and False in a `finally` around the loop. Clear it before the closing `on_validated(...)` call, so that call sends the batch.
  - `on_validated`'s `EDGE_ADDED` branch skips the edge while `self.mounting`. Leave the removal branch as is, since an unsent edge has no state.
  - `resync_edges` returns at once while `self.mounting`.
  - Rewrite the `sync_with_graph_chunked` docstring paragraph about the validation timer: the edges go out in one batch after the last node, and a validation pass or canvas mount during the load sends none.
  - Fix the `_await_client_drawn` docstring bullet "The batch has usually gone out ALREADY…", which is no longer true.
- [ ] **Step 4:** In `canvas.vue`, replace the `console.error('🔗 Vue could not find pins:', …)` with nothing. A missing pin is the normal parked case, and the caller parks the edge. Fix `graph_load_modal.py`'s docstring so it matches the new order.
- [ ] **Step 5:** Run `uv run pytest tests/ui/test_canvas_handlers/ -q`. Expected: PASS.
- [ ] **Step 6:** Commit: `perf(canvas): a large graph's edges go out once, after its nodes`.

### Task 4: Mount in batches (D3)

**Files:**
- Modify: `visual_layer.py`: a module constant and the loop in `sync_with_graph_chunked`
- Test: `test_visual_layer_chunked_sync.py`

**Interfaces:**
- Produces: `CHUNKED_LOAD_BATCH: int = 25` in `visual_layer.py`.
- `on_progress` is now called once per batch, with the running count. The callback's signature is unchanged.

- [ ] **Step 1: Write the failing test.** In `test_yields_between_batches`, which replaces `test_yields_between_nodes`:
  - `monkeypatch.setattr(visual_layer, "CHUNKED_LOAD_BATCH", 2)` over the 5-node fixture.
  - The competitor task records `len(handler.mounted)` at each tick.
  - Assert the set of recorded counts is a subset of `{2, 4, 5}` and contains `2` and `4`.
  - Also assert that `on_progress` was called with `[(2, 5), (4, 5), (5, 5)]`.
- [ ] **Step 2:** Run the file. Expected: FAIL, because the competitor sees 1 and 3.
- [ ] **Step 3: Implement.** Yield (`await asyncio.sleep(0)`) and call `on_progress` after every `CHUNKED_LOAD_BATCH` nodes and after the last node. Read the constant through the module at call time, so the test's patch takes effect. Comment on the constant: `#: Nodes mounted per event-loop yield. Each yield costs the browser one full page re-render.`
  - Update the docstring's "a node at a time" wording, and the test module's docstring bullet "it yields between nodes".
- [ ] **Step 4:** Run `uv run pytest tests/ui/test_canvas_handlers/ -q`. Expected: PASS.
- [ ] **Step 5:** Commit: `perf(canvas): a large graph mounts in batches of 25 nodes`.
- [ ] **Step 6:** Run `bis.sh <sha>` and record metric A. Try a batch of 50 too, as a scratch edit with no commit, and keep whichever is faster. Record both numbers in the ledger.

### Task 5: Fit the viewport before the nodes arrive (D1)

**Files:**
- Modify: `packages/haywire-core/src/haywire/ui/components/zoom/pan.py`: add `fit_to_rect`
- Modify: `packages/haywire-core/src/haywire/ui/components/zoom/pan.vue:736-792`
  - split the fit maths out of `_doFitToContent` into `_fitRect(minX, minY, maxX, maxY)`;
  - add `fitToRect(minX, minY, maxX, maxY)`, which returns early when the container measures 0×0;
  - `_doFitToContent` calls `_fitRect`.
- Modify: `visual_layer.py`: add `content_bounds`
- Modify: `barn/haybale-graph-editor/haybale_graph_editor/editors/graph_editor.py:1201-1203`
- Test: `tests/ui/test_canvas_handlers/test_visual_layer_chunked_sync.py` (bounds); `tests/graph_editor/test_graph_editor_levels.py` or the nearest `_build_canvas` test (wiring); a browser test in `tests/ui/harness/` (the vue guard)

**Interfaces:**
- Produces:
  - `ZoomPanContainer.fit_to_rect(min_x: float, min_y: float, max_x: float, max_y: float) -> None`, in content (canvas) coordinates;
  - `VisualLayerHandlers.content_bounds() -> Optional[tuple[float, float, float, float]]`, which returns `(min_x, min_y, max_x, max_y)` over the included nodes' `_canvas_position` plus `_FIT_CARD_SIZE`, or `None` when there are none.

- [ ] **Step 1: Write the failing tests.**
  - `test_content_bounds_span_every_included_node`: nodes at (10,20) and (500,300). Expect `(10, 20, 700, 400)`.
  - `test_content_bounds_of_an_empty_canvas_is_none`.
  - Wiring test: with `node_count >= CHUNKED_LOAD_THRESHOLD` and no saved viewport, calling `zoom_container._on_ready()` calls `fit_to_rect(*content_bounds())`, and `on_nodes_mounted` is still `center_on_content`.
  - Browser test: `fitToRect` on a canvas inside a hidden tab panel leaves zoom and pan unchanged.
- [ ] **Step 2:** Run them. Expected: FAIL.
- [ ] **Step 3: Implement.**
  - `fit_to_rect` does `self.run_method("fitToRect", min_x, min_y, max_x, max_y)`.
  - `_fitRect` keeps the existing `PADDING = 80`, the zoom clamp and `_clampPanValues()`.
  - In `_build_canvas`, change only the chunked branch: when `node_count >= CHUNKED_LOAD_THRESHOLD` and `bounds := manager.visual_layer.content_bounds()`, set `_on_ready = lambda: zoom_container.fit_to_rect(*bounds)`. The small-graph and saved-viewport branches stay as they are.
- [ ] **Step 4:** Run `uv run pytest tests/ui/test_canvas_handlers/ tests/graph_editor/ -q` and the new browser test. Expected: PASS.
- [ ] **Step 5:** Commit: `feat(canvas): a large graph opens with the viewport already over it`.

### Task 6: The load overlay stops dimming the canvas (D4)

**Files:**
- Modify: `graph_load_modal.py:graph_load_modal()`: `Popup(..., backdrop_color="transparent")`
- Test: `tests/ui/test_canvas_handlers/test_graph_load_modal.py`

- [ ] **Step 1: Write the failing test.** `test_the_overlay_does_not_dim_the_canvas`: assert the popup's `_props["backdrop-color"] == "transparent"`. Check the prop key in `popup.py:__init__`. Keep the existing tests that pin blocking: `closable=False` and no backdrop click-close. A centred popup's backdrop keeps `pointer-events: auto` (`popup.vue:121-131`), so input stays blocked.
- [ ] **Step 2:** Run it. Expected: FAIL.
- [ ] **Step 3:** Implement. In the module docstring, say the backdrop is transparent and still swallows input. Fix the stale "the canvas tops out at 1002" against `design-guide.md`.
- [ ] **Step 4:** Run `uv run pytest tests/ui/test_canvas_handlers/test_graph_load_modal.py -q`. Expected: PASS.
- [ ] **Step 5:** Commit: `feat(canvas): the graph-load overlay leaves the canvas visible`.

### Task 7: Measure, gate, live check, and reconnect timeout (Q3 b)

- [ ] **Step 1:** Run `bis.sh <head sha>` and record metric A against Task 0. Also record the longest gap between messages from the browser during the load, using the same method as `d82bb64f`.
- [ ] **Step 2: Q3 (b), only if the user confirmed it.** If the longest gap is now under 5 s, lower `reconnect_timeout` in `app.py:405` to 15.0. Update its comment to name the measured gap. Otherwise leave it at 60 and note why in the ledger.
- [ ] **Step 3:** Run the full gate: both pytest commands, `uv run ruff check .`, `uv run ruff format --check .`, and the mypy command from `CLAUDE.md`. Expected: all clean.
- [ ] **Step 4: Live check by the user** (in a studio started from this branch):
  1. Open the 512-node graph. The viewport sits over the whole graph from the start, the cards appear in visible batches under a progress card that doesn't dim the canvas, and the edges appear once at the end.
  2. While it loads, clicks on the canvas do nothing.
  3. Open a small graph (< 30 nodes). It behaves as before.
  4. Toggle the network off and on in devtools (or stop and restart Wi-Fi) for 5 s. Selection, panels, presence and editing all keep working, and the session has not changed.
  5. Close the tab. The user leaves the presence list within about 60 s, or within the new timeout.
  6. Reload the tab. The new page works. The old session leaves presence after the timeout.
- [ ] **Step 5:** Update the memory and the handoff status, then report the metric A numbers per task.
