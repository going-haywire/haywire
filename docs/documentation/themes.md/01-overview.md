# Theme System Overview

---

## Two Theme Types

### WorkbenchTheme

Controls the visual appearance of the **application shell** — backgrounds, text colours,
borders, sidebar, topbar, status bar, console, canvas, etc. Values are injected as CSS
custom properties on `:root` so they cascade everywhere.

### NodeTheme

Controls the appearance of **node chips** on the graph canvas — header colour, port colours,
error state colours, etc. Values are consumed directly by the node renderer (JavaScript /
canvas layer).

---

## CSS Token Map

`WorkbenchTheme` defines `_CSS_TOKEN_MAP` mapping Python field names → CSS variable names:

| Field | CSS variable | Used for |
|-------|-------------|---------|
| `bg_page` | `--hw-bg-page` | Page/root background |
| `bg_surface` | `--hw-bg-surface` | Cards, panels |
| `bg_sidebar` | `--hw-bg-sidebar` | Left/right sidebars |
| `bg_elevated` | `--hw-bg-elevated` | Dropdowns, tooltips |
| `bg_overlay` | `--hw-bg-overlay` | Modal overlays |
| `bg_input` | `--hw-bg-input` | Input fields |
| `border` | `--hw-border` | Subtle borders |
| `border_strong` | `--hw-border-strong` | Visible dividers |
| `text_body` | `--hw-text-body` | Primary text |
| `text_muted` | `--hw-text-muted` | Secondary text |
| `text_dim` | `--hw-text-dim` | Placeholder, captions |
| `text_expansion` | `--hw-text-expansion` | Expandable section labels |
| `text_on_accent` | `--hw-text-on-accent` | Text on accent-coloured buttons |
| `accent` | `--hw-accent` | Interactive elements, focus rings |
| `accent_hover` | `--hw-accent-hover` | Hover state |
| `accent_active` | `--hw-accent-active` | Active/pressed state |
| `danger` | `--hw-danger` | Error indicators |
| `warning` | `--hw-warning` | Warning indicators |
| `success` | `--hw-success` | Success indicators |
| `info` | `--hw-info` | Info indicators |
| `node_bg` | `--hw-node-bg` | Node body background |
| `node_border` | `--hw-node-border` | Node border |
| `node_header_bg` | `--hw-node-header-bg` | Node header background |
| `node_header_text` | `--hw-node-header-text` | Node header text |
| `node_selected` | `--hw-node-selected` | Selected node highlight |
| `node_shadow` | `--hw-node-shadow` | Node drop shadow |
| `edge_default` | `--hw-edge-default` | Default edge colour |
| `edge_selected` | `--hw-edge-selected` | Selected edge colour |
| `canvas_bg` | `--hw-canvas-bg` | Canvas background |
| `canvas_grid` | `--hw-canvas-grid` | Canvas grid lines |
| `topbar_bg` | `--hw-topbar-bg` | Top bar background |
| `topbar_text` | `--hw-topbar-text` | Top bar text |
| `sidebar_bg` | `--hw-sidebar-bg` | Activity bar background |
| `sidebar_icon` | `--hw-sidebar-icon` | Inactive activity icon |
| `sidebar_icon_active` | `--hw-sidebar-icon-active` | Active activity icon |
| `panel_bg` | `--hw-panel-bg` | Side panel background |
| `panel_text` | `--hw-panel-text` | Side panel text |
| `statusbar_bg` | `--hw-statusbar-bg` | Status bar background |
| `statusbar_text` | `--hw-statusbar-text` | Status bar text |
| `console_bg` | `--hw-console-bg` | Console background |
| `console_text` | `--hw-console-text` | Console text |

---

## ThemeRegistry

`ThemeRegistry` extends `BaseRegistry` with typed registration and lookup helpers:

```python
from haywire.ui.themes.theme_registry import ThemeRegistry

# Accessing the registry (inside a panel or editor)
theme_registry: ThemeRegistry = context.metadata.get('theme_registry')

# List available themes (returns registry_keys)
workbench_keys = theme_registry.list_workbench_keys()   # ['core:theme:workbench:haywire-dark', ...]
node_keys      = theme_registry.list_node_theme_keys()  # ['core:theme:node:default', ...]

# Instantiate a theme by registry_key (returns fresh instance each call — stateless)
theme = theme_registry.get_workbench('core:theme:workbench:haywire-dark')
css   = theme.to_css_vars()   # {--hw-bg-page: '#12121e', ...}
```

---

## CSS Application

`AppShell` calls `apply_workbench_theme()` when the user switches themes:

```python
async def apply_workbench_theme(self, registry_key: str):
    theme = self._theme_registry.get_workbench(registry_key)
    context.active_workbench_theme_key = registry_key
    for token, value in theme.to_css_vars().items():
        await ui.run_javascript(
            f"document.documentElement.style.setProperty('{token}', '{value}')"
        )
```

The initial theme CSS is injected as `<style>` in the `:root` block during page load from
the `workbench.theme` global setting.

---

## Next Steps

- **[02-workbench-themes.md](02-workbench-themes.md)** — Creating WorkbenchTheme subclasses
- **[03-node-themes.md](03-node-themes.md)** — Creating NodeTheme subclasses
- **[04-library-themes.md](04-library-themes.md)** — Shipping themes from haybale libraries
