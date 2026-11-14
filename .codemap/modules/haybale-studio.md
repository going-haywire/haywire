# Module: haybale-studio

> The built-in studio plugin: the editors, panels, surfaces, file browser, state container, themes and settings that make up the Haywire workbench (activity, code, errors, logs, properties, roster, shortcuts, volumes, network and theme settings, account).

**Path:** `barn/haybale-studio/haybale_studio/`
**Language:** Python 3.10+
**Owner:** Haywire studio team (bundled plugin)
**Tree hash:** `643acc424dff795f8d4b21a132f1d869c8a54a30`
**Mapped at:** 9b104fd36 (2026-11-10, branch feat/exec-audio)

---

## 1. Scope & Purpose

`haybale-studio` supplies the workbench surfaces that sit around the graph: the file browser and file viewer, code and component-source editors, the errors, log and activity editors, the properties panel with its app/canvas/debug/execution setting groups, the roster editor for login users, the shortcuts editor, the volumes editor, component docs, and the `account` panel. It builds on the abstractions in [haywire-core-ui](haywire-core-ui.md). It holds the `file` surface and the file-browser state that other libraries react to. If this library were removed the studio would boot without its workbench panels.

## 2. Folder Architecture

```
haybale_studio/
├── __init__.py             ← exposes `Library` (BaseLibrary subclass)
├── editors/
│   ├── activity_editor.py  ← activity tracker view
│   ├── code_editor.py      ← CodeMirror-based editing
│   ├── component_docs_editor.py, component_source_editor.py
│   ├── error_navigation.py, errors_editor.py
│   ├── file_browser.py     ← file browser editor
│   │   └── file_browser_menu/ ← provider.py (menu provider)
│   ├── file_viewer.py, log_editor.py
│   ├── properties_editor.py
│   ├── roster_editor.py    ← login roster (users, roles)
│   ├── shortcuts_editor.py
│   └── volumes_editor.py
├── panels/
│   ├── account/account.py
│   ├── file_browser/menu/file.py
│   └── properties/setting/ ← app.py, canvas.py, debug.py, execution.py (setting groups)
├── settings/               ← network_settings.py, theme_settings.py (typed `setting[...]` markers)
├── states/
│   └── file_browser_state.py ← file-browser state container
├── surfaces/
│   └── file.py             ← file surface
├── themes/                 ← node.py (NodeTheme), workbench.py (WorkbenchTheme)
├── farmhands/              ← Farmhand tool definitions: authoring, catalog, errors, status, _helpers
├── adapters/, nodes/, skins/, types/, widgets/ ← `__init__.py` only (no content)
└── haybale.toml            ← library manifest
```

## 3. Always-load vs On-demand

### Always-load

- `__init__.py` — `Library` and `register_components()`.
- `surfaces/file.py` and `states/file_browser_state.py` — the file surface and state that the file browser, viewer and graph editors read.

### On-demand

- `editors/` — adding or changing an editor. Pair with `haywire/ui/editor/wrapper.py`.
- `editors/roster_editor.py` — login roster UI; the roster itself is owned by haywire-studio `security/roster.py`.
- `panels/properties/setting/` — the properties groups. Add a settings group here; the settings model is in [haywire-core-engine](haywire-core-engine.md).
- `settings/` — studio settings. `theme_settings.py` uses typed markers (`setting[BOOL]`, `setting[INT]`, `setting[CHOICES]`, `setting[STRING]` from `haywire.barn.builtin.types`), not raw Python types.
- `themes/` — `NodeTheme` and `WorkbenchTheme`. Follow `docs/reference/design-guide.md`.
- `farmhands/` — Farmhand (MCP) tool surfaces for studio features.

## 4. Rules & Boundaries

- Register all components in `Library.register_components()`; no side-effect imports.
- Editor classes subclass `haywire.ui.editor.base.Editor`; wrappers handle lifecycle.
- Focus IDs are stable identifiers; see `tests/libraries/test_focuses_have_ids.py`.
- Reactive panel updates: follow the pattern in `tests/libraries/test_clipboard_reactive.py`.
- Inherits the rename and barn-reload traps from [haybale-core](haybale-core.md).

## 5. Source of Truth

| Concept | Canonical file | Notes |
|---------|---------------|-------|
| Library entry | `haybale_studio/__init__.py` | `Library` subclass |
| File surface | `surfaces/file.py` | Surface for file-focused panels |
| Workbench state | `states/file_browser_state.py` | File-browser state container |
| Workbench theme | `themes/workbench.py` | `WorkbenchTheme` |
| Node theme | `themes/node.py` | `NodeTheme` |

---

## Dependencies

### Depends on

- [haywire-core-engine](haywire-core-engine.md), [haywire-core-ui](haywire-core-ui.md).
- [haybale-core](haybale-core.md) — shared types and widgets.

### Depended on by

- [haywire-studio](haywire-studio.md) — runtime dependency.
- [haybale-graph-editor](haybale-graph-editor.md), [haybale-haystack](haybale-haystack.md), [haybale-marketplace](haybale-marketplace.md), [haybale-models](haybale-models.md), [haybale-share](haybale-share.md) — reuse its panels, state and surfaces.
- [tests](tests.md) — `tests/studio/`, `tests/libraries/`.

---

## Key Entry Points

| Entry point | File | Description |
|-------------|------|-------------|
| Library plugin | `__init__.py:Library` | Discovered via `haywire.libraries` entry point |
| File browser | `editors/file_browser.py` | Main file editor |
| Properties editor | `editors/properties_editor.py` | Settings and properties surface |
| Roster editor | `editors/roster_editor.py` | Login roster UI |
