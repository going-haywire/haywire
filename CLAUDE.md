# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

```sh
# Run the app
uv run haywire
uv run python -m haywire_studio

# Tests
uv run pytest                    # all tests
uv run pytest tests/ -k "edge"  # filtered by name
uv run pytest --cov              # with coverage
uv run pytest tests/core/test_graph/test_edge_connections.py  # single file

# Code quality
uv run ruff check .              # lint (line-length = 109)
uv run mypy .                    # type checking

# Build a package
uv build --package haywire-core

# Init a dev test project
cd /tmp && uv run --project <repo-root> haywire init my-test-project --dev
```

## Architecture

Haywire is a Blueprint-inspired visual programming system with a **dual-flow model**: control pins define execution order, data pins pass values.

### Dual-Flow Model

- **EXEC ports** (`FlowType.CONTROL`): define execution order (outlets: `allow_multiple=False`, inlets: `allow_multiple=True`)
- **DATA ports** (`FlowType.DATA`): pass values (outlets: `allow_multiple=True`, inlets: `allow_multiple=False`)
- **CALLBACK ports**: freely configurable
- Pooled inlets override to `allow_multiple=True`

Node types (DATA, CONTROL, EVENT, OUTPUT, LOOPBACK) are determined by control port configuration.

### Package Layout

- **`packages/haywire-core/`** — publishable core (`import haywire`)
  - `haywire/core/` — graph engine, DI, nodes, edges, ports, types, execution, settings
  - `haywire/ui/` — NiceGUI renderers, widgets, canvas, themes
  - `haywire/undo/` — undo/redo history management
- **`packages/haywire-studio/`** — CLI application (`haywire` entry point)
  - `app.py` — main `HaywireApp` class (~500 lines)
  - `config.py` — global/project TOML config
  - `library_manager.py` — runtime library install/UI
  - `init.py` / `share.py` — CLI subcommands
- **`barn/haybale-*/`** — plugin node libraries

### Dependency Injection

The DI container uses the `injector` library. The main module is `HaywireModule` in [packages/haywire-core/src/haywire/core/di/config.py](packages/haywire-core/src/haywire/core/di/config.py).

Key singletons provided: `LibraryRegistry`, `NodeRegistry`, `TypeRegistry`, `RendererRegistry`, `WidgetRegistry`, `AdapterRegistry`, `NodeFactory`, `IHistoryManager`, `GlobalSettingsRegistry`, `ThemeRegistry`.

Entry points: `create_haywire_injector()` and `create_library_system_service()`.

### Library Plugin System

Libraries are discovered via `importlib.metadata.entry_points(group='haywire.libraries')`. Each library:
1. Defines a class decorated with `@library(...)` inheriting `BaseLibrary`
2. Implements `register_components()` to scan folders into registries
3. Registers itself via `[project.entry-points."haywire.libraries"]` in `pyproject.toml`

Hot-reload works for editable installs via `file_watcher=True` on the `@library` decorator.

### Edge Lifecycle

Three-tier lifecycle: `link()` → `unlink()` → `detach()`. Two-tier port storage: `_linked_edges` (active) + `_all_edges` (all). Displacement is asymmetric: inlet informs outlet, outlet does NOT inform inlet.

### Lazy Propagation

`is_lazy` flag is per-edge (on `Edge`/`EdgeWrapper`), not per-port. Pipes own all data transport — eager push or lazy `pull_lazy()` (always-latest semantics). `resolve_dirty_data()` pulls lazy pipes then fires deferred `on_change` once. `_execute()` resolves dirty ports for all node types.

### Assembly & Execution Pipeline

Graph → Assembly → Flow → VM execution. The graph is descriptive (visual layout); assembly converts it to executable flows once, then the VM interprets them.

- **LocalizedDataFlow**: Each control node gets its own data dependency DAG (backpropagated from its inlets), topologically sorted. Data flow is not global.
- **VM two-stack model**: Done-stack (prevents re-execution) + Loopback-stack (loops/sequences).
- **Lazy bitmasks**: Assembly creates an EVAL_MASK per inlet; execution creates a LAZY_MASK per control node; `AND` determines which data nodes actually run. If lazy state changes at runtime, reassembly is triggered.

### Type System

Three categories:

| Category | Purpose | Example |
| --- | --- | --- |
| `PrimitiveType[T]` | Single primitive | `FLOAT`, `INT`, `BOOL` |
| `BaseType` | Structured object | `MeshData`, `FRAME` |
| `CompoundType[T]` | Typed collection | `ArrayType[FLOAT]`, `PooledType[MESH]` |

Types are descriptors — they describe what flows through ports, not storage. **Child → parent is a passthrough** (no adapter needed, e.g. `Temperature → FLOAT`). Parent → child requires an explicit adapter. Adapter chain resolution uses BFS and is **tested at connection time** with sample data — connection is rejected if the chain fails.

### Node Development Patterns

**Worker parameter names must exactly match inlet port IDs:**

```python
def worker(self, context: ExecutionContext, value: float, multiplier: float):
    # 'value' and 'multiplier' must be the exact port IDs
    self.out('result', value * multiplier)
```

**Pooled inlets** return a dict keyed by upstream node ID:

```python
def worker(self, context, values: dict):
    average = sum(values.values()) / len(values)
```

**Config ports** use `flow_type=NONE` — they configure node structure/behavior, trigger `on_change` callbacks, and are read-only to the worker.

**Dynamic port reconfiguration** uses the `rejig` context manager — ports re-added inside the block keep connections; ports not re-added are destroyed:

```python
with self.rejig(include=r'^dynamic_'):
    for i in range(self.count):
        self.add(FLOAT.as_inlet(f'dynamic_{i}'))
```

**Method naming**: prefix custom node methods with `hb_`, `my_`, `custom_`, or `ext_` to avoid conflicts with framework methods.

**Port lifecycle callbacks**: `on_change`, `on_connect`, `on_disconnect` — referenced by method name string, used to trigger dynamic reconfiguration:

```python
self.add(INT.as_inlet('port_count', on_change='hb_reconfigure'))
```

### Settings & Themes

Both use TOML files. Settings have `SettingMode` and `SettingScope` (global vs. project). Themes use a palette system with TOML data files in `haywire/ui/themes/data/`.

## Key Gotchas

- **Test setup**: `create_node_wrapper()` leaves a pending `NODE_ADDED` (priority 90) in the dirty queue. Tests must call `force_immediate_validation()` after setup to flush the queue before asserting, or lower-priority marks (e.g., `NODE_HOT_RELOADED` at priority 80) will be silently dropped.
- **Library paths**: Default to `[]` — must be explicitly provided in app or test DI config.
- **Port rules** are hardcoded in `DataPort.__post_init__` — don't set `allow_multiple` manually for DATA/EXEC ports.
- Line length is **109** (not the ruff default of 88).

### Scoped Panel System

Panels are grouped into **scopes** — named navigation tabs in a panel-consuming editor (e.g. PropertiesEditor's left icon strip). This replaces the old flat `context=` string on `@panel`.

Core types (haywire-core):

- `ScopeDescriptor` (`haywire/ui/panel/scope.py`) — metadata for one tab: `scope_id`, `label`, `icon`, `order`, `poll(ctx) -> bool`
- `PanelIdentity.scope: list[str]` — panels can declare multiple scopes; decorator normalises `str` to `[str]`
- `PanelRegistry.register_scope(editor_id, descriptor)` — registers a scope tab; call before scanning panels folder
- `PanelRegistry.get_scopes(editor_id)` — returns `List[ScopeDescriptor]` sorted by `order`
- `@panel(scope='node')` or `@panel(scope=['node', 'graph'])` — replaces old `context=` parameter

haybale-studio contributions:

- `haybale_studio/editors/scopes.py` — `PROPERTIES_SCOPES` list: `app` (10), `execution` (20), `canvas` (30), `debug` (40), `graph` (50), `node` (60), `edge` (70)
- `haybale_studio/__init__.py` — `register_components()` registers all `PROPERTIES_SCOPES` into `PanelRegistry` before scanning the panels folder
- `haybale_studio/editors/properties_editor.py` — fully rewritten: left 36 px toolbar (one icon button per scope) + content area; scope state stored in `context.metadata['properties_scope']`; auto-falls-back to first available scope when current scope's `poll()` returns False

Architecture principle: haywire-core contains only framework machinery (base classes, registries, decorators). All concrete UI contributions — editors, panels, scope registrations — live in haybale-studio or the node library that defines those nodes.

Multi-scope panels: A panel registered with `scope=['node', 'graph']` appears under both scope tabs. Deregistration removes it from all scopes.
