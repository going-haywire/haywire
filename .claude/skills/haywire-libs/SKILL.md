---
name: haywire-libs
description: Load Haywire library plugin system docs into context. Use when the user wants to create, configure, or debug a haybale library plugin — entry points, BaseLibrary, register_components(), hot-reload, DI wiring.
---

# Load Haywire Library System Docs

Read the following documentation files in order and use them as the authoritative reference for any library plugin task. After reading, output a brief recap of key patterns before proceeding.

## Files to read

1. `docs/documentation/Library_System_Developer_Guide.md` — practical guide: `@library` decorator, `BaseLibrary`, `register_components()`, `pyproject.toml` entry points, hot-reload via `file_watcher=True`
2. `docs/documentation/architecture/Library_System_Technical_Reference.md` — technical reference: `LibraryRegistry`, `NodeRegistry`, `RendererRegistry`, discovery via `importlib.metadata`, `LibraryManager` runtime install/uninstall, disable/enable lifecycle

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
