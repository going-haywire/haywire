# Module: haybale-studio

> Studio companion library: registers editors, panels, file-focus model, and state container that the Haywire Studio workspace uses by default.

**Path:** `barn/haybale-studio/haybale_studio/`
**Language:** Python 3.10+
**Owner:** Haywire studio team (bundled plugin)
**Tree hash:** `18c6dab24dd5fcbdc447687645cc015fc7242829`
**Mapped at:** 51d1ac64 (2026-06-17)

---

## 1. Scope & Purpose

Where [haybale-core](haybale-core.md) provides nodes/types for graphs, `haybale-studio` provides the **studio's UI furniture**: concrete editors (graph editor wrapper, file viewer, etc.), the file-focus model, panels (library overview, properties editor, file browser), the workbench/state container, and the studio's default theme/skin set. Removing it would leave the studio with no editors or panels registered.

## 2. Folder Architecture

```
haybale_studio/
├── __init__.py              ← Library entry (BaseLibrary subclass)
├── adapters/                ← studio-specific adapters
├── editors/                 ← Editor classes (graph editor, file viewer, …)
│   └── …/ with major rewrites to file_browser.py, properties_editor.py
├── nodes/                   ← studio-only node types
├── panels/
│   ├── __init__.py (new)   ← exports
│   ├── canvas_settings.py (new) ← canvas zoom/pan preference panel
│   ├── context_menu/        ← file/node actions
│   └── …
├── settings/                ← studio settings descriptors
├── skins/
│   └── node_skin.py (major rewrite) ← widget rendering per node type
├── state/                   ← state container (edit/runtime, focuses)
├── themes/                  ← studio themes
├── types/                   ← studio value/port types
├── widgets/                 ← studio widgets
├── focuses.py               ← focus model
├── file_focus.py            ← file-typed focus
└── loop_scheduler.py        ← LoopScheduler (NiceGUI event-loop scheduler, ADR 0002)
```

## 3. Always-load vs On-demand

### Always-load

- `__init__.py` — `Library` and `register_components()`.
- `focuses.py` + `file_focus.py` — focus model is central to the workspace; many panels react to it.
- `state/` — edit/state container that other components subscribe to.

### On-demand

- `editors/` — when adding/changing an editor; pair with `haywire/ui/editor/wrapper.py`.
- **`skins/node_skin.py`** (major rewrite) — renders node skin (widget layout, colors, icons). Pair with [widget unification](../../../.codemap/modules/haywire-core-ui.md) (ADR 0007).
- `panels/canvas_settings.py` (new) — canvas zoom/pan preferences.
- `panels/` — when modifying built-in panels (file browser, properties, etc.).
- `themes/` — when touching visual presentation.
- `settings/` — when surfacing studio settings.
- `loop_scheduler.py` — when changing validation debouncing; implements `ValidationScheduler` (ADR 0002).

## 4. Rules & Boundaries

- Must register components in `Library.register_components()`; no side-effect imports.
- Editor classes should subclass `haywire.ui.editor.base.Editor`; wrappers handle lifecycle.
- Focus IDs are stable identifiers — see `tests/libraries/test_focuses_have_ids.py` for the contract.
- Reactive panel updates: see `tests/libraries/test_clipboard_reactive.py` for the expected pattern.
- Inherits all haybale renaming/test reload gotchas from [haybale-core](haybale-core.md).

## 5. Source of Truth

| Concept | Canonical file | Notes |
|---------|---------------|-------|
| Library entry | `haybale_studio/__init__.py` | `Library` subclass |
| Focus model | `focuses.py` + `file_focus.py` | Identifies the "thing under the workspace" |
| State container | `state/` | Workbench edit/runtime state |

---

## Dependencies

### Depends on

- [haywire-core-engine](haywire-core-engine.md), [haywire-core-ui](haywire-core-ui.md).
- [haybale-core](haybale-core.md) — shared types/widgets.

### Depended on by

- [haywire-studio](haywire-studio.md) — runtime dependency.
- [haybale-haystack](haybale-haystack.md), [haybale-libs-other](haybale-libs-other.md).
- [tests](tests.md) — `tests/studio/`, `tests/libraries/`.

---

## Key Entry Points

| Entry point | File | Description |
|-------------|------|-------------|
| Library plugin | `__init__.py:Library` | Discovered via `haywire.libraries` entry point |
