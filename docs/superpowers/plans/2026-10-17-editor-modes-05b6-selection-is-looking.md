# Editor modes, slice 5b-6: selection is looking — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Every form of selection (click, Shift-click, box select, Select All, a reveal) works in every level mode, so a `view` or `operate` session can point Component Docs at a node. Acting on the selection still needs level mode `edit`.

**Architecture:** Selection changes no document, so it is looking, not touching. 5b-3 already gated everything that acts on a selection (toolbar, context menus, Properties, keyboard commands, drag, resize, copy/paste) on its own, so this slice only removes the gates on selecting itself. The rule "locking clears the selection" goes with it.

**Tech Stack:** Python 3.12, NiceGUI/Vue 3 (`canvas.vue`), pytest, Playwright browser tier.

**Spec:** user decision of 2026-10-17 (this session), reversing edit-route Q8's "Selection needs `edit`" and 5b-3's Decisions 2 and 6 ("locking clears the selection", "a reveal selects only in `edit`"). The rest of [2026-10-16-edit-route.md](2026-10-16-edit-route.md) stands.

## Global Constraints

- **Branch:** `feat/editor-modes-slice5b6` in `.worktrees/editor-modes-slice5b6`, cut from `feat/editor-modes-slice1` (`d97fe81d`); merges into slice1 after the live check.
- **Selection in every mode:** click, Shift-click, box select, `SelectAll` (Mod+A) and a reveal select at `view`, `operate` and `edit`.
- **Acting stays `edit`:** the selection toolbar, context menus, the resize gadget, drag, copy, paste and every other keyboard command stay below `edit` exactly as now (user's option (a)).
- **Tests and docs:** smallest tier while iterating; full gates at the end; docs follow `.claude/rules/python-docs.md`.

## Decisions

1. `SelectionChangedEvent` is handled at `LevelMode.VIEW`; the handler is unchanged (it already points `active_component` at the active node).
2. `GraphEditor.accepts_command` passes `SelectAll` beside `ToggleLock` and `ToggleStageView`.
3. `GraphCanvasManager.refresh_mode()` keeps the selection below `edit` (still hides the toolbar, closes a menu). Locking (`set_level_locked`, `_rekey_level`) no longer clears the session selection.
4. A reveal selects in every level mode.
5. Canvas: a press on a card below `edit` arms a click with nothing to drag (unless a readable or, in `operate`, an operable element keeps it); `_handleElementSelection` and `_startBoxSelection` lose their `editing` gate; a press that moves but drags nothing still counts as a click. On reaching `edit` the canvas re-emits its selection bounds and refits the resize gadget, so the toolbar and gadget come back for a kept selection.

## Review Focus

1. Lock a level with a node selected, then unlock: the selection stays, and on unlock the toolbar and resize gadget reappear. Test: browser, `test_unlocking_shows_the_toolbar_for_a_kept_selection`.
2. In `operate`, a click on a widget operates it and does not change the selection; a click on the card's title selects. Test: browser, `test_operate_click_on_a_widget_does_not_select`.
3. In `view`, a press-and-jitter on a card (moves a few px) still selects and moves nothing. Test: browser, `test_view_click_selects_and_moves_nothing`.

---

### Task 1: Server — selection in every level mode

**Files:** `barn/haybale-graph-editor/haybale_graph_editor/editors/graph_canvas/handlers/selection.py:80`, `.../graph_canvas/graph_canvas_manager.py:93`, `.../editors/graph_editor.py` (`set_level_locked` ~:360, `_rekey_level` ~:608, reveal ~:719, `accepts_command` :779); tests `tests/graph_editor/test_canvas_event_gating.py`, `test_graph_editor_commands.py`, `test_graph_editor_lock.py`, `test_graph_editor_views.py` (reveal), `test_graph_editor_levels.py`/`test_graph_editor_session_claim.py` where they pin the old rules.

- [ ] Rewrite the pinning tests: `test_a_selection_change_is_taken_in_every_mode` (parametrized `VIEW/OPERATE/EDIT`: session selection and `active_component` set), `test_refresh_mode_below_edit_keeps_the_canvas_selection`, `test_select_all_passes_below_edit` (Copy still refused), `test_locking_the_level_on_screen_keeps_the_selection`, `test_a_reveal_selects_in_every_mode`. Run — FAIL.
- [ ] Implement Decisions 1–4. Run the graph_editor tests — PASS. Commit `feat(graph-editor): selection works in every level mode; acting on it needs edit`.

### Task 2: Canvas — click, Shift-click and box select in every mode

**Files:** `packages/haywire-core/src/haywire/ui/components/graph/canvas.vue` (`handleMouseDown` :1767, `_startUnifiedDrag` mouseup :2318, `_handleElementSelection` :2396, `_startBoxSelection` :2605, `editing` watcher :361, the `levelMode` doc comment :138); tests `tests/ui/harness/test_level_mode_gate.py`, `tests/ui/harness/test_canvas_lock.py`.

- [ ] Browser tests (on `/graph-level-mode`): `test_view_click_selects_and_moves_nothing`, `test_view_box_select_selects`, `test_operate_click_on_a_widget_does_not_select`, `test_unlocking_shows_the_toolbar_for_a_kept_selection` (edit, select, F9 locks, then the harness unlock key; adjust the route if it has none), and rewrite tests that assert no selection below edit. Run — FAIL.
- [ ] Implement Decision 5. Run `uv run pytest -m browser -n 4` — PASS. Commit `feat(canvas): select in every level mode; drag, resize and menus stay edit`.

### Task 3: Docs and gates

- [ ] Glossary **Level mode** ("Selection and copy need `edit`" → "Selection works in every level mode; acting on it needs `edit`"), **Lock** (no clearing), **Operate (tier)** ("no selection" goes); security guide tier list; ADR 0051 :20 and its Decision on locking; ADR 0055 if it states the selection rule; the spec's decision log gets a row "Q8 revised 2026-10-17: selection works in every mode".
- [ ] `uv run mkdocs build --strict`, ruff check + format check, mypy (CLAUDE.md command), full non-browser and browser suites. Commit `docs: selection is looking`.
- [ ] Live check: `view` and `operate` click, Shift-click and box select nodes, Component Docs follows; no toolbar, no resize gadget, no drag; Mod+A selects all, Mod+C does nothing; locking keeps the selection, unlocking brings the toolbar back.
