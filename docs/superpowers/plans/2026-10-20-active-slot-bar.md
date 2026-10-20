# Active Slot Bar Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Every slot's top bar looks the same, the slot that receives key presses has a lighter bar, and a click anywhere in a slot makes it that slot — so Ctrl+S (and every other shortcut) visibly goes where the user expects. Component Source gains Ctrl+S.

**Architecture:** Two bar kinds with one look each: the *slot bar* (the shell's tab bar in EDIT/INFO, a new `hui.slot_header` drawn by an ACTION/CONTEXT editor) and the *editor toolbar* (a second row an editor draws under the tab bar, new `hui.editor_toolbar`). The `KeymapListener` tracks the **active slot** client-side, writes it to `<html data-hw-active-slot>`, and resolves keys to that slot's visible editor; shell CSS lights the active slot's bar from that attribute, so no server redraw can wipe it.

**Tech Stack:** NiceGUI 3.13, Vue 3 (`keymap_listener.vue`), Tailwind 4 / Quasar, Playwright harness.

**Spec:** conversation rulings 2026-10-20 (no spec file): user's proposal (one height/colour/separator for all top bars, the active slot's bar lighter) + Q1 b, Q2 a, Q3 a, Q4 a. Folded into branch `fix/save-key-and-core-fixes`.

## Global Constraints

- Slot bar: `min-height: 36px`, `background: var(--hw-bg-surface)`, `border-bottom: 1px solid var(--hw-border)`.
- Editor toolbar: `min-height: 32px`, `background: var(--hw-bg-surface)`, `border-bottom: 1px solid var(--hw-border)`; never lit.
- Active colour: `var(--hw-slot-bar-bg-active, var(--hw-bg-elevated))`; new optional theme field `slot_bar_bg_active` → `--hw-slot-bar-bg-active`. No theme sets it (elevated is lighter than surface in both Haywire themes: `#2a2a3e`/`#1e1e2e` dark, `#f0f0f6`/`#e8e8f0` light).
- Q1 b: Component Docs, Properties and Shortcuts get no header; in an active ACTION/CONTEXT slot the rail's selected icon (`.hw-icon-bar-tabs .q-tab--active`) takes the active colour — for every editor there, header or not.
- Q4 a: the active slot is the last slot that took a pointer-down **and holds a visible editor root**; keys go to its visible editor (the last-clicked root if it is visible in that slot, else the slot's first visible root); if it has none at key time, keys and the highlight fall back to `fallback_slot` (EDIT). Initial value: `fallback_slot`.
- Haystack keeps Ctrl+S. Never a bare Tailwind `border-b`/`border-t` class (Tailwind 4 preflight leaves its colour `currentColor`, which draws a near-white line); always `var(--hw-border)`.
- Pointer-downs outside any `[data-hw-slot]` (topbar, status bar, Popups, dialogs, menus — all mounted outside the slots) change nothing.

## Review Focus

1. **A click on a tab header** (outside any editor root) while CONTEXT is active makes EDIT active and the next key goes to the tab's editor — Task 2 harness test on a bar element.
2. **A server redraw of the active slot** (tab switch, editor redraw) keeps the highlight — the attribute lives on `<html>`, which Vue never patches; Task 2 asserts the attribute is on `document.documentElement`.
3. **Folding INFO, or closing the active editor**, while that slot is active: the next key goes to EDIT and EDIT lights — Task 2 hidden-root test.
4. **A click inside a Popup** opened from a slot keeps the active slot — Task 2 popup test.
5. **Two visible editors in one slot (split)**: the last-clicked one keeps the keys — existing `ed::one`/`ed::two` tests stay green unchanged.

---

### Task 1: One look for slot bars and editor toolbars

**Files:**
- Modify: `packages/haywire-core/src/haywire/ui/elements/elements.py` (add `slot_header`, `editor_toolbar` beside `panel_header` :59; export in `ui/elements/__init__.py`)
- Modify (header → `hui.slot_header`, same title/icon/is_dirty/actions): `barn/haybale-haystack/haybale_haystack/editors/haystack_editor.py:171`, `barn/haybale-studio/haybale_studio/editors/file_browser.py:108`, `barn/haybale-share/haybale_share/editors/share_editor.py:47`, `barn/haybale-marketplace/haybale_marketplace/editors/library_browser_editor.py:115`, `barn/haybale-studio/haybale_studio/editors/component_source_editor.py:242-245` (custom content, no title)
- Modify (row → `hui.editor_toolbar`): `barn/haybale-graph-editor/haybale_graph_editor/editors/graph_editor.py:1038-1041`, `barn/haybale-studio/haybale_studio/editors/code_editor.py:164-167`, `barn/haybale-studio/haybale_studio/editors/file_viewer.py:102-105`, `barn/haybale-studio/haybale_studio/editors/log_editor.py:133-136`, `barn/haybale-studio/haybale_studio/editors/activity_editor.py:151-154`
- Modify: `file_viewer.py:154-157` info row — `border-b` class → `_BORDER`-equivalent style (stays 28px).
- Test: `tests/ui/test_slot_bars.py` (new)

**Interfaces:**
- Produces: `hui.slot_header(title: str | None = None, *, icon: str | None = None, is_dirty: bool = False)` — context manager yielding the `ui.row`; classes include `hw-slot-header`; with `title=None` it draws no icon/label and the caller fills the row. `hui.editor_toolbar()` — context manager yielding a `ui.row` with class `hw-editor-toolbar`. Task 2's CSS targets `.hw-slot-bar` (existing tab bar row, `slot.py:353`) and `.hw-slot-header`.

- [ ] **Step 1: Write the failing tests** in `tests/ui/test_slot_bars.py` (use the `nicegui_slot_context` fixture; read `row._style` / `row._classes`):
  - `test_a_slot_header_has_the_slot_bar_look`: `min-height` `36px`, `background` `var(--hw-bg-surface)`, `border-bottom` `1px solid var(--hw-border)`, class `hw-slot-header`.
  - `test_a_slot_header_without_a_title_draws_no_label`: `slot_header()` has no `ui.label` descendant.
  - `test_an_editor_toolbar_has_the_toolbar_look`: `32px`, surface, `--hw-border`, class `hw-editor-toolbar`.
  - `test_no_editor_draws_a_bare_tailwind_border`: for every `.py` under `barn/*/*/editors/` and `packages/haywire-core/src/haywire/ui/app/`, assert no match of `r"""["' ]border-[btlr]\b(?!-)"""` in a `.classes(` string (strip `border-b-0`-style suffixes via the lookahead). Message names file and line.
- [ ] **Step 2:** `uv run pytest tests/ui/test_slot_bars.py -q` — Expected: FAIL (no `slot_header`; six `border-b` hits).
- [ ] **Step 3: Implement** both helpers (padding `px-2 gap-1 items-center flex-shrink-0 w-full`; slot_header reuses `panel_header`'s icon/dirty/label rendering — factor the shared row body into one private helper) and migrate the eleven call sites. `panel_header` stays as is for panels (errors_editor keeps it).
- [ ] **Step 4:** `uv run pytest tests/ui/test_slot_bars.py tests/ui/ tests/graph_editor/ -q -n 4` — Expected: PASS.
- [ ] **Step 5: Commit** `feat(ui): one look for slot bars and editor toolbars`.

### Task 2: The active slot — routing and highlight

**Files:**
- Modify: `packages/haywire-core/src/haywire/ui/app/tab_slot.py:42-46` and `icon_slot.py:71` — stamp `data-hw-slot="<SlotName value>"` on the wrapper holding bar + area.
- Modify: `packages/haywire-core/src/haywire/ui/app/shell.py` — new module constant `ACTIVE_SLOT_CSS`, appended to `STATIC_CSS`.
- Modify: `packages/haywire-core/src/haywire/ui/themes/workbench.py` `_CSS_TOKEN_MAP` — `"slot_bar_bg_active": "--hw-slot-bar-bg-active"` (comment: optional, CSS falls back to `--hw-bg-elevated`).
- Modify: `packages/haywire-core/src/haywire/ui/components/keymap/keymap_listener.vue` and the class docstring in `keymap_listener.py`.
- Modify: `tests/ui/harness/routes.py` `/keymap` page.
- Test: `tests/ui/test_active_slot_css.py` (new), `tests/ui/harness/test_keymap_listener.py`, slot render test beside `tests/ui/test_slot_on_focus.py`.

**Interfaces:**
- Consumes: `.hw-slot-header` (Task 1), `.hw-slot-bar` (`slot.py:353`).
- Produces: DOM contract `[data-hw-slot="<name>"]` on each slot wrapper; `document.documentElement.dataset.hwActiveSlot`; `ACTIVE_SLOT_CSS: str` in `haywire.ui.app.shell`. `hw-target` payload unchanged (`{"binding_id"}`).

- [ ] **Step 1: Harness.** In `/keymap`: give the existing `#hw-slot-edit` div `data-hw-slot="edit"` and a first child `div.hw-slot-bar#edit-bar`; add sibling `div[data-hw-slot="context"]` holding `div.hw-slot-header#ctx-bar` and root `ed::ctx` (`data-hw-editor="ed"`, id `ctx-root`); add `div[data-hw-slot="info"]` holding only `div.hw-slot-bar#info-bar`. `ui.add_css(ACTIVE_SLOT_CSS + ":root{--hw-bg-surface:#101010;--hw-bg-elevated:#505050}")`; bars get `background: var(--hw-bg-surface)`.
- [ ] **Step 2: Write the failing tests.**
  - `test_active_slot_css.py`: `test_every_slot_lights_its_bars` — for each `SlotName` value `x`, `ACTIVE_SLOT_CSS` contains `html[data-hw-active-slot="x"] [data-hw-slot="x"] .hw-slot-bar` and `… .hw-slot-header` and `… .hw-icon-bar-tabs .q-tab--active`; `test_the_active_colour_is_themable` — the CSS reads `var(--hw-slot-bar-bg-active, var(--hw-bg-elevated))` and `--hw-slot-bar-bg-active` is in `BaseTheme._CSS_TOKEN_MAP.values()`; `test_it_ships_in_the_shell_css` — `ACTIVE_SLOT_CSS in STATIC_CSS`.
  - Slot render: `test_the_slot_wrapper_carries_its_name` for a `TabSlot` and an `IconSlot`.
  - `test_keymap_listener.py`:
    - `test_the_edit_slot_is_active_at_load`: `document.documentElement.dataset.hwActiveSlot == "edit"`.
    - `test_a_click_on_a_slot_bar_activates_that_slot`: click `#ctx-bar`; attr `"context"`; `#last-target` `ed::ctx`; Ctrl+S → `#last-command` `save@ed::ctx`.
    - `test_a_slot_without_an_editor_is_not_activated`: click `#ctx-root`, then `#info-bar`; attr stays `"context"`; Delete → `delete@ed::ctx`.
    - `test_a_hidden_active_editor_falls_back_to_the_edit_slot`: click `#ctx-root`; `el.style.display='none'` on it; Delete → `delete@ed::one`; attr `"edit"`.
    - `test_a_click_in_a_popup_keeps_the_active_slot`: click `#ctx-root`, `#open-popup`, then the popup field; attr `"context"`; close popup.
    - `test_the_active_slot_bar_is_lighter`: click `#ctx-bar`; computed `backgroundColor` of `#ctx-bar` is `rgb(80, 80, 80)`, of `#edit-bar` `rgb(16, 16, 16)`.
- [ ] **Step 3:** `uv run pytest tests/ui/test_active_slot_css.py tests/ui/harness/test_keymap_listener.py -q` — Expected: new tests FAIL, existing ones PASS.
- [ ] **Step 4: Implement.**
  - `keymap_listener.vue`: `data()` gains `activeSlot: null`; `mounted()` sets it to `fallbackSlot` and writes the attribute. `onPointerDown`: `slotEl = e.target.closest('[data-hw-slot]')`; root = `e.target.closest('[data-hw-binding]')` or the first visible root in `slotEl`; if no root, return (slot not activated); set `activeSlot`, write the attribute, and emit `hw-target` when the binding changed. `resolveRoot()`: last-clicked root if visible and inside the active slot's wrapper; else first visible root in the active slot; else first visible root in `[data-hw-slot="<fallbackSlot>"]`, switching `activeSlot` + attribute to the fallback. Query slots by `[data-hw-slot=…]`, no longer `#hw-slot-…`.
  - `ACTIVE_SLOT_CSS`: generated from `SlotName`, one rule group per slot, `background: var(--hw-slot-bar-bg-active, var(--hw-bg-elevated)) !important` (the bars carry inline `background`).
  - Docstring: replace the target-editor paragraph with the active-slot rule (Global Constraints, Q4 a).
- [ ] **Step 5:** `uv run pytest tests/ui/ tests/studio/ -q -n 4` then `uv run pytest -m browser -n 4` — Expected: PASS.
- [ ] **Step 6: Commit** `feat(shell): the active slot takes the keys and lights its bar`.

### Task 3: Component Source saves on Ctrl+S; docs

**Files:**
- Modify: `barn/haybale-studio/haybale_studio/editors/component_source_editor.py` — `@react_on(Save) _on_save(self, context, event) -> None` → `self._save()`.
- Test: `tests/graph_editor/test_graph_editor_commands.py` (the existing "all three editors bind Mod+S" test becomes four; add `test_component_source_save_writes_the_file` beside the code-editor routing test).
- Docs: `docs/reference/design-guide.md` (§4.4 heights table: "Slot bar 36px", "Editor toolbar 32px"; §8 new `hui.slot_header` / `hui.editor_toolbar` entries; colour table row `--hw-slot-bar-bg-active`; rule: no bare `border-b`), `docs/reference/glossary.md` UI section (new **Active slot**, **Slot header**, **Editor toolbar**; fix ActivityBar/ContextBar "styled with `hw-slot-bar`" — the icon column carries no such class), `docs/guides/signals.md:251,446` (Save fires in Component Source too; "target editor" → active slot wording).

**Interfaces:**
- Consumes: `Save` (`haywire.core.signals`), Task 2's active-slot rule (docs only).

- [ ] **Step 1: Write the failing tests** (Mod+S bound for the component-source editor key in `build_keymap`; `_on_save` with an editable path writes `_content` to disk and clears `_pinned`).
- [ ] **Step 2:** run them — Expected: FAIL.
- [ ] **Step 3: Implement** the handler; write the docs.
- [ ] **Step 4:** full gate: `uv run ruff check .`, `uv run ruff format --check .`, mypy (CLAUDE.md path list), `uv run pytest -m "not browser and not perf" -n 4`, `uv run pytest -m browser -n 4` — Expected: all clean.
- [ ] **Step 5: Commit** `feat(studio): Ctrl+S saves Component Source; active-slot docs`.

### Task 4: Live check (user, Chrome + Firefox)

- [ ] All top bars match in height, colour and gray separator (Haystack, tabs, Component Source); graph/code second rows are a separate 32px row.
- [ ] Click into the haystack → its header lightens, the tab bar darkens; Ctrl+S saves the haystack. Click a tab header → the tab bar lightens; Ctrl+S saves that tab.
- [ ] Click into Properties / Shortcuts → only their rail icon lightens; Ctrl+S does nothing.
- [ ] Component Source: Ctrl+S saves, caret stays.
- [ ] Light theme: the active bar is visibly lighter.
- [ ] Earlier Save checks: commit-mode text widget and note save the typed text; Ctrl+S in port-edit/Save-As popups does nothing.
