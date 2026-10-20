---
name: edit-instance-followups
description: Handoff — what editor-modes slice 3 (Edit Instance) left open: a latent core bug where a node's structural-dirty flag sticks under an inline validation scheduler, Update Macro… error paths, and small polish and test gaps
metadata:
  type: project
  status: open
---

# Handoff — Edit Instance follow-ups

**Status:** §1, §2 and the pluralisation item in §3 are done (2026-10-20, branch `fix/save-key-and-core-fixes`); the rest of §3 and §4 are open.

**Original status:** not started. Slice 3 is merged into `feat/editor-modes-slice1` (`3d1506f9`) and was checked live in the studio on 2026-10-14. These items came out of its reviews. None of them blocks slice 4, and none shows up in normal studio use.

**Context:** [ADR 0052](../../docs/adr/0052-instance-edit-by-detach-with-origin.md); plan `docs/superpowers/plans/2026-10-13-editor-modes-03-edit-instance.md`.

The items are in priority order. Verify each line reference before trusting it, because they are from 2026-10-14.

## 1. A node's structural-dirty flag sticks under an inline scheduler (core bug) — DONE

Fixed: the flag is set before `mark_node_dirty` and cleared again if it raises; `test_update_macro.py` runs on a plain `SyncScheduler` again.

**Where:** `NodeWrapper.mark_as_structuraly_dirty`, `packages/haywire-core/src/haywire/core/node/node_wrapper.py:611-623`.

**Mechanism:** the method calls `self._graph._validation.mark_node_dirty(...)` first and sets `self._is_dirty_structural = True` after it. With a scheduler that validates inline, the validation pass runs inside `mark_node_dirty` and clears the flag. The flag is then set to `True` after the pass, and nothing clears it again. Every later call is skipped by the `not self._is_dirty_structural` guard, so the node is never re-checked structurally. The edges on its pins are never re-checked either. Inline schedulers are `SyncScheduler`, and `LoopScheduler` when no event loop is running.

**Why the studio does not show it:** studio graphs run on `LoopScheduler` with a running loop, so the pass is debounced and runs after the flag is set.

**Where it can bite:** graphs built with `SyncScheduler()` outside tests:
- `packages/haywire-studio/src/haywire_studio/packaging/docs/extract.py:154`, docs extraction;
- `barn/haybale-studio/haybale_studio/farmhands/catalog.py:264`, Farmhand "describe";
- `barn/haybale-studio/haybale_studio/farmhands/authoring.py:367`, Farmhand "verify";
- `packages/haywire-core/src/haywire/barn/builtin/nodes/macro_node.py:145` passes one into a placement's interior. `add_subgraph` should force the host's scheduler there (see `.insights/project_subgraph_scheduler_deadlock.md`); confirm that it does.

Any test that builds a graph on `SyncScheduler` is also exposed. A pin added after the first validation stays unchecked there.

**Suggested fix:** set `_is_dirty_structural = True` before calling `mark_node_dirty`, inside the same lock. Check what clears the flag in the validation pass, and make sure a pass that raises does not leave it set.

**How it was found:** `tests/haystack/test_update_macro.py::test_an_added_wired_pin_is_connected_after_the_save` failed with an inline scheduler. It now uses a `_ParkedScheduler` that holds the pass back, as the studio does. After the fix, that test should also pass on a plain `SyncScheduler`.

**Verify with:**
1. A unit test on a `SyncScheduler` graph: add a pin after the first validation, then assert that an edge to it validates.
2. The test above, switched to `SyncScheduler`.
3. The full gate: `uv run pytest -m "not browser and not perf" -n 4`.

The change is in core validation, so run the whole suite, not one area.

## 2. Update Macro… error paths (haystack) — DONE

Fixed: a failed load raises and leaves the macro as its file has it; an error after the swap is reported with "Undo restores the instance" (the swap stands, user ruling Q1 a).

1. **A failed load leaves an empty tab marked unsaved.** In `HaystackState.open_macro_with` (`barn/haybale-haystack/haybale_haystack/state/haystack_state.py:315`), the `load_from_dict(document)` calls at ~:336 and ~:359 return a `bool` that is ignored. On `False`, the tab is left emptied or half loaded with `unsaved = True`, and a Save would write it over the macro.
   - **Fix:** check the result and raise before touching `unsaved`.
2. **An error after the swap is not handled.** `_update_macro` (`barn/haybale-haystack/haybale_haystack/panels/graph/menu/macro.py:~236-243`) swaps the card first and calls `open_macro_with` second. If that call raises (a stale unsaved entry, or an error from `prehydrate`), the user is left with a swapped card, no tab and an unhandled exception. Undo restores the card.
   - **Fix:** catch the error and notify the user that the card was turned back into a placement and the macro can be opened with Edit Macro…. The alternative is to undo the swap; decide which the user should see.
   - **Test:** make `open_macro_with` raise after a successful swap.

## 3. Polish

- **Revert notification shows a raw key.** `process_revert_to_macro` (`barn/haybale-graph-editor/haybale_graph_editor/editors/graph_canvas/handlers/visual_layer.py:~1092-1094`) looks up the label after the swap and falls back to `origin.key`. Compute `origin_label(definition)` before the swap.
- **Pluralisation.** DONE ("1 placement in 1 open graph"). "Save {label} to update {n} placements in {m} open graphs." reads "1 placements in 1 open graphs". The plan specified the wording, so pluralise it without changing it otherwise.
- **`Editor.last_promotion_dropped_edges`** reports the count from the last call, a pattern `Editor` has nowhere else. Leave it unless a second caller needs the count; then return it from `promote_to_macro`.
- **Optional:** a notification in a second session whose open placement level was turned into a modified instance by another session. Its level follows and keeps its own lock, and the only visible change is the lock tooltip. Decided 2026-10-14 that this works as planned, so the notification is optional.

## 4. Test gaps

- Redo of a detach re-applies the origin: not tested. `_AdoptTemplateInteriorAction` re-captures the previous value on execute, so redo should work.
- `drop_unmatched_edges=True` keeping an edge whose pin exists: not tested. The `_revert` helper in `tests/core/test_macro/test_detach_placement.py` does not pass the flag that the real Revert passes.
- `tests/graph_editor/test_graph_editor_placement_levels.py`: the background-session test calls `_rekey_level(claim=False)` directly. It does not go through `_prune_dead_levels` with `_holds_session()` false.
- `tests/graph_editor/test_group_verbs.py`: `TestEditInstanceRow` creates `TestEnterRow()` to reuse its helpers. Move them to module functions.
- The Clone-to-Library row ordering test reads the edit state through `ctx.data[next(iter(ctx.data))]`, which breaks if another state is added first.

## Out of scope

The settings-promotion feature still says "Promote to" and "Promote setting". It is a separate feature from the macro verbs, and it was left alone on purpose.
