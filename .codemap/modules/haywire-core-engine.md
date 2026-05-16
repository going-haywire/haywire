# Module: Haywire Core Engine

> The graph engine: nodes, edges, ports, types, the assembly→VM execution pipeline, DI wiring, session/state, settings, and the registry/library framework. This is the framework layer everyone else builds on; it does not know about NiceGUI.

**Path:** `packages/haywire-core/src/haywire/core/`
**Language:** Python 3.10+
**Owner:** Haywire core team
**Tree hash:** `520f7ab7cac4798334fe611c45c3f477d6469fdf` (whole package)
**Mapped at:** b2e5340b (2026-05-16)

---

## 1. Scope & Purpose

This is the framework half of `haywire-core`. It defines the dual-flow node model (control + data pins), the lazy-propagation graph editor, the Assembly→Interpreter→VM execution pipeline, the DI container (module-level globals; see CLAUDE.md trap), the settings descriptor system (`shadow()`/`watch()`), the library plugin protocol, sessions, state, signals, validation, and adapters. If you are touching execution order, port lifecycle, edge propagation, node behavior, or DI wiring — start here.

## 2. Folder Architecture

```
core/
├── adapter/         ← type adapters (port↔value coercion)
├── assembly/        ← graph→executable assembly (control_flow + data_flow builders)
├── debug/           ← debug configurator, settings, keys
├── di/              ← injector-based DI (module-level globals, NOT ContextVar)
├── edge/            ← edge model + wrapper
├── errors/          ← haywire_exception, node_exceptions, error utils
├── execution/       ← VM, scheduler, interpreter, callbacks, ExecutionContext, flow
├── graph/           ← Graph base/editor (lazy-propagation), validation, graph→python
├── library/         ← Library base, decorator, discovery, file_watcher, registry
├── node/            ← Node base/decorator/factory/registry/wrapper, behavior, properties
├── registry/        ← generic registry base, dependency_graph, folder_scan, lifecycle
├── session/         ← session_manager, context, handlers, protocols, signals/, workspace/
├── settings/        ← SettingsRegistry, descriptors, schema, value, enums
├── state/           ← edit/runtime state containers
├── types/           ← FlowType, port types, value types
├── undo/            ← undo/redo machinery
├── validation/      ← graph & node validators
├── namespaces.py    ← canonical namespace string utilities
└── utils.py         ← misc shared helpers
```

## 3. Always-load vs On-demand

### Always-load (read these first for any task in this module)

- `graph/editor.py` — Graph editor with lazy propagation; MUST be imported before other haywire modules in tests (circular-import gotcha).
- `node/base.py` — Node base class; central authority for ports, behavior, properties.
- `execution/vm.py` + `execution/interpreter.py` — control-flow VM and instruction interpreter.
- `di/context.py` + `di/config.py` — DI scopes and module-level container (see `.insights/project_di_context.md`).
- `library/base.py` — `BaseLibrary` plugin contract; entry-point loading lives in `discovery.py`.

### On-demand (read only when the task touches these areas)

- `assembly/*` — only when modifying how graphs compile into VM programs.
- `settings/descriptor.py` — when adding `shadow()`/`watch()` to a node/library.
- `session/signals/*` — when emitting/listening to UI/system signals (see signals cross-cut).
- `adapter/*` — when adding type coercion across port boundaries.
- `state/*`, `undo/*` — when working on user-facing edit history.
- `registry/folder_scan.py`, `library/file_watcher.py` — when debugging hot-reload.

## 4. Rules & Boundaries

- This module MUST NOT import from `haywire/ui/` or any `haybale-*` library.
- DI uses **module-level globals**, not `ContextVar`. Switching back broke hot-reload — don't redo it without solving that.
- Tests must `import haywire.core.graph.editor` before any other haywire module to avoid circular imports.
- After node setup in tests, call `force_immediate_validation()` to flush the dirty queue before asserting.
- Settings: don't introduce patterns that conflict with the existing reactive `shadow()`/`watch()` descriptors.
- Ownership models / singleton patterns / registration paths are NOT to be assumed — ask before changing.

## 5. Source of Truth

| Concept | Canonical file | Notes |
|---------|---------------|-------|
| Node base class | `node/base.py` | All concrete nodes subclass this |
| Graph + lazy propagation | `graph/editor.py` | Must be imported first in tests |
| Execution VM | `execution/vm.py` | Control-flow execution engine |
| DI container | `di/context.py` | Module-level globals (intentional) |
| Library protocol | `library/base.py` | `BaseLibrary.register_components()` |
| Settings descriptors | `settings/descriptor.py` | `shadow()` / `watch()` |
| Type system | `types/` | FlowType, port types, value types |
| Signals bus | `session/signals/bus.py` | Vocabulary in `vocabulary.py` |

---

## Dependencies

### Depends on

- External: `injector`, `attrs`, `cattrs`, `watchdog`, `duit`, `numpy`.

### Depended on by

- [haywire-core-ui](haywire-core-ui.md) — renders graphs/nodes/settings produced here.
- [haywire-studio](haywire-studio.md) — composes the engine into the CLI app.
- [haybale-core](haybale-core.md) — registers nodes/adapters/types via `BaseLibrary`.
- [haybale-studio](haybale-studio.md) — registers editors/panels/state.
- [haybale-haystack](haybale-haystack.md) — multi-graph manager on top of the engine.

---

## Key Entry Points

| Entry point | File | Description |
|-------------|------|-------------|
| Public `haywire` package | `packages/haywire-core/src/haywire/__init__.py` | `import haywire` re-exports core |
| Graph creation | `graph/editor.py` | `Graph` / `GraphEditor` factories |
| Library discovery | `library/discovery.py` | Loads `haywire.libraries` entry points |
| Session bootstrap | `session/session_manager.py` | Session creation + DI wiring |
