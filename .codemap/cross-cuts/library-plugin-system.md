# Cross-cut: Library Plugin System

> How haybale-* packages are discovered, registered, DI-wired, and hot-reloaded into a running Haywire studio.

## Overview

"Library" has five meanings in Haywire (see `docs/reference/glossary.md`). Here it means a *haybale plugin package*: a Python package that exposes a `Library` class through the `haywire.libraries` setuptools entry point and registers components (nodes, editors, panels, types, widgets, themes, skins, settings, macros, catalog entries) in `Library.register_components()`.

Discovery happens at studio boot in `haywire.core.library.discovery`, which loads each entry point's `Library` (`_load_library_from_entry_point`). `register_components()` runs against the registries, and each registration routes to its per-category registry. Hot reload in development is driven by `library/file_watcher.py` and the `haybale.toml` watcher in `library/base.py`. Reload reuses registry slots so identities stay stable.

DI uses **module-level globals**, not `ContextVar`. `ContextVar` broke hot reload because a reloaded module captured a different instance (see `.insights/project_di_context.md`).

## Modules Involved

| Module | Role | Manifest |
|--------|------|----------|
| haywire-core-engine | Library base, registry, discovery, file watcher, DI, host store | [→ modules/haywire-core-engine.md](../modules/haywire-core-engine.md) |
| haywire-core-ui | Editor, panel, theme and skin registries that libraries write into | [→ modules/haywire-core-ui.md](../modules/haywire-core-ui.md) |
| haywire-studio | Boots the engine and discovers installed libraries | [→ modules/haywire-studio.md](../modules/haywire-studio.md) |
| haybale-marketplace | Runtime install, uninstall and reload UI | [→ modules/haybale-marketplace.md](../modules/haybale-marketplace.md) |
| haybale-core and other haybale libs | Provide the `Library` classes that get discovered | [→ modules/haybale-core.md](../modules/haybale-core.md), [→ modules/haybale-libs-other.md](../modules/haybale-libs-other.md) |

## Flow

```
1. studio boots → discovery loads entry points in group "haywire.libraries"
2. For each entry point: Library() → BaseLibrary instance
3. instance.register_components()
     ├── node registry
     ├── editor registry        (ui/editor/registry.py)
     ├── panel registry         (ui/panel/registry.py)
     ├── theme + skin registries
     ├── adapter / type registries
     ├── settings registry      (settings/registry.py)
     └── macro / catalog registries
4. file_watcher (dev only) → on change: importlib.reload + re-register
5. studio mounts UI; signals propagate node/editor/panel changes
```

Installed-library enable state is persisted by `LibraryRegistry` through `host/store.py` (host.toml). Bundled libraries inside the `haywire` package resolve via `LibraryRegistry._bundled_module_path`.

## Key Files

- `packages/haywire-core/src/haywire/core/library/base.py`: `BaseLibrary` contract, `register_components()`.
- `packages/haywire-core/src/haywire/core/library/discovery.py`: entry-point discovery.
- `packages/haywire-core/src/haywire/core/library/file_watcher.py`: hot-reload trigger.
- `packages/haywire-core/src/haywire/core/library/registry.py`: library-level registry.
- `packages/haywire-core/src/haywire/core/di/context.py`: module-level DI scopes.
- `packages/haywire-core/src/haywire/core/marketstall/`: install and share backend.
- `packages/haywire-core/src/haywire/core/host/store.py`: host.toml persistence.
- `barn/haybale-marketplace/haybale_marketplace/library_manager.py`: runtime install and uninstall service.
- `barn/haybale-*/pyproject.toml`: `[project.entry-points."haywire.libraries"]` declarations.

## Gotchas

- Never use `ContextVar` for DI. It breaks hot reload; module-level globals are intentional.
- After `importlib.reload`, top-of-file imports of barn classes are stale. In tests use `importlib.import_module` and `patch.object` (see `.insights/feedback_barn_module_reload_test_trap.md`).
- A historical bug (`force_reload=True` on initial scans) made `Foo is Foo` fail for same-name, distinct objects. Fixed in `7b7d86e`; watch registry init paths for recurrence.
- Renaming a registered class needs a `check-rename` sweep. String patches, doc citations and `importlib.import_module` paths slip past IDE rename.
- Do not add side-effect imports for registration. Everything goes through `register_components()`.
