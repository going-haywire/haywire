# Haywire Codebase Map

**Haywire** is a Blueprint-inspired visual programming system with a dual-flow model: control pins
define execution order, data pins pass values. Built on NiceGUI (web UI) + injector (DI).

---

## Module Table

| Module | Purpose | Manifest |
|--------|---------|---------|
| [haywire-core/engine](#) | Graph engine, DI, nodes, edges, ports, types, settings, execution/assembly | [modules/core-engine.md](modules/core-engine.md) |
| [haywire-core/ui](#) | NiceGUI UI framework — editors, panels, workspace, graph canvas, themes, widgets | [modules/core-ui.md](modules/core-ui.md) |
| [haywire-studio](#) | CLI application entry point — app shell wiring, config, graph/library managers | [modules/haywire-studio.md](modules/haywire-studio.md) |
| [haybale-studio](#) | Studio UI contributions — editors, panels, scopes, settings for the workbench | [modules/haybale-studio.md](modules/haybale-studio.md) |
| [haybale-core](#) | Standard node library — built-in nodes (Tick, ForLoop, Switch, etc.) and types | [modules/haybale-core.md](modules/haybale-core.md) |
| [barn/other](#) | Additional plugin libraries: example, testing, visiongraph, TEST_A | [modules/barn-other.md](modules/barn-other.md) |
| [tests](#) | Test suite — core graph, execution, nodes, settings, UI integration | [modules/tests.md](modules/tests.md) |

---

## Tech Stack

| Layer | Technology |
|-------|------------|
| Language | Python 3.12+ |
| Package manager | uv (workspace monorepo) |
| UI framework | NiceGUI (+ Quasar/Vue) |
| Dependency injection | `injector` library |
| Build backend | hatchling |
| Linter / formatter | ruff (line-length=109) |
| Type checker | mypy |
| Test runner | pytest |
| Plugin discovery | `importlib.metadata.entry_points(group='haywire.libraries')` |

---

## How to Use This Map

1. Load this file (`INDEX.md`) — it always fits in context.
2. Identify the module(s) relevant to your task from the table above.
3. Load only those module manifests.
4. Within each manifest, read the **Always-load** section first; defer **On-demand** files
   until you actually need them.

---

## Key Entry Points

| Purpose | File |
|---------|------|
| Run the app | `uv run haywire` → `packages/haywire-studio/src/haywire_studio/app.py` |
| DI wiring | `packages/haywire-core/src/haywire/core/di/config.py` |
| Library plugin base | `packages/haywire-core/src/haywire/core/library/base.py` |
| Node base class | `packages/haywire-core/src/haywire/core/node/base.py` |
| Test config | `packages/haywire-core/src/haywire/core/di/test_config.py` |

---

## Cross-Cuts (optional deeper docs)

- [cross-cuts/dual-flow-model.md](cross-cuts/dual-flow-model.md) — Control vs. data flow, port rules, node types
- [cross-cuts/library-plugin-system.md](cross-cuts/library-plugin-system.md) — How to build and register a haybale library
