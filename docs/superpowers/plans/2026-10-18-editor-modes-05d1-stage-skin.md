# Editor modes, slice 5d-1: stage skin — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** The view picks the skin. Every node has a patch skin and a stage skin, each resolved through framework < graph < node. A skin no longer learns which view it draws for, and the default stage look is the *Stacked Stage* twin. A stage canvas refuses any new edge that it would not draw.

**Architecture:**
- `stage_skin` mirrors `skin`: a framework field, a graph shadow and a node mirror. `UINode` reads one or the other by `channel.stage`.
- `on_stage` leaves the public skin contract (`render`, `render_pin`, `SkinFactory.render`). The NodeSkin family keeps its internal helpers and takes the flag from a class attribute, `stage_twin`, which `StackedStageSkin` sets.
- Skins carry machine `tags` (a new `BaseIdentity` field, separate from nodes' `search_tags`). One tag-aware function builds every skin choice list.
- The edge gate is server-side, in the two canvas paths that create edges. A pin attribute lets the canvas refuse the drag early.

**Tech Stack:** Python 3.12, NiceGUI/Vue 3 (`canvas.vue`), pytest, Playwright browser tier.

**Spec:** [2026-10-12-editor-modes.md](2026-10-12-editor-modes.md) (Stage), as changed by the user's 5d inquisition of 2026-10-18 (Q11b–Q15, Q19–Q23, Q30; summarised under Decisions). This plan supersedes ADR 0054's "Skin contract: `on_stage`" decision.

## Global Constraints

- **Branch:** `feat/editor-modes-slice5d1` in `.worktrees/editor-modes-slice5d1`, cut from `feat/editor-modes-slice1` (`c45c53e1`). It merges into slice1 after the user's live check. Nothing goes to master until slice 6 lands. Slice1 holds an uncommitted edit to `docs/architecture/execution/edges/edges-arch.md` §3.5 from the inquisition; ask the user before cutting the branch whether to commit it first.
- **Saved files:** an untouched graph saves byte-identical. No `stage_skin`/`default_stage_skin`/`tags` key appears unless set.
- **No cross-view inheritance (Q12b, Q14 D):** the stage chain never falls back to the patch skin. `studio_stage_skin` defaults to the registry's default stage skin, which is fixed.
- **Every skin stays selectable in both chains (Q14 D),** filtered only by tags (Q30). Writes are not validated against the lists: `CHOICES` options are UI-only.
- **Tests and docs:** use the smallest test tier while iterating, then the full gates at the end. Docs follow `.claude/rules/python-docs.md`, and glossary/ADR edits land with the code (Task 4).

## Amendment (2026-10-18, after the build, Q32/Q37/Q38)

The user reversed Q14 D: `on_stage` stays in the skin contract. This supersedes Decisions 3, 5 (contract), 6 and 7 (detail) below; Decisions 1, 2, 4, 8 and the factory per-card fix stand.

- **Contract (ADR 0054, unchanged):** `render(main_card, wrapper, *, on_stage)`, `_render(wrapper, *, on_stage=False, route=None)`, `SkinFactory.render(key, wrapper, *, on_stage=False, ...)`, `render_pin(..., on_stage)`. `render_pin` stamps `data-pin-on-stage` (Decision 8).
- **UINode** picks `props.stage_skin` on a stage canvas and `props.skin` on a patch canvas, falling back to the registry's default skin, and passes `on_stage=channel.stage`.
- **No twins:** no `StackedStageSkin`, no `NodeSkin.stage_twin`, no `_is_default_stage` or registry default-stage tracking. `studio_stage_skin` defaults to `_default_skin` (Stacked), fixed.
- **Default skins on stage** ignore collapse (`is_collapsed(...) and not on_stage`), layout direction (`NodeSkin.layout_of(wrapper, *, on_stage=False)` returns `LEFT_TO_RIGHT` on stage) and detail (`BaseSkin.honours_detail(*, on_stage) -> bool`, default `True`; `NodeSkin` returns `not on_stage`; UINode stamps full detail when the skin says no). Annotation and Reroute keep their ADR 0054 stage behaviour.
- Dropped after discussion (Q33–Q36): no reroute gating, no affordance changes for reroutes.

## Decisions

1. **Tags.**
   - `BaseIdentity.tags: list[str] = field(default_factory=list)`, last field (`core/registry/identity.py`). It holds machine classification only; `NodeIdentity.search_tags` stays the node-search vocabulary.
   - `@skin` does `kwargs.setdefault("tags", [SKIN_TAG_GENERAL])`, so an untagged skin is general.
   - Constants in `core/skin/settings.py`: `SKIN_TAG_GENERAL = "general"`, `SKIN_TAG_SPECIAL = "special"`, `SKIN_TAG_STAGE_ONLY = "stage-only"`.
   - `DataPort` inherits the field through `DataTypeIdentity`. Its `to_dict` skips a default-equal field, so ports save unchanged.
2. **Choice lists.** `skin_choices(*, include: Collection[str], exclude: Collection[str] = ()) -> dict[str, str]` lists the visible skins that hold **all** of `include` and **none** of `exclude`, as `{registry_key: label}`.
   - `_patch_skin_choices()` uses include `general`, exclude `special`, `stage-only`.
   - `_stage_skin_choices()` uses include `general`, exclude `special`.
   - `_node_skin_choices` is deleted. Its callers (`studio_skin`, `GraphProperties.default_skin`, `NodeProperties.skin` and the tests) use `_patch_skin_choices`.
3. **Default stage skin.**
   - `SkinIdentity` gains `_is_default_stage: bool = False` and `_default_stage_priority: int = 0`.
   - `SkinRegistry` tracks them exactly as it tracks `_is_default`: `_default_stage_skin_name`, `_default_stage_priority`, `_find_next_default_stage_skin`, and `get_default_stage_skin_registry_key(fallback: str | None = None) -> str | None`.
   - `_default_stage_skin()` returns that key, else the default skin key, else `"default"`, mirroring `_default_skin`.
4. **Fields (Q11b B).** Labels and descriptions are given verbatim.
   - **Framework:** `NodeDefaultSkinSettings.studio_stage_skin = setting[CHOICES](default=_default_stage_skin, label="Default Studio Stage Skin", description="Studio default skin for nodes on a stage", category=CATEGORY_NODE_SKINS, widget_config={"options": _stage_skin_choices})`. It is not a shadow of `studio_skin`.
   - **Graph:** `GraphProperties.default_stage_skin = shadow(src=NodeDefaultSkinSettings.studio_stage_skin, label="Default Stage Skin", description="Default skin for nodes on THIS graph's stage. Overrides the studio default; a node's own stage skin overrides this.", category="appearance", order=11, widget_config={"options": _stage_skin_choices})`.
   - **Node:** `NodeProperties.stage_skin = graph(src=GraphProperties.default_stage_skin, label="Stage Skin", description="Skin for THIS node on the stage", category="appearance", order=11, widget_config={"options": _stage_skin_choices})`.
   - `"stage_skin"` joins `NodeProperties.REDRAW_FIELDS` after `"skin"`.
   - `AnnotationNode.props` and `RerouteNode.props` bind `stage_skin = setting[CHOICES]("<their own skin key>", label="Stage Skin", category="appearance", order=11)`, beside their `skin`.
5. **Skin contract.**
   - `BaseSkin.render(self, main_card, wrapper)` and `BaseSkin._render(self, wrapper, *, route=None)`.
   - `SkinFactory.render(skin_registry_key, wrapper, *, route=None, _is_error_render=False)`.
   - `render_pin(...)` loses `on_stage`. It stamps `data-pin-on-stage` when `pin.on_stage`.
   - `BaseSkin.honours_detail: ClassVar[bool] = True`.
6. **Stage twin.**
   - `NodeSkin.stage_twin: ClassVar[bool] = False`. Each NodeSkin-family `render()` passes `on_stage=self.stage_twin` to the internal helpers, which keep their `on_stage` parameter and behaviour.
   - `NodeSkin._render_pin` keeps the filter `if on_stage and not port.on_stage: return None` before calling `render_pin`.
   - In `stacked_skin.py`: `@skin(label="Stacked Stage", description="The Stacked card for a stage: the node label as title, one row per port that shows a widget, on-stage pins only", tags=[SKIN_TAG_GENERAL, SKIN_TAG_STAGE_ONLY], _is_default_stage=True) class StackedStageSkin(StackedNodeSkin)`, with `stage_twin = True` and `honours_detail = False`.
   - **Q15 A:** in a twin, `NodeSkin.layout_of` returns `LayoutDirection.LEFT_TO_RIGHT`, and `is_collapsed` returns `False`.
   - `SplitNodeSkin`, `ErrorNodeSkin`, `AnnotationSkin` and `RerouteSkin` lose every stage branch and draw as in the patch in both views (Q19 B).
7. **UINode.**
   - `UINode._skin_key() -> str | None` returns `props.stage_skin` if `channel.stage`, else `props.skin`. If that is `None`, it falls back to the registry's default stage key (stage) or default key (patch). `_render` uses it.
   - `_apply_detail_attr` stamps `NodeDetail.FULL.value` when the resolved skin class has `honours_detail` false. It is also called at the end of a successful `_render`, so a skin change re-stamps it.
8. **Edge gate.**
   - `stage_takes_edge(graph, source_node_id, outlet_port_id, sink_node_id, inlet_port_id) -> bool` in `core/graph/stage.py`. It returns false when either end names an existing port whose `on_stage` is false. A missing port (a ghost `root_in`/`root_out`) does not count.
   - On a stage canvas, `VisualLayerHandlers.process_edge_creation` and the pending-edge auto-wire (`visual_layer.py` ~1328–1385) refuse such an edge. They call `ui.notify("This connection would not show on the stage. Make it in the patch view.", type="warning")` and create nothing. The auto-wire also emits `SyncEdgeConnectCancelEvent()`.
   - In `canvas.vue`, the pin branch at ~:1756 returns before `_enterActiveEdge(pin)` when `this.$el.hasAttribute('data-hw-stage') && !('pinOnStage' in pin.dataset)`. The attribute index at the top of `<script>` gains `data-pin-on-stage`.

## Review Focus

1. **Legacy graph.** A graph saved before this slice opens on stage with *Stacked Stage* cards that look exactly like today's stage cards: one row per shown widget, annotation pins, expanded. It saves byte-identical. Test: Task 2 `test_an_untouched_graph_saves_no_stage_skin_keys`, plus the rewritten `test_stage_render.py`.
2. **Stage skin change.** Changing a node's stage skin redraws its stage card but leaves its patch card visually unchanged, and the reverse. Test: Task 2 `test_a_stage_skin_change_redraws_with_the_new_skin_in_the_stage_view_only`.
3. **Annotations on stage.** Text and connector pins still draw and connect on stage. The gate never blocks an annotation link, including a drop onto a side's open `ADD[ANNOTATION]` slot. Test: Task 3 `test_an_annotation_link_is_created_on_stage`, `test_a_drop_on_an_annotation_open_slot_is_created_on_stage`.
4. **A patch skin chosen for the stage.** It draws data pins, and dragging one starts nothing in the browser. A crafted `EdgeCreatedEvent` is refused server-side with the notice. Test: Task 3 browser `test_a_data_pin_drag_does_not_start_on_stage`, `test_a_data_edge_is_refused_on_a_stage_canvas`.
5. **Third-party skins.** A skin registered without `tags` appears in the patch and stage lists; one tagged `special` appears in neither. Test: Task 1 `test_an_untagged_skin_is_general`, `test_a_special_skin_is_in_no_general_list`.

---

### Task 1: Core — tags, choice lists, default stage skin, fields

**Files:**
- Modify:
  - `packages/haywire-core/src/haywire/core/registry/identity.py`
  - `packages/haywire-core/src/haywire/ui/skin/base.py` (`SkinIdentity`)
  - `packages/haywire-core/src/haywire/ui/skin/decorator.py` (tags default)
  - `packages/haywire-core/src/haywire/ui/skin/registry.py` (default-stage tracking)
  - `packages/haywire-core/src/haywire/core/skin/settings.py` (constants, `skin_choices`, `_patch_skin_choices`, `_stage_skin_choices`, `_default_stage_skin`, `studio_stage_skin`; delete `_node_skin_choices`)
  - `packages/haywire-core/src/haywire/core/graph/properties.py`
  - `packages/haywire-core/src/haywire/core/node/properties.py`
  - `packages/haywire-core/src/haywire/barn/builtin/nodes/annotation.py`, `.../reroute.py`
- Test: `tests/core/test_skin/test_stage_skin_fields.py` (new; integration, `library_system` fixture as in `tests/ui/skin/test_stage_render.py`)

**Interfaces:**
- Produces:
  - `BaseIdentity.tags`
  - `SKIN_TAG_GENERAL`, `SKIN_TAG_SPECIAL`, `SKIN_TAG_STAGE_ONLY`, and `skin_choices(*, include, exclude=()) -> dict[str, str]` (all in `haywire.core.skin.settings`)
  - `SkinRegistry.get_default_stage_skin_registry_key(fallback=None)`
  - `NodeDefaultSkinSettings.studio_stage_skin`, `GraphProperties.default_stage_skin`, `NodeProperties.stage_skin`

- [ ] **Step 1: Write the failing tests:**
  - `test_skin_choices_need_every_include_and_no_exclude`: register three test skins tagged `["general"]`, `["general", "stage-only"]` and `["special", "x"]`. `skin_choices(include=["general"], exclude=["stage-only"])` holds only the first. `skin_choices(include=["special", "x"])` holds only the third. `skin_choices(include=["special", "y"])` is empty.
  - `test_an_untagged_skin_is_general`: a skin registered with `@skin()` has `tags == ["general"]` and is in both `_patch_skin_choices()` and `_stage_skin_choices()`.
  - `test_a_special_skin_is_in_no_general_list`.
  - `test_every_skin_field_uses_its_views_list`: the `widget_config["options"]` of `studio_skin`, `GraphProperties.default_skin` and `NodeProperties.skin` is `_patch_skin_choices`, and that of `studio_stage_skin`, `default_stage_skin` and `stage_skin` is `_stage_skin_choices`.
  - `test_the_default_stage_skin_follows_registration`: registering two skins with `_is_default_stage=True` and priorities 0 and 5 makes the priority-5 key the default. Unregistering it falls back to the other. With none registered, the stage key falls back to the default skin key.
  - `test_the_stage_skin_chain_resolves_node_then_graph_then_framework`: a node's `props.stage_skin` reads the framework default. It reads the graph's value once `graph.props.default_stage_skin` is set, and its own once set locally. Setting `props.skin` changes nothing on the stage chain.
  - `test_annotation_and_reroute_bind_their_own_stage_skin`: a fresh node of each reads its own skin key from `stage_skin`.
  - `test_a_port_without_tags_saves_no_tags_key`: no `"tags"` in `port.to_dict()["kwargs"]` for a plain `FLOAT.as_inlet` port.
- [ ] **Step 2:** Run `uv run pytest tests/core/test_skin/test_stage_skin_fields.py -q`. Expected: FAIL (import error).
- [ ] **Step 3:** Implement Decisions 1–4. The `skin_choices` docstring carries an example per list.
- [ ] **Step 4:** Run the tests again, plus `tests/core/test_settings/`, `tests/core/test_graph/test_graph_props_serialization.py`, `tests/ui/skin/test_node_skin_settings.py` and `tests/core/node/`. Expected: PASS. Grep `_node_skin_choices` across `packages/`, `barn/` and `tests/`: zero hits.
- [ ] **Step 5:** Commit `feat(core): stage skin fields, skin tags and tag-filtered skin lists`.

### Task 2: Skins — drop `on_stage`, Stacked Stage twin, UINode picks by view

**Files:**
- Modify:
  - `packages/haywire-core/src/haywire/ui/skin/base.py`, `.../ui/skin/factory.py`, `.../ui/skin/pin_render.py`
  - `barn/haybale-studio/haybale_studio/skins/node_skin.py`, `stacked_skin.py`, `split_skin.py`, `error_skin.py`
  - `packages/haywire-core/src/haywire/barn/builtin/skins/annotation_skin.py`, `reroute_skin.py`
  - `barn/haybale-graph-editor/haybale_graph_editor/editors/graph_canvas/ui_node.py` (`_render`, new `_skin_key`, `_apply_detail_attr`)
- Test:
  - `tests/ui/skin/test_stage_render.py`: rewrite to target `StackedStageSkin` and delete the cases listed in Step 1.
  - Other tests that pass `on_stage=` (grep `tests/` for `on_stage=` in a render/render_pin call): `test_pin_native_tag_contract.py`, `test_pin_render_layout.py`, `test_pin_wire_attribute.py`, `tests/graph_editor/test_stage_folds.py`, `test_stage_parity.py`, `test_graph_editor_views.py`, `tests/ui/test_canvas_handlers/test_stage_visual_layer.py`.
  - `tests/graph_editor/test_ui_node_stage_skin.py` (new; the `card` fixture as in `test_ui_node_stacking.py`).

**Interfaces:**
- Consumes: `NodeProperties.stage_skin`, `get_default_stage_skin_registry_key`, `SKIN_TAG_*` (Task 1).
- Produces: `BaseSkin.render(main_card, wrapper)`, `BaseSkin.honours_detail`, `NodeSkin.stage_twin`, `StackedStageSkin` (tests take its key from `StackedStageSkin.class_identity.registry_key`, never a literal), `render_pin` without `on_stage`, `data-pin-on-stage`.

- [ ] **Step 1: Write the failing tests:**
  - In `test_stage_render.py`, the stage cases (rows only for shown widgets, on-stage pins only, ghost pins, collapsed drawn expanded, folds on stage) now render through `StackedStageSkin().render(card, wrapper)`.
    - The vertical-layout case becomes `test_the_stage_twin_draws_left_to_right_whatever_the_layout`: under `TOP_TO_BOTTOM`, pins carry `data-hw-layout="left_to_right"`.
    - Delete `test_a_skin_without_the_on_stage_keyword_fails_loudly`, `test_the_error_fallback_forwards_on_stage`, both split-skin stage cases, and the reroute/annotation "no pins on stage" cases.
  - `test_the_stage_twin_is_registered_as_the_default_stage_skin`: `get_default_stage_skin_registry_key()` is the `StackedStageSkin` key. It appears in `_stage_skin_choices()` and not in `_patch_skin_choices()`.
  - `test_an_annotation_draws_the_same_pins_in_both_views`: a linked control pin draws under `AnnotationSkin` with no view input.
  - `test_render_pin_marks_on_stage_pins`: an `ANNOTATION` swinglet's pin carries `data-pin-on-stage`; a `FLOAT` inlet's does not.
  - In `test_ui_node_stage_skin.py`:
    - `test_a_stage_card_uses_the_stage_skin_and_a_patch_card_the_skin`.
    - `test_a_stage_skin_change_redraws_with_the_new_skin_in_the_stage_view_only`: set `stage_skin` to the Stacked key. The stage `UINode` renders with `StackedNodeSkin`; the patch `UINode`'s skin key is unchanged.
    - `test_the_stage_twin_stamps_full_detail`: `props.detail = "pins"` stamps `data-node-props-detail="full"` on the stage container and `"pins"` on the patch one.
    - `test_an_untouched_graph_saves_no_stage_skin_keys`: `"stage_skin"` is not in the node's saved props values, and `"default_stage_skin"` is not in the graph's.
- [ ] **Step 2:** Run `uv run pytest tests/ui/skin/ tests/graph_editor/test_ui_node_stage_skin.py -q`. Expected: FAIL.
- [ ] **Step 3:** Implement Decisions 5–7. Each studio skin's `render` docstring states which view-independent look it draws. Grep `packages/`, `barn/` and `tests/` for `on_stage=` passed to `render(`, `_render(`, `SkinFactory.render(` or `render_pin(`: zero hits outside NodeSkin-internal helpers.
- [ ] **Step 4:** Run the tests again, plus `tests/ui/`, `tests/graph_editor/` and `uv run pytest -m browser -n 4 tests/ui/harness/test_graph_views.py tests/ui/harness/test_stage_origin.py -q`. Expected: PASS.
- [ ] **Step 5:** Commit `feat(skins): the view picks the skin — Stacked Stage twin, on_stage leaves the skin contract`.

### Task 3: Stage edge gate

**Files:**
- Modify:
  - `packages/haywire-core/src/haywire/core/graph/stage.py` (`stage_takes_edge`)
  - `barn/haybale-graph-editor/haybale_graph_editor/editors/graph_canvas/handlers/visual_layer.py` (`process_edge_creation`, the pending-edge auto-wire)
  - `packages/haywire-core/src/haywire/ui/components/graph/canvas.vue` (pin branch ~:1756, attribute index)
  - `tests/ui/harness/routes.py`: new route `/graph-stage-gate`. Two on-stage `DataNodeTemplate` nodes with `stage_skin` set to the `StackedNodeSkin` key, plus two on-stage annotations. A polled label `data-testid="server-edges"` holds the sorted edge ids, as in the swinglet route.
- Test: `tests/core/test_graph/test_stage_graph.py` (append), `tests/ui/test_canvas_handlers/test_stage_visual_layer.py` (append), `tests/ui/harness/test_stage_edge_gate.py` (new, browser)

**Interfaces:**
- Consumes: `data-pin-on-stage` (Task 2), the `data-hw-stage` canvas root (5c).
- Produces: `stage_takes_edge(graph, source_node_id, outlet_port_id, sink_node_id, inlet_port_id) -> bool`.

- [ ] **Step 1: Write the failing tests:**
  - `test_stage_takes_annotation_edges_only`: annotation→annotation is True; data→data is False; data→a missing `root_in` is False; annotation→a missing port is True.
  - `test_a_data_edge_is_refused_on_a_stage_canvas`: an `EdgeCreatedEvent` between two data pins on a stage-channel handler creates no edge and notifies the exact copy from Decision 8. The same event on a patch-channel handler creates it.
  - `test_an_annotation_link_is_created_on_stage`.
  - `test_a_drop_on_an_annotation_open_slot_is_created_on_stage`: the target is the side's `ADD[ANNOTATION]` slot.
  - `test_an_auto_wire_from_a_data_pin_is_refused_on_stage`: a pending data pin plus a new node on a stage canvas gives no edge and a `SyncEdgeConnectCancelEvent`.
  - Browser `test_a_data_pin_drag_does_not_start_on_stage`: mouse-down on a data pin and move 60px. `.graph-canvas.edge-dragging` never appears, and `server-edges` is unchanged.
  - Browser `test_an_annotation_pin_drag_connects_on_stage`: drag annotation pin to annotation pin; `server-edges` gains one id.
- [ ] **Step 2:** Run `uv run pytest tests/core/test_graph/test_stage_graph.py tests/ui/test_canvas_handlers/test_stage_visual_layer.py -q`. Expected: FAIL.
- [ ] **Step 3:** Implement Decision 8. The handler-side check is the enforcement; the comment on the `canvas.vue` line says it only saves a drag the server would refuse.
- [ ] **Step 4:** Run the tests again, plus `uv run pytest -m browser -n 4 tests/ui/harness/test_stage_edge_gate.py tests/ui/harness/test_graph_connect.py -q`. Expected: PASS.
- [ ] **Step 5:** Commit `feat(graph-editor): a stage canvas refuses edges it would not draw`.

### Task 4: Docs and gates

**Files:**
- Create: `docs/adr/0056-the-view-picks-the-skin.md`
- Modify:
  - `docs/adr/0054-the-stage-view.md` (front-matter description; the "Skin contract: `on_stage`" bullet)
  - `docs/components/skins/skin-canon.md` (the `render` signatures at ~:107/:186/:202; the section "Stage view: the `on_stage` keyword" at ~:405)
  - `docs/reference/glossary.md`
  - `docs/superpowers/plans/2026-10-12-editor-modes.md` (Stage "Skin contract" paragraph, "Control nodes" bullet, Inset "render(..., on_stage=True)" mentions, Sequence 5d)

- [ ] **Step 1:** Make the doc edits:
  - **ADR 0056** (format of 0054; `status: accepted`; `see-also: ADR-0054`):
    - Context: one skin drew both views through a required `on_stage` keyword, so a node's stage look was fixed to its patch skin.
    - Decision: Decisions 1–8 in prose.
    - Alternatives: the keyword kept, with a widget skin branching on it; inheriting the stage skin from the patch skin per tier; a `stage_variant` link on the skin identity; refusing tagged skins at write time.
    - Consequences: a patch skin chosen for the stage draws every pin, and the gate makes those inert; annotations and reroutes draw control/data pins on stage; third-party skins lose the keyword.
  - **ADR 0054:** the skin-contract bullet ends with "Superseded by ADR 0056: the view picks the skin." The description's last clause becomes "a stage view draws each node with its stage skin (ADR 0056)".
  - **skin-canon:** signatures without `on_stage`. The stage section becomes "Stage view: the stage skin", covering Decisions 4–8, the tag table from Q30, and how a skin author tags a stage-only or node-specific skin.
  - **Glossary:**
    - Add rows **Stage skin**, **Stage twin**, **Tags** (machine classification on every component's identity; contrast **Search tags**) and **Search tags** (words a person types in node search), each linking ADR 0056.
    - **On-stage wire** row: replace "a stage canvas draws only the pins of on-stage wires (`render(..., on_stage=True)`)" with "a stage canvas creates and draws only edges on on-stage wires".
    - **Layout channel** row: `stage` means the canvas uses the stage skin and draws only on-stage edges.
  - **Spec:**
    - The Stage "Skin contract" paragraph points to ADR 0056.
    - "Control nodes" becomes **Widget nodes**, renamed because "control node" names the EXEC-sequenced CONTROL node, and links the 5d decisions.
    - Inset draws interior nodes "with their stage skin".
    - Sequence 5d lists 5d-1 (this plan), 5d-2 list widget and 5d-3 widget nodes.
- [ ] **Step 2:** Run the gates:
  - `uv run ruff check .` and `uv run ruff format --check .`
  - the full mypy command from CLAUDE.md
  - `uv run pytest -m "not browser and not perf" -n 4 -q > /tmp/t.log 2>&1; echo "exit=$?"`
  - `uv run pytest -m browser -n 4 -q > /tmp/b.log 2>&1; echo "exit=$?"`
  - `uv run haywire docs --all`, then commit any regenerated library docs (new skin, new props fields).

  Expected: all exit 0.
- [ ] **Step 3:** Commit `docs: the view picks the skin — ADR 0056, skin canon, glossary, spec`.

### Live check (user, studio started from the worktree)

1. Open a graph with nodes and annotations on stage. The stage looks as before: cards with one row per shown widget, annotation links and pins, collapsed nodes drawn expanded. Saving without edits leaves the file unchanged (`git diff`).
2. On a graph with a vertical layout direction, stage cards read left to right; the patch keeps its direction.
3. Set Node Detail to "Pins" on an on-stage node: the patch card thins, the stage card does not.
4. Node properties → Stage Skin offers *Stacked* and *Split*. Set one on-stage node's Stage Skin to *Split*: its stage card redraws as a Split stage card, its patch card is unchanged. Undo restores it.
5. Graph properties → Default Stage Skin = *Split*: every on-stage node without its own stage skin follows; annotations keep their face.
6. On stage, drag between two annotations: they connect.
7. Studio settings → Default Studio Skin = *Split*: the patch changes, the stage does not.
