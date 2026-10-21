# Error-Node Stand-In Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** A node wrapper always holds a node. When a node's class is missing or its constructor raises, an `ErrorNode` stands in: the graph stays editable, the card shows the error, and a save writes the node's original data back, so nothing is lost until the class works again.

**Architecture:** `NodeWrapper._instantiate` falls back to the registry's error node when the class constructor raises, as `NodeFactory.get_node` already does for an unknown key. Whenever the instance is the error node standing in for another key, the wrapper keeps that node's original `node_data` (from the file, or captured from the old instance before a failed rebuild). `serialize()` writes it back with the live props; `build()` without data rebuilds from it, so a fixed class or a returning library restores the real node with its values.

**Tech Stack:** Python, haywire core (`NodeWrapper`, `NodeFactory`, `BaseGraph`), pytest.

**Spec:** conversation 2026-10-21 (bug 6 reproduced live: `__init__` raising → `move_node` fails in `_check_canvas_size`, toolbar panels raise in `is_reroute_node` / `node_appearance_subject`, the card stays stale with no error badge; probe: an unknown-key `ErrorNode` saves its own `identity`/`library` and drops every settings bag but `props`). User chose option (d). Handoff: `internals/handoff/canvas-size-check-failed-node.md`.

## Global Constraints

- **Stand-in** = the error node (`NodeRegistry._get_error_node()`) held by a wrapper whose `registry_key` is not the error node's own key. Both causes produce one: unknown/failed-import key (factory fallback, `state.error_import`) and constructor raised (`state.error_instantiate`).
- A stand-in's saved `node_data` = its original `node_data`, except `"props"` and `"settings"["props"]`, which come from the live stand-in (position, label, colour and stage fields the user can change on the card). `identity`, `library`, other settings bags, `ports`, `store` stay exactly as the original.
- `NodeWrapper.node` raises only before the first build and after `cleanup()`; if the error node class itself fails to construct, today's no-instance behaviour remains (no further fallback).
- The real class's generic rebuild (`build()` with no data, e.g. a reset) is unchanged for a live real node: it runs `init()`. Only a stand-in's rebuild uses the kept data.

## Review Focus

1. **A failed hot reload of a node with edited values, then the fix**: the real node comes back with its values, position and edges — Task 1 test.
2. **Saving twice** (stand-in saved, reopened while still broken, saved again): data stays identical — Task 1 round-trip test runs the save→load→save loop.
3. **A stand-in that the user moves or relabels, then the class is fixed**: the real node takes the new position/label, not the file's — Task 1.
4. **Undo of deleting a stand-in** (`RemoveNodeAction` re-adds from `serialize()`): it comes back as a stand-in with the original data — Task 2 test.
5. **Copy/paste of a stand-in** (clipboard uses `serialize()`): the paste carries the original data — Task 2 test.

---

### Task 1: The wrapper always holds a node; a stand-in keeps and saves the original data

**Files:**
- Modify: `packages/haywire-core/src/haywire/core/node/factory.py` — public `get_error_node()`.
- Modify: `packages/haywire-core/src/haywire/core/node/node_wrapper.py` — `_instantiate` (:296-345), `build` (:264), `serialize` (:745), new `_stand_in_data`, `is_stand_in`.
- Modify: `tests/core/test_node/test_position_single_source.py:155-202` — three tests assert `_node_instance is None` after a failed construction; they now assert `wrapper.is_stand_in`.
- Create: `tests/core/test_node/conftest.py` — move the `construction_fails` fixture here (shared by both files).
- Test: `tests/core/test_node/test_stand_in.py` (new).

**Interfaces:**
- Produces: `NodeFactory.get_error_node() -> type[BaseNode]` (raises the same `HaywireException` as `get_node` when none is registered). `NodeWrapper.is_stand_in -> bool` (property: the instance is the error node and `registry_key` is not its key). `NodeWrapper._stand_in_data: dict | None`.

- [ ] **Step 1: Write the failing tests** in `test_stand_in.py` (integration; `graph_with_library_system`, `construction_fails`, `TestPrintNode` and `SettingsNode` keys from `class_identity.registry_key`, `isinstance`-check against `ErrorNode` from `haywire.barn.builtin.nodes.error_node`):
  - `test_a_constructor_failure_stands_in_an_error_node`: arm(1), `create_node_wrapper` → no raise; `isinstance(w.node, ErrorNode)`, `w.is_stand_in`, `w.state.error_instantiate is not None`, `w.registry_key` unchanged.
  - `test_the_graph_stays_editable_around_a_stand_in`: load a saved two-node graph with arm(1) (one fails) → `create_node_wrapper`, `move_node` on the healthy node, and `remove_node_wrapper` of it all succeed; the stand-in can be moved too.
  - `test_a_stand_in_saves_its_original_node_data`: save → `node_data` equals the original; then load that save (still failing) and save again → still equal.
  - `test_a_moved_stand_in_saves_its_new_position`: move the stand-in → saved `position_of(...) == new`, every other key equal to the original.
  - `test_an_unknown_class_keeps_its_settings_and_identity`: `SettingsNode` saved, `registry_key` changed to `haybale-testing:node:NoSuchNode`, loaded and saved → `node_data == original` (settings `example` bag, `identity`, `library` kept).
  - `test_a_failed_rebuild_keeps_the_values_for_the_fix`: create, set `message` to `"kept"`, move to (640, 320); arm(1) + `request_node_reset` → stand-in whose ports include `message`; reset again → real `TestPrintNode`, `message == "kept"`, position (640, 320), `not w.is_stand_in`, `_stand_in_data is None`.
- [ ] **Step 2:** `uv run pytest tests/core/test_node/test_stand_in.py -q` — Expected: FAIL (`RuntimeError: ... has no node instance`, settings/identity diffs).
- [ ] **Step 3: Implement.**
  - `_instantiate`: before cleaning up a live instance, capture its data — `self._node_instance._to_dict()` — unless it is already a stand-in (then keep the existing `_stand_in_data`). When `node_info` is given, it is the original. On a constructor exception: record `error_instantiate` as today, then construct `self._node_factory.get_error_node()(node_id, self)`, set the carried position on it, keep the original data in `_stand_in_data`, and return `True` so `_initialize` restores ports from that data. If the error node raises too, fall back to today's no-instance path (`_pending_position`).
  - `build(node_info=None)`: when `node_info` is falsy and `_stand_in_data` is set, build from `_stand_in_data` merged with the live stand-in's props (Global Constraints), so a moved/relabelled stand-in keeps those.
  - `_initialize`: a stand-in initializes from `_stand_in_data` when `node_info` is empty (the first failure inside a data-less rebuild captures the data in `_instantiate`, after `build` chose no data), never through `init()`.
  - An instance of the factory's error class for another key (unknown key) also sets `_stand_in_data` from `node_info`.
  - A successful build of the real class clears `_stand_in_data`.
  - `serialize()`: for a stand-in, `node_data` = deep copy of `_stand_in_data` with `"props"` and `"settings"]["props"]` replaced from the live instance's `_to_dict()`.
- [ ] **Step 4:** `uv run pytest tests/core/test_node/ tests/core/test_graph/ -q -n 4` — Expected: PASS.
- [ ] **Step 5: Commit** `fix(node): an error node stands in for a node that cannot be built, and saves its data back`.

### Task 2: Undo, clipboard and the canvas with a stand-in

**Files:**
- Test: `tests/core/test_node/test_stand_in.py` (extend), `tests/graph_editor/test_stand_in_canvas.py` (new).
- Modify only if a test fails: `packages/haywire-core/src/haywire/core/undo/actions/graph_actions.py` (remove/add node), clipboard copy path.

**Interfaces:**
- Consumes: `NodeWrapper.is_stand_in`, `serialize()` from Task 1.

- [ ] **Step 1: Write the tests.**
  - `test_undoing_the_delete_of_a_stand_in_restores_its_data`: `Editor` remove stand-in, `undo()` → wrapper back, `is_stand_in`, serialized `node_data` equal to the original.
  - `test_a_pasted_stand_in_carries_the_original_data`: copy the stand-in (`build clipboard payload` path used by `test_clipboard_payload.py`), paste → new wrapper's serialized `node_data` equals the original except `node_id`/position.
  - `test_stand_in_canvas.py::test_the_selection_toolbar_gates_read_a_stand_in`: `is_reroute_node(ctx)` and `node_appearance_subject(ctx)` with a stand-in selected return without raising.
  - `test_stand_in_canvas.py::test_the_canvas_refreshes_a_stand_in`: `on_validated` with `NODE_HOT_RELOADED` for a stand-in calls `refresh_node_visual` (a card is drawn for it).
- [ ] **Step 2:** run them — Expected: PASS if Task 1 covered the path; any FAIL is fixed in the named file (rule and ledger).
- [ ] **Step 3: Commit** `test(node): undo, paste and the canvas handle a stand-in`.

### Task 3: Docs, ADR, handoff

**Files:**
- Create: `docs/adr/0058-a-broken-node-keeps-its-data.md` — context (the two failure kinds, the crash and both save losses), decision (Global Constraints), consequences (`NodeWrapper.node` raises only before build/after cleanup; `_pending_position` only for an error node that cannot construct).
- Modify: `docs/reference/glossary.md` — new row after **NodeWrapper**: **Stand-in** — the `ErrorNode` a NodeWrapper holds when its node's class is missing or fails to construct; shows the error, keeps the node's place and connections, and saves the node's original data back. Alternatives to avoid: placeholder node, error node (the class).
- Modify: `packages/haywire-core/src/haywire/barn/builtin/nodes/error_node.py` — class docstring (displayed, Markdown): stands in for a node whose class is missing or fails to build; the file keeps the original node; fixing the class or installing the library restores it.
- Delete: `internals/handoff/canvas-size-check-failed-node.md` (resolved; its "Related" save-loss item is this plan).
- [ ] **Step 1:** write the docs.
- [ ] **Step 2:** full gate: ruff check, ruff format --check, mypy (CLAUDE.md list), `uv run pytest -m "not browser and not perf" -n 4`, `uv run pytest -m browser -n 4` — Expected: clean.
- [ ] **Step 3: Commit** `docs: ADR 0058, stand-in glossary entry, ErrorNode docstring`.

### Task 4: Live check (user)

- [ ] `PrintNode.__init__` raising: the card turns into an error card with the "Instantiate Node" error; moving, adding, deleting other nodes works; no panel errors in the log.
- [ ] Save while broken, remove the `__init__`: the node returns with its message value and edges.
- [ ] Rename a node's `registry_key` in a `.haywire` file to an unknown one, open, save, diff: only nothing (or the props you changed) differs.
