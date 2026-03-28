# Settings Refactor — Context Dump

> Generated: 2026-03-25
> Scope: Bag/prop → Settings/setting rename + ongoing design discussion about FrameworkSettings vs LibrarySettings

---

## What this project is

Haywire is a Blueprint-inspired visual programming system with a dual-flow model (control pins for execution order, data pins for values). It's a Python framework for building node-based dataflow UIs, targeting plugin extensibility via "haybale" library plugins. The UI is built on NiceGUI.

---

## Tech stack

- Python 3.12, uv workspace monorepo
- NiceGUI (UI framework, Quasar/Vue under the hood)
- injector (DI library)
- hatchling (build backend)
- pytest (100% coverage target)
- TOML for settings persistence

---

## Project structure

```
haywire-repo/
├── packages/
│   ├── haywire-core/src/haywire/
│   │   ├── core/
│   │   │   ├── node/           # BaseNode, @node decorator, NodeProperties
│   │   │   ├── settings/       # Settings, setting, FrameworkSettings, LibrarySettings, registry
│   │   │   ├── execution/      # graph execution engine
│   │   │   ├── types/          # port types, DataPort
│   │   │   └── di/             # DI config, test_config.py
│   │   └── ui/
│   │       ├── prefs/          # CanvasSettings, NodeUISettings, etc. (app-layer schemas)
│   │       ├── editors/        # GraphEditor, etc.
│   │       ├── panels/         # NodePropertiesPanel, etc.
│   │       └── workspace/      # WorkspaceState, WorkspaceManager
│   └── haywire-studio/         # CLI app entry point (HaywireApp)
├── barn/
│   ├── haybale-studio/         # studio panels, _settings_panel_base.py
│   ├── haybale-testing/        # test nodes, settings_node.py
│   └── haybale-core/           # standard node library
└── tests/
    ├── core/test_settings/     # test_settings.py, test_schema_rebasing.py, test_hot_reload.py
    └── core/test_reactive.py
```

---

## Architecture — Settings System

### Class hierarchy (post-refactor)

```
Settings                          # haywire/core/settings/settings.py
├── NodeProperties                # haywire/core/node/properties.py — per-instance visual state
├── FrameworkSettings                # haywire/core/settings/schema.py — framework/app-level schemas
│   └── CanvasSettings, NodeUISettings, DebugSettings, ExecutionSettings, ...
├── LibrarySettings               # haywire/core/settings/schema.py — plugin library schemas
│   └── (user subclasses decorated with @settings)
└── <inner classes on nodes>      # declared by node authors as class filter(Settings): ...
```

### Descriptor

`setting()` — `haywire/core/settings/descriptor.py`. Reactive descriptor that:
- Simple mode (no registry): reads/writes `_local_store` directly
- Extended mode (registry injected by `@node`): reads through full TOML resolution chain

### Registry

`SettingsRegistry` — `haywire/core/settings/registry.py`. Central store for:
- Schema definitions (metadata from FrameworkSettings/LibrarySettings classes)
- Values in three tiers: global TOML (`~/.haywire/settings.toml`), workspace TOML, local instance
- Resolution chain: global OVERRIDE > workspace OVERRIDE > local SET > workspace SET > global SET > default

### Node wiring

`@node` decorator calls `_wire_settings_schemas()` in `node/decorator.py`:
- Scans class body for `Settings` subclasses
- Assigns `_field_key` to each `setting()` descriptor: `'{registry_key_dotted}.{class_name}.{field_name}'`
- Stores result as `cls._settings_bags` dict

`BaseNode.__init__` (`node/base.py` ~line 79):
- Instantiates each Settings subclass with registry injected
- Calls `_subscribe_mirrors()` for weakref cache invalidation
- Binds instance directly as node attribute (`object.__setattr__`)

### TOML format

```toml
[ui.node]
bg_color = "#f0f0f0"
font_size = { override = true, value = 14 }  # OVERRIDE mode
```

---

## Key files

| File | Why it matters |
|------|---------------|
| `settings/settings.py` | The `Settings` base class — simple/extended modes, subscribe, to_dict/from_dict, reset |
| `settings/descriptor.py` | The `setting()` descriptor — `__get__`/`__set__`, mirrors, read_only, validate |
| `settings/base.py` | `FieldDescriptor` — metadata contract for UI panels (label, category, widget, choices) |
| `settings/registry.py` | `SettingsRegistry` — resolution chain, TOML load/save, namespace subscriptions |
| `settings/schema.py` | `FrameworkSettings` + `LibrarySettings` — namespace-aware base classes |
| `node/decorator.py` | `_wire_settings_schemas()` — how node authors' inner Settings classes get field keys |
| `node/base.py` | `list_setting_bags()`, settings instantiation loop |
| `node/properties.py` | `NodeProperties(Settings)` — per-node visual state (muted, collapsed, position, skin) |
| `di/test_config.py` | `create_test_bag()`, `create_test_settings_registry()`, `SettingsTestContext` |
| `ui/prefs/` | 8 concrete Settings subclasses for UI configuration — currently in core, debated |
| `barn/haybale-studio/panels/_settings_panel_base.py` | `render_reactive()`, `render_schema()` — drives settings UI panels |

---

## What was just done — the Bag/prop → Settings/setting rename

**Completed in this session.** Fully atomic rename, 357 tests passing.

### What changed

- `haywire/core/property/` subpackage **deleted entirely** (bag.py, descriptor.py, base.py, __init__.py)
- New files created in `settings/`: `settings.py` (was `bag.py`), `descriptor.py` (was `descriptor.py`), `base.py` (was `base.py`)
- `settings/__init__.py` — no longer uses aliases (`Settings = Bag`, `setting = prop`); imports directly
- `FieldDescriptor` is now exported from `settings/__init__.py`
- All framework internals updated: `node/base.py`, `node/decorator.py`, `node/properties.py`, `settings/registry.py`, all `ui/prefs/*.py`
- `barn/haybale-studio` panels updated
- Tests: `test_bag_settings.py` deleted, replaced by `test_settings.py`; `test_reactive.py` and `test_schema_rebasing.py` updated
- Docs updated: `settings.md/01-overview.md`, `02-node-development.md`, `05-reference.md`, `06-testing.md`, `UBIQUITOUS_LANGUAGE.md`

### What was NOT renamed

- `_settings_bags` attribute on node classes (already well-named)
- `NodeProperties` class name (stays as `NodeProperties(Settings)`)
- `list_setting_bags()` method on `BaseNode` (could be renamed to `list_settings()` in future)
- `create_test_bag()` in `di/test_config.py` (function name kept for now)

---

## Open design thread — FrameworkSettings vs LibrarySettings

**Current state:** Two base classes exist — `FrameworkSettings` (for framework/app-level schemas) and `LibrarySettings` (for plugin library schemas).

**User's argument:** `FrameworkSettings` subclasses (`CanvasSettings`, `NodeUISettings`, etc.) are runtime configuration owned by the app shell, not the framework itself. The framework (`haywire-core`) shouldn't be defining canvas grid sizes — that's a `haywire-studio` concern.

**Counter-argument acknowledged:** `ExecutionSettings` (auto_execute, lazy propagation) is legitimately consumed by the engine in `haywire-core`. Moving that to the app layer creates a dependency inversion problem.

**Where the split actually lands:**
- `haywire/ui/prefs/` schemas (`CanvasSettings`, `NodeUISettings`, `MinimapSettings`, `EdgeUISettings`, `WorkbenchSettings`) → should move to app layer (`haywire-studio` or `haybale-studio`)
- `ExecutionSettings`, possibly `DebugSettings` → legitimate core-level schemas
- `FrameworkSettings` as a named base class may be unnecessary — a single schema mechanism with explicit `register_schema()` calls could cover both use cases

**Not yet resolved.** This is a design decision pending further discussion. No code changes made yet.

---

## Gotchas

- `_prop_fields()` is the method name on `Settings` that walks MRO and returns all `setting` descriptors. The name `_prop_fields` is a historical artifact — it was named when `prop` was the descriptor class.
- `_settings_bags` dict on node classes maps accessor name → Settings subclass (the class, not the instance). Instances are created fresh per node in `BaseNode.__init__`.
- `FrameworkSettings` deep inheritance is blocked at `__init_subclass__` time — subclassing a `FrameworkSettings` subclass raises `TypeError`. Same for `LibrarySettings`.
- `setting(mirrors=SomeClass.field)` requires `SomeClass.field._field_key` to already be set at the time the descriptor is constructed. This means the target `FrameworkSettings`/`LibrarySettings` class must have been defined with a `namespace=` kwarg before the mirroring class is defined.
- `registry.py` internally uses `prop` as the type alias for `setting` descriptors in its type annotations — this was changed to `setting` during the refactor but worth verifying if touching that file.
- `NodeProperties` runs in simple mode (no registry) — it does NOT participate in the TOML resolution chain. It's purely local observable state.
- The `@settings` decorator (for LibrarySettings) is separate from the `Settings` class itself. Import: `from haywire.core.settings.decorator import settings`.

---

## Conventions

- Node authors import from `haywire.core.settings`: `Settings`, `setting`, `Color`, `Icon`
- Framework internals also use `Settings`/`setting` — no special carve-out
- Inner class name on a node becomes the accessor: `class filter(Settings):` → `self.filter.threshold`
- `_field_key` format: `'{registry_key_dotted}.{inner_class_name}.{field_name}'`
- `registry_key` uses colons: `haybale_core:node:transform`; `_field_key` replaces `:` with `.`
- Tests call `force_immediate_validation()` after node setup to flush the dirty queue before asserting
- Import `haywire.core.graph.editor` before other haywire modules in test files to avoid circular imports
