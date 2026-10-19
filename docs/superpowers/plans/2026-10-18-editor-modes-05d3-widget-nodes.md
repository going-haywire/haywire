# Editor modes, slice 5d-3: widget nodes — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Seven widget nodes in `haybale-core`: Float Slider, Int Slider, Float Number, Int Number, Toggle, Text and Menu. Each is a DATA node whose outlet's widget is the control. It shows what flows in, and it sends what the operator sets. On a stage they draw with a frameless widget-node skin: the node label on the left, then the control.

**Architecture:**
- **One base class, `WidgetNode`.** Each node has a widget-less inlet `in` (`NEVER`) and an outlet `value` whose widget is `ALWAYS`.
- **Forwarding.** A value arriving at `in` goes out of `value` through the inlet's `on_change`, but only while `in` holds a linked value (Q2 A, Q4 A). So an unlink keeps the last value.
- **Settings.** The range and options live in a settings bag, promotable to inlets (Q6 B). A change reaches the widget through a new seam, `DataPort.set_widget_config(key, value)`, which mutates the config and redraws the card only when the value changed (Q6c).
- **The skin.** `WidgetNodeSkin` is tagged `special`, `stage-only` and `widget-node` (Q30). The widget nodes bind it as their `stage_skin`, and their `stage_skin` list offers only skins carrying those tags (Q23 A).
- **Nothing new in execution.** An outlet's saved value reaches downstream when an edge links or the graph loads (`DataPort._housekeeping`). Card and stage writes take the edit route (OPERATE tier, undo only in EDIT).

**Tech Stack:** Python 3.12, NiceGUI 3 / Quasar, pytest, Playwright browser tier.

**Spec:** [2026-10-12-editor-modes.md](2026-10-12-editor-modes.md) (Stage → Widget nodes, Sequence 5d-3), as settled by the user's 5d inquisition of 2026-10-18 (session `9680a528`): Q1 C, Q2 A, Q3 C, Q4 A (with the linked-value guard), Q5 A, Q6 B, Q6b B, Q6c C, Q7 A, Q8 A, Q9 A, Q10 B, Q18–Q20 (label left plus the declared, non-promoted outlet widget), Q21 A + Q22 B + Q23 A (tags), Q24 B, Q28 A and Q30 A. It builds on [5d-1](2026-10-18-editor-modes-05d1-stage-skin.md) (stage skin, tags, `skin_choices`) and [5d-2](2026-10-18-editor-modes-05d2-list-widget.md) (`ArrayWidget`, `TextWidget` commit mode).

## Global Constraints

- **Branch:** work directly on `feat/editor-modes-slice1` in the main checkout, from `74bba92c`. There is no worktree and no slice branch. After the user's live check, tag the tip `editor-modes-slice5d3-full`, then `git reset --soft 74bba92c` and make one commit. Nothing goes to master until slice 6 lands.
- **The user's uncommitted files** (`.claude/settings.local.json`, `docs/components/nodes/node-canon.md`, `graphs/any_and_nonde.haywire`, `.scratch/docs-story/`) share the checkout. Stage explicit paths only, never `git add -A` or `git add .`. `graphs/any_and_nonde.haywire` is the user's live-check save of a `test_prehydration` fixture. While it stays modified, that one test fails. Report it rather than restoring it.
- **Placement (Q24 B):**
  - Nodes go in `barn/haybale-core/haybale_core/nodes/widgets/`, with menu `core/widgets/<slug>`.
  - The skin goes in `barn/haybale-core/haybale_core/skins/widget_node_skin.py`.
  - `haybale-core` depends only on `haywire-core`, so the skin subclasses `BaseSkin` (as `RerouteSkin` does), never studio's `NodeSkin`.
- **No nicegui on the headless path:** node modules name widgets and skins by registry-key string, as `AnnotationNode` does. They never import a widget class.
- **Saved files:** an untouched graph saves byte-identical. Only new widget nodes write new keys.
- **Not in scope (inquisition):** Button; live widget reconfigure (its own design round); the other label positions; a Split twin; an Error stage twin; `ArrayWidget` as `ArrayType`'s default; a Menu index outlet; stage-specific layout/detail props; an inlet "set without output".
- **Tests and docs:** use the smallest tier while iterating, then the full gates at the end. Docstrings follow `.claude/rules/python-docs.md`; node and skin class docstrings are displayed (Markdown). Glossary and ADR edits land with the code (Task 4).

## Decisions

1. **A widget write on the outlet (the 5d-2 flag).** It runs `DataPort.set_value` → `_after_node_write` → `Pipes.propagate()` on the UI thread.
   - An eager pipe stores the value in the downstream inlet and marks it dirty at once. The downstream node acts on it (`on_change`, worker) only in its next frame, in `BaseNode._execute`.
   - A lazy pipe only marks the inlet dirty.
   - So the only out-of-frame step is storing a value in another node's cell. Every widget on a plain inlet already does more than that: its own write fires `on_change` at once (`DataPort.set_value`).
   - **Decided (user, 2026-10-18, option a):** keep it. Widget-node outlets are plain outlets, not `is_linked_lazy`, so their edges stay eager by default and the user may pick lazy. A test pins the behaviour (Task 2).
2. **Widget keys as constants.**
   - `haywire.barn.builtin.widget_keys` gains `SLIDER_WIDGET = "haywire-core:widget:SliderWidget"`. `test_widget_keys.py` already checks every constant against its class.
   - New leaf module `barn/haybale-core/haybale_core/keys.py` holds `ARRAY_WIDGET = "haybale-core:widget:ArrayWidget"` and `WIDGET_NODE_SKIN = "haybale-core:skin:WidgetNodeSkin"`. A test compares them with the classes' `class_identity.registry_key`.
3. **`DataPort.set_widget_config(key: str, value: Any) -> bool`** in `core/types/port.py`.
   - It writes `self.widget_config.setdefault("properties", {})[key] = value`. A `value` of `None` removes the key.
   - It returns whether anything changed. If it did and the port has a wrapper, it calls `self._wrapper.redraw()`; an unchanged value redraws nothing.
   - The docstring states the contract: the card rebuilds its widgets from the new config, and live reconfiguration is a later design round.
4. **Tags.**
   - `core/skin/tags.py` gains `SKIN_TAG_WIDGET_NODE = "widget-node"`.
   - `core/skin/settings.py` gains `_widget_node_stage_skin_choices()`, which returns `skin_choices(include=[SKIN_TAG_SPECIAL, SKIN_TAG_WIDGET_NODE], exclude=[SKIN_TAG_GENERAL])`. Its docstring example already exists in `skin_choices`; it switches to the constant.
5. **`WidgetNode(BaseNode)`** in `haybale_core/nodes/widgets/base.py`. It carries no `@node`, so it is not registered.
   - **`class props(BaseNode.props)`** binds `stage_skin = setting[CHOICES](WIDGET_NODE_SKIN, label="Stage Skin", description="Widget nodes draw as their control on the stage", category="appearance", order=11, widget_config={"options": _widget_node_stage_skin_choices})`.
   - **ClassVars set by each subclass:**
     - `value_type: ClassVar[type[IType]]`
     - `widget_key: ClassVar[str]`
     - `default_value: ClassVar[Any]`
     - `base_properties: ClassVar[dict[str, Any]]` (widget properties that no setting drives; default `{}`)
   - **`init()`** adds:
     - `value_type.as_inlet("in", label="In", show_widget=ShowWidgetStrategy.NEVER, on_change="_forward")`
     - `value_type.as_outlet("value", label="Value", default=default_value, show_widget=ShowWidgetStrategy.ALWAYS, widget={"key": widget_key, "config": {"properties": {**base_properties, **self._widget_properties()}}})`
   - **`_widget_properties(self) -> dict[str, Any]`** maps the node's settings to widget properties. The base returns `{}`.
   - **`post_init()`** subscribes each field of the node's settings bag with `bag._subscribe_field(name, self._on_config_setting)`, then calls `self._apply_widget_config()`.
   - **`_apply_widget_config()`** calls `self.ports["value"].set_widget_config(k, v)` for each `_widget_properties()` item, so a load or reload that restored settings re-stamps the config.
   - **`_forward(self, port, value)`** calls `self.out("value", value)` only if `port.data.has_linked_value()`.
   - **`worker(self, context) -> None`** returns `None`.
6. **The nodes** (Q28 A). Labels as given; menu `core/widgets/<slug>`. Search tags: the label's words plus `"widget"`, `"control"` and `"stage"`. Settings bags carry the defaults below, `promotable` default (ALL).

   | Class / label | value_type | widget | bag `.field` = default | `_widget_properties` | default_value |
   |---|---|---|---|---|---|
   | `FloatSliderNode` "Float Slider" | `FLOAT` | `SLIDER_WIDGET` | `range`: `min` 0.0, `max` 1.0, `step` 0.01 (`FLOAT`) | min, max, step | 0.0 |
   | `IntSliderNode` "Int Slider" | `INT` | `SLIDER_WIDGET` | `range`: `min` 0, `max` 100, `step` 1 (`INT`) | min, max, step | 0 |
   | `FloatNumberNode` "Float Number" | `FLOAT` | `NUMBER_WIDGET` | `range`: `min`/`max` `OPTIONAL[FLOAT]` None, `step` `FLOAT` 0.1 | min, max (None removes), step | 0.0 |
   | `IntNumberNode` "Int Number" | `INT` | `NUMBER_WIDGET` | `range`: `min`/`max` `OPTIONAL[INT]` None, `step` `INT` 1 | min, max, step | 0 |
   | `ToggleNode` "Toggle" | `BOOL` | `SWITCH_WIDGET` | none | — | False |
   | `TextNode` "Text" | `STRING` | `TEXT_WIDGET`, `base_properties={"commit": True}` | none | — | "" |
   | `MenuNode` "Menu" | `CHOICES` (`in` is `STRING`) | `SELECT_WIDGET` | `menu`: `options` `ArrayType[STRING]` ["One", "Two", "Three"], `widget={"key": ARRAY_WIDGET, "config": {"properties": {"item": {"commit": True}}}}` | options | "One" |

   - `MenuNode` overrides `init()` so its inlet is `STRING`.
   - Nothing clamps a value or checks it against the options (Q6 B): an out-of-range or unknown value passes through unchanged.
   - Each class docstring says a fed control is a display, and last write wins (Q3 C).
7. **`WidgetNodeSkin(BaseSkin)`**, `@skin(label="Widget Node", description="The control alone, with the node label on its left — for widget nodes on a stage", tags=[SKIN_TAG_SPECIAL, SKIN_TAG_STAGE_ONLY, SKIN_TAG_WIDGET_NODE])`.
   - **The face:** a frameless card (`node-card drag-handle zoom-pan-lod0`, transparent background, no shadow, 4px padding). Inside is one no-wrap row: `ui.label(node.display_label)` (text-sm, shrink-0), then a `widget-container flex-1 min-w-0` element per port that is `port.is_outlet() and port.origin is PortOrigin.DECLARED and port.widget_key`, drawn by `self.render_widget(port, node_id)`.
   - **On a patch canvas** (no list offers it there, but a write can set it) it also draws every pin with `render_pin(..., layout=LayoutDirection.LEFT_TO_RIGHT, on_stage=False)`. Inlets go in an absolute column on the left edge and outlets on the right, using `RerouteSkin`'s edge wrappers, so the card stays wireable.
   - **On stage** it draws no pins.
   - `honours_detail(*, on_stage)` returns `False`.

## Review Focus

1. **Unlink keeps the last value.** A slider fed 0.73 keeps 0.73 on its outlet after the feeding edge is deleted, and sends nothing on the unlink. Test: Task 2 `test_an_unlink_keeps_the_last_value`.
2. **A range driven by an edge.** A promoted `range.max` fed 5.0 redraws the card once per change, and an unchanged value redraws nothing. The outlet value outside the new range is untouched. Test: Task 2 `test_a_driven_max_redraws_only_on_change`.
3. **Menu fed an unknown item.** `ui.select` turns an unknown value into `None` server-side. The outlet must keep `"Four"` and the widget must not write `None` back. Test: Task 3 `test_a_menu_fed_an_unknown_item_keeps_it`.
4. **A locked stage.** An operator (level mode OPERATE) can drag the slider on the stage and the value reaches downstream. The stage card offers no pin and no other port widget, even with `range.max` promoted to an inlet. Test: Task 3 browser `test_an_operator_drives_a_slider_on_a_locked_stage`, plus headless `test_the_skin_draws_only_the_declared_outlet_widget`.
5. **Skin lists.** A widget node's Stage Skin list offers only *Widget Node*. No general list (patch skin, stage skin, graph and studio defaults) offers it. Test: Task 1 `test_widget_node_skins_are_only_in_the_widget_node_list`.

---

### Task 1: Seams — `set_widget_config`, tag, choice list, keys

**Files:**
- Modify:
  - `packages/haywire-core/src/haywire/core/types/port.py` (Decision 3)
  - `packages/haywire-core/src/haywire/core/skin/tags.py`, `.../core/skin/settings.py` (Decision 4)
  - `packages/haywire-core/src/haywire/barn/builtin/widget_keys.py` (`SLIDER_WIDGET`)
- Create: `barn/haybale-core/haybale_core/keys.py` (Decision 2)
- Test: `tests/core/test_types/test_set_widget_config.py` (new, unit), `tests/core/test_skin/test_stage_skin_fields.py` (append), `tests/barn/test_haybale_core_keys.py` (new, integration)

**Interfaces:**
- Produces: `DataPort.set_widget_config(key, value) -> bool`, `SKIN_TAG_WIDGET_NODE`, `_widget_node_stage_skin_choices`, `SLIDER_WIDGET`, `haybale_core.keys.ARRAY_WIDGET` and `WIDGET_NODE_SKIN`.

- [ ] **Step 1: Write the failing tests:**
  - `test_set_widget_config_writes_a_property`: on a `FLOAT` outlet with `widget_config={"properties": {"min": 0}}`, `set_widget_config("max", 5)` returns True and `widget_config["properties"] == {"min": 0, "max": 5}`.
  - `test_set_widget_config_none_removes_the_key`.
  - `test_an_unchanged_value_does_not_redraw`: with a `MagicMock` wrapper, setting the same value twice calls `redraw` once and returns False the second time.
  - `test_a_port_without_a_wrapper_still_updates`.
  - `test_widget_node_skins_are_only_in_the_widget_node_list`: register a test skin tagged `["special", "stage-only", "widget-node"]`. It is in `_widget_node_stage_skin_choices()` and in neither `_patch_skin_choices()` nor `_stage_skin_choices()`. A `["general"]` skin is not in the widget-node list.
  - `test_haybale_core_keys_match_their_classes`: `ARRAY_WIDGET == ArrayWidget.class_identity.registry_key` (and the skin key once Task 3 lands; until then this test asserts only the widget key, and Task 3 extends it).
- [ ] **Step 2:** Run `uv run pytest tests/core/test_types/test_set_widget_config.py tests/core/test_skin/test_stage_skin_fields.py tests/barn/test_haybale_core_keys.py -q`. Expected: FAIL.
- [ ] **Step 3:** Implement Decisions 2–4.
- [ ] **Step 4:** Run the tests again, plus `tests/barn/builtin/ tests/core/test_types/ -q`. Expected: PASS.
- [ ] **Step 5:** Commit `feat(core): DataPort.set_widget_config, the widget-node skin tag and list`.

### Task 2: The widget nodes

**Files:**
- Create: `barn/haybale-core/haybale_core/nodes/widgets/__init__.py`, `base.py` (Decision 5), `slider.py` (both sliders), `number.py` (both numbers), `toggle.py`, `text.py`, `menu.py` (Decision 6)
- Test: `tests/barn/test_widget_nodes.py` (new, integration; `graph_with_library_system`). Keys come from `Cls.class_identity.registry_key`, and each node is `isinstance`-checked (unknown-key trap).

**Interfaces:**
- Consumes: Task 1's seams, `haybale_core.keys`.
- Produces: the seven node classes and `WidgetNode`. Task 3 relies on `ports["in"]`, `ports["value"]` and `props.stage_skin == WIDGET_NODE_SKIN`.

- [ ] **Step 1: Write the failing tests** (parametrized over the seven classes where marked ★):
  - ★ `test_a_widget_node_has_a_hidden_inlet_and_a_shown_outlet`: `ports["in"].show_widget is NEVER`, `ports["value"].show_widget is ALWAYS`, the outlet's `widget_key` is per the table, and `get_value()` equals the default.
  - ★ `test_a_widget_node_binds_the_widget_node_stage_skin`: `node.props.stage_skin == WIDGET_NODE_SKIN`. The descriptor's `widget_config["options"] is _widget_node_stage_skin_choices`.
  - `test_a_linked_value_is_forwarded`: Float Number A → Float Slider B (`value` → `in`). Write 0.73 on A's outlet and run `B.node._execute(context)` (a `MagicMock` context). B's outlet reads 0.73, and a sink downstream of B receives it.
  - `test_an_unlink_keeps_the_last_value`: after the above, delete the edge and execute B. B's outlet still reads 0.73.
  - `test_a_widget_write_reaches_downstream_at_once` (Decision 1 pin): `EditRoute(...).set_port(A.node_id, "value", 0.5, minimum=LevelMode.OPERATE)` returns True. The downstream inlet's `get_value() == 0.5` before any execution, and the downstream node's dirty-port set holds it.
  - `test_an_operator_write_is_not_an_undo_step` and `test_an_edit_write_is_one`: in OPERATE the history does not grow; in EDIT it grows by one.
  - `test_a_range_setting_reaches_the_widget_config`: Float Slider `range.max = 5.0` gives `ports["value"].widget_config["properties"]["max"] == 5.0`.
  - `test_a_number_without_bounds_has_no_min_or_max`: a fresh Float Number has neither key. Setting `range.min = 1.0` adds it, and setting it back to `None` removes it.
  - `test_a_driven_max_redraws_only_on_change`: promote `range.max` to an inlet and feed it 5.0 through an edge. `wrapper.redraw` (patched) is called once; feeding 5.0 again adds no call. The outlet value 7.0 stays 7.0.
  - `test_menu_options_reach_the_select`: `menu.options = ["A", "B"]` gives `widget_config["properties"]["options"] == ["A", "B"]`, and the outlet value `"One"` is unchanged.
  - `test_text_commits`: the Text outlet's widget config has `commit: True`.
  - `test_a_saved_widget_node_round_trips`: Int Slider with `range.max = 10` and outlet 7. Through `graph.to_dict()`, `clear()` and `load_from_dict()` it reads max 10 in both the setting and `widget_config`, and value 7.
  - `test_the_saved_value_reaches_downstream_on_link` (Q3 fact): an Int Number at 42, newly linked, delivers 42 after housekeeping (`graph` validation via `force_immediate_validation()`), with no execution.
- [ ] **Step 2:** Run `uv run pytest tests/barn/test_widget_nodes.py -q`. Expected: FAIL (import error).
- [ ] **Step 3:** Implement Decisions 5 and 6.
- [ ] **Step 4:** Run the tests again, plus `tests/core/node/ tests/core/test_settings/ -q`. Expected: PASS.
- [ ] **Step 5:** Commit `feat(haybale-core): seven widget nodes — sliders, numbers, toggle, text, menu`.

### Task 3: `WidgetNodeSkin`

**Files:**
- Create: `barn/haybale-core/haybale_core/skins/widget_node_skin.py` (Decision 7)
- Modify:
  - `tests/barn/test_haybale_core_keys.py` (add the skin key)
  - `tests/ui/harness/routes.py`: new route `/graph-widget-nodes`. A graph holds a Float Slider (with `range.max` promoted to an inlet), a Menu and a downstream Float Number, wired slider → number. The slider and menu are on stage. It mounts a stage canvas through `_mount_graph_canvas(..., channel=STAGE, level=_HarnessLevel(mode=LevelMode.OPERATE))`. A polled echo `data-testid="echo-downstream"` shows the number's `in` value, and `data-testid="menu-node-id"` and `slider-node-id` carry the node ids.
- Test: `tests/ui/skin/test_widget_node_skin.py` (new, integration; `card` pattern from `tests/graph_editor/test_ui_node_stage_skin.py`), `tests/ui/harness/test_widget_nodes.py` (new, browser)

**Interfaces:**
- Consumes: Task 2's nodes, `WIDGET_NODE_SKIN`.
- Produces: `WidgetNodeSkin` (registry key `WIDGET_NODE_SKIN`).

- [ ] **Step 1: Write the failing tests:**
  - `test_the_skin_draws_the_label_then_the_control`: on stage, a Float Slider card holds one label with `display_label` text, then one element with `data-hw-operable`.
  - `test_the_skin_draws_only_the_declared_outlet_widget`: with `range.max` promoted to an inlet whose Show Widget is `ALWAYS`, the stage card still draws exactly one widget (the outlet's).
  - `test_on_stage_the_skin_draws_no_pins` and `test_on_a_patch_canvas_it_draws_every_pin`: no `.connection-pin` on stage; on patch, one per port, `in` and the promoted inlet on the left and `value` on the right, each with `data-pin-dir-x` per side.
  - `test_the_skin_ignores_detail`: `honours_detail(on_stage=True) is False`, and so is `on_stage=False`.
  - `test_a_menu_fed_an_unknown_item_keeps_it`: on a rendered Menu card, write `"Four"` to the outlet with `port.set_value("Four")`. The outlet still reads `"Four"` afterwards, and no write reached the route.
  - Browser, `tests/ui/harness/test_widget_nodes.py`:
    - `test_an_operator_drives_a_slider_on_a_locked_stage`: drag the stage slider from its left to its right end. `echo-downstream` reads the slider's max (1.0).
    - `test_the_stage_shows_label_left_of_the_control`: the label's bounding box ends left of the slider's start, and both share a vertical band.
    - `test_a_menu_pick_on_stage_sends_the_item`: pick "Two". The Menu outlet echo (add `echo-menu` to the route) reads `Two`.
- [ ] **Step 2:** Run `uv run pytest tests/ui/skin/test_widget_node_skin.py -q`. Expected: FAIL.
- [ ] **Step 3:** Implement Decision 7. If `test_a_menu_fed_an_unknown_item_keeps_it` shows `SelectWidget` writing `None` back, guard it in `SelectWidget` (a view value of `None` the model did not hold is not written). Ledger that as a ruling.
- [ ] **Step 4:** Run the tests again, plus `tests/ui/skin/ tests/graph_editor/ -q` and `uv run pytest -m browser -n 4 tests/ui/harness/test_widget_nodes.py tests/ui/harness/test_graph_views.py tests/ui/harness/test_stage_edge_gate.py -q`. Expected: PASS.
- [ ] **Step 5:** Commit `feat(haybale-core): the widget-node stage skin — label left, then the control`.

### Task 4: Docs and gates

**Files:**
- Modify:
  - `docs/reference/glossary.md`:
    - **Widget node:** "A DATA node in haybale-core whose outlet's widget is the node: it shows what flows into its inlet and sends what the operator sets. Float/Int Slider, Float/Int Number, Toggle, Text, Menu. Not a CONTROL node (that one is EXEC-sequenced)." Aliases to avoid: control node, UI node.
    - **Widget-node skin:** the skin tagged `widget-node`; offered only in a widget node's Stage Skin list.
    - **`set_widget_config`:** "the seam through which a node changes its outlet's widget config; today it redraws the card, a later round makes it live." It goes beside **live widget_config callable**.
  - `docs/architecture/execution/edges/edges-arch.md` §3.5: one sentence. "A widget's write to an outlet runs its pipes at once, on the UI thread. An eager edge stores the value in the sink's inlet then, and the sink's node acts on it in its next frame."
  - `docs/components/skins/skin-canon.md`: in the stage section, a paragraph on the widget-node skin and how a third-party one joins the list (the three tags).
  - `docs/components/nodes/node-canon.md`: the user has uncommitted edits here, so leave it alone. A pointer to widget nodes waits for the user.
  - `docs/superpowers/plans/2026-10-12-editor-modes.md`: the 5d-3 line links this plan.
- No ADR: every choice here was settled in the inquisition, and the one new seam is explicitly temporary (Q6c).

- [ ] **Step 1:** Make the doc edits.
- [ ] **Step 2:** Run the gates:
  - `uv run ruff check . --extend-exclude .scratch/draw-perf -q` and `uv run ruff format --check .` (only `.scratch/draw-perf` may drift)
  - the full mypy command from CLAUDE.md
  - `uv run pytest -m "not browser and not perf" -n 4 -q > /tmp/t.log 2>&1; echo "exit=$?"` (the user-modified `test_prehydration` fixture may be the one failure; anything else is ours)
  - `uv run pytest -m browser -n 4 -q > /tmp/b.log 2>&1; echo "exit=$?"`
  - `uv run haywire docs --all`, then commit the regenerated library docs (seven nodes, one skin).

  Expected: all exit 0, apart from the one noted fixture.
- [ ] **Step 3:** Commit `docs: widget nodes — glossary, edges arch, skin canon, spec`.

### Live check (user, studio started from the main checkout)

1. In node search, type "slider": *Float Slider* and *Int Slider* appear under `core/widgets`. Add a Float Slider, a Float Number and a *Print* (or any FLOAT consumer), and wire slider → number → print.
2. Patch view: each widget node is a normal card in your patch skin, with the control in the *Value* row and no widget on *In*.
3. Add the slider and the number to the stage and switch to Stage: each shows its label on the left, then the control, with no frame and no pins. Its Stage Skin list offers only *Widget Node*.
4. Lock the canvas, run the graph and drag the slider: the number follows, and so does the print. Undo has nothing to undo (OPERATE writes are not recorded).
5. Unlock. In the slider's properties, set Max to 10: the slider's range grows on both cards. Promote Max to an inlet and wire a Float Number into it: changing that number moves the range.
6. Delete the slider → number edge while the graph runs: the number keeps its last value.
7. Add a Menu, set its options to Red/Green/Blue in the list widget, and pick Green on the stage: a downstream STRING consumer receives "Green".
8. Save, close and reopen: values, ranges, options and stage placement are as left.
