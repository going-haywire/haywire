# Module: Haywire Core UI

> NiceGUI/Vue renderers for the Haywire engine: app shell and slots, the graph canvas, panels, editors, modals, surfaces, themes, skins, widgets, and access-gated components. Provides the abstract UI primitives that haybale libraries extend.

**Path:** `packages/haywire-core/src/haywire/ui/`
**Language:** Python + Vue 3 (.vue) + JS
**Owner:** Haywire core team
**Tree hash:** `2908b8b7a84b83893cbfb034dbb997722a88ee0f` (part of packages/haywire-core)
**Mapped at:** 9b104fd36 (2026-11-10, branch feat/exec-audio)

---

## 1. Scope & Purpose

The presentation layer of `haywire-core`. It renders the dual-flow graph as an interactive Vue canvas, hosts editors and panels in the workspace shell, exposes a theme/skin system (CSS tokens, `WorkbenchTheme`/`NodeTheme`), and provides reactive UI primitives (BaseWidget, binding, converters). It bridges the engine's signal bus to the browser via NiceGUI. Concrete editors, panels and widgets live in haybale-* libraries; this module supplies the abstractions and registries.

Settings fields render through one shared `BaseWidget` per field, resolved from the stamped `widget_key`/`widget_config` (ADR 0017) and bound to `SettingWidgetModel` (`panel/setting_widget_model.py`). Its write goes through an injected `on_edit` policy (instance vs registry tier). `elements/flyout.py` backs nested hover menus (add-node menu, Promote-Setting flyout). `modals/text_modal.py` gives expand-to-modal editing for long text.

## 2. Folder Architecture

```
ui/
├── app/             ← app shell + slots: shell.py, slot.py, icon_slot.py, tab_slot.py, account_menu.py
├── components/      ← Vue-backed components (each a .py + .vue pair where needed)
│   ├── graph/       ← canvas (main editing surface, Vue canvas + generated events)
│   ├── zoom/        ← pan/zoom container
│   ├── minimap/     ← minimap (must be sibling of ZoomPanContainer, never child)
│   ├── cull/        ← off-screen culling
│   ├── popup/       ← popup component
│   ├── stepper/     ← stepper component
│   ├── number/      ← number input
│   ├── keymap/      ← keymap component
│   ├── access_gate/ ← access-gated UI wrapper
│   └── debug_overlay/ ← optional debug UI for tracing
├── editor/          ← Editor base, decorator, registry, wrapper, identity
├── elements/        ← shared NiceGUI elements: elements.py, icons.py, folder_tree.py,
│                      path_fit.py, flyout.py (nested hover-flyout mechanics)
├── modals/          ← confirm, pick, rename, save-as, diff, info, text (expand-to-modal),
│                      install progress/safety, upgrade-impact, update dialog, restart affordance
├── panel/           ← Panel base, decorator, registry, identity, layout, context_menu_base,
│                      render_utils.py (settings-field rendering), setting_widget_model.py,
│                      port_default_widget_model.py, host_rendering.py, redraw_coordinator.py
├── surface/         ← surface, presentation, tree (focus/surface model)
├── skin/            ← Skin base, decorator, factory, registry, nodecard, pin_icons, pin_render
├── themes/          ← WorkbenchTheme, theme decorator/registry, icons, identity
├── widget/          ← BaseWidget: base, binding, converters, factory, factory_interface,
│                      decorator, registry, interface, globals, identity, sizing
├── keymap/          ← keymap registration
├── errors/          ← error_info, haywire_exception (UI-level)
├── extends/codemirror/ ← jedi-backed autocomplete/hover for CodeMirror editors
├── access_stamp.py  ← access stamp on UI objects
├── hover_tip.py     ← hover tooltip helper
├── console_bridge.py ← console bridge
└── utils.py         ← shared helpers
```

## 3. Always-load vs On-demand

### Always-load

- `components/graph/` (canvas) — the editing surface; the `lastMousePos` resume workaround lives here.
- `panel/registry.py`, `panel/base.py` — Panel contract used by every haybale library.
- `editor/registry.py`, `editor/base.py`, `editor/wrapper.py` — Editor contract and lifecycle.
- `app/shell.py` — app shell hosting slots, panels, editors.
- `panel/render_utils.py` + `panel/setting_widget_model.py` — canonical path for rendering any settings field; read together (ADR 0017).

### On-demand

- `widget/` — BaseWidget (ADR 0007). Start with `base.py`, `binding.py`, then `factory.py`.
- `widget/binding.py` — reactive two-way binding to ports and cells.
- `elements/flyout.py` — hierarchical hover menus. Read `.insights/feedback_nicegui_nested_menu_flyouts.md` first.
- `modals/*` — adding dialogs; use `hui.dialog_card()`.
- `surface/` — focus/surface presentation tree.
- `skin/`, `themes/` — `NodeTheme`/`WorkbenchTheme`, CSS tokens, node skins.
- `components/debug_overlay/` — event tracing and performance profiling.
- `components/minimap/`, `components/cull/` — rendering performance of large graphs.
- `extends/codemirror/` — jedi autocomplete and hover docs for code editors.

## 4. Rules & Boundaries

- UI MUST NOT contain engine logic; graph and execution code stays in `core/`.
- No hardcoded colors, `box-shadow` on chrome, `truncate` on QBtn, or `ui.card()` inside `ui.dialog()`. See `docs/reference/design-guide.md`.
- Use `hui.dialog_card()` (carries `hw-panel`) inside dialogs.
- The NiceGUI slot stack is per asyncio task: never wrap `ui.notify()` in `asyncio.ensure_future()`.
- Autofocus in dynamic popups needs `ui.timer(0.1, ...)` plus `run_javascript`.
- Minimap must be a sibling of `ZoomPanContainer`, never a child.
- Pin lookup: prefer `pin.flow_type.value` (`'data'`) over `str(pin.flow_type)`.
- A settings widget binds the shared `DataField` cell. `SettingWidgetModel.set_value` forwards to `on_edit` and never writes the cell itself; writing both would race the next registry sync.
- Hover-flyout menus go through `elements/flyout.py`. No ad-hoc close timers: NiceGUI 3.x drops closed-menu DOM.
- Follow `docs/reference/design-guide.md` for new UI features.

## 5. Source of Truth

| Concept | Canonical file | Notes |
|---------|---------------|-------|
| Graph canvas | `components/graph/` | Vue canvas + generated events |
| Panel registry | `panel/registry.py` | Receives panels from haybale libs |
| Editor registry | `editor/registry.py` | Receives editors from haybale libs |
| Theme decorator | `themes/decorator.py` | `@theme(...)` registration |
| Skin factory | `skin/factory.py` | Resolves which skin renders a node |
| App shell | `app/shell.py` | Top-level layout and slot mounting |
| Settings field rendering | `panel/render_utils.py` | Entry points → group → row → shared widget → write policy |
| Settings field → widget adapter | `panel/setting_widget_model.py` | Thin `WidgetModel` over a `DataField` cell |
| Nested hover-flyout | `elements/flyout.py` | Add-node menu and Promote-Setting menu |

---

## Dependencies

### Depends on

- [haywire-core-engine](haywire-core-engine.md) — graph, node, session, signal types.
- External: NiceGUI, Quasar, Vue 3, `duit[nicegui]`.

### Depended on by

- [haywire-studio](haywire-studio.md) — hosts the shell and workspace.
- [haybale-core](haybale-core.md), [haybale-studio](haybale-studio.md) — register panels, editors, themes, widgets.

---

## Key Entry Points

| Entry point | File | Description |
|-------------|------|-------------|
| App shell | `app/shell.py` | Wires slots, panels, editors into a NiceGUI page |
| Graph canvas | `components/graph/` | Backend half of the Vue canvas |
| Settings render | `panel/render_utils.py` | Renders a `Settings` instance as labelled form rows |
| Panel host render | `panel/host_rendering.py` | Renders a panel under host ownership |
