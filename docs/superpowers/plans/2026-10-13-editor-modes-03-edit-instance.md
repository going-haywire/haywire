# Editor modes, slice 3: Edit Instance — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Let an editor change one running macro placement in place. The placement becomes a *modified instance*, and three verbs send the changes back to a macro or discard them.

**Architecture:**
- **Detach stamps an origin.** `DetachPlacementFromMacroAction` already turns a placement into a Group as one undo step. It now also records an **origin** on the interior's `SubgraphDefinition`: the macro's registry key, and the template's `content_hash` at the moment of the detach. A Group with an origin is a *modified instance*, and its origin is saved with it.
- **Two entry points run the same detach.**
  - Unlocking the placement's own interior level asks first, then detaches and unlocks.
  - The menu row "Detach from Macro" becomes **Edit Instance**: it detaches and enters the new Group.
- **An open level follows a re-key.** The detach moves the same `SubgraphDefinition` object to a new key, so `_prune_dead_levels` finds the object under its new key and re-keys the level instead of closing it. Undo moves it back the same way.
- **The three verbs reuse the promote swap** (`Editor.promote_to_macro`, one undo step, writes no file):
  - **Revert to Macro** swaps the card to a placement of the origin macro.
  - **Update Macro…** does the same swap, then opens the origin `.hwm` in a macro tab loaded with the instance's contents and marked unsaved. The user saves it, and the reload updates every placement.
  - **Save new Macro…** is the existing Promote flow under its new name.

**Tech Stack:** Python 3.12, NiceGUI/Vue 3, pytest (`uv run pytest`), ruff, mypy.

**Spec:** [2026-10-12-editor-modes.md](2026-10-12-editor-modes.md), section "Macros: Enter, Edit Instance, and three verbs"; Sequence item 3. Decisions taken with the user on 2026-10-13 refine the spec; they are listed below and bind where they differ.

## Decisions (2026-10-13, user)

1. The origin lives on the interior's `SubgraphDefinition` and is saved as `"origin": {"key": …, "hash": …}`.
2. Only a **placement's own interior level** offers Edit Instance. A level deeper inside a placement (a nested Group, or a placement inside the interior) keeps the slice-2 refusal. To edit deeper, the user unlocks the outer placement first.
3. The menu row "Detach from Macro" is renamed **Edit Instance**: detach with origin, then enter the new Group.
4. **Update Macro…** turns the card back into a placement, as one undoable step. It then opens the `.hwm` in a macro tab with the instance's contents applied and unsaved; the user's Save is the write. It lives in `haybale-haystack`, next to Edit Macro…. It is greyed out, with a hint, while that macro has unsaved edits in its tab.
5. A modified-instance card carries no visual marker in this slice.

## Global Constraints

- **Labels:** `"Edit Instance"`, `"Update Macro…"`, `"Save new Macro…"`, `"Revert to Macro"`. "Promote to Macro…" disappears from the UI. The Promote flow's popup title becomes `"Save new Macro"`.
- **Unlock confirmation:**
  - `confirm_modal` with title `"Edit Instance"` and confirm label `"Edit Instance"`.
  - Message: `f"Edit this instance? It becomes a modified instance of {label} until you Update or Revert."`, where `label` is the template's `class_identity.label`, or the definition's label if the template is absent.
- **Lock-button tooltip on a placement's own level** (EDIT principal): `"Unlock to edit this instance"`. Deeper levels keep `"Locked: inside a macro placement"`, disabled.
- **Disabled-row hints:**
  - origin macro absent: `f"{label} is not installed."`
  - Update Macro… on a read-only install: the text `macro_edit_refusal` returns.
  - unsaved macro tab: `f"{label} has unsaved edits in its macro tab. Save them first."`
- **Tiers:** every verb, and the unlock, needs EDIT, enforced where the write lands. Update Macro… also needs an editable install (`macro_edit_refusal`).
- **The origin hash** is `MacroTemplate.content_hash` (sha256 of the `.hwm` text) at detach time.
- **ADR 0038 stays true:** a placement never saves its interior; a modified instance is a Group and saves like one.
- **Out of scope:** agent tools for these verbs, placement value overrides (slice 6), and a card marker.
- **Docs rules:** follow `.claude/rules/python-docs.md`. Glossary and ADR edits land in Task 7.
- **Commit trailer:** `Co-Authored-By: Claude Opus 5.5 (1M context) <noreply@anthropic.com>`.

## Review Focus

1. **Undo of Edit Instance while its level is open.** The level re-keys back to `macro_<id>` and is locked again, and the interior is the same live object, with no rebuild. Test in Task 2.
2. **A second session viewing the placement level when the first detaches.** Its level follows the re-key and stays locked. Test in Task 2.
3. **Update Macro… when a clean macro tab for that file is already open** (Edit Macro… entries stay in memory after their tab closes). The open document receives the instance's contents and turns unsaved, and its canvas shows them. Test in Task 6.
4. **Save new Macro… on a modified instance** writes a `.hwm` without the `origin` key. Test in Task 5.
5. **A saved and reloaded host file keeps the origin, and an origin whose macro is gone** leaves Revert and Update disabled with the "not installed" hint. Tests in Tasks 1 and 4.

---

### Task 1: The origin

**Files:**
- Create: `packages/haywire-core/src/haywire/core/macro/origin.py`
- Modify:
  - `packages/haywire-core/src/haywire/core/graph/subgraph.py`: attribute ~:99, `to_dict` ~:263, `load_from_dict` ~:270.
  - `packages/haywire-core/src/haywire/core/undo/actions/graph_actions.py`: `_AdoptTemplateInteriorAction` ~:1832, `DetachPlacementFromMacroAction` ~:1877.
  - `packages/haywire-core/src/haywire/core/macro/source.py`
  - `barn/haybale-graph-editor/haybale_graph_editor/panels/_gating.py`
- Test: `tests/core/test_macro/test_detach_placement.py` (reuse `macro_folder`, `_place`, `_detach`); new `tests/core/test_macro/test_macro_origin.py`.

**Interfaces — produces:**
- `MacroOrigin`: a frozen dataclass `(key: str, hash: str)` with `to_dict() -> dict[str, str]` and `@classmethod from_dict(data) -> MacroOrigin`.
- `SubgraphDefinition.origin: MacroOrigin | None = None`. It is written as `"origin"` in `to_dict` only when set, and read in `load_from_dict`.
- `_AdoptTemplateInteriorAction(..., origin: MacroOrigin | None)`. Execute sets `definition.origin`; undo restores the previous value.
- `DetachPlacementFromMacroAction` computes `MacroOrigin(card.registry_key, template.content_hash)` from the macro registry. The origin is `None` when the template is absent.
- `modified_instance_origin(node) -> MacroOrigin | None` in `core/macro/source.py`: the origin of a Graph-node card's definition.
- `_gating.is_modified_instance(ctx) -> bool`.

- [ ] **Step 1: Tests.**
  - `test_detach_records_the_origin`: `definition.origin == MacroOrigin("testlib:macro:Blur", registry.template(...).content_hash)`.
  - `test_undo_of_detach_clears_the_origin`.
  - `test_the_origin_survives_save_and_load`: `to_dict` → a fresh graph `load_from_dict` gives an equal origin.
  - `test_a_plain_group_has_no_origin_key`: `"origin" not in definition.to_dict()`.
  - `test_is_modified_instance_polls`: True for the detached card; False for a plain Group, a placement, and a plain node.
- [ ] **Step 2: Run** `uv run pytest tests/core/test_macro/ -q`. Expect FAIL.
- [ ] **Step 3: Implement.**
- [ ] **Step 4: Run** `uv run pytest tests/core/test_macro/ tests/core/test_graph/ -n 4 -q`. Expect PASS.
- [ ] **Step 5: Commit** `feat(macro): a detached placement records its origin`.

### Task 2: An open level follows a re-key

**Files:**
- Modify: `barn/haybale-graph-editor/haybale_graph_editor/editors/graph_editor.py`:
  - `_prune_dead_levels` ~:407;
  - a new `_rekey_level`, next to `_repoint_level` ~:450.
- Test: `tests/graph_editor/test_graph_editor_placement_levels.py` (`_open_placement`, `_placement_definition`, `_editor`).

**Interfaces:**
- Consumes: nothing from Task 1. The re-key is generic: the same definition object under a new key.
- Produces:
  - In `_prune_dead_levels`: when the level's key no longer resolves but `container.definition` sits in the host's `subgraphs` under another key, and its card is alive, call `_rekey_level(context, level, *, claim)` instead of closing.
  - `_rekey_level` moves the level and every descendant level to their new `level_key_for(...)` keys, keeping canvas, viewport and selection. It updates `_active_level` and recomputes `inside_placement`. It forces `locked=True` when the result is inside a placement, and otherwise keeps the level's lock. It re-renders the level bar.

- [ ] **Step 1: Tests.** Simulate the detach as the action does it: `host.subgraphs` pops the key, re-adds the same object under `"subgraph_new"`, and clears `template_key`.
  - `test_a_detached_placement_level_follows_the_new_key`: the active level becomes `"subgraph_new"`, its canvas manager `is` the old one, `_teardown_level` is not called, `inside_placement is False`, and `locked` is unchanged (`True`).
  - `test_undo_of_the_detach_follows_back_and_locks`: the key returns to `"macro_card_1"` and `template_key` is set again, so the level is `"macro_card_1"`, locked and `inside_placement`.
  - `test_descendant_levels_follow_the_re_key`: `"macro_card_1#sg_inner"` → `"subgraph_new#sg_inner"`.
  - `test_a_background_editor_follows_without_claiming`: called with `claim=False`, `_claim_session_state` is not called.
- [ ] **Step 2: Run** `uv run pytest tests/graph_editor/test_graph_editor_placement_levels.py -q`. Expect FAIL.
- [ ] **Step 3: Implement.**
- [ ] **Step 4: Run** `uv run pytest tests/graph_editor/ -n 4 -q`. Expect PASS.
- [ ] **Step 5: Commit** `feat(graph-editor): an open level follows its Subgraph to a new key`.

### Task 3: Edit Instance — unlock and menu row

**Files:**
- Modify: `graph_editor.py`:
  - module function `placement_root(container) -> bool`, next to `inside_placement` ~:108: True for a `SubgraphContainer` whose `definition.template_key` is set and whose host is not `inside_placement`;
  - `_on_toggle_lock` ~:620;
  - `_update_lock_button` ~:1162;
  - new `_edit_instance(context, level) -> bool`.
- Modify:
  - `panels/graph/menu/selection/selection.py` ~:736-775: `DetachFromMacroMenuPanel` → `EditInstanceMenuPanel`; label, row and tooltip become `"Edit Instance"`.
  - `editors/graph_canvas/handlers/visual_layer.py` ~:1034 `process_detach_from_macro`: after a successful detach and sync, publish `SubgraphNavigation` for the new card, as `process_enter_group` does.
  - The notify text becomes `"Editing this instance — Update Macro… or Revert to Macro when done"`.
- Test: `tests/graph_editor/test_graph_editor_placement_levels.py`; `tests/graph_editor/test_group_verbs.py`.

**Interfaces:**
- Consumes:
  - Task 1's origin stamping, through `Editor.detach_placement_from_macro`;
  - Task 2's re-key.
- Produces:
  - `_edit_instance` refuses (returns False) unless `context.can_edit()`. It detaches through `level.container.host.editor.detach_placement_from_macro(card.node_id, graph_node_key)`, where `card = definition.graph_node_wrapper()` and `graph_node_key = self._project_state.node_factory.get_graph_node().class_identity.registry_key`. It then calls `_prune_dead_levels(context)`, and `set_level_locked(context, <new key>, False)`.
  - `set_level_locked` still refuses every unlock on an `inside_placement` level. The confirm is the only route, and it detaches first.

- [ ] **Step 1: Tests.**
  - `test_unlocking_a_placement_root_asks_first`: `_on_toggle_lock` calls `confirm_modal` with the Global Constraints title, message and confirm label (patch `confirm_modal`). Nothing is detached before the confirm.
  - `test_confirming_edits_the_instance`: on a real placement (core `_place` + real `Editor`), invoking `on_confirm` leaves the active level on the new Group key, unlocked, with `definition.origin` set.
  - `test_a_level_deeper_in_a_placement_keeps_the_refusal`: a Group nested in the placement interior notifies `_PLACEMENT_REFUSAL`, and `confirm_modal` is not called.
  - `test_edit_instance_needs_edit`: an OPERATE context gets `"Unlocking needs edit access"` and no confirm.
  - `test_lock_button_on_a_placement_root`: enabled for EDIT, tooltip `"Unlock to edit this instance"`. On a deeper level it stays disabled with the placement tooltip.
  - `test_edit_instance_row`: the panel is labelled `"Edit Instance"` and polls on a placement only.
- [ ] **Step 2: Run** the two test files. Expect FAIL.
- [ ] **Step 3: Implement.** The `on_confirm` callback runs synchronously in the popup's click; follow `.insights/feedback_nicegui_async.md`.
- [ ] **Step 4: Run** `uv run pytest tests/graph_editor/ tests/core/test_macro/ -n 4 -q`. Expect PASS.
- [ ] **Step 5: Commit** `feat(graph-editor): Edit Instance — unlocking a placement detaches it with its origin`.

### Task 4: Revert to Macro

**Files:**
- Modify:
  - `panels/graph/menu/selection/selection.py`: a new `ModifiedInstanceMenuPanel` (`surface=SelectionMenu`, `label="Modified instance"`, `order=39`, `poll=is_modified_instance`), with a row `"Revert to Macro"` that calls `self.actions.revert_to_macro(node_id)`.
  - `surfaces/selection.py` `SelectionActions`;
  - `handlers/selection_toolbar.py` and `handlers/context_menu.py`: `revert_to_macro`, emitting `RevertToMacroEvent`;
  - `event_definitions.py`: `RevertToMacroEvent(node_id)`. Regenerate `generated/graph_events.js` with `uv run python -m haywire.ui.components.graph.generators`.
  - `visual_layer.py`: `process_revert_to_macro` with default EDIT access. It calls `self.editor.promote_to_macro(node_id, origin.key)`, then syncs, notifies `"Reverted to {label}"`, and selects the new card.
- Test: `tests/core/test_macro/test_detach_placement.py`; `tests/graph_editor/test_group_verbs.py`.

**Interfaces:**
- Consumes: `modified_instance_origin` and `is_modified_instance` (Task 1).
- Produces: `ModifiedInstanceMenuPanel` (order 39). Task 6's haystack panel takes order 40.

- [ ] **Step 1: Tests.**
  - `test_revert_makes_a_placement_of_the_current_template`: detach, change an interior value and add a node, then `promote_to_macro(card, origin.key)`. The new card `is_macro_placement`, and its interior matches the template.
  - `test_undo_of_revert_restores_the_modified_instance`: the origin and the added node are back.
  - `test_revert_row_disabled_when_the_macro_is_gone`: the registry returns no template, so the row is disabled with the hint `f"{label} is not installed."`.
  - `test_revert_row_shows_only_on_a_modified_instance`.
- [ ] **Step 2: Run.** Expect FAIL.
- [ ] **Step 3: Implement.**
- [ ] **Step 4: Run** `uv run pytest tests/graph_editor/ tests/core/test_macro/ tests/ui/ -n 4 -q`. Expect PASS.
- [ ] **Step 5: Commit** `feat(graph-editor): Revert to Macro`.

### Task 5: Save new Macro…

**Files:**
- Modify:
  - `packages/haywire-core/src/haywire/core/macro/promote.py` `plan_promotion`: drop `"origin"` from the document, as it drops `"key"`. Extract `macro_document(definition) -> dict` for Task 6.
  - `panels/graph/menu/selection/selection.py` ~:727: the row becomes `"Save new Macro…"`.
  - `_promote_flow/chrome.py:76`: the title becomes `"Save new Macro"`.
  - Rename docstrings and user-visible strings in `_promote_flow/` and `visual_layer.py` ~:932 from "Promote to Macro" to "Save new Macro". Keep module and class names.
  - `graph_actions.py:2101`: the description becomes `"Save new Macro"`.
- Test: `tests/core/test_macro/test_promote_plan.py`; `tests/graph_editor/test_promote_flow.py`; `tests/graph_editor/test_group_verbs.py`.

**Interfaces — produces:** `macro_document(definition: SubgraphDefinition) -> dict[str, Any]`, the `.hwm` document for a Group interior, without `key` or `origin`.

- [ ] **Step 1: Tests.**
  - `test_a_modified_instance_saves_without_its_origin`: `"origin" not in plan_promotion(...).document`.
  - `test_group_row_says_save_new_macro`.
- [ ] **Step 2: Run.** Expect FAIL.
- [ ] **Step 3: Implement.** Grep for `"Promote to Macro"` in non-doc sources afterwards; it should appear only in history-free identifiers.
- [ ] **Step 4: Run** `uv run pytest tests/core/test_macro/ tests/graph_editor/ -n 4 -q`. Expect PASS.
- [ ] **Step 5: Commit** `feat(macro): "Save new Macro…" replaces "Promote to Macro…"`.

### Task 6: Update Macro…

**Files:**
- Modify:
  - `packages/haywire-core/src/haywire/core/macro/source.py`: `count_placements(graphs: Iterable[BaseGraph], registry_key: str) -> tuple[int, int]` returns (placements, graphs holding at least one). It walks `node_wrappers` and every Subgraph recursively, placement interiors included.
  - `barn/haybale-haystack/haybale_haystack/state/haystack_state.py`: `open_macro_with(path: Path, document: dict) -> GraphEntry`, next to `open_macro` ~:301.
    - It raises `ValueError` if an entry for `path` has unsaved edits.
    - A clean existing entry gets `graph.load_from_dict(document)`, its history cleared, and `unsaved=True`; this broadcasts `GraphUnsavedChanged` and `GraphDataMutated`.
    - With no entry, it opens one loaded from `document` instead of the file, with `unsaved=True`.
    - A save writes `path`.
  - `barn/haybale-haystack/haybale_haystack/panels/graph/menu/macro.py`: `UpdateMacroMenuPanel` (`surface=SelectionMenu`, `order=40`, `poll=is_modified_instance`).
    - The row reads `"Update Macro…"`. It is disabled, with the Global Constraints hint, when the origin's template is absent, when `macro_edit_refusal` returns a reason, or when the entry for the template's path is `unsaved`.
    - On click, `_update_macro(ctx, node_id)`:
      1. Refuse unless `session_allows(ctx, AccessTier.EDIT)` (from `haybale_graph_editor.access`). Re-check the three disabled conditions too, since the row can be stale. Nothing has changed yet when it refuses.
      2. Build `document = macro_document(definition)`.
      3. Swap with the host `Editor.promote_to_macro(node_id, origin.key)`.
      4. Call `entry = hs.open_macro_with(path, document)` and publish `Reveal` as `_open_macro` does.
      5. Notify `f"Save {label} to update {n} placements in {m} open graphs."` If `origin.hash != template.content_hash`, add, as a warning: `f"{label} changed since this instance was made; saving replaces those changes."`
- Test: `tests/core/test_macro/test_macro_origin.py` (`count_placements`); new `tests/haystack/test_update_macro.py` (find the haystack test folder; reuse the `HaystackState` fixtures there).

**Interfaces — consumes:** `macro_document` (Task 5); `modified_instance_origin` and `is_modified_instance` (Task 1); `session_allows` (slice 1).

- [ ] **Step 1: Tests.**
  - `test_count_placements_spans_graphs_and_interiors`.
  - `test_open_macro_with_opens_unsaved_with_the_document`.
  - `test_open_macro_with_replaces_a_clean_open_entry`: same entry object, new content, unsaved, history empty.
  - `test_open_macro_with_refuses_an_unsaved_entry`.
  - `test_update_swaps_the_card_and_opens_the_document`: the card `is_macro_placement`, and the opened entry's graph holds the instance's added node.
  - `test_saving_the_opened_document_updates_the_placements`: drive `_save_entry`, then deliver the file change through the `_modified` helper pattern from `test_macro_reload.py`. A second placement in another graph shows the change.
  - `test_update_row_disabled_while_the_macro_tab_is_unsaved`, with the hint text.
  - `test_update_row_disabled_on_a_read_only_install`.
- [ ] **Step 2: Run.** Expect FAIL.
- [ ] **Step 3: Implement.**
- [ ] **Step 4: Run** `uv run pytest tests/core/test_macro/ tests/haystack/ tests/graph_editor/ -n 4 -q` (adjust the haystack path to the real one). Expect PASS.
- [ ] **Step 5: Commit** `feat(haystack): Update Macro… sends a modified instance back to its macro`.

### Task 7: Docs

**Files:**
- Create: `docs/adr/0052-instance-edit-by-detach-with-origin.md`. It amends ADR 0038 and records:
  - the origin;
  - the two entry points;
  - placement-root-only unlocking;
  - the three verbs as swaps;
  - Update Macro… writing through the macro tab's Save;
  - undo restoring the card but leaving files untouched.

  Wire it into the ADR index/nav per `docs/reference/doc-authoring.md`. Add a short amendment note to ADR 0038 pointing to 0052.
- Modify: `docs/reference/glossary.md`.
  - Add **Modified instance**, **Origin**, **Edit Instance**, **Update Macro…**, **Revert to Macro**.
  - Rename the **Promote to Macro** row to **Save new Macro…** and list "Promote to Macro" under aliases to avoid.
  - Fold **Detach from Macro** into Edit Instance.
  - Lock row: a placement's own level unlocks through Edit Instance.
- Modify: `docs/guides/security.md` lock paragraph (~:486): Edit Instance needs edit.
- Run:
  - `uv run haywire docs barn/haybale-graph-editor` and `uv run haywire docs barn/haybale-haystack`; commit the regenerated pages;
  - `uv run python scripts/bake_docs.py`;
  - `uv run mkdocs build --strict`.

- [ ] **Step 1: Edit the docs.**
- [ ] **Step 2: Run** the commands above and `uv run pytest tests/ -k "bake or docs" -n 4 -q`. Expect PASS.
- [ ] **Step 3: Commit** `docs: Edit Instance, the origin and the three macro verbs (ADR 0052)`.

### Task 8: Full gate

- [ ] **Step 1:** `uv run ruff check . && uv run ruff format --check .`
- [ ] **Step 2:** the CLAUDE.md mypy command.
- [ ] **Step 3:** `uv run pytest -m "not browser and not perf" -n 4 -q > /tmp/t.log 2>&1; echo "exit=$?"`. Expect `exit=0`.
- [ ] **Step 4:** `uv run pytest -m browser -n 4 -q`. Expect PASS.
