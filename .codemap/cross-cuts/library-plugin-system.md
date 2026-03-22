# Cross-cut: Library Plugin System

## Overview

Haywire discovers node libraries at runtime via Python's `importlib.metadata` entry points.
Any Python package that declares itself under `haywire.libraries` in its `pyproject.toml`
will be automatically loaded when the app starts.

---

## Registration Mechanism

In `pyproject.toml` of the library package:

```toml
[project.entry-points."haywire.libraries"]
my_library = "my_package:MyLibraryClass"
```

Discovery code: `packages/haywire-core/src/haywire/core/library/discovery.py`
Registry: `packages/haywire-core/src/haywire/core/library/registry.py`

---

## BaseLibrary Contract

Every library must:

1. Define a class decorated with `@library(...)` inheriting `BaseLibrary`
2. Implement `register_components()` to scan folders into registries

```python
from haywire.core.library import library, BaseLibrary

@library(name="my-library", version="1.0.0", file_watcher=True)
class MyLibrary(BaseLibrary):
    def register_components(self) -> None:
        self.scan_nodes("my_package/nodes")
        self.scan_types("my_package/types")
        self.scan_adapters("my_package/adapters")
        self.scan_skins("my_package/skins")
        self.scan_widgets("my_package/widgets")
        self.scan_themes("my_package/themes")
```

---

## Component Registration Order (matters for haybale-studio)

For libraries contributing panels with scopes (like haybale-studio), scope registration
**must precede** folder scanning:

```python
def register_components(self) -> None:
    # 1. Register scope tabs first
    for scope in PROPERTIES_SCOPES:
        self.panel_registry.register_scope('properties', scope)
    # 2. Then scan panels (so @panel decorators can reference the scopes)
    self.scan_panels("haybale_studio/panels")
```

---

## Hot-Reload

`file_watcher=True` on the `@library` decorator enables hot-reload for editable installs.
File changes trigger `library.disable()` → `library.enable()` cycle, which unregisters
all components and re-registers them from disk.

Only works for packages installed with `uv pip install -e .` (editable mode).

---

## DI Integration

`LibraryRegistry` is a DI singleton provided by `HaywireModule`. Libraries are loaded
after the injector is created. Test configs use `TestHaywireModule` with library paths
defaulting to `[]` — pass explicit paths to load test libraries.

---

## Related Source Files

- Base class: `packages/haywire-core/src/haywire/core/library/base.py`
- Decorator: `packages/haywire-core/src/haywire/core/library/decorator.py`
- Discovery: `packages/haywire-core/src/haywire/core/library/discovery.py`
- Registry: `packages/haywire-core/src/haywire/core/library/registry.py`
- File watcher: `packages/haywire-core/src/haywire/core/library/file_watcher.py`
- DI config: `packages/haywire-core/src/haywire/core/di/config.py`
