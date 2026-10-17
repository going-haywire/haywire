# Editor modes, slice 5b-4: skins write nothing — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Every control on a node card is a widget that writes through the edit route. The fold header becomes a `FoldWidget`, the annotation text becomes a `NoteTextWidget` on the `text` setting, and `operable=False` lets a field or port need level mode `edit` even on a card. After this slice no skin writes the model, and the last two direct card writes (fold toggle, annotation text) gain the server check, the unsaved mark and undo.

**Architecture:**
- **`operable=False`** is a boolean on `setting(...)` and on `DataPort`. `EditRoute` raises a write's `minimum` to `EDIT` when its target is not operable, so every surface (cards, Farmhand) gets the rule from the route. `BaseSkin.render_widget` stamps `data-hw-operable` only on operable widgets, so the browser gate follows.
- **Fold:** the `FOLD` type declares `widget_key=FOLD_WIDGET`. The widget draws the triangle, the label and the checked/unchecked icon; a click writes `not value` through its routed model. The type's `_configure_port` hook makes every value change of a fold port request a card redraw, so a toggle, an undo and an agent's write all redraw. The stacked skin draws the header with `render_widget`; the split skin gets the toggle for free from its ordinary row.
- **Annotation text:** `BaseSkin.render_setting_widget(bag, name, node_id, *, widget_key=None, classes="")` draws a settings field's widget on a card through a routed `SettingWidgetModel`. The annotation skin draws `NoteTextWidget` on `annotation.text` inside a wrapper that carries the note's text style; the widget owns the double-click, the editor and the commit.

**Tech Stack:** Python 3.12, NiceGUI/Quasar/Vue 3, pytest (`uv run pytest`), Playwright browser tier, ruff, mypy.

**Spec:** [2026-10-16-edit-route.md](2026-10-16-edit-route.md): sections "Skins: a skin draws, widgets write" and "`operable=False`"; sequence item 4 ("5b-4, skins write nothing"); the traps "The annotation label must stay non-interactive" and "Focusing the opened editor needs a timer"; the 5b-4 items under "Docs corrections". Decisions are listed below.

## Global Constraints

- **Branch:** work on `feat/editor-modes-slice5b4` in worktree `.worktrees/editor-modes-slice5b4`, cut from `feat/editor-modes-slice1` (HEAD `8a87a9a8`). It merges into `feat/editor-modes-slice1` after the live check; nothing goes to master. The main checkout has the user's uncommitted edits (`docs/components/nodes/node-canon.md`, `barn/haybale-example/.../math_op.py`, `.claude/settings.json`); never touch them.
- **Breaking changes are allowed.** No shims: `StackedNodeSkin._toggle_fold` and the annotation skin's inline editor are deleted, not kept beside the widgets.
- **A skin writes nothing** (spec): no skin calls `set_value`, assigns a settings field, or calls `Editor`. Skin author's `render()` signature does not change.
- **Level modes per write** (spec): card and stage widgets `operate`; an `operable=False` target `edit`; panels `edit` (unchanged). A fold's open state is a saved value, so it toggles in `operate` and `edit`, never in `view` (Q9).
- **`operable` is a boolean, not a tier** (spec): `operable: bool = True`. No `access=` keyword anywhere.
- **Undo** (unchanged from 5b-2): a write in `edit` is one step (same-field runs merge, `VALUE_EDIT_MERGE_IDLE_S = 3.0`); in `operate` it marks unsaved and is not recorded. A text edit is one undo step and marks the graph unsaved.
- **Annotation UX kept** (spec): double-click opens an editor over the card; Tab types a tab; Shift+Tab leaves; mouse, pointer and wheel events stay in the editor; blur or Ctrl+Enter commits; Esc cancels; empty text shows `Double-click to write` dimmed and italic; the editor placeholder is `Write a note…`. While showing text, nothing in the widget carries `.widget-container`, so the note drags by its body.
- **Not in this slice:** access defaults and haystack tiers (5b-5), the security guide's known-gaps box itself (5b-5 removes it; this slice only removes the fold and annotation bullet), the promoted pin "Show widget" exception in ADR 0055 (stays), undo of edge propagation to `None`, Ctrl+S, the undo-history panel.
- **Docs rules:** follow `.claude/rules/python-docs.md`. Widget class docstrings are displayed docstrings (Markdown, no reST). ADR, glossary, canon and guide edits land in Task 6.
- **Pre-edit baseline** (CLAUDE.md), before Task 1: `uv run ruff check packages/haywire-core/src barn/haybale-studio barn/haybale-graph-editor tests/ui tests/core tests/graph_editor tests/farmhand` and the CLAUDE.md mypy command. It must be clean; if not, stop and ask.
- **Tests:** smallest tier while iterating (`uv run pytest <file>`). Commit before any full-suite run (`tests/studio/test_docs/test_generate.py` reverts uncommitted edits under `barn/haybale-testing`). Use `-n 4`. Playwright tests under `tests/ui/harness/` are marked `browser` automatically.
- **Commit trailer:** end every commit message with `Co-Authored-By: Claude Opus 5.5 (1M context) <noreply@anthropic.com>`.

## Decisions (this plan's, against the spec)

1. **The route enforces `operable`, not the callers.** `EditRoute.set_port` looks the port up (`graph.get_node_wrapper(node_id).node.ports.get(port_id)`) and `EditRoute.set_settings`/`reset_settings` read the descriptor `_split` already fetches; a non-operable target raises the effective minimum to `EDIT`. So `_write_for` in the widget factory and the Farmhand operate tool need no rule of their own. The operate tool still adds `not port.operable` to its `not_operable` precheck, for the clearer error.
2. **A promoted port inherits `operable` from its setting** (`_metadata_to_port_kwargs` adds `operable=False` when the descriptor says so). `DataPort.operable` is an ordinary serialized dataclass field (default `True`, so it is written only when `False`), refreshed like `show_widget`.
3. **The fold's label travels in its widget config.** A widget sees only its model (`id`, `widget_config`, `data`). `NodeData.fold()` passes `widget_config={"properties": {"text": label}}` (the `SwitchWidget` spelling), merged under any `widget_config` the caller passes.
4. **The redraw on a fold change lives on the `FOLD` type.** `FOLD._configure_port(port)` subscribes the port's field so a value change calls `port._wrapper.redraw()` while the wrapper is registered. `DataPort.from_spec` calls the hook for every built port, a rejig's spec port included, and `refresh_from` keeps the live port's field, so each live fold has exactly one subscription. The fold's own `on_change=` stays free for the node.
5. **A fold row draws no separate label.** In `NodeSkin._render_config` and `NodeSkin._render_port_horizontal`, a port with `is_fold` skips its `ui.label(port.label)`: the `FoldWidget` is the row. On stage the stacked header follows `_shows_widget(group_port)` like any row; the special case at `stacked_skin.py:356-359` goes.
6. **The skin call is `render_setting_widget`, with an optional `widget_key`.** It defaults to the field's own widget. The annotation skin passes `NOTE_TEXT_WIDGET`, so the `text` setting keeps its `TextWidget` in the Properties panel. The routed model is built by a new `setting_widget_model(bag, name, route, minimum)` beside `_write_for` in `ui/widget/factory.py`; the card's widget instances are keyed by the descriptor's `storage_key` (`annotation.text`).
7. **The note's text style reaches the widget by CSS inheritance.** The skin's wrapper carries the inheritable part of `_text_style(bag)` (font family, size, weight, style, decoration, alignment, colour) plus three custom properties: `--hw-note-highlight` (highlight colour or `transparent`), `--hw-note-justify` and `--hw-note-align` (the `_VERTICAL` and `_JUSTIFY` flex values). The widget root fills the wrapper and lays out with those variables; its label paints `background-color: var(--hw-note-highlight)`; its textarea sets `input-style` to `font: inherit; color: inherit; text-align: inherit; text-decoration: inherit` (Quasar's native field does not inherit font by default). Neither the wrapper nor the widget root is positioned, so the editor's `position: absolute; inset: 0` still covers the card.
8. **`NoteTextWidget` and `FoldWidget` live in the builtin widget package** (`haywire/barn/builtin/widgets/`), with keys `FOLD_WIDGET = "haywire-core:widget:FoldWidget"` and `NOTE_TEXT_WIDGET = "haywire-core:widget:NoteTextWidget"` in `widget_keys.py` (enforced by `test_widget_keys.py`).
9. **A source guard pins "skins write nothing".** A unit test scans every skin module in `haywire/barn/builtin/skins/` and `haybale_studio/skins/` for `.set_value(`, `setattr(` and `.redraw()`; none may appear.

## Review Focus

1. **A fold toggled on a locked level by an `edit` principal** (level mode `operate`). It opens, the graph is marked unsaved, and no undo step is recorded. Test: Task 3, `test_an_operate_fold_toggle_marks_unsaved_and_records_nothing`.
2. **Undo of a fold toggle made in `edit`.** The card redraws and the children show again, with no click on the card. Test: Task 2, `test_a_fold_value_change_requests_a_redraw` and Task 3, `test_undoing_a_fold_toggle_redraws_the_card`.
3. **An annotation double-clicked on a locked level.** No editor opens (browser), and a write that slips through anyway is refused by the route. Tests: Task 1, `test_a_non_operable_setting_is_refused_in_operate`; Task 5, `test_operate_annotation_double_click_opens_no_editor`.
4. **A text edit cancelled with Esc, or committed unchanged.** Nothing is written, no undo step, no unsaved mark. Test: Task 4, `test_cancel_and_unchanged_commit_write_nothing`.
5. **A split-skin node with a closed fold.** The row shows the toggle once (no second label), and clicking it opens the fold. Test: Task 3, `test_the_split_skin_draws_a_fold_as_one_toggle_row`.

---

### Task 1: `operable=False` on settings and ports, enforced by the route

**Files:**
- Modify: `packages/haywire-core/src/haywire/core/settings/descriptor.py` (`__init__` :164, docstring Args)
- Modify: `packages/haywire-core/src/haywire/core/types/port.py` (field beside `show_widget` :226)
- Modify: `packages/haywire-core/src/haywire/core/node/promotion.py` (`_metadata_to_port_kwargs` :86)
- Modify: `packages/haywire-core/src/haywire/core/graph/edit_route.py` (`set_port` :63, `set_settings` :95, `reset_settings` :115, `_split` :132, class docstring)
- Modify: `packages/haywire-core/src/haywire/ui/skin/base.py` (`render_widget` :136)
- Modify: `barn/haybale-graph-editor/haybale_graph_editor/farmhands/editor_tools.py` (`GraphEditorOperateTool.run` :1076)
- Test: `tests/core/test_graph/test_edit_route.py`, `tests/ui/skin/test_operable_stamp.py`, `tests/core/settings/test_promote_demote_bag_api.py`, `tests/farmhand/test_farmhand_access.py`

**Interfaces:**
- Produces:
  - `setting(..., operable: bool = True)`; read as `descriptor.operable -> bool` (property over `_operable`).
  - `DataPort.operable: bool = True` (docstring: whether operating its widget on a card may change it; `False` needs level mode `edit`). Accepted by `as_inlet/as_outlet/as_config/as_swinglet(..., operable=False)` through the spec kwargs.
  - `EditRoute`: a write to a non-operable port or field needs `LevelMode.EDIT` whatever `minimum` says. Return contract unchanged (`False`, nothing written).
  - `BaseSkin.render_widget` stamps `data-hw-operable` only when `port.operable` (getattr default `True` for a non-`DataPort` model).

- [ ] **Step 1: Write the failing tests**
  - `test_edit_route.py`:
    - `test_a_non_operable_port_is_refused_in_operate`: a node with `FLOAT.as_config("gain", default=1.0, operable=False, widget_key=NUMBER_WIDGET)`; route in `OPERATE`; `route.set_port(nid, "gain", 2.0, minimum=LevelMode.OPERATE) is False` and the value is still `1.0`; in `EDIT` the same call is `True`.
    - `test_a_non_operable_setting_is_refused_in_operate`: an annotation node; route in `OPERATE`; `route.set_setting(node.annotation, "text", "hi", minimum=LevelMode.OPERATE) is False`; `node.annotation.text == ""`. (Fails until Task 4 sets `operable=False` on `text`; write it now against a test-local `NodeSettings` subclass with `operable=False`, and add the annotation case in Task 4.)
    - `test_an_operable_target_keeps_its_minimum`: an ordinary port in `OPERATE` with `minimum=OPERATE` still writes.
  - `test_operable_stamp.py`: `test_a_non_operable_widget_is_not_stamped` (`SimpleNamespace(..., operable=False)` → no `data-hw-operable`); keep `test_render_widget_stamps_operable` (no `operable` attribute → stamped).
  - `test_promote_demote_bag_api.py`: `test_a_promoted_port_inherits_operable` (`_metadata_to_port_kwargs(desc)["operable"] is False` for an `operable=False` setting; key absent for an operable one).
  - `test_farmhand_access.py`: `test_operate_refuses_a_non_operable_port` → `FarmhandError` code `not_operable`.
- [ ] **Step 2: Run** `uv run pytest tests/core/test_graph/test_edit_route.py tests/ui/skin/test_operable_stamp.py tests/farmhand/test_farmhand_access.py tests/core/settings/test_promote_demote_bag_api.py` — the new tests fail (`operable` unknown kwarg).
- [ ] **Step 3: Implement** the interfaces. In the route, compute the effective minimum once per call (`LevelMode.EDIT` if any target is non-operable, else `minimum`) before `allows`. `_split` may return the descriptors it already reads, or the route reads `type(bag)._settings_descriptors()[name].operable` per bag; either is fine.
- [ ] **Step 4: Run** the same files — PASS. Also `uv run pytest tests/core/test_graph tests/ui/skin tests/farmhand -n 4`.
- [ ] **Step 5: Commit** `feat(core): operable=False on settings and ports; the edit route needs edit for them`

---

### Task 2: `FoldWidget` on the `FOLD` type

**Files:**
- Create: `packages/haywire-core/src/haywire/barn/builtin/widgets/fold_widget.py`
- Modify: `packages/haywire-core/src/haywire/barn/builtin/widgets/__init__.py`, `packages/haywire-core/src/haywire/barn/builtin/widget_keys.py`
- Modify: `packages/haywire-core/src/haywire/barn/builtin/types/fold.py` (`widget_key`, `_configure_port`, class docstring)
- Modify: `packages/haywire-core/src/haywire/core/node/data.py` (`fold()` :262: widget config, docstring "a port with no pin and no widget")
- Test: `tests/ui/widget/test_fold_widget.py` (new), `tests/core/test_node/test_fold.py`, `tests/core/test_widget_keys.py` (existing, enforces the key)

**Interfaces:**
- Consumes: `SettingWidgetModel(field_id, widget_config, cell, on_edit)` (existing); `hui.icon.fold_open / fold_closed / checked / unchecked` (existing).
- Produces:
  - `FOLD_WIDGET = "haywire-core:widget:FoldWidget"`.
  - `class FoldWidget(BaseWidget)` registered with `@widget(description="Fold header")`. `build()` returns a `ui.row` with classes `w-full items-center gap-1 cursor-pointer` and props `data-hw-fold-id="<model id>"` and `data-hw-fold-open="true|false"`, holding the triangle icon, a `ui.label(<properties.text>)` (`text-xs grow`) and the checked/unchecked icon. A click calls `self.set_value(not bool(self.get_value()))`. `on_model_changed(value)` sets both icons and `data-hw-fold-open`.
  - `FOLD`: `widget_key=FOLD_WIDGET`; `_configure_port(port)` subscribes `port.data.on_changed` to request `port._wrapper.redraw()` when the wrapper exists and `wrapper.state.is_registered`.
  - `NodeData.fold(label, ...)` builds the spec with `widget_config={"properties": {"text": label}}` merged under a caller's `widget_config`.

- [ ] **Step 1: Write the failing tests**
  - `test_fold_widget.py` (unit, `nicegui_slot_context`; model = `SettingWidgetModel` on a `FOLD` field with an `on_edit` spy):
    - `test_a_click_writes_the_opposite_value` (value `True` → `on_edit` called with `False`).
    - `test_a_refused_click_shows_the_model_again` (`on_edit` returns `False` → `data-hw-fold-open` still `"true"`, open icons kept).
    - `test_the_header_shows_the_label_and_state` (label text from `widget_config["properties"]["text"]`; closed value → `fold_closed` and `unchecked` icons, `data-hw-fold-open="false"`).
  - `test_fold.py`:
    - `test_a_fold_carries_the_fold_widget_and_its_label` (`port.widget_key == FOLD_WIDGET`, `port.widget_config["properties"]["text"] == "Solver"`, `port.should_show_widget()` true).
    - `test_a_fold_value_change_requests_a_redraw` (registered wrapper on a `SyncScheduler` graph: `port.set_value(False)` marks the node `ChangeReason.NODE_REDRAW_REQUESTED`; patch `wrapper.redraw` with a spy, or read the validation result).
    - `test_a_rejigged_fold_redraws_once` (a node that re-adds its fold in a `rejig`; one value change → exactly one `redraw` call).
- [ ] **Step 2: Run** the three files — FAIL (no widget, `widget_key` is `None`).
- [ ] **Step 3: Implement.** Update the `FOLD` comment and class docstring (displayed: Markdown) and the `fold()` docstring: the fold's control is its widget, a click on the header toggles it, its value is the open state.
- [ ] **Step 4: Run** the three files — PASS. Then `uv run pytest tests/core/test_node tests/ui/widget -n 4` (the fold-lane and stacked-skin tests may now fail; they are Task 3's).
- [ ] **Step 5: Commit** `feat(builtin): the fold's header is a FoldWidget; a fold change redraws its card`

---

### Task 3: Skins draw the fold through the widget

**Files:**
- Modify: `barn/haybale-studio/haybale_studio/skins/stacked_skin.py` (`_render_group` :313-403; delete `_toggle_fold` :405-414)
- Modify: `barn/haybale-studio/haybale_studio/skins/node_skin.py` (`_render_port_horizontal` label :557, `_render_config` label :655)
- Test: `tests/ui/skin/test_fold_header.py` (rewrite), `tests/ui/skin/test_fold_lane_rendering.py`, `tests/graph_editor/test_stage_folds.py`, `tests/ui/skin/test_stage_render.py` (fold cases), new `tests/ui/skin/test_skins_write_nothing.py`, new `tests/graph_editor/test_fold_toggle_route.py`

**Interfaces:**
- Consumes: `FoldWidget`, `FOLD_WIDGET` (Task 2); `BaseSkin.render_widget` with operable stamping (Task 1); `SkinFactory.render(key, wrapper, *, on_stage, route=)` (existing).
- Produces:
  - `StackedNodeSkin._render_group`: when `not on_stage or self._shows_widget(group_port)`, an indented `ui.row` (`padding-left: _config_indent(depth)`, classes `w-full zoom-pan-lod2 hw-detail-label`) holding `self.render_widget(group_port, wrapper.node_id)`; the tooltip is `add_pin_tooltip(header_row, group_port, trigger_el=<widget element>)`. Children drawn while `node.value(group_port.id)` is true, as now. The row carries no `data-hw-operable` of its own and no click handler.
  - `NodeSkin` rows: a port with `is_fold` draws no separate label (Decision 5).

- [ ] **Step 1: Write the failing tests**
  - `test_fold_header.py` (replace the source-inspection tests that pin the old header): `test_the_header_is_the_fold_widget` (rendered stacked card with a route: exactly one element with `data-hw-fold-id`, and it is the widget's root, stamped `data-hw-operable`); `test_the_header_has_no_click_handler_of_its_own` (no `click` listener on any non-widget element of the header row); keep the icon-token assertion against `fold_widget.py`.
  - `test_skins_write_nothing.py`: `test_no_skin_writes_the_model` (Decision 9) over the source of every module in `haywire.barn.builtin.skins` and `haybale_studio.skins`.
  - `test_fold_toggle_route.py` (integration, real graph, `SyncScheduler`, route built like `test_edit_route.py`'s fixtures, the card rendered through `SkinFactory.render(..., route=route)`; click the widget's root `click` listener):
    - `test_an_edit_fold_toggle_is_one_undo_step` (mode `EDIT`: value flips, `can_undo()` true; undo restores it).
    - `test_an_operate_fold_toggle_marks_unsaved_and_records_nothing` (mode `OPERATE`: value flips, graph marked unsaved (`GRAPH_CONTENT_CHANGED` in the validation result, or the unsaved flag the 5b-1 tests read), `can_undo()` false).
    - `test_a_view_fold_toggle_is_refused` (mode `VIEW`: value unchanged, `data-hw-fold-open` unchanged).
    - `test_undoing_a_fold_toggle_redraws_the_card` (after the `EDIT` toggle and an undo, the node is marked `NODE_REDRAW_REQUESTED`).
  - `test_the_split_skin_draws_a_fold_as_one_toggle_row` (split skin card of `FoldProbeNode` with a closed config fold: one `data-hw-fold-id` element, the fold's label appears once among the card's labels, a click opens it and the children's labels appear on the next render).
  - `test_stage_folds.py`: pass a route to `_render` (mode `EDIT`) and click the widget root instead of the old header; the existing assertions stay.
- [ ] **Step 2: Run** `uv run pytest tests/ui/skin tests/graph_editor/test_stage_folds.py tests/graph_editor/test_fold_toggle_route.py` — FAIL.
- [ ] **Step 3: Implement.** Delete `_toggle_fold` and the on-stage special-case comment. Fix any other test that relied on the old header (`grep -rn "data-hw-fold\|_toggle_fold" tests/`).
- [ ] **Step 4: Run** the same — PASS; then `uv run pytest tests/ui tests/graph_editor -m "not browser" -n 4`.
- [ ] **Step 5: Commit** `feat(skins): the stacked and split skins draw folds with the FoldWidget`

---

### Task 4: `render_setting_widget` and the annotation text widget

**Files:**
- Modify: `packages/haywire-core/src/haywire/ui/widget/factory.py` (new `setting_widget_model` beside `_write_for` :48)
- Modify: `packages/haywire-core/src/haywire/ui/skin/base.py` (new `render_setting_widget`)
- Create: `packages/haywire-core/src/haywire/barn/builtin/widgets/note_text_widget.py`
- Modify: `packages/haywire-core/src/haywire/barn/builtin/widgets/__init__.py`, `.../widget_keys.py`
- Modify: `packages/haywire-core/src/haywire/barn/builtin/skins/annotation_skin.py` (`render` :179-244; move `_EDITOR_CSS`, `_ensure_editor_css`, `_TAB_JS` into the widget module)
- Modify: `packages/haywire-core/src/haywire/barn/builtin/nodes/annotation.py` (`text` setting :81: `operable=False`; class docstring stays true)
- Test: `tests/ui/skin/test_render_setting_widget.py` (new), `tests/ui/widget/test_note_text_widget.py` (new), `tests/core/test_graph/test_edit_route.py` (annotation case from Task 1), `tests/ui/skin/test_annotation_skin.py`

**Interfaces:**
- Consumes: `EditRoute` with operable enforcement (Task 1); `BaseSkin._nodeids_routes` (existing).
- Produces:
  - `setting_widget_model(bag: Settings, name: str, route: EditRoute | None, minimum: LevelMode) -> SettingWidgetModel`: reads `bag._cell_for(descriptor)`; writes `route.set_setting(bag, name, value, minimum=minimum)`; no route refuses.
  - `BaseSkin.render_setting_widget(self, bag: Settings, name: str, node_id: str, *, widget_key: str | None = None, classes: str = "") -> ui.element | None`: draws through `self._widget_factory.render_widget(key, model, node_id)` at `LevelMode.OPERATE` with the node's route for this render; `widget_key=None` uses the descriptor's own; returns `None` when there is no key; stamps `data-hw-operable` only when `descriptor.operable`; applies `stamp_size_declaration`; records the instance under `descriptor.storage_key`.
  - `NOTE_TEXT_WIDGET = "haywire-core:widget:NoteTextWidget"`; `class NoteTextWidget(BaseWidget)` (displayed docstring: shows a note's text; double-click to edit; Ctrl+Enter or clicking away keeps the text, Esc discards it). `build()` returns a plain `div` root (Decision 7 layout, no `widget-container` class) holding the display label (`zoom-pan-lod1`, `white-space: pre-wrap; word-break: break-word; padding: 2px 6px; max-width: 100%`) and the hidden `ui.textarea` editor (`hw-note-editor`, `borderless`, the absolute overlay styles from today's skin). The root's `dblclick` opens the editor with the model's value and focuses it after `ui.timer(0.1, ..., once=True)`. Commit: hide, then `self.set_value(text)` only if it differs from `self.get_value()`. Cancel: restore the model's value, hide. `on_model_changed` sets the label text, or the dimmed italic `Double-click to write` when empty.
  - `AnnotationSkin.render`: the card keeps `drag-handle` and its styles; the text box is a wrapper `div` (`flex: 1 1 auto; width: 100%; display: flex; flex-direction: column;` plus Decision 7's style and variables) holding `self.render_setting_widget(bag, "text", wrapper.node_id, widget_key=NOTE_TEXT_WIDGET)`. No `dblclick` on the card, no editor in the skin. `_text_style` splits into the inheritable style and the highlight variable.
  - `annotation.text`: `operable=False`.

- [ ] **Step 1: Write the failing tests**
  - `test_render_setting_widget.py` (unit, factory spy as in `test_operable_stamp.py`, a test-local `NodeSettings` bag on a node):
    - `test_it_draws_the_field_s_own_widget_by_default` and `test_a_widget_key_overrides_it` (the key passed to the factory).
    - `test_writes_go_through_the_route_at_operate` (route spy: the model's `set_value("x")` calls `set_setting(bag, name, "x", minimum=LevelMode.OPERATE)`).
    - `test_without_a_route_it_is_read_only` (`set_value` returns `False`, bag unchanged).
    - `test_operable_is_stamped_only_for_an_operable_field`.
  - `test_note_text_widget.py` (unit, `SettingWidgetModel` with an `on_edit` spy; drive the element's listeners as `test_stage_folds.py` does):
    - `test_double_click_opens_the_editor_with_the_text` (editor visible, value = model value).
    - `test_commit_writes_the_new_text_once`.
    - `test_cancel_and_unchanged_commit_write_nothing` (Esc after typing → spy not called, label unchanged; commit with the same text → not called).
    - `test_a_refused_commit_shows_the_stored_text` (`on_edit` returns `False` → label shows the model value).
    - `test_empty_text_shows_the_hint`.
    - `test_the_shown_text_is_not_a_widget_container` (no element in the widget carries `widget-container`).
  - `test_edit_route.py`: `test_the_annotation_text_needs_edit` (Task 1's case on the real `AnnotationNode`: refused in `OPERATE`, written in `EDIT` as one undo step, graph marked unsaved).
  - `test_annotation_skin.py`: `test_the_card_has_no_editor_of_its_own` (rendered card: no `ui.textarea` outside the `NoteTextWidget`, no `dblclick` listener on the card).
- [ ] **Step 2: Run** the four files — FAIL.
- [ ] **Step 3: Implement.**
- [ ] **Step 4: Run** the four files — PASS; then `uv run pytest tests/ui tests/core/test_node/test_annotation_node.py -m "not browser" -n 4` and the Task 3 source guard.
- [ ] **Step 5: Commit** `feat(annotation): the note's text is a NoteTextWidget drawn through render_setting_widget`

---

### Task 5: Browser checks

**Files:**
- Modify: `tests/ui/harness/routes.py` (`/graph-level-mode` :1727: add an annotation card with text `Harness note`, its id in a `level-note-id` label)
- Modify: `tests/ui/harness/test_level_mode_gate.py`
- Modify: `packages/haywire-core/src/haywire/ui/components/graph/canvas.vue` (doc comment :105-110: `data-hw-operable` is stamped on operable widgets; drop "the stacked skin's fold header")

**Interfaces:**
- Consumes: Tasks 3 and 4.

- [ ] **Step 1: Write the failing tests** in `test_level_mode_gate.py`:
  - `test_operate_fold_header_toggles` and any test using the fold header: locate the header by `[data-hw-fold-id]` (now the widget root); assertions unchanged.
  - `test_view_fold_header_does_not_toggle` (`view`: click → `data-hw-fold-open` unchanged after `wait_for_canvas_settled`).
  - `test_edit_annotation_double_click_edits_the_text` (`edit`: double-click the note's label → `.hw-note-editor textarea` visible and focused; type ` more`; Ctrl+Enter → label text is `Harness note more`).
  - `test_operate_annotation_double_click_opens_no_editor` (`operate`: double-click → the editor stays hidden; the hit at the label's centre is not inside the widget).
  - `test_a_note_drags_by_its_text` (`edit`: drag from the label's centre moves the card; compare the card's `data-node` position or bounding box before and after).
- [ ] **Step 2: Run** `uv run pytest tests/ui/harness/test_level_mode_gate.py` — the new tests fail until the harness card exists.
- [ ] **Step 3: Implement** the harness card and the canvas.vue comment.
- [ ] **Step 4: Run** `uv run pytest -m browser -n 4` — PASS.
- [ ] **Step 5: Commit** `test(harness): fold and annotation widgets under the level-mode gate`

---

### Task 6: Docs, glossary, ADRs, full gates

**Files:**
- Modify: `docs/components/skins/skin-canon.md` (a new "A skin draws, widgets write" section with `render_widget` and `render_setting_widget`; "Skin instances are app-wide singletons, shared by every session and canvas, so per-render state is keyed by node id"; line 384's fold sentences: the header is the `FoldWidget` under the ordinary widget rule, the split skin draws a fold as a toggle row)
- Modify: `docs/components/widgets/widget-canon.md` (`FoldWidget` and `NoteTextWidget` in the builtin list, if the canon lists them; `operable=False` makes a card widget need `edit`)
- Modify: `docs/reference/glossary.md` (:380 **Operable widget** → **Operable**: whether operating a widget on a card may change its field; `operable=False` needs `edit`; stamped `data-hw-operable` by the skin funnel. :537 Stage view: "folds keep their header (when its widget shows)" stays true; check)
- Modify: `docs/adr/0055-every-user-edit-takes-the-edit-route.md` (:23 drop "it also covers the few writes … until 5b-4" and "stamps every card widget" → "stamps every operable card widget"; :44 only the promoted pin's widget-visibility choice still writes directly; add the `operable` rule and Decision 1 to Decision/Consequences)
- Modify: `docs/adr/0051-operate-tier-and-the-canvas-lock.md` (:25 drop the bypass sentence; :26 drop the fold and annotation exceptions; :40 replace with the operable rule (folds toggle from `operate`, the annotation text needs `edit`, both through the route); :41 keep only the haystack gaps)
- Modify: `docs/adr/0054-the-stage-view.md` (:25 "since a `FOLD` port has no `widget_key`" and "the split skin draws no fold header" → current behaviour)
- Modify: `docs/guides/security.md` (:492 drop the bypass sentence; :497 drop the fold/annotation bullet)
- Modify: `docs/superpowers/plans/2026-10-16-edit-route.md` (sequence item 4: mark built, list Decisions 1, 3–7 in one line each)

- [ ] **Step 1: Edit** the docs above, in present tense, no history (`.claude/rules/python-docs.md` applies to prose too).
- [ ] **Step 2: Run** `uv run mkdocs build --strict` — PASS (no broken links).
- [ ] **Step 3: Commit** `docs: skins draw, widgets write; operable; fold and annotation widgets`
- [ ] **Step 4: Full gates.** `uv run ruff check .`, `uv run ruff format --check .`, the CLAUDE.md mypy command, `uv run pytest -m "not browser and not perf" -n 4 -q > /tmp/t.log 2>&1; echo "exit=$?"`, `uv run pytest -m browser -n 4`. All green; a failure is fixed, not skipped.
- [ ] **Step 5: Hand off for the live check** (studio started from the worktree):
  1. Stacked-skin node with a fold, unlocked: click the header → opens; Undo → closes again and the card redraws; the graph shows unsaved.
  2. Lock the level (Mod+E): the header still toggles; Undo is hidden; the graph shows unsaved.
  3. `view` principal: the header does not toggle.
  4. Split skin (Appearance → Skin): the fold row shows one label with the toggle; it opens and closes.
  5. Stage view: a fold toggles there and the patch card follows.
  6. Annotation, unlocked: double-click → editor in the note's font and colour; Tab types a tab; Ctrl+Enter commits; one Undo restores the old text; the graph shows unsaved. Esc discards an edit. The note drags by its text.
  7. Annotation, locked: double-click opens nothing.
  8. Farmhand `graph_editor_operate` on a fold port toggles it and the card redraws.
