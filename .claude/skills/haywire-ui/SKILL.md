---
name: haywire-ui
description: Load Haywire UI architecture docs into context. Use when the user wants to build or modify editors, panels, the app shell, or any UI feature in the workspace system.
---

# Load Haywire UI Architecture

Read the following documentation files in order and use them as the authoritative reference for any UI implementation task. After reading, output a brief recap of the key patterns before proceeding with the user's task.

## Files to read

1. `docs/components/editors/editor-canon.md` — `@editor` decorator (`label`, `default_slot`, `opens` — `OpenBehavior` enum: `REQUIRED` / `ON_CONTEXT` / `ON_PAYLOAD`), `BaseEditor` lifecycle (`render(container, context)`, `on_focus(slot, context)`, `on_context_changed(event, context)`, `cleanup`), context-driven rendering
2. `docs/components/panels/panel-canon.md` — `@panel(editor='...', focus=...)` decorator, `BasePanel` lifecycle (`poll(cls, context)` classmethod, `draw(self, context, layout)` instance method), `PanelLayout` API, `Focus` classes (`NodeFocus` / `EdgeFocus` / `GraphFocus`), ordering, panel-aware editor hosting
3. `docs/architecture/studio/studio-arch.md` — the studio as a product: 4-slot layout (Left / Main / Right / Bottom), TopBar / ActivityBar / ContextBar / StatusBar, `WorkspaceState` + presets, `Session` + `SessionContext`, context events, cross-session broadcast

Optional context (load if the task touches them):

- `docs/architecture/session-and-state/session-and-state-arch.md` — `AppState` / `SessionState` taxonomy, `LibraryStateRegistry`, container subscription, lifecycle
- `docs/reference/design-guide.md` — visual / UX rules, design tokens, `hui` API patterns

## After reading

Summarise in 6–10 bullet points:
- The `@editor` / `@panel` decorator contract — `default_slot` constraints (Left/Right are `REQUIRED`-only), `opens` enum, `editor=` + `focus=` for panels
- `BaseEditor.render(container, context)` and `on_context_changed(event, context)` contract — keep `on_context_changed` fast, filter by `event.change_type`
- `BasePanel.poll(cls, context)` (classmethod, fast) vs `draw(self, context, layout)` (instance, called only after poll=True)
- The 4-slot layout (Left / Main / Right / Bottom) and which `default_slot` each editor targets
- `SessionContext` fields (`active_node`, `active_edge`, etc.) and the two state namespaces — `ctx.app_data[Cls]` (AppState) and `ctx.data[Cls]` (SessionState)
- `ContextChangedEvent` flow + `reveal_editor` field (NOT the old `metadata['main_tabs']` / `metadata['bottom_tabs']` shims — those were removed)
- `EditorTypeRegistry` / `PanelRegistry` are `BaseRegistry` subclasses → hot-reload aware; new classes picked up at next render boundary
- NiceGUI slot context rules: only call `ui.*` inside `render()` / `draw()`; don't cache `ctx.app_data[Cls]` in long-lived `__init__` (stale on hot-reload)

Then proceed with the user's task using these patterns as the guide.
