---
status: draft
doc_template: canonical-example
scope: Authoring a Library — BaseLibrary subclass, @library decorator, register_components, validate, hot-reload
see-also:
  - ../haybale-package/haybale-package-canon.md
  - ../../architecture/library-system/library-system-arch.md
  - ../../architecture/hot-reload/hot-reload-arch.md
  - ../../reference/glossary.md
---

# Library — Canonical Example

## 1. What it solves

A **Library** (the haywire `BaseLibrary` subclass, decorated with `@library`) is the plugin protocol that contributes nodes, types, adapters, widgets, skins, themes, and settings to a running haywire app. As an author, you write one Library class per haybale package — the framework discovers it through the `pyproject.toml` entry point, calls `register_components()` to populate the global registries, and (optionally) starts a file watcher so your changes hot-reload without restart.

This is meaning **#1** of the five "library" concepts in haywire (see [reference/glossary §Library — five distinct meanings](../../reference/glossary.md#library-five-distinct-meanings)). For the runtime infrastructure that *uses* your Library class (LibraryRegistry, LibraryDiscovery, FileWatcher), see [architecture/library-system](../../architecture/library-system/library-system-arch.md). For packaging a Library as a distributable Haybale package (pyproject layout, entry points, publishing), see [components/haybale-package](../haybale-package/haybale-package-canon.md).

## 2. How it fits

```text
Author writes                  pyproject.toml                 Discovery
─────────────                  ──────────────                 ─────────
@library(label='...')          [project.entry-points          LibraryDiscovery
class Library(BaseLibrary):    "haywire.libraries"]            scans installed
   def register_components:    mylib = "haybale_mylib:Library" packages on startup
       self.add_folder_to_                                     ↓
         registry(...)                                         LibraryRegistry
   def validate(): ...                                         imports the module,
                                                                instantiates Library,
                                                                calls register_components()
                                                                ↓
                                                                NodeRegistry / TypeRegistry /
                                                                AdapterRegistry / WidgetRegistry /
                                                                SkinRegistry / ThemeRegistry are
                                                                populated; nodes appear in
                                                                the canvas menu.
```

The Library class has two mandatory hooks:

- `register_components()` — call `self.add_folder_to_registry(folder, registry_cls)` for each component category your library contributes. The framework scans the folder for `@node`/`@type`/`@adapter`/`@widget`/etc.-decorated classes and registers each one.
- `validate() -> bool` — return `False` to abort loading. Use for sanity checks (required folders exist, dependencies importable). Most libraries return `True` unconditionally.

Optional: `@library(file_watcher=True)` enables hot-reload — the framework starts a file watcher rooted at the library's source directory and re-runs `register_components()` whenever a `.py` file changes.

**Boundaries.** What the registries actually do at runtime, what `LibraryDiscovery` checks, how `InstallType` is determined, the discovery priority order — all in [architecture/library-system](../../architecture/library-system/library-system-arch.md). The `pyproject.toml` shape, build/publish workflow, and `marketplace.toml` distribution — all in [components/haybale-package](../haybale-package/haybale-package-canon.md).

## 3. Important concepts

**The `@library` decorator.** Sets `class_identity` (a `LibraryIdentity`), records the metadata, and registers the file watcher when `file_watcher=True`. **The bare `@library` form (no parens) is not supported** — always invoke with parentheses, even when only `label=` is given.

| Parameter | Required | Default | Purpose |
|---|---|---|---|
| `label` | yes | — | Human-readable display name |
| `id` | no | derived from `label` | Unique identifier (becomes part of every component's `registry_key`) |
| `version` | no | `'1.0.0'` | Semantic version |
| `description` | no | `''` | Description for the library manager UI |
| `file_watcher` | no | `False` | Enable hot-reload via filesystem observer |
| `dependencies` | no | `[]` | List of required library IDs (currently informational only — load order is by discovery priority, not dependency graph) |
| `url` | no | `''` | Library website |
| `help_url` | no | `''` | Documentation URL |
| `author` | no | `''` | Author name |
| `author_url` | no | `''` | Author homepage |

**The `id` parameter is load-bearing.** It becomes the prefix for every component's `registry_key` — `haybale_mylib:node:my_node`, `haybale_mylib:widget:NumberWidget`, etc. The convention is to match the Python module name (`my_lib` if your package is `my_lib/`); changing it after the library has been published breaks any saved graphs that reference component keys.

**`add_folder_to_registry()` does the heavy lifting.** It scans a folder, imports every `.py` file, and lets each `@node` / `@type` / `@adapter` / `@widget` / `@skin` / `@theme` decorator self-register. You don't enumerate classes manually; the decorators do it.

```python
def register_components(self):
    base = Path(__file__).parent
    self.add_folder_to_registry(folder_path=str(base / 'nodes'), registry_cls=NodeRegistry)
    self.add_folder_to_registry(folder_path=str(base / 'types'), registry_cls=TypeRegistry)
    # ... one call per component category your library contributes
```

The `exclude_patterns=['test_', '__']` kwarg skips matching files — useful when your nodes folder also contains a `test_my_nodes.py` you don't want auto-registered.

**Decorator convention: always use parentheses.** All component decorators (`@library`, `@node`, `@adapter`, `@skin`, `@widget`, `@editor`, `@panel`, `@theme`, `@type`) must be invoked with parentheses, even with no arguments. Most require at least one keyword argument anyway, so this is rarely visible — but `@node()` (with parens) is required even for an "empty" decoration; `@node` (no parens) is unsupported.

**Imports** (verified against codebase 2026-05):

```python
from haywire.core.library.base import BaseLibrary
from haywire.core.library.decorator import library

# Component registries — each lives with its component, not under library/
from haywire.core.node.registry import NodeRegistry
from haywire.core.types.registry import TypeRegistry
from haywire.core.adapter.registry import AdapterRegistry
from haywire.ui.widget.registry import WidgetRegistry
from haywire.ui.skin.registry import SkinRegistry
from haywire.ui.themes.registry import ThemeRegistry
```

(Older docs reference `haywire.core.library.library` and `haywire.core.library.registries.reg_*` — those paths are out of date; registries live with the component, not under the library subpackage.)

**Hot-reload.** When `file_watcher=True`, the framework starts a `watchdog` observer rooted at your library's source directory. On any `.py` change:

1. The `BaseRegistry._on_change` pipeline re-imports the changed module.
2. Decorators re-run, registering new class versions under the same `registry_key`.
3. Existing wrappers (NodeWrapper, EdgeWrapper) rebuild from their recipes against the new class.
4. The graph revalidates; the UI re-renders.

Hot-reload only works for **editable** installs (`uv pip install -e .`) or **folder-loaded** libraries — `REGULAR` (pip-installed-from-wheel) installs don't have a writable source path, so the file watcher has nothing to watch. See [architecture/library-system](../../architecture/library-system/library-system-arch.md) for the install-type rules and [architecture/hot-reload](../../architecture/hot-reload/hot-reload-arch.md) for the full pipeline.

**`__all__` is required.** Export the `Library` class so the entry point can find it:

```python
# In your library's __init__.py
@library(label='My Library', id='my_library')
class Library(BaseLibrary):
    ...

__all__ = ['Library']
```

**The Library *class* is what the entry point points at — not an instance.** The framework instantiates it.

## 4. Live example from the codebase

Source: [`barn/haybale-testing/haybale_testing/__init__.py`](../../../barn/haybale-testing/haybale_testing/__init__.py)

`haybale_testing` is the framework's own test library — it registers all nine component categories (types, adapters, themes, widgets, skins, settings, nodes, panels, state), enables hot-reload, and includes a `validate()` that always passes. It is the most complete `Library` subclass in the codebase:

```python
--8<-- "barn/haybale-testing/haybale_testing/__init__.py:testing_library"
```

The companion `pyproject.toml` (full coverage in [components/haybale-package](../haybale-package/haybale-package-canon.md)):

```toml
[project]
name = "haybale-mylib"
version = "1.0.0"
requires-python = ">=3.10"
dependencies = ["haywire-core>=0.1.0"]

[project.entry-points."haywire.libraries"]
mylib = "haybale_mylib:Library"

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[tool.hatch.build.targets.wheel]
packages = ["haybale_mylib"]
```

What this example exercises:

| Concept | Where |
|---|---|
| `@library(label=..., id=..., version=..., file_watcher=True)` | decoration |
| Stable `id=` — becomes prefix of every component's `registry_key` | `id='testing'` |
| Required parens on every component decorator | `@library(...)` |
| `BaseLibrary` subclass with the two required hooks | `Library(BaseLibrary)` |
| `register_components` calling `add_folder_to_registry` per category | nine calls, one per folder |
| `validate()` returning `True` unconditionally | `def validate(self) -> bool` |
| `__all__` exporting the Library class for the entry point | last line |
| Imports from canonical paths (not the obsolete `library/library` / `library/registries/`) | every import |
| Hot-reload via `file_watcher=True` | `@library(file_watcher=True)` |

For the `pyproject.toml` shape, build/publish workflow, distribution via `marketplace.toml`, and the full commands for `uv pip install -e .` etc., see [components/haybale-package](../haybale-package/haybale-package-canon.md). For the runtime infrastructure that loads your Library, see [architecture/library-system](../../architecture/library-system/library-system-arch.md). For the studio's in-app library manager UI, see [architecture/library-manager](../../architecture/library-manager/library-manager-arch.md).

---

## Quick reference

### Authoring checklist

- [ ] One `Library` class per haybale package, in the package's `__init__.py`
- [ ] `@library(label='...', id='...', file_watcher=True)` — parens always required
- [ ] Inherit from `BaseLibrary`
- [ ] Implement `register_components(self)` — call `add_folder_to_registry` per category
- [ ] Implement `validate(self) -> bool` — return `False` to abort loading
- [ ] Add `__all__ = ['Library']` to the module
- [ ] Pick a stable `id=` — changing it later breaks saved graphs
- [ ] Match folder layout to convention: `types/`, `adapters/`, `nodes/`, `widgets/`, `skins/`, `themes/`

### Imports

```python
from haywire.core.library.base import BaseLibrary
from haywire.core.library.decorator import library
from haywire.core.node.registry import NodeRegistry
from haywire.core.types.registry import TypeRegistry
from haywire.core.adapter.registry import AdapterRegistry
from haywire.ui.widget.registry import WidgetRegistry
from haywire.ui.skin.registry import SkinRegistry
from haywire.ui.themes.registry import ThemeRegistry
```

### Common pitfalls

| Pitfall | Why it matters |
|---|---|
| Using bare `@library` without parens | Unsupported — must always invoke with `()` |
| Importing from `haywire.core.library.library` | Out of date — use `haywire.core.library.base` |
| Importing registries from `haywire.core.library.registries.reg_*` | Out of date — registries live with their components |
| Changing `id=` after publishing | Breaks saved graphs that reference `<old_id>:node:my_node` |
| `file_watcher=True` on a non-editable install | No effect — pip-from-wheel installs have no watchable source |
| Importing the `Library` class from a submodule of the same package | Causes circular imports — register decorators handle discovery |
