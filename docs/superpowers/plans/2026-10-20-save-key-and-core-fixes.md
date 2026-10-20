# Ctrl+S, the Structural-Dirty Flag and Update Macro Errors — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** This plan does three things:
- A node re-checks its structure after every change, also on an inline scheduler.
- Update Macro… can neither write a broken macro nor crash.
- Ctrl+S saves in the graph, haystack and code editors, also while a text field has focus.

**Architecture:**
- **The flag:** `mark_as_structuraly_dirty` sets its flag before it asks for validation.
- **Macro loading:** a failed load raises, restores the entry from its file, and the caller turns the error into a notice.
- **The key:** `Save` is a new `EditorCommand` (`Mod+S`). A new `in_text_fields` ClassVar lets a command fire while a text field has focus. The key listener blurs and refocuses an `input` or `textarea` first, so a pending value commits.

**Tech Stack:** Python 3.12, NiceGUI 3.13 (Vue), pytest, Playwright harness.

**Spec:** this conversation's rulings, 2026-10-20 (no spec file):
- Items 3, 4 and 11 of the follow-up list.
- **Q1 (a):** an error after the Update Macro swap is caught and reported, and the swap is left in place for Undo.
- **Q2 (c):** Ctrl+S works in the graph, haystack and code editors.
- **Q3 (b):** Ctrl+S fires from text fields; a focused `input` or `textarea` is blurred and refocused first.
- **Standing ruling (editor modes):** Save needs real edit access and ignores the canvas lock.
- **Handoff:** `internals/handoff/edit-instance-followups.md` §1 and §2.

## Global Constraints

- Work on branch `fix/save-key-and-core-fixes`, off `master` (`881ac8c6`).
- Docstrings and comments follow `.claude/rules/python-docs.md`.
- Tests use only files under `tests/` or `barn/haybale-testing`.
- Command id `save`, label `Save`, keys `("Mod+S",)`, access `AccessTier.EDIT`, `in_text_fields = True`.
- Bug 3 touches core validation, so run the full gate (`-m "not browser and not perf" -n 4` and `-m browser -n 4`) before that commit.

## Review Focus

1. **Ctrl+S inside a dialog must not save the editor behind it.** The dialog exemption stays. Task 4 tests it in the browser.
2. **Ctrl+S in a commit-mode text widget (Enter/blur) must save the value just typed,** not the old one. The blur must reach the server before the command does. Task 4 adds a browser test that the blur fires before `hw-command`.
3. **Ctrl+S in the code editor keeps the caret.** CodeMirror (`.cm-editor`) is not blurred. Task 4 tests it in the browser.
4. **Ctrl+S on a locked graph canvas saves.** A viewer (below edit) gets no binding, so the browser keeps its own Ctrl+S. Task 4 tests both.
5. **A validation pass that raises must not leave the flag set** (handoff §1). Task 1 tests it.

---

### Task 1: The structural-dirty flag (bug 3)

**Files:**
- Modify: `packages/haywire-core/src/haywire/core/node/node_wrapper.py:637-649`
- Test: `tests/core/test_node/test_structural_dirty_inline.py` (new)
- Modify: `tests/haystack/test_update_macro.py:343-363` (drop `_ParkedScheduler`, use `SyncScheduler`)

**Interfaces:** none new.

- [ ] **Step 1: Write the failing tests.** In `test_structural_dirty_inline.py`, on a graph built with `SyncScheduler()`:
  - `test_a_pin_added_after_the_first_validation_is_validated`: build a node with a dynamic port. Validate once, add a pin, call `wrapper.mark_as_structuraly_dirty()`, connect an edge to the new pin, and assert the edge validates (`edge_wrapper.is_valid`). Take the node key from `Cls.class_identity.registry_key` and `isinstance`-check the node.
  - `test_the_flag_clears_after_an_inline_pass`: after `mark_as_structuraly_dirty()`, assert `wrapper._is_dirty_structural is False`.
  - `test_a_pass_that_raises_leaves_the_flag_clear`: patch `graph._validation.mark_node_dirty` to raise. Assert the call raises and `wrapper._is_dirty_structural is False`.
- [ ] **Step 2:** Run `uv run pytest tests/core/test_node/test_structural_dirty_inline.py -v`. Expected: the first two FAIL.
- [ ] **Step 3: Implement.** Set `self._is_dirty_structural = True` before `mark_node_dirty`, inside the same lock. Wrap the call in `try/except BaseException`: on an exception, reset the flag to `False` and re-raise. Comment: `# Set before the call: an inline scheduler validates inside it and clears the flag.`
- [ ] **Step 4:** In `test_update_macro.py`, delete `_ParkedScheduler` and switch the test to a plain `SyncScheduler`. Run `uv run pytest tests/haystack/test_update_macro.py tests/core/test_node/ -q`. Expected: PASS.
- [ ] **Step 5:** Run the full gate. Expected: green.
- [ ] **Step 6:** Commit: `fix(node): a node re-checks its structure after every change, also on an inline scheduler`.

### Task 2: A failed macro load leaves the macro untouched (bug 4, part 1)

**Files:**
- Modify: `barn/haybale-haystack/haybale_haystack/state/haystack_state.py:327-386` (`open_macro_with`, `_open_document`)
- Test: `tests/haystack/test_update_macro.py`

**Interfaces:**
- Produces: `open_macro_with` raises `ValueError(f"'{name}' could not be loaded")` when `load_from_dict` returns `False`.
  - For a reused entry, the entry is first reloaded from its file. It stays clean, and its undo history is kept.
  - For a new entry, nothing is registered.

- [ ] **Step 1: Write the failing tests.**
  - `test_a_failed_load_into_an_open_macro_restores_it`: open the macro clean. Patch `BaseGraph.load_from_dict` to return `False` for the document, using a `side_effect` that calls through for the file reload. Assert `open_macro_with` raises `ValueError`, `entry.unsaved is False`, and the node set equals the file's.
  - `test_a_failed_load_into_a_new_entry_registers_nothing`: assert it raises and `str(path) not in hs._entries`.
- [ ] **Step 2:** Run them. Expected: FAIL.
- [ ] **Step 3: Implement.**
  - **Reused entry:** on `False`, call `existing.graph.load_from_file(str(path))` and `force_validation()`, then raise.
  - **New entry:** in `_open_document`, when `document is not None` and the load returns `False`, raise before registering.
  - Update the `Raises:` sections.
- [ ] **Step 4:** Run `uv run pytest tests/haystack/ -q`. Expected: PASS.
- [ ] **Step 5:** Commit: `fix(haystack): a macro document that fails to load leaves the macro as it was`.

### Task 3: Update Macro… reports an error after the swap (bug 4, part 2; Q1 a)

**Files:**
- Modify: `barn/haybale-haystack/haybale_haystack/panels/graph/menu/macro.py:236-247`
- Test: `tests/haystack/test_update_macro.py`

- [ ] **Step 1: Write the failing test.** In `test_an_error_opening_the_macro_after_the_swap_is_reported`, patch `HaystackState.open_macro_with` to raise `ValueError("boom")`, then call `_update_macro`. Use the existing UI-test pattern in that file.
  - No exception escapes.
  - A warning notice names the macro and says that Undo restores the instance.
  - The card is a placement (the swap stands).
  - `editor.history_manager.can_undo()` is true.
- [ ] **Step 2:** Run it. Expected: FAIL, because the exception propagates.
- [ ] **Step 3: Implement.** Wrap the `hs.open_macro_with` call. On `Exception`, log it and `ui.notify(f"Could not open {label}: {exc}. Undo restores the instance.", type="warning", multi_line=True)` under `with client:`, then return. Also fix the pluralisation of the following notice (item 27): "1 placement in 1 open graph".
- [ ] **Step 4:** Run `uv run pytest tests/haystack/ -q`. Expected: PASS.
- [ ] **Step 5:** Commit: `fix(haystack): Update Macro… reports a macro it cannot open instead of raising`.

### Task 4: Ctrl+S (item 11; Q2 c, Q3 b)

**Files:**
- Modify: `packages/haywire-core/src/haywire/core/signals/signal.py` (`EditorCommand.in_text_fields`), `packages/haywire-core/src/haywire/core/signals/vocabulary.py` (`Save`, `__all__`), `packages/haywire-core/src/haywire/core/signals/__init__.py` (export)
- Modify: `packages/haywire-core/src/haywire/ui/keymap/keymap.py` (`to_client` gains `"text_fields"`)
- Modify: `packages/haywire-core/src/haywire/ui/components/keymap/keymap_listener.vue` (`onKeyDown`)
- Modify: `barn/haybale-graph-editor/haybale_graph_editor/editors/graph_editor.py` (`accepts_command`, `@react_on(Save)`)
- Modify: `barn/haybale-haystack/haybale_haystack/editors/haystack_editor.py` (`@react_on(Save)` → `_on_save_haystack_in_place`)
- Modify: `barn/haybale-studio/haybale_studio/editors/code_editor.py` (`@react_on(Save)` → `_save`)
- Modify: `tests/ui/harness/routes.py` (`/keymap` route: add `"Mod+S": "save"` and `"text_fields": ["save"]`, plus a commit-on-blur input and a `.cm-editor` div)
- Modify: `docs/guides/signals.md:239-250` (table row + `in_text_fields`; "one of the eight above" becomes nine)
- Test: `tests/ui/keymap/test_keymap.py`, `tests/core/signals/test_editor_command.py`, `tests/graph_editor/test_graph_editor_commands.py`, `tests/ui/harness/test_keymap_listener.py`, `tests/studio/` (code editor), `tests/haystack/` (haystack editor)

**Interfaces:**
- Produces: `EditorCommand.in_text_fields: ClassVar[bool] = False`, documented in its Attributes as "fires while a text field or code editor has focus; a focused `input` or `textarea` is blurred and refocused first, so its pending value is committed."
- Produces: `Save(EditorCommand)` with `command_id="save"`, `label="Save"`, `default_keys=("Mod+S",)`, `access=AccessTier.EDIT`, `in_text_fields=True`.
- Produces: `Keymap.to_client()` returns an extra key, `"text_fields": [command_id, ...]`, sorted.

- [ ] **Step 1: Write the failing Python tests.**
  - `test_keymap.py::test_text_field_commands_reach_the_client`: build a keymap from an editor subscribing to `Save` and `Copy`. Assert `to_client()["text_fields"] == ["save"]`.
  - `test_keymap.py::test_save_binds_mod_s_for_an_editor_that_reacts_to_it`, and that a VIEW-tier principal gets no `Mod+S`.
  - `test_graph_editor_commands.py::test_save_is_accepted_on_a_locked_canvas`: with the level locked (mode OPERATE) and a principal at EDIT, `accepts_command(ctx, Save(binding_id=...))` is True, and the handler calls `_save_graph(context)`.
  - The haystack and code editor each get a test that `Save` reaches `_on_save_haystack_in_place` / `_save`. Discover the handlers with `discover_handlers` or call them directly.
- [ ] **Step 2:** Run them. Expected: FAIL (`Save` not defined).
- [ ] **Step 3: Implement the Python side.**
  - Add the ClassVar and `Save`.
  - `to_client` lists `in_text_fields` commands.
  - `GraphEditor.accepts_command` lets `Save` through with the toggles; the handler checks `context.can_edit()` (`_save_graph` already does).
  - Add the three `@react_on(Save)` handlers.
- [ ] **Step 4: Write the failing browser tests** in `test_keymap_listener.py`:
  - `test_save_fires_inside_a_text_field`: focus the `ed::one` input, press `Control+s`. Expect `#last-command` == `save@ed::one`, and that `keydown`'s `defaultPrevented` is True.
  - `test_save_blurs_the_field_before_the_command`: the commit-on-blur input logs `blur` to `#command-log` through its own `change` listener. After `Control+s`, the log reads `blur,save@ed::one` in that order, and the input has focus again.
  - `test_save_keeps_focus_in_a_code_editor`: focus the `.cm-editor` div (`contenteditable`), press `Control+s`. Expect `save@ed::one`, `document.activeElement` unchanged, and no `blur` logged.
  - `test_save_inside_a_dialog_is_native`: focus `#dialog-button`, press `Control+s`, and `_expect_only_sentinel`.
  - `test_other_keys_stay_native_in_a_text_field`: the existing `test_keys_native_inside_text_field` still passes, since `Mod+A` is not in `text_fields`.
- [ ] **Step 5:** Run them. Expected: FAIL.
- [ ] **Step 6: Implement the listener.** In `onKeyDown`:
  - When `keepsNativeKeys(e.target)` is true, continue only if the target is not in a dialog and the resolved combo's command is in `keymap.text_fields`.
  - Before `emitCommand`, if `document.activeElement` is an `INPUT` or `TEXTAREA`, call `el.blur(); el.focus();` so a commit-on-blur widget sends its value first. The websocket keeps the order.
  - Leave `contenteditable` and `.cm-editor` alone: CodeMirror streams every change.
- [ ] **Step 7:** Run `uv run pytest tests/ui/keymap tests/core/signals tests/graph_editor tests/studio tests/haystack -q -n 4` and `uv run pytest tests/ui/harness/test_keymap_listener.py -q`. Expected: PASS.
- [ ] **Step 8: Docs.**
  - `signals.md`: add the `Save | save | Mod+S | edit` row, one sentence on `in_text_fields`, and "nine" commands.
  - `graph_editor.py:1070`: the tooltip shows the platform combo through `display_combo` if that is how the other tooltips do it; otherwise keep "Save (Ctrl+S)".
- [ ] **Step 9:** Commit: `feat(editors): Ctrl+S saves the graph, haystack and code editors`.

### Task 5: Gate and live check

- [ ] **Step 1:** Run the full gate: ruff, ruff format, mypy, the non-browser suite and the browser suite. Expected: green.
- [ ] **Step 2:** Update the handoff `internals/handoff/edit-instance-followups.md`: §1, §2 and the pluralisation polish item are done, and the remaining items stay open.
- [ ] **Step 3: Live check by the user,** in Chrome and Firefox:
  1. A graph with unsaved edits: Ctrl+S saves (notice, dirty dot cleared), and the browser's save dialog doesn't appear.
  2. The same on a locked canvas.
  3. Type into a node's text widget in commit mode, press Ctrl+S without Enter, then reopen: the new value was saved.
  4. Ctrl+S in the haystack editor saves the haystack.
  5. Ctrl+S in the code editor saves the file and the caret stays where it was.
  6. Ctrl+S in an open dialog (e.g. port edit) does nothing to the graph.
