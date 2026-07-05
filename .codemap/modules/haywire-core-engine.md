# Module: Haywire Core — Engine

> The framework heart: dependency-injection container, graph/node/edge model, dual-flow execution VM, settings resolution, the library system, the marketstall (install/share/manifest) backend, the host.toml store, and all the registries plugins hook into. Pure Python, no NiceGUI imports.

**Path:** `packages/haywire-core/src/haywire/core/`
**Language:** Python 3.10+
**Owner:** Haywire core team
**Tree hash:** `9abfb988f88b5f930ab41264fc2905884347e8ec` (part of packages/haywire-core)
**Mapped at:** 19bda1e (2026-07-05)

---

## 1. Scope & Purpose

This is the engine layer. It defines the graph data model (nodes, edges, pins/ports), the dual-flow execution model (control + data), the DI framework, the settings/registry systems, validation/undo, copy/paste (clipboard), node compatibility warnings, the library plugin system, and the **marketstall** backend (manifests, sources, installer, provenance, share) plus the **host** store that persists app-level state like enabled libraries (host.toml). It has **no UI dependencies** — `haywire/ui` builds on top of it. If this module broke, nothing would execute.

## 2. Folder Architecture

```
haywire/core/
├── di/              ← dependency injection (module-level globals, NOT ContextVar)
├── graph/           ← graph model + editor + scheduler.py (ADR 0002) + clipboard.py (copy/paste)
├── node/            ← node base classes, ports, workers, node_warning.py (compatibility)
│   └── promotion.py ← (new) setting↔port promotion: bind_field, _resolve_promoted (ADR 0014)
├── edge/            ← edge model, connection rules, edge_wrapper.py
├── assembly/        ← graph→execution assembly pipeline
├── execution/       ← the dual-flow execution VM; event_source.py carries per-source queue_mode
├── settings/        ← settings descriptors, resolution, registry (single-cell model, ADR 0013)
│   └── persistence.py ← (new) SettingsFileStore: pure JSON file I/O + watching, split out of registry.py
├── registry/        ← component registries (nodes/types/etc.)
├── library/         ← plugin system: base, decorator, discovery, loader, registry, scope, compatibility.py
├── marketstall/     ← install/share backend: installer, manifest, sources, provenance, share
├── host/            ← host.py + store.py (host.toml app-level persistence)
├── adapter/         ← type/port adapters
├── types/           ← core value & port types
│   └── widget_model.py ← (new) WidgetModel protocol: structural contract a widget binds to (ADR 0017)
├── session/         ← session management
├── state/           ← reactive state containers + state registries
├── validation/      ← graph validation rules
├── undo/            ← undo/redo stack (includes paste_action.py)
├── debug/           ← debug helpers
├── errors/          ← error types
├── namespaces.py    ← namespace constants
└── storage.py       (new) ← storage path helpers (unifies workspace + per-library storage)
```

## 3. Always-load vs On-demand

### Always-load (read these first for any task in this module)

- `di/` — the DI container; nearly everything resolves through it. Module-level globals, not ContextVar (see `.insights/project_di_context.md`).
- `graph/` — core graph model; `graph.editor` must be imported before other haywire modules in tests.
- `node/` — node base classes and the worker/port model.

### On-demand

- `assembly/`, `execution/` — when touching how graphs run (dual-flow, scheduling, lazy propagation).
- `graph/clipboard.py` — when changing copy/paste logic; handles `ClipboardPayload`, serialization/deserialization.
- `node/node_warning.py` — when adding node warnings (e.g., compatibility flags); integrates with `node_warnings` in `node/registry.py`.
- `library/compatibility.py` — when versioning libraries or handling breaking changes; tracks `compatibility_version`, issues warnings on load.
- `library/` — when changing plugin discovery/loading/hot-reload or `BaseLibrary` (see [library plugin system cross-cut](../cross-cuts/library-plugin-system.md)). `library/registry.py` now resolves the dotted import path for libraries bundled inside the installed `haywire` package (`_bundled_module_path`) so a decorator-registered class matches the one a normal `import haywire.barn.builtin` yields.
- `marketstall/` — when changing install/uninstall, manifest parsing, remote sources, provenance, or share/export.
- `host/` — when changing host.toml persistence (e.g. enabled-library state).
- `settings/` — when adding or changing settings descriptors/resolution. `descriptor.py`, `settings.py`, `registry.py`, `value.py` implement the single-cell model (ADR 0013); `persistence.py` is the pure file-I/O collaborator (`SettingsFileStore`) split out of `registry.py`.
- `node/promotion.py` — when changing setting↔port promotion (a promoted port's id IS the setting's `storage_key`; the port borrows the setting's `DataField` cell by reference). See ADR 0014.
- `edge/`, `adapter/`, `types/` — when changing the type/connection system. `types/widget_model.py` defines the `WidgetModel` protocol both `DataPort` and the settings panel's `SettingWidgetModel` adapter satisfy (ADR 0017).
- `execution/event_source.py` — when changing per-event-node realtime behavior; `queue_mode`/`max_queue_size` (kw-only, `compare=False`) let an event node opt into `DROP`+depth-1 queuing instead of the default `BLOCK`. See ADR 0010.
- `session/`, `state/`, `undo/`, `validation/` — persistence, reactive state, undo, validation.
- `graph/scheduler.py` — when changing the validation debounce strategy; defines the `ValidationScheduler`/`ScheduleHandle` protocols. See ADR 0002.
- `registry/` — when adding a new registry or component kind.

## 4. Rules & Boundaries

- **No NiceGUI / UI imports in this layer.** UI lives in `haywire/ui`.
- DI uses module-level globals, NOT `ContextVar` (ContextVar broke hot-reload). See `.insights/project_di_context.md`.
- Library enable/disable persistence is owned here (`host/store.py` via `LibraryRegistry`) — UI plugins must write through it, not maintain their own.
- In tests, import `haywire.core.graph.editor` before other haywire modules (circular-import guard).
- `force_immediate_validation()` after node setup in tests before asserting.
- Renames here need a `check-rename` sweep (string-based patches/citations).
- **Single-cell model** (ADR 0013): a setting's per-instance value lives in a per-field `DataField` cell, not a raw dict. `setting.__get__` is a pure cell read (`obj._cell_for(self).get_value()`) on every path — no mode branch, no chain walk at read time. The resolution chain runs only at write/seed time. A wired persistent field's cell is **registry-owned** (one live cell per definition, borrowed by instances); tier mutations must funnel through `_notify_subscribers` or registry cells go stale.
- **Promotion is field + direction, not a bridge** (ADR 0014): a promoted port `bind_field`s the setting's cell by reference — one cell, two views, no `_promoted_port_id` read-tier branch, no second value. A promoted port's id IS `descriptor.storage_key`. Demote freezes the cell's current value (no auto-revert); recovery is an explicit `reset()`.
- **Widget selection is a stamped port contract, resolved once** (ADR 0017): `widget_key`/`widget_config` are computed once by `_stamp_widget()`, never recomputed at render time. `choices=` and string `widget=` params are deleted — use `setting[CHOICES](..., widget_config={"options": ...})`.
- CONTROL/CALLBACK flow types cannot carry a `widget_key` (`@type` decorator raises) — they are signals, not editable values.
- Load hardening: a stale promotion, or a poisoned node/edge in `load_from_dict`, degrades per-item (warns and skips) rather than aborting the whole graph load.

## 5. Source of Truth

| Concept | Canonical file | Notes |
|---------|---------------|-------|
| DI container | `di/` | Module-level singletons |
| Graph model | `graph/` | Nodes/edges/pins |
| Execution model | `assembly/` + `execution/` | Assembly → dual-flow VM |
| Settings resolution | `settings/descriptor.py`, `settings/settings.py`, `settings/registry.py`, `settings/value.py` | Single-cell model (ADR 0013); `settings/persistence.py` is file I/O only |
| Setting↔port promotion | `node/promotion.py` | One cell, two views (ADR 0014) |
| Widget binding contract | `types/widget_model.py` | `WidgetModel` protocol (ADR 0017) |
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
