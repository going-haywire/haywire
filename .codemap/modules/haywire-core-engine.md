# Module: Haywire Core — Engine

> The framework heart: dependency-injection container, graph/node/edge model, dual-flow execution VM, settings resolution, the library system, the marketstall (install/share/manifest) backend, the host.toml store, and all the registries plugins hook into. Pure Python, no NiceGUI imports.

**Path:** `packages/haywire-core/src/haywire/core/`
**Language:** Python 3.10+
**Owner:** Haywire core team
**Tree hash:** `(part of packages/haywire-core: 93e6c623)`
**Mapped at:** a08a6931 (2026-05-31)

---

## 1. Scope & Purpose

This is the engine layer. It defines the graph data model (nodes, edges, pins/ports), the dual-flow execution model (control + data), the DI framework, the settings/registry systems, validation/undo, the library plugin system, and the **marketstall** backend (manifests, sources, installer, provenance, share) plus the **host** store that persists app-level state like enabled libraries (host.toml). It has **no UI dependencies** — `haywire/ui` builds on top of it. If this module broke, nothing would execute.

## 2. Folder Architecture

```
haywire/core/
├── di/           ← dependency injection (module-level globals, NOT ContextVar)
├── graph/        ← graph model + editor + scheduler.py (injectable validation debounce, ADR 0002)
├── node/         ← node base classes, ports, workers
├── edge/         ← edge model, connection rules
├── assembly/     ← graph→execution assembly pipeline
├── execution/    ← the dual-flow execution VM
├── settings/     ← settings descriptors, resolution, registry
├── registry/     ← component registries (nodes/types/etc.)
├── library/      ← plugin system: base, decorator, discovery, loader, registry, scope
├── marketstall/  ← install/share backend: installer, manifest, sources, provenance, share
├── host/         ← host.py + store.py (host.toml app-level persistence)
├── adapter/      ← type/port adapters
├── types/        ← core value & port types
├── session/      ← session management
├── state/        ← reactive state containers + state registries
├── validation/   ← graph validation rules
├── undo/         ← undo/redo stack
├── debug/        ← debug helpers
├── errors/       ← error types
└── namespaces.py ← namespace constants
```

## 3. Always-load vs On-demand

### Always-load (read these first for any task in this module)

- `di/` — the DI container; nearly everything resolves through it. Module-level globals, not ContextVar (see `.insights/project_di_context.md`).
- `graph/` — core graph model; `graph.editor` must be imported before other haywire modules in tests.
- `node/` — node base classes and the worker/port model.

### On-demand

- `assembly/`, `execution/` — when touching how graphs run (dual-flow, scheduling, lazy propagation).
- `library/` — when changing plugin discovery/loading/hot-reload or `BaseLibrary` (see [library plugin system cross-cut](../cross-cuts/library-plugin-system.md)).
- `marketstall/` — when changing install/uninstall, manifest parsing, remote sources, provenance, or share/export.
- `host/` — when changing host.toml persistence (e.g. enabled-library state).
- `settings/` — when adding or changing settings descriptors/resolution.
- `edge/`, `adapter/`, `types/` — when changing the type/connection system.
- `session/`, `state/`, `undo/`, `validation/` — persistence, reactive state, undo, validation.
- `graph/scheduler.py` — when changing the validation debounce strategy; defines the `ValidationScheduler`/`ScheduleHandle` protocols + `ThreadingTimerScheduler` (default) and `SyncScheduler` (tests). The studio injects `haybale_studio.loop_scheduler.LoopScheduler`. See ADR 0002.
- `registry/` — when adding a new registry or component kind.

## 4. Rules & Boundaries

- **No NiceGUI / UI imports in this layer.** UI lives in `haywire/ui`.
- DI uses module-level globals, NOT `ContextVar` (ContextVar broke hot-reload). See `.insights/project_di_context.md`.
- Library enable/disable persistence is owned here (`host/store.py` via `LibraryRegistry`) — UI plugins must write through it, not maintain their own.
- In tests, import `haywire.core.graph.editor` before other haywire modules (circular-import guard).
- `force_immediate_validation()` after node setup in tests before asserting.
- Renames here need a `check-rename` sweep (string-based patches/citations).

## 5. Source of Truth

| Concept | Canonical file | Notes |
|---------|---------------|-------|
| DI container | `di/` | Module-level singletons |
| Graph model | `graph/` | Nodes/edges/pins |
| Execution model | `assembly/` + `execution/` | Assembly → dual-flow VM |
| Settings resolution | `settings/` | Descriptors + registry |
| Component registries | `registry/`, `state/` | Node/type/state registration |
| Plugin system | `library/base.py`, `library/registry.py` | `BaseLibrary`, `LibraryRegistry` |
| Install/share backend | `marketstall/` | manifest, sources, installer, share |
| App-level persistence | `host/store.py` | host.toml (enabled libraries, etc.) |

---

## Dependencies

### Depends on

- Nothing else in this repo (foundation layer). External: `injector`, `attrs`/`cattrs`, `packaging`, `toml`.

### Depended on by

- [haywire-core-ui](haywire-core-ui.md) — builds UI on the engine.
- [haywire-studio](haywire-studio.md) — boots the engine.
- [haybale-core](haybale-core.md) and all haybale libs — register into the engine's registries.
- [haybale-marketplace](haybale-marketplace.md) — wraps `marketstall` + `LibraryRegistry`.
- [tests](tests.md) — extensively.

---

## Key Entry Points

| Entry point | File | Description |
|-------------|------|-------------|
| DI container | `di/__init__.py` | Resolve/bind services |
| Graph editor | `graph/editor.py` | Import-first in tests |
| Execution | `assembly/` + `execution/` | Runs the dual-flow graph |
| Plugin loader | `library/loader.py` | Discovers/loads haybale libs |
| Marketstall | `marketstall/marketstall.py` | Install/share orchestration |
