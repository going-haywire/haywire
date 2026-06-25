# Module: Haywire Core UI

> NiceGUI/Vue-based renderers for the Haywire engine: the graph canvas, panels, editors, modals, themes, skins, and reactive UI elements. Provides the abstract UI primitives that haybale libraries extend.

**Path:** `packages/haywire-core/src/haywire/ui/`
**Language:** Python + Vue 3 (.vue) + JS
**Owner:** Haywire core team
**Tree hash:** `5cd252d120509ae2bed07e37e4d195cba73569cb` (part of packages/haywire-core)
**Mapped at:** 45140b27 (2026-06-25)

---

## 1. Scope & Purpose

The presentation layer of `haywire-core`. It renders the dual-flow graph as an interactive Vue canvas, hosts editors/panels in the workspace shell, exposes a theme/skin system (CSS tokens + `WorkbenchTheme`/`NodeTheme`), and provides reactive UI primitives (unified BaseWidget, binding, converters). It bridges the engine's signal bus to the browser via NiceGUI. Concrete editors/panels/widgets live in haybale-* libraries; this module supplies the abstractions and registries.

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
├── errors/          ← UI-level error info
├── modals/          ← confirm, pick, rename, save-as dialogs
├── panel/           ← Panel base + decorator + registry + focus + layout
│   ├── host_rendering.py (new) ← renders panels under host ownership (replaces error_boundary)
│   └── redraw_coordinator.py (new) ← coordinates panel redraws to avoid slot deletion
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

### On-demand

- `widget/` — **BaseWidget unification** (ADR 0007); replaces old simple.py + converters.py. Read `base.py`, `binding.py`, then ad-hoc `simple.py` pieces if needed.
- `widget/binding.py` — reactive data binding for NiceGUI; enables two-way sync with ports.
- `themes/`, `skin/` — when building/editing `WorkbenchTheme`/`NodeTheme` or CSS tokens.
- `modals/*` — when adding dialogs (use `hui.dialog_card()`).
- `components/debug_overlay/` — optional instrumentation for event tracing / performance profiling.
- `components/zoom/` — pan/zoom rendering; pan.vue was rewritten for performance.
- `nicegui_patches.py` — patches for NiceGUI/Quasar workarounds (nested menus, autofocus, etc.).

## 4. Rules & Boundaries

- UI MUST NOT contain engine logic — keep graph/execution code in `core/`.
- Do NOT use hardcoded colors, `box-shadow` on chrome, `truncate` on QBtn, or `ui.card()` inside `ui.dialog()` (see `.insights/project_ui_design_system.md`).
- Use `hui.dialog_card()` (carries `hw-panel`) instead of `ui.card()` inside dialogs.
- NiceGUI slot stack is **per asyncio-task**: never use `asyncio.ensure_future()` around `ui.notify()` (see `feedback_nicegui_async.md`).
- Autofocus in dynamic popups needs `ui.timer(0.1, ...) + run_javascript`.
- Minimap must be a sibling of `ZoomPanContainer`, never a child.
- Pin lookup: prefer `pin.flow_type.value` (`'data'`) over `str(pin.flow_type)` (`'FlowType.DATA'`).
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
| Panel render | `panel/render_utils.py` | Renders a panel inside an error boundary |
