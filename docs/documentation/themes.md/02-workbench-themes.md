# Workbench Themes

This guide covers creating and registering custom workbench themes.

---

## Anatomy of a WorkbenchTheme

```python
from haywire.ui.themes.workbench import WorkbenchTheme
from haywire.ui.themes.decorator import theme


@theme(label='Ocean Dark')
class OceanDarkTheme(WorkbenchTheme):
    """A deep-ocean dark theme."""

    # Backgrounds
    bg_page    = '#0a0f1a'
    bg_surface = '#0f1c2e'
    bg_sidebar = '#0d1726'
    bg_elevated = '#162337'
    bg_overlay = 'rgba(0,0,0,0.6)'
    bg_input   = '#0a0f1a'

    # Borders
    border       = 'rgba(255,255,255,0.08)'
    border_strong = '#2a4a6a'

    # Text
    text_body      = 'rgba(200,220,255,0.9)'
    text_muted     = 'rgba(200,220,255,0.55)'
    text_dim       = 'rgba(200,220,255,0.45)'
    text_expansion = 'rgba(200,220,255,0.75)'
    text_on_accent = '#ffffff'

    # Accent
    accent        = '#3498db'
    accent_hover  = '#5dade2'
    accent_active = '#1f6aa5'

    # Status
    danger  = '#e74c3c'
    warning = '#f39c12'
    success = '#2ecc71'
    info    = '#3498db'

    # Node chrome
    node_bg          = '#0f1c2e'
    node_border      = '#1a3050'
    node_header_bg   = '#162337'
    node_header_text = 'rgba(200,220,255,0.9)'
    node_selected    = '#3498db'
    node_shadow      = 'rgba(0,0,0,0.5)'

    # Edge
    edge_default  = '#2a4a6a'
    edge_selected = '#3498db'

    # Canvas
    canvas_bg   = '#060d18'
    canvas_grid = '#0d1726'

    # TopBar
    topbar_bg   = '#0a0f1a'
    topbar_text = 'rgba(200,220,255,0.9)'

    # Sidebar / ActivityBar
    sidebar_bg          = '#060d18'
    sidebar_icon        = '#3a5a7a'
    sidebar_icon_active = '#3498db'

    # Panel
    panel_bg   = '#0f1c2e'
    panel_text = 'rgba(200,220,255,0.87)'

    # StatusBar
    statusbar_bg   = '#0a2040'
    statusbar_text = 'rgba(200,220,255,0.7)'

    # Console
    console_bg   = '#060d18'
    console_text = '#4ade80'
```

---

## Rules

| Rule | Detail |
|------|--------|
| **Decorator required** | `@theme(...)` must appear before the class |
| **Unique `registry_id`** | Must not clash with existing ids within the same library (`haywire-dark`, `haywire-light`). Choose unique class names and let the `registry_id` be automatically derived. |
| **All fields optional** | Only define fields you want to override from the base class |
| **Values must be CSS strings** | Hex, rgba, hsl, named colours — anything valid as a CSS colour |
| **No `setting()` descriptors** | Fields are plain class attributes, not descriptors |

---

## Partial Themes (Override Only)

You can subclass an existing theme and override only the tokens you want:

```python
from haywire.ui.themes.builtin import HaywireDarkTheme


@theme(label='Dark — Red Accent')
class DarkRedAccentTheme(HaywireDarkTheme):
    """Haywire dark with a red accent colour."""
    accent        = '#e74c3c'
    accent_hover  = '#ec7063'
    accent_active = '#c0392b'
    node_selected = '#e74c3c'
    edge_selected = '#e74c3c'
```

---

## to_css_vars()

`to_css_vars()` returns the complete `{--hw-var: value}` dict by walking `_CSS_TOKEN_MAP`:

```python
theme = OceanDarkTheme()
css   = theme.to_css_vars()
# {'--hw-bg-page': '#0a0f1a', '--hw-accent': '#3498db', ...}
```

Fields defined in the class but NOT in `_CSS_TOKEN_MAP` are silently ignored.
Fields listed in `_CSS_TOKEN_MAP` but missing from `_fields` are also silently skipped —
so a partial theme subclass works correctly.

---

## Registration

### From a library plugin

```python
# my_lib/__init__.py
from haywire.core.node import BaseLibrary, library
from haywire.ui.themes.theme_registry import ThemeRegistry
from .themes import OceanDarkTheme


@library(label='My Library')
class MyLibrary(BaseLibrary):

    def register_components(self, registries):
        theme_registry: ThemeRegistry = registries.get(ThemeRegistry)
        if theme_registry:
            theme_registry.register_workbench(OceanDarkTheme)
```

### From framework code

```python
from haywire.core.di.config import HaywireModule

# Add to provide_theme_registry() in config.py
registry.register_workbench(OceanDarkTheme)
```

---

## Testing

```python
from haywire.ui.themes.theme_registry import ThemeRegistry
from my_lib.themes import OceanDarkTheme


def test_ocean_dark_theme():
    r = ThemeRegistry()
    r.register_workbench(OceanDarkTheme)

    theme = r.get_workbench(OceanDarkTheme.class_identity.registry_key)
    css = theme.to_css_vars()

    assert css['--hw-bg-page']  == '#0a0f1a'
    assert css['--hw-accent']   == '#3498db'
    assert all(k.startswith('--hw-') for k in css)
```

---

## Next Steps

- **[03-node-themes.md](03-node-themes.md)** — Creating NodeTheme subclasses
- **[04-library-themes.md](04-library-themes.md)** — Shipping themes from haybale libraries
