# Haywire Theme System

The Haywire theme system controls the visual appearance of the application shell and node
rendering. Two independent theme types are supported:

| Type | Class | Registry key prefix | Controlled by |
|------|-------|---------------------|---------------|
| Workbench | `WorkbenchTheme` | `__haywire__:theme:workbench:` | CSS custom properties on `:root` |
| Node | `NodeTheme` | `__haywire__:theme:node:` | Node renderer colour tokens |

---

## Quick Start

```python
from haywire.ui.themes.workbench import WorkbenchTheme
from haywire.ui.themes.node_theme import NodeTheme
from haywire.ui.themes.decorator import theme


@theme(registry_id='my-dark', label='My Dark Theme')
class MyDarkTheme(WorkbenchTheme):
    bg_page    = '#0d0d17'
    bg_surface = '#1a1a2e'
    accent     = '#6c63ff'
    text_body  = 'rgba(255,255,255,0.87)'
    # ... other tokens


@theme(registry_id='my-nodes', label='My Node Theme')
class MyNodeTheme(NodeTheme):
    header_bg   = '#1a1a2e'
    header_text = '#e0e0f0'
    body_bg     = '#141424'
    port_inlet  = '#5590e0'
    port_outlet = '#e05555'
```

Register with the app:

```python
from haywire.ui.themes.theme_registry import ThemeRegistry

def register_components(self, registries):
    theme_registry: ThemeRegistry = registries.get(ThemeRegistry)
    if theme_registry:
        theme_registry.register_workbench(MyDarkTheme)
        theme_registry.register_node_theme(MyNodeTheme)
```

---

## Active Theme Selection

The active theme is controlled by two global settings:

```toml
# ~/.haywire/settings.toml
[workbench]
theme = "mylib:theme:workbench:my-dark"   # workbench theme registry_key

[node]
theme = "mylib:theme:node:my-nodes"       # node theme registry_key
```

Users can switch themes at runtime via the Settings panel — changes apply immediately
without a page reload.

---

## Architecture

```
ThemeRegistry (BaseRegistry)
├── WorkbenchTheme subclasses  →  to_css_vars()  →  :root { --hw-* }
└── NodeTheme subclasses       →  get_color()    →  node renderer tokens
```

- `WorkbenchTheme` fields are **plain string class attributes** (not `setting()` descriptors).
  `__init_subclass__` wraps them into `_FieldProxy` objects collected in `_fields`.
- `NodeTheme` uses the same mechanism.
- `ThemeRegistry` follows the same `BaseRegistry` pattern as `NodeRegistry`,
  `EditorTypeRegistry`, and `GlobalSettingsRegistry`.
- TOML data files in `haywire/ui/themes/data/` provide user-editable defaults that can be
  copied and customised without subclassing.

---

## Contents

| File | Topic |
|------|-------|
| [01-overview.md](01-overview.md) | Theme system architecture, CSS token map, ThemeRegistry |
| [02-workbench-themes.md](02-workbench-themes.md) | Creating WorkbenchTheme subclasses |
| [03-node-themes.md](03-node-themes.md) | Creating NodeTheme subclasses |
| [04-library-themes.md](04-library-themes.md) | Shipping themes from haybale libraries |
