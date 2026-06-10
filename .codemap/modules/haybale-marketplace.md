# Module: haybale-marketplace

> Optional plugin that provides the library installer + browser UI: marketplace dialog, library overview/component/source editors, and the `LibraryManager` service. Wraps the engine's `marketstall` backend and pip install/uninstall with hot-reload-safe eviction. When absent, the library-browser slot is simply empty and haybale-studio works unmodified.

**Path:** `barn/haybale-marketplace/haybale_marketplace/`
**Language:** Python 3.10+
**Owner:** Haywire team (optional bundled plugin)
**Tree hash:** (updated 2026-06-10)
**Mapped at:** b5068ae7 (2026-06-10)

---

## 1. Scope & Purpose

`haybale-marketplace` is the runtime UI for discovering, installing, enabling, and uninstalling haybale libraries. It registers two state containers (`LibraryManagerState`, `MarketplaceState`) and a set of editors (library browser, overview, component, component-source, marketplace dialog). `library_manager.py` owns the pip wrap plus the **dry-run pre-eviction + `sys.modules` ejection** logic that keeps hot-reload from corrupting on installs (see memory `project_install_hotreload_fix`). Library enable/disable persistence is **not** owned here — it lives in the core `LibraryRegistry`/`HostStore`; editors call `manager.registry.enable_library/disable_library` directly.

## 2. Folder Architecture

```
haybale_marketplace/
├── __init__.py                ← Library subclass; scans state/ BEFORE editors/
├── library_manager.py         ← LibraryManager service: pip + reload + eviction
├── state/
│   ├── library_manager_state.py  ← publishes LibraryManager for editors
│   └── marketplace_state.py      ← wraps core Marketstall (parse/refresh/impact)
└── editors/
    ├── library_browser_editor.py     ← browse/install/enable surface
    ├── library_overview_editor.py    ← per-library overview
    ├── library_component_editor.py   ← per-component view
    ├── component_source_editor.py    ← source inspector
    └── library_marketplace_dialog.py ← install/upgrade impact + progress dialog
```

## 3. Always-load vs On-demand

### Always-load

- `__init__.py` — Library subclass + `register_components()` (state-before-editors ordering matters).
- `library_manager.py` — the install/uninstall/reload service; central to most tasks here.

### On-demand

- `state/marketplace_state.py` — when changing manifest parsing, refresh, or install/upgrade impact (delegates to core `marketstall`).
- `state/library_manager_state.py` — when changing how editors obtain the manager.
- **`editors/library_browser_editor.py`** (updated UX) — main browser surface; see memory `project_install_hotreload_fix` for 3-step install flow.
- `editors/library_overview_editor.py` (updated) — per-library overview.
- `editors/library_marketplace_dialog.py` — install/upgrade impact + progress dialogs.

## 4. Rules & Boundaries

- Same plugin contract as [haybale-core](haybale-core.md): register via `register_components()`; entry point `marketplace = "haybale_marketplace:Library"`.
- **Scan `state/` before `editors/`** — editors transitively import state classes; reversing the order leaves stale class objects after `force_reload` (same reasoning as haybale-studio).
- **Do not** add enable/disable persistence here — that is owned by core `LibraryRegistry` → `HostStore` (`core/host/store.py`), which writes through to host.toml.
- Install/uninstall must go through the dry-run pre-eviction + `sys.modules` ejection path; bypassing it reintroduces the hot-reload corruption bug.
- Backend logic (manifest/sources/installer/share) belongs in engine [core/marketstall](haywire-core-engine.md), not here — this module is UI + a thin service wrapper.

## 5. Source of Truth

| Concept | Canonical file | Notes |
|---------|---------------|-------|
| Library entry | `haybale_marketplace/__init__.py` | `marketplace` entry point |
| Install/uninstall service | `library_manager.py` | pip + reload + eviction |
| Marketplace orchestration | `state/marketplace_state.py` | wraps core `Marketstall` |
| Install/upgrade UX | `editors/library_marketplace_dialog.py` | impact + progress popups |

---

## Dependencies

### Depends on

- [haywire-core-engine](haywire-core-engine.md) — `BaseLibrary`, `LibraryRegistry`, `core/marketstall`, `core/host`, `LibraryStateRegistry`.
- [haywire-core-ui](haywire-core-ui.md) — `EditorTypeRegistry`, editor/dialog bases.
- [haybale-studio](haybale-studio.md) — provides the slot the browser fills (declared dependency).

### Depended on by

- [haywire-studio](haywire-studio.md) — discovers it as an optional installed plugin.
- [tests](tests.md) — `tests/test_library_manager_*`, `tests/test_marketplace_state.py`, `tests/test_library_browser_*`.

---

## Key Entry Points

| Entry point | File | Description |
|-------------|------|-------------|
| Library plugin | `__init__.py:Library` | `haywire.libraries` entry point `marketplace` |
| Manager service | `library_manager.py:LibraryManager` | install/uninstall/reload |
| Browser UI | `editors/library_browser_editor.py` | main user-facing surface |
