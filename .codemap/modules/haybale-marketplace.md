# Module: haybale-marketplace

> Optional plugin: the library browser and installer UI. A `LibraryManager` service wraps the engine's `core/marketstall` backend, and editors drive the install, uninstall, refresh and add-source flows.

**Path:** `barn/haybale-marketplace/haybale_marketplace/`
**Language:** Python 3.10+
**Owner:** Haywire core team (bundled plugin)
**Tree hash:** `e4c453c9170503694a7161719b25c7cac519d304`
**Mapped at:** 9b104fd36 (2026-11-10, branch feat/exec-audio)

---

## 1. Scope & Purpose

`haybale-marketplace` is what a user sees when they browse, install, update or remove haybale libraries. It is a UI and service layer. The backend (manifests, sources, installer, provenance, share) lives in the engine's `core/marketstall` ([haywire-core-engine](haywire-core-engine.md)). Enable and disable persistence belongs to the engine's `LibraryRegistry` and `HostStore`. This library is optional: the studio runs without it, but users then have no in-app way to install libraries.

## 2. Folder Architecture

```
haybale_marketplace/
├── __init__.py            ← `Library` subclass
├── library_manager.py     ← LibraryManager service over core/marketstall
├── library_origin.py      ← where a library came from
├── uninstall_impact.py    ← uninstall impact analysis
├── config.py, identity.py
├── editors/
│   ├── library_browser_editor.py   ← browse catalog
│   ├── library_overview_editor.py  ← per-library overview
│   ├── _overview_actions.py, _overview_edit_dialog.py, _overview_install_flow.py
│   ├── _add_source_flow/   ← add a source (_state, chrome, copy, panels)
│   ├── _install_flow/      ← install (_state, chrome, copy, panels)
│   ├── _refresh_flow/      ← refresh (_state, chrome, copy, panels)
│   └── _uninstall_flow/    ← uninstall (_state, chrome, copy, panels)
├── panels/
│   └── marketplace_settings_panel.py
├── settings/
│   └── marketplace_settings.py
├── state/
│   ├── library_manager_state.py
│   └── marketplace_state.py
├── farmhands/
│   ├── catalog_tools.py   ← Farmhand catalog tools
│   └── install_tools.py   ← Farmhand install tools
└── haybale.toml           ← library manifest
```

## 3. Always-load vs On-demand

### Always-load

- `__init__.py` — `Library` and `register_components()`.
- `library_manager.py` — the service every flow calls.
- `state/` — scan before `editors/` (see Rules).

### On-demand

- `editors/_install_flow/`, `_uninstall_flow/` — the install and uninstall flows. They must use the dry-run pre-eviction path.
- `uninstall_impact.py` — impact analysis shown before uninstall.
- `editors/_add_source_flow/`, `_refresh_flow/` — remote sources and refresh.
- `library_origin.py` — provenance display.
- `farmhands/` — Farmhand tools for catalog and install.

## 4. Rules & Boundaries

- Register through `Library.register_components()`. Entry point: `marketplace = "haybale_marketplace:Library"`.
- Scan `state/` before `editors/`. Editors import state classes, so reversing the order leaves stale class objects after `force_reload`.
- Do not add enable/disable persistence here. That is owned by core `LibraryRegistry` and `HostStore` (`core/host/store.py`), which writes through to host.toml.
- Install and uninstall go through the dry-run pre-eviction and `sys.modules` ejection path. Bypassing it reintroduces the hot-reload corruption bug.
- Backend logic (manifest, sources, installer, share) belongs in engine `core/marketstall`, not here.
- Same plugin contract as [haybale-core](haybale-core.md).

## 5. Source of Truth

| Concept | Canonical file | Notes |
|---------|---------------|-------|
| Install/library service | `library_manager.py` | Thin wrapper over `core/marketstall` |
| Marketplace state | `state/marketplace_state.py` | Catalog and selection state |
| Library manager state | `state/library_manager_state.py` | Installed-library view |
| Uninstall impact | `uninstall_impact.py` | Dependents and effects |

---

## Dependencies

### Depends on

- [haywire-core-engine](haywire-core-engine.md) — `core/marketstall`, `LibraryRegistry`, `HostStore`.
- [haywire-core-ui](haywire-core-ui.md) — modals (install progress, install safety, upgrade impact).
- [haybale-core](haybale-core.md) — shared types and widgets.

### Depended on by

- [haywire-studio](haywire-studio.md) — optional runtime plugin.
- [tests](tests.md) — `tests/marketplace/`, `tests/marketstall/`.

---

## Key Entry Points

| Entry point | File | Description |
|-------------|------|-------------|
| Library plugin | `__init__.py:Library` | `marketplace` entry point |
| Install service | `library_manager.py` | `LibraryManager` |
| Browser editor | `editors/library_browser_editor.py` | Catalog UI |
| Install flow | `editors/_install_flow/` | Install UX |
