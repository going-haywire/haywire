# Previous Setup After a Hot Reload Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** A hot reload no longer records an undo step; each node it changes keeps its pre-reload data as a **previous setup** the user applies or dismisses explicitly, in every graph, with or without a history (backlog #46).

**Architecture:** The previous setup is a field on `NodeWrapper`, written into the node's own `serialize()["node_data"]` under the key `previous_setup` and read back by `build(node_info)`. Because it travels inside the node data, the file, Collapse to Group, Delete+Undo and every `RebuildNodesAction` snapshot carry it with no extra code. A `NodeWarning(kind="previous_setup")` is derived from the field. The validation pass sets the field on reload instead of recording a step. Apply, Dismiss and Reset are all `RebuildNodesAction`, generalized with an optional `after` per node.

**Tech Stack:** Python 3.12, NiceGUI, pytest; uv.

**Spec:** The decisions below (inquisition Q1–Q16, Q5′, Q10′, 2026-10-27, this file's own section) and the handoff `internals/handoff/reload-without-history-loses-setup.md`. They supersede the handoff's options (a)–(c).

## Decisions (the spec)

| # | Decision |
|---|---|
| Q1 | **Apply** rebuilds the node from the whole previous setup through the load path (as undo of a reload did). No per-field matching. |
| Q2 | A second reload never replaces a held previous setup. If the node's data after a reload equals the held previous setup, the previous setup clears itself. |
| Q3 | The previous setup is saved in the file; reopening restores it and its warning. |
| Q4 | Notice: `NodeWarning(kind="previous_setup")` on the node (amber badge) **and** a ledger WARNING. ADR 0061 line 50 is amended. |
| Q4b | One ledger entry **per node**, carrying `graph_id` + `node_id`, so Reveal works. |
| Q5′ | The ledger row offers Reveal only (no Apply/Dismiss in the Errors editor). |
| Q6 | Ledger row and previous setup are independent: resolving leaves the row; deleting/clearing rows leaves the setup. |
| Q7 | Opening a graph that holds previous setups records one ledger row per such node. |
| Q8 | A row for a node inside a Group/Macro interior names its host node. Reveal into closed interiors and badge aggregation onto Group cards are **out of scope** (two new backlog items). |
| Q9 | A node gets a previous setup when its data before ≠ after the reload (stand-ins and nodes that absorb their reload excluded). Default-change false positives are accepted. |
| Q10/Q10′ | Apply and Dismiss are undoable steps; undo brings the previous setup and warning back. All three verbs (Reset, Apply, Dismiss) are `RebuildNodesAction`, generalized with an optional `after`; no new action class. Dismiss pays a node rebuild. |
| Q11 | **Reset dismisses** the previous setup; Undo of Reset brings it back. |
| Q12 | It travels with the node (file, Delete+Undo, Collapse to Group, Dissolve), not with copies (Paste, a Macro template). |
| Q13 | Term: **Previous setup**. Card text `Rebuilt from new code. Previous setup kept.` Buttons `Apply previous setup` / `Dismiss previous setup`. |
| Q14 | Farmhand tool `graph_editor_previous_setup(binding_id, node_ids, action)`, action `apply` or `dismiss`, one undo step. |
| Q15 | Apply/Dismiss live in the card's diagnostics-badge popup, in a `Previous setup` section, stamped `LevelMode.EDIT`. The popup groups warnings by `kind`. |
| Q16 | New ADR 0062 supersedes ADR 0059's reload half; ADR 0059 keeps Reset. Glossary and node-canon land with the code. |

## Global Constraints

- The file key is exactly `previous_setup`, inside a node's `node_data`; it is written only while a previous setup is held.
- `NodeWarning.kind` value is exactly `"previous_setup"`; its message is exactly `Rebuilt from new code. Previous setup kept.`
- Ledger rows: `severity=WARNING`, `graph_id` and `node_id` set; `operation="Hot reload"` at reload, `operation="Load graph"` at load.
- Ledger messages: reload `"{display_label} '{node_id}' kept its previous setup{where}"`; load `"{display_label} '{node_id}' holds a previous setup{where}"`; `where` is `""` for a root graph, else ` (inside '{host display_label}')`, host from `SubgraphDefinition.graph_node_wrapper()`. `display_label` is `BaseNode.display_label`.
- Undo descriptions come from `describe_rebuild(verb, labels)` with verbs exactly `"Reset"`, `"Apply previous setup"`, `"Dismiss previous setup"`.
- The app never depends on a barn library; no relative imports under `barn/`; ruff line length 109.
- Docstrings and comments follow `.claude/rules/python-docs.md` (no history, no "rather than", present tense).
- `tests/studio/test_docs/test_generate.py` reverts `barn/haybale-testing` — commit before running the full suite.
- Glossary, ADRs and `node-canon.md` change only in Task 7, with the code.

## Review Focus

1. **A node moved after the reload, then Apply** — the node must stay where it is now (position, z, on-stage, stage position): Apply restores the setup, not the old arrangement. Test in Task 3.
2. **A reload that leaves a node as a stand-in while it holds a previous setup** — the held previous setup must survive the stand-in phase and still be there when the class is fixed. Test in Task 2.
3. **Reset on a node holding a previous setup, then Undo** — the previous setup and its warning come back. Test in Task 3.
4. **Pasting a node copied from inside a Group whose interior holds previous setups** — no pasted node, interior or not, carries one. Test in Task 5.
5. **A Macro instance whose interior node holds a previous setup** — saving it as a new Macro template writes no `previous_setup` into the `.hwm`. Test in Task 5.

---

## File Structure

- Create `packages/haywire-core/src/haywire/core/node/previous_setup.py`: the key and message constants, `strip_previous_setups`, `report_previous_setup`.
- Modify `packages/haywire-core/src/haywire/core/node/node_wrapper.py`: the field, `build` / `serialize` / `set_previous_setup`, the warning sync.
- Modify `packages/haywire-core/src/haywire/core/node/node_warning.py`: `kind` docstring.
- Modify `packages/haywire-core/src/haywire/core/graph/validation.py`: reload keeps the previous setup; the undo recording goes.
- Modify `packages/haywire-core/src/haywire/core/undo/actions/graph_actions.py`: `RebuildNodesAction.after`.
- Modify `packages/haywire-core/src/haywire/core/graph/editor.py`: `apply_previous_setup`, `dismiss_previous_setup`.
- Modify `packages/haywire-core/src/haywire/core/graph/base.py`: load records rows.
- Modify `packages/haywire-core/src/haywire/core/graph/clipboard.py`, `packages/haywire-core/src/haywire/core/macro/promote.py`: copies drop it.
- Modify `barn/haybale-graph-editor/haybale_graph_editor/skins/node_skin.py`: the popup section.
- Modify `barn/haybale-graph-editor/haybale_graph_editor/farmhands/editor_tools.py`: the tool.
- Docs: `docs/adr/0062-a-reload-keeps-the-previous-setup.md` (new), ADR 0059, ADR 0061, glossary, `docs/components/nodes/node-canon.md`, backlog.

---

### Task 1: The previous setup on the node

**Files:**
- Create: `packages/haywire-core/src/haywire/core/node/previous_setup.py`
- Modify: `packages/haywire-core/src/haywire/core/node/node_wrapper.py` (`build` :314, `serialize` :844)
- Modify: `packages/haywire-core/src/haywire/core/node/node_warning.py` (docstring of `kind`)
- Test: `tests/core/test_node/test_previous_setup.py` (integration; use the `graph_with_library_system` / `library_system` fixtures and `TestPrintNode` as `tests/core/test_node/test_reload_undo.py` does)

**Interfaces:**
- Produces, in `previous_setup.py`:
  - `PREVIOUS_SETUP_KEY: Final = "previous_setup"`
  - `PREVIOUS_SETUP_WARNING: Final = "Rebuilt from new code. Previous setup kept."`
  - `strip_previous_setups(document: dict) -> None` — removes `PREVIOUS_SETUP_KEY` from every `document["nodes"][*]["node_data"]`, recursing into every `document.get("subgraphs", {})` value (same shape). Mutates in place.
  - `report_previous_setup(wrapper: NodeWrapper, *, operation: str) -> None` — one ledger WARNING per Global Constraints; the message verb is `kept its previous setup` when `operation == "Hot reload"`, else `holds a previous setup`. Built with `HaywireException.create(..., severity=ErrorSeverity.WARNING, operation=operation).enrich(graph_id=..., node_id=...).log()`, never raises (wrap in `try/except Exception` with a debug log, as `report_loss` does).
- Produces, on `NodeWrapper`:
  - `previous_setup -> Optional[Dict[str, Any]]` (property, read-only, the held node data or `None`)
  - `set_previous_setup(data: Optional[Dict[str, Any]]) -> None` — sets the field and syncs the warning: removes every `NodeWarning` with `kind == "previous_setup"` from `state.warnings`, then adds one (`message=PREVIOUS_SETUP_WARNING, source_version=None, kind="previous_setup"`) when `data is not None`.
  - `build(node_info)`: when `node_info is not None`, work on a shallow copy, pop `PREVIOUS_SETUP_KEY` from it and keep the popped value; `node_info is None` leaves the field alone. After the build (warnings were cleared at its start) call `set_previous_setup(<the kept field>)`, so the warning reappears.
  - `serialize()`: when the field is set, `result["node_data"][PREVIOUS_SETUP_KEY] = copy.deepcopy(field)` — for a stand-in too.

- [ ] **Step 1: Write the failing tests**

```python
def test_a_previous_setup_round_trips_through_node_data(graph_with_library_system, library_system):
    graph, wrapper = _graph_and_printer(library_system, "kept")      # helper: graph + TestPrintNode, message set
    old = wrapper.serialize()["node_data"]
    wrapper.set_previous_setup(old)
    data = wrapper.serialize()["node_data"]
    assert data["previous_setup"] == old
    assert [w.kind for w in wrapper.state.warnings] == ["previous_setup"]
    assert wrapper.state.warnings[0].message == "Rebuilt from new code. Previous setup kept."

    wrapper.build(data)                     # the load / undo path
    assert wrapper.previous_setup == old
    assert [w.kind for w in wrapper.state.warnings] == ["previous_setup"]

def test_building_from_data_without_the_key_clears_it(graph_with_library_system, library_system):
    graph, wrapper = _graph_and_printer(library_system, "kept")
    wrapper.set_previous_setup(wrapper.serialize()["node_data"])
    data = wrapper.serialize()["node_data"]
    data.pop("previous_setup")
    wrapper.build(data)
    assert wrapper.previous_setup is None
    assert wrapper.state.warnings == []

def test_a_fresh_build_keeps_the_field(graph_with_library_system, library_system):
    graph, wrapper = _graph_and_printer(library_system, "kept")
    wrapper.set_previous_setup({"x": 1})
    wrapper.build()                          # node_info None: the field is left alone
    assert wrapper.previous_setup == {"x": 1}

def test_strip_previous_setups_recurses_into_subgraphs():
    doc = {
        "nodes": {"a": {"node_data": {"previous_setup": {}, "props": {}}}},
        "subgraphs": {"g": {"nodes": {"b": {"node_data": {"previous_setup": {}}}}, "subgraphs": {}}},
    }
    strip_previous_setups(doc)
    assert "previous_setup" not in doc["nodes"]["a"]["node_data"]
    assert "previous_setup" not in doc["subgraphs"]["g"]["nodes"]["b"]["node_data"]

def test_report_names_the_host_of_an_interior(graph_with_library_system, library_system, ledger):
    # ledger: fresh ErrorLedger fixture as in tests/core/test_graph/test_load_save_boundary.py
    # build a Group (Editor.collapse_to_group on one printer); take the interior wrapper
    report_previous_setup(interior_wrapper, operation="Hot reload")
    (entry,) = ledger.query().entries
    assert entry.severity.value == "warning"
    assert (entry.graph_id, entry.node_id) == (definition.graph_id, interior_wrapper.node_id)
    assert entry.message.endswith(f"kept its previous setup (inside '{host.node.display_label}')")
```

- [ ] **Step 2: Run them to verify they fail**

Run: `uv run pytest tests/core/test_node/test_previous_setup.py -v`
Expected: FAIL (`ImportError` on `haywire.core.node.previous_setup`).

- [ ] **Step 3: Implement** `previous_setup.py` and the `NodeWrapper` interface above; update `NodeWarning.kind`'s docstring to list `"compatibility"` and `"previous_setup"` (the latter: "the node holds the data it had before a hot reload; the remedy is Apply or Dismiss on its card").

- [ ] **Step 4: Run them to verify they pass**, plus `uv run pytest tests/core/test_node/ tests/core/test_graph/ -q -n 4`.

- [ ] **Step 5: Commit** — `feat(node) a node can hold a previous setup, saved inside its node data (#46)`

---

### Task 2: A reload keeps the previous setup instead of recording a step

**Files:**
- Modify: `packages/haywire-core/src/haywire/core/graph/validation.py` (the `NODE_HOT_RELOADED` branch near :318, `_capture_for_undo` :445, `_unchanged_by_reload` :461, `_record_reload` :469, its call near :438)
- Modify: `tests/core/test_node/test_reload_undo.py` → rename to `tests/core/test_node/test_reload_previous_setup.py` (`git mv`) and rewrite
- Modify: `docs/components/nodes/node-canon.md` only in Task 7

**Interfaces:**
- Consumes: Task 1 (`previous_setup`, `set_previous_setup`, `PREVIOUS_SETUP_KEY`, `report_previous_setup`).
- Produces: nothing new; `_capture_for_undo`, `_record_reload` and the `threading` main-thread guard are deleted. No history is consulted.

Per reloaded node that is not a stand-in before the reload, the rule (Q2, Q9):

```text
before = serialize()["node_data"];  held = before.pop("previous_setup", None)
build(take_rebuild_data())                       # as today
if is_stand_in:            set_previous_setup(held)      # a failed reload keeps what was held
else:
    after = serialize()["node_data"] without "previous_setup"
    candidate = held if held is not None else before
    if after == candidate:  set_previous_setup(None)
    else:                   set_previous_setup(candidate); report_previous_setup(wrapper, operation="Hot reload")
```

A stand-in before the reload and a node that absorbs its reload (`on_class_reloaded` → no `NODE_HOT_RELOADED` mark) are untouched, as today. If serializing fails, log at debug and leave the field as it was.

- [ ] **Step 1: Rewrite the tests** in `test_reload_previous_setup.py`, keeping the module's helpers (`_ParkedScheduler`, `_graph_with_editor`, `_printer`, `_reload`, `_message`). Delete the tests about undo steps (`test_a_reload_records_one_step_for_the_graph`, `test_each_graph_records_its_own_step`, `test_a_reload_step_holds_only_the_nodes_it_changed`, `test_a_graph_without_an_editor_records_nothing`, `test_a_reload_validated_off_the_main_thread_records_nothing`, `test_undo_and_redo_rebuilds_are_not_recorded`, `test_two_quick_undos_reach_the_state_before_both`, `test_a_recorded_reload_is_its_own_step`, `test_a_reload_inside_a_group_is_a_step_on_the_host_history`, `test_reload_batches_in_a_row_undo_one_by_one`, `test_an_undone_reload_saves_and_reopens_with_the_old_data`); keep `test_undoing_a_reset_and_then_its_delete_quickly_restores_the_node` (it is about Reset) and adapt the rest:

```python
def test_a_reload_keeps_the_previous_setup_and_records_no_step(...):
    graph, editor = _graph_with_editor(library_system)
    first = _printer(graph, "one")
    before = first.serialize()["node_data"]
    _reload(graph, first)
    assert _message(first) == "Hello, World!"
    assert first.previous_setup == before
    assert not editor.history_manager.can_undo()
    (entry,) = ledger.query().entries
    assert (entry.operation, entry.node_id) == ("Hot reload", first.node_id)

def test_an_untouched_node_keeps_nothing(...):         # printer left at its default
    assert untouched.previous_setup is None and ledger.query().total == 0

def test_a_graph_without_an_editor_keeps_the_previous_setup(...):     # #46
    graph = BaseGraph("Bare", validation_scheduler=_ParkedScheduler())  # no Editor
    ...; assert wrapper.previous_setup is not None

def test_a_reload_inside_a_never_opened_group_keeps_the_previous_setup(...):  # #46
    # collapse a set printer into a Group, never create an Editor for the interior,
    # reload the interior node: its previous_setup holds "one"; the row names the host

def test_a_second_reload_keeps_the_first_previous_setup(...):
    _reload(graph, first); _reload(graph, first)
    assert first.previous_setup == before            # not the pristine data

def test_a_reload_back_to_the_previous_setup_clears_it(...):
    # hold a previous setup equal to what the next rebuild produces
    # (set_previous_setup(pristine data)); reload; previous_setup is None, no warning

def test_a_failed_reload_keeps_the_held_previous_setup(..., construction_fails):   # Review Focus 2
    _reload(graph, first)                                # holds `before`
    with construction_fails(...): _reload(graph, first)  # now a stand-in
    assert first.is_stand_in and first.previous_setup == before
    # fix the class (leave the context), reload again: previous_setup still == before

def test_a_node_that_absorbs_its_reload_keeps_nothing(...):   # adapted from the old test
```

- [ ] **Step 2: Run to verify they fail** — `uv run pytest tests/core/test_node/test_reload_previous_setup.py -v` (previous_setup is None; a step is still recorded).
- [ ] **Step 3: Implement** the rule above in `validation.py`.
- [ ] **Step 4: Run** the file, then `uv run pytest tests/core/ -q -n 4 -m "not browser and not perf"`; grep the tests for `Reload ` undo descriptions (`grep -rn '"Reload ' tests/`) and update any that asserted the old step.
- [ ] **Step 5: Commit** — `feat(reload) a hot reload keeps each changed node's previous setup instead of an undo step (#46)`

---

### Task 3: Apply, Dismiss and Reset as one action

**Files:**
- Modify: `packages/haywire-core/src/haywire/core/undo/actions/graph_actions.py` (`RebuildNodesAction` :2913)
- Modify: `packages/haywire-core/src/haywire/core/graph/editor.py` (beside `reset_nodes` :463)
- Test: `tests/core/test_undo/test_rebuild_nodes_action.py` (extend), `tests/core/test_node/test_previous_setup.py` (extend)

**Interfaces:**
- Consumes: Task 1.
- Produces:
  - `RebuildNodesAction.__init__(graph, before, description, after: Optional[Mapping[str, Optional[Dict[str, Any]]]] = None)` — execute/redo rebuilds each node from `after[node_id]`; `None` (or no `after`) is `init()` as today **and** clears the node's previous setup (`set_previous_setup(None)` before the rebuild request), which is how Reset dismisses (Q11). Undo is unchanged: `before` carries `previous_setup` inside it, so undo restores it.
  - `RebuildNodesAction.capture(graph, node_ids, description, after=None)` — same pass-through.
  - `Editor.apply_previous_setup(node_ids: List[str]) -> bool` — `False` without changes when the list is empty, names a missing node, or a node holds no previous setup. `after[node_id]` is the previous setup with the node's **current arrangement** written over it: position and the `_CARRIED_ARRANGEMENT` fields from `node_wrapper.py` (Review Focus 1). One undo step, `describe_rebuild("Apply previous setup", labels)`.
  - `Editor.dismiss_previous_setup(node_ids: List[str]) -> bool` — same refusals; `after[node_id]` is the node's current `serialize()["node_data"]` without `previous_setup`. One undo step, `describe_rebuild("Dismiss previous setup", labels)`.
  - Both report a failure as `reset_nodes` does (`report_failure(e, operation="Apply previous setup" | "Dismiss previous setup", graph_id=..., node_ids=...)`).

- [ ] **Step 1: Write the failing tests**

```python
def test_apply_restores_the_previous_setup_and_undo_brings_the_warning_back(...):
    _reload(graph, first)                                  # "one" -> default, previous setup held
    assert editor.apply_previous_setup([first.node_id])
    assert _message(first) == "one" and first.previous_setup is None
    assert editor.history_manager.get_undo_description() == f"Apply previous setup {label}"
    assert editor.undo(); graph._validation.force_immediate_validation()
    assert _message(first) == "Hello, World!" and first.previous_setup is not None
    assert [w.kind for w in first.state.warnings] == ["previous_setup"]

def test_apply_keeps_the_node_where_it_is_now(...):        # Review Focus 1
    _reload(graph, first); first.node.props.set_position((500.0, 300.0))
    editor.apply_previous_setup([first.node_id])
    assert first.node.props.get_position() == (500.0, 300.0)

def test_dismiss_drops_it_and_undo_brings_it_back(...):
    assert editor.dismiss_previous_setup([first.node_id])
    assert first.previous_setup is None and _message(first) == "Hello, World!"
    editor.undo(); ...; assert first.previous_setup is not None

def test_reset_dismisses_and_undo_of_reset_restores(...):   # Q11, Review Focus 3
    assert editor.reset_nodes([first.node_id])
    assert first.previous_setup is None
    editor.undo(); ...; assert first.previous_setup is not None

def test_apply_refuses_a_node_without_a_previous_setup(...):
    assert editor.apply_previous_setup([untouched.node_id]) is False
    assert not editor.history_manager.can_undo()
```

In `test_rebuild_nodes_action.py`: `test_execute_rebuilds_from_after_when_given` — `after={id: data_with_message("x")}`, execute → message `"x"`, undo → original.

- [ ] **Step 2: Run to verify they fail.**
- [ ] **Step 3: Implement** the interfaces above.
- [ ] **Step 4: Run** both files and `uv run pytest tests/core/test_undo/ -q`.
- [ ] **Step 5: Commit** — `feat(editor) apply or dismiss a previous setup as one undo step; Reset dismisses it (#46)`

---

### Task 4: Opening a graph records its previous setups

**Files:**
- Modify: `packages/haywire-core/src/haywire/core/graph/base.py` (`load_from_dict`, the nodes loop near :1119; or after the housekeeping loop near :1171)
- Test: `tests/core/test_graph/test_load_save_boundary.py` (extend; it has the `ledger` fixture)

**Interfaces:**
- Consumes: Task 1 (`report_previous_setup(wrapper, operation="Load graph")`).
- Produces: after the nodes are built, one row per node with `previous_setup is not None`, interior definitions included (their own `load_from_dict` runs the same loop).

- [ ] **Step 1: Write the failing test**

```python
def test_a_saved_previous_setup_reopens_with_its_warning_and_row(library_system, ledger, tmp_path):
    g, a, _b = _two_linked_nodes(library_system)
    a.set_previous_setup(a.serialize()["node_data"])
    path = tmp_path / "held.haywire"
    assert g.save_to_file(str(path))
    ledger.clear()
    g2 = _graph(); assert g2.load_from_file(str(path))
    reopened = g2.get_node_wrapper(a.node_id)
    assert reopened.previous_setup is not None
    assert [w.kind for w in reopened.state.warnings] == ["previous_setup"]
    (entry,) = ledger.query().entries
    assert (entry.operation, entry.node_id) == ("Load graph", a.node_id)
    assert "holds a previous setup" in entry.message
```

and `test_round_trip_records_nothing` must still pass unchanged.

- [ ] **Step 2: Run to verify it fails.**
- [ ] **Step 3: Implement.**
- [ ] **Step 4: Run** `uv run pytest tests/core/test_graph/ -q -n 4`.
- [ ] **Step 5: Commit** — `feat(load) a graph that holds previous setups records them in the ledger (#46)`

---

### Task 5: Copies drop the previous setup

**Files:**
- Modify: `packages/haywire-core/src/haywire/core/graph/clipboard.py` (`build_clipboard_payload` :26 — strip the returned payload)
- Modify: `packages/haywire-core/src/haywire/core/macro/promote.py` (`macro_document` :133)
- Test: `tests/core/test_graph/test_previous_setup_copies.py` (new)

**Interfaces:**
- Consumes: Task 1 (`strip_previous_setups`).
- Produces: `build_clipboard_payload(...)` and `macro_document(...)` return documents with no `previous_setup` at any depth. The moving paths (`CollapseToGraphNodeAction` :2184 and the Dissolve path :2403, Delete+Undo) are **not** touched: they move the same node and keep it (Q12).

- [ ] **Step 1: Write the failing tests**

```python
def test_a_pasted_node_holds_no_previous_setup(...)                    # copy + Editor.paste_clipboard
def test_a_pasted_group_holds_none_inside_either(...)                  # Review Focus 4: interior node holds one
def test_a_macro_document_holds_no_previous_setup(...)                 # Review Focus 5
    assert "previous_setup" not in json.dumps(macro_document(definition))
def test_collapse_to_group_keeps_it(...)                               # the interior node still holds it
```

- [ ] **Step 2–4:** fail, implement, pass; run `uv run pytest tests/core/test_graph/ tests/core/test_macro/ -q -n 4` (whichever macro test dir exists).
- [ ] **Step 5: Commit** — `feat(clipboard) copies and macro templates drop a node's previous setup (#46)`

---

### Task 6: Apply and Dismiss on the card, and for agents

**Files:**
- Modify: `barn/haybale-graph-editor/haybale_graph_editor/skins/node_skin.py` (`_render_diagnostics_button` :828 and its call near :409)
- Modify: `barn/haybale-graph-editor/haybale_graph_editor/farmhands/editor_tools.py` (new tool after `GraphEditorRedoTool` :1222)
- Test: `tests/graph_editor/test_warning_badge.py` (extend), `tests/farmhand/test_graph_editor_tools.py` (extend); check `tests/farmhand/test_tool_tiers.py` and `tests/farmhand/test_doc_keys_resolve.py` for lists of tools that must name the new one

**Interfaces:**
- Consumes: Task 3 (`Editor.apply_previous_setup`, `Editor.dismiss_previous_setup`).
- Produces:
  - `NodeSkin._render_diagnostics_button(errors, warnings, node_id, deprecation_str="", route: EditRoute | None = None)`; the call passes `self._nodeids_routes.get(node_id)`.
  - Popup: warnings grouped by `kind`. `"compatibility"` keeps the heading `Compatibility warnings` and the Reset tip. `"previous_setup"` gets heading `Previous setup`, the message, and two buttons `Apply previous setup` / `Dismiss previous setup`, each `stamp_requires(button, LevelMode.EDIT)`. A button's click calls `NodeSkin._resolve_previous_setup(route, node_id, apply: bool) -> None`: `editor = route.editor() if route else None`; `None` does nothing; else `editor.apply_previous_setup([node_id])` / `dismiss_previous_setup([node_id])`.
  - Farmhand tool, `registry_id="previous_setup"`, label `Previous setup`, `annotations=_MUTATING`, default tier (edit): `run(ctx, binding_id: str, node_ids: list[str], action: str) -> dict`. `ctx.fence(editor)`, then the Editor verb; `ctx.broadcast(GraphDataMutated())`. Errors: `FarmhandError("bad_action", ...)` unless action is `"apply"` or `"dismiss"`; `FarmhandError("no_previous_setup", ..., ids={"node_ids": node_ids}, help="Run graph_editor_inspect_node; a node holding one lists a 'previous_setup' warning.")` when the verb returns `False`. Summary `"Applied the previous setup of N node(s)."` / `"Dismissed ..."`.

- [ ] **Step 1: Write the failing tests**

```python
# test_warning_badge.py (source-wiring style of this file, plus a direct call)
def test_previous_setup_buttons_are_stamped_edit():
    src = inspect.getsource(NodeSkin._render_diagnostics_button)
    assert "Apply previous setup" in src and "Dismiss previous setup" in src
    assert "LevelMode.EDIT" in src

def test_resolve_previous_setup_goes_through_the_route_editor():
    calls = []
    class _Editor:
        def apply_previous_setup(self, ids): calls.append(("apply", ids))
        def dismiss_previous_setup(self, ids): calls.append(("dismiss", ids))
    class _Route:
        def __init__(self, editor): self._e = editor
        def editor(self): return self._e
    NodeSkin._resolve_previous_setup(_Route(_Editor()), "n1", apply=True)
    NodeSkin._resolve_previous_setup(_Route(None), "n1", apply=False)    # below edit: nothing
    NodeSkin._resolve_previous_setup(None, "n1", apply=False)
    assert calls == [("apply", ["n1"])]

# test_graph_editor_tools.py — follow the file's existing tool-call fixture
def test_previous_setup_tool_applies_and_refuses_bad_input(...):
    # reload a set printer in an open graph, call the tool with action="apply": message restored
    # action="bogus" -> bad_action; a node without one -> no_previous_setup
```

- [ ] **Step 2–4:** fail, implement, pass; run `uv run pytest tests/graph_editor/ tests/farmhand/ -q -n 4`.
- [ ] **Step 5: Commit** — `feat(graph-editor) apply or dismiss a previous setup from the card or a Farmhand tool (#46)`

---

### Task 7: Records

**Files:**
- Create: `docs/adr/0062-a-reload-keeps-the-previous-setup.md` (front matter as ADR 0059: `name`, `description`, `status: accepted`, `see-also: ADR-0059, ADR-0058, ADR-0061`, `level: framework`; sections Context / Decision / Considered / Consequences)
- Modify: `docs/adr/0059-reload-and-reset-are-undoable.md` — add `superseded-in-part-by: ADR-0062` to the front matter and one line at the top of Decision: "The hot-reload half is superseded by ADR 0062; Reset stands."
- Modify: `docs/adr/0061-errors-reach-the-ledger-at-named-boundaries.md` line 50 → "Backlog #46 is settled by ADR 0062: a reload keeps the previous setup, so nothing is lost; each node holding one gets a WARNING row."
- Modify: `docs/reference/glossary.md` — **Rebuild step** (:453): "The undo step a node Reset, Apply previous setup or Dismiss previous setup records (`RebuildNodesAction`) …", no hot reload. Add **Previous setup**: "The data a node had before a hot reload rebuilt it from new code, kept on the node until the user applies or dismisses it from the card's warning badge. Saved with the graph; not copied with the node. See ADR 0062 | reload snapshot, kept data (that is a stand-in's)".
- Modify: `docs/components/nodes/node-canon.md` § hot-reload — replace the limits paragraph (written in #37) with what happens now.
- Modify: `docs/superpowers/plans/2026-10-22-open-follow-ups.md` — mark #46 **DONE**; add two items: "Reveal a node inside a closed Group/Macro interior (Reveal finds only open editors, `haystack_editor.py:118`)" and "Aggregate interior errors and warnings onto the host card's badge".
- Modify: `internals/handoff/reload-without-history-loses-setup.md` — `status: done`, one line pointing to ADR 0062.

ADR 0062's Decision states the Decisions table above in prose (Q1, Q2, Q3, Q4/Q4b, Q9, Q10′, Q11, Q12, Q15); Considered: the undo step (ADR 0059 — undo reapplied old values over a code change about them, on whichever instance the user undid; silent without a history), a ledger-only notice (ADR 0061 line 50 — the decision belongs on the node), per-field rehydration (rejected in ADR 0059). Consequences: a reload is no longer undoable; default-change false positives; Dismiss costs a rebuild; nodes inside closed interiors are reached through the ledger row only.

- [ ] **Step 1:** write the records.
- [ ] **Step 2:** `uv run mkdocs build --strict` passes (new ADR wired into nav as `docs/reference/doc-authoring.md` describes).
- [ ] **Step 3:** full gate: `uv run ruff check . && uv run ruff format --check . && <CI mypy command from CLAUDE.md> && uv run pytest -m "not browser and not perf" -n 4 -q`, then `uv run pytest -m browser -n 4 -q`.
- [ ] **Step 4: Commit** — `docs(reload) ADR 0062: a reload keeps the previous setup; glossary, canon, backlog (#46)`
