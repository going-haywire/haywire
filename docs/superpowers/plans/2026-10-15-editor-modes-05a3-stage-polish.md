# Editor modes, slice 5a-3: stage polish, and Save-As keeps the canvas — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Follow-ups from the user's live check of slices 5a and 5a-2 on 2026-10-15. All 13 steps passed; this plan covers the six wrinkles that check found. They are listed as A–F under Decisions.

**Base:** branch `feat/editor-modes-slice5a` at 3720665b, already fast-forwarded into `feat/editor-modes-slice1`. Earlier plans: [05a](2026-10-14-editor-modes-05a-stage-core.md) and [05a-2](2026-10-15-editor-modes-05a2-stage-is-a-display.md), whose Decisions still bind except where amended below. Spec: [2026-10-12-editor-modes.md](2026-10-12-editor-modes.md).

## Decisions (user, 2026-10-15)

- **A, Save-As keeps the canvas.**
  - **Cause:** Save-As (`Slot.repayload_binding`, around `packages/haywire-core/src/haywire/ui/app/slot.py:844-853`) renames the document's `q-tab-panel` (`panel._props["name"] = new_id`, `set_value(new_id)`). The keep-alive treats the new name as a new panel and mounts a fresh canvas. NiceGUI's `$refs['r'+id]` keeps pointing at the old, detached instance, so the edge resync lands there and the live canvas draws no edges. Plain Save does not rename the panel and is unaffected.
  - **Fix:** every document panel in `Slot` gets a stable uuid name, like `_Level.panel_name`. `ui.tab_panel`, `initial_value`, every `set_value`, and `_panels` key on that name. A re-payload changes only `data-hw-binding` and the wrapper's binding id, never the panel name. The canvas is not remounted, and keeps its edges and viewport.
- **B, a stage row is a widget row.** This amends 05a-2 Decision 2. On stage, a default-skin card draws a port's row only if the port renders a widget there: label plus widget, as in the patch. A port without a shown widget draws no label and no row.
- **B1, an on-stage pin without a widget** (for example, an annotation swinglet on a default-skin node) draws its pin only, with no label. The pin still needs an anchor, so the skin seats it in a bare pin row.
  - The Annotation skin is unaffected: it keeps its card, text, annotation pins and ADD slots.
  - The title bar is unchanged. Ghost pins stay. Collapse stays forced off.
- **C, the header switch shows the active view.** Patch | Stage becomes a segmented control that clearly marks the view now shown. It follows `docs/reference/design-guide.md` (tokens, active-state styling, `aria-pressed`, a tooltip on each segment). Clicking the active segment does nothing.
- **D, a node made in stage view lands near its siblings in the patch.** This amends 05a-2 Decision 5, which had the patch position copy the stage numbers. In a stage canvas:
  - A new node (create, edge-drop, wizard create or clone, reroute split) gets patch position = **(patch centroid of the on-stage nodes) + (its stage position − (stage centroid of the on-stage nodes))**. Centroids are taken over the nodes on stage before the add.
  - If the stage holds no nodes yet, the patch position is the centre of the patch canvas's last-known viewport, when the level's patch canvas is mounted. Otherwise it is the centroid of all patch nodes. On an empty graph it is the stage numbers.
  - **Paste:** the pasted nodes keep their layout relative to each other in both views. The anchor's patch position follows the rule above.
  - **Duplicate:** the copy's patch position is the original's patch position plus `DUPLICATE_OFFSET`. Its stage position is the original's stage position plus the same offset, as in 05a-2.
  - Everything is still one undo step with the creation, and a patch canvas is unaffected.
- **E, the selection is shared between the views.** Switching views no longer clears the selection. It carries over, **pruned to the nodes the new view shows**. The new view draws the carried selection highlighted, and the active node and component carry over too, when they are still shown.
  - This replaces 05a's "switching clears the selection". The prune keeps 5a's invariant: no invisible node stays selected.
  - Selection visuals in `canvas.vue` must act only on the canvas's own DOM. The ~10 page-wide lookups by node id parked in 5a (`getElementById(nodeId)` / `document.querySelector('[data-node-id=…]')`, in selection and active styling, culling, the resize gadget and others) become lookups inside `this.$el`, as `_syncNodePosition` already does.
- **F, the shortcut.** `ToggleStageView.default_keys = ("Mod+Shift+E",)`. `Mod+Alt+E` belongs to Firefox's developer tools.

## Global Constraints

- Patch view behaviour is unchanged, apart from E: selection now survives a view switch.
- No new undo actions. Placement goes into `node_data` before the add, through the existing `with_stage_placement` path.
- Commit trailer: `Co-Authored-By: Claude Opus 5.5 (1M context) <noreply@anthropic.com>`.
- Docs follow `.claude/rules/python-docs.md`. ADR and glossary changes land in Task 6.

---

### Task 1: Save-As keeps the canvas (A)

**Files:** `packages/haywire-core/src/haywire/ui/app/slot.py`, plus any reader of the panel name. Grep for `_panels`, `panel_name`, `repayload`, `set_value(`, and `_props["name"]` across `packages/` and `barn/`. `graph_editor.py` (`_save_fn` around :1524, `_recover_stale_binding_id` around :874) only calls `repayload_binding`; check that no caller depends on the panel name equalling the binding id. Any lookup that does must move to the new mapping.

**Tests:**
- Unit: `Slot.repayload_binding` leaves the panel's `name` prop unchanged and updates `data-hw-binding` and the binding id. The slot still selects and closes the document by its new binding id.
- Browser, under `tests/ui/harness/`: a real `Slot` with a `GraphEditor` document holding edges. After `repayload_binding` to a new id:
  - every drawn `path[data-edge-id]` is present and meets its pins (as in `test_graph_views.py`);
  - `mounted_app.$refs['r'+canvasId].$el.isConnected` is true;
  - the viewport (zoom and pan) is unchanged.
- [ ] Commit `fix(slot): a re-payloaded document keeps its panel, so Save-As keeps the canvas`.

### Task 2: A stage row is a widget row (B, B1)

**Files:**
- `barn/haybale-studio/haybale_studio/skins/node_skin.py`, `stacked_skin.py`, `split_skin.py`, `error_skin.py`: the port-row builders take `on_stage`.
- Grep where the rows and labels are built (`render_port`, the lane and group builders).
- Leave `annotation_skin.py` and `reroute_skin.py` alone, unless the reroute's pin-only body needs B1's pin-only row.

**Tests:** in `tests/ui/skin/test_stage_render.py`, replace the 05a-2 "same row labels" test with:
- on stage, the row labels are exactly the labels of ports with a shown widget;
- a no-widget data port has no label and no pin;
- a no-widget annotation swinglet on a default-skin node has its pin and no label;
- the patch render is unchanged in horizontal, T2B and B2T;
- the Annotation skin is unchanged.

- [ ] Commit `feat(skin): on stage a default card draws only its widget rows`.

### Task 3: The header shows the active view, and the shortcut moves (C, F)

**Files:** `barn/haybale-graph-editor/haybale_graph_editor/editors/graph_editor.py` (the header switch built in 5a Task 6), `packages/haywire-core/src/haywire/core/signals/vocabulary.py` (`ToggleStageView.default_keys`). Grep for `Mod+Alt+E` in docs, tests and generated keymap files, and update each hit. Don't touch the ADR and glossary prose; that is Task 6.

**Tests:**
- The switch marks the active view (an active class or prop, plus `aria-pressed`). Its marking follows `_switch_view`, `ToggleStageView`, `open_view="stage"` and a level change.
- `ToggleStageView` has `default_keys == ("Mod+Shift+E",)`, and `Mod+Shift+E` is not in `RESERVED_COMBOS`.
- Browser: the active segment's computed style differs from the inactive one.
- [ ] Commit `feat(graph-editor): the Patch | Stage switch shows the active view; Mod+Shift+E toggles it`.

### Task 4: Nodes made in stage view land near their siblings in the patch (D)

**Files:**
- `packages/haywire-core/src/haywire/core/node/layout.py`, or `core/graph/stage.py` next to `next_stage_spot`: a pure helper `patch_position_for_stage(graph, stage_xy, fallback_xy) -> tuple[float, float]` implementing Decision D.
- The creation paths 05a-2 Task 3 made stage-aware: background menu and add-node search, edge-drop, wizard create and clone, paste, duplicate, reroute split. Grep `with_stage_placement` callers. The stage canvas supplies the fallback (the patch canvas's last-known viewport centre) through the level's canvases. Find the least invasive route, and say which in your report.

**Tests:** in `tests/graph_editor/test_stage_creation.py`, update the 05a-2 assertions (`posX/posY == stage`) to Decision D:
- with on-stage siblings, the new node's patch position sits at the same offset from the siblings' patch centroid as its stage position from their stage centroid;
- an empty stage uses the viewport centre;
- with no patch canvas mounted, the all-nodes centroid;
- a paste keeps the relative layout in both views;
- a duplicate uses the original's patch position plus the offset;
- one undo step; the patch canvas unchanged.
- [ ] Commit `feat(graph-editor): a node made on stage lands near its siblings in the patch`.

### Task 5: The selection is shared between the views (E)

**Files:**
- `graph_editor.py`: `_switch_view` stops clearing the selection. It prunes to the nodes the target canvas includes, then pushes the pruned selection, active node and active component to the target canvas.
- `graph_canvas_manager.py` and `handlers/selection.py`: a "show this selection" entry, if one doesn't exist. Reuse the existing selection-sync path.
- `packages/haywire-core/src/haywire/ui/components/graph/canvas.vue`: scope every page-wide lookup by node id to `this.$el`. List each site and what you changed in the report.
- Check which, if any, pin and edge id lookups (`getElementById(pinUUID)`, edge and gradient ids) can collide between the two mounted canvases, and scope those too.

**Tests:**
- Unit: patch selection {a (on stage), b (off stage)} → switch to Stage → selection {a}, with `a` highlighted on the stage canvas → switch back → {a} highlighted on the patch. The active node carries over or is cleared when pruned.
- Browser: select a node shown in both views in Patch, switch, and the stage card is highlighted. Select and resize it on Stage, switch, and only the patch card of that node is highlighted. The other view's card never moves or highlights.
- [ ] Commit `feat(graph-editor): the selection carries across Patch and Stage`.

### Task 6: Docs

- `docs/adr/0054-the-stage-view.md` (amend in place): B and B1 (the stage row rule), D (patch placement), E (shared selection), F (the shortcut), and C as a line. Record 05a-2's "same rows" as superseded by B.
- `docs/reference/glossary.md` (Stage view), `docs/components/skins/skin-canon.md` (the row rule for `on_stage`), and `docs/guides/security.md` if the shortcut appears there.
- The spec: the shortcut `Mod+Alt+E` → `Mod+Shift+E` wherever it appears.
- `.insights/project_multi_canvas_dom_globals.md`: add the `Slot` Save-As case. Renaming a keep-alive panel remounts it, and `$refs` keeps the detached instance. Panels are named by stable uuid, not by binding id.
- Regenerate and verify: `uv run haywire docs barn/haybale-graph-editor`, `uv run haywire docs barn/haybale-studio`, `uv run haywire docs barn/haybale-core`, `uv run python scripts/bake_docs.py`, `uv run mkdocs build --strict`, `uv run pytest tests/ -k "bake or docs" -n 4 -q`. Commit the doc edits first.
- [ ] Commit `docs: stage polish and Save-As (ADR 0054 amended)`.

### Task 7: Full gate

- [ ] `uv run ruff check . && uv run ruff format --check .`
- [ ] The full mypy command from CLAUDE.md
- [ ] `uv run pytest -m "not browser and not perf" -n 4 -q` must exit 0
- [ ] `uv run pytest -m browser -n 4 -q` must exit 0
