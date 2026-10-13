# Editor modes, slice 2: Enter and look inside — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Let any session look inside a running macro placement. **Enter** opens the placement's live interior as a level that is locked and cannot be unlocked. Double-clicking a Graph-node card enters it at VIEW tier.

**Architecture:**
- **One rule decides "inside a placement".** A level whose container chain passes through a definition with `template_key` set is *inside a placement*. That level opens locked, and unlocking it is refused. The rule is applied once, where a `_Level` is made (`GraphEditor._new_level`). That way every path that opens a level gets it: Enter, the error-ledger reveal, and a Group nested in a placement.
- **`descend_into` stops refusing placements.**
- **Enter at VIEW tier.** A double-click gesture on Graph-node cards provides it, because context menus need effective EDIT since slice 1.
- **An open placement level follows a `.hwm` reload** instead of closing.
- **Nothing that cannot be saved marks the host unsaved.** A placement's non-structural interior changes are not forwarded to the host, because ADR 0038 never saves them.

**Tech Stack:** Python 3.12, NiceGUI/Vue 3, pytest (`uv run pytest`), ruff, mypy.

**Spec:** [2026-10-12-editor-modes.md](2026-10-12-editor-modes.md), section "Macros: Enter, Edit Instance, and three verbs"; build sequence item 2.

## Global Constraints

- **The verb is Enter.** It replaces the label "Enter Group" and works for Groups and macro placements.
- **A level inside a placement** (the placement's interior, or anything nested in it) opens **locked** and **cannot be unlocked** in this slice. Edit Instance arrives in slice 3.
- **Refusing to unlock shows:** `"Inside a macro placement this level stays locked. Use Edit Macro… to change the macro."`
- **The lock-button tooltip on such a level:** `"Locked: inside a macro placement"`. The button renders disabled.
- **Entering needs VIEW.** Double-clicking a Graph-node card enters it, unless the double-click lands on an interactive widget.
- **A placement's interior values are runtime state** (ADR 0038). They stay operable on a locked placement level (OPERATE), are not saved, and do not mark the host unsaved.
- **Slice-1 rules stand:** the single `allows(can_access, locked, required)` rule, enforcement where the write lands, and Save/unlock on the real tier.
- **Docs rules:** follow `.claude/rules/python-docs.md`. Glossary and ADR edits land in Task 6 with the code.
- **Commit trailer:** end every commit message with `Co-Authored-By: Claude Opus 5.5 (1M context) <noreply@anthropic.com>`.

## Review Focus

1. **An error raised inside a placement**, revealed from the error ledger, opens the interior locked, and unlocking it is refused. Test in Task 1.
2. **A Group nested inside a placement** opens locked and refuses unlock as well. Test in Task 1.
3. **The `.hwm` is saved while its placement level is open.** The level stays open and shows the new interior, and the card still hears edits made inside it. Test in Task 4.
4. **A slider moved inside a locked placement level** changes the live value. The host is not marked unsaved and is not reassembled. Test in Task 5.
5. **A double-click on a widget inside a Graph-node card** (for example a slider) does not enter the node. Test in Task 3.

---

### Task 1: Levels inside a placement stay locked

**Files:**
- Modify: `barn/haybale-graph-editor/haybale_graph_editor/editors/graph_editor.py`:
  - `_Level` (~:100-111) gains `inside_placement: bool = False`;
  - `_new_level` (~:248-251);
  - `set_level_locked` (~:253-269);
  - `_on_toggle_lock` (~:509-521);
  - `_update_lock_button` (~:1029-1040).
- Test: `tests/graph_editor/test_graph_editor_placement_levels.py` (new; reuse the fakes from `tests/graph_editor/test_graph_editor_levels.py` and the resolver helpers from `tests/graph_editor/test_graph_editor_lock.py`)

**Interfaces:**
- Produces:
  - module function `inside_placement(container: GraphContainer) -> bool` in `graph_editor.py`. It is True when `container` is a `SubgraphContainer` whose `definition.template_key is not None`, or whose host chain contains such a container.
  - `_Level.inside_placement`;
  - `set_level_locked(...)` returns False for `locked=False` on such a level.

- [ ] **Step 1: Write the tests.**
  - `test_a_placement_interior_opens_locked`: a `SubgraphContainer` over a definition with `template_key="lib:macro:Blur"` gives `_new_level(...)`, with `locked is True` and `inside_placement is True`, even when its graph's `props.open_locked` is False.
  - `test_a_group_nested_in_a_placement_opens_locked`: a container whose host is a placement container gives `inside_placement is True`.
  - `test_a_plain_group_is_not_inside_a_placement`.
  - `test_unlock_is_refused_inside_a_placement_even_for_admin`: `set_level_locked(ctx, key, False)` returns False and the level stays locked; `set_level_locked(ctx, key, True)` is a no-op returning True.
  - `test_toggle_lock_inside_a_placement_notifies`: `_on_toggle_lock` calls `ui.notify` with the Global Constraints refusal text, type `"warning"` (patch `ui`).
  - `test_lock_button_disabled_inside_a_placement`: `_update_lock_button` calls `set_enabled(False)` and sets the tooltip text `"Locked: inside a macro placement"` for an ADMIN principal.
  - `test_reveal_opens_a_placement_interior_locked`: `_open_level_for_graph(context, interior.graph_id)` on a document whose `subgraphs` holds a `template_key` definition. The opened level is locked and `inside_placement`.
- [ ] **Step 2: Run** `uv run pytest tests/graph_editor/test_graph_editor_placement_levels.py -q`. Expect FAIL.
- [ ] **Step 3: Implement.**
  - `_new_level` sets `inside_placement=inside_placement(container)` and `locked=inside or graph.props.open_locked`.
  - `set_level_locked` returns False for an unlock when `level.inside_placement`, before the tier check.
  - `_on_toggle_lock` picks the refusal message: the placement text when `inside_placement`, the existing "needs edit access" text otherwise.
  - `_update_lock_button` disables the button and uses the placement tooltip on such a level.
- [ ] **Step 4: Run** `uv run pytest tests/graph_editor/ -n 4 -q`. Expect PASS.
- [ ] **Step 5: Commit** `feat(graph-editor): levels inside a macro placement open locked and stay locked`.

### Task 2: Enter a placement; the Enter verb

**Files:**
- Modify: `graph_editor.py` `descend_into` (~:814-851): remove the `is_macro_placement` refusal; update the docstring.
- Modify: `barn/haybale-graph-editor/haybale_graph_editor/panels/graph/menu/selection/selection.py`:
  - Move the Enter row out of `GroupMenuPanel` (~:656-700) into a new `EnterMenuPanel` (same surface, `label="Enter"`, `order=35`, `poll` true when `is_graph_node(ctx) or is_macro_placement(ctx)` from `panels/_gating.py`). The row is labelled `"Enter"` and calls `self.actions.enter_group(node_id)`.
  - `GroupMenuPanel` keeps Expand Group and Promote to Macro….
- Modify: `packages/haywire-core/src/haywire/ui/components/graph/event_definitions.py:190-197`: the `EnterGroupEvent` description becomes `"Step inside a Graph-node: a Group or a macro placement"`. Regenerate `generated/graph_events.js` the way the repo does (find the generator; `canvas.py` imports it).
- Modify: stale docstrings that describe the refusal:
  - `packages/haywire-core/src/haywire/core/macro/source.py:25-33` (`is_macro_placement`);
  - `panels/_gating.py:133-139`;
  - `barn/haybale-haystack/haybale_haystack/panels/graph/menu/macro.py:36-42` (`EditMacroMenuPanel`).
- Test: `tests/graph_editor/test_graph_editor_levels.py` (replace `TestDescending.test_a_macro_placement_is_refused`); `tests/graph_editor/test_group_verbs.py` (panel polls); `tests/core/test_macro/test_macro_editing_surface.py:119-143` (`test_a_placement_is_not_descendable` → descendable)

**Interfaces:**
- Consumes: `_Level.inside_placement` and locked-on-open (Task 1).
- Produces: `EnterMenuPanel`.

- [ ] **Step 1: Write the tests.**
  - `test_a_macro_placement_is_entered_locked`: replaces the refusal test. `descend_into` returns True, the active level key is `"macro_card_1"`, and that level is `locked` and `inside_placement`.
  - `test_enter_row_shows_for_groups_and_placements`: `EnterMenuPanel.poll` is True for a Graph-node and for a placement, and False for a plain node.
  - `test_group_panel_no_longer_offers_enter`: `GroupMenuPanel` draws no "Enter Group" row.
  - The core test: entering a real placement through `GraphEditor`'s level machinery opens `resolve_definition()` of that placement.
- [ ] **Step 2: Run.** Expect FAIL.
- [ ] **Step 3: Implement.**
- [ ] **Step 4: Run** `uv run pytest tests/graph_editor/ tests/core/test_macro/ -n 4 -q`. Expect PASS.
- [ ] **Step 5: Commit** `feat(graph-editor): Enter opens Groups and macro placements`.

### Task 3: Double-click a Graph-node card to enter

**Files:**
- Modify: `barn/haybale-graph-editor/haybale_graph_editor/editors/graph_canvas/ui_node.py`. Stamp `data-node-enterable` on the `[data-node-id]` container when the node is a Graph-node (`identity._is_graph_node`) or a macro placement (`is_macro_placement(node)`). Follow the `data-node-props-locked` stamping pattern (~:249-283).
- Modify: `packages/haywire-core/src/haywire/ui/components/graph/canvas.vue`.
  - A `dblclick` handler on the node container emits `EnterGroupEvent` (`EventCreators`, the generated creator) with the node id, when:
    - the target is inside a `[data-node-enterable]` container;
    - the target is not inside an interactive widget (`_isInteractiveWidgetElement`);
    - the target is not a pin (`[data-pin-id]`).
  - Works while the canvas is read-only; entering is VIEW.
  - Document the attribute in the attribute index at the top of the file.
- Test: unit test for the stamp; browser test `tests/ui/harness/test_enter_by_double_click.py` (auto-marked `browser`; use `goto_ready`; add a harness route in `tests/ui/harness/routes.py` only if no existing route has a Group card — reuse the lock route pattern if one does).

**Interfaces:**
- Consumes: `EnterGroupEvent` handler `process_enter_group` (VIEW access, slice 1), `descend_into` (Task 2).

- [ ] **Step 1: Write the tests.**
  - `test_graph_node_cards_are_enterable`: a Group card and a placement card carry `data-node-enterable`; a plain node does not.
  - Browser `test_double_click_enters_a_group`: double-clicking a Group card's title opens the Group level. The breadcrumb shows its label.
  - Browser `test_double_click_on_a_widget_does_not_enter`: double-clicking a widget inside the card leaves the active level unchanged.
  - Browser `test_double_click_enters_on_a_locked_level`.
- [ ] **Step 2: Run.** Expect FAIL.
- [ ] **Step 3: Implement.**
- [ ] **Step 4: Run** `uv run pytest tests/graph_editor/ -n 4 -q` and `uv run pytest -m browser -n 4 -k "double_click or enter" -q`. Expect PASS.
- [ ] **Step 5: Commit** `feat(canvas): double-click a Graph-node card to enter it`.

### Task 4: An open placement level follows a `.hwm` reload

**Files:**
- Modify: `packages/haywire-core/src/haywire/barn/builtin/nodes/macro_node.py` `on_class_reloaded` (~:153-163). After `instantiate_from_template()`, the card watches the new definition. Call `GraphNode._watch_definition` with the new one; read `graph_node.py` for its signature.
- Modify: `graph_editor.py` `_prune_dead_levels` (~:348-370). For a level that is `inside_placement` whose definition was replaced, look up the host's current definition under the same key. If one exists and its card is alive, re-point the level instead of closing it: a new `SubgraphContainer` over the new definition, its canvas torn down and remounted (`_teardown_level` / `_mount_level`), the lock and `inside_placement` kept, and the active level kept if it was active. Close it only when the key no longer resolves.
- Test:
  - `tests/core/test_macro/test_macro_reload.py`: card re-watch; use its `macro_file` / `_modified` helpers.
  - `tests/graph_editor/test_graph_editor_placement_levels.py`: level re-point.

**Interfaces:**
- Consumes: `_Level.inside_placement` (Task 1).

- [ ] **Step 1: Write the tests.**
  - `test_reload_rewatches_the_new_interior`: after a `.hwm` reload, a structural edit inside the new interior still reaches the card. `reconcile_interface` runs, or the host receives `GRAPH_REQUIRE_REASSEMBLY`. The assertion must fail on today's code.
  - `test_an_open_placement_level_follows_a_reload`: with the placement level open and active, replace the host's definition under the same key and call `_prune_dead_levels`. The level is still open, is active, its container's definition `is` the new one, and it is locked and `inside_placement`.
  - `test_a_removed_placement_closes_its_level`: when the key no longer resolves, the level closes, as today.
- [ ] **Step 2: Run.** Expect FAIL.
- [ ] **Step 3: Implement.**
- [ ] **Step 4: Run** `uv run pytest tests/core/test_macro/ tests/graph_editor/ -n 4 -q`. Expect PASS.
- [ ] **Step 5: Commit** `fix(macro): an open placement level and its card follow a template reload`.

### Task 5: A placement's interior changes do not mark the host unsaved

**Files:**
- Modify: `macro_node.py`. Override how the card forwards its interior's validation:
  - structural changes (`result.requires_reassembly()`) are forwarded as `GraphNode` does: redraw plus `GRAPH_REQUIRE_REASSEMBLY`;
  - non-structural save-relevant changes are not forwarded, because the interior is never saved (ADR 0038).

  Keep the interface-reconcile branch. Prefer a small hook on `GraphNode` (for example `_forwards_content_changes: bool = True`, set False on `MacroNode`) over copying the handler. Read `graph_node.py` `_on_definition_validated` (~:107-132).
- Test: `tests/core/test_macro/test_macro_node.py`

**Interfaces:**
- Consumes: `ChangeReason.GRAPH_CONTENT_CHANGED`, `NodeWrapper.mark_value_edited` (slice 1).

- [ ] **Step 1: Write the tests.**
  - `test_an_interior_value_edit_does_not_mark_the_host`: a real placement (`_place`). Calling `mark_value_edited()` on an interior node delivers no host batch with `requires_save()`, and the host is not reassembled.
  - `test_a_group_still_forwards_content_changes`: the same edit inside a Group interior still forwards `GRAPH_CONTENT_CHANGED` (slice-1 behaviour).
  - `test_an_interior_value_is_still_live`: after the edit, the interior port's value is the new one.
- [ ] **Step 2: Run.** Expect FAIL.
- [ ] **Step 3: Implement.**
- [ ] **Step 4: Run** `uv run pytest tests/core/test_macro/ tests/core/test_graph/ -n 4 -q`. Expect PASS.
- [ ] **Step 5: Commit** `fix(macro): a placement's interior edits do not mark the host unsaved`.

### Task 6: Docs, glossary, ADR amendment

**Files:**
- Modify: `docs/adr/0038-a-placements-interior-is-runtime-state.md:99-102`. Replace "Descending into a placement is refused…" with the current rule:
  - Enter opens the live interior locked;
  - it cannot be unlocked until Edit Instance;
  - interior values are operable and not saved;
  - the level follows a reload.

  Add an amendment note naming this slice. Keep the original reasoning.
- Modify: `docs/reference/glossary.md`. Add **Enter** (open a Graph-node's interior as a level: double-click its card or use the menu; a placement opens locked). Mention "inside a placement" in the **Lock** row. Follow the existing row style.
- Modify: `barn/haybale-graph-editor/haybale_graph_editor/protocols.py:79-99`. The `SubgraphContainer` docstring example registers in `GraphAppState` and repayloads, which `GraphEditor` never does. Replace it with the real use: the editor builds one per level and keeps it in its `_levels`. Fix the `binding_id_for` docstring the same way.
- Modify: `docs/guides/security.md:486` and `docs/adr/0051-operate-tier-and-the-canvas-lock.md` ("enters levels") to name macro placements.
- Run: `uv run python scripts/bake_docs.py`; `uv run mkdocs build --strict`.

- [ ] **Step 1: Edit the docs.**
- [ ] **Step 2: Run** the bake, `mkdocs build --strict`, and `uv run pytest tests/ -k "bake or docs" -n 4 -q`. Expect PASS.
- [ ] **Step 3: Commit** `docs: Enter and read-only placement levels (ADR 0038 amendment)`.

### Task 7: Full gate

- [ ] **Step 1:** `uv run ruff check . && uv run ruff format --check .`
- [ ] **Step 2:** the CLAUDE.md mypy command.
- [ ] **Step 3:** `uv run pytest -m "not browser and not perf" -n 4 -q > /tmp/t.log 2>&1; echo "exit=$?"`. Expect `exit=0`.
- [ ] **Step 4:** `uv run pytest -m browser -n 4 -q`. Expect PASS.
