---
status: draft
doc_template: system-reference
scope: Runtime infrastructure that discovers, loads, and tracks libraries — LibraryRegistry, LibraryDiscovery, LibraryIdentity, FileWatcher
see-also:
  - ../../haybale/haybale-marketplace-arch.md
  - ../hot-reload/hot-reload-arch.md
  - ../../haybale/library-canon.md
  - ../../haybale/haybale-package-canon.md
  - ../../reference/glossary.md
---

# Library System — Architecture

## 1. Overview

The Library System is the framework infrastructure that finds Haywire libraries on disk, loads their `Library` classes, and routes their components into the right registries (nodes, types, adapters, widgets, skins, themes). It runs at app startup and stays running for hot-reload.

It is **not** the studio's library-manager UI — see [haybale/marketplace — architecture](../../haybale/marketplace/haybale-marketplace-arch.md) for that. It is **not** how a developer authors a library — see [haybale/library](../../haybale/library-canon.md) for that. It is the layer between the package manager (uv/pip) and the registries.

Two layers, one wrapper:

```text
┌─────────────────────────────────────────────────────────────┐
│  Layer 1 — Package layer  (uv / pip)                        │
│  Installs Python distributions into the virtual environment │
│  and writes entry points to site-packages metadata.         │
└──────────────────────────┬──────────────────────────────────┘
                           │ importlib.metadata.entry_points()
┌──────────────────────────▼──────────────────────────────────┐
│  Layer 2 — Registry layer  (haywire-core)                   │
│  LibraryRegistry scans entry points, loads Library classes, │
│  and populates NodeRegistry / TypeRegistry / WidgetRegistry │
│  / AdapterRegistry / SkinRegistry / ThemeRegistry.          │
└─────────────────────────────────────────────────────────────┘
```

The studio adds a third UI layer ([haybale/marketplace — architecture](../../haybale/marketplace/haybale-marketplace-arch.md)) that wraps both — but the Library System works without it.

## 2. Components

### 2.1 `LibraryDiscovery` (`haywire/core/library/discovery.py`)

Reads the `haywire.libraries` entry-point group. At startup, calls:

```python
importlib.metadata.entry_points(group='haywire.libraries')
```

For each entry point, returns a `DiscoveredLibrary` record with the library ID, the dotted import path, and the install type (see §2.3).

### 2.2 `LibraryRegistry` (`haywire/core/library/registry.py`)

Owns the registry-of-registries. For each discovered library:

1. Imports the `Library` class.
2. Reads its `@library(...)` decorator metadata and constructs a `LibraryIdentity`.
3. Calls `Library.register_components()`, which uses `add_folder_to_registry()` calls to populate the global registries.
4. If `file_watcher=True` on the decorator, starts a `FileWatcher` rooted at the library's source directory.

Class registries it routes into (each is a `BaseRegistry` subclass):

- `NodeRegistry` — `@node` classes
- `TypeRegistry` — `@type` classes
- `AdapterRegistry` — `@adapter` classes
- `WidgetRegistry` — `@widget` classes
- `SkinRegistry` — skin classes
- `ThemeRegistry` — `WorkbenchTheme` / `NodeTheme` subclasses

`LibraryRegistry.add_class_registry(cls, instance)` is how the DI layer registers each one at startup.

### 2.3 `InstallType` enum (`haywire/core/library/install_type.py`)

Three values, all set by `LibraryDiscovery` based on filesystem inspection:

| `InstallType` | Value | Detection rule | Hot-reload |
|---|---|---|---|
| `REGULAR` | `"regular"` | Source path is inside `site-packages` | No |
| `EDITABLE` | `"editable"` | Source path is in the source tree (resolved via `.pth`) | Yes |
| `FOLDER` | `"folder"` | Added via `library_paths` config (no entry point) | Yes |

The install type is propagated to `LibraryIdentity` and exposed by the [haybale/marketplace — architecture](../../haybale/marketplace/haybale-marketplace-arch.md) UI to control which actions are available (Save source, Uninstall).

### 2.4 `LibraryIdentity` (`haywire/core/library/identity.py`)

Frozen dataclass attached as `class_library` on every component class. Carries the library ID, version, label, install type, and source path. The identity is what every other registry uses to attribute a class to its owning library.

### 2.5 `FileWatcher` (`haywire/core/library/file_watcher.py`)

A `watchdog`-based file-system observer started per library when `file_watcher=True`. On any `.py` change inside the library's source directory, it triggers the [hot-reload](../hot-reload/hot-reload-arch.md) pipeline: re-import the module, re-register components, rebuild affected node and edge wrappers, revalidate the graph.

Two switches gate file watching at different scopes:

- `@library(file_watcher=True)` — per-library decorator field. Off by default. Tells `LibraryRegistry` to attach a watcher when this library is loaded.
- `enable_file_watching: bool` — system-level switch passed to `create_library_system_service(...)` / `create_haywire_injector(...)` (see §5). Defaults to `True`. When `False`, no library gets a watcher regardless of the per-library decorator.

The debounce delay (how long the watcher waits after the last `.py` change before triggering a reload) is hardcoded to **0.5 s** in `provide_library_registry` and is not currently a tunable parameter of the public API. If you need a different debounce, call `LibraryRegistry.enable_file_watching(debounce_delay=X, force=True)` directly after constructing the injector.

### 2.6 `BaseLibrary` and `@library` (`haywire/core/library/base.py`, `decorator.py`)

Authoring surface — see [haybale/library](../../haybale/library-canon.md). The architecture-relevant facts:

- `register_components()` is the mandatory hook called by `LibraryRegistry`.
- `validate()` is called after registration; returning `False` aborts the load.
- The `@library` decorator's `file_watcher` parameter wires up §2.5.
- The decorator's `id` parameter is the library's stable identifier across the registries.

## 3. Data flow

### 3.1 Discovery sequence at startup

```text
HaywireApp.__init__()
  │
  ├── LibraryDiscovery.scan()
  │     importlib.metadata.entry_points(group='haywire.libraries')
  │     → [DiscoveredLibrary(id, import_path, install_type), ...]
  │
  ├── for each DiscoveredLibrary:
  │     LibraryRegistry.load(discovered)
  │       │
  │       ├── importlib.import_module(import_path)
  │       ├── Library = getattr(module, 'Library')
  │       ├── LibraryIdentity(...) ← from @library decorator + install_type
  │       ├── library_instance = Library()
  │       ├── library_instance.register_components()
  │       │     └── self.add_folder_to_registry(folder='nodes', registry_cls=NodeRegistry)
  │       │     └── self.add_folder_to_registry(folder='types', registry_cls=TypeRegistry)
  │       │     └── ...
  │       ├── if not library_instance.validate(): abort
  │       └── if @library(file_watcher=True):
  │             FileWatcher(library_instance.source_path).start()
  │
  └── all class registries now populated; app proceeds
```

State classes registered via `LibraryStateRegistry` have a two-phase lifecycle that intersects this loop: instantiation happens per library as it enables, but `AppState.on_enable` is held back until the whole `enable_all_libraries()` loop returns and a catch-up pass runs. See [session-and-state-arch §3.1](../session-and-state/session-and-state-arch.md#31-appstate-lifecycle) and [§5.2](../session-and-state/session-and-state-arch.md#52-librarysystemservice-wiring) for the wiring and rationale.

### 3.2 Priority order when multiple sources provide the same library ID

| Priority | Source | Origin |
|---|---|---|
| 1 | Core libraries | Bundled with `haywire-core` (internal) |
| 2 | Regular pip installs | `site-packages` |
| 3 | Editable pip installs | `pip install -e` (resolved via `.pth`) |
| 4 | Folder paths | Added through `library_paths` config (no entry point) |

First match wins. Detection is by the resolved filesystem location of the import.

### 3.3 Hot-reload trigger

For libraries with `file_watcher=True`:

```text
FileWatcher detects .py change
  │
  ├── importlib.reload(module)
  │
  ├── BaseRegistry._on_change fires for each registry that holds classes from this module
  │     → NodeRegistry, TypeRegistry, AdapterRegistry, WidgetRegistry, …
  │     → For each registered class whose source is in the changed file:
  │         drop old class, register new class under same registry_key
  │
  ├── Affected NodeWrappers rebuild from recipe (port specs serialized → re-instantiated)
  │
  ├── Affected EdgeWrappers rebuild adapter chains
  │
  └── Graph revalidates; UI re-renders
```

See [architecture/hot-reload](../hot-reload/hot-reload-arch.md) for the full pipeline.

## 4. Performance, errors, and boundaries

### 4.1 Entry-point scanning

`importlib.metadata.entry_points()` is fast (milliseconds) but scales linearly with the number of installed Python packages — not just Haywire libraries. There is no caching layer in the framework; if startup time becomes an issue with very large environments, this is the place to look first.

### 4.2 Module-resolution cost

Each library import triggers Python's full import chain (its dependencies, its dependencies' dependencies). For libraries with heavy native dependencies (numpy, opencv), this dominates startup. The framework has no lazy-loading for libraries today — every discovered library is loaded eagerly so its types and nodes appear in the registries.

### 4.3 Hot-reload memory

Hot-reload does not unload the *old* module — Python's import system keeps stale references in `sys.modules` and in any closures that captured them. The framework's discipline is to rebuild every wrapper that references a reloaded class (see §3.3) so user code sees only the new class. Memory grows on each reload; restart is the only cleanup.

### 4.4 Error handling

| Error class | Where raised | Effect |
|---|---|---|
| `LibraryDiscoveryError` | `library/registry.py` | Wraps any error during entry-point scanning |
| `LibraryLoadError` | `library/registry.py` | Wraps any error during a single library's load (import error, decorator failure, `register_components()` raises) |

A failed library does not abort the app — it is logged and skipped, its components do not appear in the registries.

### 4.5 Boundary — what the Library System is not

- **Not a package manager.** It does not install, uninstall, or update Python packages. That is uv/pip (Layer 1) and the [library-manager UI](../../haybale/marketplace/haybale-marketplace-arch.md) (Layer 3) wrapping uv.
- **Not a marketplace.** The `marketplace.toml` format and feed-fetching live with the library-manager UI, not here.
- **Not the place where component authoring is documented.** That belongs in [haybale/library](../../haybale/library-canon.md) and [haybale/haybale-package](../../haybale/haybale-package-canon.md).

### 4.6 Authoring contract for libraries

A haybale library is a Python package with:

1. A `pyproject.toml` declaring the entry point:
   ```toml
   [project.entry-points."haywire.libraries"]
   mylib = "haybale_mylib:Library"
   ```
2. An `__init__.py` containing a `@library(...)` decorated `Library` class that subclasses `BaseLibrary`.
3. Implements `register_components()` (mandatory) and `validate()` (returns `bool`).

See [haybale/library](../../haybale/library-canon.md) for the full authoring story and [haybale/haybale-package](../../haybale/haybale-package-canon.md) for packaging and distribution.

## 5. Programmatic embedding

Two factory functions in `packages/haywire-core/src/haywire/core/di/config.py` let you embed the library system outside the studio app — for headless scripts, integration tests, or alternative front-ends.

### `create_library_system_service(...)` — most callers

Convenience factory that creates the DI injector, constructs a `LibrarySystemService`, and runs `service.initialize()` in one call. Use this when you want a fully-loaded library system ready to read from.

```python
from haywire.core.di.config import create_library_system_service

service = create_library_system_service(
    workspace_root='/path/to/project',  # or None to auto-detect
    library_paths=['/path/to/extra/libs'],  # additional folder-loaded libraries
    enable_file_watching=True,              # hot-reload (default True)
    settings_path='~/.haywire/settings.toml',  # global settings (default)
    watch_settings=True,                    # reload settings on file change (default True)
)

# At this point all entry-point libraries are discovered and registered.
node_registry = service.get_node_registry()
panel_registry = service.get_panel_registry()
# ... etc.
```

### `create_haywire_injector(...)` — when you need the injector itself

Returns the raw DI `Injector` without initializing the library system. Use this when you want to wire your own services on top, or when you need to defer `service.initialize()` until later in your bootstrap. Same parameter list as `create_library_system_service` (minus the auto-initialization).

```python
from haywire.core.di.config import create_haywire_injector
from haywire.core.di.config import LibrarySystemService

injector = create_haywire_injector(
    workspace_root='/path/to/project',
    enable_file_watching=False,  # disable hot-reload in CI
)

# Wire your own services here, then initialize the library system:
service = injector.get(LibrarySystemService)
service.initialize()
```

### Parameter reference (both functions)

| Parameter | Type | Default | Notes |
| --- | --- | --- | --- |
| `workspace_root` | `Optional[str]` | `None` (auto-detect) | Project root used for `barn/` discovery and workspace settings. |
| `library_paths` | `Optional[List[str]]` | `None` | Extra folders scanned for `FOLDER`-install libraries (no pyproject required). |
| `enable_file_watching` | `bool` | `True` | System-level hot-reload switch. Set `False` in CI / tests to keep the suite deterministic. |
| `settings_path` | `Optional[str]` | `~/.haywire/settings.toml` | Path to the global settings file. |
| `watch_settings` | `bool` | `True` | Whether to reload settings TOML on file change. |

**For tests:** pass `enable_file_watching=False` and `watch_settings=False` to keep the watchdog observer from leaking threads across test runs. Tests that need to exercise hot-reload should construct the watcher explicitly via `LibraryRegistry.enable_file_watching(...)` after the test setup is complete.

**Embedding outside `haywire-studio`:** the service has no UI dependency — it's pure registry plumbing. You can use it in a Jupyter notebook, a Discord bot, or a CLI runner that loads libraries and reads `node_registry.list_nodes()` without touching NiceGUI.
