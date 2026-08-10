---
name: haywire-libs
description: Load Haywire library plugin system docs into context. Use when the user wants to create, configure, or debug a haybale library plugin — entry points, BaseLibrary, register_components(), hot-reload, DI wiring.
---

# Load Haywire Library System Docs

Read the following documentation files in order and use them as the authoritative reference for any library plugin task. After reading, output a brief recap of key patterns before proceeding.

## Files to read

1. `docs/haybale/haybale-canon.md` — authoring and packaging in one: `@library` decorator, `BaseLibrary`, `register_components()`, the eleven registries, hot-reload via `file_watcher=True`, `pyproject.toml` entry points, folder layout, `haybale-` naming, the compliance contract
2. `docs/reference/files/haybale-toml.md` — the authoring surface: every field, who writes it, and which files it reaches. Descriptive metadata is NOT decorator kwargs
3. `docs/architecture/library-system/library-system-arch.md` — runtime infrastructure: `LibraryRegistry`, `LibraryDiscovery`, `LibraryIdentity`, `FileWatcher`, install-type detection, registry-of-registries pattern, hot-reload pipeline
4. `docs/haybale/marketplace/haybale-marketplace-arch.md` — studio's package-manager UI internals: catalog lifecycle, install pipeline, marketplace feed mechanism, recovery

Read `docs/haybale/metadata-flow.md` as well for any task touching publishing or metadata: it maps `haybale.toml` → `pyproject.toml` → `marketstall.toml` → a consumer's cache.

Note on the **five meanings of "library"** in haywire (see `docs/reference/glossary.md` "Library — five distinct meanings"):
1 = `BaseLibrary` (authoring) → file 1; 2 = Library System (runtime) → file 3; 3 = Haybale package (distribution) → file 1, same page; 4 = Library Manager (studio UI) → file 4; 5 = LibrarySettings/LibraryState → see `docs/components/{settings,states}/` canons.

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
