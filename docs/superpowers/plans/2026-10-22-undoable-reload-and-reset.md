# Undoable Reload and Reset Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** A successful hot reload and a node Reset stay pristine — the node is rebuilt through `init()` — but each is one undo step: Undo puts the node back exactly as it was, Redo makes it pristine again.

**Architecture:** One action, `RebuildNodesAction`, holds each node's `serialize()["node_data"]` from before the rebuild. Undo asks the graph to rebuild each node from that data (`build(node_info)`, the load path); Redo asks for a plain rebuild (`init()`). Both requests go through the validation pass (`BaseGraph.request_node_rebuild`), so attached edges follow as they do for a reload. Reset runs the action through `Editor.add_action`. A reload is recorded after the fact: the validation pass captures each `NODE_HOT_RELOADED` node before rebuilding it and records the batch on the graph's history (`HistoryManager.record_executed`), which an `Editor` registers on its graph.

**Tech Stack:** Python, haywire core (`HistoryManager`, `BaseGraph`, validation pass, `NodeWrapper`), haybale-graph-editor (`VisualLayerHandlers`), pytest.

**Spec:** conversation 2026-10-22. User's idea: treat a successful hot reload like a node Reset whose undo restores the previous node. Decisions: Q1 a (one step per graph covering all its rebuilt nodes), Q2 a (Reset uses the same undoable action), and "a reload that breaks the class is NOT an undoable step". Check report: history lives on `Editor` (one per open graph; a Group's editor shares its host's history); the graph has no link to it; `HistoryManager._record_executed` exists privately; studio validation runs on the NiceGUI loop (main thread).

## Global Constraints

- The rebuild itself is unchanged: pristine, through `init()`, position kept (ADR 0053). No data is carried across it (see feedback: pristine over heuristic restore).
- **One step per graph per validation batch**, description `"Reload <Node label>"` when one class was reloaded, `"Reload <n> nodes"` otherwise; Reset: `"Reset <Node label>"` / `"Reset <n> nodes"`.
- **Not recorded:** a node whose rebuild ended as a stand-in (`is_stand_in`, ADR 0058) — the failed reload is not undoable; a node that absorbed its reload (`on_class_reloaded` → True; no rebuild happens); a class that fails to import (no rebuild); a graph with no history registered; a batch validated off the main thread (`threading.current_thread() is not threading.main_thread()`), logged at debug.
- **Recorded:** the reload that fixes a broken class (a stand-in becomes the real node). Its undo rebuilds from the stand-in's kept data, i.e. the configuration before the break, on the fixed class.
- Undo/Redo requests use `ChangeReason.NODE_RESET_REQUESTED`, so they are never themselves recorded and they mark the file unsaved like any edit.
- A recorded step is never merged and closes any running value-edit series (`_amendable = None`).

## Review Focus

1. **Undo of a reload, then the user keeps editing, then saves**: the file holds the restored (pre-reload) node; reopening shows it the same way (load path).
2. **Several quick saves of the class** (several reload batches): each is its own step; undoing all of them in order ends at the original node.
3. **Undo of a reload whose node was meanwhile deleted** (delete is a later step, so it is undone first) — and an undo whose node id no longer resolves fails without corrupting the history (the history manager's existing failure path).
4. **A reload while a Group's interior is open** (the interior editor shares the host's history): the step lands on the shared history; a Group whose interior was never opened has no editor on its definition graph, so its reload is not recorded — documented, not a bug.
5. **Reset below level mode edit**: refused, nothing recorded (the edit route returns no editor).

---

### Task 1: `RebuildNodesAction`, `request_node_rebuild`, undoable Reset

**Files:**
- Modify: `packages/haywire-core/src/haywire/core/undo/interfaces.py` (`IHistoryManager`), `history_manager.py`, `no_op_history_manager.py` — `record_executed(action) -> None`.
- Modify: `packages/haywire-core/src/haywire/core/graph/base.py` (beside `request_node_reset` :235) — `request_node_rebuild`.
- Modify: `packages/haywire-core/src/haywire/core/node/node_wrapper.py` — `_rebuild_data` slot, `take_rebuild_data()`.
- Modify: `packages/haywire-core/src/haywire/core/graph/validation.py:317` — a `NODE_RESET_REQUESTED` rebuild builds from `wrapper.take_rebuild_data()`.
- Modify: `packages/haywire-core/src/haywire/core/undo/actions/graph_actions.py` — `RebuildNodesAction`.
- Modify: `packages/haywire-core/src/haywire/core/graph/editor.py` — `reset_nodes(node_ids) -> bool`.
- Modify: `barn/haybale-graph-editor/haybale_graph_editor/editors/graph_canvas/handlers/visual_layer.py:1501-1505` — `ElementResetEvent` nodes go through `self.route.editor().reset_nodes(...)`; no editor (below edit) → nothing; edges keep `request_edge_reset`.
- Test: `tests/core/test_undo/test_rebuild_nodes_action.py` (new), `tests/ui/test_canvas_handlers/test_visual_layer_handlers.py` (extend).

**Interfaces:**
- Produces: `IHistoryManager.record_executed(action: IAction) -> None` — marks it executed and records it as `add_action` would after executing (ends the redo branch, no merge into a value run). `BaseGraph.request_node_rebuild(node_id: str, node_data: dict | None = None) -> None` — marks `NODE_RESET_REQUESTED`; with data the pass builds from it exactly, else through `init()`. `NodeWrapper.take_rebuild_data() -> dict | None` (returns and clears). `RebuildNodesAction(graph, before: dict[str, dict], description: str)` — `before` maps node id → `node_data`; `execute` = `request_node_rebuild(id)` for each; `undo` = `request_node_rebuild(id, before[id])` for each; raises `ValueError` on an id the graph no longer has. Classmethod `RebuildNodesAction.capture(graph, node_ids, description)` builds `before` from `serialize()`. `Editor.reset_nodes(node_ids: list[str]) -> bool`.

- [ ] **Step 1: Write the failing tests** (`graph_with_library_system`; `SettingsNode` / `TestPrintNode` keys from `class_identity.registry_key`; promotion via `Editor.promote_setting`, as in the reviewed probes):
  - `test_record_executed_adds_an_undoable_step_without_running_it` — a counting fake action: `record_executed` → execute count 0, `can_undo()`; `undo()` → undo count 1; `redo()` → execute count 1.
  - `test_a_reset_is_one_undoable_step` — value 7 + promotion on `example.example_int`, `message="kept"` on a print node; `editor.reset_nodes([a, b])` → both pristine; `editor.undo()` → value, promotion, promoted port and message back; `editor.redo()` → pristine; `history_manager.get_undo_description() == "Reset 2 nodes"` before the undo.
  - `test_undoing_a_reset_brings_an_edge_on_a_promoted_port_back_to_life` — edge into the promoted inlet; reset → edge not valid; undo → edge valid.
  - `test_rebuild_with_data_restores_exactly` — `request_node_rebuild(id, data)` + `force_immediate_validation` → `serialize()["node_data"] == data` (minus nothing).
  - `test_undo_of_a_rebuild_whose_node_is_gone_fails_cleanly` — record, remove the wrapper bypassing history, `undo()` returns False, `can_redo()` False.
  - visual layer: `test_a_reset_event_goes_through_the_editor` (route editor mock → `reset_nodes` called with the node ids, `graph.request_node_reset` not called) and `test_a_reset_below_edit_does_nothing` (`edit_route(editor, LevelMode.VIEW)` → neither called).
- [ ] **Step 2:** `uv run pytest tests/core/test_undo/test_rebuild_nodes_action.py tests/ui/test_canvas_handlers/test_visual_layer_handlers.py -q` — Expected: FAIL.
- [ ] **Step 3: Implement** per Interfaces. `record_executed`: `self._amendable = None; action.mark_executed(); self._record_executed(action, time.time())`. `RebuildNodesAction` is not mergeable (`merge` returns None / not overridden).
- [ ] **Step 4:** `uv run pytest tests/core/test_undo/ tests/core/test_graph/ tests/ui/test_canvas_handlers/ -q -n 4` — Expected: PASS.
- [ ] **Step 5: Commit** `feat(undo): Reset is one undoable step that restores the node exactly`.

### Task 2: A reload records its undo step

**Files:**
- Modify: `packages/haywire-core/src/haywire/core/graph/base.py` — `set_history(history: IHistoryManager | None) -> None`, `history` attribute (default `None`).
- Modify: `packages/haywire-core/src/haywire/core/graph/editor.py` — `__init__` calls `graph.set_history(self.history_manager)`.
- Modify: `packages/haywire-core/src/haywire/core/graph/validation.py` (rebuild branch :315-325, and before `_notify_subscribers` :413) — capture, filter, record.
- Test: `tests/core/test_node/test_reload_undo.py` (new).

**Interfaces:**
- Consumes: `RebuildNodesAction`, `record_executed` (Task 1).

- [ ] **Step 1: Write the failing tests.** Reload helper `_reload(graph, *wrappers)`: mark each `NODE_HOT_RELOADED`, then `force_immediate_validation()`. The one-batch tests build their graph with a scheduler that never fires on its own (a test-local `schedule()` returning a no-op handle), so several marks land in one batch; the rest may use `graph_with_library_system`.
  - `test_a_reload_records_one_step_for_the_graph` — two print nodes with messages, one editor; reload both in one batch → one step `"Reload <TestPrintNode label>"`; nodes pristine; `undo()` → messages back; `redo()` → pristine.
  - `test_each_graph_records_its_own_step` — two graphs, each with an editor and a node of the class; reloading both → each history has one step.
  - `test_a_failed_reload_records_nothing` — `construction_fails(1)` (conftest) → stand-in; `can_undo()` False.
  - `test_the_reload_that_fixes_a_class_undoes_to_the_setup_before_the_break` — message "kept"; failed reload (stand-in); fixed reload → pristine real node, one step; `undo()` → real node with `message == "kept"`.
  - `test_a_graph_without_an_editor_records_nothing` — bare graph, reload → no error, no history.
  - `test_a_reload_validated_off_the_main_thread_records_nothing` — run `force_immediate_validation` in a `threading.Thread`, join → `can_undo()` False, node pristine.
  - `test_undo_redo_requests_are_not_recorded` — after undo of a reload, the history holds exactly one step (redo-able), none added by the undo's own rebuild.
- [ ] **Step 2:** `uv run pytest tests/core/test_node/test_reload_undo.py -q` — Expected: FAIL.
- [ ] **Step 3: Implement.** In the rebuild branch, for `NODE_HOT_RELOADED` only and only when `self._graph.history is not None`: capture `wrapper.serialize()["node_data"]` (guarded: a failure skips that node) into a batch dict before `build`; after `build`, drop the node if `wrapper.is_stand_in`. After the loop, if the dict is non-empty and on the main thread, `history.record_executed(RebuildNodesAction(graph, captured, description))`. The label comes from the node class's `class_identity.label`.
- [ ] **Step 4:** `uv run pytest tests/core/ -q -n 4` — Expected: PASS.
- [ ] **Step 5: Commit** `feat(undo): a successful hot reload is one undoable step per graph`.

### Task 3: Docs

**Files:**
- Create: `docs/adr/0059-reload-and-reset-are-undoable.md` — context (a reload and a Reset discard what the user set; the rejected rehydrate approach, 2026-10-21, as "Considered"), decision (Global Constraints), consequences (Undo restores the pre-reload shape on new code, as an old file does; a Group's interior reload is recorded only once its interior editor exists; off-main-thread validation records nothing).
- Modify: `docs/components/nodes/node-canon.md` §5 — one paragraph: editing the class rebuilds placed nodes from `init()` (fresh, only the position kept); Undo (Ctrl+Z) in the graph brings each back exactly as it was, Redo makes it fresh again; Reset Node is undoable the same way. Hook table: `init(self)` row "created, reset or hot-reloaded — never on load".
- Modify: `docs/reference/glossary.md` — Undo section: **Rebuild step** row (the undo step a Reset or a successful hot reload records; Undo rebuilds the nodes from their data from before, Redo through `init()`).
- [ ] **Step 1:** write the docs.
- [ ] **Step 2:** full gate: ruff check, ruff format --check, mypy (CLAUDE.md list), `uv run pytest -m "not browser and not perf" -n 4`, `uv run pytest -m browser -n 4` — Expected: clean.
- [ ] **Step 3: Commit** `docs: ADR 0059, reload and Reset are undoable`.

### Task 4: Live check (user)

- [ ] Promote a setting, set values, grow a pin; save a harmless edit to the class → node fresh; Ctrl+Z in that graph → everything back; Ctrl+Shift+Z → fresh again.
- [ ] Two graphs with the class open → each undoes its own reload.
- [ ] Break the constructor → stand-in, nothing to undo for it; fix → Ctrl+Z gives the setup from before the break.
- [ ] Reset Node on a configured node → Ctrl+Z restores it.
