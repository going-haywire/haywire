# Module: Haywire Core — Engine

> The framework heart: DI container, graph/node/edge model, dual-flow execution VM (assembly → interpreter), settings single-cell model, library system, marketstall (install/share/manifest) backend, host.toml store, volumes, undo, session, and every registry plugins hook into. Pure Python, no NiceGUI imports.

**Path:** `packages/haywire-core/src/haywire/core/`
**Language:** Python 3.10+
**Owner:** Haywire core team
**Tree hash:** `50bc578ca0b79a8ea76b7bfd84bcf7e950c463a1` (part of packages/haywire-core)
**Mapped at:** 9b104fd36 (2026-11-10, branch feat/exec-audio)

---

## 1. Scope & Purpose

The engine layer. It owns the graph data model (nodes, edges, pins/ports), the dual-flow execution model (control pins order work, data pins carry values), the DI framework, the settings and registry systems, validation, undo/redo, clipboard, macros/subgraphs, access control, the library plugin system, the marketstall backend (manifests, sources, installer, provenance, share), the `host.toml` app store, and the volumes/value-storage layer. It has **no UI dependencies** — `haywire/ui` builds on it. If this module broke, nothing would execute.

## 2. Folder Architecture

```
haywire/core/
├── di/              ← DI container: module-level globals (NOT ContextVar), config, test_config
├── graph/           ← graph model + editor, validation, scheduler.py (ADR 0002), clipboard.py,
│                      arrange.py, stacking.py, stage.py, subgraph*.py, edit_route.py, metadata.py
│   ├── prehydration/ ← pre-load graph shaping
│   └── utils/
├── node/            ← node base/behavior/data/factory/registry, node_warning.py, promotion.py (ADR 0014),
│                      layout.py, inspector.py, previous_setup.py
├── edge/            ← edge model, edge_wrapper.py, settings.py, style.py, arrow_heads.py
├── assembly/        ← graph → execution pipeline: control_flow_builder, data_flow_builder, flat_view,
│                      flow_assembly_manager
├── execution/       ← dual-flow VM: vm.py, interpreter.py, flow.py, flow_queue.py, execution_group.py,
│                      event_source.py (queue_mode, ADR 0010), callback_manager.py, compile_result.py
├── settings/        ← settings descriptors and single-cell model (ADR 0013): descriptor, settings,
│                      registry, value, settings_{framework,library,graph,node,edge}.py, persistence.py
├── registry/        ← registry base, component, dependency_graph, folder_scan, lifecycle events
├── library/         ← plugin system: base, decorator, discovery, registry, haybale.py / haybale_toml.py,
│                      file_watcher.py (hot-reload), dep_detect/dep_edit, compatibility.py, identity.py
├── marketstall/     ← install/share backend: marketstall-level installer, sources, refresh, cache,
│                      parsing, requirement, subscribe, url_resolution, framework_gate, host_providers/
├── host/            ← store.py (host.toml app-level persistence; enabled-library state)
├── publishing/      ← release/publish pipeline: barn, generate, git, manifest/, pipeline/, drift/, readme
├── macro/           ← macro (reusable component) registry, template, promote, origin, source
├── catalog/         ← catalog entries + registry
├── authoring/       ← node authoring: registration, node_clone, deps, targets
├── access/          ← access tiers and resolver (tier, level_mode, presence, resolver)
├── session/         ← session/context/handlers/protocols; workspace/ (per-project state)
├── state/           ← reactive state containers, state registry, data_namespace
├── signals/         ← signal bus, dispatcher, descriptor, host, peer, vocabulary
├── undo/            ← history manager, actions/, config, origin, settings (no-op variant included)
├── update/          ← update check, pin, conflict, confirmed
├── volumes/         ← value storage: store, resolve, keys, value
├── types/           ← core value & port types; widget_model.py (WidgetModel protocol, ADR 0017), wire, pipe
├── adapter/         ← type/port adapters: base, factory, registry
├── validation/      ← structural_validator, interface
├── errors/          ← ledger, boundary, refusal, haywire_exception, node_exceptions
├── farmhand/        ← MCP-facing tool registry + schema/pagination (Farmhand API surface)
├── debug/           ← configurator, debug_settings, keys
├── docs/            ← canons.py, tree.py (served docs tree)
├── tooling/         ← tooling settings
├── skin/            ← skin settings, fonts, tags
├── namespaces.py    ← namespace constants
├── storage.py       ← storage path helpers (workspace + per-library storage)
├── tomlio.py        ← TOML read/write helpers
└── workspace.py     ← workspace object
```

## 3. Always-load vs On-demand

### Always-load (read these first for any task in this module)

- `di/` — DI container; nearly everything resolves through it.
- `graph/` — core graph model. `graph/editor.py` must be imported before other haywire modules in tests (circular-import guard).
- `node/` — node base classes, worker/port model.

### On-demand

- `assembly/`, `execution/` — how graphs run (dual-flow, scheduling, lazy propagation, execution groups).
- `graph/scheduler.py` — validation debounce strategy (`ValidationScheduler`/`ScheduleHandle`). ADR 0002.
- `graph/clipboard.py` — copy/paste (`ClipboardPayload`, serialize/deserialize).
- `graph/arrange.py`, `graph/stacking.py` — node arrange verbs and stacking.
- `graph/subgraph*.py`, `macro/` — grouping/collapsing and macro components.
- `node/node_warning.py` — node warnings (compatibility flags).
- `node/promotion.py` — setting↔port promotion (ADR 0014); promoted port id == `descriptor.storage_key`.
- `settings/` — settings descriptors/resolution. `persistence.py` is pure file I/O (`SettingsFileStore`).
- `execution/event_source.py` — per-event realtime behavior (`queue_mode`/`max_queue_size`, ADR 0010).
- `library/` — plugin discovery/loading/hot-reload (see [library plugin system cross-cut](../cross-cuts/library-plugin-system.md)). `library/compatibility.py` for versioning.
- `marketstall/`, `publishing/`, `host/` — install/share, release publishing, host.toml.
- `access/` — tiers and permission resolution.
- `volumes/` — value storage.
- `undo/`, `session/`, `state/`, `signals/`, `validation/`, `errors/` — persistence, undo, reactive state, signals, validation, error ledger.
- `farmhand/` — Farmhand tool surface (MCP).
- `registry/` — adding a new registry or component kind.
- `types/widget_model.py` — `WidgetModel` protocol (ADR 0017), shared by `DataPort` and the settings widget model.

## 4. Rules & Boundaries

- **No NiceGUI / UI imports in this layer.** UI lives in `haywire/ui`.
- DI uses module-level globals, NOT `ContextVar` (ContextVar broke hot-reload). See `.insights/project_di_context.md`.
- Library enable/disable persistence is owned here (`host/store.py` via `LibraryRegistry`). UI plugins write through it; they do not keep their own state.
- In tests, import `haywire.core.graph.editor` before other haywire modules.
- Call `force_immediate_validation()` only when the `ValidationResult` is needed synchronously, or for graphs on the timer scheduler (ADR 0002).
- Renames here need a `check-rename` sweep (string-based patches and doc citations).
- **Single-cell model** (ADR 0013): a setting's per-instance value lives in a per-field `DataField` cell. `setting.__get__` is a pure cell read. The resolution chain runs only at write/seed time. A persistent field's cell is registry-owned; tier mutations must go through `_notify_subscribers` or registry cells go stale.
- **Promotion is field + direction, not a bridge** (ADR 0014): a promoted port `bind_field`s the setting's cell by reference. Demote freezes the value; recovery is an explicit `reset()`.
- **Widget selection is a stamped port contract** (ADR 0017): `widget_key`/`widget_config` are computed once by `_stamp_widget()`. `choices=` and string `widget=` params are gone; use `widget_config={"options": ...}`.
- A widget writes only to a field where `DataField.accepts_own_value()` holds; `@type` refuses a value type without a wire type, except containers, wrappers and `ADD` (ADR 0043).
- Load hardening: a stale promotion or poisoned node/edge in `load_from_dict` degrades per item (warn and skip), never aborts the whole load.

## 5. Source of Truth

| Concept | Canonical file | Notes |
|---------|---------------|-------|
| DI container | `di/` | Module-level singletons |
| Graph model | `graph/` | Nodes, edges, pins |
| Execution model | `assembly/` + `execution/` | Assembly → dual-flow VM |
| Settings resolution | `settings/descriptor.py`, `settings/settings.py`, `settings/registry.py`, `settings/value.py` | Single-cell model (ADR 0013) |
| Setting↔port promotion | `node/promotion.py` | One cell, two views (ADR 0014) |
| Widget binding contract | `types/widget_model.py` | `WidgetModel` protocol (ADR 0017) |
| Component registries | `registry/`, `state/`, `catalog/` | Node/type/state/catalog registration |
| Plugin system | `library/base.py`, `library/registry.py` | `BaseLibrary`, `LibraryRegistry` |
| Install/share backend | `marketstall/` | Sources, installer, manifest, provenance |
| App-level persistence | `host/store.py` | host.toml |
| Access tiers | `access/resolver.py`, `access/tier.py` | Who can edit what |

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
| Library discovery | `library/discovery.py` | Finds haybale libs |
| Library registry | `library/registry.py` | Enable/disable, bundled-module path resolution |
| Marketstall | `marketstall/` | Install/share backend |
