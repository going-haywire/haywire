# Module: Haywire Core UI

> NiceGUI/Vue-based renderers for the Haywire engine: the graph canvas, panels, editors, modals, themes, skins, and reactive UI elements. Provides the abstract UI primitives that haybale libraries extend.

**Path:** `packages/haywire-core/src/haywire/ui/`
**Language:** Python + Vue 3 (.vue) + JS
**Owner:** Haywire core team
**Tree hash:** `5935247b3cc5f4cc6d1b65b06a43ea5ee3927b68` (part of packages/haywire-core)
**Mapped at:** 19bda1e (2026-07-05)

---

## 1. Scope & Purpose

The presentation layer of `haywire-core`. It renders the dual-flow graph as an interactive Vue canvas, hosts editors/panels in the workspace shell, exposes a theme/skin system (CSS tokens + `WorkbenchTheme`/`NodeTheme`), and provides reactive UI primitives (unified BaseWidget, binding, converters). It bridges the engine's signal bus to the browser via NiceGUI. Concrete editors/panels/widgets live in haybale-* libraries; this module supplies the abstractions and registries.

Recent work (Tier 2 settings/widget convergence, ADR 0017) rebuilt how the settings panel renders a field: `panel/render_utils.py` now resolves one shared `BaseWidget` per field by its stamped `widget_key`/`widget_config` and binds it to a `SettingWidgetModel` (new, `panel/setting_widget_model.py`) wired to an `on_edit` write-policy closure (instance vs. registry tier), instead of building throwaway per-row widgets. A new nested-flyout mechanics module (`elements/flyout.py`) backs both the add-node menu and the new hierarchical Promote-Setting flyout, and a new `modals/text_modal.py` restores expand-to-modal editing for long text fields.

## 2. Folder Architecture

```
ui/
├── app/             ← app shell, slots (icon_slot, tab_slot, generic slot)
├── components/      ← Vue components: graph/, zoom/, popup/
│   ├── graph/       ← canvas.py + canvas.vue (main editing surface + event defs)
│   ├── debug_overlay/ ← optional debug UI for tracing
│   └── zoom/        ← pan.py (pan.vue rewrite for perf)
├── editor/          ← Editor base + decorator + registry + wrapper + identity
├── elements/        ← shared NiceGUI elements + icon set
│   └── flyout.py (new) ← nested hover-flyout menu mechanics (add-node menu, Promote-Setting menu)
├── errors/          ← UI-level error info
├── extends/codemirror/ ← jedi-backed autocomplete/hover for CodeMirror editors
├── modals/          ← confirm, pick, rename, save-as, upgrade-impact dialogs
│   └── text_modal.py (new) ← expand-to-modal multi-line text editing
├── panel/           ← Panel base + decorator + registry + focus + layout + context-menu base
│   ├── render_utils.py ← settings-field rendering (rewritten: shared BaseWidget per field, ADR 0017)
│   ├── setting_widget_model.py (new) ← adapts a settings field's DataField cell to the WidgetModel surface
│   ├── host_rendering.py ← renders panels under host ownership (replaces error_boundary)
│   └── redraw_coordinator.py ← coordinates panel redraws to avoid slot deletion
├── prefs/           ← canvas/editor/edge_ui preferences
├── skin/            ← Skin interface + factory + decorator + registry + settings
├── themes/          ← Theme decorator, icons
├── widget/          ← **BaseWidget unification** (binding, converters, simple merged in)
├── nicegui_patches.py ← patches for NiceGUI/Quasar issues
└── utils.py         ← shared helpers
```

## 3. Always-load vs On-demand

### Always-load

- `components/graph/canvas.py` + `canvas.vue` — the editing surface; the resume/`lastMousePos` workaround lives here.
- `panel/registry.py`, `panel/base.py` — Panel contract used by every haybale library.
- `editor/registry.py`, `editor/base.py`, `editor/wrapper.py` — Editor contract + lifecycle.
- `app/shell.py` — App shell that hosts slots/panels/editors.
- `panel/render_utils.py`, `panel/setting_widget_model.py` — canonical path for rendering any `Settings` field; read together before touching settings-panel UI (see ADR 0017).

### On-demand

- `widget/` — **BaseWidget unification** (ADR 0007); replaces old simple.py + converters.py. Read `base.py`, `binding.py`, then ad-hoc `simple.py` pieces if needed.
- `widget/binding.py` — reactive data binding for NiceGUI; enables two-way sync with ports.
- `elements/flyout.py` — building a hierarchical hover-menu (submenus that cascade on hover); shared mechanics for the add-node menu and the Promote-Setting flyout. Read `.insights/feedback_nicegui_nested_menu_flyouts.md` first.
- `modals/*` — when adding dialogs (use `hui.dialog_card()`); `text_modal.py` is the expand-to-modal pattern for a single long text field.
- `themes/`, `skin/` — when building/editing `WorkbenchTheme`/`NodeTheme` or CSS tokens.
- `components/debug_overlay/` — optional instrumentation for event tracing / performance profiling.
- `components/zoom/` — pan/zoom rendering; pan.vue was rewritten for performance.
- `extends/codemirror/` — jedi autocomplete/hover-docs provider for CodeMirror-based code editors.
- `nicegui_patches.py` — patches for NiceGUI/Quasar workarounds (nested menus, autofocus, etc.).

## 4. Rules & Boundaries

- UI MUST NOT contain engine logic — keep graph/execution code in `core/`.
- Do NOT use hardcoded colors, `box-shadow` on chrome, `truncate` on QBtn, or `ui.card()` inside `ui.dialog()` (see `docs/reference/design-guide.md`).
- Use `hui.dialog_card()` (carries `hw-panel`) instead of `ui.card()` inside dialogs.
- NiceGUI slot stack is **per asyncio-task**: never use `asyncio.ensure_future()` around `ui.notify()` (see `feedback_nicegui_async.md`).
- Autofocus in dynamic popups needs `ui.timer(0.1, ...) + run_javascript`.
- Minimap must be a sibling of `ZoomPanContainer`, never a child.
- Pin lookup: prefer `pin.flow_type.value` (`'data'`) over `str(pin.flow_type)` (`'FlowType.DATA'`).
- A setting field's widget binds the shared `DataField` cell directly (instance cell or registry-owned cell); `SettingWidgetModel.set_value` forwards writes to an injected `on_edit` policy and never writes the cell itself — writing here too would race the next registry sync (see `panel/setting_widget_model.py` docstring).
- Hierarchical hover-flyout menus (nested `ui.menu` submenus) must go through `elements/flyout.py` — no ad-hoc close-timers; NiceGUI 3.x drops closed-menu DOM, so hover-open + sibling/cascade-close must use this module's mechanics.
- Follow `docs/reference/design-guide.md` for new UI features.

## 5. Source of Truth

| Concept | Canonical file | Notes |
|---------|---------------|-------|
| Graph canvas Vue component | `components/graph/canvas.vue` | Generated JS events in `generated/graph_events.js` |
| Panel registry | `panel/registry.py` | Receives panels from haybale libs |
| Editor registry | `editor/registry.py` | Receives editors from haybale libs |
| Theme decorator | `themes/decorator.py` | `@theme(...)` registration |
| Skin factory | `skin/factory.py` | Resolves which skin renders a node |
| App shell | `app/shell.py` | Top-level layout / slot mounting |
| Settings field rendering | `panel/render_utils.py` | Waterfall: entry points → collect/group → row render → resolve shared widget → write policy |
| Settings field → widget adapter | `panel/setting_widget_model.py` | `SettingWidgetModel`; thin `WidgetModel` shim over a `DataField` cell |
| Nested hover-flyout mechanics | `elements/flyout.py` | Shared by add-node menu and Promote-Setting menu |

---

## Dependencies

### Depends on

- [haywire-core-engine](haywire-core-engine.md) — graph/node/session/signal types.
- External: NiceGUI, Quasar, Vue 3, `duit[nicegui]`.

### Depended on by

- [haywire-studio](haywire-studio.md) — hosts the shell + workspace.
- [haybale-core](haybale-core.md) / [haybale-studio](haybale-studio.md) — register concrete panels/editors/themes/widgets.

---

## Key Entry Points

| Entry point | File | Description |
|-------------|------|-------------|
| App shell mount | `app/shell.py` | Wires slots, panels, editors into a NiceGUI page |
| Graph canvas | `components/graph/canvas.py` | Backend half of the Vue canvas |
| Settings field render | `panel/render_utils.py` | `render_settings`/`render_schema`/`render_keys` — renders a `Settings` instance as labelled form rows |
| Panel host render | `panel/host_rendering.py` | Renders a panel under host ownership (error containment) |
