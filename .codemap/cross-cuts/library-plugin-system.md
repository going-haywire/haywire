# Cross-cut: Library Plugin System

> How haybale-* packages are discovered, registered, DI-wired, and hot-reloaded into a running Haywire studio.

## Overview

The word "library" has five meanings in Haywire (see `docs/reference/glossary.md`). In this cross-cut, "library" means a *haybale plugin package*: a Python package that exposes a `Library` class via the `haywire.libraries` setuptools entry point and registers components (nodes, editors, panels, types, widgets, themes, skins, settings) in `Library.register_components()`.

Discovery happens at studio boot via `haywire.core.library.discovery`. A `BaseLibrary` subclass's `register_components()` runs against a registry context, which routes each registration to the appropriate per-category registry. A file watcher (`library/file_watcher.py`) can hot-reload a library in development; reload reuses the existing registry slots so identities remain stable.

Crucially, DI uses **module-level globals** (not `ContextVar`). Switching to ContextVar broke hot-reload because the reloaded module captured a different ContextVar instance — see `.insights/project_di_context.md`.

## Modules Involved

| Module | Role | Manifest |
|--------|------|----------|
| haywire-core-engine | Library base, registry, discovery, file_watcher, DI | [→ modules/haywire-core-engine.md](../modules/haywire-core-engine.md) |
| haywire-core-ui | Editor/panel/theme/skin registries that libraries write into | [→ modules/haywire-core-ui.md](../modules/haywire-core-ui.md) |
| haywire-studio | `library_manager.py` runtime install + reload UI | [→ modules/haywire-studio.md](../modules/haywire-studio.md) |
| haybale-core / studio / haystack / other | Provide the `Library` classes that get discovered | [→ haybale-core](../modules/haybale-core.md) |

## Flow

```
1. studio boots → discovery.scan_entry_points("haywire.libraries")
2. For each entry point:
     module.Library() → BaseLibrary instance
3. instance.register_components(registry_ctx)
     ├── node registry (node/registry.py)
     ├── editor registry (ui/editor/registry.py)
     ├── panel registry (ui/panel/registry.py)
     ├── theme + skin registries
     ├── adapter / type registries
     └── settings registry (settings/registry.py)
4. file_watcher (dev only) → on change: importlib.reload + re-register
5. studio mounts UI; signals propagate node/editor/panel changes
```

## Key Files

- `packages/haywire-core/src/haywire/core/library/base.py` — `BaseLibrary` contract.
- `packages/haywire-core/src/haywire/core/library/discovery.py` — entry-point scanning.
- `packages/haywire-core/src/haywire/core/library/file_watcher.py` — hot-reload trigger.
- `packages/haywire-core/src/haywire/core/library/registry.py` — library-level registry.
- `packages/haywire-core/src/haywire/core/di/context.py` — module-level DI scopes.
- `packages/haywire-studio/src/haywire_studio/library_manager.py` — runtime install/uninstall UI.
- `barn/haybale-*/pyproject.toml` — `[project.entry-points."haywire.libraries"]` declarations.

## Gotchas

- Never use `ContextVar` for DI — it breaks hot-reload. Module-level globals are intentional.
- After `importlib.reload`, top-of-file imports of barn classes are stale. In tests, use `importlib.import_module` + `patch.object` (see `.insights/feedback_barn_module_reload_test_trap.md`).
- A historical bug (`force_reload=True` on initial scans) caused `assert Foo is Foo` to fail with same name / distinct objects. Fixed in `7b7d86e` — watch for recurrences in registry init paths.
- Renaming a registered class needs a `check-rename` sweep: `patch("module.Symbol")` strings, doc citations, and `importlib.import_module(...)` paths slip past IDE rename.
- Don't introduce side-effect imports for registration — everything must go through `register_components()`.
