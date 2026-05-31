# Module: haybale-studio

> Studio companion library: registers editors, panels, file-focus model, and state container that the Haywire Studio workspace uses by default.

**Path:** `barn/haybale-studio/haybale_studio/`
**Language:** Python 3.10+
**Owner:** Haywire studio team (bundled plugin)
**Tree hash:** `87f375f7c060a3115d30a59a0db070cc7f8ae3bb`
**Mapped at:** 4e5c1da7 (2026-05-31)

---

## 1. Scope & Purpose

Where [haybale-core](haybale-core.md) provides nodes/types for graphs, `haybale-studio` provides the **studio's UI furniture**: concrete editors (graph editor wrapper, file viewer, etc.), the file-focus model, panels (library overview, properties editor, file browser), the workbench/state container, and the studio's default theme/skin set. Removing it would leave the studio with no editors or panels registered.

## 2. Folder Architecture

```
haybale_studio/
├── __init__.py     ← Library entry (BaseLibrary subclass)
├── adapters/       ← studio-specific adapters
├── editors/        ← Editor classes (graph editor, file viewer, …)
├── nodes/          ← studio-only node types (if any)
├── panels/         ← library overview, properties editor, file browser panels
├── settings/       ← studio settings descriptors
├── skins/          ← studio skins
├── state/          ← state container (edit/runtime state, focuses)
├── themes/         ← studio themes
├── types/          ← studio value/port types
├── widgets/        ← studio widgets
├── focuses.py      ← focus model (which object the workspace is on)
└── file_focus.py   ← file-typed focus
```

## 3. Always-load vs On-demand

### Always-load

- `__init__.py` — `Library` and `register_components()`.
- `focuses.py` + `file_focus.py` — focus model is central to the workspace; many panels react to it.
- `state/` — edit/state container that other components subscribe to.

### On-demand

- `editors/` — when adding/changing an editor; pair with `haywire/ui/editor/wrapper.py`.
- `panels/` — when modifying built-in panels.
- `themes/`, `skins/` — when touching visual presentation.
- `settings/` — when surfacing studio settings.

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
