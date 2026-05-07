---
name: haywire-libs
description: Load Haywire library plugin system docs into context. Use when the user wants to create, configure, or debug a haybale library plugin — entry points, BaseLibrary, register_components(), hot-reload, DI wiring.
---

# Load Haywire Library System Docs

Read the following documentation files in order and use them as the authoritative reference for any library plugin task. After reading, output a brief recap of key patterns before proceeding.

## Files to read

1. `docs/components/libraries/library-canon.md` — practical guide: `@library` decorator, `BaseLibrary`, `register_components()`, hot-reload via `file_watcher=True`, the `Library` class authoring contract
2. `docs/components/haybale-package/haybale-package-canon.md` — packaging: `pyproject.toml` entry points, folder layout, `haybale-` naming, install/build/publish workflow, `marketplace.toml` distribution
3. `docs/architecture/library-system/library-system-arch.md` — runtime infrastructure: `LibraryRegistry`, `LibraryDiscovery`, `LibraryIdentity`, `FileWatcher`, install-type detection, registry-of-registries pattern, hot-reload pipeline
4. `docs/architecture/library-manager/library-manager-arch.md` — studio's package-manager UI internals: install pipeline, marketplace feed mechanism, source viewer, doc rendering

Note on the **five meanings of "library"** in haywire (see `docs/reference/glossary.md` "Library — five distinct meanings"):
1 = `BaseLibrary` (authoring) → file 1; 2 = Library System (runtime) → file 3; 3 = Haybale package (distribution) → file 2; 4 = Library Manager (studio UI) → file 4; 5 = LibrarySettings/LibraryState → see `docs/components/{settings,states}/` canons.

## After reading

Summarise in 6–10 bullet points:
- The `@library(...)` decorator fields and `BaseLibrary` contract
- `register_components()` — what registries are available and how to scan folders into them
- Entry point declaration in `pyproject.toml` (`[project.entry-points."haywire.libraries"]`)
- Hot-reload: `file_watcher=True`, `library.disable()` / `library.enable()` lifecycle
- DI integration: how the library system provides `NodeRegistry`, `TypeRegistry`, etc. to the injector
- `LibraryManager` — runtime install/uninstall, persisted disabled state, marketplace
- Library path defaults (`[]` — must be explicitly provided) and workspace-local libraries
- Any gotchas called out in the docs

Then proceed with the user's task using these patterns as the guide.
