# Editor modes, slice 5a-4: folds on stage, and patch paste places on stage — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Two follow-ups from the user's live check of slice 5a-3 on 2026-10-15. Every other step passed.

**Base:** branch `feat/editor-modes-slice5a` at 927e2447, already fast-forwarded into `feat/editor-modes-slice1`. Earlier plans in this folder still bind except where amended here: 05a, 05a-2 and 05a-3.

## Decisions (user, 2026-10-15)

- **G. Folds work on stage.** The user restated the model:
  > on stage a default-skin card keeps all its UX except patch cords and pins; a label without a widget is meaningless there, so it is hidden; but a fold and its hiding and showing of widgets make sense even without pins.

  This reverses the 5a-3 controller ruling "on stage fold state is ignored". In detail:
  - The fold header is drawn on stage under the same widget rule as any port. It draws when the fold port shows its toggle widget, and is hidden when its widget is hidden, for example when an edge drives the fold.
  - The open/closed state is honoured on stage. A closed fold hides its children on stage, as in the patch.
  - The state is the node's one fold state, shared with the patch, so toggling it in either view changes it in both.
  - Node collapse stays forced off on stage (05a-2 Q4b).
  - The split skin's config band honours fold state on stage again. Revert 5a-3's `get_all_ports() if on_stage` back to the visible ports. The empty-band skip stays.
- **H. Paste and duplicate in the patch place the copies on stage like D, mirrored.** Today, a copy of an on-stage node pasted in a **patch** canvas lands on stage on exactly the original's stage spot. The fix mirrors 05a-3's Decision D. In a patch canvas:
  - **Paste.** Pasted nodes that carry `on_stage=True` keep their stage layout relative to each other. The anchor's stage position = (stage centroid of the on-stage nodes) + (the anchor's new patch position − (patch centroid of the on-stage nodes)), with centroids over the nodes on stage before the add.
    - If the stage is empty, use the next free stage spot (`next_stage_spot`, 5a R1).
    - Pasted nodes without `on_stage` stay off stage, as today.
  - **Duplicate.** A copy of an on-stage node gets the original's stage position plus `DUPLICATE_OFFSET`, the same offset as its patch copy.
  - Everything stays one undo step with the creation. Creating a node in the patch still leaves it off stage. The stage canvas's paths from D are unchanged.

## Global Constraints

- Patch view rendering is unchanged.
- No new undo actions.
- Commit trailer: `Co-Authored-By: Claude Opus 5.5 (1M context) <noreply@anthropic.com>`.
- Docs follow `.claude/rules/python-docs.md`.

---

### Task 1: Folds work on stage (G)

**Files:**
- `barn/haybale-studio/haybale_studio/skins/stacked_skin.py`: around :355–:396, the fold header (`if not on_stage`) and the children `get_all_ports() if on_stage …`.
- `split_skin.py`: around :111 and :161.
- `node_skin.py`: wherever the widget rule (`_shows_widget`, the `render_port` gate) needs to treat a fold port's toggle as its widget.
- Grep the studio skins for `on_stage` and `is_expanded`/fold handling.
- Make sure toggling a fold on a stage card works: it goes through the same handler as in the patch, and a stage canvas allows every edit (05a-2 Decision 1).

**Tests** in `tests/ui/skin/test_stage_render.py`. Replace 5a-3's two "closed fold draws expanded without a header on stage" tests (stacked and split) with:
- on stage, an open fold draws its header and its widget children;
- a closed fold draws its header and hides its children;
- a fold whose port is driven by an edge draws no header, and its children follow the fold's state;
- the patch is unchanged.

Add a graph-editor test: toggling the fold from a stage canvas changes the node's fold state, and the patch card follows.

- [ ] Commit `fix(skin): folds keep their header and state on stage`.

### Task 2: Patch paste and duplicate place copies on stage (H)

**Files:**
- `packages/haywire-core/src/haywire/core/graph/stage.py`: add the mirror helper `stage_position_for_patch(graph, patch_xy) -> tuple[float, float] | None`, next to `patch_position_for_stage`. It returns None when the stage is empty, so the caller falls back to `next_stage_spot`.
- The patch-canvas paste and duplicate paths, for which 05a-3 Task 4 added `patch_anchor`/`patch_fallback`. Grep `with_stage_placement`, `layout_position_of`, `patch_position_for_stage`, `DUPLICATE_OFFSET` (`barn/haybale-graph-editor/haybale_graph_editor/editors/graph_canvas/handlers/selection.py:38`), the paste action in `graph_actions.py`, and `Editor`.

**Tests** in `tests/graph_editor/test_stage_creation.py`:
- in a patch canvas, a paste of a copied on-stage node places the copy on stage by the mirrored centroid rule;
- several pasted on-stage copies keep their relative stage layout;
- a paste of an off-stage copy stays off stage;
- a paste on an empty stage uses `next_stage_spot`;
- a duplicate gets the original's stage position plus `DUPLICATE_OFFSET`;
- each case is one undo step;
- the 05a-3 stage-canvas paths are unchanged.

- [ ] Commit `feat(graph-editor): a patch paste places on-stage copies near their siblings on stage`.

### Task 3: Docs

- `docs/adr/0054-the-stage-view.md`, amended in place:
  - G replaces the 5a-3 fold ruling; record that ruling under Considered options as rejected by the user on 2026-10-15;
  - H mirrors D.
- `docs/components/skins/skin-canon.md`: folds on stage.
- `docs/reference/glossary.md`, if Stage view mentions folds.
- Regenerate and verify: `uv run haywire docs barn/haybale-studio`, `uv run haywire docs barn/haybale-graph-editor`, `uv run python scripts/bake_docs.py`, `uv run mkdocs build --strict`, `uv run pytest tests/ -k "bake or docs" -n 4 -q`. Commit the doc edits first.
- [ ] Commit `docs: folds on stage and patch paste placement (ADR 0054 amended)`.

### Task 4: Full gate

- [ ] `uv run ruff check . && uv run ruff format --check .`
- [ ] The full mypy command from CLAUDE.md.
- [ ] `uv run pytest -m "not browser and not perf" -n 4 -q`, exit 0.
- [ ] `uv run pytest -m browser -n 4 -q`, exit 0.
