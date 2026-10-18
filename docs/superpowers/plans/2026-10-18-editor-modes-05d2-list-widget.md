# Editor modes, slice 5d-2: list widget — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** A setting can hold a list (`setting[ArrayType[T]]`) and be edited, saved, promoted and linked like any other setting. An opt-in `ArrayWidget` edits such a list one row per item, each row drawn by the item type's own widget. `TextWidget` gains a commit mode that writes on Enter or blur instead of on every keystroke. 5d-3's Menu node (options) and Text node (commit) build on both.

**Architecture:**
- **Spike first (Task 1).** No setting uses `ArrayType` today. A pre-plan probe (2026-10-18) showed the cell, a bag's save/load and reset already work for `setting[ArrayType[STRING]]`. Promotion, graph round trip and edges are untested, so Task 1 pins them as characterization tests on `SettingsNode` before any widget exists.
- **`ArrayWidget` delegates like `OptionalWidget`.** It reads the item type off the cell (`type_cls.element_type_cls`), looks up that type's declared `widget_key` and builds one inner widget per item. Each inner widget gets a per-row `WidgetModel` that shares the outer cell for change notification and reads and writes one index of the list. Every write is a new list through the outer model, so it takes the outer widget's edit route.
- **Opt-in (Q27 B).** `ArrayType` declares no `widget_key`. A port or setting names it with `widget=ArrayWidget.config(...)`. No existing graph changes look.
- **Commit mode** is a `TextWidget` property. The input stays bound model→view, and the write moves from `update:value` to the input's `keydown.enter` and `blur` events.

**Tech Stack:** Python 3.12, NiceGUI 3 / Quasar, pytest, Playwright browser tier.

**Spec:** [2026-10-12-editor-modes.md](2026-10-12-editor-modes.md) (Sequence 5d-2), as settled by the user's 5d inquisition of 2026-10-18: Q10 B (commit on Enter or blur), Q25 C (an `ArrayType[STRING]` setting plus a list widget, modelled on `FillWidget`), Q26 C (generic delegation; `STRING`, `INT` and `FLOAT` tested), Q27 B (opt-in), Q29 A (5d-2 opens with the spike).

## Global Constraints

- **Branch:** work directly on `feat/editor-modes-slice1` in the main checkout, starting from `63083b5f`. There is no worktree and no slice branch. After the user's live check, the slice's commits are squashed into one: tag the tip `editor-modes-slice5d2-full` first, then `git reset --soft 63083b5f` and commit. Nothing goes to master until slice 6 lands.
- **The user's uncommitted files** (`docs/components/nodes/node-canon.md`, `.scratch/docs-story/`) share this checkout. Leave them alone: stage explicit paths only, never `git add -A` or `git add .`.
- **No existing look changes (Q27 B):** `ArrayType`'s `@type` keeps no `widget_key`. `TextWidget` without `commit` behaves exactly as today.
- **Tested item types (Q26 C):** `STRING`, `INT`, `FLOAT`. Other item types render through the same delegation untested. An item type with no registered widget shows a read-only summary.
- **Placement:** `ArrayType` lives in `haybale-core`, so `ArrayWidget` does too (`barn/haybale-core/haybale_core/widgets/`, already a registered widget folder). `haywire-core` never imports it.
- **haybale-testing trap:** `tests/studio/test_docs/test_generate.py` reverts uncommitted edits under `barn/haybale-testing/`. Commit each task's edits there before running the docs test or a full suite.
- **Tests and docs:** use the smallest test tier while iterating, then the full gates at the end. Docstrings follow `.claude/rules/python-docs.md`; `ArrayWidget`'s class docstring is a displayed docstring (Markdown).

## Amendment (2026-10-18, after the build)

The user asked for a drag handle instead of the move up/down buttons. Each row is `[grip] [item widget] [remove]`; the rows column is `make_sortable(group=<per widget>, handle=".hw-array-grip")`, as in the Ports panel. A drop calls `ArrayWidget._reorder(old_index, new_index)`, which writes the moved list and then redraws the rows from the model, accepted or refused. The grip carries `data-interactive="true"` and `data-array-grip="{i}"`. `hui.icon.move_up`/`move_down` are not added. This supersedes the up/down parts of Decisions 4 and 7.

## Decisions

1. **Spike fields.** `SettingsNode.example` gains, in a new `category="array"`:
   - `example_string_list = setting[ArrayType[STRING]](["One", "Two", "Three"], label="Example String List")`
   - `example_int_list = setting[ArrayType[INT]]([1, 2, 3], label="Example Int List")`
   - `example_float_list = setting[ArrayType[FLOAT]]([0.5, 1.5], label="Example Float List")`

   Task 3 adds `widget=ArrayWidget.config()` to all three.
2. **Spike stop rule.** A Task 1 test that fails needs a fix local to `ArrayField` or `haywire.core.node.promotion` (a missing copy, a wrong recipe). If the fix reaches further (the settings value model, the port binding, the edge pipe), stop and report the failing test and its cause to the user before Task 2.
3. **Commit mode.** `TextWidget.config(properties={"commit": True})`.
   - The input is bound `one_way=True` (model→view only).
   - `keydown.enter` and `blur` call `TextWidget._commit()`. It writes `str(input.value)` through `self.set_value` unless it equals the model's current value, in which case it writes nothing.
   - The expand-to-modal button is unchanged; its confirm is already a commit.
   - The `TextWidget` docstring lists `commit` (bool, default `False`): "Write only on Enter or when the field loses focus. While typing, nothing is written."
4. **`ArrayWidget`** in `barn/haybale-core/haybale_core/widgets/array_widget.py`, `@widget(description="List editor — one row per item, each drawn by the item type's widget")`.
   - **Config:** `properties.item` (dict, default `{}`) is the widget config properties handed to every row, layered over the item type's declared widget config. Example: `ArrayWidget.config(properties={"item": {"commit": True}})` gives commit-mode text rows.
   - **Layout:** a column of rows, then an Add button. Each row is `[item widget (flex-1)] [move up] [move down] [remove]`, as flat dense `size=xs` buttons. Up is hidden on the first row and down on the last.
   - **DOM hooks:** the root carries `data-array`, each row `data-array-row="{i}"`, and the controls `data-array-up="{i}"`, `data-array-down="{i}"`, `data-array-remove="{i}"` and `data-array-add`.
   - **Add** appends the item type's declared default (`class_identity.default["value"]`: `""`, `0`, `0.0`).
   - **Every edit builds a new list** from `get_value()` and writes it with `self.set_value(new_list)`. `ArrayField` stores the list it is handed.
   - **Rows rebuild only when the item count changes** (add, remove, or an external write such as reset or undo), as in `FillWidget._render_stops`. Rebuilding cleans up every old row widget first. An edit or a reorder keeps the rows, and each row re-reads its index.
   - **An item type with no widget** shows one read-only label, `"{n} items"`, with no rows and no controls (Q26 C).
5. **Row model (`_ItemModel`)**, private to `array_widget.py`, satisfying `WidgetModel`:
   - `id = f"{outer.id}__{index}"`, and `widget_config = {"properties": {**item type props, **item}}`.
   - `data` returns an `_ItemField` view of the outer cell (below).
   - `get_value()` returns `outer.get_value()[index]`, or the item default if the index is past the end. A row can still be called once after a shrink, because `Event` dispatches over its live handler list.
   - `set_value(v)` coerces `v` through a fresh item field (`item_cls.create_field()`, `set_value(v)`, `get_value()`), so an `INT` row stores an `int`. It then returns `outer.set_value(list with index replaced)`.
6. **`_ItemField`**, private, presents the outer cell as a field of the item type. It holds exactly what the inner widgets read:
   - `type_cls` is the item type, and `get_stored_type()` returns the item type. `NumberWidget`'s `INT` check needs this.
   - `on_changed` is an instance attribute set to the outer cell's `Event` object, so `+=` and `-=` act on the outer event.
   - `has_linked_value()` and `accepts_own_value()` delegate to the outer cell.
7. **Icons:** `hui.icon` gains `move_up = "arrow_upward"` and `move_down = "arrow_downward"` (`packages/haywire-core/src/haywire/ui/elements/icons.py`). Add and remove use the existing `add` and `close`.

## Review Focus

1. **External shrink.** A reset or undo makes the list shorter while every row is subscribed. Nothing raises, and the rows rebuild to the new count. Test: Task 3 `test_an_external_shrink_rebuilds_rows_without_error`.
2. **A linked, promoted inlet.** The rows show the linked value. Edit, Add, Remove and move all leave the model unchanged. Test: Task 3 `test_a_linked_list_refuses_every_edit`.
3. **A refused write** (a locked canvas, or a route that says no). After Add or Remove the model is unchanged, and the rows redraw to it. Test: Task 3 `test_a_refused_add_redraws_the_model`.
4. **No shared list.** Editing one node's list leaves another node's list and the declared default alone; Reset restores `["One", "Two", "Three"]`. Test: Task 1 `test_two_nodes_never_share_a_list`.
5. **A commit without a change.** Focusing and blurring a commit-mode field writes nothing (no undo step). Enter after typing writes exactly once. Test: Task 2 `test_a_blur_without_change_writes_nothing`, `test_enter_writes_once`.

---

### Task 1: Spike — `setting[ArrayType[T]]`

**Files:**
- Modify: `barn/haybale-testing/haybale_testing/nodes/testbed/settings_node.py` (Decision 1)
- Test: `tests/core/test_settings/test_array_setting.py` (new; `pytest.mark.integration`, fixtures `graph_with_library_system`, `library_system`, as in `tests/core/node/test_promotion_roundtrip.py`)

**Interfaces:**
- Produces: `SettingsNode.example.example_string_list`, `example_int_list`, `example_float_list`.

- [ ] **Step 1: Write the tests.** Node key `"haybale-testing:node:SettingsNode"`; the port id is the field's `storage_key`.
  - `test_an_array_setting_reads_a_copy`: mutating the list read from `node.example.example_string_list` leaves the next read `["One", "Two", "Three"]`.
  - `test_two_nodes_never_share_a_list`: write `["A"]` on node 1. Node 2 reads `["One", "Two", "Three"]`. After `node1.example._reset("example_string_list")`, node 1 reads `["One", "Two", "Three"]`.
  - `test_an_array_setting_round_trips_with_the_node`: write `["A", "B"]` and `[4, 5]`. `_to_dict()` into a fresh node via `_initialize_from_dict` reads both back, and the int items are `int`.
  - `test_a_default_list_saves_no_value`: an untouched node's `_to_dict()["settings"]["example"]["values"]` has none of the three keys.
  - `test_a_promoted_list_port_carries_the_array_type`: `promote_setting(node, "example", "example_string_list", PortType.INLET)`. Then `port.type_cls is ArrayType[STRING]`, and `port._data is node.example._cell_for(desc)`.
  - `test_a_promoted_list_survives_a_graph_round_trip`: promote as INLET, write `["A"]`, then `graph.to_dict()`, `graph.clear()`, `graph.load_from_dict(data)`. The port exists and the setting reads `["A"]`.
  - `test_a_list_flows_over_an_edge_between_promoted_ports`: promote as OUTLET on node 1 and INLET on node 2, and connect with `graph.create_edge_wrapper`. Writing `["X", "Y"]` on node 1, then `sink_port.resolve_dirty_data()`, makes node 2's port read `["X", "Y"]`. Repeat for `example_float_list`.
  - `test_demoting_a_list_keeps_its_value`: promote, write `["A"]`, `demote_setting`. The setting reads `["A"]`.
  - `test_a_list_promotes_to_config`: as `PortType.CONFIG`; `port.is_config()`.
- [ ] **Step 2:** Run `uv run pytest tests/core/test_settings/test_array_setting.py -q`. Expected: the import works (Decision 1 is in place). Record which tests fail. Fix each failure under Decision 2's stop rule, adding the fix to the module that owns it.
- [ ] **Step 3:** Run the tests again, plus `tests/core/node/ tests/core/test_settings/ -q`. Expected: PASS.
- [ ] **Step 4:** Commit `test(settings): pin setting[ArrayType[T]] — cell, save/load, promotion, edges`. Its message lists each spike fix, or says none was needed.

### Task 2: `TextWidget` commit mode

**Files:**
- Modify: `packages/haywire-core/src/haywire/barn/builtin/widgets/basic_widgets.py` (`TextWidget`)
- Modify: `tests/ui/harness/routes.py`: new route `/list-widget`, modelled on `/fill-widget`. A fresh `NodeData` per load holds one port, `STRING.as_config(id="text_commit", widget=TextWidget.config(properties={"commit": True}))`. It renders through `render_widget` with a `SettingWidgetModel` whose `on_edit` writes the port and counts calls. A polled echo `data-testid="echo-text_commit"` shows `f"{value}|{writes}"`. End with `_stamp_synced()`.
- Test: `tests/ui/widget/test_text_widget_commit.py` (new; integration, a headless `Client` as in `test_optional_widget.py`), `tests/ui/harness/test_list_widget.py` (new; browser)

**Interfaces:**
- Produces: the `commit` property of `TextWidget`, and the `/list-widget` route (Task 3 adds ports to it).

- [ ] **Step 1: Write the failing tests:**
  - Headless. Existing widget tests drive edits through `widget._bindings[0]._sync_to_model(v)` (see `test_linked_widget_writes.py`), and these follow that pattern:
    - `test_commit_mode_binds_one_way`: with `commit`, `widget._bindings[0].mode is BindingMode.ONE_WAY`; without it, `TWO_WAY` (today's behaviour).
    - `test_commit_writes_the_typed_text_once`: set the inner `ui.input`'s `.value = "abc"`, and `on_edit` is not called. `widget._commit()` calls it once with `"abc"`. A second `_commit()` adds no call.
    - `test_commit_mode_still_shows_model_changes`: `cell.set_value("zz")` shows `"zz"` in the input.
  - Browser, using `goto_ready`:
    - `test_enter_writes_once`: type `"/data/scene.json"` into the `text_commit` input. The echo stays `"|0"`. Press Enter, and the echo becomes `"/data/scene.json|1"`.
    - `test_blur_commits`: type `"abc"`, then click the page body. The echo becomes `"abc|1"`.
    - `test_a_blur_without_change_writes_nothing`: focus the input, then blur. The echo stays `"|0"`.
- [ ] **Step 2:** Run `uv run pytest tests/ui/widget/test_text_widget_commit.py -q`. Expected: FAIL.
- [ ] **Step 3:** Implement Decision 3.
- [ ] **Step 4:** Run the tests again, plus `tests/ui/widget/ -q` and `uv run pytest -m browser -n 4 tests/ui/harness/test_list_widget.py tests/ui/harness/test_widgets.py -q`. Expected: PASS.
- [ ] **Step 5:** Commit `feat(widgets): TextWidget commit mode — write on Enter or blur`.

### Task 3: `ArrayWidget`

**Files:**
- Create: `barn/haybale-core/haybale_core/widgets/array_widget.py` (Decisions 4–6)
- Modify:
  - `packages/haywire-core/src/haywire/ui/elements/icons.py` (Decision 7)
  - `barn/haybale-testing/haybale_testing/nodes/testbed/settings_node.py` (`widget=ArrayWidget.config()` on the three list fields)
  - `tests/ui/harness/routes.py`: `/list-widget` gains three ports, `ArrayType[STRING|INT|FLOAT].as_config(id="strings"|"ints"|"floats", default=..., widget=ArrayWidget.config())`, with defaults `["One", "Two", "Three"]`, `[1, 2, 3]` and `[0.5, 1.5]`. Each has its own polled echo, `data-testid="echo-<id>"` showing `repr(value)`.
- Test: `tests/ui/widget/test_array_widget.py` (new; integration, headless `Client`. Its autouse fixture registers the builtin widgets plus `ArrayWidget` and restores `WIDGET_REGISTRY`, as in `test_optional_widget.py`), `tests/ui/harness/test_list_widget.py` (append)

**Interfaces:**
- Consumes: the `commit` property (Task 2), the `/list-widget` route (Task 2).
- Produces: `ArrayWidget` (tests take its key from `ArrayWidget.class_identity.registry_key`), `hui.icon.move_up` and `hui.icon.move_down`. 5d-3's Menu declares `widget=ArrayWidget.config(properties={"item": {"commit": True}})`.

- [ ] **Step 1: Write the failing tests.** `_rendered(item_cls, initial, widget_config=None, on_edit=None)` builds an `ArrayType[item_cls]` cell (`create_field(default_override={"value": initial})`) and a `SettingWidgetModel` whose default `on_edit` writes the cell. It returns `(widget, cell, edits)`.
  - `test_each_item_gets_its_type_widget`: for `STRING`, the rows hold `TextWidget`s; for `INT` and `FLOAT`, `NumberWidget`s. There is one row per item.
  - `test_an_int_row_steps_in_whole_numbers`: an `INT` row's `NumberDrag` has `precision == 0` and `step == 1`.
  - `test_a_row_edit_writes_a_new_list`: a row model `set_value("B")` at index 1 of `["a", "b"]` gives `cell.get_value() == ["a", "B"]`, and the written list is not the object read before.
  - `test_an_int_row_stores_ints`: row `set_value(4.0)` stores `4`, an `int`.
  - `test_add_appends_the_item_default`: Add on `STRING`, `INT` and `FLOAT` appends `""`, `0` and `0.0`. The row count grows by one.
  - `test_remove_and_move`: on `["a", "b", "c"]`, remove index 1 gives `["a", "c"]`; move index 0 down gives `["c", "a"]`; move index 1 up gives `["a", "c"]`.
  - `test_the_end_rows_hide_their_outward_move`: row 0's up button and the last row's down button are not visible.
  - `test_an_external_shrink_rebuilds_rows_without_error`: `cell.set_value(["x"])` on a three-row widget raises nothing, and one row remains.
  - `test_an_edit_keeps_the_rows`: a row edit leaves the same row widget objects in place (no rebuild).
  - `test_a_rebuild_releases_old_rows`: after Add then Remove, `cell.on_changed.handler_size()` equals its value right after render.
  - `test_a_refused_add_redraws_the_model`: with `on_edit` returning `False`, Add leaves the cell unchanged and the row count at its old value.
  - `test_a_linked_list_refuses_every_edit` (`graph_with_library_system`): a promoted `example_string_list` INLET fed by an edge from a promoted OUTLET. A row edit, Add, Remove and move each leave the sink's value equal to the linked value.
  - `test_item_config_reaches_every_row`: `ArrayWidget.config(properties={"item": {"commit": True}})` gives each `TextWidget` row `_config["properties"]["commit"] is True`.
  - `test_an_item_type_without_a_widget_shows_a_summary`: an `ArrayType` of an item type whose `widget_key` is unregistered shows the label `"2 items"`, with no `data-array-row` and no `data-array-add`.
  - Browser, in `test_list_widget.py`:
    - `test_a_string_row_edit_reaches_the_model`: fill row 1 of `strings` with `"Deux"`. The echo becomes `"['One', 'Deux', 'Three']"`.
    - `test_add_remove_and_reorder_in_the_browser`: click `[data-array-add]` on `ints`, then `[data-array-remove="0"]`, then `[data-array-up="1"]`. The echo goes `[1, 2, 3, 0]`, then `[2, 3, 0]`, then `[2, 0, 3]`.
    - `test_a_float_row_drags`: click a `floats` row's `NumberDrag` and type `2.5` + Enter. The echo shows `2.5` at that index.
    - `test_the_settings_panel_draws_list_rows`: on `/node?class=haybale_testing.nodes.testbed.settings_node.SettingsNode&bag=example`, `[data-field="example_string_list"] [data-array-row]` has count 3.
- [ ] **Step 2:** Run `uv run pytest tests/ui/widget/test_array_widget.py -q`. Expected: FAIL (import error).
- [ ] **Step 3:** Implement Decisions 4–7. The class docstring (Markdown) shows declaring it on a setting and a port, plus the `item` property.
- [ ] **Step 4:** Run the tests again, plus `tests/ui/widget/`, `tests/core/test_settings/test_array_setting.py`, `tests/barn/` and `uv run pytest -m browser -n 4 tests/ui/harness/test_list_widget.py tests/ui/harness/test_widgets.py tests/ui/harness/test_fill_widget.py -q`. Expected: PASS.
- [ ] **Step 5:** Commit `feat(haybale-core): ArrayWidget — opt-in list editor delegating each row to its item widget`.

### Task 4: Docs and gates

**Files:**
- Modify:
  - `docs/components/widgets/widget-canon.md`: after "Delegating to another type's widget", add "Delegating per item: `ArrayWidget`". It covers the per-row model (shared cell, one index, a new list per write), why rows rebuild only on a count change, `_ItemField`'s narrow surface, opt-in declaration, the `item` property, and the no-widget summary.
  - `docs/reference/glossary.md`: a row **List widget**: "`ArrayWidget` (haybale-core): edits an `ArrayType[T]` value one row per item with the item type's own widget. Opt-in: a port or setting names it with `widget=ArrayWidget.config()`." Plus a row **Commit mode**: "`TextWidget`'s `commit` property: the value is written on Enter or blur, not per keystroke."
  - `docs/superpowers/plans/2026-10-12-editor-modes.md`: in Sequence 5d, the 5d-2 line links this plan.

- [ ] **Step 1:** Make the doc edits.
- [ ] **Step 2:** Run the gates:
  - `uv run ruff check .` and `uv run ruff format --check .` (the `.scratch/draw-perf/*.py` failures predate this branch; anything else is ours)
  - the full mypy command from CLAUDE.md
  - `uv run pytest -m "not browser and not perf" -n 4 -q > /tmp/t.log 2>&1; echo "exit=$?"`
  - `uv run pytest -m browser -n 4 -q > /tmp/b.log 2>&1; echo "exit=$?"`
  - `uv run haywire docs --all`, then commit the regenerated library docs (haybale-core's new widget, SettingsNode's fields).

  Expected: all exit 0.
- [ ] **Step 3:** Commit `docs: list widget and TextWidget commit mode — widget canon, glossary, spec`.

### Live check (user, studio started from the main checkout)

1. Open a graph and add a *Settings Test Node*. Its properties panel shows *Example String List* as three text rows, each with a grip and a remove button, and an Add button.
2. Edit a row, add one, remove one, and drag one by its grip to a new place. Undo steps back through each change, and Redo replays them.
3. Save, close and reopen: the list is as left. Reset on the row menu restores One/Two/Three.
4. Promote *Example Int List* to an inlet. The card shows integer rows that step by whole numbers.
5. Promote *Example String List* to config and select the node: the card shows its rows. Zoom out a little and drag a row by its grip: the list reorders and the node stays put.
6. Lock the canvas: card rows can still be edited (OPERATE), and the properties panel is read-only.
7. Untouched graphs from before the branch open and save byte-identical (`git diff` on a tracked graph file).
