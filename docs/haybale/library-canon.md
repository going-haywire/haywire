---
status: draft
doc_template: canonical-example
scope: Authoring a Library — BaseLibrary subclass, @library decorator, register_components, validate, hot-reload
see-also:
  - haybale-package-canon.md
  - ../architecture/library-system/library-system-arch.md
  - ../architecture/hot-reload/hot-reload-arch.md
  - ../reference/glossary.md
---

# Library — Canonical Example

## 1. What it solves

A **Library** (the haywire `BaseLibrary` subclass, decorated with `@library`) is the plugin protocol that contributes nodes, types, adapters, widgets, skins, themes, and settings to a running haywire app. As an author, you write one Library class per haybale package — the framework discovers it through the `pyproject.toml` entry point, calls `register_components()` to populate the global registries, and (optionally) starts a file watcher so your changes hot-reload without restart.

This is meaning **#1** of the five "library" concepts in haywire (see [reference/glossary §Library — five distinct meanings](../reference/glossary.md#library-five-distinct-meanings)). For the runtime infrastructure that *uses* your Library class (LibraryRegistry, LibraryDiscovery, FileWatcher), see [architecture/library-system](../architecture/library-system/library-system-arch.md). For packaging a Library as a distributable Haybale package (pyproject layout, entry points, publishing), see [haybale/haybale-package](haybale-package-canon.md).

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

**Boundaries.** What the registries actually do at runtime, what `LibraryDiscovery` checks, how `InstallType` is determined, the discovery priority order — all in [architecture/library-system](../architecture/library-system/library-system-arch.md). The `pyproject.toml` shape, build/publish workflow, and `marketplace.toml` distribution — all in [haybale/haybale-package](haybale-package-canon.md).

## 3. Important concepts

**The `@library` decorator.** Sets `class_identity` (a `LibraryIdentity`), records the metadata, and registers the file watcher when `file_watcher=True`. **The bare `@library` form (no parens) is not supported** — always invoke with parentheses, even when only `label=` is given.

| Parameter | Required | Default | Purpose |
|---|---|---|---|
| `label` | yes | — | Human-readable display name |
| `id` | no | derived from `label` | Unique identifier (becomes part of every component's `registry_key`) |
| `version` | no | `'1.0.0'` | Semantic version — see SemVer guidance below |
| `description` | no | `''` | Description for the library manager UI |
| `file_watcher` | no | `False` | Enable hot-reload via filesystem observer |
| `dependencies` | no | `[]` | List of required library IDs (currently informational only — load order is by discovery priority, not dependency graph) |
| `url` | no | `''` | Library website |
| `help_url` | no | `''` | Documentation URL |
| `author` | no | `''` | Author name |
| `author_url` | no | `''` | Author homepage |

**SemVer for the `version` field.** Follow [Semantic Versioning](https://semver.org/) when publishing updates:

| Bump | When |
|---|---|
| **MAJOR** (1.0.0 → 2.0.0) | Breaking changes — renamed nodes, changed port types, removed components |
| **MINOR** (1.0.0 → 1.1.0) | New features, backward-compatible — added nodes, optional fields |
| **PATCH** (1.0.0 → 1.0.1) | Bug fixes only, no API changes |

Keep `version=` in the `@library(...)` decorator in sync with the `version` field in `pyproject.toml` — they are independent strings; mismatching them confuses the library manager UI.

**Naming conventions.** Each of the four names in a haybale project has its own casing rule:

| Name | Convention | Example |
| --- | --- | --- |
| Pip distribution name (`name` in `pyproject.toml`) | `haybale-<lowercase-hyphenated>` | `haybale-image-tools` |
| Python module name (importable package folder) | `haybale_<lowercase_underscored>` | `haybale_image_tools` |
| Library `id` field | lowercase, underscores OK; should match module name without `haybale_` prefix | `image_tools` |
| Display `label` field | Human-readable, title-case | `"Image Tools"` |

The `id` is stable across releases — it becomes the prefix for every component's `registry_key` (e.g., `image_tools:node:Resize`). Changing it after publishing breaks saved graphs.

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

**All ten registries and their folder conventions.** Each call to `add_folder_to_registry()` targets one registry class. The full set available to a library author:

| Registry class | Import path | Folder convention | What it registers |
| --- | --- | --- | --- |
| `NodeRegistry` | `haywire.core.node.registry` | `nodes/` | `@node`-decorated classes |
| `TypeRegistry` | `haywire.core.types.registry` | `types/` | `@type`-decorated classes |
| `AdapterRegistry` | `haywire.core.adapter.registry` | `adapters/` | `@adapter`-decorated classes |
| `WidgetRegistry` | `haywire.ui.widget.registry` | `widgets/` | `@widget`-decorated classes |
| `SkinRegistry` | `haywire.ui.skin.registry` | `skins/` | skin classes |
| `ThemeRegistry` | `haywire.ui.themes.registry` | `themes/` | `WorkbenchTheme` / `NodeTheme` subclasses |
| `SettingsRegistry` | `haywire.core.settings.registry` | `settings/` | `@settings`-decorated `LibrarySettings` classes |
| `LibraryStateRegistry` | `haywire.core.state` | `state/` | `AppState` / `SessionState` subclasses |
| `EditorTypeRegistry` | `haywire.ui.editor.registry` | `editors/` | `@editor`-decorated classes |
| `PanelRegistry` | `haywire.ui.panel.registry` | `panels/` | `@panel`-decorated classes |

Most libraries only need the first six. `SettingsRegistry`, `LibraryStateRegistry`, `EditorTypeRegistry`, and `PanelRegistry` are needed for libraries that contribute studio UI or persistent state. See `barn/haybale-studio/haybale_studio/__init__.py` for the canonical example that registers all ten. The architecture-side view (how `LibraryRegistry` routes into each registry at startup) is in [architecture/library-system §2.2](../architecture/library-system/library-system-arch.md#22-libraryregistry-haywirecorelibrary).

**Hot-reload.** When `file_watcher=True`, the framework starts a `watchdog` observer rooted at your library's source directory. On any `.py` change:

1. The `BaseRegistry._on_change` pipeline re-imports the changed module.
2. Decorators re-run, registering new class versions under the same `registry_key`.
3. Existing wrappers (NodeWrapper, EdgeWrapper) rebuild from their recipes against the new class.
4. The graph revalidates; the UI re-renders.

Hot-reload only works for **editable** installs (`uv pip install -e .`) or **folder-loaded** libraries — `REGULAR` (pip-installed-from-wheel) installs don't have a writable source path, so the file watcher has nothing to watch. Note that `file_watcher=True` on the decorator is a **per-library switch**; the system-level switch `enable_file_watching` in `create_library_system_service()` must also be `True` (it is `True` by default in `haywire-studio`) — if it is `False`, no hot-reload fires regardless of the decorator. See [architecture/library-system §5](../architecture/library-system/library-system-arch.md#5-programmatic-embedding) for the `enable_file_watching` and `debounce_delay` parameters, and [architecture/hot-reload](../architecture/hot-reload/hot-reload-arch.md) for the full pipeline.

**`__all__` is required.** Export the `Library` class so the entry point can find it:

```python
# In your library's __init__.py
@library(label='My Library', id='my_library')
class Library(BaseLibrary):
    ...

__all__ = ['Library']
```

**The Library *class* is what the entry point points at — not an instance.** The framework instantiates it.

## 4. Minimal working example

The smallest valid Library class — one registry call, `validate()` that always passes:

```python
# haybale_minimal/__init__.py — the minimum viable Library

from pathlib import Path

from haywire.core.library.base import BaseLibrary
from haywire.core.library.decorator import library
from haywire.core.node.registry import NodeRegistry


@library(label='Minimal', id='minimal')
class Library(BaseLibrary):
    def register_components(self):
        self.add_folder_to_registry(
            folder_path=str(Path(__file__).parent / 'nodes'),
            registry_cls=NodeRegistry,
        )

    def validate(self) -> bool:
        return True


__all__ = ['Library']
```

The matching minimal `pyproject.toml`:

```toml
[project]
name = "haybale-minimal"
version = "1.0.0"
requires-python = ">=3.10"
dependencies = ["haywire-core>=0.1.0"]

[project.entry-points."haywire.libraries"]
minimal = "haybale_minimal:Library"

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[tool.hatch.build.targets.wheel]
packages = ["haybale_minimal"]
```

For a maximally complete example that registers all ten component categories, see below.

## 5. Live example from the codebase

Source: [`barn/haybale-testing/haybale_testing/__init__.py`](../../barn/haybale-testing/haybale_testing/__init__.py)

`haybale_testing` is the framework's own test library — it registers all nine component categories (types, adapters, themes, widgets, skins, settings, nodes, panels, state), enables hot-reload, and includes a `validate()` that always passes. It is the most complete `Library` subclass in the codebase:

```python
--8<-- "barn/haybale-testing/haybale_testing/__init__.py:testing_library"
```

The companion `pyproject.toml` (full coverage in [haybale/haybale-package](haybale-package-canon.md)):

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

For the `pyproject.toml` shape, build/publish workflow, distribution via `marketplace.toml`, and the full commands for `uv pip install -e .` etc., see [haybale/haybale-package](haybale-package-canon.md). For the runtime infrastructure that loads your Library, see [architecture/library-system](../architecture/library-system/library-system-arch.md). For the studio's in-app library manager UI, see [haybale/marketplace](marketplace/haybale-marketplace-arch.md).

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

---

## Troubleshooting

### Library not discovered

The library does not appear in the canvas node menu or the library manager UI.

1. **Verify the package is installed:**

   ```bash
   uv pip list | grep haybale-
   ```

   If your library is missing, run `uv pip install -e .` (editable) or `uv pip install .` from the library's directory.

2. **Check the entry point is registered:**

   ```bash
   python -c "from importlib.metadata import entry_points; print([ep.name for ep in entry_points(group='haywire.libraries')])"
   ```

   Your library's entry-point name (the key in `[project.entry-points."haywire.libraries"]`) should appear. If it does not, the package was not installed with entry-point metadata — re-install it.

3. **Verify the Library class loads:**

   ```bash
   python -c "from haybale_mylib import Library; print(Library.class_identity)"
   ```

   Replace `haybale_mylib` with your module name. An import error here means the module is broken independently of Haywire.

4. **Watch app startup logs** — look for lines like `✓ Found pip install: haybale-mylib` (found) or `ERROR: Failed to load entry point …` (entry point found but the import raised). A `LibraryLoadError` in the logs means the library was discovered but failed during `register_components()` or `validate()`.

### Hot-reload not working

File edits do not trigger a canvas refresh.

1. **Confirm editable install:**

   ```bash
   uv pip list --editable | grep haybale-
   ```

   Regular (non-editable) installs have no live source path — the file watcher has nothing to watch.

2. **Confirm `file_watcher=True` in the `@library` decorator:**

   ```python
   @library(label='My Library', id='my_library', file_watcher=True)
   ```

   Without this, no watcher is started for this library regardless of system settings.

3. **Confirm the system-level switch is on** — in `haywire-studio` this is controlled by `enable_file_watching` in `app.py` (defaults to `True` in development mode). If you embedded Haywire via `create_library_system_service()`, make sure you passed `enable_file_watching=True` (the default). When it is `False`, no hot-reload fires for any library.

4. **Check for silent reload failures** — a syntax error in a reloaded module causes the reload to fail silently (the old class version stays registered). After saving a file, check the app logs for `ERROR` lines. Fix the syntax error and save again.

### Same library loaded from the wrong source

The library manager shows the right library but you are editing the wrong copy.

Check the **Source** path printed at startup for each library (e.g., `Source: /path/to/haybale_mylib`). If it points to `site-packages` instead of your development checkout, you have two copies installed — one editable and one regular. Uninstall the regular copy (`uv pip uninstall haybale-mylib`) and re-install as editable (`uv pip install -e .`).
