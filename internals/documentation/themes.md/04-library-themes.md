# Library Themes Guide

This guide covers how to package and ship WorkbenchTheme and NodeTheme classes from a
haybale library plugin, including hot-reload support.

---

## File Layout

```
my-haybale/
├── haybale_mylib/
│   ├── __init__.py           # BaseLibrary subclass
│   ├── themes/
│   │   ├── __init__.py
│   │   ├── workbench.py      # WorkbenchTheme subclasses
│   │   └── node.py           # NodeTheme subclasses
│   └── nodes/
│       └── ...
└── pyproject.toml
```

---

## Defining Themes

### workbench.py

```python
# haybale_mylib/themes/workbench.py
from haywire.ui.themes.workbench import WorkbenchTheme
from haywire.ui.themes.decorator import theme


@theme(label='My Library — Dark')
class MyLibDarkTheme(WorkbenchTheme):
    bg_page    = '#0e0e18'
    bg_surface = '#18182a'
    accent     = '#9b59b6'
    text_body  = 'rgba(240,230,255,0.87)'
    # ... all other tokens
```

### node.py

```python
# haybale_mylib/themes/node.py
from haywire.ui.themes.node_theme import NodeTheme
from haywire.ui.themes.decorator import theme


@theme(label='My Library — Nodes')
class MyLibNodeTheme(NodeTheme):
    header_bg   = '#1a0a2e'
    header_text = '#d8b4fe'
    body_bg     = '#120820'
    port_inlet  = '#9b59b6'
    port_outlet = '#e67e22'
    # ...
```

---

## Registering in `register_components()`

```python
# haybale_mylib/__init__.py
from haywire.core.node import BaseLibrary, library
from haywire.ui.themes.theme_registry import ThemeRegistry


@library(label='My Library')
class MyLibrary(BaseLibrary):

    def register_components(self, registries):
        # Register themes
        theme_registry: ThemeRegistry = registries.get(ThemeRegistry)
        if theme_registry:
            from .themes.workbench import MyLibDarkTheme
            from .themes.node import MyLibNodeTheme
            theme_registry.register_workbench(MyLibDarkTheme)
            theme_registry.register_node_theme(MyLibNodeTheme)

        # Register nodes, settings, etc.
        ...
```

---

## Hot-Reload

`ThemeRegistry` extends `BaseRegistry`, which supports hot-reload via the library system.
When a library is reloaded (e.g. after editing theme files in a dev install):

1. `ThemeRegistry._unregister_class(registry_key)` removes the old theme class.
2. `register_components()` is called again, registering the updated theme class.
3. The active theme is re-applied to all connected sessions.

No additional code is required in the library — `BaseRegistry` handles this.

---

## Declaring Theme Support in pyproject.toml

Library metadata is declared in `pyproject.toml`. Theme support doesn't require a separate
entry point — it is discovered automatically when `register_components()` is called.

```toml
[project]
name = "haybale-mylib"
# ...

[project.entry-points."haywire.libraries"]
mylib = "haybale_mylib:MyLibrary"
```

---

## Multiple Themes from One Library

A library can register any number of workbench and node themes:

```python
theme_registry.register_workbench(MyLibDarkTheme)
theme_registry.register_workbench(MyLibLightTheme)
theme_registry.register_workbench(MyLibHighContrastTheme)
theme_registry.register_node_theme(MyLibNodeTheme)
theme_registry.register_node_theme(MyLibMinimalNodeTheme)
```

Themes from multiple libraries are merged in `ThemeRegistry` — ids must be globally unique.

---

## Documenting Themes for Users

Provide a reference TOML file alongside your library so users can see all available tokens
and create partial overrides:

```
my-haybale/
└── internals/
    └── themes/
        ├── mylib-dark.toml     # all tokens for dark theme
        └── mylib-nodes.toml    # all tokens for node theme
```

---

## Testing Library Theme Registration

```python
import pytest
from haywire.ui.themes.theme_registry import ThemeRegistry
from haybale_mylib.themes.workbench import MyLibDarkTheme
from haybale_mylib.themes.node import MyLibNodeTheme


@pytest.fixture
def theme_registry():
    r = ThemeRegistry()
    r.register_workbench(MyLibDarkTheme)
    r.register_node_theme(MyLibNodeTheme)
    return r


def test_workbench_theme_registered(theme_registry):
    assert MyLibDarkTheme.class_identity.registry_key in theme_registry.list_workbench_keys()


def test_node_theme_registered(theme_registry):
    assert MyLibNodeTheme.class_identity.registry_key in theme_registry.list_node_theme_keys()


def test_workbench_css_vars(theme_registry):
    theme = theme_registry.get_workbench(MyLibDarkTheme.class_identity.registry_key)
    css = theme.to_css_vars()
    assert css.get('--hw-bg-page') == '#0e0e18'
    assert all(k.startswith('--hw-') for k in css)


def test_node_colors(theme_registry):
    theme = theme_registry.get_node_theme(MyLibNodeTheme.class_identity.registry_key)
    assert theme.get_color('header_bg') == '#1a0a2e'
    assert theme.get_color('port_inlet') == '#9b59b6'
```

---

## Checklist

- [ ] `@theme(label=...)` decorator applied to WorkbenchTheme subclass
- [ ] `@theme(label=...)` decorator applied to NodeTheme subclass
- [ ] All tokens defined (or explicitly inherited from a base class)
- [ ] `register_components()` calls `theme_registry.register_workbench()` / `register_node_theme()`
- [ ] `registry_id` values are unique within the library (prefix with library name, e.g. `mylib-dark`)
- [ ] Tests pass: `uv run pytest tests/`
- [ ] Reference TOML file provided in docs

---

## Next Steps

- **[01-overview.md](01-overview.md)** — Full CSS token reference and ThemeRegistry API
- **[02-workbench-themes.md](02-workbench-themes.md)** — WorkbenchTheme field guide
- **[03-node-themes.md](03-node-themes.md)** — NodeTheme field guide
