# Editor modes, slice 5a-2: the stage is a display, not a mode — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Stage view stops being an arrange-only mode. Editing in stage view is exactly editing in patch view. What differs is only the display:
- stage view shows the on-stage nodes, at their stage rect;
- each node is drawn with its normal patch card: same skin, title, rows, labels and widgets;
- the only pins drawn are on-stage pins (annotation pins, including annotation ADD slots);
- ghost pins stay;
- a collapsed node is drawn expanded.

**Why:** the live check of slice 5a on 2026-10-15 showed that 5a had misread the intent. Two things were wrong:
- the frameless R3 face drew a ported-less node as nothing, and drew an annotation as a column of pins;
- the arrange-only gating refused edits the user wants.

**Base:** branch `feat/editor-modes-slice5a` at 143ed9c4 (slice 5a, already fast-forwarded into `feat/editor-modes-slice1`). Plan 5a: [2026-10-14-editor-modes-05a-stage-core.md](2026-10-14-editor-modes-05a-stage-core.md). Spec: [2026-10-12-editor-modes.md](2026-10-12-editor-modes.md).

## Decisions (user, 2026-10-15) — these override plan 5a and the spec where they differ

1. **No arrange-only.** Stage view allows every edit patch view allows, at the same tier: paste, duplicate, cut, node creation, edge creation and reconnection, every context menu (selection, background, edge), every toolbar panel and every editor command. The lock and the tiers still apply exactly as in patch view. 5a's Decision 7 (Q7a) and Review Focus 4 are void.
2. **Q3b.** A stage card keeps every row and label of the patch card. Only pins differ.
3. **Q4b.** A node collapsed in the patch is drawn expanded on stage. Port-group folds are untouched.
4. **Q5a.** Edges on stage are editable like any edge. The edge context menu works in stage view. Since stage view draws only on-stage edges, those are the only edges it can reach.
5. **Q7a.** A node created, pasted or duplicated while stage view is active lands **on stage** at the gesture position (stage coordinates: the click, the paste point, or an offset from the original for a duplicate). Its patch position takes the same numbers. It is one undo step with the creation.
6. **Q8, the skin contract.**
   - `BaseSkin.render(self, main_card, wrapper, *, on_stage: bool)`. The keyword is **required**, so a skin outside the repo breaks loudly, not silently.
   - `render_pin(..., on_stage: bool)` gains a **required** keyword. With `on_stage=True` it returns `None` for a port whose `port.on_stage` is false. With `False` it behaves as today.
   - `render_ghost_pin` is unchanged: ghost pins still give an orphaned edge a home.
   - Each skin's collapse check becomes `self.is_collapsed(wrapper) and not on_stage`, or the skin's equivalent.
   - `SkinFactory.render(key, wrapper, *, on_stage: bool = False, ...)` calls `skin._render(wrapper, on_stage=...)`, which calls `render(card, wrapper, on_stage=...)`. The error-skin fallback forwards it.
   - `UINode._render` passes `on_stage=self.channel.stage`.
   - `BaseSkin.render_stage`, `BaseSkin._render_stage`, the R3 default face and `_STAGE_PIN_GUTTER`/`_STAGE_PIN_PROTRUSION` are **deleted**.
7. **Kept from 5a:**
   - the STAGE channel, props, extents, `on_stage` and `NODE_STAGE_CHANGED`;
   - the two keep-alive views, the header switch, `ToggleStageView` and `open_view`;
   - the origin marker and clamps;
   - Add to Stage and Remove from Stage (rows and events);
   - selection pruning when a stage canvas unmounts a node;
   - the per-canvas `_syncNodePosition`.

## Global Constraints

- Patch view behaviour is unchanged by this plan. Every pre-5a patch test passes untouched.
- `SelectionMenu` shows Add to Stage when the selection holds an off-stage node, and Remove from Stage when it holds an on-stage one, in **both** views, at EDIT.
- Commit trailer: `Co-Authored-By: Claude Opus 5.5 (1M context) <noreply@anthropic.com>`.
- Docs follow `.claude/rules/python-docs.md`. ADR/glossary changes land in Task 4.

---

### Task 1: Revert the arrange-only gating

**Files** (from a grep for `in_stage_view|stage_allowed|_STAGE_COMMANDS|StageSelectionMenu`; re-grep, and also grep `stage=True` in `@handles_event` sites and `channel.stage` in handlers):
- `barn/haybale-graph-editor/haybale_graph_editor/editors/graph_canvas/event_handlers.py`: drop the `stage` parameter of `handles_event`, and `stage_allowed`. Drop `stage=True` from every `@handles_event` site.
- `graph_canvas_manager.py`: drop the stage refusal in `_handle_canvas_event`. Drop the `duplicate_selection`/`cut_selection` stage no-ops.
- `handlers/context_menu.py`: the background menu and the edge menu open in stage view; the selection menu is `SelectionMenu` in both views.
- `handlers/selection_toolbar.py`: the ⋯ hosts `SelectionMenu` in both views. Remove the `EditState.stage_view` write.
- `surfaces/selection.py`, `surfaces/__init__.py`: delete `StageSelectionMenu`. Keep `SelectionActions.add_to_stage`/`remove_from_stage`.
- `panels/graph/menu/selection/stage.py`:
  - delete the stage-surface rows (StageRemove/StageCopy/StageDelete panels);
  - keep the Add to Stage and Remove from Stage rows in `SelectionMenu`, polled per Global Constraints.
- `panels/graph/toolbar/selection.py`, `appearance.py`, `style.py`, `panels/_gating.py`: remove the `in_stage_view` gates and the helper.
- `state/edit_state.py`: remove `stage_view`.
- `editors/graph_editor.py`: remove `_STAGE_COMMANDS` and its branch in `accepts_command`.
- `generated/graph_events.js`: regenerate only if an event class is removed. `AddToStageEvent`/`RemoveFromStageEvent` stay.

**Tests:**
- Rewrite `tests/graph_editor/test_stage_gating.py` as `tests/graph_editor/test_stage_parity.py`, at EDIT in stage view:
  - paste, duplicate, cut, node creation, edge creation, reconnect, drag, resize and delete all run;
  - the background menu and edge menu open;
  - the toolbar's Collapse, Appearance, Lock and Style poll as in patch view;
  - `accepts_command` accepts Paste/Duplicate/Cut;
  - the Add/Remove rows behave per Global Constraints in both views;
  - in a locked stage view, OPERATE is still capped exactly as in patch view.
- Keep the selection-prune tests from the 5a fix wave.
- Delete the toolbar-stage tests from 5a, and revert the `stage_view=False` additions to existing test fakes.

- [ ] Steps: grep → edit → `uv run pytest tests/graph_editor/ tests/ui/ -m "not browser" -n 4 -q` → commit `revert(graph-editor): stage view edits like patch view`.

### Task 2: The stage card is the patch card with only on-stage pins

**Files:**
- `packages/haywire-core/src/haywire/ui/skin/base.py`: the `render` signature, `_render`, `_render_into_card`. Delete `render_stage`, `_render_stage`, the R3 face and its constants.
- `packages/haywire-core/src/haywire/ui/skin/pin_render.py`: `render_pin(..., on_stage: bool)`, a required keyword.
- `packages/haywire-core/src/haywire/ui/skin/factory.py`: the `on_stage` keyword (rename from `stage`), forwarded in the error fallback.
- The skins: `annotation_skin.py`, `reroute_skin.py` (core); `error_skin.py`, `stacked_skin.py`, `split_skin.py`, `node_skin.py` (haybale-studio). Each:
  - takes `on_stage`;
  - passes it to every `render_pin` call;
  - applies `and not on_stage` to its collapse check.
- `ui_node.py`: `on_stage=self.channel.stage`.
- Grep every other `render_pin(` and `.render(` caller of a skin (properties/ports panels, wizard templates, `barn/haybale-testing` skins, test skins under `tests/`) and update them. Skin templates or examples in docs get the new signature (Task 4 for prose).

**Tests:** rewrite `tests/ui/skin/test_stage_face.py` as `tests/ui/skin/test_stage_render.py`:
- a Stacked/Node-skin node renders on stage with the same card classes and title as in the patch, and keeps every row label (Q3b);
- no pin for an EXEC or data port; widgets are present and registered in `widget_instances`;
- an annotation node on stage has its text, its grown annotation pins and its ADD slots, but no exec/done pin, even when linked;
- ghost pins are present on stage;
- a node with `collapsed=True` renders expanded on stage and collapsed in the patch;
- `render_pin(port, ..., on_stage=True)` returns `None` for an EXEC port and a pin for an ANNOTATION port;
- `on_stage=False` is today's behaviour;
- a skin missing the `on_stage` keyword raises `TypeError`;
- the error fallback forwards `on_stage`.

Update the browser tests that assumed the R3 face (`tests/ui/harness/test_stage_origin.py`, `tests/ui/harness/test_graph_views.py`) for the patch card's geometry: same assertions, new measurements.

- [ ] Steps: baseline ruff/mypy on touched paths → edit → `uv run pytest tests/ui/ tests/graph_editor/ -m "not browser" -n 4 -q` → `uv run pytest -m browser -n 4 -q` → commit `feat(skin): a stage render is the patch card with only on-stage pins`.

### Task 3: Nodes made in stage view land on stage (Q7a)

**Files:** find every creation path the canvas drives, by grepping the graph-editor handlers for node creation, paste, duplicate, the node wizard / Add-node menu at a click position, and drop-to-create from an edge drag. Each one already receives a canvas position. In a stage canvas:
- the new node's `node_data` props get `on_stage=True`;
- `stage_x`/`stage_y` = `STAGE.from_canvas(canvas position)`, or the original's stage position plus the usual duplicate offset;
- `stage_size_adapt="auto"`;
- `posX`/`posY` take the same numbers as `stage_x`/`stage_y`.

Do this in the node data **before** the add, so the creation stays one undo step and the patch canvas mounts the node at that patch position. Reuse the existing creation actions; add no new action.

**Tests:** `tests/graph_editor/test_stage_creation.py`:
- for each path, in a stage canvas: the node is on stage at the expected stage position, `posX/posY` equal it, and one undo removes it;
- in a patch canvas, the same paths leave `on_stage` False and are unchanged.

- [ ] Steps: grep → edit → `uv run pytest tests/graph_editor/ tests/ui/ -m "not browser" -n 4 -q` → commit `feat(graph-editor): a node made in stage view lands on stage`.

### Task 4: Docs

- Edit `docs/adr/0054-the-stage-view.md` in place. It is not yet on master.
  - Replace arrange-only with "stage view is a display, editing is unchanged" (Decision 1).
  - Replace the R3 face with the `render(..., *, on_stage)` contract (Decision 6).
  - Add Q7a.
  - Under Considered options, record arrange-only and the frameless face as rejected, with the 2026-10-15 reason.
- `docs/reference/glossary.md`: update Stage view, Stage face (remove it, or redefine it as "a node's patch card drawn with only on-stage pins"), and On-stage wire.
- `docs/guides/security.md`: remove the stage arrange-only rule. The lock and the tiers apply in both views alike.
- `docs/components/skins/skin-canon.md`: the `on_stage` keyword on `render()` and `render_pin()`, the collapse rule, and the fact that ghost pins stay.
- The spec, `docs/superpowers/plans/2026-10-12-editor-modes.md`, under "Stage":
  - replace "Unlocked stage view arranges only, except …" with Decision 1;
  - replace the `render_stage()` default-face bullet with Decision 6;
  - note Q7a.
- Plan 5a: add a one-line note at its top: "Superseded in part by 2026-10-15-editor-modes-05a2-stage-is-a-display.md (Decisions 1 and 6)."
- Run:
  - `uv run haywire docs barn/haybale-graph-editor`, `uv run haywire docs barn/haybale-studio`, `uv run haywire docs barn/haybale-core`;
  - `uv run python scripts/bake_docs.py`;
  - `uv run mkdocs build --strict`;
  - `uv run pytest tests/ -k "bake or docs" -n 4 -q`.

  Commit the doc edits first, because the docs test resets `barn/haybale-testing`.
- [ ] Commit `docs: the stage is a display (ADR 0054 amended)`.

### Task 5: Full gate

- [ ] `uv run ruff check . && uv run ruff format --check .`
- [ ] The full mypy command from CLAUDE.md.
- [ ] `uv run pytest -m "not browser and not perf" -n 4 -q`, which must give exit=0.
- [ ] `uv run pytest -m browser -n 4 -q`, which must give exit=0.
