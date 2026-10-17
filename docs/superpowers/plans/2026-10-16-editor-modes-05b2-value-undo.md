
# Editor modes, slice 5b-2: undo for values — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Value edits made in level mode `edit` become undo steps; consecutive writes to the same field by the same session amend one step until another action, another field or a 3 s idle gap ends the run; a multi-node form edit is one step.

**Architecture:**
- **Core actions** report whether they changed anything and carry a merge key; a value step can absorb a newer write of the same key (`amend_from`).
- **`HistoryManager.add_value_action`** is the one new history path: it drops no-op writes and amends the newest step (pending tail, else the history tip) when key, redo state and idle time allow. The generic 100 ms merge and 500 ms grouping stay as they are for every other action.
- **`Editor` and `EditRoute`** record in level mode `edit` with the route as the session token, and gain set/reset verbs for a whole multi-node form.
- **Save adds a fence**; the selection toolbar's Lock button writes through the route.

**Tech Stack:** Python 3.12, NiceGUI/Vue 3, pytest (`uv run pytest`), ruff, mypy.

**Spec:** [2026-10-16-edit-route.md](2026-10-16-edit-route.md), section "Undo", sequence item 2 ("5b-2, undo for values"), traps "The undo merge needs a new path" and "The history is shared across sessions". Design decisions Q1–Q8 of the 2026-10-16 5b-2 inquisition are listed below.

## Global Constraints

- **Branch:** work on `feat/editor-modes-slice5b2` in worktree `.worktrees/editor-modes-slice5b2`, cut from `feat/editor-modes-slice1`. It merges into `feat/editor-modes-slice1` after the live check; nothing goes to master.
- **Breaking changes are allowed.** No compatibility shims.
- **Recording rule:** a route write is recorded only when the route's level mode is `edit`. In `operate` it is written, marks unsaved, and adds a fence after it (a no-op adds nothing, see below).
- **`VALUE_EDIT_MERGE_IDLE_S = 3.0`**, a module-top constant in `packages/haywire-core/src/haywire/core/undo/actions/graph_actions.py`. Idle is measured from the step's last write, with `time.monotonic()`.
- **A merge run ends at:** any other step on the history (any action, another field, another session), a fence (an unrecorded write, a canvas gesture, a Farmhand call, a save), an undo (something is redoable), or the idle gap.
- **No-op rule:** a write that leaves what the field stores unchanged (`(is_locally_set, value)` for a setting, the own value for a port) adds no step, no fence and no mark, does not clear the redo branch, and does not touch a merge run.
- **The `.insights/project_undo_merge_executed_state.md` contract holds:** an amended step stays the executed action it already was; never execute it again to apply an amend.
- **Not in this slice:** per-session undo (the history stays shared by every session on the graph), level mode replacing `allows` (5b-3), skin widgets (5b-4), access defaults (5b-5), the `None`-propagation undo gap.
- **Docs rules:** follow `.claude/rules/python-docs.md`. ADR, glossary and insight edits land in Task 6, with the code.
- **Pre-edit baseline** (CLAUDE.md), before Task 1: `uv run ruff check packages/haywire-core/src barn/haybale-graph-editor barn/haybale-haystack` and the CLAUDE.md mypy command. It must be clean; if not, stop and ask.
- **Tests:** smallest tier while iterating (`uv run pytest <file>`). Commit before any full-suite run (`tests/studio/test_docs/test_generate.py` reverts uncommitted edits under `barn/haybale-testing`). Use `-n 4`. Core undo tests run with `enable_action_merging=True` and default grouping unless a test says otherwise — 5b-1's dropped-undo bug hid behind tests that turned merging off.
- **Commit trailer:** end every commit message with `Co-Authored-By: Claude Opus 5.5 (1M context) <noreply@anthropic.com>`.

## Decisions (inquisition Q1–Q8, plus this plan's)

1. **(Q1) A dedicated amend path for value steps**, not a generalized `HistoryManager` merge and not widget begin/end gestures.
2. **(Q2) The `EditRoute` object is the session token** in the merge key. Each Farmhand call builds its own route, so agent writes never merge across calls.
3. **(Q3) Value writes still enter through the pending/grouping path.** The amend candidate is the pending tail if anything is pending, else `history[-1]`; if that is an `ActionGroup`, its last action. Farmhand's one-step-per-call contract is kept.
4. **(Q4) A multi-node form edit is one `SetSettingsAction`/`ResetSettingsAction`** (a `CompositeAction` of per-bag setting actions), made by new `route.set_settings`/`route.reset_settings`; a drag on the form amends every child.
5. **(Q5) No-ops add nothing** (rule above). A run that returns to its start value keeps its step.
6. **(Q6) Saving adds a fence** to the saved graph's history.
7. **(Q7) The selection toolbar's Lock button writes `props.locked` through the route.**
8. **(plan) Resets never amend and are never amended.** A reset is one discrete step; a set after it starts a new run.
9. **(plan) Only route writes carry a merge key.** `Editor` verbs called without `merge_owner` (Farmhand `set_property`, the resize commit) record with key `None`, which never amends and is never amended; they still obey the no-op rule.

## Review Focus

1. **A slider drag longer than 500 ms.** The grouping window flushes the step to the history mid-drag; later ticks must amend the history tip, so the drag is still one step. Test: Task 2, `test_a_run_amends_the_history_tip_after_the_pending_flush`.
2. **Undo in the middle of a run, then keep dragging.** The undone step must not be amended; the new write clears the redo branch and starts a new step. Test: Task 2, `test_a_write_after_undo_starts_a_new_step`.
3. **Two sessions dragging the same field, interleaved.** Their writes never merge, and each undo step restores one session's change. Test: Task 4, `test_two_routes_never_merge`.
4. **A locked-level (`operate`) tweak between two `edit` writes within 3 s.** The fence it adds splits the run into two steps. Test: Task 4, `test_an_operate_write_between_edit_writes_splits_the_run`.
5. **A click that sets a value to what it already is, just after an undo.** Nothing is recorded and Redo stays available. Test: Task 2, `test_a_no_op_keeps_the_redo_branch`.

---

### Task 1: Value steps — change reporting, merge keys and amending

**Files:**
- Modify: `packages/haywire-core/src/haywire/core/undo/actions/graph_actions.py` (`SetPropertyAction` ~:1093, `_SettingWriteAction` ~:1213, `SetSettingAction`, `ResetSettingAction`; new `SetSettingsAction`, `ResetSettingsAction`; `VALUE_EDIT_MERGE_IDLE_S` at the top)
- Test: `tests/core/test_undo/test_value_steps.py` (new)

**Interfaces:**
- Produces:
  - `VALUE_EDIT_MERGE_IDLE_S: float = 3.0`.
  - On `SetPropertyAction`, `_SettingWriteAction` (so `SetSettingAction`, `ResetSettingAction`), `SetSettingsAction`, `ResetSettingsAction`:
    - `changed: bool` — set by every execute and undo: whether what the field(s) store changed.
    - `merge_key: Hashable | None = None` — assigned by `HistoryManager.add_value_action`.
    - `last_write: float` — `time.monotonic()` of the latest write the step stands for; set on execute and by `amend_from`.
    - `value_key() -> Hashable | None` — what the write addresses: `("port", node_id, name)` for `SetPropertyAction`, `("setting", owner, name)` for `SetSettingAction`, `("settings", frozenset(owners), name)` for `SetSettingsAction`, `None` for both reset actions (never amend).
    - `amend_from(newer) -> None` — adopt `newer`'s new value and `last_write`; keep this step's old value(s). Only valid when `self.merge_key == newer.merge_key`; never executes anything.
  - `SetSettingsAction(graph, owners: Sequence[SettingOwner], name: str, value: Any)` and `ResetSettingsAction(graph, owners: Sequence[SettingOwner], name: str)`: `CompositeAction`s of one `SetSettingAction`/`ResetSettingAction` per owner; `changed` is true when any child changed; `amend_from` sets every child's new value.

- [ ] **Step 1: Write the tests** in `test_value_steps.py`, on a held graph, executing the actions directly (no `HistoryManager`):
  - `test_a_write_reports_change`: `SetSettingAction` to a new value → `changed is True`; again to the same value → `changed is False`.
  - `test_a_port_write_reports_change`: same for `SetPropertyAction` on a port's own value.
  - `test_amend_keeps_the_first_old_value`: execute A (2→5), execute B (5→8), `A.amend_from(B)`; `A.undo()` restores 2; `A.execute()` (redo) gives 8.
  - `test_amend_restores_unset_on_undo`: field unset, A sets 5, B sets 8, amend, undo → `_is_locally_set` is `False`.
  - `test_value_keys`: the three keys above; resets give `None`; two `SetSettingAction`s on the same owner and name have equal keys.
  - `test_a_form_step_writes_every_bag_and_undoes_each`: `SetSettingsAction` over 3 node owners whose old values differ (one unset); undo restores each node's own old value, unset included; `changed` true; all three nodes marked (`NODE_VALUE_CHANGED`).
  - `test_a_form_step_amends_every_child`: two `SetSettingsAction`s, amend, undo → every bag back to its own first old value.
- [ ] **Step 2: Run** `uv run pytest tests/core/test_undo/test_value_steps.py` — fails (missing attributes/classes).
- [ ] **Step 3: Implement** the interfaces above. `changed` reuses the existing change checks (`value_changed`, `_stored_changed`) the actions already compute for marking. Do not override `can_merge`/`merge`.
- [ ] **Step 4: Run** the new file plus `tests/core/test_undo/` — all pass.
- [ ] **Step 5: Commit** `feat(undo): value steps report change, carry a merge key and can be amended`.

### Task 2: `HistoryManager.add_value_action`

**Files:**
- Modify: `packages/haywire-core/src/haywire/core/undo/history_manager.py`
- Test: `tests/core/test_undo/test_value_history.py` (new)

**Interfaces:**
- Consumes: Task 1's `changed`, `merge_key`, `value_key()`, `last_write`, `amend_from`, `VALUE_EDIT_MERGE_IDLE_S`.
- Produces: `HistoryManager.add_value_action(action: IAction, merge_owner: object | None, idle_s: float = VALUE_EDIT_MERGE_IDLE_S) -> bool`:
  1. Execute `action`; on exception log and return `False` (as `add_action`).
  2. If `not action.changed`: clean it up, return `True` — no step, redo branch untouched.
  3. Key = `None` if `merge_owner is None` or `action.value_key() is None`, else `(action.value_key(), merge_owner)`; assign `action.merge_key`.
  4. Candidate = `_pending_actions[-1]` if pending, else `history[-1]` when nothing is redoable and it is not a `Fence`; an `ActionGroup` candidate means its last action.
  5. Amend when key is not `None`, `candidate.merge_key == key`, and `time.monotonic() - candidate.last_write < idle_s`: `candidate.amend_from(action)`, `action.cleanup()`, return `True`.
  6. Otherwise behave exactly as `add_action` after its execute (clear redo, append to pending, flush rules, limits).

- [ ] **Step 1: Write the tests** with a `HistoryManager(UndoConfig())` (merging and grouping on) and real `SetSettingAction`s on a held graph:
  - `test_same_key_amends_into_one_step`: 3 writes 2→5→8→9 with one merge owner → one undo restores 2; nothing left to undo from them.
  - `test_a_run_amends_the_history_tip_after_the_pending_flush` (Review Focus 1): write, force the flush (`_flush_pending_actions()`), write again → still one step.
  - `test_another_field_starts_a_new_step`, `test_another_owner_object_starts_a_new_step`.
  - `test_idle_gap_starts_a_new_step`: age the tip (`last_write -= 4.0`), write → two steps.
  - `test_a_fence_ends_the_run`: write, `add_fence()`, write → two steps.
  - `test_a_write_after_undo_starts_a_new_step` (Review Focus 2): write 2→5, undo, write 2→7 → one step (2→7); redo branch gone.
  - `test_a_no_op_keeps_the_redo_branch` (Review Focus 5): write, undo, write the current value → `can_redo()` still `True`, history unchanged.
  - `test_a_none_owner_never_amends`: two writes with `merge_owner=None` inside one grouping window → both actions stay, grouped as one `ActionGroup` by the existing 500 ms rule; one undo restores 2.
  - `test_resets_never_amend`: set, reset, set (same owner) → three actions.
  - `test_amend_into_a_flushed_group_tail`: pending `[AddNodeAction-like PlainAction, SetSettingAction]` flushed as a group, then a same-key write → amends the group's last action.
- [ ] **Step 2: Run** — fails (no `add_value_action`).
- [ ] **Step 3: Implement** `add_value_action` as specified; factor the shared "after execute" part of `add_action` into a private helper rather than copying it.
- [ ] **Step 4: Run** the new file and `tests/core/test_undo/` — all pass.
- [ ] **Step 5: Commit** `feat(undo): value steps amend the newest step within a merge run`.

### Task 3: `Editor` records value steps and fans out form edits

**Files:**
- Modify: `packages/haywire-core/src/haywire/core/graph/editor.py` (`set_property`, `set_setting`, `reset_setting`, `_apply` ~:254-337; new `set_settings`, `reset_settings`)
- Test: `tests/core/test_graph/test_editor_value_steps.py` (new); update `tests/core/test_undo/test_set_property_action.py`, `tests/core/test_undo/test_value_actions.py` where they assert today's fence/no-op behaviour

**Interfaces:**
- Consumes: Task 1 actions, Task 2 `add_value_action`.
- Produces:
  - `set_property(node_id, name, value, prefer_setting=False, *, record=True, merge_owner: object | None = None) -> bool`
  - `set_setting(owner, name, value, *, record=True, merge_owner=None) -> bool`
  - `reset_setting(owner, name, *, record=True, merge_owner=None) -> bool`
  - `set_settings(owners: Sequence[SettingOwner], name: str, value: Any, *, record=True, merge_owner=None) -> bool`
  - `reset_settings(owners: Sequence[SettingOwner], name: str, *, record=True, merge_owner=None) -> bool`
  - Value verbs: `record=True` → `history_manager.add_value_action(action, merge_owner)`; `record=False` → execute, then `add_fence()` only if `action.changed`. `False` if the action raised.
  - Structure verbs (`reorder_ports`, `set_edge_propagation`, …) unchanged.

- [ ] **Step 1: Write the tests:**
  - `test_a_recorded_write_is_one_undo_step` and `test_recorded_writes_with_one_owner_amend`.
  - `test_an_unrecorded_no_op_adds_no_fence`: `history` unchanged after `record=False` of the current value.
  - `test_an_unrecorded_change_still_fences` (5b-1 behaviour kept).
  - `test_a_recorded_no_op_adds_no_step`: `set_property(..., record=True)` of the current value → `can_undo()` is `False` (closes 5b-1's deferred ruling).
  - `test_set_settings_is_one_step_over_every_owner` and `test_reset_settings_is_one_step`.
- [ ] **Step 2: Run** — fails.
- [ ] **Step 3: Implement.** Split `_apply` into a value path and the existing structure path; keep the debug/info log choice from 5b-1.
- [ ] **Step 4: Run** the new file, `tests/core/`, `tests/farmhand/` — pass. Farmhand `set_metadata`'s two fields remain one undo step (existing test).
- [ ] **Step 5: Commit** `feat(graph): Editor records value steps and writes a multi-node form as one step`.

### Task 4: The route records in level mode `edit`; forms write through `set_settings`

**Files:**
- Modify: `packages/haywire-core/src/haywire/core/graph/edit_route.py`; `barn/haybale-graph-editor/haybale_graph_editor/panels/_selection_forms.py` (`fan_out_to` ~:148)
- Test: `tests/core/test_graph/test_edit_route.py`; `tests/graph_editor/test_selection_forms.py` (or the file holding `fan_out_to` tests — grep)

**Interfaces:**
- Consumes: Task 3 verbs.
- Produces:
  - Every route value write passes `record=(self._mode() is LevelMode.EDIT)` and `merge_owner=self`.
  - `EditRoute.set_settings(bags: Sequence[Settings], name, value, *, minimum) -> bool` and `EditRoute.reset_settings(bags, name, *, minimum) -> bool`: mode check; bags the document saves go to one `editor.set_settings`/`reset_settings`; bags it doesn't save are written directly (as `set_setting` does today). `False` if refused or any bag lacks `name`.
  - `fan_out_to` calls `route.set_settings(bags, …)` / `route.reset_settings(bags, …)` once per edit instead of looping.
  - Class docstring: replace "Value writes are not recorded as undo steps." with the recording rule and the run's end conditions, in one or two sentences.

- [ ] **Step 1: Write the tests:**
  - `test_edit_mode_records_and_operate_does_not`.
  - `test_two_routes_never_merge` (Review Focus 3): routes A and B over one `Editor`, both `EDIT`, interleaved writes A,B,A to one field → three steps; undo restores in reverse, each to the value before that write.
  - `test_an_operate_write_between_edit_writes_splits_the_run` (Review Focus 4): route E (`EDIT`) writes 2→5, route O (`OPERATE`) writes 6, E writes 7 → two recorded steps; undo once → 6; undo again → 2.
  - `test_a_form_edit_is_one_undo_step`: `fan_out_to` over 3 node bags, one change → one undo restores all three; a second change of the same field within 3 s amends it.
- [ ] **Step 2: Run** — fails.
- [ ] **Step 3: Implement.**
- [ ] **Step 4: Run** the touched test files, `tests/graph_editor/`, `tests/ui/panel/` — pass.
- [ ] **Step 5: Commit** `feat(graph): the route records value edits in level mode edit`.

### Task 5: Save ends a run; the toolbar Lock button takes the route

**Files:**
- Modify: `barn/haybale-haystack/haybale_haystack/state/haystack_state.py` (`_save_entry` ~:385, where it clears `entry.unsaved`); `barn/haybale-graph-editor/haybale_graph_editor/panels/graph/toolbar/selection.py` (`_toggle` ~:136)
- Test: `tests/haystack/` (the file testing `_save_entry` — grep), `tests/graph_editor/` (the toolbar test file — grep, or new `test_selection_toolbar_lock.py`)

**Interfaces:**
- Consumes: `route_for(ctx)` (`haybale_graph_editor.state.graph_app_state`), `EditRoute.set_setting`.
- Produces:
  - A successful save calls `entry.editor.add_fence()` once the file is written.
  - The Lock button writes `route.set_setting(bag, "locked", now, minimum=LevelMode.EDIT)`; with no route or a refused write it leaves the icon and tooltip as they were.

- [ ] **Step 1: Write the tests:**
  - `test_saving_ends_the_merge_run`: route write 2→5, save, write 8 → two undo steps; first undo → 5.
  - `test_a_failed_save_adds_no_fence` (untitled entry with no path).
  - `test_the_lock_button_marks_unsaved_and_undoes`: click → `props.locked` true, graph unsaved, one undo restores false.
  - `test_the_lock_button_without_edit_changes_nothing`: `OPERATE` route → nothing written, icon unchanged.
- [ ] **Step 2: Run** — fails.
- [ ] **Step 3: Implement.**
- [ ] **Step 4: Run** the touched files and `tests/haystack/` — pass.
- [ ] **Step 5: Commit** `feat(graph-editor): saving ends a merge run; the Lock button is an undoable edit`.

### Task 6: Docs, insight and gate

**Files:**
- Modify: `docs/adr/0055-every-user-edit-takes-the-edit-route.md`, `docs/adr/0049-selection-forms-and-verbs.md:35`, `docs/adr/0047-edge-settings.md:40`, `docs/reference/glossary.md`, `CLAUDE.md` (Architecture traps list)
- Create: `.insights/project_value_steps_amend_the_tip.md`

- [ ] **Step 1: ADR 0055**, corrected in place (no history notes):
  - The "Value writes are not recorded yet" decision bullet (~:27) becomes the recording rule, the merge run (same field, same route, ends at another step, a fence, an undo or `VALUE_EDIT_MERGE_IDLE_S`), the amend path and why it bypasses the 100 ms/500 ms merge (the trap in the spec).
  - Consequences (~:42): value edits in level mode `edit` are undoable; a multi-node form edit is one step; the history stays shared across sessions, so one session's undo can undo another's step.
  - Alternatives: one line each for a generalized history merge (changes every action's behaviour) and widget begin/end gestures (typing has no natural end).
- [ ] **Step 2: ADR 0049:35 and ADR 0047:40** state that setting and style edits are undoable (one step per edit; a form edit across many elements is one step).
- [ ] **Step 3: Glossary.**
  - New row **Merge run**: consecutive writes by one session to one field that amend a single undo step until another step, a fence, an undo or a 3 s idle gap. Aliases to avoid: coalescing window, burst.
  - **graph metadata** (~:458): "a panel edit is not recorded" → a panel edit in level mode `edit` is one undo step.
  - **Fence** (~:437): add that a save and an unrecorded write also add one.
- [ ] **Step 4: Insight** `project_value_steps_amend_the_tip.md`: value writes cannot use the generic merge (100 ms window, pending-only, flushed 500 ms after a fence), so they amend the newest step through `add_value_action`; tests of undo must run with merging and grouping on. Add a one-line entry under "Architecture traps" in `CLAUDE.md`.
- [ ] **Step 5: Gate.** `uv run ruff check . --extend-exclude .scratch`, `uv run ruff format --check` on touched files, the CLAUDE.md mypy command, `uv run mkdocs build --strict`, `uv run python scripts/bake_docs.py`, then commit and run `uv run pytest -m "not browser and not perf" -n 4 -q` and `uv run pytest -m browser -n 4 -q`. All green.
- [ ] **Step 6: Commit** `docs: value edits are undoable (ADR 0055, 0049, 0047, glossary)`.
- [ ] **Step 7: Live-check list** for the user (studio started from the worktree):
  1. Unlocked level: drag a card slider for ~2 s, Ctrl+Z → back to the value before the drag in one step; Ctrl+Shift+Z redoes it.
  2. Type a word into a text setting in Properties, Ctrl+Z → the whole word goes.
  3. Drag a slider, wait 4 s, drag again → two undo steps.
  4. Multi-node form: change one field across 3 nodes, Ctrl+Z → all three back.
  5. Locked level: drag a card slider → graph unsaved, Ctrl+Z does not undo it (Undo is unavailable in `operate`).
  6. Drag, Ctrl+S, drag again within 3 s, Ctrl+Z → returns to the saved value.
  7. Selection toolbar Lock: toggle → graph unsaved; Ctrl+Z toggles back.
  8. Undo a Properties edit → the Properties row and the card widget both show the restored value.
  9. Two browser sessions on one graph, both dragging the same slider → separate undo steps.
