# Open follow-ups — backlog

What is still open after the editor-modes slices and the follow-up batches of 2026-10-20 to 2026-10-22 (save key and active slot bar, quick wins, bugs 5–10, the first branch's deferred minors). Everything else from those plans has landed on master; the plans themselves were removed with this file's commit. ADRs 0051–0059 record the decisions.

This is a backlog, not an executable plan: each item names what is wrong, where, and a suggested first step. Pick one, settle it with the user, then write a plan for it.

Line references are from 2026-10-22. ✓ = confirmed in code; anything else comes from notes and may be stale.

---

## 1. Features and UX gaps

1. **DONE** ~~**Undo cannot restore an edge's propagation to `None`.**~~ Obsolete premise: `None` means the wire type allows no mode, and the setter refuses every such edge, so no step is ever recorded from `None`. The unreachable guard in `_undo_impl` was replaced by an assert; a test pins the refusal (`test_an_edge_without_propagation_refuses_a_mode_and_records_nothing`).
2. **No undo-history panel.** The two-session undo case (two sessions on one file) cannot be checked live without seeing the stack. Needs a design round: where the panel lives, what an entry shows (description, group, fence), whether it is per graph or per file history (Group interiors share their host's history, ADR 0059).
3. **A Farmhand tool run outside the MCP host gets no closing fence.** No such caller exists yet; record it where a non-MCP caller is added.
4. **An Inset on a node that is not a Graph-node shows the "Enter" placeholder.** The skin should refuse, or the skin lists should not offer it there (they already filter by the `graph-node` tag — check how the user reached it).
5. **Tooltips with a separate trigger (config row, fold triangle) do not respond in view mode;** readable pins keep their crosshair below edit. Part of the level-mode pointer gate (`.insights/project_level_mode_pointer_gate.md`): the trigger needs `data-hw-readable`.
6. **Live reconfigure of a widget** (changing a widget's config while it is drawn) was left for a later design round.

## 2. Performance

7. **The Inset host card is rebuilt in full on every visual change inside it,** patch moves included. Narrow it to stage changes (edge-only interior batches already skip it). Note: every rebuild also releases its widgets, which no longer leaks since `bb40afd5`.
8. **The first restack writes N−1 nodes** (stacking order, slice 5c).
9. **Drawing large graphs.** The 512-node load went from 23 s to ~12 s (Firefox 52 s → 11 s) on 2026-10-20; the Vue full-tree render walk remains (`.insights/project_nicegui_component_vs_native_tag.md`). Handoff: `internals/handoff/draw_performance_regression_fix.md` — check whether its `_claim_session_state` regression is cleared by `_clear_selection` publishing only when something was selected.

## 3. Polish

10. **On stage, two cards with equal z can come back in a different order after a remount** (DOM order vs graph order).
11. **Restack compares with `is`.**
12. **In patch, the selected-card lift outranks the dragging lift.**
13. **Slice 5b-4 leftovers:** a `storage_key` collision in `widget_instances`; the guard misses `bag.x =`; a Group's mirrored ports drop `operable`; Farmhand's not-operable message; hard-coded 12 px padding.
14. **DONE** ~~**Relative `..` imports** in `barn/haybale-graph-editor/haybale_graph_editor/skins/node_skin.py:19` and `inset_skin.py`.~~ Widened to all of `barn/`: 266 import statements made absolute, ruff `TID252` (`ban-relative-imports = "all"`) enforced on `barn/**`; reasons in `.insights/feedback_no_relative_imports_in_barn.md`. `packages/` still uses relative imports. `haybale-visiongraph` (separate repo) not converted.
15. **Edit-instance polish** (`internals/handoff/edit-instance-followups.md` §3): `Editor.last_promotion_dropped_edges` is a last-call field (return it from `promote_to_macro` once a second caller needs it); optional notice in a second session whose placement level became a modified instance.

## 4. Test gaps

16. **No browser tests** for dragging the Inset body, its menu, or double-click to Enter.
17. **No split-pane browser test.**
18. **The 5c rebuild test is weak.**
19. **Edit-instance test gaps** (`internals/handoff/edit-instance-followups.md` §4): redo of a detach; `drop_unmatched_edges` keeping an edge whose pin exists; the background-session rekey test bypasses `_prune_dead_levels`; `TestEditInstanceRow` reuses `TestEnterRow()` helpers; the Clone-to-Library ordering test reads `ctx.data[next(iter(ctx.data))]`.

## 5. Deferred minors from the 2026-10-20 → 22 branches

Ctrl+S and core fixes:

20. **DONE** ~~`in_text_fields` also overrides the `[data-hw-native-keys]` opt-out in `keymap_listener.vue` (nothing uses the attribute yet).~~ The opt-out is absolute; browser test `test_save_stays_with_a_native_keys_element`.
21. ✓ `HaystackState.open_macro_with`: if `load_from_file` raises (file deleted since opening), the entry is left emptied; `macro.py` catches it, so the UI is safe.
22. No core end-to-end test that an edge validates on a pin added after the first validation (the macro integration test covers the reported case).

Active slot bar:

23. ✓ Expanding a collapsed ACTION/CONTEXT slot from its rail does not activate it (no editor visible at pointer-down).
24. **DONE** ~~Tab-bar overflow arrows keep `--hw-bg-surface` on a lit bar (`shell.py`, `.q-tabs__arrow`); use `inherit`.~~ Background dropped: with `outside-arrows` they overlap nothing and show the bar's own background, resting or lit. Not checked live yet.
25. **DONE** ~~`STATIC_CSS`'s attribute docstring sits under `ACTIVE_SLOT_CSS` in `shell.py`; reorder.~~ Replaced by a comment block above `STATIC_CSS` (a docstring after its 490-line body would be unreadable).
26. ✓ Ctrl+S in Component Source overwrites during a "file changed on disk" conflict (the header button does the same).
27. ✓ The bare-border guard (`tests/ui/test_slot_bars.py`) scans only `editors/*.py` and `ui/app`, single-line `.classes(` calls.
28. **DONE** ~~`hui.slot_header(icon=…, is_dirty=…)` without a title silently drops both.~~ Icon and dot now draw without a title; test in `tests/ui/test_slot_bars.py`.

Error-node stand-in (ADR 0058):

29. **DONE** ~~`NodeWrapper.build()`, `_instantiate` and `set_props` docstrings still describe the pre-stand-in behaviour.~~
30. **DONE** ~~`_stand_in_data` aliases the caller's `node_info` dict; deep-copy once on capture.~~ Was live, not latent: the loader passes its own dict through (tests failed before the fix). Deep-copied on capture; two tests in `test_stand_in.py`.
31. **DONE** ~~A stand-in ignores `serialize(include_data=False)`, so a template save writes its port values.~~ The kept ports drop `field_data` without `include_data`; test in `test_stand_in.py`.
32. The graph-editor stand-in tests use an unknown-key stand-in only, not a constructor failure.
33. No tests for break → fix with an edge attached, or relabel → fix (review probes passed).
34. **DONE** ~~Farmhand's node state row lacks `is_stand_in`.~~ State row carries `is_stand_in`; `inspect_node`'s summary names the node's own key (was the ErrorNode's) and flags a stand-in. Open question split off as #45.
35. A Graph-node or Macro stand-in pasted while broken carries no Subgraph (the clipboard reads `wrapper.node.subgraph_key`); once fixed it would share its Subgraph with the original. Same pattern as an unknown-key Graph-node.

Undoable reload and Reset (ADR 0059):

36. **DONE** ~~A reload of an already fresh node still records a step; compare the data before and after and drop equal ones.~~ Equal nodes dropped from the batch; ADR 0059's "Not recorded" list updated. Reset of an untouched node still records a step (explicit command, left as is).
37. **DONE** ~~`docs/components/nodes/node-canon.md` says the user's setup "is not lost" unconditionally; qualify "in an open graph" (no editor, a never-opened Group interior, a node absorbing its own reload).~~
38. **DONE** ~~`BaseGraph.request_node_reset` has no production callers left.~~ Removed (a non-undoable public Reset); tests use `request_node_rebuild(node_id)`.
39. Missing tests: a Group interior on the shared history, several reload batches in a row, save and reopen after an undone reload, the `on_class_reloaded` absorb path.

## 6. Other open handoffs

Each has its own note in `internals/handoff/`:

40. `graph-loop-benchmark-drift.md` — `graph_loop` ~8% slower between June and September 2026, not attributed.
41. `install-writeback-breaks-the-dev-repo.md` — a marketplace install over an editable install silently replaces it.
42. `node-busy-highlight-from-is-executing.md` — a busy highlight while a worker runs (`NodeWrapper.is_executing` is never assigned).
43. `popup-overlay-should-stop-capturing.md` — a `backdrop_click_close` Popup intercepts outside clicks.
44. `startup-main-thread-block.md` — the browser main thread is blocked ~800 ms after a large load.

## 7. Found while working the backlog

45. **A port or setting edit on a stand-in is lost at the next save,** silently — a stand-in saves its kept data and takes only props from the live card. Applies to the canvas and to Farmhand's `set_property`/`operate` alike. Decide: refuse such writes, write them into the kept data, or leave it to the STAND-IN note (`inspect_node`).
46. **A hot reload in a graph without a history loses the user's setup silently** (a never-opened Group interior, mainly). Handoff: `internals/handoff/reload-without-history-loses-setup.md`. **On hold** until #47 has landed.
47. **Errors on the main editing and running pathways do not reach the error ledger** systematically; convert to `HaywireException` at a short list of central boundaries (`Editor._apply`, validation loops, signal dispatch, a global UI hook, Farmhand runner, load/save). Needs a design round and an ADR. Handoff: `internals/handoff/haywire-exception-at-boundaries.md`.
